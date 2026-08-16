import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_run_service
from app.db.models import Conversation
from app.db.session import SessionLocal
from app.schemas.api import RunAccepted, RunCreate, RunOut
from app.services.runs import RunService

router = APIRouter(tags=["runs"])


def _create(
    payload: RunCreate,
    service: RunService,
    conversation_id: str | None = None,
) -> RunAccepted:
    if conversation_id:
        with SessionLocal() as session:
            if session.get(Conversation, conversation_id) is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        run = service.create_run(payload, conversation_id=conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RunAccepted(id=run.id, status=run.status)


@router.post("/runs", response_model=RunAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_standalone_run(
    payload: RunCreate, service: RunService = Depends(get_run_service)
) -> RunAccepted:
    return _create(payload, service)


@router.post(
    "/conversations/{conversation_id}/runs",
    response_model=RunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_conversation_run(
    conversation_id: str,
    payload: RunCreate,
    service: RunService = Depends(get_run_service),
) -> RunAccepted:
    return _create(payload, service, conversation_id)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str) -> object:
    run = RunService.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunAccepted)
async def cancel_run(run_id: str, service: RunService = Depends(get_run_service)) -> RunAccepted:
    run = RunService.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await service.cancel(run_id)
    return RunAccepted(id=run_id, status="cancelled")


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    if RunService.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generate() -> AsyncIterator[str]:
        signature = ""
        while True:
            if await request.is_disconnected():
                break
            run = RunService.get_run(run_id)
            if run is None:
                break
            payload = jsonable_encoder(RunOut.model_validate(run))
            encoded = json.dumps(payload, separators=(",", ":"))
            new_signature = f"{run.status}:{len(run.steps)}:{run.finished_at}"
            if new_signature != signature:
                yield f"event: snapshot\ndata: {encoded}\n\n"
                signature = new_signature
            if run.status in {"succeeded", "review_failed", "failed", "cancelled"}:
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
