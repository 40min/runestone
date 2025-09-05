# Refactoring/Design Plan: Web Application and Core Configuration Refactor for Runestone

## 1. Executive Summary & Goals
This plan outlines the process of wrapping the existing `runestone` CLI application with a web interface and simultaneously refactoring its core configuration management. The core image processing logic will be exposed via a REST API built with FastAPI. A single-page frontend using React and Tailwind CSS will be developed for user interaction. A centralized, type-safe configuration system using Pydantic will be implemented and integrated into both the core application and the new web backend.

-   **Goal 1:** Refactor the core application to use a centralized, type-safe configuration system, removing direct environment variable access from business logic.
-   **Goal 2:** Create a robust FastAPI backend that wraps the refactored `RunestoneProcessor` functionality, using dependency injection for configuration.
-   **Goal 3:** Develop a responsive, single-page React frontend with an intuitive file upload and results display interface.
-   **Goal 4:** Provide simple `Makefile` commands for running the entire web application locally, including a unified command for development.

## 2. Current Situation Analysis
The current system is a well-structured Python CLI application. The core business logic is encapsulated within the `runestone.core` module, particularly the `RunestoneProcessor` class.

-   **Strengths:** The separation of the core processing logic (`RunestoneProcessor`) from the presentation layer (`cli.py`) makes it straightforward to reuse the existing functionality in a new web context.
-   **Areas for Improvement:** Configuration is currently decentralized, with multiple direct calls to `os.getenv` in different parts of the application (e.g., `cli.py`, `core/clients/factory.py`). This makes configuration management brittle, harder to test, and less explicit.

## 3. Proposed Solution / Refactoring Strategy
### 3.1. High-Level Design / Architectural Overview
The target architecture is a client-server model. A new centralized configuration module will be consumed by both the existing CLI and the new API layer. The API layer will serve a new frontend client.

```mermaid
graph TD
    subgraph App Configuration
        A[env vars / .env file] --> B(Pydantic Settings: config.py)
    end
    
    subgraph Backend
        B --> C{FastAPI: DI}
        B --> D(CLI: cli.py)
        
        C --> E{API Endpoint: /api/process}
        D --> F(RunestoneProcessor)
        E --> F
        
        F --> G[runestone.core (OCR, Analyzer)]
        G --> H[LLM Provider API]
    end

    subgraph Frontend (Browser)
        I[React UI] <-->|HTTP| E
    end
```

### 3.2. Key Components / Modules
1.  **Configuration (New Module: `src/runestone/config.py`)**
    *   **Responsibility:** To define and load all application settings from environment variables in a centralized, type-safe manner.
    *   **Technology:** Pydantic `BaseSettings`.

2.  **Backend API (New Module: `src/runestone/api`)**
    *   **Responsibility:** To expose the core application functionality over HTTP.
    *   **Components:**
        *   `main.py`: FastAPI app instance, CORS middleware, API routers.
        *   `endpoints.py`: API endpoint for image processing.
        *   `schemas.py`: Pydantic models for API request/response contracts.

3.  **Frontend Application (New Directory: `frontend/`)**
    *   **Responsibility:** Provide a web-based user interface.
    *   **Technology:** React, Vite, Tailwind CSS.

### 3.3. Detailed Action Plan / Phases
#### Phase 1: Core Refactoring & Configuration Management
-   **Objective(s):** Centralize application configuration using Pydantic Settings and refactor core components to use this new system.
-   **Priority:** High

-   **Task 1.1:** Create Centralized Configuration Module
    -   **Rationale/Goal:** To create a single, type-safe source of truth for all configuration, improving maintainability and testability.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** A `src/runestone/config.py` file is created with a Pydantic `Settings` class that loads all necessary environment variables (`LLM_PROVIDER`, API keys, `VERBOSE`, etc.).

-   **Task 1.2:** Refactor Client Factory (`core/clients/factory.py`)
    -   **Rationale/Goal:** Decouple the client factory from the global environment by removing direct `os.getenv` calls.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `create_llm_client` function is updated to accept configuration parameters directly, rather than reading them from the environment.

-   **Task 1.3:** Refactor Core Processor (`core/processor.py`)
    -   **Rationale/Goal:** Update the main processor to be initialized via the centralized configuration.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `RunestoneProcessor` `__init__` method is updated to accept configuration parameters and pass them down to the `create_llm_client` function.

-   **Task 1.4:** Refactor CLI (`cli.py`)
    -   **Rationale/Goal:** Adapt the CLI to use the new `Settings` object, while still respecting command-line arguments as overrides.
    -   **Estimated Effort (Optional):** M
    -   **Deliverable/Criteria for Completion:** The `process` command in `cli.py` instantiates the `Settings` object and uses its values to configure the `RunestoneProcessor`. The CLI continues to function as before.

#### Phase 2: Backend Setup & API Implementation
-   **Objective(s):** Create a functional FastAPI server that exposes the refactored image processing logic.
-   **Priority:** High

-   **Task 2.1:** Update Project Dependencies
    -   **Rationale/Goal:** Add necessary libraries for building the web server.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `pyproject.toml` file is updated to include `fastapi`, `uvicorn[standard]`, and `python-multipart`.

-   **Task 2.2:** Create Backend Application Structure
    -   **Rationale/Goal:** Establish an organized structure for web-related code.
    -   **Estimated Effort (Optional):S**
    -   **Deliverable/Criteria for Completion:** New directory `src/runestone/api` is created with `__init__.py`, `main.py`, `endpoints.py`, `schemas.py`.

-   **Task 2.3:** Define API Response Schemas
    -   **Rationale/Goal:** Create Pydantic models for a consistent and validated API contract.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `src/runestone/api/schemas.py` file contains Pydantic models reflecting the structure of the processing result.

-   **Task 2.4:** Implement Image Processing Endpoint with DI
    -   **Rationale/Goal:** Create the core API endpoint that uses FastAPI's Dependency Injection to receive the centralized configuration.
    -   **Estimated Effort (Optional):** M
    -   **Deliverable/Criteria for Completion:** A `POST /api/process` endpoint is implemented in `src/runestone/api/endpoints.py`. It accepts a file upload, gets the `Settings` object via `Depends()`, instantiates and uses the `RunestoneProcessor`, and returns a valid JSON response.

-   **Task 2.5:** Configure FastAPI Application
    -   **Rationale/Goal:** Set up the main application entry point, including CORS middleware.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `src/runestone/api/main.py` file initializes the FastAPI app, includes the endpoint router, and configures `CORSMiddleware` to allow requests from `http://localhost:3000`.

-   **Task 2.6:** Add Backend Run Command to Makefile
    -   **Rationale/Goal:** Provide a simple command to start the backend server.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** A new target `run-backend` in the `Makefile` runs `uvicorn runestone.api.main:app --reload`.

#### Phase 3: Frontend Development
-   **Objective(s):** Build a single-page React application for image upload and result display.
-   **Priority:** High

-   **Task 3.1:** Bootstrap React + Tailwind Project
    -   **Rationale/Goal:** Set up the frontend project with all necessary build tools.
    -   **Estimated Effort (Optional):** M
    -   **Deliverable/Criteria for Completion:** A `frontend` directory is created with a React project (using Vite) and configured Tailwind CSS. An entry for `frontend/node_modules` is added to the root `.gitignore`.

-   **Task 3.2:** Implement File Upload and Results Display Components
    -   **Rationale/Goal:** Create the core UI for user interaction.
    -   **Estimated Effort (Optional):** L
    -   **Deliverable/Criteria for Completion:** React components for file upload, API communication, loading/error states, and structured results display are implemented and styled.

-   **Task 3.3:** Add Frontend Commands to Makefile
    -   **Rationale/Goal:** Simplify frontend development workflows.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** New `Makefile` targets: `install-frontend` (`npm install` in `frontend/`) and `run-frontend` (`npm run dev` in `frontend/`).

#### Phase 4: Finalization and Documentation
-   **Objective(s):** Ensure seamless integration, update documentation, and provide a unified development command.
-   **Priority:** Medium

-   **Task 4.1:** Add Unified Development Command
    -   **Rationale/Goal:** Create a single command to launch both the backend and frontend for a streamlined developer experience.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** A `run-dev` target is added to the `Makefile` that starts both the backend FastAPI server and the frontend Vite server concurrently.

-   **Task 4.2:** Update README
    -   **Rationale/Goal:** Document the new web interface and development process.
    -   **Estimated Effort (Optional):** S
    -   **Deliverable/Criteria for Completion:** The `README.md` is updated with a section on the web UI, prerequisites (`Node.js`), and instructions for using the new `Makefile` commands.

### 3.5. API Design / Interface Changes
-   **Endpoint:** `POST /api/process`
-   **Request:** `multipart/form-data` with a file field named `image`.
-   **Success Response (200 OK):** `application/json` with the full analysis result.
-   **Error Responses:** `422 Unprocessable Entity` for invalid input, `500 Internal Server Error` for processing failures.

## 4. Key Considerations & Risk Mitigation
### 4.1. Technical Risks & Challenges
-   **Risk:** Refactoring the core logic to use the new configuration system could introduce regressions in the CLI functionality.
    -   **Mitigation:** Perform thorough manual testing of the CLI's key features after the refactoring in Phase 1 to ensure it operates identically to the original version.
-   **Risk:** Cross-Origin Resource Sharing (CORS) will block requests from the frontend to the backend.
    -   **Mitigation:** The FastAPI application will be configured with `CORSMiddleware` to explicitly allow requests from the frontend's development origin.

### 4.2. Dependencies
-   **Internal:** Frontend development (Phase 3) is dependent on a functional backend API (Phase 2). The backend API is dependent on the core refactoring (Phase 1).
-   **External:** The development environment will now require `Node.js` and `npm` (or `yarn`) in addition to Python. This must be clearly documented.

### 4.3. Non-Functional Requirements (NFRs) Addressed
-   **Usability:** The web UI will dramatically improve usability for users not comfortable with a command line.
-   **Maintainability:** Centralizing configuration into a single Pydantic model makes the system easier to understand, configure, and maintain. Decoupling components into `core`, `cli`, `api`, and `frontend` improves modularity.

## 5. Success Metrics / Validation Criteria
-   The core refactoring is complete, and the CLI (`runestone process ...`) functions exactly as before.
-   The `run-dev` command successfully starts both the backend and frontend servers.
-   A user can navigate to the local web page, upload an image, and see the formatted analysis results displayed correctly.
-   The API is self-documenting and accessible via the `/docs` path provided by FastAPI.

## 6. Assumptions Made
-   The development environment has `Node.js` (v18+) and `npm` installed.
-   The `RunestoneProcessor` class is stateless and safe to be instantiated on a per-request basis.
-   All required application configuration can be sourced from environment variables.

## 7. Open Questions / Areas for Further Investigation
-   For the `run-dev` command, we will need to decide on a simple mechanism for running processes concurrently. A simple shell command using `&` within the Makefile is sufficient for this scope. Example: `(cd frontend && npm run dev) & uvicorn runestone.api.main:app --reload`.