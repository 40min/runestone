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

Database-backed tests normally use a **per-test outer PostgreSQL transaction**. The engine and schema are created once per test session, and each test's sessions join its dedicated connection through savepoints. The shared schema remains a serial-test design; concurrent pytest workers must not target it.

### Isolation Guarantees

- **Fast default isolation**: Each eligible test runs inside one outer transaction that is rolled back afterward
- **Real commit/rollback behavior**: Test and application sessions use `join_transaction_mode="create_savepoint"`
- **Explicit exception path**: `@pytest.mark.db_schema_reset` gives tests real independent connections and a clean schema
- **Unique test user**: Each test gets a unique user with a UUID-based email
- **Automatic cleanup**: The outer transaction removes ordinary test data; marked tests reset the schema
- **No shared state**: No data persists between tests

### Database Configuration

```python
# Database-backed tests use the PostgreSQL URL from .env.test
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    poolclass=NullPool,
)
```

This deliberately exercises the same PostgreSQL dialect and async driver as the application. A local test database must be available at the `DATABASE_URL` configured in `.env.test`.

## Key Fixtures

### Database Fixtures

Located in `tests/conftest.py`:

#### `db_engine`
Creates the engine and application schema once for the test session.

```python
@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

#### `db_isolation`
By default, opens one connection and outer transaction per test, then transactionally truncates mapped tables with `RESTART IDENTITY` so legacy tests receive deterministic PostgreSQL identities. `db_session_factory` binds every session to that connection with `join_transaction_mode="create_savepoint"`, so commits and rollbacks remain testable while final outer rollback removes all changes. A session or connection must never be used concurrently by multiple async tasks.

Tests that require genuinely independent connections must use `@pytest.mark.db_schema_reset`. This includes concurrent insert races, committed cross-session visibility, true lock contention, and sequence-dependent cases that cannot safely be rewritten. Marked tests receive engine-bound sessions and a schema reset before and after the test.

#### `db_session`
Provides a database session with automatic rollback after the test.

```python
@pytest.fixture(scope="function")
async def db_session(db_session_factory):
    db = db_session_factory()
    try:
        yield db
    finally:
        await db.rollback()
        await db.close()
```

#### `db_with_test_user`
Provides both a database session and a pre-created test user.

```python
@pytest.fixture(scope="function")
async def db_with_test_user(db_session):
    db = db_session
    test_user = User(..., email=f"test-{uuid.uuid4()}@example.com")
    db.add(test_user)
    await db.commit()
    await db.refresh(test_user)
    yield db, test_user
```

`db_with_test_user` reuses the canonical `db_session` fixture. Tests must not keep multiple sessions with overlapping transactions on the same test connection: rolling back an older PostgreSQL savepoint invalidates savepoints opened later by another session. Create additional sessions only for sequential work, or use `@pytest.mark.db_schema_reset` when the behavior genuinely requires independent concurrent connections.

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
    output = await read_memory.coroutine(runtime, category="personal_info", statuses=["active"])
    assert output == "No memory items found."
```

**Why different approaches?**
- Tools without `ToolRuntime`: Parameters can be serialized to JSON, so `.ainvoke()` works directly
- Tools with `ToolRuntime`: The runtime contains complex objects (like database models) that can't be serialized to JSON, so we use `.coroutine()` with a manually constructed runtime

Example: Service test
```python
@pytest.mark.anyio
async def test_load_current_recall_words(recall_service):
    recall_service.recall_repository.get_current_recall_words.return_value = [
        "hello",
        "goodbye",
    ]

    words = await recall_service.load_current_recall_words(user_id=1)

    assert words == ["hello", "goodbye"]
    recall_service.recall_repository.rollback.assert_not_awaited()
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

### Parallel Execution

Do not run database-backed tests with `pytest -n auto` against the shared
`.env.test` database. Outer transactions and marked schema resets are designed
for serial pytest execution. Parallel execution requires a separate PostgreSQL
database or schema per worker and is not part of the current fixture contract.

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
- **Don't point tests at development or production databases** - use the dedicated PostgreSQL database in `.env.test`
- **Don't mock database models directly** - use the repository layer
- **Don't create fixtures in test files** - use the shared fixtures in `conftest.py`

## Troubleshooting

### PostgreSQL connection errors
- Ensure PostgreSQL is running and the `.env.test` database exists
- Verify the test user can create and drop tables in that database
- Confirm no other test process is using or resetting the same schema concurrently

### Tests failing on CI but passing locally
- Check that all tests use the `.env.test` file (set by conftest)
- Ensure `ENV_FILE` environment variable is set before imports
- Verify all database operations are wrapped in transactions

### Missing-relation errors
- Ensure `Base.metadata.create_all()` runs through `conn.run_sync()` before tests
- Check that your model imports are correct
- Verify the model is registered with `Base`

## Architecture Decisions

### Why PostgreSQL?
- **Parity**: Repository SQL and constraint behavior match production
- **Async coverage**: Tests exercise SQLAlchemy's asyncpg path
- **Reliability**: PostgreSQL-specific queries and metadata cannot silently diverge

### Why Transaction/Savepoint Isolation?
- **Speed**: Schema creation and teardown happen once for ordinary tests
- **Compatibility**: Transactional identity restart preserves deterministic ids without rebuilding the schema
- **Behavior coverage**: Nested savepoints let application code commit and roll back normally
- **Safety**: The outer transaction is owned by the fixture and always rolled back
- **Honest concurrency tests**: The schema-reset marker preserves real independent connections where one shared connection would be invalid

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
