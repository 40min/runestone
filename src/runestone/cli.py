"""
Command-line interface for Runestone.

This module provides the main CLI commands and handles user interaction.
"""

import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from runestone.config import Settings
from runestone.core.clients.factory import get_available_providers
from runestone.core.console import setup_console
from runestone.core.exceptions import RunestoneError
from runestone.core.logging_config import setup_logging
from runestone.core.processor import RunestoneProcessor

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
        "Model name to use. If not provided, uses provider defaults (gpt-4o-mini for OpenAI, "
        "gemini-2.0-flash-exp for Gemini). Can be set via OPENAI_MODEL environment "
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
        runestone process --provider openai /path/to/textbook_page.jpg
        runestone process --provider gemini --api-key YOUR_KEY /path/to/textbook_page.jpg # noqa: E501
    """
    try:
        # Determine provider (use CLI arg, then settings, then default)
        if not provider:
            provider = settings.llm_provider

        # Get API key from CLI arg, then settings
        if not api_key:
            if provider == "openai":
                api_key = settings.openai_api_key
            elif provider == "gemini":
                api_key = settings.gemini_api_key

        # Validate API key is available
        if not api_key:
            if provider == "openai":
                console.print(
                    "[red]Error:[/red] OpenAI API key is required. "
                    "Set OPENAI_API_KEY environment variable or use --api-key option."
                )
                sys.exit(1)
            elif provider == "gemini":
                console.print(
                    "[red]Error:[/red] Gemini API key is required. "
                    "Set GEMINI_API_KEY environment variable or use --api-key option."
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

        if verbose:
            console.print(f"Processing image: {image_path}")
            console.print(f"Provider: {provider}")
            console.print(f"Output format: {output_format}")

        # Initialize processor with settings
        processor = RunestoneProcessor(
            settings=settings, provider=provider, api_key=api_key, model_name=model, verbose=verbose
        )

        # Process the image
        result = processor.process_image(image_path)

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


def main():
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
