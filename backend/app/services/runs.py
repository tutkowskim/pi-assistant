import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import Orchestrator
from app.agents.runner import OpenAIAgentRunner
from app.core.config import Settings
from app.core.model_registry import ModelRegistry
from app.db.models import Conversation, Message, Run, RunStep
from app.db.session import SessionLocal
from app.schemas.api import ParticipantConfig, RunCreate, RunOptions
from app.services.conversations import set_title_from_prompt
from app.services.validation import resolve_run_options
from app.tools.delegation import reset_delegation_context, set_delegation_context


class RunService:
    def __init__(self, settings: Settings, model_registry: ModelRegistry) -> None:
        self.settings = settings
        self.model_registry = model_registry
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_runs)
        self.child_semaphores = {
            depth: asyncio.Semaphore(settings.max_concurrent_child_runs)
            for depth in range(1, settings.max_child_agent_depth + 1)
        }

    def create_run(
        self,
        request: RunCreate,
        conversation_id: str | None = None,
        schedule_id: str | None = None,
        parent_run_id: str | None = None,
        source_type: str = "manual",
    ) -> Run:
        options = RunOptions.model_validate(request.model_dump(exclude={"prompt"}))
        options = resolve_run_options(options, self.settings, self.model_registry)
        with SessionLocal.begin() as session:
            run = Run(
                conversation_id=conversation_id,
                schedule_id=schedule_id,
                parent_run_id=parent_run_id,
                source_type=source_type,
                prompt=request.prompt,
                config=options.model_dump(mode="json"),
                status="queued",
            )
            session.add(run)
            session.flush()
            if conversation_id:
                session.add(
                    Message(
                        conversation_id=conversation_id,
                        run_id=run.id,
                        role="user",
                        content=request.prompt,
                    )
                )
                conversation = session.get(Conversation, conversation_id)
                if conversation is not None:
                    set_title_from_prompt(session, conversation, request.prompt)
                    conversation.updated_at = datetime.now(UTC)
            session.flush()
            run_id = run.id
        self.start(run_id)
        with SessionLocal() as session:
            return session.get(Run, run_id)  # type: ignore[return-value]

    def start(self, run_id: str) -> None:
        task = asyncio.create_task(self._execute(run_id), name=f"run-{run_id}")
        self.tasks[run_id] = task
        task.add_done_callback(lambda _task: self.tasks.pop(run_id, None))

    @staticmethod
    def record_rejected_schedule_run(
        request: RunCreate, schedule_id: str, conversation_id: str | None, message: str
    ) -> Run:
        with SessionLocal.begin() as session:
            run = Run(
                conversation_id=conversation_id,
                schedule_id=schedule_id,
                source_type="schedule",
                prompt=request.prompt,
                config=request.model_dump(mode="json", exclude={"prompt"}),
                status="failed",
                error_code="model_unavailable",
                error_message=message,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()
            run_id = run.id
        with SessionLocal() as session:
            return session.get(Run, run_id)  # type: ignore[return-value]

    async def cancel(self, run_id: str) -> bool:
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            return True
        return False

    async def _execute(self, run_id: str) -> None:
        with SessionLocal() as session:
            queued_run = session.get(Run, run_id)
            is_child = queued_run is not None and queued_run.source_type == "child_agent"
            child_depth = 0
            ancestor_id = queued_run.parent_run_id if queued_run is not None else None
            while ancestor_id is not None:
                child_depth += 1
                ancestor = session.get(Run, ancestor_id)
                ancestor_id = ancestor.parent_run_id if ancestor is not None else None
        semaphore = (
            self.child_semaphores[min(max(child_depth, 1), self.settings.max_child_agent_depth)]
            if is_child
            else self.semaphore
        )
        async with semaphore:
            try:
                await self._execute_inner(run_id)
            except asyncio.CancelledError:
                with SessionLocal.begin() as session:
                    run = session.get(Run, run_id)
                    if run:
                        run.status = "cancelled"
                        run.finished_at = datetime.now(UTC)
                raise
            except Exception as exc:
                with SessionLocal.begin() as session:
                    run = session.get(Run, run_id)
                    if run:
                        run.status = "failed"
                        run.error_code = "execution_failed"
                        run.error_message = str(exc)
                        run.finished_at = datetime.now(UTC)

    async def _execute_inner(self, run_id: str) -> None:
        with SessionLocal.begin() as session:
            run = session.get(Run, run_id)
            if run is None:
                return
            run.status = "running"
            run.started_at = datetime.now(UTC)
            prompt = run.prompt
            config = RunOptions.model_validate(run.config)
            conversation_id = run.conversation_id

        history = ""
        if conversation_id:
            with SessionLocal() as session:
                messages = session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                ).all()
                history = "\n".join(
                    f"{message.role}: {message.content}"
                    for message in messages[-20:]
                    if message.run_id != run_id
                )

        sequence_lock = asyncio.Lock()
        with SessionLocal() as session:
            sequence = (
                session.scalar(
                    select(func.count()).select_from(RunStep).where(RunStep.run_id == run_id)
                )
                or 0
            )

        async def record_step(
            participant: ParticipantConfig,
            output: str | None,
            verdict: dict[str, Any] | None,
            usage: dict[str, Any],
            review_attempt: int,
            debate_round: int | None,
        ) -> None:
            nonlocal sequence
            async with sequence_lock:
                sequence += 1
                with SessionLocal.begin() as session:
                    session.add(
                        RunStep(
                            run_id=run_id,
                            sequence=sequence,
                            participant_id=participant.id,
                            role=participant.role,
                            model_id=participant.model_id,
                            reasoning_effort=participant.reasoning_effort,
                            review_attempt=review_attempt,
                            debate_round=debate_round,
                            output=output,
                            verdict=verdict,
                            usage=usage,
                        )
                    )

        orchestrator = Orchestrator(OpenAIAgentRunner(self.settings), record_step)
        context_token = set_delegation_context(run_id)
        try:
            result = await orchestrator.execute(prompt, history, config)
        finally:
            reset_delegation_context(context_token)
        with SessionLocal.begin() as session:
            run = session.get(Run, run_id)
            if run is None:
                return
            run.status = result.status
            run.final_output = result.output
            run.error_code = result.error_code
            run.error_message = result.error_message
            run.finished_at = datetime.now(UTC)
            if result.status == "succeeded" and result.output and run.conversation_id:
                session.add(
                    Message(
                        conversation_id=run.conversation_id,
                        run_id=run.id,
                        role="assistant",
                        content=result.output,
                    )
                )
                conversation = session.get(Conversation, run.conversation_id)
                if conversation is not None:
                    conversation.updated_at = datetime.now(UTC)

    @staticmethod
    def get_run(run_id: str) -> Run | None:
        with SessionLocal() as session:
            return session.scalar(
                select(Run).where(Run.id == run_id).options(selectinload(Run.steps))
            )

    @staticmethod
    def recover_interrupted() -> None:
        with SessionLocal.begin() as session:
            runs = session.scalars(select(Run).where(Run.status == "running")).all()
            for run in runs:
                run.status = "failed"
                run.error_code = "interrupted"
                run.error_message = "The service restarted while this run was active."
                run.finished_at = datetime.now(UTC)
