from pydantic import BaseModel, Field, computed_field


class RecognitionStatistics(BaseModel):
    """OCR recognition statistics."""

    total_elements: int = Field(ge=0, default=0, description="Total number of text elements detected")
    successfully_transcribed: int = Field(ge=0, default=0, description="Number of successfully transcribed elements")
    unclear_uncertain: int = Field(ge=0, default=0, description="Number of unclear or uncertain elements")
    unable_to_recognize: int = Field(ge=0, default=0, description="Number of elements unable to recognize")


class OCRResult(BaseModel):
    """Unified OCR result model for both parser output AND API response."""

    transcribed_text: str = Field(..., description="The transcribed text from the image", serialization_alias="text")
    recognition_statistics: RecognitionStatistics = Field(..., description="Statistics about recognition quality")

    @computed_field
    @property
    def character_count(self) -> int:
        """Computed field - automatically included in API responses."""
        return len(self.transcribed_text)
