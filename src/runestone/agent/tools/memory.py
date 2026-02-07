"""Memory-related agent tools."""

import json
import logging
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from runestone.agent.tools.context import AgentContext
from runestone.services.user_service import UserService
from runestone.utils.merge import deep_merge

logger = logging.getLogger(__name__)


@tool
async def read_memory(
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Read the entire student memory profile.

    Use this tool when you need context about the student to personalize your
    teaching or when asked about what you know about the student.

    Returns:
    A JSON string containing all memory categories:
        - personal_info: goals, preferences, name, background
        - areas_to_improve: struggling concepts, recurring mistakes
        - knowledge_strengths: mastered topics, successful applications
    """
    user_context = runtime.context.user
    user_service = runtime.context.user_service

    logger.info(f"Reading memory for user {user_context.id}")

    # Fetch fresh user data from DB to ensure we don't use stale data
    # if memory was updated in the same conversation turn.
    user = user_service.get_user_by_id(user_context.id)
    if not user:
        return "Error: User not found."

    memory = {
        "personal_info": json.loads(user.personal_info) if user.personal_info else {},
        "areas_to_improve": json.loads(user.areas_to_improve) if user.areas_to_improve else {},
        "knowledge_strengths": json.loads(user.knowledge_strengths) if user.knowledge_strengths else {},
    }

    return json.dumps(memory, indent=2)


@tool
async def update_memory(
    category: Literal["personal_info", "areas_to_improve", "knowledge_strengths"],
    operation: Literal["merge", "replace"],
    data: dict,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """
    Update the student's memory profile with new information.

    Use this tool to store long-term information about the student:
    - personal_info: goals, preferences, name, background
    - areas_to_improve: struggling concepts, recurring mistakes
    - knowledge_strengths: mastered topics, successful applications

    Args:
        category: Which memory category to update
        operation: 'merge' to add/update keys, 'replace' to overwrite entirely
        data: JSON data to store (use descriptive keys like 'grammar_struggles')
        runtime: Tool runtime context containing user and user_service

    Returns:
        Confirmation message
    """
    user = runtime.context.user
    user_service: UserService = runtime.context.user_service

    logger.info(f"Updating memory for user {user.id}: {category}")

    async with runtime.context.db_lock:
        try:
            final_data = data
            if operation == "merge":
                # Get current data to merge with
                current_json = getattr(user, category)
                current_dict = json.loads(current_json) if current_json else {}
                final_data = deep_merge(current_dict, data)

            # Update memory via service
            user_service.update_user_memory(user, category, final_data)
            return f"Successfully updated {category}."
        except Exception as e:
            logger.error(f"Error updating memory for user {user.id}: {e}")
            # Ensure session is rolled back on error to avoid PendingRollbackError
            try:
                user_service.user_repo.db.rollback()
            except Exception:
                pass
            return f"Error updating memory: {str(e)}"
