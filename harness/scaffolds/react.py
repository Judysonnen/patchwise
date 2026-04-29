"""minimal react loop: model produces thoughts + tool calls until it stops or
hits max_steps. nothing fancy — this is the baseline scaffold to compare
the planner-executor variant against.
"""
from __future__ import annotations

from typing import Callable

from ..model_client import Completion, Message, ModelClient, ToolCall, ToolDef
from ..trace_store import TraceStore

SYSTEM_PROMPT = (
    "you are a coding agent fixing a bug in a python repository. you have "
    "tools to inspect files, search the repo, run tests, and apply patches. "
    "work step by step. when the failing tests pass, stop calling tools."
)


def run_react(
    task_prompt: str,
    tools: list[ToolDef],
    tool_dispatch: Callable[[ToolCall], str],
    model: ModelClient,
    trace: TraceStore,
    trajectory_id: str,
    max_steps: int = 25,
) -> Completion | None:
    messages: list[Message] = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=task_prompt),
    ]
    trace.append(
        trajectory_id, 0, "start",
        {"prompt": task_prompt, "model": model.name, "scaffold": "react"},
    )

    for step in range(1, max_steps + 1):
        completion = model.complete(messages, tools=tools)
        trace.append(
            trajectory_id, step, "completion",
            {
                "text": completion.text,
                "tool_calls": [
                    {"name": tc.name, "args": tc.arguments} for tc in completion.tool_calls
                ],
            },
        )

        if not completion.tool_calls:
            trace.append(trajectory_id, step, "stop", {"reason": "no_more_tools"})
            return completion

        messages.append(
            Message(
                role="assistant",
                content=completion.text,
                tool_calls=completion.tool_calls,
            )
        )
        for tc in completion.tool_calls:
            try:
                result = tool_dispatch(tc)
            except Exception as e:
                result = f"tool error: {type(e).__name__}: {e}"
            # 2000 char cap on logged result so the trace db doesn't explode on
            # huge run_tests output. the FULL result still goes to the model
            # (via messages.append below) — only the trace log is truncated.
            trace.append(
                trajectory_id, step, "tool_result",
                {"call_id": tc.call_id, "name": tc.name, "result": result[:2000]},
            )
            messages.append(
                Message(role="tool", content=result, tool_call_id=tc.call_id)
            )

    trace.append(trajectory_id, max_steps, "stop", {"reason": "max_steps"})
    return None
