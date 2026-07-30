"""Router node — extracts task + constraints (budget, brand, material) and
safety flags from the transcript, via forced tool-calling for structured
output. System prompt: prompts/router_system.md (also the disclosure copy —
this file reads it directly, so there's one source of truth).

Also resolves follow-ups against `state["history"]` (prior turns in this
conversation): ellipsis like "what about under $10" needs the previous
turn's product type filled back in, and pure selections over what's
already on screen ("the cheapest one", "the second option") need
`is_followup_on_existing_results=true` so the Retriever can skip a fresh
search and just re-rank the evidence already shown, rather than
re-querying and risking a subtly different result set (rag.search/live
search aren't guaranteed to return byte-identical results turn to turn).
"""
import json

from config import PROMPTS_DIR
from llm_client import LLMClient
from state import AgentState

_SYSTEM_PROMPT = (PROMPTS_DIR / "router_system.md").read_text()

# Must match the catalog's real category_top_level values (see
# src/ingestion/README.md#category-organization) — kept as a plain string
# (not a hard `enum`) so a stale/mismatched value degrades gracefully
# (rag.search just returns zero private hits, which is exactly the
# retriever's trigger to fall back to web.search) rather than making the
# whole tool call fail schema validation.
_KNOWN_CATEGORIES = [
    "Toys & Games", "Home & Kitchen", "Clothing, Shoes & Jewelry",
    "Sports & Outdoors", "Baby Products", "Arts, Crafts & Sewing",
    "Office Products", "Hobbies", "Industrial & Scientific",
    "Health & Household", "Remote & App Controlled Vehicle Parts",
    "Tools & Home Improvement", "Remote & App Controlled Vehicles & Parts",
    "Pet Supplies", "Patio, Lawn & Garden", "Grocery & Gourmet Food",
    "Beauty & Personal Care", "Automotive", "Electronics", "Video Games",
    "Musical Instruments", "Movies & TV", "Cell Phones & Accessories",
]

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
            "category": {
                "type": ["string", "null"],
                "description": (
                    "one of the catalog's known top-level categories: "
                    + ", ".join(_KNOWN_CATEGORIES)
                    + " — or null if the request doesn't clearly fit one"
                ),
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
            "is_followup_on_existing_results": {
                "type": "boolean",
                "description": (
                    "true only if this request is purely selecting/comparing/re-ranking among "
                    "products already shown in the previous turn's evidence (e.g. 'the cheapest "
                    "one', 'the second option', 'that one but tell me the link') rather than "
                    "asking for anything a fresh search could turn up new results for"
                ),
            },
        },
        "required": [
            "task", "constraints", "category", "wants_live_data",
            "safety_flags", "is_followup_on_existing_results",
        ],
    },
}


async def run(state: AgentState, llm: LLMClient) -> dict:
    history = state.get("history") or []
    user_message = state["transcript"]
    if history:
        # Compact history, not a raw dump: task/constraints/category (to resolve
        # ellipsis like "what about under $10") plus title/price/rating per
        # evidence item (to resolve selections like "the cheapest one" against
        # what was actually shown, not a re-derived guess).
        compact_history = [
            {
                "transcript": turn["transcript"],
                "intent": {k: v for k, v in turn["intent"].items() if k != "safety_flags"},
                "evidence": [
                    {k: e.get(k) for k in ("title", "price", "rating", "brand", "source")}
                    for e in turn["evidence"]
                ],
            }
            for turn in history
        ]
        user_message = json.dumps({"history": compact_history, "new_transcript": state["transcript"]})

    intent = await llm.call_tool(
        system=_SYSTEM_PROMPT,
        user_message=user_message,
        tool=_EMIT_INTENT_TOOL,
    )
    trace = state.get("trace", [])
    followup_note = " (follow-up on prior results)" if intent.get("is_followup_on_existing_results") else ""
    trace.append(f"router: {intent['task']!r} (category={intent['category']!r}){followup_note}")
    return {"intent": intent, "trace": trace}
