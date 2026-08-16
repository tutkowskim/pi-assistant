import pytest

from app.core.capabilities import participant_layout
from app.core.config import MCPServerDefinition, Settings
from app.core.model_registry import ModelRegistry
from app.schemas.api import RunOptions
from app.services.validation import resolve_run_options


def settings() -> Settings:
    return Settings(
        model_ids=["a", "b"],
        model_discovery_enabled=False,
        default_model_id="a",
        openai_api_key="test-openai-key",
        database_url="sqlite:///:memory:",
    )


def test_child_agent_tool_is_enabled_by_default() -> None:
    assert RunOptions().enabled_tools == ["spawn_child_agent"]


def test_hybrid_layouts_include_all_roles() -> None:
    judge = participant_layout("debate_judge", 3, 2)
    assert [item["id"] for item in judge] == ["debater_1", "debater_2", "moderator", "judge"]
    jury = participant_layout("debate_jury", 3, 2)
    assert [item["id"] for item in jury] == [
        "debater_1",
        "debater_2",
        "moderator",
        "juror_1",
        "juror_2",
        "juror_3",
    ]


def test_plan_layout_separates_planning_review_and_execution() -> None:
    assert participant_layout("plan", 3, 3) == [
        {"id": "planner", "role": "planner"},
        {"id": "plan_reviewer", "role": "plan_reviewer"},
        {"id": "executor", "role": "executor"},
    ]


def test_resolver_creates_individual_participants() -> None:
    configured = settings()
    resolved = resolve_run_options(
        RunOptions(execution_mode="jury", model_id="a", jury_size=3),
        configured,
        ModelRegistry(configured),
    )
    assert [participant.id for participant in resolved.participants] == [
        "primary",
        "juror_1",
        "juror_2",
        "juror_3",
    ]


def test_even_jury_is_rejected() -> None:
    with pytest.raises(ValueError, match="jury_size must be odd"):
        RunOptions(execution_mode="jury", jury_size=4)


def test_configured_mcp_server_can_be_selected() -> None:
    configured = settings().model_copy(
        update={
            "mcp_servers": [
                MCPServerDefinition(
                    id="notes",
                    label="Notes",
                    url="http://notes:9000/mcp",
                )
            ]
        }
    )
    configured = Settings.model_validate(configured.model_dump())
    resolved = resolve_run_options(
        RunOptions(model_id="a", enabled_mcp_servers=["notes"]),
        configured,
        ModelRegistry(configured),
    )
    assert resolved.enabled_mcp_servers == ["notes"]


def test_unknown_mcp_server_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown MCP server IDs"):
        configured = settings()
        resolve_run_options(
            RunOptions(model_id="a", enabled_mcp_servers=["unknown"]),
            configured,
            ModelRegistry(configured),
        )
