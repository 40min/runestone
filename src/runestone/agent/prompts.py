"""
Prompt management for the chat agent.

This module handles loading persona configurations and building prompts.
"""

from pathlib import Path
from typing import Dict, List

import yaml

from runestone.agent.schemas import ChatMessage


def load_persona(persona_name: str) -> Dict[str, str]:
    """
    Load a persona configuration from YAML file.

    Args:
        persona_name: Name of the persona to load (e.g., "default")

    Returns:
        Dictionary containing persona configuration with 'name' and 'system_prompt'

    Raises:
        FileNotFoundError: If the persona file doesn't exist
        yaml.YAMLError: If the YAML file is malformed
    """
    # Get the directory where this file is located
    current_dir = Path(__file__).parent
    persona_file = current_dir / "persona" / f"{persona_name}.yaml"

    if not persona_file.exists():
        raise FileNotFoundError(f"Persona file not found: {persona_file}")

    with open(persona_file, "r", encoding="utf-8") as f:
        persona_data = yaml.safe_load(f)

    if not isinstance(persona_data, dict) or "system_prompt" not in persona_data:
        raise ValueError(f"Invalid persona file format: {persona_file}")

    return persona_data


def build_messages(system_prompt: str, history: list[ChatMessage], user_message: str) -> List[Dict[str, str]]:
    """
    Build the full message list for the LLM.

    Args:
        system_prompt: The system prompt defining the agent's persona
        history: Previous conversation messages
        user_message: The current user message

    Returns:
        List of message dictionaries in LangChain format
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    return messages
