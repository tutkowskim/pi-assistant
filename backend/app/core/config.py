from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class MCPServerDefinition(BaseModel):
    id: str
    label: str
    description: str = ""
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


def split_model_id(model_id: str) -> tuple[str, str]:
    if "/" not in model_id:
        return "openai", model_id
    provider, upstream_id = model_id.split("/", 1)
    if provider not in {"gemini", "ollama"} or not upstream_id:
        raise ValueError(f"Unsupported model provider in ID: {model_id}")
    return provider, upstream_id


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", PROJECT_ROOT / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Pi Assistant"
    app_version: str = "0.1.0"
    app_data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/pi-assistant.db"
    app_timezone: str = "America/Los_Angeles"
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ollama_base_url: str = "http://olamma.tutkowski.com/v1/"
    model_discovery_enabled: bool = True
    model_refresh_seconds: int = 15
    model_ids: Annotated[list[str], NoDecode] = []
    mcp_servers: list[MCPServerDefinition] = Field(default_factory=list)
    default_model_id: str | None = None
    default_execution_mode: str = "single"
    default_reasoning_effort: str = "medium"
    max_concurrent_runs: int = 2
    max_concurrent_child_runs: int = 4
    max_child_agents_per_run: int = 8
    max_child_agent_depth: int = 2
    child_agent_api_base_url: str = "http://127.0.0.1:8000/api/v1"
    child_agent_poll_seconds: float = 0.5
    child_agent_timeout_seconds: float = 300
    python_sandbox_docker_executable: str = "docker"
    python_sandbox_image: str = "python:3.12-alpine"
    python_sandbox_timeout_seconds: int = 10
    python_sandbox_max_timeout_seconds: int = 30
    python_sandbox_start_timeout_seconds: int = 15
    python_sandbox_max_code_chars: int = 50_000
    python_sandbox_max_output_bytes: int = 64 * 1024
    max_jury_size: int = 5
    default_max_review_attempts: int = 3
    max_review_attempts: int = 5
    default_debate_participants: int = 3
    max_debate_participants: int = 5
    default_debate_rounds: int = 2
    max_debate_rounds: int = 3
    scheduler_poll_seconds: int = 15
    agents_tracing_enabled: bool = False
    log_level: str = "INFO"

    @field_validator("allowed_origins", "model_ids", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def validate_runtime(self) -> None:
        for model_id in self.model_ids:
            split_model_id(model_id)
        if not self.model_discovery_enabled and not self.model_ids:
            raise ValueError("MODEL_IDS is required when MODEL_DISCOVERY_ENABLED is false")
        if self.default_model_id and not self.model_discovery_enabled:
            if self.default_model_id not in self.model_ids:
                raise ValueError("DEFAULT_MODEL_ID must appear in MODEL_IDS")
        if self.model_refresh_seconds < 5:
            raise ValueError("MODEL_REFRESH_SECONDS must be at least 5")
        if self.max_jury_size < 3:
            raise ValueError("MAX_JURY_SIZE must be at least 3")
        if self.max_concurrent_child_runs < 1:
            raise ValueError("MAX_CONCURRENT_CHILD_RUNS must be at least 1")
        if self.max_child_agents_per_run < 1:
            raise ValueError("MAX_CHILD_AGENTS_PER_RUN must be at least 1")
        if self.max_child_agent_depth < 1:
            raise ValueError("MAX_CHILD_AGENT_DEPTH must be at least 1")
        if self.child_agent_poll_seconds <= 0 or self.child_agent_timeout_seconds <= 0:
            raise ValueError("Child-agent polling and timeout settings must be positive")
        if not self.python_sandbox_docker_executable or not self.python_sandbox_image:
            raise ValueError("Python sandbox Docker executable and image must be configured")
        if self.python_sandbox_timeout_seconds < 1:
            raise ValueError("PYTHON_SANDBOX_TIMEOUT_SECONDS must be at least 1")
        if self.python_sandbox_max_timeout_seconds < self.python_sandbox_timeout_seconds:
            raise ValueError("Python sandbox maximum timeout is below its default timeout")
        if self.python_sandbox_start_timeout_seconds < 1:
            raise ValueError("PYTHON_SANDBOX_START_TIMEOUT_SECONDS must be at least 1")
        if self.python_sandbox_max_code_chars < 1 or self.python_sandbox_max_output_bytes < 1:
            raise ValueError("Python sandbox code and output limits must be positive")
        if self.default_max_review_attempts > self.max_review_attempts:
            raise ValueError("DEFAULT_MAX_REVIEW_ATTEMPTS exceeds MAX_REVIEW_ATTEMPTS")
        if self.agents_tracing_enabled and not self.openai_api_key:
            raise ValueError("AGENTS_TRACING_ENABLED requires OPENAI_API_KEY")
        mcp_ids = [server.id for server in self.mcp_servers]
        if len(mcp_ids) != len(set(mcp_ids)):
            raise ValueError("MCP_SERVERS contains duplicate IDs")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    settings.validate_runtime()
    return settings
