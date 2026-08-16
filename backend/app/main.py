import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import capabilities, conversations, delegations, health, runs, schedules
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.middleware import RequestIdMiddleware
from app.core.model_registry import ModelRegistry
from app.db.base import Base
from app.db.session import engine
from app.scheduler import ScheduleDispatcher
from app.services.conversations import backfill_default_conversation_titles
from app.services.runs import RunService

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    Base.metadata.create_all(engine)
    backfill_default_conversation_titles()
    RunService.recover_interrupted()
    model_registry = ModelRegistry(settings)
    await model_registry.refresh(force=True)
    model_registry.start()
    run_service = RunService(settings, model_registry)
    dispatcher = ScheduleDispatcher(run_service, settings.scheduler_poll_seconds)
    app.state.run_service = run_service
    app.state.model_registry = model_registry
    app.state.dispatcher = dispatcher
    dispatcher.start()
    yield
    await dispatcher.stop()
    await model_registry.stop()
    for task in list(run_service.tasks.values()):
        task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": None}},
    )


app.include_router(health.router, prefix="/api/v1")
app.include_router(capabilities.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(delegations.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
