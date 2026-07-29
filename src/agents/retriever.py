"""Retriever node — queries the private catalog via rag.search, calls
web.search if the plan includes "live", and reconciles the two by
title similarity. No LLM call here: this node only talks to the MCP tool
server (src/mcp_server), matching the README's "Queries private vector DB;
calls web.search if the plan requires it; reconciles conflicts" spec.
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

    private_hits: list[dict] = await mcp_client.rag_search(
        intent["task"],
        max_price=constraints.get("max_price"),
        brand=constraints.get("brand"),
        k=5,
    )
    for hit in private_hits:
        hit["source"] = "private"

    evidence: list[dict] = list(private_hits)

    if "live" in plan.get("sources", []):
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
    trace.append(f"retriever: {len(evidence)} evidence items (sources={plan.get('sources')})")
    return {"evidence": evidence, "trace": trace}
