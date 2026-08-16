from collections.abc import Callable
from typing import Any

from app.tools.delegation import spawn_child_agent
from app.tools.local import calculator, current_time

ToolCallable = Callable[..., Any]

LOCAL_TOOLS: dict[str, ToolCallable] = {
    "current_time": current_time,
    "calculator": calculator,
    "spawn_child_agent": spawn_child_agent,
}


def validate_tool_ids(tool_ids: list[str]) -> None:
    unknown = set(tool_ids) - set(LOCAL_TOOLS)
    if unknown:
        raise ValueError(f"Unknown tools: {', '.join(sorted(unknown))}")


def get_tool_functions(tool_ids: list[str]) -> list[ToolCallable]:
    validate_tool_ids(tool_ids)
    return [LOCAL_TOOLS[tool_id] for tool_id in tool_ids]
