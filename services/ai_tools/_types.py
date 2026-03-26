"""Core types for the AI tool system."""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable
from uuid import UUID

from repositories.container import RepositoryContainer


@dataclass
class AgentContext:
    """Context passed to all tool executions."""
    user_id: UUID
    chat_id: UUID
    repo: RepositoryContainer
    current_date: date = field(default_factory=date.today)


@dataclass
class ToolParam:
    """Annotation for tool parameters with description and optional constraints."""
    description: str
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Holds a tool's schema and executor function."""
    name: str
    description: str
    schema: dict[str, Any]  # OpenAI function calling format
    func: Callable  # The actual async function to execute
