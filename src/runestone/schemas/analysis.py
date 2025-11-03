from typing import List, Optional

from pydantic import BaseModel, Field


class GrammarFocus(BaseModel):
    """Grammar focus section of content analysis."""

    has_explicit_rules: bool = Field(description="Whether explicit grammar rules are present")
    topic: str = Field(description="Main grammatical topic")
    rules: Optional[str] = Field(None, description="Grammar rules from the page")
    explanation: str = Field(description="English explanation of the grammar concept")


class VocabularyItem(BaseModel):
    """Individual vocabulary item from content analysis."""

    swedish: str = Field(description="Swedish word or phrase")
    english: str = Field(description="English translation")
    example_phrase: Optional[str] = Field(None, description="Example sentence from source text")
    known: bool = Field(default=False, description="Whether the word is already in user's vocabulary database")


class SearchNeeded(BaseModel):
    """Search requirement information."""

    should_search: bool = Field(description="Whether additional resource search is needed")
    query_suggestions: List[str] = Field(default_factory=list, description="Suggested search queries")


class ContentAnalysis(BaseModel):
    """Complete content analysis response."""

    grammar_focus: GrammarFocus = Field(description="Grammar focus information")
    vocabulary: List[VocabularyItem] = Field(default_factory=list, description="Vocabulary items found")
    core_topics: List[str] = Field(default_factory=list, description="Main topics covered")
    search_needed: SearchNeeded = Field(description="Search requirements")
