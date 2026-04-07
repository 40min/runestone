# React Best-Practices Follow-Ups

## Context

This document captures concrete follow-up work from the April 7, 2026 frontend React audit.

## Priority Work

1. Fix form submit flow so native validation is preserved.
2. Improve keyboard accessibility for click-only UI elements.
3. Align interactive row/card behavior with accessible semantics.
4. Reduce hook dependency suppression where possible.

## Action Items

### 1) Restore native form validation in auth/profile forms

- Problem: submit buttons call `preventDefault()` in `onClick`, while forms already use `onSubmit`.
- Risk: HTML `required` and built-in email validity checks can be bypassed when clicking the button.
- Files:
  - `frontend/src/components/auth/Login.tsx`
  - `frontend/src/components/auth/Register.tsx`
  - `frontend/src/components/auth/Profile.tsx`
- Suggested approach:
  - Keep `type="submit"` buttons.
  - Remove `onClick` submit handlers.
  - Let each form `onSubmit` own submission.

### 2) Make image sidebar interactions keyboard-accessible

- Problem: non-button containers are used for click interactions.
- Risk: keyboard/screen-reader users have incomplete access.
- File:
  - `frontend/src/components/chat/ImageSidebar.tsx`
- Suggested approach:
  - Use `button`/`IconButton` for thumbnail open and modal close.
  - Add clear accessible labels for controls.
  - Ensure Enter/Space activation works via native button semantics.

### 3) Make file preview zoom interaction accessible

- Problem: preview zoom is attached directly to `<img onClick>`.
- Risk: mouse-only interaction.
- File:
  - `frontend/src/components/FileUpload.tsx`
- Suggested approach:
  - Move zoom toggle to a button wrapper or dedicated zoom button.
  - Keep image content separate from interactive control semantics.

### 4) Improve row/card click accessibility in table UI

- Problem: clickable `Paper`/`TableRow` rely on pointer events only.
- Risk: poor keyboard operability and unclear semantics for assistive tech.
- File:
  - `frontend/src/components/ui/DataTable.tsx`
- Suggested approach:
  - Prefer explicit row action buttons.
  - If row-level click remains, provide focus handling and keyboard activation.

### 5) Review `react-hooks/exhaustive-deps` suppressions

- Problem: dependency checks are suppressed in a few places.
- Risk: stale closures and harder maintenance over time.
- Files:
  - `frontend/src/components/auth/Profile.tsx`
  - `frontend/src/hooks/useChat.ts`
- Suggested approach:
  - Re-evaluate if current behavior can be preserved without lint suppression.
  - Where intentional, add short comments explaining the invariant and why suppression is safe.

## Validation Checklist

- `npm run lint` passes.
- Manual keyboard pass:
  - Can open/close image modal with keyboard.
  - Can activate row/card primary actions with keyboard.
  - Form submit validates required fields without custom click handlers.

## Out Of Scope For This Follow-Up

- Migration from MUI/emotion to shadcn/Tailwind.
- Large architecture refactors unrelated to the issues above.
