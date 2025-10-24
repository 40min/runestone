# Batch Vocabulary Improvement Refactoring Plan

## 1. Overview

### Current State
The system currently enriches vocabulary items one at a time by calling `_enrich_vocabulary_item()` for each item in a loop within `save_vocabulary()`. Each call:
- Creates a single-item improvement request with `EXTRA_INFO_ONLY` mode
- Calls `improve_item()` which sends one word/phrase to the LLM
- Parses the response and returns enriched item

**Problem:** Processing 100+ vocabulary items means 100+ sequential LLM calls, which is:
- Slow (network latency × 100+)
- Expensive (separate API calls for each item)
- Inefficient (LLM not utilized for batch processing)

### Proposed Solution
Refactor to process vocabulary items in batches of up to 100 items per LLM call:
- Create new batch-specific prompt template
- Send list of word_phrases to LLM in single call
- LLM returns JSON dictionary mapping word_phrases to their extra_info
- Parse batch response and apply enrichments
- Handle partial failures gracefully

### Design Decisions

1. **Batch size: 100 items**
   - Balances throughput with prompt size limits
   - Typical page extraction yields 50-150 vocabulary items
   - Single batch for most pages, 2 batches for large pages

2. **Mode: EXTRA_INFO_ONLY**
   - Current enrichment only needs `extra_info` field
   - Simplifies prompt and response format
   - Keeps backward compatibility with API endpoint

3. **Error handling: Partial success**
   - Save successfully enriched items
   - Log warnings for failures
   - Continue processing without blocking

4. **Backward compatibility: Keep single-item API**
   - `/api/vocabulary/improve` endpoint unchanged
   - `improve_item()` method remains for interactive use
   - New batch method only for internal enrichment

## 2. Implementation Details

### 2.1 Add New PromptType (types.py)

Add new enum value to PromptType:

```python
class PromptType(str, Enum):
    """Supported prompt types for different operations."""

    OCR = "ocr"
    ANALYSIS = "analysis"
    SEARCH = "search"
    VOCABULARY_IMPROVE = "vocabulary_improve"
    VOCABULARY_BATCH_IMPROVE = "vocabulary_batch_improve"  # NEW
```

### 2.2 New Prompt Template (templates.py)

Add to TEMPLATE_REGISTRY:

```python
PromptType.VOCABULARY_BATCH_IMPROVE: PromptTemplate(
    name="Vocabulary Batch Improvement",
    version="1.0.0",
    content="""
You are a Swedish language learning expert. Your task is to provide grammatical information (extra_info) for a batch of Swedish words/phrases.

WORD/PHRASE LIST:
{word_phrases_list}

For each word/phrase, provide:
- Grammatical information (word form, base form, en/ett classification for nouns, verb forms, etc.)
- Keep it concise and human-readable
- Focus on the most important details for language learners

Return ONLY a JSON object where each key is the Swedish word/phrase and the value is the extra_info string:

{{
    "word_phrase_1": "grammatical details here",
    "word_phrase_2": "grammatical details here"
}}

IMPORTANT:
- Include ALL word_phrases from the input list
- If you cannot determine extra_info for a word, use null as the value
- Keep extra_info concise (e.g., "en-word, noun, base form: ord")
- For nouns: include en/ett classification and base form if different
- For verbs: include verb forms (infinitive, present, past, supine) if relevant
- For adjectives: include comparative forms if relevant
- Don't provide base form if word is already in base form

Return ONLY valid JSON, no additional text or formatting.
""",
    parameters=["word_phrases_list"],
    metadata={"output_format": "json"},
)
```

### 2.3 PromptBuilder Enhancement (builder.py)

Add new method to PromptBuilder class:

```python
def build_vocabulary_batch_prompt(self, word_phrases: List[str]) -> str:
    """
    Build batch vocabulary improvement prompt for multiple items.

    Args:
        word_phrases: List of Swedish words/phrases (max 100)

    Returns:
        Complete batch improvement prompt string

    Raises:
        ValueError: If word_phrases list is empty or exceeds 100 items
    """
    if not word_phrases:
        raise ValueError("word_phrases list cannot be empty")
    if len(word_phrases) > 100:
        raise ValueError(f"Batch size {len(word_phrases)} exceeds maximum of 100")

    template = self._templates[PromptType.VOCABULARY_BATCH_IMPROVE]

    # Format as numbered list for clarity
    word_phrases_list = "\n".join(f"{i+1}. {wp}" for i, wp in enumerate(word_phrases))

    return template.render(word_phrases_list=word_phrases_list)
```

### 2.4 ResponseParser Enhancement (parsers.py)

Add new methods to ResponseParser class:

```python
def parse_vocabulary_batch_response(self, response: str) -> Dict[str, Optional[str]]:
    """
    Parse batch vocabulary improvement response.

    Args:
        response: Raw LLM response string (expected as JSON dict)

    Returns:
        Dictionary mapping word_phrase -> extra_info (or None if failed)

    Raises:
        ResponseParseError: If parsing completely fails
    """
    try:
        data = self._parse_json(response)

        # Validate it's a dictionary
        if not isinstance(data, dict):
            raise ResponseParseError("Batch response must be a JSON object/dictionary")

        # Normalize: ensure all values are str or None
        result = {}
        for word_phrase, extra_info in data.items():
            if extra_info is None or isinstance(extra_info, str):
                result[word_phrase] = extra_info
            else:
                # Convert to string if possible
                result[word_phrase] = str(extra_info) if extra_info else None

        return result

    except json.JSONDecodeError:
        # Try fallback parsing
        return self._fallback_vocabulary_batch_parse(response)

def _fallback_vocabulary_batch_parse(self, response: str) -> Dict[str, Optional[str]]:
    """
    Fallback parser for malformed batch responses.

    Attempts to extract key-value pairs using regex when JSON parsing fails.
    """
    result = {}

    # Try to find quoted key-value pairs
    # Pattern: "key": "value" or "key": null
    pattern = r'"([^"]+)"\s*:\s*(?:"([^"]*)"|null)'
    matches = re.finditer(pattern, response, re.DOTALL)

    for match in matches:
        word_phrase = match.group(1)
        extra_info = match.group(2) if match.group(2) else None
        result[word_phrase] = extra_info

    if not result:
        raise ResponseParseError("Could not extract any vocabulary data from malformed batch response")

    return result
```

### 2.5 LLM Client Interface (base.py)

Add abstract method to BaseLLMClient:

```python
@abstractmethod
def improve_vocabulary_batch(self, prompt: str) -> str:
    """
    Improve multiple vocabulary items in a single batch request.

    Args:
        prompt: Batch vocabulary improvement prompt containing list of words

    Returns:
        JSON string containing word_phrase -> extra_info mappings

    Raises:
        LLMError: If batch improvement fails
    """
    pass
```

### 2.6 GeminiClient Implementation

Add to GeminiClient class:

```python
def improve_vocabulary_batch(self, prompt: str) -> str:
    """
    Improve multiple vocabulary items using Gemini in batch.

    Args:
        prompt: Batch vocabulary improvement prompt

    Returns:
        JSON string with batch improvements

    Raises:
        LLMError: If batch improvement fails
    """
    try:
        if self.verbose:
            self.logger.info("Improving vocabulary batch with Gemini...")

        response = self.analysis_model.generate_content(prompt)

        if not response.text:
            raise LLMError("No vocabulary batch improvement returned from Gemini")

        return response.text.strip()

    except google.api_core.exceptions.GoogleAPICallError as e:
        raise LLMError(f"Gemini API call failed: {str(e)}")
    except Exception as e:
        raise LLMError(f"Vocabulary batch improvement failed: {str(e)}")
```

### 2.7 OpenAIClient Implementation

Add to OpenAIClient class:

```python
def improve_vocabulary_batch(self, prompt: str) -> str:
    """
    Improve multiple vocabulary items using OpenAI in batch.

    Args:
        prompt: Batch vocabulary improvement prompt

    Returns:
        JSON string with batch improvements

    Raises:
        LLMError: If batch improvement fails
    """
    try:
        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10000,
            temperature=0.1,
        )

        if not response.choices or not response.choices[0].message.content:
            raise LLMError(f"No vocabulary batch improvement returned from {self.provider_name}")

        return response.choices[0].message.content.strip()

    except APIError as e:
        raise LLMError(f"OpenAI API error during vocabulary batch improvement: {str(e)}")
    except Exception as e:
        raise LLMError(f"Vocabulary batch improvement failed: {str(e)}")
```

### 2.8 OpenRouterClient Implementation

Add to OpenRouterClient class (similar to OpenAI):

```python
def improve_vocabulary_batch(self, prompt: str) -> str:
    """
    Improve multiple vocabulary items using OpenRouter in batch.

    Args:
        prompt: Batch vocabulary improvement prompt

    Returns:
        JSON string with batch improvements

    Raises:
        LLMError: If batch improvement fails
    """
    try:
        response = self.client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10000,
            temperature=0.1,
        )

        if not response.choices or not response.choices[0].message.content:
            raise LLMError(f"No vocabulary batch improvement returned from {self.provider_name}")

        return response.choices[0].message.content.strip()

    except APIError as e:
        raise LLMError(f"OpenRouter API error during vocabulary batch improvement: {str(e)}")
    except Exception as e:
        raise LLMError(f"Vocabulary batch improvement failed: {str(e)}")
```

### 2.9 VocabularyService Refactoring

Replace `_enrich_vocabulary_item` with `_enrich_vocabulary_items`:

```python
def _enrich_vocabulary_items(self, items: List[VocabularyItemCreate]) -> List[VocabularyItemCreate]:
    """
    Enrich vocabulary items with extra_info using LLM batch processing.

    Processes items in batches of up to 100 for optimal performance.
    Handles partial failures gracefully - enriches successful items and logs failures.

    Args:
        items: List of vocabulary items to enrich

    Returns:
        List of vocabulary items with extra_info populated where successful
    """
    if not items:
        return items

    enriched_items = []
    BATCH_SIZE = 100
    total_enriched = 0
    total_failed = 0

    # Process in batches
    for batch_start in range(0, len(items), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(items))
        batch = items[batch_start:batch_end]
        batch_num = batch_start // BATCH_SIZE + 1

        try:
            # Extract word_phrases for this batch
            word_phrases = [item.word_phrase for item in batch]

            # Build batch prompt
            prompt = self.builder.build_vocabulary_batch_prompt(word_phrases)

            # Get batch improvements from LLM
            response_text = self.llm_client.improve_vocabulary_batch(prompt)

            # Parse batch response
            enrichments = self.parser.parse_vocabulary_batch_response(response_text)

            # Apply enrichments to items
            batch_success = 0
            batch_failed = 0

            for item in batch:
                extra_info = enrichments.get(item.word_phrase)

                # Create enriched item
                enriched_item = VocabularyItemCreate(
                    word_phrase=item.word_phrase,
                    translation=item.translation,
                    example_phrase=item.example_phrase,
                    extra_info=extra_info if extra_info else item.extra_info,
                    in_learn=item.in_learn,
                )
                enriched_items.append(enriched_item)

                if extra_info:
                    batch_success += 1
                else:
                    batch_failed += 1

            total_enriched += batch_success
            total_failed += batch_failed

            if batch_failed > 0:
                self.logger.warning(
                    f"Batch {batch_num}: {batch_success} items enriched, {batch_failed} items failed"
                )
            else:
                self.logger.info(f"Batch {batch_num}: All {batch_success} items enriched successfully")

        except Exception as e:
            # Log error but continue with non-enriched items
            self.logger.error(f"Failed to enrich batch {batch_num}: {e}")
            # Add items without enrichment
            enriched_items.extend(batch)
            total_failed += len(batch)

    # Log summary
    total_items = len(items)
    self.logger.info(
        f"Enrichment summary: {total_enriched}/{total_items} successful, {total_failed}/{total_items} failed"
    )

    return enriched_items
```

Update `save_vocabulary` method to use new batch enrichment:

```python
def save_vocabulary(self, items: List[VocabularyItemCreate], enrich: bool = True, user_id: int = 1) -> dict:
    """Save vocabulary items, handling business logic."""
    # Get unique word_phrases from the batch
    batch_word_phrases = [item.word_phrase for item in items]

    # Get existing word_phrases for the user from this batch
    existing_word_phrases = self.repo.get_existing_word_phrases_for_batch(batch_word_phrases, user_id)

    # Filter items: remove duplicates within batch and existing in DB
    seen_in_batch = set()
    filtered_items = []

    for item in items:
        if item.word_phrase not in seen_in_batch and item.word_phrase not in existing_word_phrases:
            filtered_items.append(item)
            seen_in_batch.add(item.word_phrase)

    # Enrich filtered items if requested (CHANGED: now uses batch method)
    if enrich and filtered_items:
        filtered_items = self._enrich_vocabulary_items(filtered_items)

    # Batch insert the filtered (and potentially enriched) items
    if filtered_items:
        self.repo.batch_insert_vocabulary_items(filtered_items, user_id)

    return {"message": "Vocabulary saved successfully"}
```

## 3. Testing Strategy

### 3.1 Unit Tests (test_services_vocabulary_service.py)

**Test 1: Successful batch enrichment**
```python
def test_enrich_vocabulary_items_success(self, service):
    """Test successful vocabulary items batch enrichment."""
    # Mock LLM client to return batch response
    service.llm_client.improve_vocabulary_batch.return_value = '''
    {
        "ett äpple": "en-word, noun, base form: äpple",
        "en banan": "en-word, noun",
        "vara": "verb, forms: vara, är, var, varit"
    }
    '''

    # Test items
    items = [
        VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
        VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase="Han äter en banan."),
        VocabularyItemCreate(word_phrase="vara", translation="to be", example_phrase="Jag vill vara glad."),
    ]

    # Enrich the items
    enriched_items = service._enrich_vocabulary_items(items)

    # Verify all enriched
    assert len(enriched_items) == 3
    assert enriched_items[0].extra_info == "en-word, noun, base form: äpple"
    assert enriched_items[1].extra_info == "en-word, noun"
    assert enriched_items[2].extra_info == "verb, forms: vara, är, var, varit"
```

**Test 2: Partial batch failure**
```python
def test_enrich_vocabulary_items_partial_failure(self, service):
    """Test vocabulary items batch enrichment with partial failures."""
    # Mock LLM with some null values
    service.llm_client.improve_vocabulary_batch.return_value = '''
    {
        "ett äpple": "en-word, noun, base form: äpple",
        "en banan": null,
        "vara": "verb, forms: vara, är, var, varit"
    }
    '''

    items = [
        VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
        VocabularyItemCreate(word_phrase="en banan", translation="a banana", example_phrase="Han äter en banan."),
        VocabularyItemCreate(word_phrase="vara", translation="to be", example_phrase="Jag vill vara glad."),
    ]

    enriched_items = service._enrich_vocabulary_items(items)

    # Verify: 2 enriched, 1 failed
    assert len(enriched_items) == 3
    assert enriched_items[0].extra_info == "en-word, noun, base form: äpple"
    assert enriched_items[1].extra_info is None  # Failed
    assert enriched_items[2].extra_info == "verb, forms: vara, är, var, varit"
```

**Test 3: Complete batch failure**
```python
def test_enrich_vocabulary_items_llm_exception(self, service):
    """Test vocabulary items enrichment when LLM raises exception."""
    # Mock LLM to raise exception
    service.llm_client.improve_vocabulary_batch.side_effect = Exception("LLM error")

    items = [
        VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple."),
    ]

    # Should not raise, but return items without enrichment
    enriched_items = service._enrich_vocabulary_items(items)

    assert len(enriched_items) == 1
    assert enriched_items[0].extra_info is None
```

**Test 4: Large batch handling**
```python
def test_enrich_vocabulary_items_large_batch(self, service):
    """Test vocabulary items enrichment with >100 items (multiple batches)."""
    # Create 150 items
    items = [
        VocabularyItemCreate(
            word_phrase=f"word_{i}",
            translation=f"translation_{i}",
            example_phrase=f"Example {i}."
        )
        for i in range(150)
    ]

    # Mock LLM to return appropriate responses for each batch
    def mock_batch_response(prompt):
        # Extract word count from prompt
        if "word_0" in prompt and "word_99" in prompt:
            # First batch (0-99)
            return '{' + ','.join(f'"word_{i}": "info_{i}"' for i in range(100)) + '}'
        else:
            # Second batch (100-149)
            return '{' + ','.join(f'"word_{i}": "info_{i}"' for i in range(100, 150)) + '}'

    service.llm_client.improve_vocabulary_batch.side_effect = mock_batch_response

    enriched_items = service._enrich_vocabulary_items(items)

    # Verify all 150 items enriched across 2 batches
    assert len(enriched_items) == 150
    assert all(item.extra_info for item in enriched_items)
    assert service.llm_client.improve_vocabulary_batch.call_count == 2
```

**Test 5: Empty list**
```python
def test_enrich_vocabulary_items_empty_list(self, service):
    """Test vocabulary items enrichment with empty list."""
    enriched_items = service._enrich_vocabulary_items([])

    assert enriched_items == []
    service.llm_client.improve_vocabulary_batch.assert_not_called()
```

**Test 6: Integration with save_vocabulary**
```python
def test_save_vocabulary_with_batch_enrichment(self, service, db_session):
    """Test save_vocabulary using batch enrichment."""
    # Mock batch enrichment
    service.llm_client.improve_vocabulary_batch.return_value = '''
    {
        "ett äpple": "en-word, noun, base form: äpple"
    }
    '''

    items = [
        VocabularyItemCreate(word_phrase="ett äpple", translation="an apple", example_phrase="Jag äter ett äpple.")
    ]

    result = service.save_vocabulary(items, user_id=1, enrich=True)
    db_session.commit()

    # Verify result
    assert result == {"message": "Vocabulary saved successfully"}

    # Verify item saved with enrichment
    vocab = db_session.query(VocabularyModel).filter(VocabularyModel.word_phrase == "ett äpple").first()
    assert vocab is not None
    assert vocab.extra_info == "en-word, noun, base form: äpple"
```

## 4. Performance Impact

### Before (Current)
- 100 items = 100 LLM calls
- Average latency: 1-2s per call
- Total time: 100-200 seconds
- API calls: 100

### After (Batch)
- 100 items = 1 LLM call
- Average latency: 2-4s per call
- Total time: 2-4 seconds
- API calls: 1

**Expected improvement:**
- ⚡ **50-100x faster** processing
- 💰 **99% fewer API calls**
- 📈 **Better user experience**

## 5. Success Criteria

- ✅ All tests pass (unit + integration)
- ✅ Batch processing completes in < 5s for 100 items
- ✅ Partial failure handling works correctly
- ✅ Existing API endpoint `/api/vocabulary/improve` unchanged
- ✅ No data loss or corruption
- ✅ Error logs show clear failure information
- ✅ Code coverage maintained or improved
