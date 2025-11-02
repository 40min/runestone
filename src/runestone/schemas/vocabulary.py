from typing import Optional

from pydantic import BaseModel, Field


class VocabularyResponse(BaseModel):
    """Vocabulary improvement response from LLM.

    Fields returned depend on the improvement mode:
    - EXAMPLE_ONLY: only example_phrase is populated
    - EXTRA_INFO_ONLY: only extra_info is populated
    - ALL_FIELDS: all fields are populated
    """

    translation: Optional[str] = Field(None, description="English translation of the Swedish word/phrase")
    example_phrase: Optional[str] = Field(None, description="Natural Swedish sentence using the word in context")
    extra_info: Optional[str] = Field(None, description="Grammatical details (word form, base form, etc.)")
