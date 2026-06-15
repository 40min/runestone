"""
Agent tools for memory management.

This module provides tools for the agent to read and manage user memory.
"""

import logging
from typing import Annotated, Optional

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.utils import serialize_active_learning_focus, serialize_memory_items
from runestone.api.memory_item_schemas import (
    AreaToImproveStatus,
    MemoryCategory,
    MemoryItemCreate,
    MemorySortBy,
    PersonalInfoStatus,
    SortDirection,
)
from runestone.core.exceptions import PermissionDeniedError, UserNotFoundError

logger = logging.getLogger(__name__)


class MemoryStatusUpdate(BaseModel):
    """Input for updating memory item status."""

    item_id: int = Field(..., description="ID of the memory item to update")
    new_status: str = Field(..., description="New status value")


class MemoryPriorityUpdate(BaseModel):
    """Input for updating priority of an area_to_improve item."""

    item_id: int = Field(..., description="ID of the area_to_improve memory item")
    priority: Optional[int] = Field(
        ...,
        ge=0,
        le=9,
        description="Priority 0-9 (0=highest urgency). Null is treated as 9 (lowest/default).",
    )


class MemoryDeleteInput(BaseModel):
    """Input for deleting a memory item."""

    item_id: int = Field(..., description="ID of the memory item to delete")


class MemoryContentUpdate(BaseModel):
    """Input for updating the content of an existing memory item."""

    item_id: int = Field(..., description="ID of the memory item to update")
    category: MemoryCategory = Field(..., description="Expected category of the memory item")
    content: str = Field(..., min_length=1, description="Replacement content for the memory item")


class PersonalInfoAppendInput(BaseModel):
    """Input for appending a raw personal_info memory item."""

    key: str = Field(..., min_length=1, max_length=100, description="Descriptive personal_info key")
    content: str = Field(..., min_length=1, description="Raw personal fact to append")
    status: str = Field(
        default=PersonalInfoStatus.ACTIVE.value,
        description="personal_info status, defaults to active",
    )


def _format_tool_error(tool_name: str, exc: Exception) -> str:
    """Return agent-readable tool errors for expected memory business rule failures."""
    logger.warning("Agent tool call failed: %s: %s", tool_name, exc)
    return f"Tool error in {tool_name}: {exc}"


@tool
async def read_memory(
    runtime: ToolRuntime[AgentContext],
    category: Annotated[
        Optional[MemoryCategory],
        Field(description="Optional category filter"),
    ] = None,
    statuses: Annotated[
        Optional[list[str]],
        Field(description="Optional status filters"),
    ] = None,
) -> str:
    """
    Read the agent's memory about the user.

    Returns structured memory items with IDs, categories, keys, content, and status.
    Use this tool when you need context about the student to personalize your
    teaching or when asked about what you know about the student.
    Results are capped to the 100 freshest matching items and ordered by last-updated date
    descending so agents see the newest signals first.

    Args:
        runtime: Tool runtime context
        category: Optional filter by category (personal_info, area_to_improve)
        statuses: Optional filter by statuses

    Returns:
        Formatted string with memory items including IDs for reference
    """
    logger.info("Agent tool call: read_memory (category=%s, statuses=%s)", category, statuses)
    user = runtime.context.user

    # Use fresh service with its own session for concurrency safety
    async with provide_memory_item_service() as service:
        items = await service.list_memory_items(
            user_id=user.id,
            category=category,
            statuses=statuses,
            sort_by=MemorySortBy.UPDATED_AT,
            sort_direction=SortDirection.DESC,
            limit=100,
            offset=0,
        )

    if not items:
        return "No memory items found."

    return serialize_memory_items(items)


@tool
async def read_active_learning_focus(runtime: ToolRuntime[AgentContext]) -> str:
    """Read the student's current high-priority learning focus for Teacher."""
    logger.info("Agent tool call: read_active_learning_focus")
    user = runtime.context.user

    async with provide_memory_item_service() as service:
        items = await service.list_memory_items(
            user_id=user.id,
            category=MemoryCategory.AREA_TO_IMPROVE,
            statuses=[
                AreaToImproveStatus.STRUGGLING.value,
                AreaToImproveStatus.IMPROVING.value,
            ],
            limit=5,
            offset=0,
        )

    if not items:
        return "No active learning focus items found."

    return serialize_active_learning_focus(items)


@tool
async def upsert_memory_item(
    runtime: ToolRuntime[AgentContext],
    item: Annotated[MemoryItemCreate, Field(description="Memory item to create or update")],
) -> str:
    """
    Create or update a memory item about the user.

    Use this when you learn new information or need to update existing knowledge.
    If an item with the same category and key exists, it will be updated.
    For area_to_improve items, you may optionally set a priority (0-9, 0=highest urgency).

    Args:
        runtime: Tool runtime context
        item: Memory item data (category, key, content, optional status, optional priority)

    Returns:
        Confirmation message with item ID
    """
    logger.info(
        "Agent tool call: upsert_memory_item (category=%s, key=%s, status=%s, priority=%s)",
        item.category,
        item.key,
        item.status,
        item.priority,
    )
    user = runtime.context.user

    # Use fresh service with its own session for concurrency safety
    async with provide_memory_item_service() as service:
        result = await service.upsert_memory_item(
            user_id=user.id,
            category=item.category,
            key=item.key,
            content=item.content,
            status=item.status,
            priority=item.priority,
        )

    priority_str = f", priority: {result.priority}" if result.priority is not None else ""
    return (
        f"Memory item saved: [ID:{result.id}] {result.key} in {result.category} (status: {result.status}{priority_str})"
    )


@tool
async def append_personal_info_item(
    runtime: ToolRuntime[AgentContext],
    item: Annotated[PersonalInfoAppendInput, Field(description="Raw personal_info fact to append")],
) -> str:
    """Append a raw personal_info memory item without deduplicating by key."""
    logger.info("Agent tool call: append_personal_info_item (key=%s, status=%s)", item.key, item.status)
    user = runtime.context.user

    try:
        async with provide_memory_item_service() as service:
            result = await service.append_personal_info_item(
                user_id=user.id,
                key=item.key,
                content=item.content,
                status=item.status,
            )
    except (PermissionDeniedError, UserNotFoundError, ValueError) as exc:
        return _format_tool_error("append_personal_info_item", exc)

    return f"Personal info appended: [ID:{result.id}] {result.key} (status: {result.status})"


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

    Args:
        runtime: Tool runtime context
        update: Status update data (item_id, new_status)

    Returns:
        Confirmation message
    """
    logger.info("Agent tool call: update_memory_status (item_id=%s, new_status=%s)", update.item_id, update.new_status)
    user = runtime.context.user

    # Use fresh service with its own session for concurrency safety
    try:
        async with provide_memory_item_service() as service:
            result = await service.update_item_status(update.item_id, update.new_status, user.id)
    except (PermissionDeniedError, UserNotFoundError, ValueError) as exc:
        return _format_tool_error("update_memory_status", exc)

    return f"Status updated: [ID:{result.id}] {result.key} is now '{result.status}'"


@tool
async def update_memory_item_content(
    runtime: ToolRuntime[AgentContext],
    update: Annotated[MemoryContentUpdate, Field(description="Content update data")],
) -> str:
    """
    Replace the content of an existing memory item by id.

    Use this when the current turn explicitly corrects or replaces the substance
    of an existing memory item and you already know which item id should change.

    Args:
        runtime: Tool runtime context
        update: Content update data (item_id, content)

    Returns:
        Confirmation message
    """
    logger.info("Agent tool call: update_memory_item_content (item_id=%s)", update.item_id)
    user = runtime.context.user

    try:
        async with provide_memory_item_service() as service:
            result = await service.update_item_content_in_category(
                update.item_id,
                update.category,
                update.content,
                user.id,
            )
    except (PermissionDeniedError, UserNotFoundError, ValueError) as exc:
        return _format_tool_error("update_memory_item_content", exc)

    return f"Content updated: [ID:{result.id}] {result.key}"


@tool
async def update_memory_priority(
    runtime: ToolRuntime[AgentContext],
    update: Annotated[MemoryPriorityUpdate, Field(description="Priority update data")],
) -> str:
    """
    Set the priority of an area_to_improve memory item.

    Use this to indicate which directly implicated topics need the most urgent attention:
    - Lower priority = more urgent (0 is the highest priority).
    - Raise priority (lower number) when the student repeatedly makes errors on the same topic.
    - Lower priority (higher number) only when the current signal is explicitly about reduced urgency,
      not as a routine companion to a status change.
    - Priority still matters for stored urgency and for downstream maintenance decisions, even though
      read_memory now returns the freshest matching items first.
    - Only reprioritize the specific item(s) directly tied to the current turn's explicit signal.
      Never use this tool to rebalance or renumber the broader memory set; that belongs to MemoryMaintainer.
    - For normal progress updates such as struggling -> improving or improving -> mastered, prefer
      update_memory_status instead of changing both status and priority for the same item in one turn.

    Args:
        runtime: Tool runtime context
        update: Priority update data (item_id, priority 0-9, or null which maps to 9)

    Returns:
        Confirmation message
    """
    logger.info("Agent tool call: update_memory_priority (item_id=%s, priority=%s)", update.item_id, update.priority)
    user = runtime.context.user

    try:
        async with provide_memory_item_service() as service:
            result = await service.update_item_priority(update.item_id, update.priority, user.id)
    except (PermissionDeniedError, UserNotFoundError, ValueError) as exc:
        return _format_tool_error("update_memory_priority", exc)

    return f"Priority updated: [ID:{result.id}] {result.key} priority is now {result.priority}"


@tool
async def delete_memory_item(
    runtime: ToolRuntime[AgentContext],
    delete: Annotated[MemoryDeleteInput, Field(description="Memory item to delete")],
) -> str:
    """
    Delete a memory item.

    Use only when the student explicitly asks you to forget something, or when the
    student confirms an existing memory item is wrong and should be removed.
    """
    logger.info("Agent tool call: delete_memory_item (item_id=%s)", delete.item_id)
    user = runtime.context.user

    # Use fresh service with its own session for concurrency safety
    try:
        async with provide_memory_item_service() as service:
            await service.delete_item(delete.item_id, user.id)
    except (PermissionDeniedError, UserNotFoundError, ValueError) as exc:
        return _format_tool_error("delete_memory_item", exc)

    return f"Deleted memory item: [ID:{delete.item_id}]"
