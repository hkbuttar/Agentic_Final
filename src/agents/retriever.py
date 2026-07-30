"""Retriever node — queries the private catalog via rag.search (scoped to
the Router's inferred category), falls back to web.search if that isn't
satisfactory (or the plan explicitly wants live data), and reconciles the
two by title similarity. No LLM call here: this node only talks to the MCP
tool server (src/mcp_server).

Routing behavior:
1. rag.search, scoped to intent.category (if any) and constraints.
2. If that returns zero hits — the category+constraints combination has no
   match — OR the plan wants live data, also try web.search.
3. If *neither* private nor web search finds anything, evidence is empty
   and stays empty: that's the only failure state. The Answerer's prompt
   handles it by saying so honestly rather than fabricating a
   recommendation (see prompts/answerer_system.md).

"Satisfactory" is deliberately just "at least one hit," not a similarity-
score cutoff — rag.search's `where` filter already enforces the hard
constraints (price/brand/category), and there's no calibrated eval set to
justify a specific score threshold on top of that.
"""
import difflib
from typing import Optional

from mcp_client import MCPToolClient
from state import AgentState

_TITLE_MATCH_THRESHOLD = 0.6


def _titles_match(a: str, b: str) -> bool:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= _TITLE_MATCH_THRESHOLD


async def run(state: AgentState, mcp_client: MCPToolClient) -> dict:
    intent = state["intent"]
    plan = state["plan"]
    constraints = intent.get("constraints", {})
    category = intent.get("category")

    private_hits: list[dict] = await mcp_client.rag_search(
        intent["task"],
        max_price=constraints.get("max_price"),
        brand=constraints.get("brand"),
        category=category,
        k=5,
    )
    for hit in private_hits:
        hit["source"] = "private"

    evidence: list[dict] = list(private_hits)

    private_satisfactory = len(private_hits) > 0
    need_web = not private_satisfactory or "live" in plan.get("sources", [])

    if need_web:
        live_hits: list[dict] = await mcp_client.web_search(intent["task"], k=5)
        for hit in live_hits:
            hit["source"] = "live"
            reconciled: Optional[dict] = next(
                (p for p in private_hits if _titles_match(p["title"], hit.get("title") or "")),
                None,
            )
            if reconciled is not None:
                reconciled.setdefault("live_matches", []).append(hit)
            else:
                evidence.append(hit)

    trace = state.get("trace", [])
    reason = "plan wants live data" if "live" in plan.get("sources", []) else "no private match" if need_web else None
    trace_msg = f"retriever: {len(evidence)} evidence items (category={category!r}"
    trace_msg += f", web fallback: {reason})" if need_web else ")"
    trace.append(trace_msg)
    return {"evidence": evidence, "trace": trace}
