from typing import Any

import pytest

from app.agents.orchestrator import Orchestrator
from app.agents.runner import AgentResult
from app.schemas.api import ParticipantConfig, ReviewVerdict, RunOptions


class FakeRunner:
    def __init__(self, outputs: dict[str, list[Any]]) -> None:
        self.outputs = {key: list(value) for key, value in outputs.items()}
        self.calls: list[tuple[str, str]] = []

    async def run_text(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult:
        self.calls.append((participant.id, prompt))
        return AgentResult(self.outputs[participant.id].pop(0), {})

    async def run_structured(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        output_type: type[ReviewVerdict],
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult:
        self.calls.append((participant.id, prompt))
        return AgentResult(self.outputs[participant.id].pop(0), {})


def participant(identifier: str, role: str) -> ParticipantConfig:
    return ParticipantConfig(
        id=identifier,
        role=role,  # type: ignore[arg-type]
        model_id="test-model",
        reasoning_effort="medium",
    )


@pytest.mark.asyncio
async def test_judge_retries_rejected_answer() -> None:
    runner = FakeRunner(
        {
            "primary": ["wrong answer", "corrected answer"],
            "judge": [
                ReviewVerdict(
                    verdict="incorrect",
                    summary="Wrong arithmetic",
                    issues=["Two plus two is not five"],
                    retry_instructions=["Correct the arithmetic"],
                ),
                ReviewVerdict(verdict="correct", summary="Correct"),
            ],
        }
    )
    recorded: list[dict[str, Any]] = []

    async def record(**kwargs: Any) -> None:
        recorded.append(kwargs)

    config = RunOptions(
        execution_mode="judge",
        model_id="test-model",
        max_review_attempts=3,
        participants=[participant("primary", "primary"), participant("judge", "judge")],
    )
    result = await Orchestrator(runner, record).execute(
        "What is 2+2?", "assistant: Earlier context", config
    )
    assert result.status == "succeeded"
    assert result.output == "corrected answer"
    assert "Correct the arithmetic" in runner.calls[2][1]
    assert "Earlier context" in runner.calls[1][1]
    assert [step["review_attempt"] for step in recorded] == [1, 1, 2, 2]


@pytest.mark.asyncio
async def test_jury_requires_strict_majority_and_retries() -> None:
    incorrect = ReviewVerdict(
        verdict="incorrect", summary="Incorrect", retry_instructions=["Fix it"]
    )
    correct = ReviewVerdict(verdict="correct", summary="Correct")
    runner = FakeRunner(
        {
            "primary": ["first", "second"],
            "juror_1": [incorrect, correct],
            "juror_2": [incorrect, correct],
            "juror_3": [correct, correct],
        }
    )

    async def record(**kwargs: Any) -> None:
        return None

    config = RunOptions(
        execution_mode="jury",
        model_id="test-model",
        max_review_attempts=2,
        participants=[
            participant("primary", "primary"),
            participant("juror_1", "juror"),
            participant("juror_2", "juror"),
            participant("juror_3", "juror"),
        ],
    )
    result = await Orchestrator(runner, record).execute("Question", "", config)
    assert result.status == "succeeded"
    assert result.output == "second"


@pytest.mark.asyncio
async def test_review_exhaustion_does_not_publish_candidate() -> None:
    runner = FakeRunner(
        {
            "primary": ["wrong", "still wrong"],
            "judge": [
                ReviewVerdict(verdict="incorrect", summary="No", issues=["wrong"]),
                ReviewVerdict(verdict="incorrect", summary="Still no", issues=["wrong"]),
            ],
        }
    )

    async def record(**kwargs: Any) -> None:
        return None

    config = RunOptions(
        execution_mode="judge",
        model_id="test-model",
        max_review_attempts=2,
        participants=[participant("primary", "primary"), participant("judge", "judge")],
    )
    result = await Orchestrator(runner, record).execute("Question", "", config)
    assert result.status == "review_failed"
    assert result.output is None


@pytest.mark.asyncio
async def test_debate_judge_remediates_and_is_reviewed_again() -> None:
    runner = FakeRunner(
        {
            "debater_1": ["opening A", "rebuttal A", "fix A"],
            "debater_2": ["opening B", "rebuttal B", "fix B"],
            "moderator": ["candidate one", "candidate two"],
            "judge": [
                ReviewVerdict(verdict="incorrect", summary="Missing fact", issues=["Add fact X"]),
                ReviewVerdict(verdict="correct", summary="Correct"),
            ],
        }
    )
    rounds: list[int | None] = []

    async def record(**kwargs: Any) -> None:
        rounds.append(kwargs["debate_round"])

    config = RunOptions(
        execution_mode="debate_judge",
        model_id="test-model",
        debate_participants=2,
        debate_rounds=2,
        max_review_attempts=2,
        participants=[
            participant("debater_1", "debater"),
            participant("debater_2", "debater"),
            participant("moderator", "moderator"),
            participant("judge", "judge"),
        ],
    )
    result = await Orchestrator(runner, record).execute("Question", "", config)
    assert result.status == "succeeded"
    assert result.output == "candidate two"
    assert any("Add fact X" in prompt for _name, prompt in runner.calls)
    assert 3 in rounds


@pytest.mark.asyncio
async def test_debate_jury_remediates_until_majority_passes() -> None:
    incorrect = ReviewVerdict(
        verdict="incorrect", summary="Missing detail", retry_instructions=["Add detail Y"]
    )
    correct = ReviewVerdict(verdict="correct", summary="Correct")
    runner = FakeRunner(
        {
            "debater_1": ["opening A", "rebuttal A", "fix A"],
            "debater_2": ["opening B", "rebuttal B", "fix B"],
            "moderator": ["candidate one", "candidate two"],
            "juror_1": [incorrect, correct],
            "juror_2": [incorrect, correct],
            "juror_3": [correct, incorrect],
        }
    )

    async def record(**kwargs: Any) -> None:
        return None

    config = RunOptions(
        execution_mode="debate_jury",
        model_id="test-model",
        debate_participants=2,
        debate_rounds=2,
        jury_size=3,
        max_review_attempts=2,
        participants=[
            participant("debater_1", "debater"),
            participant("debater_2", "debater"),
            participant("moderator", "moderator"),
            participant("juror_1", "juror"),
            participant("juror_2", "juror"),
            participant("juror_3", "juror"),
        ],
    )
    result = await Orchestrator(runner, record).execute("Question", "", config)
    assert result.status == "succeeded"
    assert result.output == "candidate two"
    assert any("Add detail Y" in prompt for _name, prompt in runner.calls)
