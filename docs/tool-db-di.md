# Tool Database Dependency Injection (DI)

This document describes the design pattern and implementation for database access within LangGraph agent tools in the Runestone project.

## 🎯 The Problem: Concurrency in LangGraph

LangGraph agents often execute multiple tools concurrently. In an asynchronous environment using SQLAlchemy's `AsyncSession`, sharing a single session across concurrent operations is unsafe and will lead to errors like:
- `IllegalStateError: This session is already executing a query.`
- Race conditions when committing or rolling back transactions.

Furthermore, agent tools are often imported by the agent manager, and if those tools import services from the main application layer, it can easily lead to circular import dependencies.

## 💡 The Solution: Async Context-Manager Providers

To solve these issues, we use a specialized dependency injection pattern using **async context managers** located in a dedicated module: `src/runestone/agents/tools/service_providers.py`.

### Key Benefits
1. **Session Isolation**: Each tool call gets its own fresh `AsyncSession`, ensuring concurrency safety.
2. **Automatic Cleanup**: The context manager ensures the session is closed as soon as the tool operation completes.
3. **Circular Import Prevention**: By centralizing tool-specific providers in `service_providers.py`, we avoid direct dependencies between agent tools and the main service layer's initialization logic.

## 🛠️ Implementation Details

The module `runestone.agents.tools.service_providers` provides factory functions that yield fully configured service instances.

### Example Provider Implementation

```python
@asynccontextmanager
async def provide_memory_item_service() -> AsyncIterator[MemoryItemService]:
    """
    Context manager for creating a MemoryItemService with its own database session.
    """
    async with provide_db_session() as session:
        repo = MemoryItemRepository(session)
        service = MemoryItemService(repo)
        yield service
```

## 🚀 Usage Pattern in Tools

When defining a LangGraph tool, use the `async with` statement to obtain a service instance.

```python
@tool
async def read_memory(
    runtime: ToolRuntime[AgentContext],
    category: Optional[MemoryCategory] = None,
) -> str:
    """Read the agent's memory about the user."""
    user = runtime.context.user

    # Use fresh service with its own session for concurrency safety
    async with provide_memory_item_service() as service:
        items = await service.list_memory_items(
            user_id=user.id,
            category=category
        )

    return format_results(items)
```

## ✅ Best Practices

1. **Always Use Context Managers**: Never pass a shared session into an agent tool.
2. **Grain of Usage**: Open the context manager as late as possible and close it as soon as the DB work is done.
3. **No Direct Repository Access**: Tools should interact with Services, not Repositories directly, to maintain business logic encapsulation.
4. **Keep Providers Simple**: Service providers should only handle the instantiation and wiring of dependencies.
