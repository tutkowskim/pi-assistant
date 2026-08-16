import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agents.runner import AgentResult, AgentRunner
from app.schemas.api import ParticipantConfig, ReviewVerdict, RunOptions

StepRecorder = Callable[..., Awaitable[None]]

ANSWER_INSTRUCTIONS = """You are the answer-producing personal assistant.
Answer the user's request accurately, directly, and completely. Use enabled tools when they
provide facts or calculations. When retry feedback is supplied, correct every listed defect and
return a fresh complete answer. Do not mention hidden reasoning or the review machinery.
When the child-agent tool is available, use it aggressively to split broad requests into focused,
self-contained parallel branches and keep unrelated context out of this chat. Give each child all
context it needs. Do not delegate trivial work or tasks that must be completed serially.
"""

REVIEW_INSTRUCTIONS = """You are an independent correctness reviewer. Evaluate the candidate
against the original request and available evidence. Check factual correctness, directness,
completeness, internal consistency, tool evidence, and whether it answers the request. Return the
required structured verdict. Do not rewrite the answer. Mark it correct only if no material defect
remains. Keep the public summary and issue list concise; never reveal hidden chain-of-thought.
"""

DEBATER_INSTRUCTIONS = """You are one participant in a public, concise debate. State claims,
supporting evidence, uncertainty, and your proposed answer. In later rounds, identify and challenge
specific competing claims, then say clearly whether your position changed. Do not reveal private
chain-of-thought; provide only the argument intended for the shared transcript.
When the child-agent tool is available, delegate independent evidence-gathering branches early.
"""

MODERATOR_INSTRUCTIONS = """You are the debate moderator. Synthesize the strongest supported
claims into one accurate, direct, complete candidate answer. Resolve disagreements explicitly from
the public evidence. Return only the candidate answer, not private reasoning or process commentary.
"""

PLAN_INSTRUCTIONS = """You are a planning agent. Produce a concrete, ordered plan that fully
addresses the user's request. Identify dependencies, verification, risks, and clear completion
criteria. Plan only: do not perform the work, call tools, or claim that any step is complete. When
review feedback is supplied, revise the entire plan and address every listed defect. Return only the
plan intended for the executor; never expose hidden chain-of-thought.
"""

PLAN_REVIEW_INSTRUCTIONS = """You are an independent plan reviewer. Evaluate whether the proposed
plan is correct, complete, safe, efficient, executable, and faithful to the original request. Check
that dependencies and verification are explicit and that the plan does not prematurely execute the
task. Return the required structured verdict. Do not execute or rewrite the plan. Mark it correct
only if no material defect remains; never reveal hidden chain-of-thought.
"""

EXECUTOR_INSTRUCTIONS = """You are the execution agent. Execute the approved plan to satisfy the
original request, adapting only when reality requires it. Use enabled tools and verify the result.
Return the complete final answer, not a plan or process transcript. When the child-agent tool is
available, use it aggressively for independent branches or context-heavy subtasks, giving each child
all required context. Do not delegate trivial or tightly serial work.
"""


@dataclass
class OrchestrationResult:
    status: str
    output: str | None
    error_code: str | None = None
    error_message: str | None = None


class Orchestrator:
    def __init__(self, runner: AgentRunner, record_step: StepRecorder) -> None:
        self.runner = runner
        self.record_step = record_step

    @staticmethod
    def _participant(config: RunOptions, participant_id: str) -> ParticipantConfig:
        for participant in config.participants:
            if participant.id == participant_id:
                return participant
        raise ValueError(f"Missing participant: {participant_id}")

    async def _record(
        self,
        participant: ParticipantConfig,
        result: AgentResult,
        attempt: int,
        debate_round: int | None = None,
        verdict: ReviewVerdict | None = None,
    ) -> None:
        await self.record_step(
            participant=participant,
            output=None if verdict else str(result.output),
            verdict=None if verdict is None else verdict.model_dump(),
            usage=result.usage,
            review_attempt=attempt,
            debate_round=debate_round,
        )

    async def _answer(
        self,
        prompt: str,
        history: str,
        config: RunOptions,
        attempt: int,
        feedback: list[str],
    ) -> str:
        participant = self._participant(config, "primary")
        retry = ""
        if feedback:
            retry = (
                "\nThe previous candidate was rejected. Correct all of these defects:\n- "
                + "\n- ".join(feedback)
            )
        full_prompt = f"Conversation context:\n{history}\n\nUser request:\n{prompt}{retry}"
        result = await self.runner.run_text(
            participant,
            ANSWER_INSTRUCTIONS,
            full_prompt,
            config.enabled_tools,
            config.enabled_mcp_servers,
        )
        await self._record(participant, result, attempt)
        return str(result.output)

    async def _plan(
        self,
        prompt: str,
        history: str,
        config: RunOptions,
        attempt: int,
        previous_plan: str,
        feedback: list[str],
    ) -> str:
        participant = self._participant(config, "planner")
        retry = ""
        if feedback:
            retry = (
                f"\n\nRejected prior plan:\n{previous_plan}\n\nCorrect all reviewer defects:\n- "
                + "\n- ".join(feedback)
            )
        result = await self.runner.run_text(
            participant,
            PLAN_INSTRUCTIONS,
            f"Conversation context:\n{history}\n\nUser request:\n{prompt}{retry}",
            [],
            [],
        )
        await self._record(participant, result, attempt)
        return str(result.output)

    async def _review_plan(
        self,
        prompt: str,
        history: str,
        plan: str,
        config: RunOptions,
        attempt: int,
    ) -> ReviewVerdict:
        reviewer = self._participant(config, "plan_reviewer")
        result = await self.runner.run_structured(
            reviewer,
            PLAN_REVIEW_INSTRUCTIONS,
            f"Conversation context:\n{history}\n\nOriginal request:\n{prompt}\n\n"
            f"Proposed plan:\n{plan}\n\nReturn the plan-review verdict.",
            ReviewVerdict,
            [],
            [],
        )
        verdict: ReviewVerdict = result.output
        await self._record(reviewer, result, attempt, verdict=verdict)
        return verdict

    async def _execute_plan(
        self,
        prompt: str,
        history: str,
        plan: str,
        config: RunOptions,
        attempt: int,
    ) -> str:
        executor = self._participant(config, "executor")
        result = await self.runner.run_text(
            executor,
            EXECUTOR_INSTRUCTIONS,
            f"Conversation context:\n{history}\n\nOriginal request:\n{prompt}\n\n"
            f"Approved plan:\n{plan}\n\nExecute the approved plan now.",
            config.enabled_tools,
            config.enabled_mcp_servers,
        )
        await self._record(executor, result, attempt)
        return str(result.output)

    async def _review_one(
        self,
        reviewer: ParticipantConfig,
        prompt: str,
        history: str,
        candidate: str,
        config: RunOptions,
        attempt: int,
    ) -> ReviewVerdict:
        review_prompt = (
            f"Conversation context:\n{history}\n\nOriginal request:\n{prompt}\n\n"
            f"Candidate answer:\n{candidate}\n\n"
            "Return the correctness verdict."
        )
        result = await self.runner.run_structured(
            reviewer,
            REVIEW_INSTRUCTIONS,
            review_prompt,
            ReviewVerdict,
            [tool_id for tool_id in config.enabled_tools if tool_id != "spawn_child_agent"],
            config.enabled_mcp_servers,
        )
        verdict: ReviewVerdict = result.output
        await self._record(reviewer, result, attempt, verdict=verdict)
        return verdict

    async def _review(
        self,
        prompt: str,
        history: str,
        candidate: str,
        config: RunOptions,
        attempt: int,
    ) -> tuple[bool, list[str]]:
        if config.execution_mode in {"judge", "debate_judge"}:
            verdict = await self._review_one(
                self._participant(config, "judge"), prompt, history, candidate, config, attempt
            )
            feedback = verdict.retry_instructions or verdict.issues
            return verdict.verdict == "correct", feedback

        jurors = [participant for participant in config.participants if participant.role == "juror"]
        results = await asyncio.gather(
            *[
                self._review_one(juror, prompt, history, candidate, config, attempt)
                for juror in jurors
            ],
            return_exceptions=True,
        )
        valid = [result for result in results if isinstance(result, ReviewVerdict)]
        required = len(jurors) // 2 + 1
        if len(valid) < required:
            raise RuntimeError("Jury quorum was lost")
        passes = sum(verdict.verdict == "correct" for verdict in valid)
        jury_feedback: list[str] = []
        for verdict in valid:
            if verdict.verdict == "incorrect":
                jury_feedback.extend(verdict.retry_instructions or verdict.issues)
        return passes >= required, list(dict.fromkeys(jury_feedback))

    async def _debate_initial(
        self, prompt: str, history: str, config: RunOptions, attempt: int
    ) -> tuple[str, str]:
        debaters = [p for p in config.participants if p.role == "debater"]
        transcript: list[dict[str, Any]] = []
        openings = await asyncio.gather(
            *[
                self.runner.run_text(
                    debater,
                    DEBATER_INSTRUCTIONS,
                    f"Conversation context:\n{history}\n\nUser request:\n{prompt}\n\n"
                    "Give your independent opening position.",
                    config.enabled_tools,
                    config.enabled_mcp_servers,
                )
                for debater in debaters
            ]
        )
        for debater, result in zip(debaters, openings, strict=True):
            await self._record(debater, result, attempt, debate_round=1)
            transcript.append({"round": 1, "speaker": debater.id, "argument": result.output})

        for round_number in range(2, config.debate_rounds + 1):
            shared = json.dumps(transcript, ensure_ascii=False)
            rebuttals = await asyncio.gather(
                *[
                    self.runner.run_text(
                        debater,
                        DEBATER_INSTRUCTIONS,
                        f"User request:\n{prompt}\n\nPublic transcript:\n{shared}\n\n"
                        "Rebut specific competing claims and provide your revised position.",
                        config.enabled_tools,
                        config.enabled_mcp_servers,
                    )
                    for debater in debaters
                ]
            )
            for debater, result in zip(debaters, rebuttals, strict=True):
                await self._record(debater, result, attempt, debate_round=round_number)
                transcript.append(
                    {"round": round_number, "speaker": debater.id, "argument": result.output}
                )

        candidate = await self._moderate(prompt, transcript, config, attempt, config.debate_rounds)
        return candidate, json.dumps(transcript, ensure_ascii=False)

    async def _moderate(
        self,
        prompt: str,
        transcript: list[dict[str, Any]],
        config: RunOptions,
        attempt: int,
        debate_round: int,
    ) -> str:
        moderator = self._participant(config, "moderator")
        result = await self.runner.run_text(
            moderator,
            MODERATOR_INSTRUCTIONS,
            f"User request:\n{prompt}\n\nPublic debate transcript:\n"
            f"{json.dumps(transcript, ensure_ascii=False)}",
            config.enabled_tools,
            config.enabled_mcp_servers,
        )
        await self._record(moderator, result, attempt, debate_round=debate_round)
        return str(result.output)

    async def _debate_remediation(
        self,
        prompt: str,
        prior_transcript: str,
        prior_candidate: str,
        feedback: list[str],
        config: RunOptions,
        attempt: int,
    ) -> tuple[str, str]:
        debaters = [p for p in config.participants if p.role == "debater"]
        round_number = config.debate_rounds + attempt - 1
        remediation = await asyncio.gather(
            *[
                self.runner.run_text(
                    debater,
                    DEBATER_INSTRUCTIONS,
                    f"User request:\n{prompt}\n\nPrior transcript:\n{prior_transcript}\n\n"
                    f"Rejected candidate:\n{prior_candidate}\n\nReviewer defects:\n- "
                    + "\n- ".join(feedback)
                    + "\n\nProvide a correction argument addressing every defect.",
                    config.enabled_tools,
                    config.enabled_mcp_servers,
                )
                for debater in debaters
            ]
        )
        transcript = json.loads(prior_transcript)
        for debater, result in zip(debaters, remediation, strict=True):
            await self._record(debater, result, attempt, debate_round=round_number)
            transcript.append(
                {"round": round_number, "speaker": debater.id, "argument": result.output}
            )
        candidate = await self._moderate(prompt, transcript, config, attempt, round_number)
        return candidate, json.dumps(transcript, ensure_ascii=False)

    async def execute(self, prompt: str, history: str, config: RunOptions) -> OrchestrationResult:
        if config.execution_mode == "single":
            return OrchestrationResult(
                "succeeded", await self._answer(prompt, history, config, 1, [])
            )

        if config.execution_mode == "plan":
            plan_feedback: list[str] = []
            plan = ""
            for attempt in range(1, config.max_review_attempts + 1):
                plan = await self._plan(prompt, history, config, attempt, plan, plan_feedback)
                verdict = await self._review_plan(prompt, history, plan, config, attempt)
                if verdict.verdict == "correct":
                    output = await self._execute_plan(prompt, history, plan, config, attempt)
                    return OrchestrationResult("succeeded", output)
                plan_feedback = verdict.retry_instructions or verdict.issues
            return OrchestrationResult(
                "review_failed",
                None,
                "review_failed",
                "No plan passed review after "
                f"{config.max_review_attempts} attempts; execution was not started.",
            )

        if config.execution_mode == "debate":
            candidate, _ = await self._debate_initial(prompt, history, config, 1)
            return OrchestrationResult("succeeded", candidate)

        if config.execution_mode in {"judge", "jury"}:
            feedback: list[str] = []
            last_candidate = ""
            for attempt in range(1, config.max_review_attempts + 1):
                last_candidate = await self._answer(prompt, history, config, attempt, feedback)
                passed, feedback = await self._review(
                    prompt, history, last_candidate, config, attempt
                )
                if passed:
                    return OrchestrationResult("succeeded", last_candidate)
            return OrchestrationResult(
                "review_failed",
                None,
                "review_failed",
                "No candidate passed correctness review after "
                f"{config.max_review_attempts} attempts.",
            )

        candidate, transcript = await self._debate_initial(prompt, history, config, 1)
        feedback = []
        for attempt in range(1, config.max_review_attempts + 1):
            if attempt > 1:
                candidate, transcript = await self._debate_remediation(
                    prompt, transcript, candidate, feedback, config, attempt
                )
            passed, feedback = await self._review(prompt, history, candidate, config, attempt)
            if passed:
                return OrchestrationResult("succeeded", candidate)
        return OrchestrationResult(
            "review_failed",
            None,
            "review_failed",
            f"No debate candidate passed review after {config.max_review_attempts} attempts.",
        )
