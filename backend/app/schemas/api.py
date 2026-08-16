from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParticipantConfig(BaseModel):
    id: str
    role: Literal["primary", "judge", "juror", "debater", "moderator"]
    model_id: str
    reasoning_effort: Literal["low", "medium", "high"] = "medium"


class RunOptions(BaseModel):
    execution_mode: Literal["single", "judge", "jury", "debate", "debate_judge", "debate_jury"] = (
        "single"
    )
    model_id: str | None = None
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    participants: list[ParticipantConfig] = Field(default_factory=list)
    enabled_tools: list[str] = Field(default_factory=list)
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    jury_size: int = Field(default=3, ge=3)
    debate_participants: int = Field(default=3, ge=2)
    debate_rounds: int = Field(default=2, ge=2)
    max_review_attempts: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def validate_jury_size(self) -> "RunOptions":
        if self.execution_mode in {"jury", "debate_jury"} and self.jury_size % 2 == 0:
            raise ValueError("jury_size must be odd")
        return self


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)
    defaults: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    defaults: dict[str, Any] | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    defaults: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    run_id: str | None
    role: str
    content: str
    created_at: datetime


class RunCreate(RunOptions):
    prompt: str = Field(min_length=1, max_length=100_000)


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    participant_id: str
    role: str
    model_id: str
    reasoning_effort: str
    review_attempt: int
    debate_round: int | None
    status: str
    output: str | None
    verdict: dict[str, Any] | None
    usage: dict[str, Any]
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str | None
    schedule_id: str | None
    source_type: str
    status: str
    prompt: str
    config: dict[str, Any]
    final_output: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[RunStepOut] = Field(default_factory=list)


class RunAccepted(BaseModel):
    id: str
    status: str


class ReviewVerdict(BaseModel):
    verdict: Literal["correct", "incorrect"]
    summary: str
    issues: list[str] = Field(default_factory=list)
    retry_instructions: list[str] = Field(default_factory=list)


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=100_000)
    enabled: bool = True
    schedule_type: Literal["once", "interval", "cron"]
    schedule_config: dict[str, Any]
    timezone: str
    conversation_id: str | None = None
    run_config: RunOptions


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    prompt: str | None = Field(default=None, min_length=1, max_length=100_000)
    enabled: bool | None = None
    schedule_type: Literal["once", "interval", "cron"] | None = None
    schedule_config: dict[str, Any] | None = None
    timezone: str | None = None
    conversation_id: str | None = None
    run_config: RunOptions | None = None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    prompt: str
    enabled: bool
    schedule_type: str
    schedule_config: dict[str, Any]
    timezone: str
    conversation_id: str | None
    run_config: dict[str, Any]
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
