"""thin abstraction over openai + anthropic so scaffolds don't care which vendor.

both vendors get translated to/from a neutral Message/ToolDef shape. the shape
borrows from openai's chat-completions format because it's the lingua franca,
but anything specific to one vendor stays inside its respective Client.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class ToolCall:
    name: str
    arguments: dict
    call_id: str


@dataclass
class Message:
    role: str  # "system", "user", "assistant", "tool"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # only on role="tool"


@dataclass
class Completion:
    text: str | None
    tool_calls: list[ToolCall]
    raw: Any  # vendor's native response, kept for trace logging


class ModelClient(Protocol):
    name: str

    def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> Completion: ...
