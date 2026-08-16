from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_model_registry
from app.core.config import get_settings
from app.core.model_registry import ModelRegistry
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(
    db: Session = Depends(get_db),
    model_registry: ModelRegistry = Depends(get_model_registry),
) -> dict[str, str | bool | int]:
    db.execute(text("SELECT 1"))
    settings = get_settings()
    return {
        "status": "ready",
        "version": settings.app_version,
        "timezone": settings.app_timezone,
        "openai_configured": bool(settings.openai_api_key),
        "gemini_configured": bool(settings.gemini_api_key),
        "ollama_configured": bool(settings.ollama_base_url),
        "discovered_models": len(model_registry.models),
    }
