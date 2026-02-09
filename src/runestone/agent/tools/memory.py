"""
Agent tools for memory management.

This module provides tools for the agent to read and manage user memory.
"""

from typing import Annotated, Literal, Optional

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from runestone.agent.tools.context import AgentContext


class MemoryItemInput(BaseModel):
    """Input for creating/updating a memory item."""

    category: Literal["personal_info", "area_to_improve", "knowledge_strength"] = Field(
        ..., description="Category of the memory item"
    )
    key: str = Field(..., description="Unique key for the memory item within the category")
    content: str = Field(..., description="Content/description of the memory item")
    status: Optional[str] = Field(
        None,
        description="Optional status. If not provided, defaults based on category. "
        "Valid values: personal_info (active, outdated), "
        "area_to_improve (struggling, improving, mastered), "
        "knowledge_strength (active, archived)",
    )


class MemoryStatusUpdate(BaseModel):
    """Input for updating memory item status."""

    item_id: int = Field(..., description="ID of the memory item to update")
    new_status: str = Field(..., description="New status value")


class MemoryPromoteInput(BaseModel):
    """Input for promoting an item to knowledge_strength."""

    item_id: int = Field(..., description="ID of the mastered area_to_improve item to promote")


@tool
async def read_memory(
    runtime: ToolRuntime[AgentContext],
    category: Annotated[
        Optional[Literal["personal_info", "area_to_improve", "knowledge_strength"]],
        Field(description="Optional category filter"),
    ] = None,
    status: Annotated[Optional[str], Field(description="Optional status filter")] = None,
) -> str:
    """
    Read the agent's memory about the user.

    Returns structured memory items with IDs, categories, keys, content, and status.
    Use this tool when you need context about the student to personalize your
    teaching or when asked about what you know about the student.

    Args:
        runtime: Tool runtime context
        category: Optional filter by category (personal_info, area_to_improve, knowledge_strength)
        status: Optional filter by status

    Returns:
        Formatted string with memory items including IDs for reference
    """
    user = runtime.context.user
    service = runtime.context.memory_item_service

    items = service.list_memory_items(user_id=user.id, category=category, status=status, limit=200, offset=0)

    if not items:
        return "No memory items found."

    # Group items by category
    grouped = {}
    for item in items:
        if item.category not in grouped:
            grouped[item.category] = []
        grouped[item.category].append(item)

    # Format output
    output_lines = ["=== Agent Memory ===\n"]
    for cat, cat_items in grouped.items():
        output_lines.append(f"\n## {cat.replace('_', ' ').title()}")
        for item in cat_items:
            output_lines.append(f"  [ID:{item.id}] {item.key}: {item.content} (status: {item.status})")

    return "\n".join(output_lines)


@tool
async def upsert_memory_item(
    runtime: ToolRuntime[AgentContext],
    item: Annotated[MemoryItemInput, Field(description="Memory item to create or update")],
) -> str:
    """
    Create or update a memory item about the user.

    Use this when you learn new information or need to update existing knowledge.
    If an item with the same category and key exists, it will be updated.

    Args:
        runtime: Tool runtime context
        item: Memory item data (category, key, content, optional status)

    Returns:
        Confirmation message with item ID
    """
    user = runtime.context.user
    service = runtime.context.memory_item_service

    result = service.upsert_memory_item(
        user_id=user.id,
        category=item.category,
        key=item.key,
        content=item.content,
        status=item.status,
    )

    return f"Memory item saved: [ID:{result.id}] {result.key} in {result.category} (status: {result.status})"


@tool
async def update_memory_status(
    runtime: ToolRuntime[AgentContext],
    update: Annotated[MemoryStatusUpdate, Field(description="Status update data")],
) -> str:
    """
    Update the status of a memory item.

    Use this to track progress on areas to improve or mark information as outdated.

    Valid status transitions:
    - personal_info: active, outdated
    - area_to_improve: struggling, improving, mastered
    - knowledge_strength: active, archived

    Args:
        runtime: Tool runtime context
        update: Status update data (item_id, new_status)

    Returns:
        Confirmation message
    """
    user = runtime.context.user
    service = runtime.context.memory_item_service

    result = service.update_item_status(update.item_id, update.new_status, user.id)

    return f"Status updated: [ID:{result.id}] {result.key} is now '{result.status}'"


@tool
async def promote_to_strength(
    runtime: ToolRuntime[AgentContext],
    promote: Annotated[MemoryPromoteInput, Field(description="Item to promote")],
) -> str:
    """
    Promote a mastered area_to_improve item to knowledge_strength.

    Use this when a user has fully mastered a concept that was previously a struggle.
    The item will be moved from area_to_improve to knowledge_strength.

    Args:
        runtime: Tool runtime context
        promote: Promotion data (item_id of mastered item)

    Returns:
        Confirmation message
    """
    user = runtime.context.user
    service = runtime.context.memory_item_service

    result = service.promote_to_strength(promote.item_id, user.id)

    return f"Promoted to knowledge_strength: [ID:{result.id}] {result.key}"
