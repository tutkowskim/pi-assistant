from app.core.capabilities import REASONING_EFFORTS, participant_layout
from app.core.config import Settings
from app.core.model_registry import ModelRegistry
from app.schemas.api import ParticipantConfig, RunOptions
from app.tools.registry import validate_tool_ids

REVIEWED_MODES = {"plan", "judge", "jury", "debate_judge", "debate_jury"}
DEBATE_MODES = {"debate", "debate_judge", "debate_jury"}
JURY_MODES = {"jury", "debate_jury"}


def resolve_run_options(
    options: RunOptions, settings: Settings, model_registry: ModelRegistry
) -> RunOptions:
    if options.model_id is None:
        options.model_id = model_registry.default_model_id
    if options.model_id is None:
        raise ValueError("No models are currently available")
    if options.model_id not in model_registry.model_ids:
        raise ValueError(f"Model is not enabled: {options.model_id}")
    if options.reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"Unsupported reasoning effort: {options.reasoning_effort}")
    if options.jury_size > settings.max_jury_size:
        raise ValueError("jury_size exceeds server limit")
    if options.execution_mode in JURY_MODES and options.jury_size % 2 == 0:
        raise ValueError("jury_size must be odd")
    if options.debate_participants > settings.max_debate_participants:
        raise ValueError("debate_participants exceeds server limit")
    if options.debate_rounds > settings.max_debate_rounds:
        raise ValueError("debate_rounds exceeds server limit")
    if options.max_review_attempts > settings.max_review_attempts:
        raise ValueError("max_review_attempts exceeds server limit")
    validate_tool_ids(options.enabled_tools)
    known_mcp_ids = {server.id for server in settings.mcp_servers}
    unknown_mcp_ids = set(options.enabled_mcp_servers) - known_mcp_ids
    if unknown_mcp_ids:
        raise ValueError(f"Unknown MCP server IDs: {sorted(unknown_mcp_ids)}")

    expected = participant_layout(
        options.execution_mode, options.jury_size, options.debate_participants
    )
    if not options.participants:
        options.participants = [
            ParticipantConfig(
                id=item["id"],
                role=item["role"],
                model_id=options.model_id,
                reasoning_effort=options.reasoning_effort,
            )
            for item in expected
        ]
    actual = [(item.id, item.role) for item in options.participants]
    expected_pairs = [(item["id"], item["role"]) for item in expected]
    if actual != expected_pairs:
        raise ValueError(f"Participants must exactly match the mode layout: {expected_pairs}")
    for participant in options.participants:
        if participant.model_id not in model_registry.model_ids:
            raise ValueError(f"Model {participant.model_id} is not enabled for {participant.id}")
        if participant.reasoning_effort not in REASONING_EFFORTS:
            raise ValueError(f"Reasoning effort is not supported for {participant.id}")
    if options.execution_mode not in REVIEWED_MODES:
        options.max_review_attempts = 1
    return options
