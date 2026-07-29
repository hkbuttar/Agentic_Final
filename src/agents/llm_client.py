"""The single module every agent node goes through for LLM calls — per the
top-level README's "swappable via .env/config (provider + model name)
through a single llm_client module" requirement. Swapping providers means
changing this file, not the node logic in router.py/planner.py/answerer.py.
"""
from typing import Any

from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL


class LLMClient:
    def __init__(self):
        self._client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def call_tool(self, system: str, user_message: str, tool: dict[str, Any]) -> dict[str, Any]:
        """Send one message, forcing the model to respond via `tool`, and
        return its parsed input. Nodes use this instead of free text so
        their output is always valid, schema-shaped JSON."""
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
