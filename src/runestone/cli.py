"""
Command-line interface for Runestone.

This module provides the main CLI commands and handles user interaction.
"""

import asyncio
import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from runestone.agent.tools.read_url import read_url
from runestone.api.schemas import VocabularyItemCreate
from runestone.config import Settings
from runestone.core.analyzer import ContentAnalyzer
from runestone.core.clients.factory import create_llm_client, get_available_providers
from runestone.core.console import setup_console
from runestone.core.exceptions import RunestoneError
from runestone.core.logging_config import setup_logging
from runestone.core.ocr import OCRProcessor
from runestone.core.processor import RunestoneProcessor
from runestone.core.prompt_builder.builder import PromptBuilder
from runestone.core.prompt_builder.types import ImprovementMode
from runestone.db.models import User
from runestone.db.user_repository import UserRepository
from runestone.db.vocabulary_repository import VocabularyRepository
from runestone.rag.index import GrammarIndex
from runestone.services.user_service import UserService
from runestone.services.vocabulary_service import VocabularyService

# Load environment variables from .env file
load_dotenv()

# Setup console
console = setup_console()

# Setup logging
setup_logging()

# Load centralized settings
settings = Settings()


@click.group()
@click.version_option(version="0.1.0", prog_name="runestone")
def cli():
    """
    Runestone - CLI tool for analyzing Swedish textbook pages.

    Transform phone photos of Swedish textbook pages into structured
    digital study guides with vocabulary, grammar explanations, and resources.
    """
    pass


@cli.command()
@click.argument("image_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--provider",
    type=click.Choice(get_available_providers()),
    envvar="LLM_PROVIDER",
    help=(
        f"LLM provider to use (default: {settings.llm_provider}). Can be set via " "LLM_PROVIDER environment variable."
    ),
)
@click.option(
    "--api-key",
    help=(
        "API key for the selected provider. If not provided, uses provider-specific "
        "environment variables (OPENAI_API_KEY or GEMINI_API_KEY)."
    ),
)
@click.option(
    "--model",
    help=(
        "Model name to use. If not provided, uses provider defaults (gpt-4o-mini for OpenAI, ). "
        "Can be set via OPENAI_MODEL environment "
        "variable for OpenAI."
    ),
)
@click.option(
    "--output-format",
    type=click.Choice(["console", "markdown"]),
    default="console",
    help="Output format (default: console)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    envvar="VERBOSE",
    help="Enable verbose output (can be set via VERBOSE environment variable)",
)
def process(
    image_path: Path,
    provider: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    output_format: str,
    verbose: bool,
):
    """
    Process a Swedish textbook page image and generate study materials.

    IMAGE_PATH: Path to the image file to process (.jpg, .png, etc.)

    Examples:
        runestone process /path/to/textbook_page.jpg
        runestone process --provider openai --api-key YOUR_KEY /path/to/textbook_page.jpg # noqa: E501
    """
    try:
        # Determine provider (use CLI arg, then settings, then default)
        if not provider:
            provider = settings.llm_provider

        # Get API key from CLI arg, then settings
        if not api_key:
            if provider == "openai":
                api_key = settings.openai_api_key
            elif provider == "openrouter":
                api_key = settings.openai_api_key

        # Validate API key is available
        if not api_key:
            if provider == "openai":
                console.print(
                    "[red]Error:[/red] OpenAI API key is required. "
                    "Set OPENAI_API_KEY environment variable or use --api-key option."
                )
                sys.exit(1)
            elif provider == "openrouter":
                console.print(
                    "[red]Error:[/red] Openrouter API key is required. "
                    "Set OPENROUTER_API_KEY environment variable or use --api-key option."
                )
                sys.exit(1)

        # Validate image file
        if not image_path.is_file():
            console.print(f"[red]Error:[/red] File not found at '{image_path}'")
            sys.exit(1)

        # Check if file is an image
        allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        if image_path.suffix.lower() not in allowed_extensions:
            console.print(
                f"[yellow]Warning:[/yellow] File '{image_path}' may not be an image file. "
                f"Supported formats: {', '.join(allowed_extensions)}"  # noqa: E501
            )

        # Override settings with CLI parameters if provided
        if api_key:
            # Temporarily override the appropriate API key in settings
            if provider == "openai":
                settings.openai_api_key = api_key
            elif provider == "openrouter":
                settings.openrouter_api_key = api_key

        if verbose:
            console.print(f"Processing image: {image_path}")
            console.print(f"Provider: {provider}")
            console.print(f"Output format: {output_format}")

        # Create LLM client with the specified provider
        llm_client = create_llm_client(
            settings=settings,
            provider=provider,
            model_name=model,
        )

        # Create OCR client (use dedicated OCR provider if configured, otherwise use main client)
        if settings.ocr_llm_provider:
            ocr_llm_client = create_llm_client(
                settings=settings,
                provider=settings.ocr_llm_provider,
                model_name=settings.ocr_llm_model_name,
            )
        else:
            ocr_llm_client = llm_client

        # Initialize components
        ocr_processor = OCRProcessor(settings, ocr_llm_client)
        content_analyzer = ContentAnalyzer(settings, llm_client)

        # For CLI, create a simple user object (id=1 for backward compatibility)
        mock_user = User(id=1, email="cli@runestone.local", name="CLI User", hashed_password="", timezone="UTC")

        # Create user service (minimal setup for CLI)
        user_repo = UserRepository.__new__(UserRepository)  # Create without db for minimal functionality
        vocab_repo = VocabularyRepository.__new__(VocabularyRepository)  # Create without db for minimal functionality
        user_service = UserService(user_repo, vocab_repo)

        # Create vocabulary service with mock LLM
        vocab_service = VocabularyService(vocab_repo, settings, llm_client)

        # Initialize processor with dependencies
        processor = RunestoneProcessor(
            settings=settings,
            ocr_processor=ocr_processor,
            content_analyzer=content_analyzer,
            vocabulary_service=vocab_service,
            user_service=user_service,
            verbose=verbose,
        )

        # Process the image
        # for tool we'll use default user_id=1
        result = processor.process_image(image_path, user=mock_user)

        # Output results
        if output_format == "console":
            processor.display_results_console(result)
        else:
            processor.display_results_markdown(result)

    except RunestoneError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        if verbose:
            console.print_exception()
        else:
            console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


@cli.command("read-url")
@click.argument("url")
def read_url_cli(url: str):
    """
    Fetch a URL and print simplified Markdown content.

    URL: The web page to fetch and extract.
    """
    try:
        markdown = asyncio.run(read_url.ainvoke({"url": url}))
        console.print(markdown)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("csv_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--db-name",
    default="state/runestone.db",
    help="Database file name (default: state/runestone.db)",
)
@click.option(
    "--skip-existence-check",
    is_flag=True,
    default=False,
    help="Skip checking for existing words before adding (allow duplicates)",
)
def load_vocab(csv_path: Path, db_name: str, skip_existence_check: bool):
    """
    Load vocabulary data from a CSV file into the database.

    CSV_PATH: Path to the CSV file to load (columns: word;translation;example)

    The command creates a backup of the existing database before adding new data.
    """
    try:
        # Parse CSV file
        items = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if len(row) >= 2:
                    word = row[0].strip()
                    translation = row[1].strip()
                    example = row[2].strip() if len(row) > 2 else None
                    if word and translation:
                        items.append(
                            VocabularyItemCreate(word_phrase=word, translation=translation, example_phrase=example)
                        )

        if not items:
            console.print("[yellow]Warning:[/yellow] No valid items found in CSV file.")
            return

        # Create database backup
        db_path = Path(db_name)
        if db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.with_name(f"{db_path.stem}_backup_{timestamp}.db")
            shutil.copy2(db_path, backup_path)
            console.print(f"Database backup created: {backup_path}")
        else:
            console.print("[yellow]Warning:[/yellow] Database file does not exist, skipping backup.")

        # Insert data into database using service
        engine = create_engine(f"sqlite:///{db_name}", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            # Create service with database session
            repo = VocabularyRepository(db)
            # Create LLM client for vocabulary service
            llm_client = create_llm_client(settings=settings)
            service = VocabularyService(repo, settings, llm_client)

            # Load vocabulary using service
            stats = service.load_vocab_from_csv(items, skip_existence_check, user_id=1)

            original_count = stats["original_count"]
            added_count = stats["added_count"]
            skipped_count = stats["skipped_count"]

            if skip_existence_check:
                if skipped_count > 0:
                    console.print(
                        f"[yellow]Warning:[/yellow] Skipped {skipped_count} duplicate items within the batch."
                    )
                console.print(
                    f"[green]Success:[/green] Processed {added_count} vocabulary items (inserted or updated)."
                )
            else:
                if skipped_count > 0:
                    console.print(f"[yellow]Warning:[/yellow] Skipped {skipped_count} duplicate vocabulary items.")
                console.print(f"[green]Success:[/green] Added {added_count} new vocabulary items.")

            console.print(f"Total processed: {original_count} items (added: {added_count}, skipped: {skipped_count})")
        finally:
            db.close()

    except FileNotFoundError:
        console.print(f"[red]Error:[/red] CSV file not found: {csv_path}")
        sys.exit(1)
    except csv.Error as e:
        console.print(f"[red]Error:[/red] CSV parsing error: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def test_prompts():
    """Test prompt building and display resulting prompts."""
    pass


@test_prompts.command()
def ocr():
    """Test OCR prompt building."""
    try:
        builder = PromptBuilder()
        prompt = builder.build_ocr_prompt()

        console.print("[bold cyan]OCR Prompt:[/bold cyan]")
        console.print("=" * 80)
        console.print(prompt)
        console.print("=" * 80)
        console.print(f"\n[green]Prompt length:[/green] {len(prompt)} characters")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@test_prompts.command()
@click.argument("text")
def analysis(text: str):
    """Test analysis prompt building with sample text."""
    try:
        builder = PromptBuilder()
        prompt = builder.build_analysis_prompt(text)

        console.print("[bold cyan]Analysis Prompt:[/bold cyan]")
        console.print("=" * 80)
        console.print(prompt)
        console.print("=" * 80)
        console.print(f"\n[green]Prompt length:[/green] {len(prompt)} characters")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@test_prompts.command()
@click.argument("word")
@click.option(
    "--mode",
    type=click.Choice(["example_only", "extra_info_only", "all_fields"]),
    default="example_only",
    help="Improvement mode: what fields to generate",
)
def vocabulary(word: str, mode: str):
    """Test vocabulary improvement prompt building."""
    try:
        builder = PromptBuilder()
        improvement_mode = ImprovementMode(mode)

        prompt = builder.build_vocabulary_prompt(word, improvement_mode)

        console.print(f"[bold cyan]Vocabulary Improvement Prompt (mode: {mode}):[/bold cyan]")
        console.print("=" * 80)
        console.print(prompt)
        console.print("=" * 80)
        console.print(f"\n[green]Word:[/green] {word}")
        console.print(f"[green]Mode:[/green] {mode}")
        console.print(f"[green]Prompt length:[/green] {len(prompt)} characters")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def rag():
    """RAG (Retrieval Augmented Generation) related commands."""
    pass


@rag.command(name="search")
@click.argument("query")
@click.option("--top-k", default=5, help="Number of results to return")
def rag_search(query: str, top_k: int):
    """Search grammar index for relevant pages."""
    try:
        index = GrammarIndex(settings.cheatsheets_dir, settings.frontend_url)
        results = index.search(query, top_k=top_k)

        console.print(f"\n🔍 Search results for: [bold cyan]{query}[/bold cyan]\n")
        if not results:
            console.print("No results found.")
        else:
            for i, doc in enumerate(results, 1):
                url = doc.metadata.get("url", "N/A")
                annotation = doc.metadata.get("annotation", "N/A")
                console.print(f"{i}. [bold]{annotation}[/bold]")
                console.print(f"   URL: {url}\n")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


def main():
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
