"""Planner node — chooses sources (private/live), fields, and comparison
criteria for the given intent. System prompt: prompts/planner_system.md.
"""
import json

from config import PROMPTS_DIR
from llm_client import LLMClient
from state import AgentState

_SYSTEM_PROMPT = (PROMPTS_DIR / "planner_system.md").read_text()

_EMIT_PLAN_TOOL = {
    "name": "emit_plan",
    "description": "Return the retrieval plan for this intent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": ["private", "live"]},
                "description": "private is always included; add live only if the intent needs current price/availability",
            },
            "fields": {"type": "array", "items": {"type": "string"}},
            "criteria": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["sources", "fields", "criteria"],
    },
}


async def run(state: AgentState, llm: LLMClient) -> dict:
    plan = await llm.call_tool(
        system=_SYSTEM_PROMPT,
        user_message=json.dumps(state["intent"]),
        tool=_EMIT_PLAN_TOOL,
    )
    if "private" not in plan["sources"]:
        plan["sources"].insert(0, "private")  # rag.search is always preferred, per README

    trace = state.get("trace", [])
    trace.append(f"planner: sources={plan['sources']}")
    return {"plan": plan, "trace": trace}
