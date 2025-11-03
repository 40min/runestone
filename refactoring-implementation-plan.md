# Schema Refactoring Implementation Plan

## Overview
Refactor the codebase to use unified schemas, eliminating duplication between `validators.py` and `schemas.py` while maintaining API flexibility through Pydantic features.

## Phase 1: Setup and OCR Migration (Day 1-2)

### Task 1.1: Create New Schema Structure
**Objective**: Set up the new `src/runestone/schemas/` directory structure

**Steps**:
1. Create directory: `src/runestone/schemas/`
2. Create `src/runestone/schemas/__init__.py`
3. Create placeholder files:
   - `src/runestone/schemas/ocr.py`
   - `src/runestone/schemas/analysis.py`
   - `src/runestone/schemas/vocabulary.py`

**Acceptance Criteria**:
- Directory structure exists
- All `__init__.py` files are present
- Files are importable

---

### Task 1.2: Migrate OCR Schemas
**Objective**: Create unified OCR schema with computed fields

**Steps**:
1. Create `RecognitionStatistics` in `schemas/ocr.py`
2. Create unified `OCRResult` with:
   - `transcribed_text` field with `serialization_alias="text"`
   - `recognition_statistics` field
   - `@computed_field` for `character_count`
3. Add proper docstrings and type hints
4. Add Pydantic configuration for JSON schema examples

**Files to Create**:
- `src/runestone/schemas/ocr.py`

**Acceptance Criteria**:
- `OCRResult` model created with all fields
- `character_count` is a computed property
- API serialization uses "text" instead of "transcribed_text"
- Model validates correctly

---

### Task 1.3: Update OCR Parser
**Objective**: Update parser to use new unified schema

**Steps**:
1. Update imports in `src/runestone/core/prompt_builder/parsers.py`
2. Change `OCRResponse` references to `OCRResult`
3. Update return types
4. Verify parser tests still pass

**Files to Modify**:
- `src/runestone/core/prompt_builder/parsers.py`

**Acceptance Criteria**:
- Parser imports from `runestone.schemas.ocr`
- All OCR parsing functions return `OCRResult`
- Tests pass: `make backend-test -k test_parsers`

---

### Task 1.4: Update OCR Processor
**Objective**: Update OCR processor to use new schema

**Steps**:
1. Update imports in `src/runestone/core/ocr.py`
2. Change return type annotations
3. Update any internal references

**Files to Modify**:
- `src/runestone/core/ocr.py`

**Acceptance Criteria**:
- OCR processor returns `OCRResult`
- Tests pass: `make backend-test -k test_ocr`

---

### Task 1.5: Update API Endpoints for OCR
**Objective**: Remove mapper usage for OCR endpoint

**Steps**:
1. Update imports in `src/runestone/api/endpoints.py`
2. Remove `convert_ocr_response` call
3. Return `OCRResult` directly from endpoint
4. Update response_model if needed

**Files to Modify**:
- `src/runestone/api/endpoints.py`

**Acceptance Criteria**:
- OCR endpoint returns unified schema directly
- No mapper function called
- API tests pass: `make backend-test -k test_endpoints`
- API response JSON matches expected format (with "text" and "character_count")

---

### Task 1.6: Update API Schema Imports
**Objective**: Update API schemas file to re-export OCR schemas

**Steps**:
1. Add import in `src/runestone/api/schemas.py`: `from runestone.schemas.ocr import OCRResult, RecognitionStatistics`
2. Remove old `OCRResult` definition
3. Add `__all__` export if needed

**Files to Modify**:
- `src/runestone/api/schemas.py`

**Acceptance Criteria**:
- Old OCR schema definitions removed
- New schemas imported and re-exported
- No import errors in dependent files

---

## Phase 2: Analysis Schemas Migration (Day 3-4)

### Task 2.1: Migrate Analysis Schemas
**Objective**: Create unified analysis schemas

**Steps**:
1. Create in `schemas/analysis.py`:
   - `GrammarFocus` (unified from GrammarFocusResponse)
   - `VocabularyItem` (unified from VocabularyItemResponse)
   - `SearchNeeded` (unified from SearchNeededResponse)
   - `ContentAnalysis` (unified from AnalysisResponse)
2. Ensure all fields match between old internal and API versions
3. Add proper docstrings

**Files to Create**:
- `src/runestone/schemas/analysis.py`

**Acceptance Criteria**:
- All analysis models created
- Field names consistent
- Models validate correctly

---

### Task 2.2: Update Analysis Parser
**Objective**: Update parser to use new unified schemas

**Steps**:
1. Update imports in `parsers.py`
2. Change all `AnalysisResponse` references to `ContentAnalysis`
3. Update nested model references
4. Verify parser tests pass

**Files to Modify**:
- `src/runestone/core/prompt_builder/parsers.py`

**Acceptance Criteria**:
- Parser uses unified schemas
- Tests pass: `make backend-test -k test_parsers`

---

### Task 2.3: Update Analyzer
**Objective**: Update analyzer to use new schemas

**Steps**:
1. Update imports in `src/runestone/core/analyzer.py`
2. Update return type annotations
3. Update any internal references

**Files to Modify**:
- `src/runestone/core/analyzer.py`

**Acceptance Criteria**:
- Analyzer returns unified schemas
- Tests pass: `make backend-test -k test_analyzer`

---

### Task 2.4: Update Processor
**Objective**: Update processor to use new schemas

**Steps**:
1. Update imports in `src/runestone/core/processor.py`
2. Update return type annotations
3. Update any internal references

**Files to Modify**:
- `src/runestone/core/processor.py`

**Acceptance Criteria**:
- Processor uses unified schemas
- Tests pass: `make backend-test -k test_processor`

---

### Task 2.5: Update API Endpoints for Analysis
**Objective**: Remove mapper usage for analysis endpoints

**Steps**:
1. Update imports in `endpoints.py`
2. Remove `convert_analysis_response` calls
3. Return unified schemas directly
4. Update response_model annotations

**Files to Modify**:
- `src/runestone/api/endpoints.py`

**Acceptance Criteria**:
- Analysis endpoints return unified schemas
- No mapper functions called
- API tests pass: `make backend-test -k test_endpoints`

---

### Task 2.6: Update API Schema Imports for Analysis
**Objective**: Update API schemas to re-export analysis schemas

**Steps**:
1. Import from `runestone.schemas.analysis`
2. Remove old definitions
3. Update `__all__` exports

**Files to Modify**:
- `src/runestone/api/schemas.py`

**Acceptance Criteria**:
- Old analysis schema definitions removed
- New schemas imported and re-exported
- No import errors

---

## Phase 3: Vocabulary Schemas Migration (Day 5)

### Task 3.1: Migrate Vocabulary Schemas
**Objective**: Move vocabulary-related schemas to unified location

**Steps**:
1. Create `schemas/vocabulary.py`
2. Move `VocabularyResponse` from validators
3. Keep existing API-specific schemas (VocabularyItemCreate, etc.) in `api/schemas.py`
4. Add proper docstrings

**Files to Create**:
- `src/runestone/schemas/vocabulary.py`

**Acceptance Criteria**:
- Vocabulary schemas organized by domain
- Clear separation between internal and API-specific models

---

### Task 3.2: Update Vocabulary Service
**Objective**: Update service to use new schemas

**Steps**:
1. Update imports in `src/runestone/services/vocabulary_service.py`
2. Update type annotations
3. Verify service tests pass

**Files to Modify**:
- `src/runestone/services/vocabulary_service.py`

**Acceptance Criteria**:
- Service uses unified schemas
- Tests pass: `make backend-test -k test_vocabulary`

---

## Phase 4: Cleanup and Testing (Day 6-7)

### Task 4.1: Remove Mappers Module
**Objective**: Delete the now-unused mappers module

**Steps**:
1. Verify no remaining imports of `mappers.py`
2. Delete `src/runestone/api/mappers.py`
3. Remove from any `__init__.py` exports

**Files to Delete**:
- `src/runestone/api/mappers.py`

**Acceptance Criteria**:
- File deleted
- No import errors
- All tests pass

---

### Task 4.2: Remove Old Validators Module
**Objective**: Delete the old validators module

**Steps**:
1. Verify no remaining imports of `validators.py`
2. Delete `src/runestone/core/prompt_builder/validators.py`
3. Update `prompt_builder/__init__.py` if needed

**Files to Delete**:
- `src/runestone/core/prompt_builder/validators.py`

**Acceptance Criteria**:
- File deleted
- No import errors
- All tests pass

---

### Task 4.3: Update Schema Exports
**Objective**: Ensure clean public API for schemas

**Steps**:
1. Update `src/runestone/schemas/__init__.py` with proper exports
2. Update `src/runestone/api/schemas.py` to re-export from unified schemas
3. Add docstrings explaining the organization

**Files to Modify**:
- `src/runestone/schemas/__init__.py`
- `src/runestone/api/schemas.py`

**Acceptance Criteria**:
- Clear import paths
- Proper `__all__` definitions
- Documentation updated

---

### Task 4.4: Update All Tests
**Objective**: Ensure all tests use new schema imports

**Steps**:
1. Update test imports across all test files
2. Fix any test assertions that check field names
3. Verify computed fields work in tests

**Files to Modify**:
- `tests/core/test_parsers.py`
- `tests/core/test_analyzer.py`
- `tests/core/test_processor.py`
- `tests/core/test_ocr.py`
- `tests/api/test_endpoints.py`
- `tests/api/test_schemas.py`

**Acceptance Criteria**:
- All tests pass: `make backend-test`
- No deprecation warnings
- Test coverage maintained

---

### Task 4.5: Update Frontend Types (if needed)
**Objective**: Ensure frontend TypeScript types match new API responses

**Steps**:
1. Review frontend type definitions
2. Update if API response format changed
3. Verify frontend tests pass

**Files to Check**:
- `frontend/src/hooks/useImageProcessing.ts`
- Frontend test files

**Acceptance Criteria**:
- Frontend types match API responses
- Frontend tests pass: `make frontend-test`

---

### Task 4.6: Run Full Test Suite
**Objective**: Verify entire system works correctly

**Steps**:
1. Run backend tests: `make backend-test`
2. Run frontend tests: `make frontend-test`
3. Run linting: `make lint`
4. Manual smoke test of key workflows

**Acceptance Criteria**:
- All backend tests pass
- All frontend tests pass
- No linting errors
- Manual testing successful

---

### Task 4.7: Update Documentation
**Objective**: Document the new schema organization

**Steps**:
1. Update README if it mentions schemas
2. Add docstrings to new schema modules
3. Update any architecture documentation
4. Document the decision tree for when to create separate API models

**Files to Modify**:
- `README.md` (if applicable)
- Schema module docstrings
- Any architecture docs

**Acceptance Criteria**:
- Documentation reflects new structure
- Clear guidance for future schema additions
- Examples provided

---

## Success Metrics

- ✅ Zero duplication between internal and API schemas
- ✅ All tests passing (backend + frontend)
- ✅ No linting errors
- ✅ API responses unchanged (backward compatible)
- ✅ Reduced lines of code (removed ~100 lines from mappers)
- ✅ Improved maintainability (single source of truth)

## Rollback Plan

If issues arise:
1. Keep old files in git history
2. Can revert specific commits
3. Tests will catch any breaking changes
4. Frontend types ensure API compatibility

## Estimated Timeline

- **Phase 1 (OCR)**: 2 days
- **Phase 2 (Analysis)**: 2 days
- **Phase 3 (Vocabulary)**: 1 day
- **Phase 4 (Cleanup)**: 2 days

**Total**: 7 days (1 sprint)

## Risk Mitigation

- Migrate one domain at a time (OCR → Analysis → Vocabulary)
- Run tests after each task
- Keep old files until all tests pass
- Manual testing of API endpoints
- Frontend type checking ensures API compatibility
