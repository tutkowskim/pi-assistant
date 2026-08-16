from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_run_service
from app.db.models import Run, Schedule
from app.db.session import get_db
from app.schemas.api import (
    RunAccepted,
    RunCreate,
    RunOptions,
    RunOut,
    ScheduleCreate,
    ScheduleOut,
    ScheduleUpdate,
)
from app.services.runs import RunService
from app.services.schedules import calculate_next_run
from app.services.validation import resolve_run_options

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _validated_run_config(payload: RunOptions | None, service: RunService) -> dict[str, object]:
    if payload is None:
        raise ValueError("run_config cannot be null")
    options = resolve_run_options(payload, service.settings, service.model_registry)
    return options.model_dump(mode="json")


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> Schedule:
    try:
        next_run_at = calculate_next_run(
            payload.schedule_type, payload.schedule_config, payload.timezone
        )
        run_config = _validated_run_config(payload.run_config, service)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    schedule = Schedule(
        name=payload.name,
        prompt=payload.prompt,
        enabled=payload.enabled,
        schedule_type=payload.schedule_type,
        schedule_config=payload.schedule_config,
        timezone=payload.timezone,
        run_config=run_config,
        conversation_id=payload.conversation_id,
        next_run_at=next_run_at if payload.enabled else None,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db)) -> list[Schedule]:
    return list(db.scalars(select(Schedule).order_by(Schedule.created_at.desc())).all())


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(schedule_id: str, db: Session = Depends(get_db)) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    changes = payload.model_dump(exclude_unset=True)
    if "run_config" in changes:
        changes["run_config"] = _validated_run_config(payload.run_config, service)
    for key, value in changes.items():
        setattr(schedule, key, value)
    schedule.updated_at = datetime.now(UTC)
    try:
        schedule.next_run_at = (
            calculate_next_run(schedule.schedule_type, schedule.schedule_config, schedule.timezone)
            if schedule.enabled
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)) -> Response:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{schedule_id}/run-now", response_model=RunAccepted, status_code=202)
async def run_schedule_now(
    schedule_id: str,
    db: Session = Depends(get_db),
    service: RunService = Depends(get_run_service),
) -> RunAccepted:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    try:
        run = service.create_run(
            RunCreate.model_validate({"prompt": schedule.prompt, **schedule.run_config}),
            conversation_id=schedule.conversation_id,
            schedule_id=schedule.id,
            source_type="schedule",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RunAccepted(id=run.id, status=run.status)


@router.get("/{schedule_id}/runs", response_model=list[RunOut])
def list_schedule_runs(schedule_id: str, db: Session = Depends(get_db)) -> list[Run]:
    if db.get(Schedule, schedule_id) is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return list(
        db.scalars(
            select(Run).where(Run.schedule_id == schedule_id).order_by(Run.created_at.desc())
        ).all()
    )
