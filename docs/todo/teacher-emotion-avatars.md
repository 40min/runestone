# Teacher Emotion Avatars

## Summary
Save this implementation plan as `docs/todo/teacher-emotion-avatars.md`, then add hidden per-reply emotion metadata to Teacher chat so Björn's avatar changes per assistant message. Emotion is persisted with assistant messages, returned through the API, and rendered in the frontend without exposing the emotion label to the student.

## Key Changes
- Add a shared emotion enum matching `frontend/src/assets/emotions`: `neutral`, `happy`, `sad`, `worried`, `concerned`, `thinking`, `hopeful`, `surprised`, `serious`.
- Change Teacher generation to return a structured final response envelope:
  - `message`: student-facing reply text only.
  - `emotion`: one allowed emotion value.
- Use LangChain `create_agent(..., response_format=TeacherOutput)` so Teacher keeps tool access while producing typed output.
- Update Teacher prompt instructions to choose one emotion for every assistant reply and never include the emotion in visible text.
- Normalize invalid or missing emotion to `neutral`.
- Keep post-response specialists and TTS receiving only the student-facing `message`.

## API, Persistence, And Frontend
- Add nullable `teacher_emotion` column to `chat_messages` with an Alembic migration.
- Extend backend response/history schemas with `teacher_emotion`.
- Update `TeacherAgent`, `AgentsManager`, `ChatService`, and `ChatRepository` to propagate and persist assistant emotion.
- Keep `sources` behavior unchanged.
- Extend frontend chat types with `teacherEmotion`.
- Update `TeacherAvatar` to map emotion to the PNG assets and fall back to `neutral`.
- Render each assistant message with its persisted emotion.
- Update `ChatHeader` to show `thinking` while Teacher is loading, otherwise latest assistant emotion or `neutral`.

## Test Plan
- Backend:
  - Teacher build test verifies `response_format` and emotion prompt instructions.
  - Teacher generation returns text plus emotion from `structured_response`.
  - Invalid/missing structured emotion falls back to `neutral`.
  - Manager/service tests propagate and persist emotion.
  - API tests assert `/api/chat/message`, `/api/chat/image`, and `/api/chat/history` include `teacher_emotion`.
  - History tests cover old rows with null emotion.
- Frontend:
  - `useChat` maps `teacher_emotion` from send response and history.
  - `ChatMessageBubble` passes message emotion into `TeacherAvatar`.
  - `ChatHeader` uses latest assistant emotion and switches to `thinking` during loading.
  - Missing/unknown emotion renders neutral.
- Browser skill verification:
  - Use the Playwright skill after starting the dev app.
  - Run a real browser chat flow, send at least two mocked or real Teacher messages with different emotions, and verify via snapshot/screenshot that the header avatar and per-message avatars change.
  - Save screenshots under `output/playwright/` if artifacts are useful.
  - Use commands based on the skill wrapper:
    ```bash
    export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
    export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
    "$PWCLI" open http://localhost:5173 --headed
    "$PWCLI" snapshot
    "$PWCLI" screenshot output/playwright/teacher-emotion-avatars.png
    ```
- Validation commands:
  - `uv run pytest tests/agents/test_teacher.py tests/agents/test_manager.py tests/services/test_chat_service.py tests/api/test_chat_endpoints.py`
  - `cd frontend && npm run test:run -- useChat ChatMessageBubble ChatView`
  - `cd frontend && npm run build`

## Assumptions
- Emotion is persisted per assistant message, and the header reflects the latest assistant emotion.
- Emotion is UI metadata only; it is not spoken by TTS, included in markdown, or displayed as text.
- Image-upload Teacher replies should also receive and persist emotion.
- Existing chat history remains backward-compatible via `neutral` fallback.
