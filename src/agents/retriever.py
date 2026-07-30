"""Retriever node — queries the private catalog via rag.search (scoped to
the Router's inferred category), falls back to web.search if that isn't
genuinely satisfactory (or the plan explicitly wants live data), and
reconciles the two by title similarity. Talks to the MCP tool server
(src/mcp_server) for both searches, plus one small LLM call to judge
relevance (see below) — despite the "Retriever" name being from a
non-LLM-node era of this file, that judgment call is unavoidable.

Routing behavior:
0. If the Router flagged this as a pure follow-up selection over already-
   shown results ("the cheapest one"), skip straight to reusing the
   previous turn's evidence — no rag.search/web.search call at all. See
   the `is_followup_on_existing_results` branch below.
1. rag.search, scoped to intent.category (if any) and constraints.
2. Relevance check (see prompts/retriever_system.md): do any of the
   private hits actually match the *specific product type* requested, not
   just the general topic/category? Cosine similarity alone can't tell
   the difference — see that prompt file for the concrete failure case
   that motivated this (a bolster pillow and bed sheets scored higher
   than some genuine matches elsewhere do, for a "throw pillow covers"
   query, because the embedding model tracks topical overlap, not product
   type). A plain "did we get zero rows back" check missed exactly this
   case, which is why this is a real LLM judgment, not a score threshold.
3. If private search wasn't satisfactory by that judgment — OR the plan
   wants live data — also try web.search.
4. If *neither* private nor web search finds anything, evidence is empty
   (or, if private search returned only rejected candidates, empty of
   anything the relevance check approved): that's the only failure state,
   handled by the Answerer's prompt (say so honestly) rather than here.
"""
import difflib
import json
from typing import Optional

from config import PROMPTS_DIR
from llm_client import LLMClient
from mcp_client import MCPToolClient
from state import AgentState

_TITLE_MATCH_THRESHOLD = 0.6

_RELEVANCE_SYSTEM_PROMPT = (PROMPTS_DIR / "retriever_system.md").read_text()

_EMIT_RELEVANCE_TOOL = {
    "name": "emit_relevance",
    "description": "Judge whether any candidate private-catalog result genuinely satisfies the request.",
    "input_schema": {
        "type": "object",
        "properties": {
            "satisfactory": {
                "type": "boolean",
                "description": "true only if at least one candidate is the actual product type requested",
            },
            "reason": {"type": "string", "description": "one short sentence, for debugging"},
        },
        "required": ["satisfactory", "reason"],
    },
}


def _titles_match(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _TITLE_MATCH_THRESHOLD


async def _judge_relevance(llm: LLMClient, task: str, hits: list[dict]) -> tuple[bool, str]:
    if not hits:
        return False, "no private hits at all"
    payload = {"request": task, "candidates": [h["title"] for h in hits]}
    result = await llm.call_tool(
        system=_RELEVANCE_SYSTEM_PROMPT,
        user_message=json.dumps(payload),
        tool=_EMIT_RELEVANCE_TOOL,
    )
    return result["satisfactory"], result["reason"]


async def run(state: AgentState, mcp_client: MCPToolClient, llm: LLMClient) -> dict:
    intent = state["intent"]
    plan = state["plan"]
    constraints = intent.get("constraints", {})
    category = intent.get("category")

    # Pure follow-up selection over what's already on screen ("the cheapest
    # one") — the Router already resolved this (see router_system.md) and
    # there's nothing a fresh rag.search/web.search would improve: reusing
    # the exact evidence the user already saw is more correct than
    # re-querying, since neither search is guaranteed to return the same
    # results twice (rag.search's underlying data doesn't change turn to
    # turn, but web.search's does, and Shopping search is documented
    # elsewhere in this codebase as flaky even for identical queries).
    if intent.get("is_followup_on_existing_results"):
        history = state.get("history") or []
        prior_evidence = history[-1]["evidence"] if history else []
        trace = state.get("trace", [])
        trace.append(f"retriever: reused {len(prior_evidence)} evidence items from the previous turn (follow-up)")
        return {"evidence": prior_evidence, "trace": trace}

    private_hits: list[dict] = await mcp_client.rag_search(
        intent["task"],
        max_price=constraints.get("max_price"),
        brand=constraints.get("brand"),
        category=category,
        k=5,
    )
    for hit in private_hits:
        hit["source"] = "private"

    private_satisfactory, relevance_reason = await _judge_relevance(llm, intent["task"], private_hits)
    wants_live = "live" in plan.get("sources", [])
    need_web = not private_satisfactory or wants_live

    # Rejected private hits don't count as evidence — the relevance check
    # already determined they don't answer the request, so keeping them
    # around would let a known mismatch slip into the Answerer's context
    # (caught by src/eval: a "no evidence anywhere" case still had 6 private
    # evidence items — rejected candidates that were never actually removed).
    # Satisfactory private hits are kept regardless of whether we also fetch
    # live data (wants_live_data queries want both, for current-price
    # comparison against a genuinely good private match).
    evidence: list[dict] = list(private_hits) if private_satisfactory else []

    if need_web:
        live_hits: list[dict] = await mcp_client.web_search(intent["task"], k=5)
        for hit in live_hits:
            hit["source"] = "live"
            reconciled: Optional[dict] = next(
                (p for p in private_hits if private_satisfactory and _titles_match(p["title"], hit.get("title") or "")),
                None,
            )
            if reconciled is not None:
                reconciled.setdefault("live_matches", []).append(hit)
            else:
                evidence.append(hit)

    trace = state.get("trace", [])
    reason = "plan wants live data" if wants_live else relevance_reason if need_web else None
    trace_msg = f"retriever: {len(evidence)} evidence items (category={category!r}"
    trace_msg += f", web fallback: {reason})" if need_web else ")"
    trace.append(trace_msg)
    return {"evidence": evidence, "trace": trace}
