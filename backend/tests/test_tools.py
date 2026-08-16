import asyncio
import json
import sys
from datetime import datetime

import httpx
import pytest

from app.core.config import get_settings
from app.tools import delegation, python_sandbox
from app.tools.delegation import (
    reset_delegation_context,
    set_delegation_context,
    spawn_child_agent,
)
from app.tools.local import calculator, current_time
from app.tools.python_sandbox import _docker_command, _OutputBudget, _read_bounded, execute_python


def test_calculator_respects_precedence_and_decimals() -> None:
    assert calculator("2 + 3 * 4")["result"] == "14"
    assert calculator("0.1 + 0.2")["result"] == "0.3"
    assert calculator("2 ** 8")["result"] == "256"


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "open('/etc/passwd')",
        "value + 1",
        "(1).__class__",
        "2 ** 1000",
        "1 / 0",
    ],
)
def test_calculator_rejects_unsafe_or_unbounded_input(expression: str) -> None:
    with pytest.raises(ValueError):
        calculator(expression)


def test_current_time_uses_valid_timezone() -> None:
    result = current_time("America/Los_Angeles")
    assert result["timezone"] == "America/Los_Angeles"
    assert datetime.fromisoformat(result["local_datetime"]).utcoffset() is not None
    assert datetime.fromisoformat(result["utc_datetime"]).utcoffset() is not None


def test_current_time_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        current_time("Mars/Olympus_Mons")


def test_python_sandbox_command_enforces_isolation_without_embedding_code() -> None:
    command = _docker_command("docker", "sandbox-name", "python:3.12-alpine", 11)

    assert command[:2] == ["docker", "run"]
    assert command[-8:] == [
        "python:3.12-alpine",
        "timeout",
        "-s",
        "KILL",
        "11",
        "python",
        "-I",
        "-",
    ]
    assert command[command.index("--network") + 1] == "none"
    assert command[command.index("--pull") + 1] == "never"
    assert command[command.index("--log-driver") + 1] == "none"
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert "--read-only" in command
    assert "no-new-privileges:true" in command
    assert "seccomp=builtin" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert "--pids-limit" in command
    assert "--volume" not in command
    assert "--mount" not in command
    assert "print('must only travel over stdin')" not in command


@pytest.mark.asyncio
async def test_python_sandbox_combines_and_bounds_output() -> None:
    stream = asyncio.StreamReader()
    stream.feed_data(b"123456789")
    stream.feed_eof()
    chunks: list[bytes] = []
    budget = _OutputBudget(5)

    await _read_bounded(stream, chunks, budget)

    assert chunks == [b"12345"]
    assert budget.truncated is True
    assert budget.exceeded.is_set()


@pytest.mark.asyncio
async def test_execute_python_streams_code_over_stdin(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={"python_sandbox_docker_executable": sys.executable}
    )
    monkeypatch.setattr(python_sandbox, "get_settings", lambda: settings)
    monkeypatch.setattr(
        python_sandbox,
        "_docker_command",
        lambda _executable, _name, _image, _timeout: [sys.executable, "-I", "-"],
    )

    result = await execute_python("print(sum(range(10)))")

    assert result["exit_code"] == 0
    assert result["stdout"] == "45\n"
    assert result["stderr"] == ""
    assert result["timed_out"] is False
    assert result["output_truncated"] is False


@pytest.mark.asyncio
async def test_execute_python_rejects_invalid_limits_before_starting() -> None:
    with pytest.raises(ValueError, match="must contain"):
        await execute_python("")
    with pytest.raises(ValueError, match="timeout_seconds"):
        await execute_python("print('no')", timeout_seconds=0)


@pytest.mark.asyncio
async def test_spawn_child_agent_calls_api_and_returns_result(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "conversation_id": "conversation-child",
                    "run_id": "run-child",
                    "status": "queued",
                },
            )
        return httpx.Response(
            200,
            json={"status": "succeeded", "final_output": "child result", "error_message": None},
        )

    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def client_factory(**kwargs):  # type: ignore[no-untyped-def]
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr(delegation.httpx, "AsyncClient", client_factory)
    token = set_delegation_context("run-parent")
    try:
        result = await spawn_child_agent("Analyze branch A", "Branch A")
    finally:
        reset_delegation_context(token)

    assert result == {
        "conversation_id": "conversation-child",
        "run_id": "run-child",
        "status": "succeeded",
        "output": "child result",
        "error": None,
    }
    assert json.loads(requests[0].content) == {
        "parent_run_id": "run-parent",
        "task": "Analyze branch A",
        "title": "Branch A",
    }
    assert requests[0].url.path == "/api/v1/delegations"
    assert requests[1].url.path == "/api/v1/runs/run-child"
