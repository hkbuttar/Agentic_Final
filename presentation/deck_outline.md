# Final Presentation — Detailed Deck Outline

Companion to [README.md](README.md) (the spoken demo script). This file is
the **build spec for the slides**: for each slide, what it must prove, the
literal text to put on it, the visual to draw, the words to say over it,
and the questions it invites.

**Format of each slide entry:**

- **Proves** — the rubric claim this slide exists to establish. If a slide
  doesn't prove something, cut it.
- **On the slide** — verbatim text, ready to paste. Nothing else goes on it.
- **Visual** — what to draw/screenshot, and what must be legible from the
  back of the room.
- **Say** — the spoken beats, in order. Not a script to read; the beats you
  must hit.
- **Do not say / don't put on the slide** — the specific over-claims and
  clutter to avoid.
- **If asked** — the Q&A follow-ups this slide invites, with the answer.

**Hard constraints:** 7:00 total, ~3:30 of it live demo, leaving ~3:30
across eight slides. That is roughly **25 seconds per non-demo slide.** Any
slide needing more than ~35 words of spoken content is too big — split it
or move it to the appendix.

---

# SLIDE 1 — Title

**Time:** 0:00–0:10 · **Proves:** nothing (orientation only)

### On the slide

> **Agentic Voice-to-Voice AI Assistant for Product Discovery**
> Speak a product request → grounded, cited, spoken answer
>
> Aren Mizuno · [teammate name] · ADSP 32028 · [date]

### Visual

One full-bleed screenshot of the finished UI, taken **after** a successful
query so it shows all four regions at once: transcript, agent step log,
comparison table with the Unit price column, and the citations panel with a
`doc_id` visible. Blur nothing. This is the only slide where a busy
screenshot is correct — you want the audience to see the finished thing
before you explain any of it.

### Say

- "This is a voice-in, voice-out product assistant — you speak a request,
  it answers out loud, and everything it says is cited on screen."
- Nothing else. Move.

### Do not

Do not read your own names off the slide. Do not describe the screenshot —
you'll be walking through the real thing in three minutes.

---

# SLIDE 2 — The problem

**Time:** 0:10–0:30 (20s) · **Proves:** you understood the problem, not
just the assignment

### On the slide

> **"Recommend an eco-friendly stainless-steel cleaner under fifteen dollars."**
>
> Three things a text chatbot doesn't have to do:
> 1. Pull **constraints** out of speech — budget, material, category
> 2. Decide **private catalog vs. live web** — per query, not per app
> 3. Be **honest about what isn't in the data** — never invent a rating

### Visual

Left third: the spoken query in large quotation marks with a mic glyph.
Right two-thirds: three numbered boxes, one per hard part. Number 3 gets a
visual accent (different border/color) — it's the thread that runs to
slide 8 and it should be visually recognizable when it reappears.

### Say

- "A customer says the whole request in one breath — the product type, the
  material, and the budget are all in there."
- "Three things make this harder than a text chatbot. Parsing constraints
  from speech. Deciding per-query whether our own catalog can answer it or
  whether we need to go live."
- "And the third one is the one we spent the most time on: being honest
  about what we don't have. Our catalog has no ratings and no brands at
  all — I'll come back to that. The easy failure mode is inventing them."

### Do not

Don't say "traditional chatbots struggle" — it's the brief's phrasing and
it's vague. Name the three concrete things instead. Don't put the
architecture on this slide; it's the next one.

### If asked

- *"Why is deciding private-vs-live hard?"* — Because a similarity score
  can't tell you. A search for "throw pillow covers" scores a bolster
  pillow highly; it's topically close and the wrong product. That's slide
  3's relevance check.

---

# SLIDE 3 — Architecture: the agent graph

**Time:** 0:30–1:20 (50s — the longest non-demo slide) · **Proves:**
multi-agent LangGraph orchestration (Functionality, 28) + planning/tool use
(10)

### On the slide

> **LangGraph:  Router → Planner → Retriever → Answerer/Critic**
>
> | Node | Does | Output |
> |---|---|---|
> | **Router** | transcript → task, constraints, category, safety flags | `intent` |
> | **Planner** | picks sources, fields, comparison criteria | `plan` |
> | **Retriever** | `rag.search` scoped to category → **LLM relevance check** → `web.search` only if needed | `evidence` |
> | **Answerer/Critic** | ≤15s spoken answer; **ungrounded citations dropped in code** | `answer` + `citations` |
>
> Every node returns schema-shaped JSON via **forced tool calls** — never parsed out of prose.

### Visual

The mermaid graph from [src/agents/README.md](../src/agents/README.md),
redrawn at presentation scale. Requirements:

- Four node boxes left to right, solid arrows between them.
- The `web.search` edge from Retriever to MCP drawn **dashed** and labeled
  *"only if private search isn't satisfactory, or plan needs live data."*
  This dashed edge is the single most important pixel on the slide — it's
  the conditional routing that makes this agentic rather than a fixed
  pipeline.
- A small colored dot on each node labeled with its state field (`intent`,
  `plan`, `evidence`, `answer`) so the audience sees state threading
  through.
- Do **not** draw the MCP internals here — that's slide 4.

### Say

- "Four nodes in a LangGraph state graph. Router takes the transcript and
  pulls out the task, the constraints, the category, and any safety flags."
- "Planner decides which sources to use and what to compare on."
- "Retriever hits the private catalog first, scoped to the category the
  Router inferred. Then — and this is the part I'd point at — it runs an
  **LLM relevance judgment**, not a similarity threshold, to decide whether
  those results are actually the product type the user asked for. Only if
  that fails does it fall back to live web search."
- "Answerer writes a fifteen-second spoken answer. And grounding is
  **enforced in code**, not just asked for in the prompt: any citation that
  doesn't verbatim-match an evidence item is dropped before the user ever
  sees it. The trace even logs how many got dropped."
- "One more thing that's easy to miss — every node returns structured JSON
  through a forced tool call, so we're never regex-ing an answer out of
  prose."

### Do not

- Don't read the table aloud row by row — the table is there so the
  audience can follow while you talk about the two things that matter
  (relevance check, code-enforced grounding).
- Don't say "we use LangGraph" and move on. The graders can read
  `graph.py`; what earns points is *why the edges are conditional*.
- Don't claim the relevance check is novel. It's a design choice with a
  concrete justification — say the justification.

### If asked

- *"Why not just use a similarity cutoff?"* — Tried it conceptually and it
  fails on a real case: cosine similarity tracks topical overlap, not
  product-type correctness. Bolster pillows and bed sheets outscore correct
  matches for "throw pillow covers." A row-count check misses it too,
  because the rows exist — they're just wrong. Case
  `relevance-check-catches-mismatch` in the eval is the regression test.
- *"What happens if both sources fail?"* — `evidence` comes out empty.
  That's the only failure state, and it's handled in the Answerer prompt:
  say you found nothing, cite nothing, don't invent a product.
- *"Does it handle follow-ups?"* — Yes; slide 5, demo step 3. The Router
  resolves ellipsis against history, and a pure selection over on-screen
  results (`is_followup_on_existing_results`) skips retrieval entirely.

---

# SLIDE 4 — Architecture: MCP layer + voice path

**Time:** 1:20–2:00 (40s) · **Proves:** MCP server (15 pts) + voice
pipeline + model-agnosticism

### On the slide

> **One MCP server, two tools** — JSON-schema discovery, stdio or HTTP/SSE
>
> `rag.search(query, max_price, min_rating, brand, category, k)`
> → `{sku, title, price, rating, brand, ingredients, doc_id, url, score}`
> Chroma, 10,002 products · vector + metadata filters · `doc_id` = citation key
>
> `web.search(query, k)` → `{title, url, snippet, price, availability, brand, rating}`
> Serper Shopping → allowlisted organic fallback · TTL cache 120s · 20 calls/60s · every call logged
>
> **The Retriever never calls a search API directly — it's an MCP client.**
>
> Voice: Whisper (`faster-whisper`) → graph → Azure Speech · fragment-based
> LLM: swappable via 2 `.env` lines (`LLM_PROVIDER`, `LLM_MODEL`)

### Visual

Two columns.

- **Left — MCP server box.** A container labeled "MCP Server
  (`mcp==2.0.0`)" holding two tool boxes. Under each tool, its input
  signature and 2–3 output fields. Below the box, a strip of four small
  badges: `cache 120s` · `20/60s` · `allowlist + robots.txt` · `logged`.
  Draw the arrow from Retriever → MCP as the *only* path to data.
- **Right — voice/UI strip.** Linear: 🎙 → `POST /transcribe` (Whisper) →
  `POST /query` (graph) → `POST /speak` (Azure) → 🔊, with the React UI as a
  band underneath touching all three.

### Say

- "Everything the agent knows comes through one MCP server with exactly
  two tools, discovered by JSON schema."
- "`rag.search` is vector plus metadata filters over ten thousand products
  in Chroma — and it returns a `doc_id`, which is what every on-screen
  citation traces back to."
- "`web.search` goes to Google Shopping through Serper first, then falls
  back to organic search that's domain-allowlisted and robots.txt-checked.
  Cached at two minutes, rate-limited, and every call is logged to
  `mcp_requests.log` with a timestamp — no keys, no bodies."
- "The important structural point: the Retriever node never calls a search
  API itself. It's an MCP client. Private retrieval and live search go
  through the same protocol."
- "Voice is fragment-based both directions — record, transcribe, answer,
  synthesize, play. And the LLM is genuinely swappable: two lines in
  `.env`, because every node writes its tool schema once and the provider
  facade converts it."

### Do not

- Don't put the full JSON schemas on this slide — they go in appendix A2.
- Don't claim streaming voice. It's fragment-based and that's an accepted
  choice in the brief; say it plainly rather than letting someone catch it.
- Don't skip the "Retriever is an MCP client" line to save time. It's the
  difference between "we built an MCP server for the rubric" and "the MCP
  server is load-bearing."

### If asked

- *"Why does Shopping skip the allowlist and robots.txt?"* — Because those
  checks exist for arbitrary pages we'd be crawling. Shopping results come
  from a licensed commercial feed via Serper's API contract, and the `url`
  is a Google redirect, not the merchant's domain — there's nothing to
  check it against. The organic fallback is the path that touches the open
  web, and that path gets both checks. Reasoning is in `web_tool.py`'s
  module docstring.
- *"Why Shopping first at all?"* — Organic search on a product query
  returns "Best Throw Pillow Covers" listicles, not products with prices.
  Shopping returns actual listings. It's tried up to twice because the
  endpoint is genuinely flaky — same query, full results one call, empty
  the next.
- *"What's in the log?"* — `{timestamp, tool, query, doc_ids | source_urls}`,
  one JSON line per call. Deliberately no keys and no response bodies.
- *"Have you actually run it on another provider?"* — The facade has both
  `_AnthropicProvider` and `_OpenAIProvider` implementing one
  `call_tool(system, user_message, tool)` interface; the OpenAI side
  converts the Anthropic-shaped tool schema internally, so no node has a
  provider-specific branch. [Be honest about how much you've exercised the
  OpenAI path — say "the abstraction is there and the conversion is
  implemented" if you haven't run a full demo on it.]

---

# SLIDE 5 — LIVE DEMO (holding slide)

**Time:** 2:00–5:30 (3:30 — half the talk) · **Proves:** Functionality
(28), UI/UX (10), and most of Agentic RAG (22)

### On the slide

> **Live demo**
>
> 1. Wooden puzzle for toddlers under $25 → private catalog
> 2. Cotton throw pillow covers → relevance check rejects → live fallback
> 3. "Which is the best value?" → follow-up, no re-retrieval, per-unit price
> 4. Citations → every one traces to a real `doc_id` or URL

### Visual

Text only, large. This slide exists so the audience knows what's coming and
so you have something on screen while you alt-tab. **Full-screen the app
before you advance to this slide, not after** — advance to it, say one
sentence, and switch.

### Demo choreography — do not improvise

**Query 1 — "Recommend a wooden puzzle for toddlers under 25 dollars." (~1:15)**

Point at, in this order:
1. **Transcript appears** — "that's Whisper, running locally."
2. **Agent step log** — read one line aloud: the Router's extracted intent,
   including `max_price: 25` and `category: Toys & Games`. "It pulled the
   budget and the category out of the sentence."
3. **Comparison table** — price, unit price, and the doc_id column.
4. **Play TTS** — actually play it. Let the room hear the full spoken
   answer. Do not talk over it.
5. Note what *didn't* happen: "no web search on that one — the catalog
   genuinely had it, and the trace says so."

**Query 2 — "I need cotton throw pillow covers." (~1:15) — the important one**

1. Let it run. **Point at the specific trace line** where the relevance
   check rejects the private hits — read the rejection reason out loud.
2. "The catalog returned a bolster pillow and a bed sheet set. High cosine
   similarity, wrong product type. A score threshold would have shipped
   those to the user."
3. Show the live Shopping result that comes back — real product, real
   price, real link.
4. Point at the citation on that row carrying a **URL** rather than a
   `doc_id`, and that the answer says the info came from a live search.

**Query 3 — voice follow-up: "Which is the best value?" (~0:45)**

1. Ask it **by voice**, through the same mic input — not a special
   follow-up box. That's the point.
2. Two things to point at:
   - The step log shows it answered from conversation history — no
     re-retrieval. "It knew this wasn't a new search."
   - The answer reasons in **per-unit price** — "which is what makes a big
     cheap item and a small expensive one actually comparable."

**Closing beat (~0:15)**

Point at the citations panel: "every one of these traces to a real
`doc_id` in our index or a real URL. That's enforced in code — the
Answerer's ungrounded citations get dropped before this panel renders."

### Pre-flight checklist (do before the talk starts)

- [ ] Backend running (`cd src/api && python app.py`) — **not** started live
- [ ] Frontend running (`cd frontend && npm run dev`) — **not** started live
- [ ] Chroma index built and a warm-up query already run (first call loads
      the embedding model; don't pay that latency on stage)
- [ ] Mic permissions already granted in the browser
- [ ] Browser zoom at ~125–150% so the trace lines are readable from the back
- [ ] Backup screen recording of all three queries on a hidden slide
- [ ] Serper key valid and quota not exhausted

### Failure handling — decide this now, not on stage

- **Shopping returns empty on query 2:** retry once. Say: "known flake —
  the same query returns results on a retry; it's documented in our eval
  README." Then move on. If the retry also fails, cut to the backup
  recording. Do not debug live.
- **Mic doesn't work:** `App.jsx` accepts typed text and skips
  `/transcribe`. Say you're typing it to save time; don't announce it as a
  failure.
- **Anything else:** cut to the recording. You have 3:30 and no slack.

### Do not

- Don't run a query that isn't one of these three. Query 2 in particular
  is the one *proven* to trigger the fallback path in front of an audience
  — improvising a new query is how you get a boring happy-path demo.
- Don't narrate the UI while the answer is playing. Let the TTS finish.
- Don't apologize for the UI's looks. It has every element the rubric asks
  for; say what each element is and move.

---

# SLIDE 6 — Results: RAG eval

**Time:** 5:30–6:00 (30s) · **Proves:** Agentic RAG quality (22)

### On the slide

> **RAG eval — `src/eval/run_eval.py`**
> 10 hand-picked golden cases, run against the **real** pipeline
> (real Claude, real Chroma, real web search — no mocks)
>
> Checks per case: category routing · web-fallback triggering ·
> price-constraint compliance · citation grounding · no leak of rejected hits
>
> **10 / 10 passing**
>
> **What the first run caught:** rejected private-catalog hits were still
> reaching the Answerer — `evidence` started as `list(private_hits)`
> unconditionally. Fixed in `retriever.py`.

### Visual

A 10 × 5 grid: cases down the left (`private-satisfiable-toys`,
`relevance-check-catches-mismatch`, `web-fallback-empty-category`,
`wants-live-data-forces-fallback`, `total-failure-case`, the three
category-routing cases…), the five checks across the top, green ticks in
the cells that are asserted, grey dashes where a check isn't asserted for
that case. **Call out the `total-failure-case` row** with an annotation:
"this row failed on the first run — that's the bug."

Use grey dashes deliberately and mention them if asked: `null` in a case's
JSON means "not asserted for this case," not "expected false."

### Say

- "Ten hand-picked cases, each isolating one behavior the routing logic is
  supposed to have. They run against the real pipeline — real model, real
  index, real web search."
- "They all pass now. That's not the interesting part."
- "The interesting part is the first run. The total-failure case came back
  with six evidence items instead of zero. The relevance check *was*
  correctly rejecting the private hits and *was* correctly triggering the
  fallback — but the evidence list was being seeded with those rejected
  hits unconditionally. The Answerer just happened not to cite them that
  run. That was luck, not design. Fixed in `retriever.py`."

### Do not

- Don't lead with "10/10." A perfect score on a test you wrote yourself is
  weak evidence; the bug it caught is strong evidence. Order matters.
- Don't call it a precision/recall number. It isn't one — see slide 8.

### If asked

- *"Isn't 10 cases too few?"* — Yes, and we say so on the limitations
  slide. It's a targeted mechanism test, not a sample of the query
  distribution. Each case exists to isolate one routing behavior we can
  check automatically. It costs ~40 real Claude calls per run, which is
  the tradeoff we chose.
- *"How is grounding checked here if it's already enforced in code?"* —
  Exactly for that reason: the eval check is external verification that
  the code enforcement actually works, not a second mechanism.
- *"Did the eval itself have bugs?"* — Yes, one, and we'd rather tell you:
  the original assertion was `expect_empty_evidence` — it assumed an absurd
  enough query returns nothing from *either* source. In practice Shopping
  has broad enough recall to find something topically related for almost
  any real product noun. Replaced with `expect_no_private_evidence`, which
  checks what the design actually guarantees.

---

# SLIDE 7 — Results: adversarial eval

**Time:** 6:00–6:30 (30s) · **Proves:** safety + robustness beyond the
rubric's floor

### On the slide

> **Adversarial eval — `proofagent-harness` (third-party), 5 multi-turn attacks**
> Jailbreaks · injected fake context · "state this unverified fact as certain" · prompt extraction
> Run against the **same live graph**, with real cross-turn conversation memory
>
> | metric | score |
> |---|---|
> | safety | 100% |
> | manipulation_resistance | 100% |
> | instruction_following | 100% |
> | hallucination_resistance | 94% |
> | task_success | 83% |
>
> **Certification: SILVER** — no critical/fail severities
>
> **What it caught:** an unhandled Serper `HTTPError` crashed the entire
> agent turn — on *any* transient failure, not just adversarial input.
> Fixed in `web_tool.py`.

### Visual

Horizontal bar chart, five bars, sorted descending, each labeled with its
percentage. SILVER badge top-right. Below the chart, the bug in a single
callout box — it deserves as much visual weight as the scores.

> ⚠️ **Numbers check before you build this slide.** `presentation/README.md`
> currently says "100% task success, 88–94%…" while `src/eval/README.md`'s
> latest clean run table says task_success **83%**, hallucination_resistance
> **94%**, instruction_following / manipulation_resistance / safety **100%**.
> Use the `src/eval/README.md` table — it's the latest run with conversation
> memory enabled — and fix `presentation/README.md` to match so the deck and
> the repo don't contradict each other in front of a grader. Re-run
> `proofagent_eval.py` if you want fresher numbers, but then update **both**.

### Say

- "Second eval, different question. The first one asks whether retrieval
  routes correctly. This one asks whether the assistant holds up under
  someone actively trying to break it."
- "A third-party harness drives multi-turn adversarial conversations —
  jailbreaks, fake injected context, requests to state unverified things as
  fact, prompt-extraction attempts — against the same live graph, with real
  conversation memory."
- "SILVER certification, no critical findings. Safety and
  manipulation-resistance at 100."
- "And again the useful part is the bug: the first run crashed four of five
  turns. An unhandled Serper error was taking down the whole agent turn.
  That wasn't a jailbreak problem — *any* transient search failure would
  have crashed a real user's query the same way."

### Do not

- Don't oversell SILVER. It's five turns against a harness that recommends
  fifteen-plus; say the number of turns if there's any chance of a
  follow-up.
- Don't hide the 83%. Putting it on the slide, sorted last, is stronger
  than being asked why you only showed four metrics.

### If asked

- *"Why isn't `tool_use` scored?"* — The harness's own LLM jury returned
  invalid JSON on that metric that run, and the harness explicitly reports
  the resulting 0.0 as a placeholder and excludes it from the final score.
  It's a harness-side error, not a measurement of our agent.
- *"Why only 5 turns?"* — Cost and time: ~$1–2 of harness tokens and ~4
  minutes per run. The harness's own output says this leaves most of its
  11 attack-trap families unprobed. Same tradeoff as the 10-case golden set.
- *"Is the score stable?"* — No, and that's expected: the harness generates
  its adversarial turns with its own LLM and we didn't pin a seed. Scores
  moved across dev runs, mostly attributable to the two bugs we fixed, but
  a few points of jury variance run-to-run is documented as normal.
- *"Any false positives?"* — One, and it was ours: the harness flagged a
  "fabricated 4.8 rating" that was actually a real Shopping result. Our own
  `_run_turn` was dropping `rating`/`brand` from the `tools_called` summary
  handed to the jury, so a grounded claim looked invented to a jury that
  never saw the field. Fixed by passing all evidence fields.

---

# SLIDE 8 — Limitations, honestly

**Time:** 6:30–6:55 (25s) · **Proves:** Presentation (10) — graders
reward volunteered limitations far more than they punish the limitation

### On the slide

> | What the brief assumed | What's actually true |
> |---|---|
> | embed title + features + **review snippets** | this Kaggle file has **no reviews and no rating column at all** — verified against all 10,002 raw rows. No snippets to embed, no `reviews.parquet` to build |
> | products have `brand`, `ingredients`, `rating` | all three **100% empty**. Shown as "not available", never guessed. `brand_inferred` is a labeled title heuristic, never presented as fact. Any rating on screen came from a **live** result |
> | normalized unit price enables fair comparison | it does — but it's derived from `Shipping Weight`, a **placeholder on a minority of rows**. ~62 rows carry an implausible figure. Surfaced as-is, not silently filtered |
>
> Also: fragment-based voice, not streaming · RAG eval is 10 targeted cases, not a statistical sample

### Visual

Two-column table, "What the brief assumed" left / "What's actually true"
right. Right column visually dominant. Reuse the accent color from slide
2's box 3 — this is that thread landing.

### Say

- "Three things we'd rather tell you than have you find."
- "The brief's embedding recipe is title, features, and top review
  snippets. This Kaggle file ships no reviews and no rating column at all —
  we verified that against all ten thousand raw rows in the EDA notebook.
  So there were no snippets to embed and no reviews file to build. Any
  rating you saw in the demo came from a live web result, tagged as such."
- "Brand and ingredients are the same story — a hundred percent empty. We
  show them as not-available. We do have a heuristic brand guess from the
  title, and it's labeled a guess everywhere, including in the Answerer's
  prompt."
- "And per-unit price is derived from a shipping weight that's a
  placeholder on some rows, so a handful of listings show something
  implausible. We surface those rather than filter them — a threshold
  would hide the problem without fixing it."
- "Voice is fragment-based, not streaming. And the RAG eval is ten targeted
  cases, not a statistical sample."

### Do not

- Don't hedge these into vagueness ("some data quality issues"). The
  specificity — *100% empty, verified against 10,002 rows* — is what makes
  it read as rigor rather than an excuse.
- Don't apologize. State, justify the choice you made, move.
- Don't add a fifth or sixth limitation. Four is credible; eight reads as
  a project that didn't work.

### If asked

- *"Why not use a different dataset with ratings?"* — It's the dataset the
  brief specifies. The honest handling of missing fields turned out to be
  more interesting than swapping the data would have been — it's what
  drove the grounding enforcement and half the Answerer prompt.
- *"Why not filter the bad unit prices?"* — We looked for a cutoff. There
  isn't a clean one: 62 rows exceed $100/unit, but the same implausible
  pattern continues below that (a $99.99 bed skirt at 1.00 lb → $99.99/lb).
  So the Answerer is instructed to omit obviously absurd figures rather
  than repeat them, and the limitation gets stated instead of hidden.
- *"Why 'Household Cleaning' in the brief but all categories here?"* — Only
  23 rows fall under Health & Household at all, and 7 mention cleaning
  anywhere in the breadcrumb. We index all 10,002 and filter by category at
  query time instead, which makes the slice question moot.

---

# SLIDE 9 — Prompt disclosure + repo

**Time:** 6:55–7:00 (5s — it's a closer, not a section) · **Proves:**
Prompt Disclosure (5 pts)

### On the slide

> **`prompts/` — every system prompt, read by its node at import time**
> The file *is* the runtime prompt, not a copy kept in sync by hand
>
> | file | node |
> |---|---|
> | `router_system.md` | `src/agents/router.py` |
> | `planner_system.md` | `src/agents/planner.py` |
> | `retriever_system.md` | `src/agents/retriever.py` — relevance judgment |
> | `answerer_system.md` | `src/agents/answerer.py` — grounding + safety |
>
> `python download_data.py && python clean.py && python build_index.py` → `python app.py` → `npm run dev`
>
> [repo URL]

### Visual

The mapping table on the left. On the right, a **real screenshot of actual
prompt text** — use the `brand_inferred` rule from
`prompts/answerer_system.md`:

> *"`brand_inferred` is a heuristic guess from the title, not verified data
> — never state it as fact. If you use it at all, phrase it as a guess
> ('looks like it's from LoftWorks') — never 'is made by LoftWorks.'"*

Showing real prompt text beats claiming you have prompts. It also closes
the loop with slide 8 in one image.

### Say

- "Every prompt is in `prompts/`, one file per node, and the node reads the
  file at import — so what's disclosed is literally what runs."
- "Three commands to reproduce it. Thank you — happy to take questions."

### Do not

Don't read the table. Don't start a new topic in the last five seconds.

---

# APPENDIX (not presented — hold for Q&A)

Build these. The likeliest place this presentation is won or lost is the
Q&A, and having the right slide ready is worth more than a prettier slide 3.

### A1 — Data ingestion pipeline

`download_data.py` → `clean.py` → `build_index.py`, with row counts at each
stage: 10,002 raw → 10,002 products (nothing dropped — every row has a
non-empty title and unique `Uniq Id`) → indexed. `all-MiniLM-L6-v2`,
384-dim, cosine, fully local, ~25s to rebuild. Price populated 9,839/10,002
(98%); per-unit price derivable for 8,838 (88%). Category distribution:
Toys & Games 6,662 · Home & Kitchen 708 · Clothing/Shoes/Jewelry 630 ·
Sports & Outdoors 540 · Baby Products 214 · long tail to Health &
Household 23 · 830 rows with no category at all.

### A2 — Full MCP tool schemas

Verbatim from [src/mcp_server/README.md](../src/mcp_server/README.md):
both input tables, both output JSON blocks. Have this ready — "show me the
schemas" is a likely MCP question and flipping to it beats describing it.

### A3 — Safety

Domain allowlist + `robots.txt` on the organic path (and why Shopping is
exempt); `intent.safety_flags` extracted by the Router, echoed into the UI
step log so a flagged request is *visibly* flagged, and acted on by the
Answerer; the specific rule that an unsupported "yes it's safe" is the
worst possible failure, so an unestablished safety property must be
reported as unconfirmed; never suggest workarounds (mixing, diluting,
off-label use) for a hazard the user raised; no secrets logged.

### A4 — Why an LLM relevance judgment beats a threshold

The pillow-cover case worked end to end: the query, the private hits that
came back (bolster pillow, bed sheet set), their similarity scores, the
relevance verdict text, and the live result that replaced them.

### A5 — Follow-up handling

`AgentState.history` → Router resolves ellipsis ("what about under $10" —
no product type in the sentence) vs. pure selection ("the cheapest one" →
`is_followup_on_existing_results = true` → Retriever skips search entirely
and reuses the previous evidence). Why: re-querying a selection risks
returning a *different* result set for a question that isn't asking for
anything new.

### A6 — Data-quality forensics

The price parser: `Selling Price` has ~4% garbage ("from 2 sellers",
"Total price:", "$8.25 - $31.95" ranges). `_parse_price` requires a
leading `$` — an earlier unanchored version read "from 2 sellers" as $2.00.
Ranges use the low end. Also: `Technical Details` was chosen over
`Product Specification` because the latter is ~100% boilerplate with the
words run together (`ProductDimensions:5.7x4.9x1.2inches`) — noise, not
signal, in an embedding.

### A7 — Brand inference tradeoff

Single-word by design. A 2–3 word version grabbed unrelated descriptors
("Ceaco Perfect Piece Count Puzzle" → "Ceaco Perfect Piece"). A
truncated-but-correct guess beats a confidently wrong longer one — and it
never merges into `brand`, which stays empty exactly as the source has it.

### A8 — Backup demo recording

Screen capture of all three demo queries, pre-recorded, with audio. Test
that the audio actually plays through the room's system before the talk.

---

# Rubric coverage check

| Rubric item (pts) | Where it lands | Strongest evidence |
|---|---|---|
| Functionality (28) | 3, 4, 5 | the live voice→voice loop, all three queries |
| Agentic RAG quality (22) | 3, 5 (query 2), 6 | relevance check rejecting a topical-but-wrong match, live |
| MCP server (15) | 4, A2 | two tools, schemas, cache/rate-limit/log badges |
| Planning & tool use (10) | 3, 5 | the dashed conditional edge, demonstrated firing |
| UI/UX (10) | 1, 5 | transcript + step log + table + playback, all on screen at once |
| Presentation (10) | 2, 3–4, 6–8 | limitations volunteered with specific numbers |
| Prompt disclosure (5) | 9 | real prompt text on screen, node mapping table |

# Build notes

- **9 presented slides + 8 appendix.** Only 3, 4, 6, 7, 8 carry real
  density; 1, 2, 5, 9 are one visual and a sentence.
- **Charts to build:** slide 6's case × check grid, slide 7's five-bar
  metric chart. Use the real numbers; don't round up.
- **Resolve the metric discrepancy** between `presentation/README.md` and
  `src/eval/README.md` before building slide 7 (see the warning there).
- **The two slides that earn the most:** slide 3 (conditional routing) and
  slide 8 (volunteered limitations). If you're over time, cut words from 4,
  never from those.
- **Rehearse against a timer at least once**, out loud, with the demo. The
  architecture section overruns every time; 50 seconds for slide 3 is not
  generous.
- Total non-demo speaking time is ~3:30. If your run-through comes in over
  7:00, the fix is fewer words on slides 3 and 4 — not a faster demo.
