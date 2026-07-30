"""The single module every agent node goes through for LLM calls — per the
top-level README's "swappable via .env/config (provider + model name)
through a single llm_client module" requirement. `LLMClient.call_tool` is
the entire interface every node (router/planner/retriever/answerer) uses,
so switching `LLM_PROVIDER` in .env is enough — no node logic changes.
"""
import json
from typing import Any, Protocol

from config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_PROVIDER, OPENAI_API_KEY


class _Provider(Protocol):
    async def call_tool(self, system: str, user_message: str, tool: dict[str, Any]) -> dict[str, Any]: ...


class _AnthropicProvider:
    def __init__(self):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def call_tool(self, system: str, user_message: str, tool: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        for block in response.content:
            if block.type == "tool_use":
                return block.input
        raise RuntimeError(f"model did not call {tool['name']!r}")


class _OpenAIProvider:
    """Anthropic's `{name, description, input_schema}` tool shape (what
    every node's tool dict is written in) gets converted to OpenAI's
    `{"type": "function", "function": {name, description, parameters}}`
    shape here, so router.py/planner.py/retriever.py/answerer.py don't
    need two versions of their tool schemas.
    """

    def __init__(self):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def call_tool(self, system: str, user_message: str, tool: dict[str, Any]) -> dict[str, Any]:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        response = await self._client.chat.completions.create(
            model=LLM_MODEL,
            max_completion_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            tools=[openai_tool],
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
        )
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            raise RuntimeError(f"model did not call {tool['name']!r}")
        return json.loads(tool_calls[0].function.arguments)


_PROVIDERS = {"anthropic": _AnthropicProvider, "openai": _OpenAIProvider}


class LLMClient:
    def __init__(self):
        provider_cls = _PROVIDERS.get(LLM_PROVIDER)
        if provider_cls is None:
            raise ValueError(f"unknown LLM_PROVIDER: {LLM_PROVIDER!r} (expected one of {list(_PROVIDERS)})")
        self._provider: _Provider = provider_cls()

    async def call_tool(self, system: str, user_message: str, tool: dict[str, Any]) -> dict[str, Any]:
        """Send one message, forcing the model to respond via `tool`, and
        return its parsed input. Nodes use this instead of free text so
        their output is always valid, schema-shaped JSON."""
        return await self._provider.call_tool(system, user_message, tool)
