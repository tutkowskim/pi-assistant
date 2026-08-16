from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_model_registry
from app.core.capabilities import get_capabilities
from app.core.config import Settings, get_settings
from app.core.model_registry import ModelRegistry

router = APIRouter(tags=["capabilities"])


async def _capabilities(settings: Settings, registry: ModelRegistry) -> dict[str, Any]:
    await registry.refresh()
    return get_capabilities(settings, registry)


@router.get("/capabilities")
async def capabilities(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> dict[str, Any]:
    return await _capabilities(settings, registry)


@router.get("/models")
async def models(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Any:
    return (await _capabilities(settings, registry))["models"]


@router.get("/execution-modes")
async def execution_modes(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Any:
    return (await _capabilities(settings, registry))["execution_modes"]


@router.get("/reasoning-efforts")
async def reasoning_efforts(
    model_id: str = Query(...),
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Any:
    await registry.refresh()
    if model_id not in registry.model_ids:
        raise HTTPException(status_code=404, detail="Model is not enabled")
    return get_capabilities(settings, registry)["reasoning_efforts"]


@router.get("/tools")
async def tools(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Any:
    return (await _capabilities(settings, registry))["tools"]


@router.get("/mcp-servers")
async def mcp_servers(
    settings: Settings = Depends(get_settings),
    registry: ModelRegistry = Depends(get_model_registry),
) -> Any:
    return (await _capabilities(settings, registry))["mcp_servers"]
