"""Answerer/Critic node — synthesizes a concise, cited recommendation from
the evidence. Grounding is enforced in two layers: the system prompt tells
the model citations must come verbatim from evidence, and this node then
drops any citation that doesn't actually match an evidence item's doc_id/url
— so a hallucinated citation never reaches the user even if the model
ignores the instruction. System prompt: prompts/answerer_system.md.
"""
import json

from config import PROMPTS_DIR
from llm_client import LLMClient
from state import AgentState

_SYSTEM_PROMPT = (PROMPTS_DIR / "answerer_system.md").read_text()

_EMIT_ANSWER_TOOL = {
    "name": "emit_answer",
    "description": "Return the final grounded recommendation with citations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "spoken summary, <=15 seconds read aloud"},
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "doc_id": {"type": ["string", "null"]},
                        "url": {"type": ["string", "null"]},
                    },
                    "required": ["title", "doc_id", "url"],
                },
            },
        },
        "required": ["answer", "citations"],
    },
}


async def run(state: AgentState, llm: LLMClient) -> dict:
    evidence = state.get("evidence", [])
    result = await llm.call_tool(
        system=_SYSTEM_PROMPT,
        user_message=json.dumps({"intent": state["intent"], "evidence": evidence}),
        tool=_EMIT_ANSWER_TOOL,
    )

    valid_doc_ids = {e["doc_id"] for e in evidence if e.get("doc_id")}
    valid_urls = {e["url"] for e in evidence if e.get("url")}
    grounded_citations = [
        c
        for c in result["citations"]
        if (c.get("doc_id") and c["doc_id"] in valid_doc_ids)
        or (c.get("url") and c["url"] in valid_urls)
    ]

    trace = state.get("trace", [])
    trace.append(
        f"answerer: {len(grounded_citations)}/{len(result['citations'])} citations grounded"
    )
    return {"answer": result["answer"], "citations": grounded_citations, "trace": trace}
