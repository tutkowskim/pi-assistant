from sqlalchemy import select

from app.db.models import Conversation, Run
from app.db.session import SessionLocal
from app.schemas.api import ParticipantConfig, RunOptions
from app.services.runs import RunService


def test_delegation_creates_linked_chat_and_child_run(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def execute_without_provider_call(_service: RunService, _run_id: str) -> None:
        return None

    monkeypatch.setattr(RunService, "_execute", execute_without_provider_call)
    options = RunOptions(
        model_id="test-model-a",
        enabled_tools=["spawn_child_agent", "calculator"],
        participants=[
            ParticipantConfig(
                id="primary",
                role="primary",
                model_id="test-model-a",
                reasoning_effort="medium",
            )
        ],
    )
    with SessionLocal.begin() as session:
        parent = Run(
            status="running",
            source_type="manual",
            prompt="Parent task",
            config=options.model_dump(mode="json"),
        )
        session.add(parent)
        session.flush()
        parent_id = parent.id

    response = client.post(
        "/api/v1/delegations",
        json={"parent_run_id": parent_id, "task": "Solve the isolated subproblem"},
    )

    assert response.status_code == 202
    accepted = response.json()
    with SessionLocal() as session:
        child = session.get(Run, accepted["run_id"])
        conversation = session.get(Conversation, accepted["conversation_id"])
        assert child is not None
        assert child.parent_run_id == parent_id
        assert child.source_type == "child_agent"
        assert child.conversation_id == conversation.id  # type: ignore[union-attr]
        assert child.config["execution_mode"] == "single"
        assert conversation.defaults["parent_run_id"] == parent_id  # type: ignore[union-attr]
        assert session.scalar(select(Run).where(Run.parent_run_id == parent_id)) is child
