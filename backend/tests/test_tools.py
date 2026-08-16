import json
from datetime import datetime

import httpx
import pytest

from app.tools import delegation
from app.tools.delegation import (
    reset_delegation_context,
    set_delegation_context,
    spawn_child_agent,
)
from app.tools.local import calculator, current_time


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
