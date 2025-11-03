# Enhanced Option 2: Unified Schema Layer with API Flexibility

## Your Valid Concern

You're absolutely right: **sometimes internal models and API responses should differ**. Common scenarios:
- Hiding sensitive fields (passwords, internal IDs)
- Computed/derived fields for API convenience
- Different field names for API conventions
- Aggregating/transforming data for client needs

## Current Reality Check

Looking at your actual code:

```python
# mappers.py - Current "transformations"
def convert_ocr_response(response: OCRResponse) -> OCRResult:
    return OCRResult(
        text=response.transcribed_text,  # Just renaming
        character_count=len(response.transcribed_text)  # Simple computation
    )

def convert_analysis_response(response: AnalysisResponse) -> ContentAnalysis:
    return ContentAnalysis(
        grammar_focus=GrammarFocus(
            topic=response.grammar_focus.topic,  # Field-by-field copy
            explanation=response.grammar_focus.explanation,
            has_explicit_rules=response.grammar_focus.has_explicit_rules,
            rules=response.grammar_focus.rules,
        ),
        vocabulary=[...],  # Field-by-field copy
        core_topics=response.core_topics,  # Direct copy
        search_needed=SearchNeeded(...)  # Field-by-field copy
    )
```

**Reality**: 95% of fields are identical copies. Only `character_count` is computed.

## The Solution: Hybrid Approach

Keep unified schemas BUT use Pydantic features for API-specific needs:

### Strategy 1: Pydantic Computed Fields (Recommended)

```python
# src/runestone/schemas/ocr.py
from pydantic import BaseModel, Field, computed_field

class RecognitionStatistics(BaseModel):
    total_elements: int = Field(ge=0, default=0)
    successfully_transcribed: int = Field(ge=0, default=0)
    unclear_uncertain: int = Field(ge=0, default=0)
    unable_to_recognize: int = Field(ge=0, default=0)

class OCRResult(BaseModel):
    """Single unified model for parser output AND API response."""
    transcribed_text: str
    recognition_statistics: RecognitionStatistics

    @computed_field
    @property
    def character_count(self) -> int:
        """Computed field - only appears in API responses."""
        return len(self.transcribed_text)

    class Config:
        # Control serialization
        json_schema_extra = {
            "example": {
                "transcribed_text": "Hej världen",
                "recognition_statistics": {...},
                "character_count": 11
            }
        }
```

**Usage**:
```python
# Parser creates it
ocr_result = OCRResult(
    transcribed_text="Hej världen",
    recognition_statistics=RecognitionStatistics(...)
)

# API returns it - character_count automatically computed
return ocr_result  # FastAPI serializes with character_count included
```

### Strategy 2: Field Aliases for API Naming

```python
from pydantic import Field

class OCRResult(BaseModel):
    transcribed_text: str = Field(
        ...,
        serialization_alias="text"  # API sees "text", internal uses "transcribed_text"
    )
    recognition_statistics: RecognitionStatistics

    @computed_field
    @property
    def character_count(self) -> int:
        return len(self.transcribed_text)
```

**Result**: Internal code uses `transcribed_text`, API JSON shows `text`.

### Strategy 3: Exclude Fields from API

```python
class InternalData(BaseModel):
    public_field: str
    internal_id: int = Field(exclude=True)  # Never in API response
    debug_info: str = Field(exclude=True)
```

### Strategy 4: Response Models (When Truly Different)

For cases where API response is **significantly different**:

```python
# src/runestone/schemas/ocr.py
class OCRResult(BaseModel):
    """Internal model - full data."""
    transcribed_text: str
    recognition_statistics: RecognitionStatistics
    raw_response: str  # Internal only
    processing_time: float  # Internal only

class OCRAPIResponse(BaseModel):
    """API-specific response - subset of data."""
    text: str
    character_count: int
    quality_score: float

    @classmethod
    def from_internal(cls, result: OCRResult) -> "OCRAPIResponse":
        """Smart conversion with business logic."""
        stats = result.recognition_statistics
        quality = (stats.successfully_transcribed / stats.total_elements * 100) if stats.total_elements > 0 else 0

        return cls(
            text=result.transcribed_text,
            character_count=len(result.transcribed_text),
            quality_score=quality
        )
```

**When to use this**: Only when API response is **genuinely different** (< 50% field overlap).

## Recommended Architecture

```
src/runestone/schemas/
├── __init__.py
├── ocr.py              # OCR-related schemas
├── analysis.py         # Content analysis schemas
├── vocabulary.py       # Vocabulary schemas
└── api/                # API-specific models (only when needed)
    ├── __init__.py
    └── responses.py    # Truly different API responses
```

### Decision Tree

```
Need API response?
│
├─ Same fields as internal?
│  └─ YES → Use unified schema directly
│
├─ Need computed fields (character_count)?
│  └─ YES → Use @computed_field
│
├─ Need different field names?
│  └─ YES → Use serialization_alias
│
├─ Need to hide fields?
│  └─ YES → Use Field(exclude=True)
│
└─ Completely different structure?
   └─ YES → Create separate API response model with .from_internal()
```

## Your Current Codebase Analysis

| Model | Internal Fields | API Fields | Overlap | Recommendation |
|-------|----------------|------------|---------|----------------|
| OCRResponse → OCRResult | 2 | 2 | 100% | Unified + @computed_field |
| AnalysisResponse → ContentAnalysis | 4 | 4 | 100% | Unified schema |
| GrammarFocusResponse → GrammarFocus | 4 | 4 | 100% | Unified schema |
| VocabularyItemResponse → VocabularyItem | 4 | 4 | 100% | Unified schema |

**Verdict**: Your current code has **zero** cases requiring separate models.

## Implementation Example

### Before (Current - Duplicated)

```python
# validators.py
class OCRResponse(BaseModel):
    transcribed_text: str
    recognition_statistics: RecognitionStatistics

# schemas.py
class OCRResult(BaseModel):
    text: str
    character_count: int

# mappers.py
def convert_ocr_response(response: OCRResponse) -> OCRResult:
    return OCRResult(
        text=response.transcribed_text,
        character_count=len(response.transcribed_text)
    )

# endpoints.py
ocr_result = processor.run_ocr(content)
return convert_ocr_response(ocr_result)  # Manual mapping
```

### After (Enhanced Option 2)

```python
# schemas/ocr.py
class OCRResult(BaseModel):
    """Single model for both internal and API use."""
    transcribed_text: str = Field(serialization_alias="text")
    recognition_statistics: RecognitionStatistics

    @computed_field
    @property
    def character_count(self) -> int:
        return len(self.transcribed_text)

# endpoints.py
ocr_result = processor.run_ocr(content)
return ocr_result  # Direct return - no mapping needed!
```

**API JSON Output**:
```json
{
  "text": "Hej världen",
  "character_count": 11,
  "recognition_statistics": {...}
}
```

**Internal Code**:
```python
# Still uses descriptive name
print(ocr_result.transcribed_text)  # Works!
print(ocr_result.character_count)   # Computed automatically
```

## Benefits of This Approach

✅ **Eliminates duplication** - Single source of truth
✅ **API flexibility** - Computed fields, aliases, exclusions
✅ **Future-proof** - Easy to add API-specific models when truly needed
✅ **Type safety** - Full Pydantic validation
✅ **No mappers** - Direct model usage
✅ **Clear separation** - When needed, use `schemas/api/` directory

## Migration Path

### Phase 1: Unify Identical Models (Week 1)
- Move to `src/runestone/schemas/`
- Add `@computed_field` for `character_count`
- Add `serialization_alias` if needed
- Remove mappers
- Update imports

### Phase 2: Handle Edge Cases (Week 2)
- Identify any truly different API needs
- Create `schemas/api/` for special cases
- Add `.from_internal()` methods where needed

### Phase 3: Cleanup (Week 2)
- Delete old `validators.py`
- Delete `mappers.py`
- Update tests
- Update documentation

## When to Create Separate API Models

Create `schemas/api/responses.py` only when:

1. **Security**: Hiding sensitive fields (passwords, tokens)
2. **Aggregation**: Combining multiple internal models
3. **Transformation**: Complex business logic in conversion
4. **Versioning**: Supporting multiple API versions
5. **Client Optimization**: Reducing payload size significantly

**Current verdict**: None of these apply to your codebase yet.

## Code Examples for Future Scenarios

### Scenario 1: Hide Internal Fields

```python
class UserProfile(BaseModel):
    username: str
    email: str
    password_hash: str = Field(exclude=True)  # Never in API
    internal_id: int = Field(exclude=True)
```

### Scenario 2: Aggregate Multiple Models

```python
class FullAnalysisResponse(BaseModel):
    """API-specific aggregation."""
    ocr: OCRResult
    analysis: ContentAnalysis
    resources: str

    @computed_field
    @property
    def summary(self) -> str:
        return f"Found {len(self.analysis.vocabulary)} words"

    @classmethod
    def from_components(cls, ocr: OCRResult, analysis: ContentAnalysis, resources: str):
        return cls(ocr=ocr, analysis=analysis, resources=resources)
```

### Scenario 3: API Versioning

```python
# schemas/api/v1/responses.py
class OCRResultV1(BaseModel):
    text: str
    stats: dict

# schemas/api/v2/responses.py
class OCRResultV2(BaseModel):
    text: str
    recognition_statistics: RecognitionStatistics
    quality_score: float
```

## Recommendation

**Start with unified schemas + Pydantic features**. Only create separate API models when you have a concrete need. Your current codebase doesn't need them.

This gives you:
- **Best of both worlds**: No duplication + API flexibility
- **Pragmatic**: Solve current problems, prepare for future ones
- **Maintainable**: Clear patterns for when to separate
- **Testable**: Single models = single test suite

## Next Steps

1. ✅ Approve this enhanced approach
2. Create `src/runestone/schemas/` structure
3. Migrate OCR models first (smallest, safest)
4. Verify API responses match expected format
5. Migrate remaining models
6. Delete old files

Would you like me to proceed with this enhanced Option 2?
