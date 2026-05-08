# LangChain Service LLM Migration

## Summary

Runestone currently has two separate LLM integration styles:

- agentic flows use LangChain chat models directly
- non-agent service flows still depend on the legacy `BaseLLMClient` stack

This migration moves the non-agent service flows onto LangChain chat models as
well, while intentionally keeping the agent and non-agent model builders
parallel for now. That gives OCR, content analysis, and vocabulary improvement
the same transport seam needed for future `with_structured_output` work without
forcing both architectures into one shared abstraction too early.

## Current State

Before this migration:

- `VocabularyService`, `ContentAnalyzer`, and `OCRProcessor` depended on
  `BaseLLMClient`
- app startup, dependencies, CLI flows, and background service providers used
  `create_llm_client(...)`
- OpenAI and OpenRouter support lived in bespoke `AsyncOpenAI` wrappers under
  `src/runestone/core/clients/`
- the newer agent stack already used `ChatOpenAI` directly, including
  `with_structured_output` in `word_keeper`

This split made follow-up structured-output work harder because service code was
still organized around feature-specific client methods such as
`improve_vocabulary_item()` instead of direct model invocation.

## Target Architecture

### Non-agent model builder

Add a dedicated service-side LangChain builder in `src/runestone/core/service_llm.py`.

Responsibilities:

- build non-agent `ChatOpenAI` models for OpenAI and OpenRouter
- preserve the current provider/model config surface:
  - `llm_provider`
  - `llm_model_name`
  - `ocr_llm_provider`
  - `ocr_llm_model_name`
- preserve OpenRouter base URL and attribution headers
- preserve the legacy default model behavior (`gpt-4o-mini`) when no model is configured

The agent builder in `src/runestone/agents/llm.py` remains separate on purpose.

### Service-level model usage

After the migration:

- `VocabularyService` owns prompt construction and calls `llm_model.ainvoke(...)`
- `ContentAnalyzer` owns prompt construction and calls `llm_model.ainvoke(...)`
- `OCRProcessor` builds a multimodal LangChain `HumanMessage` and calls
  `ocr_llm_model.ainvoke(...)`

`PromptBuilder` and `ResponseParser` remain in place for now. This migration
changes transport and dependency wiring, not output schema enforcement.

### Dependency and startup naming

Non-agent runtime wiring should use model-oriented names:

- `llm_model`
- `ocr_llm_model`

That applies to:

- FastAPI app state
- dependency injection
- CLI model creation
- background service providers

## Files And Surfaces

### Migrated surfaces

- `src/runestone/services/vocabulary_service.py`
- `src/runestone/core/analyzer.py`
- `src/runestone/core/ocr.py`
- `src/runestone/api/main.py`
- `src/runestone/dependencies.py`
- `src/runestone/agents/service_providers.py`
- `src/runestone/cli.py`
- test coverage for builder, dependencies, OCR, analyzer, vocabulary service, and CLI wiring

### Removed legacy service LLM stack

- `src/runestone/core/clients/base.py`
- `src/runestone/core/clients/openai_client.py`
- `src/runestone/core/clients/openrouter_client.py`
- `src/runestone/core/clients/factory.py`
- obsolete tests for those classes

`src/runestone/core/clients/voice/` stays untouched.

## Structured Output Follow-Ups

This migration is intentionally the seam-creation step, not the structured-output step.

### 1. Vocabulary improvement

First follow-up target:

- `VocabularyService.improve_item`

Goal:

- move output-shape enforcement from prompt JSON instructions and manual parser
  recovery toward `with_structured_output`
- keep semantic field guidance for `translation`, `example_phrase`, and `extra_info`

### 2. Content analysis

Second follow-up target:

- `ContentAnalyzer.analyze_content`

Goal:

- replace manual JSON parsing and fallback-heavy response validation with a
  schema-backed structured response path while keeping the current public
  response contract unchanged

### 3. Later candidates

- OCR response parsing
- vocabulary batch enrichment

These should only move once the first two structured-output migrations prove out
well in the service layer.

## Validation Plan

### Core scenarios

- default OpenAI service model wiring still works
- OpenRouter service model wiring still sets the expected base URL and headers
- OCR-specific provider/model override still builds a separate model
- Vocabulary improvement behavior remains unchanged before structured-output follow-ups
- content analysis behavior remains unchanged before structured-output follow-ups
- OCR recognition parsing and validation behavior remains unchanged

### Recommended checks

- `uv run pytest tests/core/test_factory.py -v`
- `uv run pytest tests/test_dependencies.py tests/core/test_ocr.py tests/core/test_analyzer.py -v`
- `uv run pytest tests/services/test_services_vocabulary_service.py -v`
- `uv run pytest tests/test_cli.py -k 'process_command_env_api_key' -v`
- `make backend-test`

## Related Dart Tasks

- `Migrate service-layer LLM clients from BaseLLMClient to LangChain chat models`
- `Add with_structured_output to vocabulary improvement flow`
- `Add structured output to content analysis flow`
