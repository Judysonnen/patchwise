"""thin abstraction over openai + anthropic so scaffolds don't care which vendor.

both vendors get translated to/from a neutral Message/ToolDef shape. the shape
borrows from openai's chat-completions format because it's the lingua franca,
but anything specific to one vendor stays inside its respective Client.

usage:
    from harness.model_client import OpenAIClient, AnthropicClient
    client = OpenAIClient("gpt-4o-mini")    # needs OPENAI_API_KEY
    client = AnthropicClient("claude-haiku-4-5")  # needs ANTHROPIC_API_KEY
    completion = client.complete(messages, tools=[...])
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict  # JSON Schema for arguments


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


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini"):
        # import inside __init__ so just importing this module doesn't
        # require the openai package to be installed.
        from openai import OpenAI

        self._client = OpenAI()
        self.name = model

    def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> Completion:
        oai_messages = [self._to_openai_msg(m) for m in messages]
        oai_tools = None
        if tools:
            oai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        resp = self._client.chat.completions.create(
            model=self.name,
            messages=oai_messages,
            tools=oai_tools,
        )
        choice = resp.choices[0].message
        tool_calls = []
        for tc in (choice.tool_calls or []):
            tool_calls.append(
                ToolCall(
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                    call_id=tc.id,
                )
            )
        return Completion(text=choice.content, tool_calls=tool_calls, raw=resp.model_dump())

    @staticmethod
    def _to_openai_msg(m: Message) -> dict:
        if m.role == "tool":
            return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""}
        d: dict = {"role": m.role}
        if m.content is not None:
            d["content"] = m.content
        if m.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
        return d


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicClient:
    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 4096):
        from anthropic import Anthropic

        self._client = Anthropic()
        self.name = model
        self.max_tokens = max_tokens

    def complete(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> Completion:
        # anthropic separates `system` out of the messages list.
        system_msg = None
        ant_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
                continue
            ant_messages.append(self._to_anthropic_msg(m))

        ant_tools = None
        if tools:
            ant_tools = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]

        kwargs = {
            "model": self.name,
            "max_tokens": self.max_tokens,
            "messages": ant_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if ant_tools:
            kwargs["tools"] = ant_tools

        resp = self._client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(name=block.name, arguments=block.input, call_id=block.id)
                )
        return Completion(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            raw=resp.model_dump(),
        )

    @staticmethod
    def _to_anthropic_msg(m: Message) -> dict:
        if m.role == "tool":
            # anthropic encodes tool results as user-role messages with a
            # tool_result content block. confusing convention but it's what
            # the API expects.
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content or "",
                    }
                ],
            }
        if m.tool_calls:
            content = []
            if m.content:
                content.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                content.append(
                    {"type": "tool_use", "id": tc.call_id, "name": tc.name, "input": tc.arguments}
                )
            return {"role": m.role, "content": content}
        return {"role": m.role, "content": m.content or ""}
