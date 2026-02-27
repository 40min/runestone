"""Shared context for agent tools."""

from dataclasses import dataclass

from runestone.db.models import User
from runestone.rag.index import GrammarIndex
from runestone.services.grammar_service import GrammarService


@dataclass
class AgentContext:
    """Context passed to agent tools at runtime."""

    user: User
    # Grammar services - used by grammar tools
    grammar_index: GrammarIndex | None = None
    grammar_service: GrammarService | None = None
