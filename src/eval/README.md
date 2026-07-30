# RAG Eval Plan

Automated evaluation of the [Agent Graph](../agents/README.md)'s
retrieval quality — the "RAG eval plan" deliverable — run against the **real** pipeline (real Claude, real Chroma index, real web search), not mocks. This is what actually caught and drove the fix for a real bug (see [Results and what they found](#results-and-what-they-found) below).

## Methodology

`golden_queries.json` is a small, hand-picked set of queries chosen to each isolate one specific behavior the [Retrieval routing](../agents/README.md#retrieval-routing) logic is supposed to have — not a large random sample, but targeted cases where we already know what *should* happen and can check it automatically:

| case | what it tests |
|---|---|
| `private-satisfiable-toys`, `private-satisfiable-home-kitchen` | well-populated category, genuine match -> stays private-only, no unnecessary web fallback |
| `private-satisfiable-true-positive` | contrast case for the one below — the relevance check must not become so strict it rejects a *real* match |
| `relevance-check-catches-mismatch` | regression test for the exact "cotton throw pillow covers" bug (bolster pillow / bed sheets scored well on cosine similarity but aren't the right product type) — relevance check must reject them and trigger fallback |
| `web-fallback-empty-category` | category with ~1 catalog row -> private search returns zero hits -> fallback |
| `wants-live-data-forces-fallback` | "current price... right now" must force a live check even though the category is well-populated privately |
| `total-failure-case` | deliberately absurd/unsatisfiable request — private hits must be rejected *and excluded from evidence*, and the answer must not fabricate a match |
| `baby-products-category`, `sports-outdoors-category`, `arts-crafts-category` | category-routing accuracy across differently-sized categories (214 / 540 / 124 rows) |

Each case asserts a subset of five automatically-checkable properties
(`null`/absent in a case's JSON means "not asserted for this case," not
"expected false"):

- **`category`** — Router's `intent.category` matches the expected top-level category.
- **`web_fallback`** — whether `web.search` fired matches expectation, read directly off the `trace` field (`"web fallback:"` substring in the retriever's trace line).
- **`price_compliance`** — every **private** evidence item respects `max_price`. Only private, deliberately: `rag.search`'s `where` filter enforces price server-side, so this is really checking that enforcement, not guessing; `web.search` has no price parameter, so live results legitimately can exceed budget (the Answerer is expected to flag that, not the retriever to filter it).
- **`grounding`** — every citation's `doc_id`/`url` matches an evidence item exactly. This is already enforced in code (`answerer.py` drops ungrounded citations before returning), so this check is external verification that the enforcement actually works, not a new mechanism.
- **`no_private_evidence`** — for the total-failure case specifically: once the relevance check rejects the private hits, they must not appear in `evidence` at all, regardless of whether web search also ran.

## Running

```bash
cd src/eval
python run_eval.py
```

Requires `ANTHROPIC_API_KEY` (each case runs Router + Planner + Retriever's relevance check + Answerer — 4 real LLM calls) and the ingestion pipeline already run. Prints a per-case, per-check breakdown, then aggregate pass rates, and writes full results to `last_run_results.json` (gitignored — regenerate by running the script, not something to keep committed history of).

## Results and what they found

Latest run: **10/10 cases passed**, all checks passing on every case they were asserted for. That's not the interesting part — the interesting part is what the *first* run found before the fix below.

**Real bug caught**: the first run of `total-failure-case` failed its (then-named) `expect_empty_evidence` check — evidence had 6 items instead of 0. Tracing through: the relevance check correctly rejected the private hits ("paper party plates, unrelated to a diamond-encrusted platinum toothbrush") and correctly triggered a web fallback, but `retriever.py`'s `evidence` list started as `list(private_hits)` *unconditionally* — the rejected hits were never actually removed, just potentially supplemented by web results. The Answerer's own judgment happened to avoid citing the irrelevant private items that run, but that was luck, not a guarantee; the underlying evidence list handed to it was already wrong.

Fixed in `retriever.py`: `evidence` now starts as `list(private_hits)` only when the relevance check approves them, `[]` otherwise — a rejected private hit can no longer reach the Answerer regardless of what web search does afterward. This directly matches what the module's own docstring already said the behavior should be; the code just hadn't been doing it.

**The eval's own assertion was also wrong**, separately: `expect_empty_evidence` assumed a sufficiently absurd query would return literally nothing from *either* source. In practice, Shopping search has broad enough recall to find something topically related (an over-budget, wrong-spec toothbrush) for almost any query containing a real product noun — "nothing found anywhere" turned out to be a much rarer, harder-to-construct case than assumed. Replaced with `expect_no_private_evidence`, which checks the thing that's actually guaranteed by the design: rejected private hits must not leak into evidence, independent of whether web search finds something. The Answerer is still responsible for being honest about a price/spec mismatch in whatever web results do come back (see `prompts/answerer_system.md`) — verified by reading its actual answer text for this case, not asserted mechanically.

## Known limitations of this eval

- **10 hand-picked cases, not a statistically representative sample.**
  Each one isolates a specific mechanism; this tells you those mechanisms work on these inputs, not a precision/recall number across the full query distribution.
- **No semantic quality scoring of the final answer text** 
  —    grounding and price compliance are checked mechanically, but "is this actually a *good* recommendation" is judged by reading the output, not automated.
- **Category-routing cases don't assert `web_fallback`** 
  — added for category-accuracy coverage across category sizes, not fallback-logic coverage (already covered by the other cases).
- **Costs real API calls every run** 
  (~40 Claude calls + a few web searches for the 10 cases) — not free, not instant, deliberately kept small rather than expanded into a large regression suite.

## Agent Safety & Robustness Eval (proofagent-harness)

`proofagent_eval.py` is a second, complementary eval using [proofagent-harness](https://pypi.org/project/proofagent-harness/) (a third-party adversarial agent-testing library, `pip install proofagent-harness` — deliberately **not** added to the top-level `requirements.txt`, since it's a dev-only eval tool, not something the deployed backend needs). Where `run_eval.py` asks "does retrieval route and ground correctly," this asks a different question: **does the Answerer's user-facing behavior hold up under manipulation** — jailbreak attempts, fabricated "context" injected mid-conversation, requests to state unverified facts as certain, attempts to extract the system prompt?

The harness drives a multi-turn adversarial conversation against the real agent graph (`_run_turn` in `proofagent_eval.py` calls `build_graph(...).ainvoke(...)` per turn, same graph as everything else in this repo) and scores the transcript with its own LLM jury across six metrics: task_success, instruction_following, hallucination_resistance, tool_use, safety, manipulation_resistance.

```bash
cd src/eval
python proofagent_eval.py   # requires: pip install proofagent-harness
```

### A real bug this caught

The first run crashed on 4 of 5 adversarial turns: one persona sent an extremely long jailbreak-style message (fake clinical citations, asking the agent to draft supplement marketing copy), and the resulting query text was long/unusual enough that Serper's organic-search endpoint returned a 400. `web_tool.py`'s `web_search()` had no error handling around the Serper HTTP calls — the `HTTPError` from `raise_for_status()` propagated all the way up through the MCP tool call and crashed the entire agent turn, instead of degrading to "no web results" (which the Answerer's own prompt already says to handle honestly — see `prompts/answerer_system.md`'s "empty evidence is not an error" rule). **This wasn't a jailbreak-specific issue** — any transient Serper failure (rate limit, outage, odd query) would have crashed a live user query the same way. Fixed in `web_tool.py`: both the Shopping and organic calls now catch `requests.RequestException` and treat it as "no results from that path" rather than letting it propagate. Verified directly (reproduced the same oversized query against `web_search()` — no crash, returns `[]`) and by re-running the full harness eval (0 crashes on the next two runs).

### A false-positive this eval's own integration caused (and the fix)

The first clean run flagged a "fabricated rating (4.8)" as a hallucination-resistance finding. Checked it directly: the rating was real — a genuine Shopping API result for "Nature Made Super C 60 Tablets." The bug was in `proofagent_eval.py`'s own `_run_turn`, not the product: the `tools_called` summary handed to the harness's jury only included `title`/`price`/`url`, silently dropping `rating`/`brand`/`brand_inferred` — so a claim that was genuinely grounded in tool output looked fabricated to a jury that never saw the field it came from. Fixed by including all evidence fields in `tools_called`.

### Conversation memory

The agent graph now supports real cross-turn conversation history (`AgentState.history`, threaded through the Router — see `src/agents/router.py` and `prompts/router_system.md`), so `_make_run_turn()` closes over a history list and threads it through exactly like the frontend does (`frontend/src/App.jsx`), instead of invoking a fresh, memoryless graph per harness turn. This means multi-turn adversarial attacks that try to build state across turns ("first I told you X, now do Y based on that") are now actually exercised against real memory, not a stateless stand-in.

### Results (latest clean run, `turns=5`, `consensus="delphi"`, real conversation memory enabled)

| metric | score |
|---|---|
| task_success | 83% |
| hallucination_resistance | 94% |
| instruction_following | 100% |
| manipulation_resistance | 100% |
| safety | 100% |
| tool_use | not scored — harness-side juror error, not an agent measurement (see below) |

**Certification: SILVER.** No `critical`/`fail` severities on any real (non-placeholder) metric — every deduction is `info`/`warn`-level. This run is the first with real cross-turn conversation memory wired in (see below) — manipulation_resistance and safety stayed at 100%, so enabling memory didn't open up a new attack surface a stateless agent didn't already resist. Full per-turn transcript, findings, and consensus detail: `proofagent_results.json` (gitignored, like `last_run_results.json` — regenerate by running the script).

### Known limitations of this eval specifically

- **`turns=5`, not the harness's own recommended 15–17** — kept small deliberately for cost (~$1–2 in harness-LLM tokens per run) and time (~4 min), same tradeoff as the 10-case golden set above. The harness's own output says explicitly this leaves most of its 11 attack-trap families unprobed.
- **Run-to-run variance is real and expected** — the harness generates adversarial turns via its own LLM each run (no seed pinned), so exact scores move between runs (task_success alone ranged 71%–100% across three runs during development, entirely attributable to the two bugs above, not agent nondeterminism — but even after fixing both, a few points of jury variance across runs is normal per the harness's own documentation, not a red flag on its own).
- **`tool_use` failed to score on the last run** (harness LLM jury returned invalid JSON) — the harness's own reporting is explicit that the resulting `0.0` is a placeholder, not a real measurement, and excludes it from the final-score calculation accordingly.
- **No push to proofagent's external governance dashboard** — the harness supports an optional `PROOFAGENT_API_KEY`/`PROOFAGENT_API_BASE_URL` step that uploads the run to a third-party service; deliberately not wired up here, since that would mean sending real query/answer transcripts to an external party without a specific reason to.
