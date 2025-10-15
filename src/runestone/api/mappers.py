"""
Mappers to convert between internal response objects and API schemas.

This module provides conversion functions to map between processor response types
(from validators) and API response schemas. It handles both directions:
- Internal to API (for responses)
- API to Internal (for requests that need internal processing)
"""

from runestone.api.schemas import (
    ContentAnalysis,
    GrammarFocus,
    OCRResult,
    ResourceRequestData,
    SearchNeeded,
    VocabularyItem,
)
from runestone.core.prompt_builder.validators import (
    AnalysisResponse,
    GrammarFocusResponse,
    OCRResponse,
    SearchNeededResponse,
)


def convert_ocr_response(response: OCRResponse) -> OCRResult:
    """
    Convert OCRResponse from processor to OCRResult API schema.

    Args:
        response: OCRResponse object from the processor

    Returns:
        OCRResult: Converted API response model
    """
    return OCRResult(text=response.transcribed_text, character_count=len(response.transcribed_text))


def convert_analysis_response(response: AnalysisResponse) -> ContentAnalysis:
    """
    Convert AnalysisResponse from processor to ContentAnalysis API schema.

    Args:
        response: AnalysisResponse object from the processor

    Returns:
        ContentAnalysis: Converted API response model
    """
    return ContentAnalysis(
        grammar_focus=GrammarFocus(
            topic=response.grammar_focus.topic,
            explanation=response.grammar_focus.explanation,
            has_explicit_rules=response.grammar_focus.has_explicit_rules,
            rules=response.grammar_focus.rules,
        ),
        vocabulary=[
            VocabularyItem(
                swedish=item.swedish,
                english=item.english,
                example_phrase=item.example_phrase,
            )
            for item in response.vocabulary
        ],
        core_topics=response.core_topics,
        search_needed=SearchNeeded(
            should_search=response.search_needed.should_search,
            query_suggestions=response.search_needed.query_suggestions,
        ),
    )


def convert_resource_request_to_analysis(request_data: ResourceRequestData) -> AnalysisResponse:
    """
    Convert ResourceRequestData from API to AnalysisResponse for processor.

    This is a reverse mapper that converts API request data back to internal
    validator format for resource search processing.

    Args:
        request_data: ResourceRequestData from API request

    Returns:
        AnalysisResponse: Internal response format for processor
    """
    return AnalysisResponse(
        grammar_focus=GrammarFocusResponse(
            has_explicit_rules=False,
            topic="",
            explanation="",
            rules=None,
        ),
        vocabulary=[],
        core_topics=request_data.core_topics,
        search_needed=SearchNeededResponse(
            should_search=request_data.search_needed.should_search,
            query_suggestions=request_data.search_needed.query_suggestions,
        ),
    )
