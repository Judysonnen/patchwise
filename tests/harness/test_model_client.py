"""these tests exercise the message-translation helpers without hitting the
real openai / anthropic APIs (no keys needed in CI).

end-to-end calls are exercised by scripts/run_eval.py during the actual eval.
"""
from __future__ import annotations

import json

from harness.model_client import (
    AnthropicClient,
    Message,
    OpenAIClient,
    ToolCall,
)


def test_openai_translates_user_message():
    msg = Message(role="user", content="hi")
    out = OpenAIClient._to_openai_msg(msg)
    assert out == {"role": "user", "content": "hi"}


def test_openai_translates_tool_response():
    msg = Message(role="tool", content="42", tool_call_id="call_1")
    out = OpenAIClient._to_openai_msg(msg)
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "call_1"
    assert out["content"] == "42"


def test_openai_translates_assistant_with_tool_calls():
    msg = Message(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(name="read_file", arguments={"path": "x.py"}, call_id="c1")],
    )
    out = OpenAIClient._to_openai_msg(msg)
    assert out["role"] == "assistant"
    assert out["tool_calls"][0]["function"]["name"] == "read_file"
    # arguments must be a json STRING for openai, not a dict
    assert json.loads(out["tool_calls"][0]["function"]["arguments"]) == {"path": "x.py"}


def test_anthropic_translates_tool_response_as_user_role():
    """anthropic encodes tool results as user-role messages with a
    tool_result content block. easy to get wrong, so worth a test."""
    msg = Message(role="tool", content="42", tool_call_id="c1")
    out = AnthropicClient._to_anthropic_msg(msg)
    assert out["role"] == "user"
    assert out["content"][0]["type"] == "tool_result"
    assert out["content"][0]["tool_use_id"] == "c1"
    assert out["content"][0]["content"] == "42"


def test_anthropic_translates_assistant_tool_use_block():
    msg = Message(
        role="assistant",
        content="reading the file",
        tool_calls=[ToolCall(name="read_file", arguments={"path": "x.py"}, call_id="c1")],
    )
    out = AnthropicClient._to_anthropic_msg(msg)
    assert out["role"] == "assistant"
    types = [b["type"] for b in out["content"]]
    assert types == ["text", "tool_use"]
    assert out["content"][1]["input"] == {"path": "x.py"}
