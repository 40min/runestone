# Refactoring/Design Plan: Persistent Agent Memory System

## 1. Executive Summary & Goals
The primary objective is to implement a persistent memory system for the teaching agent ("Björn") to track student progress, preferences, and learning gaps across sessions. This allows for a highly personalized teaching experience where the agent remembers past mistakes and mastered concepts.

**Key Goals:**
- **Persistent Personalization**: Inject student-specific context into the agent's system prompt.
- **Autonomous Learning**: Enable the agent to update student records via specialized tools.
- **User Control**: Provide API endpoints for users to view, edit, and prune (clear) their memory data.

## 2. Current Situation Analysis
The current `AgentService` and `ChatService` are stateless regarding long-term student data. While conversation history is maintained, the agent has no "memory" of the student's overall level, recurring struggles, or personal goals. The `User` model lacks fields for storing unstructured behavioral data, and the system prompt is currently static.

## 3. Proposed Solution / Refactoring Strategy

### 3.1. High-Level Design / Architectural Overview
The system will use a **Hybrid Memory Approach**:
1.  **Injection**: At the start of a chat session, the user's memory (stored as JSON) is fetched and formatted into the agent's system prompt.
2.  **Observation & Update**: During the session, the agent can call `update_memory` to record new insights.
3.  **Manual Management**: The user can interact with the memory via the profile settings to correct or delete information.

### 3.2. Key Components / Modules

-   **Data Storage (`runestone.db.models`)**: Three new TEXT columns in the `User` model to store JSON strings.
-   **Memory Utility (`runestone.utils.logic`)**: A new utility module containing the `deep_merge` function for recursive JSON updates.
-   **Agent Tooling (`runestone.agent.service`)**: Implementation of the `UpdateMemoryTool` using LangChain's tool-calling interface.
-   **Service Orchestration (`runestone.services.chat_service`)**: Logic to handle tool execution and database persistence during a chat flow.
-   **Pruning API (`runestone.api.user_endpoints`)**: New endpoints to allow manual cleanup of memory fields.

### 3.3. Detailed Action Plan / Phases

#### Phase 1: Foundation & Data Layer
**Objective:** Prepare the database and schemas for JSON storage.
**Priority:** High

-   **Task 1.1: Update User Model**
    -   **Rationale:** Add `personal_info`, `areas_to_improve`, and `knowledge_strengths` columns to the `User` class.
    -   **Deliverable:** Updated `src/runestone/db/models.py` and a new Alembic migration.
-   **Task 1.2: Update API Schemas**
    -   **Rationale:** Include the new memory fields in `UserProfileResponse` and `UserProfileUpdate` to allow the UI to display/edit them.
    -   **Deliverable:** Updated `src/runestone/api/schemas.py`.
-   **Task 1.3: Repository Methods**
    -   **Rationale:** Add `update_user_memory` and `clear_user_memory` to `UserRepository`.
    -   **Deliverable:** Functional DB methods in `src/runestone/db/user_repository.py`.

#### Phase 2: Logic & Tooling
**Objective:** Implement the "Deep Merge" and the Agent's update tool.
**Priority:** High

-   **Task 2.1: Implement Deep Merge Utility**
    -   **Rationale:** Create a recursive merge function to handle incremental updates to nested JSON structures.
    -   **Deliverable:** `deep_merge` in `src/runestone/utils/logic.py`.
-   **Task 2.2: Define UpdateMemoryTool**
    -   **Rationale:** Create the tool definition that the LLM will use to trigger updates.
    -   **Deliverable:** Tool schema in `src/runestone/agent/service.py`.

#### Phase 3: Agent Integration
**Objective:** Connect the agent to the memory flow.
**Priority:** High

-   **Task 3.1: System Prompt Injection**
    -   **Rationale:** Modify `AgentService.generate_response` to accept memory data and inject it into the prompt as `STUDENT MEMORY`.
    -   **Deliverable:** Personalized agent prompts.
-   **Task 3.2: Tool Execution Loop**
    -   **Rationale:** Update `ChatService.process_message` to detect tool calls from the LLM, execute the `deep_merge` or `replace` logic, and save to the DB.
    -   **Deliverable:** Working autonomous memory updates.

#### Phase 4: Management & Pruning
**Objective:** Enable manual cleanup and management.
**Priority:** Medium

-   **Task 4.1: Implement Pruning Endpoints**
    -   **Rationale:** Add `DELETE` functionality to clear specific memory categories or all memory at once.
    -   **Deliverable:** New routes in `src/runestone/api/user_endpoints.py`.
-   **Task 4.2: JSON Validation**
    -   **Rationale:** Ensure manual edits via `PUT /me` validate that the input is valid JSON.
    -   **Deliverable:** Validation logic in `UserService.update_user_profile`.

### 3.4. Data Model Changes
**Table: `users`**
-   `personal_info`: `TEXT` (JSON) - Stores identity, preferences, goals.
-   `areas_to_improve`: `TEXT` (JSON) - Stores struggles and patterns.
-   `knowledge_strengths`: `TEXT` (JSON) - Stores mastered skills.

### 3.5. API Design / Interface Changes

-   **GET `/api/me`**: Now includes the three memory objects.
-   **PUT `/api/me`**: Allows updating memory objects (Last write wins).
-   **DELETE `/api/me/memory`**:
    -   `category` (query param): Optional. Clears one field if provided, otherwise clears all three.

## 4. Key Considerations & Risk Mitigation

### 4.1. Technical Risks & Challenges
-   **Conflict Resolution**: As per requirements, "Last write wins" is implemented. If the agent and user update simultaneously, the final database commit persists.
-   **Token Bloat**: Large JSON objects could consume significant context window.
    -   *Mitigation*: The agent is instructed to focus on "actionable insights" to keep memory concise.

### 4.2. Dependencies
-   **LLM Tool Support**: Requires a model that supports function calling (e.g., GPT-4o or Grok-2).
-   **Database**: SQLite/Postgres must handle the storage of JSON strings in TEXT columns.

### 4.3. Non-Functional Requirements (NFRs)
-   **Usability**: The manual pruning feature ensures users can "reset" Björn's perception of them if it becomes inaccurate.
-   **Reliability**: The `deep_merge` function ensures that adding a new "strength" doesn't accidentally delete existing "personal info".

## 5. Success Metrics / Validation Criteria
-   The agent successfully greets the user by a name stored in `personal_info`.
-   The agent calls the `update_memory` tool when a user repeatedly fails a specific grammar point.
-   The user can successfully clear the `areas_to_improve` field via the API, and the agent no longer sees that context in the next message.

## 6. Assumptions Made
-   The agent is capable of maintaining its own internal JSON structure without a strict schema.
-   The UI will provide a JSON editor or simple text area for manual memory modifications.
-   "Last write wins" is acceptable for the current scale of the application.

## 7. Open Questions / Areas for Further Investigation
-   **Summarization**: Should we implement an automated "Memory Summarization" task if the JSON grows too large for the system prompt? (Not yet).
-   **Template Reset**: While "Reset to Template" is out of scope, we should monitor if agents struggle to initialize their own structures.
