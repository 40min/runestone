# Protected Endpoints Documentation

This document lists all API endpoints that require JWT authentication and validates that the frontend properly sends tokens.

## Protected Endpoints (Require JWT Token)

All endpoints below require `Authorization: Bearer <jwt_token>` header:

### Core Processing Endpoints
- `POST /api/ocr` - Extract text from images
- `POST /api/analyze` - Analyze text content
- `POST /api/resources` - Find learning resources

### Vocabulary Management Endpoints
- `POST /api/vocabulary` - Save multiple vocabulary items
- `POST /api/vocabulary/item` - Save single vocabulary item
- `GET /api/vocabulary` - Retrieve user's vocabulary
- `PUT /api/vocabulary/{item_id}` - Update vocabulary item
- `DELETE /api/vocabulary/{item_id}` - Delete vocabulary item
- `POST /api/vocabulary/improve` - AI-powered vocabulary improvement ✨ **FIXED**

## Public Endpoints (No Authentication Required)

### Health & Grammar
- `GET /api/health` - Service health check
- `GET /api/grammar/cheatsheets` - List grammar cheatsheets
- `GET /api/grammar/cheatsheets/{filepath}` - Get cheatsheet content

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/token` - User login (returns JWT)

## Frontend Authentication Implementation

### Authentication Flow
1. User logs in → gets JWT token
2. Frontend stores token in localStorage via AuthContext
3. All protected API calls automatically include `Authorization: Bearer ${token}` header
4. 401 responses trigger automatic logout

### Key Files
- `frontend/src/utils/api.ts` - Centralized API client with auth injection
- `frontend/src/context/AuthContext.tsx` - Authentication state management
- `frontend/src/hooks/useVocabulary.ts` - Vocabulary operations (uses auth API client)
- `frontend/src/hooks/useImageProcessing.ts` - Image processing (uses auth API client)
- `frontend/src/components/AddEditVocabularyModal.tsx` - Vocabulary improvement (uses auth API client)

## Issues Fixed

### 1. Vocabulary Improvement Endpoint
**Problem:** `POST /api/vocabulary/improve` endpoint wasn't sending auth token
**Root Cause:** `improveVocabularyItem` function made direct fetch call without authentication
**Fix:**
- Modified `improveVocabularyItem` to accept API client parameter
- Updated `AddEditVocabularyModal` to use authenticated API client
- All calls now properly include JWT token

### 2. OCR Processing Endpoint
**Problem:** `POST /api/ocr` endpoint authentication was incomplete
**Root Cause:** `recognizeImage` function in `useImageProcessing.ts` made unauthenticated fetch call
**Fix:**
- Added direct JWT token injection for FormData requests
- All image processing operations now properly authenticated

## Validation Checklist

✅ **Backend endpoints properly protected** - All user-specific endpoints require `get_current_user` dependency

✅ **Frontend hooks use authenticated API client** - All hooks use `useApi()` which injects JWT tokens

✅ **Vocabulary improvement fixed** - Modal component uses authenticated API calls

✅ **Image processing authenticated** - OCR calls include proper authorization headers

✅ **Error handling** - 401 responses trigger automatic logout and user session cleanup

## Testing Recommendations

1. **Authentication Required Tests:**
   - Verify 401 status for all protected endpoints without token
   - Verify 200 status for all protected endpoints with valid token
   - Test token expiration handling

2. **Frontend Integration Tests:**
   - Mock token storage and retrieval
   - Verify Authorization headers are sent with all protected requests
   - Test automatic logout on 401 responses

3. **User Flow Tests:**
   - Complete image processing workflow (OCR → Analyze → Save vocabulary)
   - Vocabulary management workflow (Create → Edit → Improve → Delete)
   - Session management (Login → Use → Logout)

## Environment Variables Required

- `JWT_SECRET_KEY` - Secret key for JWT token signing/verification
- `JWT_EXPIRATION_DAYS` - Token lifetime (default: 7 days)
- Frontend `API_BASE_URL` - Backend API endpoint base URL
