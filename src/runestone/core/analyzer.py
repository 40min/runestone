"""
Content analysis module for Swedish textbook pages.

This module uses configurable LLM providers to analyze extracted text and identify
grammar rules, vocabulary, and generate learning resources.
"""

from typing import Optional

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel

from runestone.config import Settings
from runestone.core.exceptions import ContentAnalysisError
from runestone.core.logging_config import get_logger
from runestone.core.prompt_builder.builder import PromptBuilder
from runestone.schemas.analysis import ContentAnalysis


class ContentAnalyzer:
    """Analyzes Swedish textbook content using configurable LLM providers."""

    def __init__(
        self,
        settings: Settings,
        model: BaseChatModel,
        verbose: Optional[bool] = None,
    ):
        """
        Initialize the content analyzer.

        Args:
            settings: Centralized application settings
            model: LangChain chat model for processing. It must support
                `with_structured_output(ContentAnalysis)`.
            verbose: Enable verbose logging. If None, uses settings.verbose
        """
        # Use provided settings or create default
        self.settings = settings
        self.verbose = verbose if verbose is not None else self.settings.verbose
        self.logger = get_logger(__name__)

        self.model = model

        # Initialize prompt builder
        self.builder = PromptBuilder()

    async def analyze_content(self, extracted_text: str) -> ContentAnalysis:
        """
        Analyze Swedish textbook content to extract learning materials.

        Args:
            extracted_text: Raw text extracted from the textbook page

        Returns:
            ContentAnalysis object containing analyzed content with grammar, vocabulary, and resources

        Raises:
            ContentAnalysisError: If content analysis fails
        """
        try:
            # Build analysis prompt using PromptBuilder
            analysis_prompt = self.builder.build_analysis_prompt(extracted_text)

            self.logger.info(
                "[ContentAnalyzer] Analyzing content with provider=%s model=%s",
                self.settings.resolve_service_llm_provider(),
                self.settings.resolve_service_llm_model(),
            )
            structured_model = self.model.with_structured_output(
                ContentAnalysis,
                method="json_schema",
            )
            response = await structured_model.ainvoke(analysis_prompt)
            if isinstance(response, ContentAnalysis):
                return response
            return ContentAnalysis.model_validate(response)

        except ContentAnalysisError:
            raise
        except OutputParserException as e:
            raise ContentAnalysisError(f"Structured content analysis validation failed: {str(e)}") from e
        except Exception as e:
            raise ContentAnalysisError(f"Content analysis failed: {str(e)}")
