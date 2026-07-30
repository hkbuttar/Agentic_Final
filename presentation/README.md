# Demo Script

Slide deck (architecture diagram, live-demo cue card, eval results,
limitations): https://claude.ai/code/artifact/d96f695a-1800-4252-a969-09592e493320
This file is the durable, repo-committed version of the same script — the
deck is a visual aid for delivering it, not the only copy.

## Timing (≤7 min)

**0:00 – 0:30 — Problem.** A hands-free voice assistant for product
discovery has to do more than a text chatbot: parse intent and
constraints from speech, decide whether a private catalog or the live
web (or both) can answer it, and reply honestly about what it does and
doesn't actually know — never inventing a rating or brand that was never
in the data.

**0:30 – 2:00 — Architecture.** Walk the pipeline: Router (extracts
task/constraints/category from the transcript) → Planner (decides
retrieval sources) → Retriever (queries the catalog scoped to category,
then runs an LLM relevance check — not a similarity threshold — before
falling back to a live search) → Answerer (synthesizes a ≤15-second
spoken answer; grounding is enforced in code, any citation that doesn't
verbatim-match an evidence item is dropped before the user sees it).
Mention the MCP tool layer underneath (`rag.search`, `web.search`) and
that ASR/TTS are fragment-based (record → transcribe; synthesize →
play), not streaming.

**2:00 – 5:30 — Live demo.** Two queries, not one — the second is chosen
specifically to show the relevance check and web fallback working, not
just the happy path:

1. *"Recommend a wooden puzzle for toddlers under 25 dollars."* Show the
   transcript, the agent step log, the comparison table, and play the
   spoken answer. This should stay entirely private-catalog — no web
   fallback.
2. *"I need cotton throw pillow covers."* The catalog has a bolster
   pillow and bed sheets that are topically close but not the right
   product type — point at the trace line where the relevance check
   rejects them and triggers a live Shopping search, returning a real
   product with a real price and link.
3. Point at the citations panel — every citation traces to a real
   `doc_id` or URL, enforced in code, not just prompted for.

**5:30 – 6:30 — Results.** Two evals, both run against the real live
pipeline (not mocks), both of which caught and drove fixes for real
bugs:

- **RAG eval** (`src/eval/run_eval.py`, 10 hand-picked cases): 10/10
  passing. The first run caught rejected private-catalog hits leaking
  into the Answerer's evidence after being judged irrelevant — fixed in
  `retriever.py`.
- **Adversarial eval** (`src/eval/proofagent_eval.py`, third-party
  proofagent-harness library): SILVER certification, 100% task success,
  100% safety, 88–94% on hallucination-resistance/instruction-following/
  manipulation-resistance. The first run crashed 4 of 5 turns — an
  unhandled Serper API error was taking down the whole agent turn on any
  transient failure, not just adversarial input — fixed in `web_tool.py`.

**6:30 – 7:00 — Limitations, honestly.** Rating and brand are genuinely
absent from the private catalog's source data (verified against the raw
file); shown as empty rather than guessed, with brand getting a
clearly-labeled heuristic guess from the title, never presented as fact.
Fragment-based, not streaming, voice I/O. The RAG eval is 10 targeted
cases, not a statistical sample. The agent has no cross-turn conversation
memory — every voice query is a one-shot exchange.

## Notes for whoever presents

- Have the frontend and backend already running locally before starting
  — don't burn demo time on `npm run dev` / `uvicorn` startup.
- If the live web search is flaky (documented, known issue — Shopping API
  occasionally returns empty on the same query, self-corrects on retry),
  don't panic: it's expected and mentioned in the eval README, not a
  live-demo failure.
- Keep query 2 exactly as written above — it's the one proven to
  reliably trigger the relevance-check/fallback path in front of an
  audience.
