# Refactoring Plan: Standardize Dependency Injection in FastAPI Backend

## 1. Executive Summary & Goals
This plan outlines the refactoring of the Runestone backend to consistently use FastAPI's Dependency Injection (DI) mechanism. Currently, several API endpoints manually instantiate processor and service classes, which leads to tight coupling, reduced testability, and architectural inconsistency.

The primary goals of this refactoring are:
-   **Standardize Dependency Management:** Consistently use `fastapi.Depends` for all service and processor dependencies within the API layer.
-   **Improve Testability:** Enable straightforward mocking of dependencies in tests using FastAPI's `dependency_overrides`.
-   **Enhance Maintainability:** Decouple API endpoints from the concrete implementation of their dependencies, making the system more modular and easier to maintain.

## 2. Current Situation Analysis
Based on the provided file structure, the current implementation exhibits an inconsistent approach to dependency management:

-   **Pain Point 1: Manual Instantiation in Endpoints:** In `src/runestone/api/endpoints.py`, the `/ocr`, `/analyze`, and `/resources` endpoints manually create an instance of `RunestoneProcessor`. This is contrary to the DI pattern used by the vocabulary-related endpoints in the same file.
-   **Pain Point 2: Chained Manual Instantiation:** The `RunestoneProcessor` class, in turn, manually instantiates its own dependencies (`OCRProcessor`, `ContentAnalyzer`). These classes also create their own `BaseLLMClient` dependency via a factory. This creates a rigid chain of dependencies that is difficult to manage and test.
-   **Pain Point 3: Inefficient Resource Creation:** The `VocabularyService.improve_item` method creates a new LLM client on every call, which is inefficient and makes testing the method in isolation more complex. The client should be a dependency of the service itself.

## 3. Proposed Solution / Refactoring Strategy
The strategy is to refactor the codebase from the core components outwards (bottom-up), making them ready for injection, then creating the necessary dependency providers, and finally updating the API endpoints to use them.

### 3.1. High-Level Design / Architectural Overview
We will introduce dependency providers for all major components (`BaseLLMClient`, `OCRProcessor`, `ContentAnalyzer`, `RunestoneProcessor`) and inject them where needed. The final dependency graph for an API call will look like this:

```mermaid
graph TD
    subgraph API Layer
        A[API Endpoint]
    end

    subgraph Dependency Injection
        B(Depends(...))
    end

    subgraph Service Layer
        C[RunestoneProcessor]
        D[VocabularyService]
    end

    subgraph Core Components
        E[OCRProcessor]
        F[ContentAnalyzer]
        G[BaseLLMClient]
        H[VocabularyRepository]
    end

    subgraph Database
        I[DB Session]
    end

    subgraph Configuration
        J[Settings]
    end

    A -- Uses --> B
    B -- Provides --> C
    B -- Provides --> D

    C --> E
    C --> F

    D --> H
    D --> G

    E --> G
    F --> G

    H --> I
    G --> J
```

### 3.2. Key Components / Modules
-   **`src/runestone/dependencies.py`**: This file will be expanded to include provider functions for `BaseLLMClient`, `OCRProcessor`, `ContentAnalyzer`, and `RunestoneProcessor`. The existing `get_vocabulary_service` will be updated.
-   **`src/runestone/core/*.py`**: `OCRProcessor`, `ContentAnalyzer`, and `RunestoneProcessor` will be modified to accept their dependencies in their `__init__` methods instead of creating them.
-   **`src/runestone/services/vocabulary_service.py`**: Will be modified to accept `BaseLLMClient` in its `__init__` method.
-   **`src/runestone/api/endpoints.py`**: The `/ocr`, `/analyze`, and `/resources` endpoints will be updated to receive `RunestoneProcessor` via `Depends`.

### 3.3. Detailed Action Plan / Phases

#### Phase 1: Refactor Core Components for Injection
-   **Objective(s):** Modify core classes to accept dependencies via their constructors, removing internal instantiation logic.
-   **Priority:** High

-   **Task 1.1:** Refactor `OCRProcessor` and `ContentAnalyzer`
    -   **Rationale/Goal:** Decouple these processors from the LLM client factory.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   The `__init__` methods of `OCRProcessor` and `ContentAnalyzer` are updated to accept an instance of `BaseLLMClient` as an argument.
        -   Internal calls to `create_llm_client` are removed from their constructors.

-   **Task 1.2:** Refactor `RunestoneProcessor`
    -   **Rationale/Goal:** Decouple the main processor from its sub-processors.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   The `__init__` method of `RunestoneProcessor` is updated to accept instances of `OCRProcessor` and `ContentAnalyzer` as arguments.
        -   Internal instantiation of these classes is removed.

-   **Task 1.3:** Refactor `VocabularyService`
    -   **Rationale/Goal:** Inject the LLM client to avoid per-call instantiation and improve testability.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   The `__init__` method of `VocabularyService` is updated to accept an instance of `BaseLLMClient`.
        -   The `improve_item` method is updated to use the injected client (`self.llm_client`) instead of calling `create_llm_client`.

---

#### Phase 2: Create and Update Dependency Providers
-   **Objective(s):** Implement the provider functions in `dependencies.py` that will construct and yield the refactored components.
-   **Priority:** High

-   **Task 2.1:** Create `get_llm_client` provider
    -   **Rationale/Goal:** Provide a single, reusable function to get a configured LLM client.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   A new function `get_llm_client(settings: Annotated[Settings, Depends(get_settings)]) -> BaseLLMClient` is added to `dependencies.py`.
        -   This function uses the `create_llm_client` factory to return a client instance.

-   **Task 2.2:** Create providers for `OCRProcessor` and `ContentAnalyzer`
    -   **Rationale/Goal:** Create injectable providers for the core processors.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   New functions `get_ocr_processor` and `get_content_analyzer` are added to `dependencies.py`.
        -   Each function depends on `get_llm_client` and `get_settings` to instantiate its respective class.

-   **Task 2.3:** Create `get_runestone_processor` provider
    -   **Rationale/Goal:** Create the top-level injectable provider for the main processor.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   A new function `get_runestone_processor` is added to `dependencies.py`.
        -   It depends on `get_ocr_processor` and `get_content_analyzer` to instantiate `RunestoneProcessor`.

-   **Task 2.4:** Update `get_vocabulary_service` provider
    -   **Rationale/Goal:** Inject the new `BaseLLMClient` dependency into the `VocabularyService`.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:**
        -   The `get_vocabulary_service` function in `dependencies.py` is updated to also depend on `get_llm_client`.
        -   The `VocabularyService` is instantiated with the repository, settings, and the new LLM client.

---

#### Phase 3: Update API Endpoints
-   **Objective(s):** Replace all manual instantiations in the API endpoints with the new dependency providers.
-   **Priority:** High

-   **Task 3.1:** Refactor OCR, Analyze, and Resources endpoints
    -   **Rationale/Goal:** Standardize dependency management in the API layer.
    -   **Estimated Effort:** M
    -   **Deliverable/Criteria for Completion:**
        -   In `endpoints.py`, the signatures of `process_ocr`, `analyze_content`, and `find_resources` are updated to include `processor: Annotated[RunestoneProcessor, Depends(get_runestone_processor)]`.
        -   The manual instantiation `processor = RunestoneProcessor(...)` is removed from the body of these functions.

---

#### Phase 4: Update Tests
-   **Objective(s):** Adapt all affected tests to the new DI-based architecture to ensure the application remains stable.
-   **Priority:** High

-   **Task 4.1:** Update API endpoint tests
    -   **Rationale/Goal:** Tests for `/ocr`, `/analyze`, and `/resources` will fail because they patch the wrong location. They must be updated to use dependency overrides.
    -   **Estimated Effort:** M
    -   **Deliverable/Criteria for Completion:**
        -   In `tests/api/test_endpoints.py`, tests for the affected endpoints are modified.
        -   Instead of `@patch("runestone.api.endpoints.RunestoneProcessor")`, they use `app.dependency_overrides` to inject a mock `RunestoneProcessor`.

-   **Task 4.2:** Update core component and service tests
    -   **Rationale/Goal:** Unit tests for `RunestoneProcessor`, `OCRProcessor`, `ContentAnalyzer`, and `VocabularyService` will fail due to changed constructor signatures.
    -   **Estimated Effort:** M
    -   **Deliverable/Criteria for Completion:**
        -   Tests in `tests/core/` and `tests/services/` are updated to pass mock dependencies to the constructors of the classes under test.

## 4. Key Considerations & Risk Mitigation
### 4.1. Technical Risks & Challenges
-   **Risk:** Incorrectly configured dependency chain.
    -   **Mitigation:** The bottom-up approach ensures that dependencies are correctly configured before their dependents are refactored. Running tests after each phase will catch issues early.
-   **Risk:** Performance overhead from DI.
    -   **Mitigation:** FastAPI's DI is highly optimized. For dependencies that are expensive to create, FastAPI's `Depends` caching mechanism will prevent re-creation within the same request, so performance impact will be negligible or even positive (e.g., `VocabularyService` no longer creates an LLM client on every call).

### 4.2. Dependencies
-   **Internal:** Tasks within phases are largely independent, but phases should be executed in order (Phase 1 -> 2 -> 3 -> 4).

### 4.3. Non-Functional Requirements (NFRs) Addressed
-   **Maintainability:** Significantly improved. Components are decoupled and follow a standard pattern, making them easier to understand, modify, and replace.
-   **Testability:** Significantly improved. All major components can be easily mocked at the boundary of the API using `dependency_overrides`, allowing for true unit testing of the endpoint logic.

## 5. Success Metrics / Validation Criteria
-   All existing unit and integration tests pass after the refactoring.
-   Manual instantiation of `RunestoneProcessor`, `OCRProcessor`, `ContentAnalyzer`, and `BaseLLMClient` is removed from the API and service layers.
-   The `/ocr`, `/analyze`, and `/resources` endpoints successfully process requests using the injected `RunestoneProcessor`.
-   Code review confirms adherence to FastAPI's DI best practices across the entire API layer.

## 6. Assumptions Made
-   The current DI pattern used for `get_vocabulary_service` is the desired standard for the application.
-   The logic within the processors and services does not need to change, only the way they receive their dependencies.
-   Refactoring of non-API components like `cli.py` and the `recall` service is out of scope for this task but can be considered as a future improvement leveraging the new injectable components.