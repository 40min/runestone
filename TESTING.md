# Testing Guide

This guide documents the testing strategy and infrastructure for the Runestone project, including database isolation, fixtures, and best practices for writing tests.

## Table of Contents

- [Testing Architecture](#testing-architecture)
- [Testing Strategy](#testing-strategy)
- [Database Isolation Strategy](#database-isolation-strategy)
- [Key Fixtures](#key-fixtures)
- [Writing New Tests](#writing-new-tests)
- [Running Tests](#running-tests)

## Testing Architecture

The test suite is organized into two main layers:

1. **API Tests** (`tests/api/`): Test HTTP endpoints using FastAPI's `TestClient`
2. **Service/Unit Tests** (`tests/services/`, `tests/db/`): Test business logic and data access layers

All test configuration and shared fixtures are centralized in:
- `tests/conftest.py`: Root configuration and shared fixtures
- `tests/api/conftest.py`: API-specific fixtures
- `tests/db/conftest.py`: Database-specific fixtures (if needed)

## Testing Strategy

### Testing Philosophy

The Runestone project employs a **hybrid testing approach** that combines the best of both patching and fixture-based testing. This strategy was chosen after architectural evaluation to optimize for test speed, maintainability, and reliability.

#### Hybrid Approach Overview
- **Patches for Unit Tests**: Service and unit tests use `@patch` decorators to mock external dependencies
- **Fixtures for Integration Tests**: API and integration tests use specialized fixtures to mock entire services
- **Factory Pattern for Complex Scenarios**: The `client_with_overrides` fixture provides flexible mocking for complex test scenarios

#### Why This Approach is Optimal
- **Performance**: Patches are lightweight and fast for unit tests
- **Isolation**: Fixtures provide complete service isolation for integration tests
- **Flexibility**: Factory fixtures allow customization without boilerplate
- **Maintainability**: Clear separation of concerns between test types
- **Reliability**: Consistent mocking patterns reduce test flakiness

#### Benefits of Each Approach
- **Patches**: Minimal setup, fast execution, focused on specific functions
- **Fixtures**: Realistic integration testing, automatic cleanup, shared setup
- **Factory Fixtures**: Maximum flexibility, complex scenarios, reusable configurations

### When to Use Each Approach

#### Service/Unit Tests → Use `@patch` decorators
Use patches when testing individual functions or methods that have external dependencies:
- Database operations
- API calls to external services
- File system operations
- Complex business logic with multiple dependencies

**Memory item services:** `MemoryItemService` tests intentionally use the real repository + DB session to validate status rules, permissions, and transactional behavior. Prefer `db_with_test_user` and avoid mocking the repository layer for these cases.

#### API/Integration Tests → Use specialized fixtures
Use fixtures when testing complete workflows or API endpoints:
- Full request/response cycles
- Authentication and authorization
- Database transactions
- Service integrations

#### Complex Scenarios → Use `client_with_overrides`
Use the factory fixture for advanced testing needs:
- Multiple service mocks required
- Custom user contexts
- Specific database states
- Non-standard configurations

### Available Fixtures

#### Public API Client Fixtures
Located in `tests/api/conftest.py`:

- **`client`**: Standard test client with fresh database and authenticated user
- **`client_with_mock_processor`**: Client with mocked RunestoneProcessor
- **`client_with_mock_vocabulary_service`**: Client with mocked vocabulary service
- **`client_with_mock_grammar_service`**: Client with mocked grammar service
- **`client_with_overrides`**: Factory fixture for customizable client configurations

#### `client_with_overrides` Parameters
The factory fixture accepts these override parameters:
- `vocabulary_service`: Custom vocabulary service instance
- `grammar_service`: Custom grammar service instance
- `processor`: Custom RunestoneProcessor instance
- `llm_client`: Custom LLM client
- `current_user`: Custom user object for authentication
- `db_override`: Custom database session

Returns: `(client, mocks_dict)` where `mocks_dict` contains all created mock objects.

### Decision Matrix

| Test Type | Scenario | Recommended Approach | Example |
|-----------|----------|---------------------|---------|
| Service/Unit | Single method with DB dependency | `@patch` decorator | `test_user_service.py` |
| Service/Unit | Complex business logic | `@patch` decorators | `test_vocabulary_service.py` |
| API/Integration | Basic endpoint testing | `client` fixture | Simple CRUD operations |
| API/Integration | Mocked service response | `client_with_mock_*` fixtures | Grammar cheatsheets endpoint |
| API/Integration | Multiple service mocks | `client_with_overrides` | Complex vocabulary improvement |
| Complex | Custom user authentication | `client_with_overrides` | Admin-only endpoints |
| Complex | Specific database state | `client_with_overrides` | Data migration testing |
| Complex | Non-standard service config | `client_with_overrides` | Error handling scenarios |

### Code Examples

#### Service Test Using Patches
```python
from unittest.mock import patch
import pytest

def test_improve_vocabulary_success(vocabulary_service, db_with_test_user):
    """Test successful vocabulary improvement with mocked processor."""
    db, test_user = db_with_test_user

    # Create test vocabulary item
    vocab_item = Vocabulary(
        user_id=test_user.id,
        word_phrase="hello",
        translation="hej"
    )
    db.add(vocab_item)
    db.commit()

    # Mock the processor's improve_item method
    with patch.object(vocabulary_service.processor, 'improve_item') as mock_improve:
        mock_improve.return_value = {
            "translation": "improved translation",
            "example_phrase": "improved example"
        }

        # Call the service method
        result = vocabulary_service.improve_item(test_user.id, "hello")

        # Verify the result
        assert result["translation"] == "improved translation"
        assert result["example_phrase"] == "improved example"
        mock_improve.assert_called_once_with("hello")
```

#### API Test Using Fixtures
```python
def test_get_grammar_cheatsheets(client_with_mock_grammar_service):
    """Test grammar cheatsheets endpoint with mocked service."""
    client, mock_service = client_with_mock_grammar_service

    # Configure the mock response
    mock_service.list_cheatsheets.return_value = [
        {"title": "Pronouns", "content": "Content here"},
        {"title": "Verbs", "content": "Verb content"}
    ]

    # Make the API request
    response = client.get("/api/grammar/cheatsheets")

    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Pronouns"

    # Verify the service was called correctly
    mock_service.list_cheatsheets.assert_called_once()
```

#### Complex Scenario Using `client_with_overrides`
```python
def test_vocabulary_improvement_with_custom_services(client_with_overrides):
    """Test vocabulary improvement with multiple custom service mocks."""
    # Create custom mock services
    mock_vocab_service = Mock()
    mock_vocab_service.improve_item.return_value = {
        "translation": "custom translation",
        "example_phrase": "custom example"
    }

    mock_grammar_service = Mock()
    mock_grammar_service.validate_grammar.return_value = True

    # Create client with custom overrides
    client, mocks = client_with_overrides(
        vocabulary_service=mock_vocab_service,
        grammar_service=mock_grammar_service
    )

    # Make request that uses both services
    response = client.post("/api/vocabulary/improve", json={
        "word_phrase": "test",
        "translation": "test translation"
    })

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["translation"] == "custom translation"

    # Verify both services were used
    mock_vocab_service.improve_item.assert_called_once()
    mock_grammar_service.validate_grammar.assert_called_once()
```

## Database Isolation Strategy

The test suite uses **complete database isolation** to ensure tests don't interfere with each other:

### Isolation Guarantees

- **Per-test database**: Each test gets a fresh in-memory SQLite database
- **Unique test user**: Each test gets a unique user with a UUID-based email
- **Automatic cleanup**: Databases are dropped and disposed after each test
- **No shared state**: No data persists between tests

### Database Configuration

```python
# All tests use this pattern
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
```

**Why in-memory SQLite?**
- Fast: No disk I/O overhead (~1-5ms per test)
- Safe: Complete isolation between tests
- Simple: No external dependencies (no PostgreSQL/MySQL needed)
- Parallel-safe: Each test has its own memory space

## Key Fixtures

### Database Fixtures

Located in `tests/conftest.py`:

#### `db_engine`
Creates a fresh database engine for each test. This is the foundation of our isolation strategy.

```python
@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine("sqlite:///:memory:", ...)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
```

#### `db_session`
Provides a database session with automatic rollback after the test.

```python
@pytest.fixture(scope="function")
def db_session(db_engine):
    SessionLocal = sessionmaker(..., bind=db_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
```

#### `db_with_test_user`
Provides both a database session and a pre-created test user.

```python
@pytest.fixture(scope="function")
def db_with_test_user(db_session_factory):
    db = db_session_factory()
    test_user = User(..., email=f"test-{uuid.uuid4()}@example.com")
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    yield db, test_user
    db.close()
```

**Use when**: You need both a database and a user object (most common case)

### API Client Fixtures

Located in `tests/api/conftest.py`:

#### `client`
The standard test client for API tests. Provides:
- Fresh database with test user
- Mocked LLM client
- Authenticated user context

```python
def test_vocabulary_endpoint(client):
    response = client.post("/api/vocabulary", json={"items": [...]})
    assert response.status_code == 200
```

#### `client_with_overrides`
**Factory fixture** for creating customizable test clients. Use this for advanced scenarios.

```python
def test_with_custom_mocks(client_with_overrides, mock_vocabulary_service):
    # Create client with custom vocabulary service mock
    client, mocks = client_with_overrides(
        vocabulary_service=mock_vocabulary_service
    )
    response = client.post("/api/vocabulary/improve", json=data)
    assert response.status_code == 200
```

**Returns**: A generator that yields `(client, mocks_dict)`

Available overrides:
- `vocabulary_service`: Mock vocabulary service
- `grammar_service`: Mock grammar service
- `processor`: Mock RunestoneProcessor
- `llm_client`: Custom LLM client
- `current_user`: Custom user object
- `db_override`: Custom database override

#### `client_with_mock_vocabulary_service`
Convenience fixture for tests that need a mocked vocabulary service.

```python
def test_improve_endpoint(client_with_mock_vocabulary_service):
    client, mock_service = client_with_mock_vocabulary_service
    mock_service.improve_item.return_value = custom_response
    response = client.post("/api/vocabulary/improve", json=data)
    assert response.status_code == 200
```

#### `client_with_mock_grammar_service`
Convenience fixture for tests that need a mocked grammar service.

```python
def test_grammar_endpoint(client_with_mock_grammar_service):
    client, mock_service = client_with_mock_grammar_service
    mock_service.list_cheatsheets.return_value = [...]
    response = client.get("/api/grammar/cheatsheets")
    assert response.status_code == 200
```

#### `client_with_mock_processor`
Convenience fixture for tests that need a mocked RunestoneProcessor.

```python
def test_resource_endpoint(client_with_mock_processor):
    client, mock_processor = client_with_mock_processor
    mock_processor.run_resource_search.return_value = "custom response"
    response = client.post("/api/resources", json=data)
    assert response.status_code == 200
```

### Factory Fixtures

Located in `tests/conftest.py`:

#### `vocabulary_model_factory`
Factory for creating `Vocabulary` model instances with sensible defaults.

```python
def test_something(vocabulary_model_factory, db_session):
    # Create a vocabulary item
    word = vocabulary_model_factory(
        user_id=1,
        word_phrase="hello",
        translation="hej",
        example_phrase="Hello there!"
    )
    db_session.add(word)
    db_session.commit()
    # ... test logic
```

**Default values** (override as needed):
- `user_id=1`
- `word_phrase=""` (empty string)
- `translation=""` (empty string)
- `example_phrase=None`
- `in_learn=True`
- `last_learned=None`
- `learned_times=0`

#### `vocabulary_item_factory`
Factory for creating `VocabularyItemCreate` schema objects (for API requests).

```python
def test_save_vocabulary(client, vocabulary_item_factory):
    items = [
        vocabulary_item_factory("hello", "hej", "Hello there!"),
        vocabulary_item_factory("goodbye", "hej då", "Goodbye!"),
    ]
    response = client.post("/api/vocabulary", json={"items": items})
    assert response.status_code == 200
```

#### `mock_user_factory`
Factory for creating mock user objects for advanced testing.

```python
def test_custom_user(client, mock_user_factory):
    custom_user = mock_user_factory(id=42, email="test@example.com")
    # ... use custom_user in test
```

## Writing New Tests

### For API Tests

1. **Use the `client` fixture** for most cases
2. **Use `client_with_overrides`** when you need custom mocks
3. **Use specialized fixtures** (`client_with_mock_*`) for common scenarios

Example: Simple API test
```python
def test_save_vocabulary_success(client):
    """Test successful vocabulary saving."""
    payload = {
        "items": [
            {
                "word_phrase": "ett äpple",
                "translation": "an apple",
                "example_phrase": "Jag äter ett äpple varje dag.",
            }
        ]
    }

    response = client.post("/api/vocabulary", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Vocabulary saved successfully"
```

Example: API test with custom mock
```python
def test_improve_vocabulary(client_with_overrides, mock_vocabulary_service):
    """Test vocabulary improvement with mocked service."""
    client, mocks = client_with_overrides(
        vocabulary_service=mock_vocabulary_service
    )

    # Configure the mock
    mock_vocabulary_service.improve_item.return_value = {
        "translation": "improved translation",
        "example_phrase": "improved example"
    }

    # Make request
    response = client.post("/api/vocabulary/improve", json={
        "word_phrase": "hello",
        "translation": "hej"
    })

    assert response.status_code == 200
    # ... verify response
```

### For Service/Unit Tests

1. **Use `db_session`** for database access
2. **Use `vocabulary_model_factory`** to create test data
3. **Use `vocabulary_repository`** for repository layer tests

### For Agent Tool Tests

Agent tools use LangChain's `@tool` decorator and require specific testing approaches depending on whether they use `ToolRuntime` for dependency injection.

#### Tools without ToolRuntime (e.g., news tools)

For tools that don't use `ToolRuntime`, you can use `.ainvoke()` directly:

```python
@pytest.mark.anyio
async def test_search_news_with_dates_formats_results(monkeypatch):
    # Mock external dependencies
    monkeypatch.setattr(agent_news, "DDGS", FakeDDGSWithResults)

    # Use .ainvoke() with a dictionary of arguments
    output = await agent_news.search_news_with_dates.ainvoke({
        "query": "ekonomi",
        "k": 2,
        "timelimit": "w"
    })
    assert output["tool"] == "search_news_with_dates"
```

#### Tools with ToolRuntime (e.g., memory tools)

For tools that use `ToolRuntime` for dependency injection, you need to use `.coroutine()` with a manually constructed runtime object:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.anyio
async def test_memory_tool_with_runtime():
    # Create mock service with AsyncMock for async methods
    memory_item_service = MagicMock()
    memory_item_service.list_memory_items = AsyncMock(return_value=[])

    # Construct runtime with context
    user = SimpleNamespace(id=123)
    runtime = SimpleNamespace(
        context=SimpleNamespace(
            user=user,
            memory_item_service=memory_item_service
        )
    )

    # Use .coroutine() and pass runtime directly
    output = await start_student_info.coroutine(runtime)
    assert output == "No memory items found."
```

**Why different approaches?**
- Tools without `ToolRuntime`: Parameters can be serialized to JSON, so `.ainvoke()` works directly
- Tools with `ToolRuntime`: The runtime contains complex objects (like database models) that can't be serialized to JSON, so we use `.coroutine()` with a manually constructed runtime

Example: Service test
```python
def test_select_daily_portion(rune_recall_service, test_vocabulary):
    """Test daily portion selection logic."""
    # Test data is already set up by test_vocabulary fixture

    # Call the method under test
    words = rune_recall_service._select_daily_portion(user_id=1)

    # Verify results
    assert len(words) == 3  # All 3 words for user 1
    word_phrases = [w["word_phrase"] for w in words]
    assert "hello" in word_phrases
    assert "goodbye" in word_phrases
    assert "thank you" in word_phrases
```

Example: Repository test
```python
def test_get_vocabulary_by_user(vocabulary_repository, vocabulary_model_factory, db_session):
    # Create test data
    words = [
        vocabulary_model_factory(user_id=1, word_phrase="hello"),
        vocabulary_model_factory(user_id=2, word_phrase="world"),
        vocabulary_model_factory(user_id=1, word_phrase="goodbye"),
    ]
    db_session.add_all(words)
    db_session.commit()

    # Test repository method
    user1_words = vocabulary_repository.get_vocabulary_by_user(1)

    # Verify results
    assert len(user1_words) == 2
    assert all(w.user_id == 1 for w in user1_words)
```

### Creating Test Data

**For simple cases**: Use the appropriate factory fixture
```python
word = vocabulary_model_factory(
    user_id=1,
    word_phrase="hello",
    translation="hej",
    example_phrase="Hello there!"
)
db_session.add(word)
db_session.commit()
```

**For complex scenarios**: Create a custom fixture in your test file
```python
@pytest.fixture
def custom_test_data(db_session, vocabulary_model_factory):
    """Create custom test data for specific tests."""
    words = [
        vocabulary_model_factory(user_id=1, word_phrase="word1", ...),
        vocabulary_model_factory(user_id=1, word_phrase="word2", ...),
    ]
    db_session.add_all(words)
    db_session.commit()
    return {"words": words}

def test_something(custom_test_data):
    # Use custom_test_data["words"]
    pass
```

## Running Tests

### Run All Tests
```bash
make backend-test
```

### Run Specific Test File
```bash
pytest tests/api/test_endpoints.py -v
```

### Run Specific Test
```bash
pytest tests/api/test_endpoints.py::TestVocabularyEndpoints::test_save_vocabulary_success -v
```

### Run with Coverage
```bash
pytest --cov=runestone tests/ -v
```

### Run in Parallel
```bash
pytest -n auto tests/
```

### Run API Tests Only
```bash
pytest tests/api/ -v
```

### Run Service Tests Only
```bash
pytest tests/services/ -v
```

### Run with Output on Failure
```bash
pytest --tb=short tests/
```

## Best Practices

### DO ✅

- Use the `client` fixture for API tests
- Use the `db_session` fixture for service tests
- Use factory fixtures to create test data
- Keep tests isolated and independent
- Use descriptive test names that explain what's being tested
- One assertion per test (or few related assertions)
- Clean up after yourself (fixtures handle this automatically)

### DON'T ❌

- **Don't create databases manually** - use `db_engine` or `db_session`
- **Don't share data between tests** - each test should be self-contained
- **Don't hardcode user IDs** - the test user is created automatically
- **Don't use real database URLs** - tests use in-memory SQLite
- **Don't mock database models directly** - use the repository layer
- **Don't create fixtures in test files** - use the shared fixtures in `conftest.py`

## Troubleshooting

### "database is locked" errors
This shouldn't happen with our in-memory SQLite setup, but if it does:
- Ensure tests are using `scope="function"` for fixtures
- Check that `db.rollback()` and `db.close()` are called in fixtures
- Run tests with `-x` to stop on first failure

### Tests failing on CI but passing locally
- Check that all tests use the `.env.test` file (set by conftest)
- Ensure `ENV_FILE` environment variable is set before imports
- Verify all database operations are wrapped in transactions

### "no such table" errors
- Ensure `Base.metadata.create_all()` is called before tests
- Check that your model imports are correct
- Verify the model is registered with `Base`

## Architecture Decisions

### Why In-Memory SQLite?
- **Speed**: 10-100x faster than file-based databases
- **Isolation**: Complete separation between tests
- **Reliability**: No risk of test pollution
- **Simplicity**: No external dependencies

### Why Per-Test Database?
- **Safety**: Tests can't affect each other
- **Debugging**: Each test starts fresh
- **Reliability**: No flakiness from shared state

### Why Factory Fixtures?
- **Consistency**: Same defaults across all tests
- **Flexibility**: Easy to override defaults
- **Readability**: Clear what data is being created
- **Maintainability**: One place to update test data structure

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/session.html)
- [Factory Pattern in Testing](https://pytest-factoryboy.readthedocs.io/)
