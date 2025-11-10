# Refactoring Plan: Enable User Email Editing

## 1. Executive Summary & Goals
This plan outlines the necessary steps to allow users to edit their email address from their profile page. The implementation will involve modifications to both the backend API to handle the update and validation, and the frontend profile component to provide the user interface for this change.

- **Primary Objective:** Implement a workflow for users to update their account's email address.
- **Key Goals:**
    1.  Modify the frontend profile page to make the email field editable.
    2.  Update the backend API to handle email change requests, ensuring the new email is not already in use.
    3.  Ensure the user's session and local data are correctly updated with the new email after a successful change.

## 2. Current Situation Analysis
Based on the provided file structure, the user profile system has the following characteristics:
-   **Frontend:** The `frontend/src/components/auth/Profile.tsx` component displays user information, including the email, but the email is currently presented as static, non-editable text. Profile updates are handled by the `updateProfile` function in the `frontend/src/hooks/useAuth.ts` hook.
-   **Backend:** The `PUT /api/me` endpoint, defined in `src/runestone/api/user_endpoints.py`, handles profile updates. The business logic resides in `src/runestone/services/user_service.py`. The current implementation does not support changing the email address.
-   **Limitation:** There is no mechanism to change a user's primary identifier (email), which is a critical account management feature.

## 3. Proposed Solution / Refactoring Strategy
### 3.1. High-Level Design / Architectural Overview
The solution involves a phased approach, starting with backend modifications to support the new functionality, followed by frontend changes to expose it to the user. Per user requirements, changing the email will not require current password verification. The primary backend validation will be to ensure the new email address is unique across the system.

**Workflow:**
1.  User navigates to the Profile page.
2.  User modifies the email address in the form.
3.  The frontend submits the new email to the `PUT /api/me` endpoint.
4.  The backend checks if the new email is available. If it is, it updates the user's record in the database.
5.  The backend returns the updated user profile data.
6.  The frontend updates its state (AuthContext, localStorage) with the new profile data, reflecting the change immediately in the UI.

### 3.2. Key Components / Modules
-   **`UserService` (Backend):** Will be modified to include logic for checking email uniqueness before updating the user record.
-   **`UserProfileUpdate` Schema (Backend):** Will be extended to include an optional `email` field.
-   **`Profile.tsx` Component (Frontend):** Will be updated to include an editable email field. Its submission logic will be adapted to handle the email change.
-   **`useAuth.ts` Hook (Frontend):** The `UpdateProfileData` interface will be extended to support sending the new email.

### 3.3. Detailed Action Plan / Phases
#### Phase 1: Backend Modifications (API & Service Layer)
-   **Objective(s):** Enable the `/api/me` endpoint to process email change requests.
-   **Priority:** High

-   **Task 1.1: Extend API Schemas**
    -   **File to Modify:** `src/runestone/api/schemas.py`
    -   **Action:** Add `email: Optional[str] = None` to the `UserProfileUpdate` Pydantic model.
    -   **Rationale/Goal:** To allow the API to accept the new email in the request body.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:** The `UserProfileUpdate` schema includes the new optional `email` field.

-   **Task 1.2: Implement Email Update Logic in Service Layer**
    -   **File to Modify:** `src/runestone/services/user_service.py`
    -   **Action:** In the `update_user_profile` method of `UserService`, add the following logic before updating the user object:
        1.  Check if `email` is present in `update_data` and is different from the user's current email.
        2.  If yes, check if the new email is already registered by another user using `self.user_repo.get_by_email`. Raise a `ValueError` if the email is taken.
        3.  If the check passes, proceed to update the user's email attribute.
    -   **Rationale/Goal:** To maintain data integrity by ensuring email uniqueness across all user accounts.
    -   **Estimated Effort:** M
    -   **Deliverable/Criteria for Completion:** The `update_user_profile` method correctly validates and updates a user's email. Unit tests for this new logic are written and passing.

-   **Task 1.3: Verify Endpoint Behavior**
    -   **File to Verify:** `src/runestone/api/user_endpoints.py`
    -   **Action:** No code changes are expected, but verify that the existing exception handling correctly translates `ValueError` from the service layer into a `400 Bad Request` HTTP response.
    -   **Rationale/Goal:** Ensure the API provides clear feedback to the client in case of validation errors (e.g., email taken).
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:** Manual or automated API tests confirm that an attempt to change to an existing email returns a 400 status code with an explanatory message.

#### Phase 2: Frontend Modifications (UI & State Management)
-   **Objective(s):** Update the user profile page to allow email editing.
-   **Priority:** High (Dependent on Phase 1)

-   **Task 2.1: Extend Frontend Auth Hook**
    -   **File to Modify:** `frontend/src/hooks/useAuth.ts`
    -   **Action:** Add `email?: string;` to the `UpdateProfileData` interface.
    -   **Rationale/Goal:** To type-safely prepare the payload for the updated backend API.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:** The `UpdateProfileData` interface is updated.

-   **Task 2.2: Update Profile Component UI and State**
    -   **File to Modify:** `frontend/src/components/auth/Profile.tsx`
    -   **Action:**
        1.  Add `email: ""` to the initial state of the `formData` `useState` hook.
        2.  In the `useEffect` that populates the form, set `email: userData.email || ""`.
        3.  Replace the static email display (`<div>Email: {userData.email}</div>`) with an `<AuthTextField>` for the email.
    -   **Rationale/Goal:** To provide the necessary UI for a user to change their email.
    -   **Estimated Effort:** M
    -   **Deliverable/Criteria for Completion:** The profile page displays an editable email field.

-   **Task 2.3: Implement Form Submission Logic**
    -   **File to Modify:** `frontend/src/components/auth/Profile.tsx`
    -   **Action:** Modify the `handleSubmit` function:
        1.  In the `updateData` object construction, conditionally add the `email` field if it has been changed from the original `userData.email`.
        2.  In the `try` block, after `await updateProfile(updateData)`, ensure the password fields are cleared from the form state as is currently done.
    -   **Rationale/Goal:** To implement the client-side logic for the email change workflow.
    -   **Estimated Effort:** S
    -   **Deliverable/Criteria for Completion:** The form correctly sends the new email in the payload when it is changed. The UI updates correctly on a successful change.

### 3.5. API Design / Interface Changes
-   **Endpoint:** `PUT /api/me`
-   **Request Body (`UserProfileUpdate` schema):**
    ```json
    {
      "name": "string (optional)",
      "surname": "string (optional)",
      "timezone": "string (optional)",
      "password": "string (optional, for changing password)",
      "email": "string (optional, for changing email)"
    }
    ```
-   **Response Body:** The `UserProfileResponse` schema remains unchanged but will return the updated user data, including the new email.

## 4. Key Considerations & Risk Mitigation
### 4.1. Technical Risks & Challenges
-   **Risk:** Changing an email without password verification exposes the account to takeover if a user's session is compromised (e.g., they left their computer unlocked).
    -   **Mitigation:** Per user requirements, this risk is accepted. The implementation will proceed without password verification for email changes. Standard session security measures (e.g., short session timeouts, secure cookie handling) remain the primary mitigation for session hijacking.
-   **Risk:** Race condition where two users try to claim the same new email address simultaneously.
    -   **Mitigation:** The `UNIQUE` constraint on the `email` column in the `users` table provides database-level protection against this. The service-layer check provides a cleaner error to the user whose request is processed second.

### 4.2. Dependencies
-   Frontend work (Phase 2) is dependent on the completion of the backend work (Phase 1).

### 4.3. Non-Functional Requirements (NFRs) Addressed
-   **Usability:** Users gain a critical account management feature, allowing them to update their primary contact information.

## 5. Success Metrics / Validation Criteria
-   A user can successfully change their email address via the profile page.
-   An attempt to change an email to one that is already in use by another account fails with a clear error message.
-   After a successful email change, the new email is displayed on the profile page without requiring a manual refresh.
-   The user can log out and log back in using their new email address and existing password.

## 6. Assumptions Made
-   The JWT payload is based on `user_id` and does not contain the user's email. Therefore, changing the email does not require token invalidation or re-issuance.
-   A full email verification flow (i.e., sending a confirmation link to the new email address) is not required for this task.

## 7. Open Questions / Areas for Further Investigation
-   There are no open questions at this time. The user has confirmed that email verification is not needed for now.
