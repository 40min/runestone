"""
Tool wrappers for memory maintainer background consolidation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from runestone.agents.service_providers import provide_memory_item_service
from runestone.agents.tools.context import AgentContext
from runestone.agents.tools.memory import _format_tool_error
from runestone.agents.tools.utils import serialize_memory_items
from runestone.api.memory_item_schemas import AreaToImproveStatus, MemoryCategory
from runestone.constants import MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY
from runestone.core.exceptions import MemoryItemNotFoundError, PermissionDeniedError
from runestone.db.models import MemoryItem

logger = logging.getLogger(__name__)

MAINTAINER_ALLOWED_STATUSES = {
    AreaToImproveStatus.STRUGGLING.value,
    AreaToImproveStatus.IMPROVING.value,
}


@dataclass
class PendingMergePlan:
    """Tracks which item ids can be deleted after a validated consolidation insert."""

    consolidated_item_id: int
    remaining_delete_ids: set[int]


_PENDING_MERGE_DELETIONS: dict[int, PendingMergePlan] = {}


def clear_pending_merge_plan(user_id: int) -> None:
    """Clear any pending merge-delete plan for a user."""
    _PENDING_MERGE_DELETIONS.pop(user_id, None)


class MaintainerInsertInput(BaseModel):
    """Input for scoped memory maintainer insert."""

    category: MemoryCategory = Field(
        default=MemoryCategory.AREA_TO_IMPROVE,
        description="Must be area_to_improve for memory maintainer",
    )
    key: str = Field(..., min_length=1, max_length=200, description="Unique key for the memory item")
    content: str = Field(..., min_length=1, max_length=1000, description="Memory content in English")
    status: AreaToImproveStatus | None = Field(
        default=None,
        description="Status for area_to_improve item; only struggling or improving allowed.",
    )
    priority: int | None = Field(
        default=None,
        ge=0,
        le=9,
        description="Priority 0-9 (0=highest urgency). Null is treated as 9 (lowest/default).",
    )
    replaced_item_ids: list[int] = Field(
        default_factory=list,
        description=(
            "Original item ids replaced by this consolidated item. " "For merge flows, must include every replaced id."
        ),
    )


class MaintainerDeleteInput(BaseModel):
    """Input for scoped memory maintainer delete."""

    item_id: int = Field(..., description="ID of the memory item to delete")


class MaintainerPriorityUpdate(BaseModel):
    """Input for scoped memory maintainer priority updates."""

    item_id: int = Field(..., description="ID of the area_to_improve memory item")
    priority: int | None = Field(
        ...,
        ge=0,
        le=9,
        description="Priority 0-9 (0=highest urgency). Null is treated as 9 (lowest/default).",
    )


def _is_in_maintainer_scope(category: str, status: str) -> bool:
    return category == MemoryCategory.AREA_TO_IMPROVE.value and status in MAINTAINER_ALLOWED_STATUSES


def _scope_error(tool_name: str, item_id: int, category: str, status: str) -> str:
    return _format_tool_error(
        tool_name,
        ValueError(
            "Item is out of memory maintainer scope "
            f"(item_id={item_id}, category={category}, status={status}). "
            "Only area_to_improve items with status struggling/improving are allowed."
        ),
    )


def _status_value(status: AreaToImproveStatus | str | None) -> str:
    if isinstance(status, AreaToImproveStatus):
        return status.value
    return status or AreaToImproveStatus.STRUGGLING.value


@tool
async def maintainer_read_memory(runtime: ToolRuntime[AgentContext]) -> str:
    """Read only in-scope memory items for maintenance."""
    logger.info("Agent tool call: maintainer_read_memory")
    user = runtime.context.user

    async with provide_memory_item_service() as service:
        items = await service.list_memory_items(
            user_id=user.id,
            category=MemoryCategory.AREA_TO_IMPROVE,
            statuses=[
                AreaToImproveStatus.STRUGGLING.value,
                AreaToImproveStatus.IMPROVING.value,
            ],
            limit=200,
            offset=0,
        )

    if not items:
        return "No in-scope memory items found."
    return serialize_memory_items(items)


@tool
async def maintainer_insert_memory_item(
    runtime: ToolRuntime[AgentContext],
    item: Annotated[MaintainerInsertInput, Field(description="Memory item to create in maintainer scope")],
) -> str:
    """Insert only in-scope memory items and validate merge replacements."""
    logger.info(
        "Agent tool call: maintainer_insert_memory_item (category=%s, key=%s, status=%s, priority=%s, replaced_ids=%s)",
        item.category,
        item.key,
        item.status,
        item.priority,
        item.replaced_item_ids,
    )
    user = runtime.context.user
    status = _status_value(item.status)

    if item.category != MemoryCategory.AREA_TO_IMPROVE:
        return _format_tool_error(
            "maintainer_insert_memory_item",
            ValueError("Only category 'area_to_improve' is allowed for memory maintainer."),
        )
    if status not in MAINTAINER_ALLOWED_STATUSES:
        return _format_tool_error(
            "maintainer_insert_memory_item",
            ValueError("Only statuses 'struggling' and 'improving' are allowed for memory maintainer."),
        )

    pending_plan = _PENDING_MERGE_DELETIONS.get(user.id)
    if pending_plan and pending_plan.remaining_delete_ids:
        return _format_tool_error(
            "maintainer_insert_memory_item",
            ValueError(
                "Cannot start a new consolidation while previous replaced items are still pending deletion "
                f"(pending_item_ids={sorted(pending_plan.remaining_delete_ids)})."
            ),
        )

    replaced_item_ids = sorted(set(item.replaced_item_ids))

    async with provide_memory_item_service() as service:
        if replaced_item_ids:
            replaced_statuses: set[str] = set()
            replaced_items = await service.repo.get_by_ids(replaced_item_ids)
            replaced_by_id = {replaced_item.id: replaced_item for replaced_item in replaced_items}
            missing_ids = [
                replaced_item_id for replaced_item_id in replaced_item_ids if replaced_item_id not in replaced_by_id
            ]
            if missing_ids:
                return _format_tool_error(
                    "maintainer_insert_memory_item",
                    MemoryItemNotFoundError(f"Memory item with id {missing_ids[0]} not found"),
                )

            for replaced_item_id in replaced_item_ids:
                replaced_item = replaced_by_id[replaced_item_id]
                if replaced_item.user_id != user.id:
                    return _format_tool_error(
                        "maintainer_insert_memory_item",
                        PermissionDeniedError("You don't have permission to replace this item"),
                    )
                if not _is_in_maintainer_scope(replaced_item.category, replaced_item.status):
                    return _scope_error(
                        "maintainer_insert_memory_item",
                        replaced_item.id,
                        replaced_item.category,
                        replaced_item.status,
                    )
                replaced_statuses.add(replaced_item.status)

            if len(replaced_statuses) > 1:
                return _format_tool_error(
                    "maintainer_insert_memory_item",
                    ValueError(
                        "Cross-status consolidation is not allowed. "
                        f"All replaced items must share one status, got {sorted(replaced_statuses)}."
                    ),
                )

            replaced_status = next(iter(replaced_statuses))
            if status != replaced_status:
                return _format_tool_error(
                    "maintainer_insert_memory_item",
                    ValueError(
                        "Consolidated item status must match replaced item status "
                        f"(expected={replaced_status}, got={status})."
                    ),
                )

        if item.priority is not None and not (0 <= item.priority <= 9):
            return _format_tool_error(
                "maintainer_insert_memory_item",
                ValueError(f"priority must be between 0 and 9, got {item.priority}"),
            )

        service.validate_status(MemoryCategory.AREA_TO_IMPROVE, status)
        create_priority = item.priority
        if create_priority is None:
            create_priority = MEMORY_DEFAULT_AREA_TO_IMPROVE_PRIORITY

        try:
            created_item = await service.repo.create(
                MemoryItem(
                    user_id=user.id,
                    category=MemoryCategory.AREA_TO_IMPROVE.value,
                    key=item.key,
                    content=item.content,
                    status=status,
                    priority=create_priority,
                    status_changed_at=datetime.now(timezone.utc),
                )
            )
        except IntegrityError as exc:
            await service.repo.db.rollback()
            return _format_tool_error(
                "maintainer_insert_memory_item",
                ValueError(
                    "Insert failed due to duplicate key for this user/category. "
                    f"Use a new versioned key. Original error: {exc.__class__.__name__}"
                ),
            )

    if replaced_item_ids:
        _PENDING_MERGE_DELETIONS[user.id] = PendingMergePlan(
            consolidated_item_id=created_item.id,
            remaining_delete_ids={item_id for item_id in replaced_item_ids if item_id != created_item.id},
        )

    priority_str = f", priority: {created_item.priority}" if created_item.priority is not None else ""
    return (
        f"Memory item saved: [ID:{created_item.id}] {created_item.key} in {created_item.category} "
        f"(status: {created_item.status}{priority_str})"
    )


@tool
async def maintainer_delete_memory_item(
    runtime: ToolRuntime[AgentContext],
    delete: Annotated[MaintainerDeleteInput, Field(description="In-scope memory item to delete")],
) -> str:
    """Delete only in-scope memory items."""
    logger.info("Agent tool call: maintainer_delete_memory_item (item_id=%s)", delete.item_id)
    user = runtime.context.user
    pending_plan = _PENDING_MERGE_DELETIONS.get(user.id)

    if pending_plan and delete.item_id == pending_plan.consolidated_item_id:
        return _format_tool_error(
            "maintainer_delete_memory_item",
            ValueError(
                f"Cannot delete the just-created consolidated item (item_id={pending_plan.consolidated_item_id})."
            ),
        )
    if not pending_plan or delete.item_id not in pending_plan.remaining_delete_ids:
        return _format_tool_error(
            "maintainer_delete_memory_item",
            ValueError(
                "Delete is only allowed for ids listed in replaced_item_ids of the active consolidation upsert call."
            ),
        )

    async with provide_memory_item_service() as service:
        item = await service.repo.get_by_id(delete.item_id)
        if not item:
            return _format_tool_error(
                "maintainer_delete_memory_item",
                MemoryItemNotFoundError(f"Memory item with id {delete.item_id} not found"),
            )
        if item.user_id != user.id:
            return _format_tool_error(
                "maintainer_delete_memory_item",
                PermissionDeniedError("You don't have permission to delete this item"),
            )
        if not _is_in_maintainer_scope(item.category, item.status):
            return _scope_error("maintainer_delete_memory_item", item.id, item.category, item.status)
        await service.delete_item(delete.item_id, user.id)

    pending_plan.remaining_delete_ids.discard(delete.item_id)
    if not pending_plan.remaining_delete_ids:
        _PENDING_MERGE_DELETIONS.pop(user.id, None)
    return f"Deleted memory item: [ID:{delete.item_id}]"


@tool
async def maintainer_update_memory_priority(
    runtime: ToolRuntime[AgentContext],
    update: Annotated[MaintainerPriorityUpdate, Field(description="In-scope priority update data")],
) -> str:
    """Set priority only for in-scope memory items."""
    logger.info(
        "Agent tool call: maintainer_update_memory_priority (item_id=%s, priority=%s)",
        update.item_id,
        update.priority,
    )
    user = runtime.context.user

    async with provide_memory_item_service() as service:
        item = await service.repo.get_by_id(update.item_id)
        if not item:
            return _format_tool_error(
                "maintainer_update_memory_priority",
                MemoryItemNotFoundError(f"Memory item with id {update.item_id} not found"),
            )
        if item.user_id != user.id:
            return _format_tool_error(
                "maintainer_update_memory_priority",
                PermissionDeniedError("You don't have permission to update this item"),
            )
        if not _is_in_maintainer_scope(item.category, item.status):
            return _scope_error("maintainer_update_memory_priority", item.id, item.category, item.status)
        result = await service.update_item_priority(update.item_id, update.priority, user.id)

    return f"Priority updated: [ID:{result.id}] {result.key} priority is now {result.priority}"
