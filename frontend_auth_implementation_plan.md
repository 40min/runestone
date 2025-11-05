# Frontend Authentication Implementation Plan
## Comprehensive Fix & Improvement Strategy

**Project**: Runestone Multi-User Authentication (Phases 4 & 5)
**Date**: 2025-11-05
**Status**: Implementation Planning

---

## Executive Summary

This document outlines a prioritized implementation plan to address all identified issues in the frontend authentication system. The strategy follows a **refactor-first, test-after** approach to avoid duplicate work and ensure tests validate the final, improved code structure.

**Key Principle**: Complete all refactoring and code improvements BEFORE writing comprehensive tests. This prevents writing tests twice and ensures tests validate the final architecture.

---

## Implementation Phases

### Phase 1: Critical Bug Fixes (P0)
**Objective**: Fix blocking issues that prevent core functionality
**Estimated Effort**: 1-2 hours

#### 1.1 Fix Missing Authorization Header in updateProfile()
- **File**: `frontend/src/hooks/useAuth.ts:116`
- **Issue**: Profile updates fail with 401 Unauthorized
- **Solution**: Add Authorization header with Bearer token
- **Implementation**:
  ```typescript
  const token = localStorage.getItem('auth_token');
  headers: {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  }
  ```

---

### Phase 2: Code Quality & Refactoring (P1)
**Objective**: Improve code maintainability and consistency
**Estimated Effort**: 4-6 hours

#### 2.1 Refactor All Hooks to Use Centralized useApi Hook
**Rationale**: Eliminate code duplication, ensure consistent auth handling

**Files to Refactor**:
1. **`frontend/src/hooks/useAuth.ts`**
   - Replace direct `fetch` calls with `useApi` hook
   - Remove manual Authorization header construction
   - Simplify error handling (useApi handles 401 automatically)

2. **`frontend/src/hooks/useImageProcessing.ts`**
   - Replace manual Authorization header injection
   - Use `useApi` for all API calls
   - Remove duplicate 401 handling logic

3. **`frontend/src/hooks/useVocabulary.ts`**
   - Replace manual Authorization header injection
   - Use `useApi` for all API calls
   - Remove duplicate 401 handling logic

**Benefits**:
- Single source of truth for API calls
- Automatic auth header injection
- Consistent 401 error handling
- Easier to maintain and test

#### 2.2 Standardize Error Handling Patterns
**Current Issues**:
- Mixed use of `localError` state and hook error state
- Inconsistent error message display
- Different error handling approaches across components

**Solution**:
1. Create standardized error handling pattern
2. Use consistent error state management
3. Implement uniform error display component

**Files to Update**:
- `frontend/src/components/auth/Login.tsx`
- `frontend/src/components/auth/Register.tsx`
- `frontend/src/components/auth/Profile.tsx`

**Approach**:
```typescript
// Standardized pattern
const { error, setError } = useState<string>('');
// Display errors consistently
{error && <ErrorAlert message={error} />}
```

#### 2.3 Extract Duplicate Button Styling to Shared Component
**Issue**: 100+ lines of identical button styling duplicated across 3 components

**Solution**: Create `AuthButton` component

**New File**: `frontend/src/components/auth/AuthButton.tsx`
```typescript
interface AuthButtonProps {
  loading?: boolean;
  children: React.ReactNode;
  onClick?: (e: React.FormEvent) => void;
  type?: 'submit' | 'button';
}
```

**Files to Update**:
- `frontend/src/components/auth/Login.tsx:101-126`
- `frontend/src/components/auth/Register.tsx:182-207`
- `frontend/src/components/auth/Profile.tsx:232-257`

---

### Phase 3: UX Improvements (P2)
**Objective**: Enhance user experience and completeness
**Estimated Effort**: 2-3 hours

#### 3.1 Add Registration Link to Login Component
**File**: `frontend/src/components/auth/Login.tsx`
**Issue**: No way to navigate to registration from login page
**Solution**: Add "Don't have an account? Register" button (similar to Register.tsx:209-215)

#### 3.2 Resolve TODO Comments
**Files with TODOs**:
1. `frontend/src/components/auth/Register.tsx:80`
   - TODO: "rewrite with standart components"
   - **Decision**: Implement or remove before merge

2. `frontend/src/components/auth/Profile.tsx:134`
   - TODO: "rewrite with standardised components"
   - **Decision**: Implement or remove before merge

**Options**:
- **Option A**: Extract TextField styling to shared component
- **Option B**: Remove TODOs and accept current implementation
- **Recommendation**: Option A - create `AuthTextField` component

#### 3.3 Add Missing User Stats to Profile
**File**: `frontend/src/components/auth/Profile.tsx:104`
**Current**: Only shows `pages_recognised_count`
**Missing**:
- `words_in_learn_count`
- `words_learned_count`

**Solution**:
1. Verify backend API returns these stats
2. Add display in Profile component
3. Update UserData interface if needed

#### 3.4 Improve Type Safety
**File**: `frontend/src/hooks/useAuth.ts:27`
**Issue**: `updateProfile` accepts `Partial<UserData> & { password?: string }` but password isn't in UserData

**Solution**: Create separate interface
```typescript
interface UpdateProfileData {
  name?: string | null;
  surname?: string | null;
  timezone?: string;
  password?: string;
}
```

---

### Phase 4: Comprehensive Testing (After All Refactoring)
**Objective**: Validate final implementation with complete test coverage
**Estimated Effort**: 6-8 hours

**IMPORTANT**: Only start this phase after Phases 1-3 are complete!

#### 4.1 Create Test Files

**Test File Structure**:
```
frontend/src/
├── components/auth/
│   ├── Login.test.tsx          [NEW]
│   ├── Register.test.tsx       [NEW]
│   ├── Profile.test.tsx        [NEW]
│   └── AuthButton.test.tsx     [NEW - if created in Phase 2.3]
├── context/
│   └── AuthContext.test.tsx    [NEW]
├── hooks/
│   └── useAuth.test.ts         [NEW]
└── utils/
    └── api.test.ts             [NEW]
```

#### 4.2 Test Coverage Requirements

**1. Login.test.tsx**
- ✅ Successful login flow
- ✅ Failed login (invalid credentials)
- ✅ Password validation (min 6 chars)
- ✅ Loading states
- ✅ Error display
- ✅ Navigation to register (after Phase 3.1)

**2. Register.test.tsx**
- ✅ Successful registration
- ✅ Password mismatch validation
- ✅ Password length validation (min 6 chars)
- ✅ Auto-login after registration
- ✅ Loading states
- ✅ Error display
- ✅ Navigation to login

**3. Profile.test.tsx**
- ✅ Profile data display
- ✅ Profile update success
- ✅ Profile update failure
- ✅ Password change validation
- ✅ Stats display (all stats after Phase 3.3)
- ✅ Loading states

**4. AuthContext.test.tsx**
- ✅ Token persistence in localStorage
- ✅ User data persistence
- ✅ Login/logout state changes
- ✅ isAuthenticated() function
- ✅ Malformed localStorage data handling
- ✅ Context provider wrapping

**5. useAuth.test.ts**
- ✅ Login action (using useApi after Phase 2.1)
- ✅ Register action (using useApi after Phase 2.1)
- ✅ UpdateProfile action (using useApi after Phase 2.1)
- ✅ Error handling
- ✅ Loading states
- ✅ Auto-login after registration

**6. api.test.ts**
- ✅ Authorization header injection
- ✅ 401 response handling (triggers logout)
- ✅ Successful API calls
- ✅ Error handling
- ✅ Token retrieval from AuthContext

#### 4.3 Update Existing Tests
**Files to Review/Update**:
- ✅ `frontend/src/App.test.tsx` - Already mocks AuthContext
- ⚠️ `frontend/src/hooks/useImageProcessing.test.ts` - May need auth mocking after Phase 2.1
- ⚠️ `frontend/src/hooks/useVocabulary.test.ts` - May need auth mocking after Phase 2.1

---

## Detailed Implementation Steps

### Step-by-Step Execution Order

#### Stage 1: Critical Fixes (Day 1, Morning)
1. ✅ Fix Authorization header in `useAuth.ts:116`
2. ✅ Test manually that profile updates work
3. ✅ Commit: "fix: add Authorization header to updateProfile"

#### Stage 2: Refactoring (Day 1, Afternoon + Day 2, Morning)
4. ✅ Refactor `useAuth.ts` to use `useApi` hook
5. ✅ Refactor `useImageProcessing.ts` to use `useApi` hook
6. ✅ Refactor `useVocabulary.ts` to use `useApi` hook
7. ✅ Test manually that all API calls still work
8. ✅ Commit: "refactor: use centralized useApi hook for all API calls"

9. ✅ Create `AuthButton` component
10. ✅ Update Login, Register, Profile to use `AuthButton`
11. ✅ Commit: "refactor: extract AuthButton shared component"

12. ✅ Standardize error handling across auth components
13. ✅ Commit: "refactor: standardize error handling in auth components"

#### Stage 3: UX Improvements (Day 2, Afternoon)
14. ✅ Add registration link to Login component
15. ✅ Commit: "feat: add registration link to login page"

16. ✅ Create `AuthTextField` component (if implementing TODO)
17. ✅ Update auth components to use `AuthTextField`
18. ✅ Remove TODO comments
19. ✅ Commit: "refactor: extract AuthTextField shared component"

20. ✅ Add missing user stats to Profile
21. ✅ Create `UpdateProfileData` interface
22. ✅ Commit: "feat: add missing user stats and improve type safety"

#### Stage 4: Comprehensive Testing (Day 3-4)
23. ✅ Create `AuthContext.test.tsx` with full coverage
24. ✅ Create `api.test.ts` with full coverage
25. ✅ Create `useAuth.test.ts` with full coverage
26. ✅ Run tests: `npm test` - ensure all pass
27. ✅ Commit: "test: add comprehensive tests for auth utilities"

28. ✅ Create `Login.test.tsx` with full coverage
29. ✅ Create `Register.test.tsx` with full coverage
30. ✅ Create `Profile.test.tsx` with full coverage
31. ✅ Create `AuthButton.test.tsx` if component was created
32. ✅ Run tests: `npm test` - ensure all pass
33. ✅ Commit: "test: add comprehensive tests for auth components"

34. ✅ Update `useImageProcessing.test.ts` if needed
35. ✅ Update `useVocabulary.test.ts` if needed
36. ✅ Run full test suite: `make frontend-test`
37. ✅ Commit: "test: update existing tests for auth integration"

---

## Testing Strategy

### Test Patterns to Follow

**1. Component Testing Pattern** (from `App.test.tsx`):
```typescript
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { AuthProvider } from './context/AuthContext';

// Mock AuthContext
vi.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    isAuthenticated: () => false,
    userData: null,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));
```

**2. Hook Testing Pattern**:
```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

// Mock fetch
global.fetch = vi.fn();

// Test hook
const { result } = renderHook(() => useAuthActions());
```

**3. API Mocking Pattern**:
```typescript
beforeEach(() => {
  global.fetch = vi.fn();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// Mock successful response
(global.fetch as any).mockResolvedValueOnce({
  ok: true,
  json: async () => ({ access_token: 'test-token' }),
});
```

---

## Success Criteria

### Definition of Done

**Phase 1 Complete When**:
- ✅ Profile updates work without 401 errors
- ✅ Manual testing confirms fix

**Phase 2 Complete When**:
- ✅ All hooks use `useApi` consistently
- ✅ No duplicate API call logic
- ✅ Shared components extracted (AuthButton, optionally AuthTextField)
- ✅ Error handling standardized
- ✅ Manual testing confirms all features still work

**Phase 3 Complete When**:
- ✅ Login page has registration link
- ✅ All TODO comments resolved
- ✅ All user stats displayed in Profile
- ✅ Type safety improved with proper interfaces
- ✅ Manual testing confirms UX improvements

**Phase 4 Complete When**:
- ✅ All 6+ test files created
- ✅ Test coverage > 80% for auth code
- ✅ All tests pass: `make frontend-test`
- ✅ No test failures or warnings
- ✅ Tests validate final refactored code

**Overall Project Complete When**:
- ✅ All phases 1-4 complete
- ✅ Code review passes
- ✅ Documentation updated
- ✅ Ready for merge to main branch

---

## Risk Mitigation

### Potential Issues & Solutions

**Risk 1**: Refactoring breaks existing functionality
- **Mitigation**: Manual testing after each refactoring step
- **Rollback**: Git commits after each logical change

**Risk 2**: Tests fail after refactoring
- **Mitigation**: This is why we refactor FIRST, then write tests
- **Benefit**: Tests validate the final, improved code

**Risk 3**: useApi hook doesn't work for all use cases
- **Mitigation**: Review all API call patterns before refactoring
- **Fallback**: Keep direct fetch as option for edge cases

**Risk 4**: Shared components don't fit all use cases
- **Mitigation**: Make components flexible with props
- **Fallback**: Allow style overrides via sx prop

---

## Effort Estimation

| Phase | Tasks | Estimated Hours | Priority |
|-------|-------|----------------|----------|
| Phase 1: Critical Fixes | 1 task | 1-2 hours | P0 |
| Phase 2: Refactoring | 3 major tasks | 4-6 hours | P1 |
| Phase 3: UX Improvements | 4 tasks | 2-3 hours | P2 |
| Phase 4: Testing | 7 test files | 6-8 hours | P0 |
| **Total** | **15 tasks** | **13-19 hours** | **~2-3 days** |

---

## Dependencies

### External Dependencies
- None - all work is frontend-only

### Internal Dependencies
- Phase 2 depends on Phase 1 completion
- Phase 3 can run parallel to Phase 2
- Phase 4 MUST wait for Phases 1-3 completion

### Team Dependencies
- Code review after Phase 2
- QA testing after Phase 4

---

## Rollout Plan

### Development Workflow
1. Create feature branch: `feat/auth-improvements`
2. Implement Phase 1 → commit
3. Implement Phase 2 → commit per task
4. Implement Phase 3 → commit per task
5. Implement Phase 4 → commit per test file group
6. Create PR with full test results
7. Code review
8. Merge to main

### Testing Checkpoints
- ✅ After Phase 1: Manual testing
- ✅ After Phase 2: Manual testing + smoke tests
- ✅ After Phase 3: Manual testing + UX review
- ✅ After Phase 4: Full automated test suite

---

## Appendix

### Files Modified Summary

**Modified Files** (11):
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/hooks/useImageProcessing.ts`
- `frontend/src/hooks/useVocabulary.ts`
- `frontend/src/components/auth/Login.tsx`
- `frontend/src/components/auth/Register.tsx`
- `frontend/src/components/auth/Profile.tsx`
- `frontend/src/hooks/useImageProcessing.test.ts`
- `frontend/src/hooks/useVocabulary.test.ts`
- `frontend/src/context/AuthContext.tsx` (type updates)
- `frontend/src/utils/api.ts` (minor improvements)
- `frontend/src/App.tsx` (if needed for registration link)

**New Files** (8-10):
- `frontend/src/components/auth/AuthButton.tsx`
- `frontend/src/components/auth/AuthButton.test.tsx`
- `frontend/src/components/auth/AuthTextField.tsx` (optional)
- `frontend/src/components/auth/Login.test.tsx`
- `frontend/src/components/auth/Register.test.tsx`
- `frontend/src/components/auth/Profile.test.tsx`
- `frontend/src/context/AuthContext.test.tsx`
- `frontend/src/hooks/useAuth.test.ts`
- `frontend/src/utils/api.test.ts`
- `frontend/src/types/auth.ts` (optional, for UpdateProfileData)

---

## Next Steps

1. ✅ Review this plan with team
2. ✅ Get approval for refactor-first approach
3. ✅ Create feature branch
4. ✅ Begin Phase 1 implementation
5. ✅ Follow step-by-step execution order

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Author**: Kilo Code (Architect Mode)
**Status**: Ready for Implementation
