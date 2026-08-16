import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import Schedule
from app.db.session import SessionLocal
from app.schemas.api import RunCreate
from app.services.runs import RunService
from app.services.schedules import calculate_next_run

logger = logging.getLogger(__name__)


class ScheduleDispatcher:
    def __init__(self, run_service: RunService, poll_seconds: int) -> None:
        self.run_service = run_service
        self.poll_seconds = poll_seconds
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self._loop(), name="schedule-dispatcher")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.poll_seconds)

    async def tick(self) -> None:
        now = datetime.now(UTC)
        due_ids: list[str] = []
        with SessionLocal.begin() as session:
            due = session.scalars(
                select(Schedule).where(
                    Schedule.enabled.is_(True),
                    Schedule.next_run_at.is_not(None),
                    Schedule.next_run_at <= now,
                )
            ).all()
            for schedule in due:
                due_ids.append(schedule.id)
                schedule.last_run_at = now
                schedule.next_run_at = calculate_next_run(
                    schedule.schedule_type, schedule.schedule_config, schedule.timezone, now
                )
                if schedule.schedule_type == "once":
                    schedule.enabled = False

        for schedule_id in due_ids:
            with SessionLocal() as session:
                current_schedule = session.get(Schedule, schedule_id)
                if current_schedule is None:
                    continue
                payload = {"prompt": current_schedule.prompt, **current_schedule.run_config}
                request = RunCreate.model_validate(payload)
                try:
                    self.run_service.create_run(
                        request,
                        conversation_id=current_schedule.conversation_id,
                        schedule_id=current_schedule.id,
                        source_type="schedule",
                    )
                except ValueError as exc:
                    logger.warning("Scheduled run rejected for %s: %s", current_schedule.id, exc)
                    self.run_service.record_rejected_schedule_run(
                        request,
                        current_schedule.id,
                        current_schedule.conversation_id,
                        str(exc),
                    )
