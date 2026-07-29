"""Router node — extracts task + constraints (budget, brand, material) and
safety flags from the transcript, via forced tool-calling for structured
output. System prompt: prompts/router_system.md (also the disclosure copy —
this file reads it directly, so there's one source of truth).
"""
from config import PROMPTS_DIR
from llm_client import LLMClient
from state import AgentState

_SYSTEM_PROMPT = (PROMPTS_DIR / "router_system.md").read_text()

_EMIT_INTENT_TOOL = {
    "name": "emit_intent",
    "description": "Return the structured intent extracted from the user's transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "one-line paraphrase of what the user wants",
            },
            "constraints": {
                "type": "object",
                "properties": {
                    "max_price": {"type": ["number", "null"]},
                    "brand": {"type": ["string", "null"]},
                    "material": {"type": ["string", "null"]},
                },
                "required": ["max_price", "brand", "material"],
            },
            "wants_live_data": {
                "type": "boolean",
                "description": 'true if the user is asking about current price, availability, "now", or "latest"',
            },
            "safety_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "chemical/product-safety concerns raised by the request; empty if none",
            },
        },
        "required": ["task", "constraints", "wants_live_data", "safety_flags"],
    },
}


async def run(state: AgentState, llm: LLMClient) -> dict:
    intent = await llm.call_tool(
        system=_SYSTEM_PROMPT,
        user_message=state["transcript"],
        tool=_EMIT_INTENT_TOOL,
    )
    trace = state.get("trace", [])
    trace.append(f"router: {intent['task']!r}")
    return {"intent": intent, "trace": trace}
