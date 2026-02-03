---
name: readiness-check
description: Check project readiness including tests, linting, and frontend build.
---

# Readiness Check Skill

This skill allows the agent to verify that the project is in a healthy state before committing or pushing changes. It is particularly useful for avoiding container build failures.

## Instructions

Whenever you are about to finalize a task or if the user asks you to check readiness, follow these steps:

1. **End of Implementation (CRITICAL)**: Always run this check at the very end of an **Implementation Plan** or any significant code change before declaring the task "Done".
2. **Run the check**: Execute `make check-readiness` from the project root.
3. **Review Output**:
   - If **linting** fails: Fix the formatting or code quality issues. You can use `make lint` to automatically fix most issues.
   - If **tests** fail: Investigate the failures in `tests/` (backend) or `frontend/` (frontend) and fix the logic.
   - If **build** fails: Check the TypeScript errors in the frontend. This is the "dry run" for the production container build.
4. **Report**: Inform the user if the checks passed or what needs to be fixed.

## Makefile Commands Used
- `make check-readiness`: Aggregated command for linting, testing, and building.
- `make lint-check`: Check linting without fixing.
- `make test`: Run all tests.
- `cd frontend && npm run build`: Verify production build.
