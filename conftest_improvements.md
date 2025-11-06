# Conftest Files Improvement Plan

## Overview

This document provides a prioritized list of improvements for the test conftest files based on the analysis of recent refactoring work. The improvements focus on eliminating duplication, improving consistency, and enhancing maintainability.

## Critical Improvements (Implement First)

### 1. Implement `client_with_overrides` Factory in `tests/api/conftest.py`

**Priority**: 🔴 CRITICAL
**Impact**: Eliminates 158 lines of duplication
**Complexity**: Medium
**Estimated Time**: 2-3 hours

**Problem**:
- [`client_with_mock_vocabulary_service`](tests/api/conftest.py:123-201) and [`client_with_mock_grammar_service`](tests/api/conftest.py:203-280) contain 79 lines of identical code each
- Only difference is which service dependency is overridden (line 191 vs 271)
- Violates DRY principle severely

**Solution**:
Add a factory fixture that accepts dependency overrides as parameters:

```python
@pytest.fixture(scope="function")
def client_with_overrides(mock_llm_client):
    """
    Factory fixture for creating test clients with customizable dependency overrides.

    This eliminates duplication by providing a single, flexible client creation
    function that can be customized for different test scenarios.

    Returns:
        function: Factory function that accepts override parameters and returns (client, mocks)

    Example:
        def test_example(client_with_overrides, mock_vocabulary_service):
            client, mocks = client_with_overrides(
                vocabulary_service=mock_vocabulary_service
            )
            response = client.post("/api/vocabulary/improve", json=data)
            assert response.status_code == 200
    """
    from sqlalchemy.pool import StaticPool
    from runestone.dependencies import get_vocabulary_service, get_grammar_service

    def _create_client(
        vocabulary_service=None,
        grammar_service=None,
        processor=None,
        llm_client=None,
        current_user=None,
        db_override=None
    ):
        # Database setup
        test_db_url = "sqlite:///:memory:"

        engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create test user if needed
        if current_user is None:
            import uuid
            unique_email = f"test-{uuid.uuid4()}@example.com"
            test_user = User(
                name="Test User",
                surname="Testsson",
                email=unique_email,
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
            )
            db = SessionLocal()
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            db.close()

        # Setup overrides
        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_llm_client():
            return llm_client or mock_llm_client

        def override_get_current_user():
            if current_user:
                return current_user
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.email == unique_email).first()
                return user
            finally:
                db.close()

        # Apply overrides
        overrides = {
            get_db: db_override or override_get_db,
            get_llm_client: override_get_llm_client,
            get_current_user: override_get_current_user,
        }

        if vocabulary_service:
            overrides[get_vocabulary_service] = lambda: vocabulary_service
        if grammar_service:
            overrides[get_grammar_service] = lambda: grammar_service
        if processor:
            overrides[get_runestone_processor] = lambda: processor

        for dep, override in overrides.items():
            app.dependency_overrides[dep] = override

        client = TestClient(app)

        # Return client and mocks for easy access
        mocks = {
            'vocabulary_service': vocabulary_service,
            'grammar_service': grammar_service,
            'processor': processor,
            'llm_client': llm_client or mock_llm_client,
            'current_user': current_user,
        }

        yield client, mocks

        # Cleanup
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    return _create_client
```

**Then simplify specialized fixtures**:

```python
@pytest.fixture(scope="function")
def client_with_mock_vocabulary_service(client_with_overrides, mock_vocabulary_service):
    """
    Create a test client with mocked vocabulary service.

    Returns:
        tuple: (TestClient, Mock) - The test client and mock vocabulary service
    """
    client, mocks = client_with_overrides(vocabulary_service=mock_vocabulary_service)
    return client, mock_vocabulary_service

@pytest.fixture(scope="function")
def client_with_mock_grammar_service(client_with_overrides, mock_grammar_service):
    """
    Create a test client with mocked grammar service.

    Returns:
        tuple: (TestClient, Mock) - The test client and mock grammar service
    """
    client, mocks = client_with_overrides(grammar_service=mock_grammar_service)
    return client, mock_grammar_service
```

**Files to Modify**:
- [`tests/api/conftest.py`](tests/api/conftest.py)

**Testing**:
```bash
pytest tests/api/test_vocabulary_improve_endpoint.py -v
pytest tests/api/test_grammar_endpoints.py -v
```

**Expected Outcome**:
- Reduce `tests/api/conftest.py` from 309 lines to ~170 lines (45% reduction)
- Single source of truth for client creation
- Easy to add new specialized fixtures

---

### 2. Create Database Engine Hierarchy in `tests/conftest.py`

**Priority**: 🔴 CRITICAL
**Impact**: Eliminates 5 separate engine creations, improves consistency
**Complexity**: Low
**Estimated Time**: 1-2 hours

**Problem**:
- Database engines are created independently in 5 different locations
- Inconsistent configuration (some use `StaticPool`, some don't)
- No shared infrastructure for database setup

**Solution**:
Add base database fixtures to create a clear hierarchy:

```python
@pytest.fixture(scope="function")
def db_engine():
    """
    Create a fresh test database engine for each test (complete isolation).

    Uses in-memory SQLite to ensure:
    - No data pollution between tests
    - Safe parallel test execution
    - Easy debugging (each test starts clean)

    Performance: In-memory databases are fast enough that per-test
    creation has minimal impact (~1-5ms overhead per test).

    Returns:
        Engine: SQLAlchemy engine instance
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session_factory(db_engine):
    """
    Create a session factory for the test database.

    Args:
        db_engine: Test database engine

    Returns:
        sessionmaker: Session factory bound to test engine
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

@pytest.fixture(scope="function")
def db_with_test_user(db_session_factory):
    """
    Create a database session with a pre-created test user.

    Each test gets a fresh database with a unique test user.
    No cleanup needed as the entire database is disposed after the test.

    Args:
        db_session_factory: Session factory from db_session_factory fixture

    Returns:
        tuple: (Session, User) - Database session and test user

    Example:
        def test_example(db_with_test_user):
            db, user = db_with_test_user
            # Use db and user in test
            assert user.email is not None
    """
    import uuid

    db = db_session_factory()
    unique_email = f"test-{uuid.uuid4()}@example.com"
    test_user = User(
        name="Test User",
        surname="Testsson",
        email=unique_email,
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjYQmP7XzL6",
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)

    try:
        yield db, test_user
    finally:
        db.close()
```

**Then refactor existing `db_session` to use the engine**:

```python
@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Create a fresh database session for each test.

    Each test gets a completely isolated database session with no
    data from previous tests. This ensures test independence and
    makes debugging easier.

    Args:
        db_engine: Test database engine

    Returns:
        Session: SQLAlchemy session instance
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
```

**Files to Modify**:
- [`tests/conftest.py`](tests/conftest.py)

**Testing**:
```bash
make backend-test
```

**Expected Outcome**:
- Clear fixture hierarchy: `db_engine` → `db_session_factory` → `db_session` / `db_with_test_user`
- Consistent database configuration across all tests
- Foundation for refactoring other fixtures

---

### 3. Fix Database URL Inconsistency in `client` Fixture

**Priority**: 🟡 HIGH
**Impact**: Improves consistency, aligns with isolation strategy
**Complexity**: Low
**Estimated Time**: 30 minutes

**Problem**:
- [`tests/api/conftest.py:41`](tests/api/conftest.py:41) uses shared cache pattern: `f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"`
- This contradicts the per-test isolation strategy
- Other fixtures use simple `"sqlite:///:memory:"`

**Solution**:
```python
# Change line 41 from:
test_db_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

# To:
test_db_url = "sqlite:///:memory:"

# And update line 44 to add StaticPool:
engine = create_engine(
    test_db_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # Add this
)
```

**Files to Modify**:
- [`tests/api/conftest.py:41,44`](tests/api/conftest.py:41)

**Testing**:
```bash
pytest tests/api/ -v
```

**Expected Outcome**:
- Consistent database URL pattern across all fixtures
- Aligns with per-test isolation strategy
- No functional changes (already per-test scoped)

---

## High Priority Improvements

### 4. Refactor `client` Fixture to Use Shared Components

**Priority**: 🟡 HIGH
**Impact**: Reduces 33 lines, improves reusability
**Complexity**: Medium
**Estimated Time**: 1-2 hours

**Problem**:
- [`tests/api/conftest.py:33-90`](tests/api/conftest.py:33-90) duplicates database and user setup
- Could reuse `db_with_test_user` fixture

**Solution**:

```python
@pytest.fixture(scope="function")
def client(db_with_test_user, mock_llm_client) -> Generator[TestClient, None, None]:
    """
    Create a test client with in-memory database and mocked LLM client for testing.

    This fixture provides a fully configured test client with:
    - Fresh in-memory database per test
    - Pre-created test user
    - Mocked LLM client

    Args:
        db_with_test_user: Database session with test user
        mock_llm_client: Mocked LLM client

    Returns:
        TestClient: Configured FastAPI test client
    """
    db, test_user = db_with_test_user

    # Override dependencies
    def override_get_db():
        yield db

    def override_get_llm_client():
        return mock_llm_client

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_client] = override_get_llm_client
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
```

**Files to Modify**:
- [`tests/api/conftest.py:33-90`](tests/api/conftest.py:33-90)

**Dependencies**:
- Requires `db_with_test_user` fixture from Improvement #2

**Testing**:
```bash
pytest tests/api/ -v
```

**Expected Outcome**:
- Reduce `client` fixture from 58 lines to 25 lines (57% reduction)
- Reuses shared database infrastructure
- Maintains all existing functionality

---

### 5. Remove Duplicate `temp_cheatsheets_dir` from test_grammar_endpoints.py

**Priority**: 🟡 HIGH
**Impact**: Eliminates 17 lines of duplication
**Complexity**: Low
**Estimated Time**: 15 minutes

**Problem**:
- [`tests/api/test_grammar_endpoints.py:19-35`](tests/api/test_grammar_endpoints.py:19-35) defines local `temp_cheatsheets_dir`
- Identical fixture exists in [`tests/conftest.py:232-259`](tests/conftest.py:232-259)

**Solution**:
1. Remove lines 19-35 from `test_grammar_endpoints.py`
2. Tests will automatically use the shared fixture from conftest

**Files to Modify**:
- [`tests/api/test_grammar_endpoints.py`](tests/api/test_grammar_endpoints.py)

**Testing**:
```bash
pytest tests/api/test_grammar_endpoints.py -v
```

**Expected Outcome**:
- Remove 17 lines of duplicate code
- Consistent fixture usage across all grammar tests

---

## Medium Priority Improvements

### 6. Consolidate `vocab_factory` Fixtures

**Priority**: 🟠 MEDIUM
**Impact**: Eliminates 27 lines, single source of truth
**Complexity**: Medium
**Estimated Time**: 1 hour

**Problem**:
- [`tests/db/test_db_repository.py:15-41`](tests/db/test_db_repository.py:15-41) defines local `vocab_factory`
- Nearly identical to [`tests/conftest.py:156-183`](tests/conftest.py:156-183) `vocabulary_model_factory`

**Solution**:
1. Remove `vocab_factory` from `test_db_repository.py`
2. Update all usages to use `vocabulary_model_factory`
3. Update dependent fixtures:
   - `basic_vocab_items` (line 45)
   - `wildcard_test_items` (line 73)
   - `mixed_wildcard_items` (line 100)
   - `special_char_items` (line 122)
   - `edge_case_items` (line 149)

**Files to Modify**:
- [`tests/db/test_db_repository.py`](tests/db/test_db_repository.py)

**Testing**:
```bash
pytest tests/db/test_db_repository.py -v
```

**Expected Outcome**:
- Remove 27 lines of duplicate code
- All tests use shared factory fixture
- Consistent vocabulary model creation

---

### 7. Refactor `test_db` Fixture in test_rune_recall_service.py

**Priority**: 🟠 MEDIUM
**Impact**: Eliminates 30 lines, uses shared infrastructure
**Complexity**: Medium
**Estimated Time**: 1-2 hours

**Problem**:
- [`tests/services/test_rune_recall_service.py:26-77`](tests/services/test_rune_recall_service.py:26-77) creates its own database
- Duplicates engine creation and session management
- Could use shared `db_session` and `vocabulary_model_factory`

**Solution**:

```python
@pytest.fixture
def test_db(db_session, vocabulary_model_factory):
    """Create a test database with sample vocabulary data."""
    # Add sample vocabulary for user 1
    words = [
        vocabulary_model_factory(
            user_id=1,
            word_phrase="hello",
            translation="hej",
            example_phrase="Hello, how are you?",
            in_learn=True,
            last_learned=None,
        ),
        vocabulary_model_factory(
            user_id=1,
            word_phrase="goodbye",
            translation="hej då",
            example_phrase="Goodbye, see you later!",
            in_learn=True,
            last_learned=None,
        ),
        vocabulary_model_factory(
            user_id=1,
            word_phrase="thank you",
            translation="tack",
            example_phrase="Thank you for your help.",
            in_learn=True,
            last_learned=None,
        ),
        vocabulary_model_factory(
            user_id=2,
            word_phrase="water",
            translation="vatten",
            example_phrase="I need water.",
            in_learn=True,
            last_learned=None,
        ),
    ]
    db_session.add_all(words)
    db_session.commit()

    yield db_session
```

**Files to Modify**:
- [`tests/services/test_rune_recall_service.py:26-77`](tests/services/test_rune_recall_service.py:26-77)

**Testing**:
```bash
pytest tests/services/test_rune_recall_service.py -v
```

**Expected Outcome**:
- Reduce fixture from 52 lines to 22 lines (58% reduction)
- Uses shared database infrastructure
- Uses shared factory for test data

---

### 8. Audit and Remove Unused Fixtures

**Priority**: 🟠 MEDIUM
**Impact**: Reduces maintenance burden, clarifies codebase
**Complexity**: Low
**Estimated Time**: 30 minutes

**Problem**:
- Some fixtures may be defined but unused
- Unclear which fixtures are actively used

**Action Items**:

1. **Verify `client_with_custom_user` usage**:
   ```bash
   grep -r "client_with_custom_user" tests/
   ```
   - If unused, remove it or document it as "for future use"

2. **Verify `client_with_mock_processor` usage**:
   ```bash
   grep -r "client_with_mock_processor" tests/
   ```
   - Ensure it's being used, otherwise remove

3. **Check all mock fixtures**:
   ```bash
   grep -r "mock_vocabulary_service" tests/
   grep -r "mock_grammar_service" tests/
   grep -r "mock_processor" tests/
   ```

**Files to Review**:
- [`tests/api/conftest.py`](tests/api/conftest.py)
- [`tests/conftest.py`](tests/conftest.py)

**Expected Outcome**:
- Clear understanding of fixture usage
- Remove dead code
- Document fixtures intended for future use

---

## Low Priority Improvements

### 9. Enhance Fixture Documentation

**Priority**: 🟢 LOW
**Impact**: Improves maintainability and onboarding
**Complexity**: Low
**Estimated Time**: 2-3 hours

**Problem**:
- Some fixtures have minimal docstrings
- No usage examples in docstrings
- Dependencies not clearly documented

**Solution**:
Add comprehensive docstrings to all fixtures following this template:

```python
@pytest.fixture
def example_fixture(dependency1, dependency2):
    """
    Brief description of what the fixture provides.

    Longer description explaining when to use this fixture,
    what it sets up, and any important considerations.

    Args:
        dependency1: Description of first dependency
        dependency2: Description of second dependency

    Returns:
        type: Description of return value

    Example:
        def test_example(example_fixture):
            result = example_fixture
            assert result is not None

    Dependencies:
        - dependency1 (from conftest)
        - dependency2 (from conftest)

    Notes:
        - Any important notes or warnings
        - Performance considerations
        - Common pitfalls
    """
    # Implementation
    pass
```

**Files to Modify**:
- [`tests/conftest.py`](tests/conftest.py)
- [`tests/api/conftest.py`](tests/api/conftest.py)

**Expected Outcome**:
- Self-documenting fixtures
- Easier onboarding for new developers
- Clear usage patterns

---

### 10. Create TESTING.md Guide

**Priority**: 🟢 LOW
**Impact**: Improves developer experience
**Complexity**: Medium
**Estimated Time**: 3-4 hours

**Problem**:
- No centralized testing documentation
- Fixture usage patterns not documented
- Database isolation strategy not explained

**Solution**:
Create comprehensive testing guide with sections:

1. **Database Testing Strategy**
   - Per-test isolation explanation
   - Performance considerations
   - When to use which database fixture

2. **Fixture Overview**
   - Database fixtures
   - Mock fixtures
   - Client fixtures
   - Factory fixtures
   - Temporary file fixtures

3. **Usage Examples**
   - Testing API endpoints
   - Testing services
   - Testing repositories
   - Custom dependency overrides

4. **Best Practices**
   - Fixture composition
   - Test data creation
   - Mock configuration
   - Common patterns

5. **Troubleshooting**
   - Common issues
   - Debugging tips
   - Performance optimization

**Files to Create**:
- `TESTING.md` in project root

**Expected Outcome**:
- Comprehensive testing guide
- Faster onboarding
- Consistent testing patterns

---

## Specific Code Issues Found

### Issue 1: Duplicate UUID Import in `client` Fixture

**Location**: [`tests/api/conftest.py:38,49`](tests/api/conftest.py:38)

**Problem**:
```python
# Line 38
import uuid
db_name = f"memdb{uuid.uuid4().hex}"

# Line 49 - duplicate import
import uuid
unique_email = f"test-{uuid.uuid4()}@example.com"
```

**Solution**: Remove duplicate import on line 49

**Impact**: Minor code quality improvement

---

### Issue 2: Inconsistent Mock Creation in Specialized Fixtures

**Location**: [`tests/api/conftest.py:176,256`](tests/api/conftest.py:176)

**Problem**:
```python
# Lines 175-177 in client_with_mock_vocabulary_service
def override_get_llm_client():
    from unittest.mock import Mock
    return Mock()

# Lines 255-257 in client_with_mock_grammar_service
def override_get_llm_client():
    from unittest.mock import Mock
    return Mock()
```

Both create a new Mock instead of using the `mock_llm_client` parameter.

**Solution**: Use the passed `mock_llm_client` parameter (will be fixed by implementing `client_with_overrides`)

**Impact**: Consistency improvement

---

### Issue 3: Missing `StaticPool` in Some Engine Creations

**Location**: [`tests/services/test_rune_recall_service.py:29`](tests/services/test_rune_recall_service.py:29)

**Problem**:
```python
engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
# Missing poolclass=StaticPool
```

**Solution**: Add `poolclass=StaticPool` or use shared `db_engine` fixture

**Impact**: Consistency and potential stability improvement

---

## Implementation Roadmap

### Week 1: Critical Improvements

**Day 1-2**: Database Engine Hierarchy
- [ ] Implement `db_engine` fixture
- [ ] Implement `db_session_factory` fixture
- [ ] Implement `db_with_test_user` fixture
- [ ] Refactor `db_session` to use `db_engine`
- [ ] Test: `make backend-test`

**Day 3-4**: Client Factory
- [ ] Implement `client_with_overrides` factory
- [ ] Refactor `client_with_mock_vocabulary_service`
- [ ] Refactor `client_with_mock_grammar_service`
- [ ] Test: `pytest tests/api/ -v`

**Day 5**: Quick Wins
- [ ] Fix database URL in `client` fixture
- [ ] Remove duplicate `temp_cheatsheets_dir`
- [ ] Fix duplicate UUID import
- [ ] Test: `make backend-test`

### Week 2: Medium Priority

**Day 1-2**: Local Fixture Cleanup
- [ ] Consolidate `vocab_factory` fixtures
- [ ] Refactor `test_db` fixture
- [ ] Test: `pytest tests/services/ tests/db/ -v`

**Day 3**: Fixture Audit
- [ ] Audit all fixtures for usage
- [ ] Remove or document unused fixtures
- [ ] Test: `make backend-test`

**Day 4-5**: Documentation
- [ ] Enhance all fixture docstrings
- [ ] Create TESTING.md guide
- [ ] Document database isolation strategy

## Success Metrics

### Quantitative Goals

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Lines of test code | ~3,500 | ~3,200 | -300 lines (9%) |
| Fixture duplication | 250 lines | 0 lines | -250 lines |
| `create_engine` calls | 5 | 1 | -4 calls |
| Local fixtures duplicating shared | 3 | 0 | -3 fixtures |
| Fixture reuse percentage | ~60% | ~90% | +30% |

### Qualitative Goals

- ✅ Single source of truth for database setup
- ✅ Consistent patterns across all test files
- ✅ Clear fixture hierarchy and dependencies
- ✅ Comprehensive documentation
- ✅ Easy to add new test fixtures
- ✅ Reduced maintenance burden

## Testing Strategy

### After Each Change

1. **Run affected tests**:
   ```bash
   pytest tests/path/to/affected/ -v
   ```

2. **Run full test suite**:
   ```bash
   make backend-test
   ```

3. **Check for warnings**:
   ```bash
   pytest tests/ -v --tb=short
   ```

4. **Verify no regressions**:
   - All tests should pass
   - No new warnings
   - Similar or better performance

### Performance Benchmarking

**Before changes**:
```bash
time make backend-test
# Record baseline time
```

**After each phase**:
```bash
time make backend-test
# Compare to baseline
# Expected: <1 second difference
```

## Risk Mitigation

### Low Risk Changes ⭐
- Adding new fixtures (db_engine, db_session_factory, db_with_test_user)
- Enhancing docstrings
- Creating documentation
- **Mitigation**: Additive changes, no breaking changes

### Medium Risk Changes ⭐⭐
- Refactoring existing fixtures (client, db_session)
- Removing local fixtures
- Implementing client_with_overrides
- **Mitigation**:
  - Test thoroughly after each change
  - Keep old code commented temporarily
  - Can rollback easily

### Rollback Strategy

1. **Git-based rollback**:
   - Each improvement should be a separate commit
   - Tag stable states
   - Easy to revert individual changes

2. **Incremental approach**:
   - Implement one improvement at a time
   - Verify before proceeding
   - Don't remove old code until new code is proven

## Conclusion

The test refactoring has made **significant progress** (60-70% complete), but **critical inefficiencies remain** in the conftest files:

### Top 3 Critical Issues:
1. **158 lines of duplication** in specialized client fixtures (needs `client_with_overrides`)
2. **5 separate engine creations** (needs `db_engine` hierarchy)
3. **Inconsistent database patterns** (needs standardization)

### Recommended Next Steps:
1. **Immediate**: Implement `client_with_overrides` factory (highest impact)
2. **This week**: Add `db_engine` hierarchy (foundation for other improvements)
3. **Next week**: Clean up local fixtures and add documentation

### Expected Benefits:
- **~300 lines** of code reduction
- **90% fixture reuse** (up from 60%)
- **Single source of truth** for all database and client setup
- **Improved maintainability** and developer experience

The improvements are **low-to-medium risk** and can be implemented incrementally with proper testing at each step.
