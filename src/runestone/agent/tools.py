"""
Tool definitions for the agent using LangChain's @tool decorator.
"""

import json
from typing import Annotated, Any, Literal

from langchain_core.tools import InjectedToolArg, tool

from runestone.utils.merge import deep_merge


@tool
def update_memory(
    category: Literal["personal_info", "areas_to_improve", "knowledge_strengths"],
    operation: Literal["merge", "replace"],
    data: dict,
    user: Annotated[Any, InjectedToolArg],
    user_service: Annotated[Any, InjectedToolArg],
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

    Returns:
        Confirmation message
    """
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
        return f"Error updating memory: {str(e)}"
