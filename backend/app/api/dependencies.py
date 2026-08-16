from typing import cast

from fastapi import Request

from app.core.model_registry import ModelRegistry
from app.scheduler import ScheduleDispatcher
from app.services.runs import RunService


def get_run_service(request: Request) -> RunService:
    return cast(RunService, request.app.state.run_service)


def get_dispatcher(request: Request) -> ScheduleDispatcher:
    return cast(ScheduleDispatcher, request.app.state.dispatcher)


def get_model_registry(request: Request) -> ModelRegistry:
    return cast(ModelRegistry, request.app.state.model_registry)
