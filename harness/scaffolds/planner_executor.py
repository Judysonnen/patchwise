"""planner-executor: planner writes a numbered plan first (no tools), then a
react-style executor follows it.

ROUGH: as written, the executor isn't actually constrained by the plan — it
just has the plan in its system prompt. on multi-file edits the upfront plan
seems to keep the model focused; on small single-file edits the planner step
just burns budget. need to redesign so the executor actually walks the plan
step by step, with a "next step is N: ..." hint each turn. TODO.
"""
from __future__ import annotations

from typing import Callable

from ..model_client import Completion, Message, ModelClient, ToolCall, ToolDef
from ..trace_store import TraceStore

PLANNER_PROMPT = (
    "you are the PLANNER. read the task and produce a numbered plan (3-7 "
    "steps) for fixing it. do not call any tools. output a numbered list, "
    "one step per line, no preamble."
)

EXECUTOR_PROMPT = (
    "you are the EXECUTOR. follow the plan below using the available tools. "
    "work step by step. when the failing tests pass, stop calling tools.\n\n"
    "PLAN:\n{plan}"
)


def run_planner_executor(
    task_prompt: str,
    tools: list[ToolDef],
    tool_dispatch: Callable[[ToolCall], str],
    model: ModelClient,
    trace: TraceStore,
    trajectory_id: str,
    max_steps: int = 25,
) -> Completion | None:
    # 1. PLANNING (no tools)
    plan_msgs = [
        Message(role="system", content=PLANNER_PROMPT),
        Message(role="user", content=task_prompt),
    ]
    plan_completion = model.complete(plan_msgs, tools=None)
    plan_text = plan_completion.text or ""
    trace.append(
        trajectory_id, 0, "plan",
        {"text": plan_text, "model": model.name, "scaffold": "planner_executor"},
    )

    # 2. EXECUTION (react-style loop, but with the plan in system prompt)
    messages: list[Message] = [
        Message(role="system", content=EXECUTOR_PROMPT.format(plan=plan_text)),
        Message(role="user", content=task_prompt),
    ]

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
            trace.append(
                trajectory_id, step, "tool_result",
                {"call_id": tc.call_id, "name": tc.name, "result": result[:2000]},
            )
            messages.append(
                Message(role="tool", content=result, tool_call_id=tc.call_id)
            )

    trace.append(trajectory_id, max_steps, "stop", {"reason": "max_steps"})
    return None
