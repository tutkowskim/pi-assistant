from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.dependencies import get_run_service
from app.db.models import Conversation, Run
from app.db.session import SessionLocal
from app.schemas.api import DelegationAccepted, DelegationCreate, RunCreate, RunOptions
from app.services.conversations import title_from_prompt
from app.services.runs import RunService

router = APIRouter(tags=["delegations"])


def _child_depth(parent: Run) -> int:
    depth = 0
    current: Run | None = parent
    with SessionLocal() as session:
        while current is not None and current.parent_run_id is not None:
            depth += 1
            current = session.get(Run, current.parent_run_id)
    return depth + 1


@router.post(
    "/delegations", response_model=DelegationAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def create_delegation(
    payload: DelegationCreate, service: RunService = Depends(get_run_service)
) -> DelegationAccepted:
    with SessionLocal() as session:
        parent = session.get(Run, payload.parent_run_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent run not found")
        if parent.status != "running":
            raise HTTPException(status_code=409, detail="Parent run is not active")
        child_count = (
            session.scalar(
                select(func.count()).select_from(Run).where(Run.parent_run_id == parent.id)
            )
            or 0
        )
        if child_count >= service.settings.max_child_agents_per_run:
            raise HTTPException(status_code=429, detail="Child-agent limit reached for this run")
        depth = _child_depth(parent)
        if depth > service.settings.max_child_agent_depth:
            raise HTTPException(status_code=422, detail="Child-agent depth limit reached")
        parent_options = RunOptions.model_validate(parent.config)

    enabled_tools = list(parent_options.enabled_tools)
    if depth >= service.settings.max_child_agent_depth:
        enabled_tools = [tool_id for tool_id in enabled_tools if tool_id != "spawn_child_agent"]
    child_options = RunOptions(
        execution_mode="single",
        model_id=parent_options.model_id,
        reasoning_effort=parent_options.reasoning_effort,
        enabled_tools=enabled_tools,
        enabled_mcp_servers=parent_options.enabled_mcp_servers,
    )

    with SessionLocal.begin() as session:
        conversation = Conversation(
            title=payload.title or title_from_prompt(payload.task),
            defaults={"delegated": True, "parent_run_id": parent.id},
        )
        session.add(conversation)
        session.flush()
        conversation_id = conversation.id

    try:
        request = RunCreate(prompt=payload.task, **child_options.model_dump())
        run = service.create_run(
            request,
            conversation_id=conversation_id,
            parent_run_id=parent.id,
            source_type="child_agent",
        )
    except ValueError as exc:
        with SessionLocal.begin() as session:
            orphan = session.get(Conversation, conversation_id)
            if orphan is not None:
                session.delete(orphan)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DelegationAccepted(conversation_id=conversation_id, run_id=run.id, status=run.status)
