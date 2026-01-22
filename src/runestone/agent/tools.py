"""
Tool definitions for the agent using LangChain's @tool decorator.
"""

import json
import logging
from dataclasses import dataclass
from typing import Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from runestone.db.models import User
from runestone.services.user_service import UserService
from runestone.utils.merge import deep_merge

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context passed to agent tools at runtime."""

    user: User
    # we can't use DI of FastAPI here, so had to put the service to context
    user_service: UserService


@tool
def update_memory(
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

    try:
        final_data = data
        if operation == "merge":
            # Get current data to merge with
            current_json = getattr(user, category)
            current_dict = json.loads(current_json) if current_json else {}
            final_data = deep_merge(current_dict, data)

        logger.info(f"Final data for {category}: {final_data}")
        # Update memory via service
        user_service.update_user_memory(user, category, final_data)
        logger.info(f"Successfully updated {category} for user {user.id}")
        return f"Successfully updated {category}."
    except Exception as e:
        logger.error(f"Error updating memory for user {user.id}: {e}")
        return f"Error updating memory: {str(e)}"
