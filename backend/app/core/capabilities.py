from typing import Any

from app.core.config import Settings
from app.core.model_registry import ModelRegistry

REASONING_EFFORTS = ["low", "medium", "high"]


def participant_layout(mode: str, jury_size: int, debate_participants: int) -> list[dict[str, str]]:
    layouts: dict[str, list[dict[str, str]]] = {
        "single": [{"id": "primary", "role": "primary"}],
        "judge": [
            {"id": "primary", "role": "primary"},
            {"id": "judge", "role": "judge"},
        ],
        "jury": [{"id": "primary", "role": "primary"}]
        + [{"id": f"juror_{i}", "role": "juror"} for i in range(1, jury_size + 1)],
        "debate": [
            *[{"id": f"debater_{i}", "role": "debater"} for i in range(1, debate_participants + 1)],
            {"id": "moderator", "role": "moderator"},
        ],
        "debate_judge": [
            *[{"id": f"debater_{i}", "role": "debater"} for i in range(1, debate_participants + 1)],
            {"id": "moderator", "role": "moderator"},
            {"id": "judge", "role": "judge"},
        ],
        "debate_jury": [
            *[{"id": f"debater_{i}", "role": "debater"} for i in range(1, debate_participants + 1)],
            {"id": "moderator", "role": "moderator"},
            *[{"id": f"juror_{i}", "role": "juror"} for i in range(1, jury_size + 1)],
        ],
    }
    if mode not in layouts:
        raise ValueError(f"Unknown execution mode: {mode}")
    return layouts[mode]


def get_capabilities(settings: Settings, model_registry: ModelRegistry) -> dict[str, Any]:
    models = [model.as_capability() for model in model_registry.models]
    modes = [
        {
            "id": "single",
            "label": "Single",
            "description": "One agent answers directly.",
            "reviewed": False,
        },
        {
            "id": "judge",
            "label": "Judge",
            "description": "A judge verifies the answer and requests retries when incorrect.",
            "reviewed": True,
        },
        {
            "id": "jury",
            "label": "Jury",
            "description": "A strict majority of jurors must verify the answer.",
            "reviewed": True,
        },
        {
            "id": "debate",
            "label": "Debate",
            "description": "Debaters challenge each other before a moderator synthesizes.",
            "reviewed": False,
        },
        {
            "id": "debate_judge",
            "label": "Debate + Judge",
            "description": "A judge verifies the debate synthesis and can trigger remediation.",
            "reviewed": True,
        },
        {
            "id": "debate_jury",
            "label": "Debate + Jury",
            "description": "A jury verifies the debate synthesis and can trigger remediation.",
            "reviewed": True,
        },
    ]
    return {
        "models": models,
        "execution_modes": modes,
        "reasoning_efforts": REASONING_EFFORTS,
        "tools": [
            {
                "id": "current_time",
                "label": "Current time",
                "description": "Get the current time in an IANA timezone.",
                "read_only": True,
                "unattended": True,
            },
            {
                "id": "calculator",
                "label": "Calculator",
                "description": "Safely evaluate basic arithmetic.",
                "read_only": True,
                "unattended": True,
            },
        ],
        "mcp_servers": [
            {
                "id": server.id,
                "label": server.label,
                "description": server.description,
                "transport": "streamable_http",
            }
            for server in settings.mcp_servers
        ],
        "model_providers": model_registry.provider_statuses,
        "defaults": {
            "model_id": model_registry.default_model_id or "",
            "execution_mode": settings.default_execution_mode,
            "reasoning_effort": settings.default_reasoning_effort,
            "jury_size": 3,
            "debate_participants": settings.default_debate_participants,
            "debate_rounds": settings.default_debate_rounds,
            "max_review_attempts": settings.default_max_review_attempts,
        },
        "limits": {
            "max_jury_size": settings.max_jury_size,
            "max_debate_participants": settings.max_debate_participants,
            "max_debate_rounds": settings.max_debate_rounds,
            "max_review_attempts": settings.max_review_attempts,
        },
    }
