from unittest.mock import AsyncMock

import pytest

from app.agents.runner import OpenAIAgentRunner
from app.core.capabilities import get_capabilities
from app.core.config import Settings, split_model_id
from app.core.model_registry import (
    ModelRegistry,
    installed_ollama_models,
    ollama_openai_base_url,
    ollama_tags_url,
)


def provider_settings() -> Settings:
    return Settings(
        model_ids=[
            "gpt-5.6",
            "gemini/gemini-3.6-flash",
            "ollama/gemma4",
        ],
        default_model_id="gpt-5.6",
        model_discovery_enabled=False,
        openai_api_key="openai-test",
        gemini_api_key="gemini-test",
        ollama_base_url="http://ollama:11434/v1/",
        app_data_dir="./data",
        database_url="sqlite:///:memory:",
    )


def test_model_provider_ids_are_resolved() -> None:
    assert split_model_id("gpt-5.6") == ("openai", "gpt-5.6")
    assert split_model_id("gemini/gemini-3.6-flash") == (
        "gemini",
        "gemini-3.6-flash",
    )
    assert split_model_id("ollama/gemma4") == ("ollama", "gemma4")


def test_ollama_discovery_uses_installed_models_endpoint() -> None:
    assert ollama_tags_url("http://ollama:11434/v1/") == "http://ollama:11434/api/tags"
    assert (
        ollama_tags_url("http://olamma.tutkowski.com/api/generate")
        == "http://olamma.tutkowski.com/api/tags"
    )
    assert (
        ollama_openai_base_url("http://olamma.tutkowski.com/api/generate")
        == "http://olamma.tutkowski.com/v1/"
    )
    assert installed_ollama_models(
        {"models": [{"name": "gemma4:latest"}, {"model": "qwen3:8b"}]}
    ) == ["gemma4:latest", "qwen3:8b"]


def test_capabilities_describe_provider_and_configuration() -> None:
    settings = provider_settings()
    models = get_capabilities(settings, ModelRegistry(settings))["models"]
    assert [(model["provider"], model["configured"]) for model in models] == [
        ("openai", True),
        ("gemini", True),
        ("ollama", True),
    ]
    assert models[1]["label"] == "gemini-3.6-flash"
    assert models[2]["label"] == "gemma4"


@pytest.mark.asyncio
async def test_discovery_prefixes_installed_ollama_models() -> None:
    settings = provider_settings().model_copy(update={"model_discovery_enabled": True})
    registry = ModelRegistry(settings)
    registry._query_openai = AsyncMock(  # type: ignore[method-assign]
        return_value=["gpt-5.6", "gpt-5.6-terra"]
    )
    registry._query_gemini = AsyncMock(  # type: ignore[method-assign]
        return_value=["gemini-3.6-flash"]
    )
    registry._query_ollama = AsyncMock(  # type: ignore[method-assign]
        return_value=["gemma4:latest"]
    )

    await registry.refresh(force=True)

    assert registry.model_ids == {
        "gpt-5.6",
        "gpt-5.6-terra",
        "gemini/gemini-3.6-flash",
        "ollama/gemma4:latest",
    }

    registry._query_ollama = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("temporary outage")
    )
    await registry.refresh(force=True)
    assert "ollama/gemma4:latest" in registry.model_ids
    ollama_status = next(
        status for status in registry.provider_statuses if status["provider"] == "ollama"
    )
    assert ollama_status["error"] == "RuntimeError: provider query failed"


@pytest.mark.asyncio
async def test_runner_builds_provider_specific_models() -> None:
    runner = OpenAIAgentRunner(provider_settings())

    openai_model, openai_client = runner._model("gpt-5.6")
    assert openai_model == "gpt-5.6"
    assert openai_client is None

    gemini_model, gemini_client = runner._model("gemini/gemini-3.6-flash")
    assert gemini_model.model == "gemini-3.6-flash"
    assert str(gemini_client.base_url) == (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    await gemini_client.close()

    ollama_model, ollama_client = runner._model("ollama/gemma4")
    assert ollama_model.model == "gemma4"
    assert str(ollama_client.base_url) == "http://ollama:11434/v1/"
    await ollama_client.close()
