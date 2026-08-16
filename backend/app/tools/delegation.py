import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

TERMINAL_STATUSES = {"succeeded", "review_failed", "failed", "cancelled"}


@dataclass(frozen=True)
class DelegationContext:
    run_id: str


_delegation_context: ContextVar[DelegationContext | None] = ContextVar(
    "delegation_context", default=None
)


def set_delegation_context(run_id: str) -> Token[DelegationContext | None]:
    return _delegation_context.set(DelegationContext(run_id=run_id))


def reset_delegation_context(token: Token[DelegationContext | None]) -> None:
    _delegation_context.reset(token)


async def spawn_child_agent(task: str, title: str | None = None) -> dict[str, Any]:
    """Delegate a self-contained task to a child agent in a fresh chat and return its result.

    Use this aggressively for large requests, independent research or analysis branches, and work
    that would otherwise add substantial context to the current chat. Give the child all context
    required to complete its task because it cannot see the parent conversation. Prefer several
    focused delegations over one sprawling task, but do not delegate trivial or tightly serial work.
    """
    context = _delegation_context.get()
    if context is None:
        raise RuntimeError("Child agents can only be spawned from an active run")

    settings = get_settings()
    timeout = httpx.Timeout(settings.child_agent_timeout_seconds, connect=10)
    async with httpx.AsyncClient(
        base_url=f"{settings.child_agent_api_base_url.rstrip('/')}/", timeout=timeout
    ) as client:
        response = await client.post(
            "delegations",
            json={"parent_run_id": context.run_id, "task": task, "title": title},
        )
        response.raise_for_status()
        accepted = response.json()
        run_id = str(accepted["run_id"])

        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.child_agent_timeout_seconds
        while loop.time() < deadline:
            response = await client.get(f"runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            if run["status"] in TERMINAL_STATUSES:
                return {
                    "conversation_id": accepted["conversation_id"],
                    "run_id": run_id,
                    "status": run["status"],
                    "output": run.get("final_output"),
                    "error": run.get("error_message"),
                }
            await asyncio.sleep(settings.child_agent_poll_seconds)

    raise TimeoutError(
        f"Child agent {run_id} did not finish within {settings.child_agent_timeout_seconds:g}s"
    )
