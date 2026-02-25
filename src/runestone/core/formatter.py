"""
Output formatting module for Runestone results.

This module handles the presentation of analysis results using Rich for console output
and markdown for file output.
"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from runestone.schemas.analysis import ContentAnalysis
from runestone.schemas.ocr import OCRResult


class ResultFormatter:
    """Formats and displays Runestone analysis results."""

    def __init__(self, console: Console = None):
        """
        Initialize the result formatter.

        Args:
            console: Rich Console instance (creates new one if None)
        """
        self.console = console or Console()

    def format_console_output(
        self,
        ocr_result: OCRResult,
        analysis: ContentAnalysis,
    ) -> None:
        """
        Format and display results to console using Rich.

        Args:
            ocr_result: OCR processing results
            analysis: Content analysis results
        """
        # Header
        self.console.print()
        header_text = Text("🪨 Runestone - Swedish Textbook Analysis", style="bold magenta")
        self.console.print(Panel(header_text, box=box.DOUBLE))
        self.console.print()

        # Full recognized text section
        self._format_recognized_text(ocr_result)

        # Grammar focus section
        self._format_grammar_focus(analysis)

        # Word bank section
        self._format_vocabulary(analysis)

        # Footer
        self.console.print()
        footer_text = Text("✨ Analysis complete!", style="bold green")
        self.console.print(Panel(footer_text, box=box.ROUNDED))

    def _format_recognized_text(self, ocr_result: OCRResult) -> None:
        """Format the recognized text section."""
        text = ocr_result.transcribed_text or "No text extracted"

        # Truncate very long text for display
        display_text = text

        panel = Panel(
            display_text,
            title="📖 Full Recognized Text",
            title_align="left",
            border_style="blue",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def _format_grammar_focus(self, analysis: ContentAnalysis) -> None:
        """Format the grammar focus section."""
        grammar = analysis.grammar_focus
        topic = grammar.topic or "No topic identified"
        explanation = grammar.explanation or "No explanation available"
        has_rules = grammar.has_explicit_rules

        rule_type = "Explicit Rule" if has_rules else "Inferred Pattern"

        content = f"[bold cyan]Topic:[/bold cyan] {topic}\n"
        content += f"[bold cyan]Type:[/bold cyan] {rule_type}\n\n"
        content += f"[bold cyan]Explanation:[/bold cyan]\n{explanation}"

        panel = Panel(
            content,
            title="🎓 Grammar Focus",
            title_align="left",
            border_style="green",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def _format_vocabulary(self, analysis: ContentAnalysis) -> None:
        """Format the vocabulary section."""
        vocab_list = analysis.vocabulary

        if not vocab_list:
            content = "[italic]No vocabulary identified[/italic]"
        else:
            # Create a table for vocabulary
            table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            table.add_column("Svenska", style="cyan", no_wrap=True)
            table.add_column("English", style="white")

            for item in vocab_list:
                swedish = item.swedish or ""
                english = item.english or ""
                if swedish and english:
                    table.add_row(swedish, "-", english)

            content = table

        panel = Panel(
            content,
            title="🔑 Word Bank",
            title_align="left",
            border_style="yellow",
            box=box.ROUNDED,
        )
        self.console.print(panel)
        self.console.print()

    def format_markdown_output(
        self,
        ocr_result: OCRResult,
        analysis: ContentAnalysis,
    ) -> str:
        """
        Format results as markdown text.

        Args:
            ocr_result: OCR processing results
            analysis: Content analysis results
            resources: Learning resources

        Returns:
            Formatted markdown string
        """
        md_lines = []

        # Header
        md_lines.append("# 🪨 Runestone - Swedish Textbook Analysis")
        md_lines.append("")

        # Full recognized text
        md_lines.append("## 📖 Full Recognized Text")
        md_lines.append("")
        text = ocr_result.transcribed_text or "No text extracted"
        md_lines.append(f"```\n{text}\n```")
        md_lines.append("")

        # Grammar focus
        md_lines.append("## 🎓 Grammar Focus")
        md_lines.append("")
        grammar = analysis.grammar_focus
        topic = grammar.topic or "No topic identified"
        explanation = grammar.explanation or "No explanation available"
        has_rules = grammar.has_explicit_rules

        rule_type = "Explicit Rule" if has_rules else "Inferred Pattern"

        md_lines.append(f"**Topic:** {topic}")
        md_lines.append(f"**Type:** {rule_type}")
        md_lines.append("")
        md_lines.append("**Explanation:**")
        md_lines.append(explanation)
        md_lines.append("")

        # Vocabulary
        md_lines.append("## 🔑 Word Bank")
        md_lines.append("")
        vocab_list = analysis.vocabulary

        if not vocab_list:
            md_lines.append("*No vocabulary identified*")
        else:
            md_lines.append("| Svenska | English |")
            md_lines.append("|---------|---------|")
            for item in vocab_list:
                swedish = item.swedish or ""
                english = item.english or ""
                if swedish and english:
                    md_lines.append(f"| {swedish} | {english} |")
        md_lines.append("")

        # Resources
        md_lines.append("## 🔗 Extra Resources")
        md_lines.append("")

        return "\n".join(md_lines)
