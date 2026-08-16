from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from app.core.config import Settings, split_model_id
from app.core.model_registry import ollama_openai_base_url
from app.schemas.api import ParticipantConfig

T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentResult:
    output: Any
    usage: dict[str, Any]


class AgentRunner(Protocol):
    async def run_text(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult: ...

    async def run_structured(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        output_type: type[T],
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult: ...


class OpenAIAgentRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.agents_tracing_enabled:
            from agents import set_tracing_disabled

            set_tracing_disabled(True)

    def _tools(self, tool_ids: list[str]) -> list[Any]:
        from agents import function_tool

        from app.tools.registry import get_tool_functions

        return [function_tool(function) for function in get_tool_functions(tool_ids)]

    def _model_settings(self, effort: str) -> Any:
        from agents import ModelSettings
        from openai.types.shared import Reasoning

        return ModelSettings(reasoning=Reasoning(effort=effort))

    def _model(self, model_id: str) -> tuple[Any, Any | None]:
        from agents import OpenAIChatCompletionsModel
        from openai import AsyncOpenAI

        provider, upstream_id = split_model_id(model_id)
        if provider == "openai":
            return upstream_id, None
        if provider == "gemini":
            client = AsyncOpenAI(
                api_key=self.settings.gemini_api_key,
                base_url=self.settings.gemini_base_url,
            )
        else:
            client = AsyncOpenAI(
                api_key="ollama",
                base_url=ollama_openai_base_url(self.settings.ollama_base_url),
            )
        return OpenAIChatCompletionsModel(model=upstream_id, openai_client=client), client

    @asynccontextmanager
    async def _mcp_servers(self, server_ids: list[str]) -> AsyncIterator[list[Any]]:
        from agents.mcp import MCPServerStreamableHttp

        definitions = {server.id: server for server in self.settings.mcp_servers}
        async with AsyncExitStack() as stack:
            connected: list[Any] = []
            for server_id in server_ids:
                definition = definitions[server_id]
                server = MCPServerStreamableHttp(
                    params={
                        "url": definition.url,
                        "headers": definition.headers,
                        "timeout": 10,
                        "sse_read_timeout": 300,
                    },
                    name=definition.label,
                    cache_tools_list=True,
                )
                connected.append(await stack.enter_async_context(server))
            yield connected

    @staticmethod
    def _usage(result: Any) -> dict[str, Any]:
        context = getattr(result, "context_wrapper", None)
        usage = getattr(context, "usage", None)
        if usage is None:
            return {}
        return {
            "requests": getattr(usage, "requests", None),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    async def run_text(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult:
        from agents import Agent, Runner

        model, client = self._model(participant.model_id)
        try:
            async with self._mcp_servers(mcp_server_ids) as mcp_servers:
                agent = Agent(
                    name=participant.id,
                    instructions=instructions,
                    model=model,
                    model_settings=self._model_settings(participant.reasoning_effort),
                    tools=self._tools(tool_ids),
                    mcp_servers=mcp_servers,
                )
                result = await Runner.run(agent, prompt)
        finally:
            if client is not None:
                await client.close()
        return AgentResult(output=str(result.final_output), usage=self._usage(result))

    async def run_structured(
        self,
        participant: ParticipantConfig,
        instructions: str,
        prompt: str,
        output_type: type[T],
        tool_ids: list[str],
        mcp_server_ids: list[str],
    ) -> AgentResult:
        from agents import Agent, Runner

        model, client = self._model(participant.model_id)
        try:
            async with self._mcp_servers(mcp_server_ids) as mcp_servers:
                agent = Agent(
                    name=participant.id,
                    instructions=instructions,
                    model=model,
                    model_settings=self._model_settings(participant.reasoning_effort),
                    tools=self._tools(tool_ids),
                    mcp_servers=mcp_servers,
                    output_type=output_type,
                )
                result = await Runner.run(agent, prompt)
        finally:
            if client is not None:
                await client.close()
        output = result.final_output
        if not isinstance(output, output_type):
            output = output_type.model_validate(output)
        return AgentResult(output=output, usage=self._usage(result))
