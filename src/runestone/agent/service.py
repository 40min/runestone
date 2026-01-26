"""
Service layer for the chat agent.

This module contains the AgentService class that handles chat interactions
using LangChain's ReAct agent pattern.
"""

import json
import logging
from typing import Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from runestone.agent.prompts import load_persona
from runestone.agent.schemas import ChatMessage
from runestone.agent.tools import AgentContext, update_memory
from runestone.config import Settings
from runestone.db.models import User
from runestone.services.user_service import UserService

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing chat agent interactions using LangChain ReAct agent."""

    MAX_HISTORY_MESSAGES = 20

    def __init__(self, settings: Settings):
        """
        Initialize the agent service.

        Args:
            settings: Application settings containing chat configuration
        """
        self.settings = settings
        self.persona = load_persona(settings.agent_persona)
        self.agent = self.build_agent()

        logger.info(
            f"Initialized AgentService with provider={settings.chat_provider}, "
            f"model={settings.chat_model}, persona={settings.agent_persona}"
        )

    def build_agent(self):
        """
        Build a ReAct agent with tools.

        Returns:
            A LangGraph ReAct agent executor
        """
        settings = self.settings

        # Initialize the LangChain chat model
        if settings.chat_provider == "openrouter":
            api_key = settings.openrouter_api_key
            api_base = "https://openrouter.ai/api/v1"
        elif settings.chat_provider == "openai":
            api_key = settings.openai_api_key
            api_base = None
        else:
            raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")

        if not api_key:
            raise ValueError(f"API key for {settings.chat_provider} is not configured")

        chat_model = ChatOpenAI(
            model=settings.chat_model,
            api_key=SecretStr(api_key) if api_key else None,
            base_url=api_base,
            temperature=1,
        )

        tools = [update_memory]

        # Build system prompt with persona and tool instructions
        system_prompt = self.persona["system_prompt"]
        system_prompt += """

 ### RESPONSE GUIDELINES
- **NO ECHOING:** You are strictly forbidden from simply repeating the student's input.
- If the student's input is in Swedish and is grammatically correct, do NOT repeat it. Instead, acknowledge the
statement and ask a follow-up question to keep the conversation going.
- If the input is a question, answer it.
- If the input is a statement, react to it.

### MEMORY PROTOCOL
You are a memory-driven AI. Your effectiveness depends on maintaining a detailed, up-to-date profile of the student.

**CRITICAL: You MUST call `update_memory` immediately when you learn something new. This is not optional.**

**When to Update Memory (call the tool NOW):**
1. **Explicit Statements:** "My name is John," "I hate geometry." → Immediately call `update_memory` on `personal_info`.
2. **Implicit Behaviors:** Student fails a quiz question → Immediately call `update_memory` on `areas_to_improve`.
   Student solves a complex problem quickly → Immediately call `update_memory` on `knowledge_strengths`.
3. **Contextual Clues:** Student mentions a hobby or interest → Immediately call `update_memory` on `personal_info`.

**Tool Usage Rules:**
- Call `update_memory` BEFORE you respond to the student
- ALWAYS prefer the 'merge' operation to append new data
- Use 'replace' for correcting a factual error in previous memory or removing mastered topics
- If you are unsure if a detail is important, save it anyway

**If you learn something about the student and do NOT call update_memory, you are failing your core function.**
"""

        agent = create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=system_prompt,
            context_schema=AgentContext,
        )

        return agent

    async def generate_response(
        self,
        message: str,
        history: list[ChatMessage],
        user: User,
        user_service: UserService,
        memory_context: Optional[dict] = None,
    ) -> str:
        """
        Generate a response to a user message using the ReAct agent.

        Args:
            message: The user's message
            history: Previous conversation messages
            user: User model instance
            user_service: UserService instance to handle memory operations
            memory_context: Optional dictionary containing student memory

        Returns:
            The agent's final text response

        Raises:
            Exception: If the agent invocation fails
        """
        # Build conversation messages
        messages = []

        # Add user's mother tongue if available
        if user.mother_tongue:
            language_msg = (
                f"[IMPORTANT] STUDENT'S MOTHER TONGUE: {user.mother_tongue}\n\n"
                "Respond only in the student's mother tongue. "
                "Use this information to personalize your teaching."
            )
            messages.append(SystemMessage(content=language_msg))

        # Add memory context as initial system message if available
        if memory_context:
            active_memory = {k: v for k, v in memory_context.items() if v}
            if active_memory:
                memory_str = json.dumps(active_memory, indent=2)
                memory_msg = f"STUDENT MEMORY:\n{memory_str}\n\nUse this information to personalize your teaching."
                messages.append(SystemMessage(content=memory_msg))

        # Add conversation history
        truncated_history = history[-self.MAX_HISTORY_MESSAGES :] if history else []
        for msg in truncated_history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        # Add current user message
        messages.append(HumanMessage(content=message))

        try:
            result = await self.agent.ainvoke(
                {"messages": messages},
                context=AgentContext(user=user, user_service=user_service),
            )

            final_messages = result.get("messages", [])
            for msg in reversed(final_messages):
                if hasattr(msg, "content") and msg.content:
                    if hasattr(msg, "tool_call_id") or (hasattr(msg, "tool_calls") and msg.tool_calls):
                        continue
                    return msg.content

            return "I'm sorry, I couldn't generate a response."

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
