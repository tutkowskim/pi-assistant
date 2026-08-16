import asyncio
import logging
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

import httpx
from openai import AsyncOpenAI

from app.core.config import Settings, split_model_id

logger = logging.getLogger(__name__)

REASONING_EFFORTS = ["low", "medium", "high"]


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    label: str
    provider: str
    reasoning_efforts: list[str]
    configured: bool = True

    def as_capability(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderStatus:
    provider: str
    configured: bool = False
    available: bool = False
    model_count: int = 0
    last_refreshed_at: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _openai_agent_model(model_id: str) -> bool:
    lowered = model_id.lower()
    excluded = (
        "audio",
        "computer-use",
        "embedding",
        "image",
        "moderation",
        "realtime",
        "search",
        "sora",
        "transcribe",
        "tts",
        "whisper",
    )
    return lowered.startswith(("gpt-5", "o1", "o3", "o4", "ft:gpt-5")) and not any(
        fragment in lowered for fragment in excluded
    )


def _gemini_agent_model(model_id: str) -> bool:
    normalized = model_id.removeprefix("models/").lower()
    return normalized.startswith("gemini-") and not any(
        fragment in normalized for fragment in ("embedding", "image", "live", "tts")
    )


def ollama_host_url(base_url: str) -> str:
    root = base_url.rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/api/ps", "/api/tags", "/v1"):
        if root.endswith(suffix):
            return root[: -len(suffix)]
    return root


def ollama_openai_base_url(base_url: str) -> str:
    return f"{ollama_host_url(base_url)}/v1/"


def ollama_tags_url(base_url: str) -> str:
    return f"{ollama_host_url(base_url)}/api/tags"


def installed_ollama_models(payload: dict[str, Any]) -> list[str]:
    return [
        str(item.get("name") or item.get("model"))
        for item in payload.get("models", [])
        if item.get("name") or item.get("model")
    ]


class ModelRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._models_by_provider: dict[str, list[ModelDefinition]] = {
            "openai": [],
            "gemini": [],
            "ollama": [],
        }
        self._statuses = {
            "openai": ProviderStatus(provider="openai", configured=bool(settings.openai_api_key)),
            "gemini": ProviderStatus(provider="gemini", configured=bool(settings.gemini_api_key)),
            "ollama": ProviderStatus(provider="ollama", configured=bool(settings.ollama_base_url)),
        }
        self._last_refresh = 0.0
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        if not settings.model_discovery_enabled:
            for model_id in settings.model_ids:
                provider, upstream_id = split_model_id(model_id)
                self._models_by_provider[provider].append(
                    ModelDefinition(
                        id=model_id,
                        label=upstream_id,
                        provider=provider,
                        reasoning_efforts=REASONING_EFFORTS,
                    )
                )
            for provider, models in self._models_by_provider.items():
                self._statuses[provider].available = bool(models)
                self._statuses[provider].model_count = len(models)

    @property
    def models(self) -> list[ModelDefinition]:
        return [
            model
            for provider in ("openai", "gemini", "ollama")
            for model in self._models_by_provider[provider]
        ]

    @property
    def model_ids(self) -> set[str]:
        return {model.id for model in self.models}

    @property
    def default_model_id(self) -> str | None:
        if self.settings.default_model_id in self.model_ids:
            return self.settings.default_model_id
        return self.models[0].id if self.models else None

    @property
    def provider_statuses(self) -> list[dict[str, Any]]:
        return [self._statuses[provider].as_dict() for provider in ("openai", "gemini", "ollama")]

    async def _query_openai(self) -> list[str]:
        if not self.settings.openai_api_key:
            return []
        client = AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=5, max_retries=0)
        try:
            page = await client.models.list()
            return [model.id for model in page.data if _openai_agent_model(model.id)]
        finally:
            await client.close()

    async def _query_gemini(self) -> list[str]:
        if not self.settings.gemini_api_key:
            return []
        client = AsyncOpenAI(
            api_key=self.settings.gemini_api_key,
            base_url=self.settings.gemini_base_url,
            timeout=5,
            max_retries=0,
        )
        try:
            page = await client.models.list()
            return [
                model.id.removeprefix("models/")
                for model in page.data
                if _gemini_agent_model(model.id)
            ]
        finally:
            await client.close()

    async def _query_ollama(self) -> list[str]:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(ollama_tags_url(self.settings.ollama_base_url))
            response.raise_for_status()
            payload = response.json()
        return installed_ollama_models(payload)

    async def refresh(self, force: bool = False) -> None:
        if not self.settings.model_discovery_enabled:
            return
        if not force and monotonic() - self._last_refresh < self.settings.model_refresh_seconds:
            return
        async with self._lock:
            if not force and monotonic() - self._last_refresh < self.settings.model_refresh_seconds:
                return
            results = await asyncio.gather(
                self._query_openai(),
                self._query_gemini(),
                self._query_ollama(),
                return_exceptions=True,
            )
            refreshed_at = datetime.now(UTC).isoformat()
            for provider, result in zip(("openai", "gemini", "ollama"), results, strict=True):
                status = self._statuses[provider]
                status.last_refreshed_at = refreshed_at
                if isinstance(result, BaseException):
                    status.available = bool(self._models_by_provider[provider])
                    status.error = f"{type(result).__name__}: provider query failed"
                    logger.warning("Model discovery failed for %s: %s", provider, result)
                    continue
                prefix = "" if provider == "openai" else f"{provider}/"
                discovered = [
                    ModelDefinition(
                        id=f"{prefix}{model_id}",
                        label=model_id,
                        provider=provider,
                        reasoning_efforts=REASONING_EFFORTS,
                    )
                    for model_id in sorted(set(result))
                ]
                self._models_by_provider[provider] = discovered
                status.available = status.configured
                status.model_count = len(discovered)
                status.error = None
            self._last_refresh = monotonic()

    def start(self) -> None:
        if self.settings.model_discovery_enabled and self._task is None:
            self._task = asyncio.create_task(self._refresh_loop(), name="model-discovery")

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.model_refresh_seconds)
            await self.refresh(force=True)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
