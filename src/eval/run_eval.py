"""RAG eval harness — runs golden_queries.json through the real agent graph
(real Claude, real Chroma, real web search — no mocks) and checks a small
set of automatically-verifiable properties per query. See README.md in
this directory for the methodology and the latest recorded results.

Usage:
    cd src/eval
    python run_eval.py
"""
import asyncio
import json
import sys
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
sys.path.insert(0, str(_AGENTS_DIR))  # src/eval/ has no config.py of its own, so no collision risk

from graph import build_graph  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from mcp_client import MCPToolClient  # noqa: E402

QUERIES_PATH = Path(__file__).resolve().parent / "golden_queries.json"


def _check_category(case: dict, intent: dict) -> tuple[bool, str]:
    expected = case.get("expected_category")
    if expected is None:
        return True, "N/A (no expected category)"
    actual = intent.get("category")
    ok = actual == expected
    return ok, f"expected {expected!r}, got {actual!r}"


def _check_web_fallback(case: dict, trace: list[str]) -> tuple[bool, str]:
    expected = case.get("expect_web_fallback")
    if expected is None:
        return True, "N/A (not asserted)"
    retriever_line = next((line for line in trace if line.startswith("retriever:")), "")
    happened = "web fallback:" in retriever_line
    ok = happened == expected
    return ok, f"expected web_fallback={expected}, got {happened} ({retriever_line})"


def _check_price_compliance(case: dict, evidence: list[dict]) -> tuple[bool, str]:
    max_price = case.get("max_price")
    if max_price is None:
        return True, "N/A (no price constraint)"
    # Only private hits are price-filtered at the query level (rag.search's
    # `where` clause) — web.search has no price parameter, so live results
    # legitimately can exceed max_price. Only check private evidence.
    violations = [
        e for e in evidence
        if e.get("source") == "private" and e.get("price") is not None and e["price"] > max_price
    ]
    ok = not violations
    return ok, "OK" if ok else f"{len(violations)} private hit(s) exceed ${max_price}: {[e['title'] for e in violations]}"


def _check_grounding(evidence: list[dict], citations: list[dict]) -> tuple[bool, str]:
    valid_doc_ids = {e["doc_id"] for e in evidence if e.get("doc_id")}
    valid_urls = {e["url"] for e in evidence if e.get("url")}
    bad = [
        c for c in citations
        if not ((c.get("doc_id") and c["doc_id"] in valid_doc_ids) or (c.get("url") and c["url"] in valid_urls))
    ]
    ok = not bad
    return ok, "OK" if ok else f"{len(bad)} ungrounded citation(s) slipped through: {bad}"


def _check_no_private_evidence(case: dict, evidence: list[dict]) -> tuple[bool, str]:
    if not case.get("expect_no_private_evidence"):
        return True, "N/A"
    leaked = [e for e in evidence if e.get("source") == "private"]
    ok = not leaked
    return ok, "OK" if ok else f"{len(leaked)} rejected private hit(s) leaked into evidence: {[e['title'] for e in leaked]}"


async def run_case(graph, case: dict) -> dict:
    result = await graph.ainvoke({"transcript": case["transcript"], "trace": []})
    intent = result.get("intent", {})
    evidence = result.get("evidence", [])
    citations = result.get("citations", [])
    trace = result.get("trace", [])

    checks = {
        "category": _check_category(case, intent),
        "web_fallback": _check_web_fallback(case, trace),
        "price_compliance": _check_price_compliance(case, evidence),
        "grounding": _check_grounding(evidence, citations),
        "no_private_evidence": _check_no_private_evidence(case, evidence),
    }
    passed = all(ok for ok, _ in checks.values())
    return {
        "id": case["id"],
        "transcript": case["transcript"],
        "passed": passed,
        "checks": checks,
        "answer": result.get("answer"),
        "trace": trace,
    }


async def main() -> None:
    cases = json.loads(QUERIES_PATH.read_text())
    llm = LLMClient()

    results = []
    async with MCPToolClient() as mcp_client:
        graph = build_graph(llm, mcp_client)
        for case in cases:
            print(f"running: {case['id']} ...", flush=True)
            results.append(await run_case(graph, case))

    print("\n" + "=" * 70)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{status}] {r['id']} — {r['transcript']!r}")
        for name, (ok, detail) in r["checks"].items():
            marker = "  ok " if ok else " FAIL"
            print(f"  {marker} {name}: {detail}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print("\n" + "=" * 70)
    print(f"{passed}/{total} cases passed")

    # Per-check pass rates, across all cases where that check was actually asserted (not N/A).
    check_names = results[0]["checks"].keys() if results else []
    for name in check_names:
        asserted = [r["checks"][name] for r in results if r["checks"][name][1] != "N/A" and not r["checks"][name][1].startswith("N/A")]
        if not asserted:
            continue
        ok_count = sum(1 for ok, _ in asserted if ok)
        print(f"  {name}: {ok_count}/{len(asserted)}")

    out_path = Path(__file__).resolve().parent / "last_run_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nfull results written to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
