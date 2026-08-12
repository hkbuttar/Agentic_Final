# Agentic Voice-to-Voice AI Assistant for Product Discovery

A voice-to-voice, multi-agent e-commerce assistant that understands spoken product requests, plans a retrieval strategy, pulls grounded evidence from a private product catalog (with optional live web reconciliation), and responds via speech with on-screen citations.

## Problem Statement

Customers often describe what they want in natural, conversational language (e.g., *"I need an eco-friendly stainless-steel cleaner under $15"*). Traditional chatbots struggle to parse intent, search private catalogs, verify live availability, and respond clearly — especially in hands-free scenarios. This project addresses that gap with a grounded, tool-using, voice-native assistant.

## Scope

- Voice-to-voice product discovery with a multi-agent flow: **intent → plan → retrieve/tools → summarize**, orchestrated in **LangGraph**.
- Grounded, cited recommendations sourced from a private catalog, optionally reconciled with live web data.
- Fragment-based ASR/TTS (record → transcribe; synthesize → play), with streaming as a stretch goal.

## System Architecture

| Node | Role | Input | Output |
|---|---|---|---|
| **Router** | Extracts task + constraints (budget, brand, material) and safety flags | Transcript | Structured intent object |
| **Planner** | Chooses sources (private/live), fields to retrieve, comparison criteria | Intent object | Retrieval plan |
| **Retriever** | Queries private vector DB; calls `web.search` if the plan requires it; reconciles conflicts | Plan | Ranked, cited evidence |
| **Answerer/Critic** | Synthesizes a concise, cited recommendation; enforces grounding & safety | Evidence | Final answer + citations | 

### Agent Graph (LangGraph)

- `rag.search` is preferred for factual/catalog questions.
- `web.search` is additionally invoked when the user asks about current price, availability, "now," or "latest." 
- Results are reconciled by SKU/brand/title similarity, and the router directs the graph to the response path best suited to the identified need.

### MCP Tool Server (Two Tools)

Built with the MCP Python SDK; tool discovery via JSON schema; transport over stdio or HTTP/SSE.

- **`web.search(query)`** — wraps a web search API (Serper.dev or Brave Search API) → returns `{title, url, snippet, price?, availability?}`. Cached (TTL 60–300s), rate-limited.
- **`rag.search(query, filters)`** — vector + metadata search over the Amazon 2020 catalog → returns `{sku, title, price, rating, brand?, ingredients?, doc_id}`.

All requests/responses are logged with timestamp and source URL. A domain allowlist is enforced and `robots.txt`/ToS are respected.

### ASR (Speech-to-Text)

- **Model:** Whisper (`faster-whisper` for lower CPU latency)
- **Mode:** Fragment-based — record → upload WAV/MP3 → transcribe
- **Output:** Transcript with timestamps; basic multilingual accent handling

### TTS (Text-to-Speech)

- **Provider:** Azure Speech (current)
- **Output:** ≤15-second spoken summary aligned to on-screen citations

### Retrieval Corpus

- **Source:** Amazon Product Dataset 2020 (Kaggle), full dataset (10,002 products, all categories)
- **Schema:** `products.parquet`, 16 columns — `id, title, brand, brand_inferred, category, category_top_level, price, rating, ingredients, model_number, url, unit_qty, unit, price_per_unit, features, doc_id`
- **Organization:** `category_top_level` (e.g. "Home & Kitchen", "Toys & Games") is stored as filterable Chroma metadata, not used to pre-filter at ingestion time — `rag.search` can scope a query to one category or search across all of them
- **Embeddings:** Title + features via `sentence-transformers` (`all-MiniLM-L6-v2`); stored in a persistent Chroma collection (cosine distance)
- **No review snippets, and no `reviews.parquet`:** the brief's embedding recipe is title + features + top review snippets, but this Kaggle file contains no reviews and no rating column of any kind (confirmed in `notebooks/00_eda.ipynb` against all 10,002 raw rows) — there were no snippets to embed. `rating` is therefore `None` for every catalog row, and any rating the UI shows came from a live `web.search` result, clearly tagged as such. `ingredients` is likewise 100% empty, so it's excluded from the embedding text (it would contribute nothing) but kept in metadata
- **Normalization:** `price_per_unit` is derived at cleaning time and carried through the whole path — indexed as Chroma metadata, returned by `rag.search` alongside its `unit` ("oz", "lb", "ct"), used by the Answerer for value comparisons, and shown in the UI's comparison table as a "Unit price" column. The number is only meaningful with its unit, so the two are never separated. Caveat: it's derived from `Shipping Weight`, which is a placeholder for a minority of rows, so a small number of listings carry an implausible per-unit price (see [Known data-quality limitations](src/ingestion/README.md#known-data-quality-limitations)) — surfaced as-is rather than filtered behind an arbitrary threshold, with the Answerer instructed to omit obviously-absurd values instead of repeating them

Full ingestion pipeline, schema decisions, and known data-quality caveats: [src/ingestion/README.md](src/ingestion/README.md), summarized below in [Data Ingestion](#data-ingestion).

### User Interface

- **Framework:** React (Vite), run locally via the dev server
- **Features:** Mic capture (record/upload), live transcript, agent step log, comparison table, citations, Play TTS button

## LLM & Configuration

- **Provider:** Claude API (Anthropic) by default, or OpenAI — model-agnostic by design, swappable via two `.env` lines (`LLM_PROVIDER` + `LLM_MODEL`) through `src/agents/llm_client.py`'s provider abstraction, no code changes needed for either node logic or tool schemas
- Native tool/function calling enabled throughout
- Context limited to grounded snippets only; citations required to reduce hallucination
- All system prompts, router/planner prompts, and few-shot examples are logged in a `prompts/` folder for disclosure

## Example Interaction

**User (voice):** "Recommend an eco-friendly stainless-steel cleaner under fifteen dollars."

**System (voice):** "Here are three options that fit your budget and material. My top pick is Brand X Steel-Safe Eco Cleaner — plant-based surfactants, 4.6★ average rating, typically $12.49. I compared this with two alternatives. I've sent details and sources to your screen. Would you like the most affordable or the highest rated?"

*(On screen: top-3 comparison table with price, rating, ingredients, and citations to private doc IDs and live links.)*

## Repository Structure

All Python code lives under `src/` (src-layout); `frontend/` is the separate
React/JS root.

```
.
├── src/
│   ├── ingestion/
│   │   ├── download_data.py      # Kaggle -> data/raw/*.csv
│   │   ├── inspect_schema.py     # confirms raw column names/dtypes
│   │   ├── clean.py              # data/raw -> data/processed/products.parquet
│   │   ├── build_index.py        # products.parquet -> data/chroma_db/
│   │   ├── embeddings.py         # sentence-transformers wrapper (all-MiniLM-L6-v2)
│   │   ├── retriever.py          # RagRetriever.search() — imported by rag.search
│   │   ├── config.py             # ingestion env/config (CHROMA_DIR, CHROMA_COLLECTION, ...)
│   │   └── README.md             # pipeline stages, schema, category organization, data-quality caveats
│   ├── mcp_server/                # MCP server exposing web.search and rag.search tools
│   │   ├── server.py              # registers both tools, runs stdio/sse/streamable-http
│   │   ├── rag_tool.py            # wraps src/ingestion's RagRetriever
│   │   ├── web_tool.py            # Serper/Brave + domain allowlist + robots.txt + cache + rate limit
│   │   ├── config.py              # MCP server env/config
│   │   ├── cache.py               # in-process TTL cache
│   │   ├── rate_limit.py          # sliding-window rate limiter
│   │   ├── log_utils.py           # request/response logging (no secrets)
│   │   └── README.md              # tool schemas (Checkpoint 2 deliverable)
│   ├── agents/                     # LangGraph nodes: router, planner, retriever, answerer/critic
│   │   ├── graph.py                # builds/compiles the StateGraph
│   │   ├── state.py                # AgentState / Intent / Plan / Citation TypedDicts
│   │   ├── router.py               # transcript -> intent (forced tool call)
│   │   ├── planner.py              # intent -> plan (forced tool call)
│   │   ├── retriever.py            # plan -> evidence (rag.search + web.search via MCP client)
│   │   ├── answerer.py             # evidence -> answer + citations (forced tool call, grounding filter)
│   │   ├── llm_client.py           # single Claude API wrapper — swap providers here only
│   │   ├── mcp_client.py           # spawns src/mcp_server/server.py over stdio
│   │   ├── config.py               # agent env/config (ANTHROPIC_API_KEY, LLM_MODEL, ...)
│   │   ├── main.py                 # CLI entrypoint for one end-to-end (text) query
│   │   ├── voice_main.py           # CLI entrypoint: audio in -> ASR -> graph -> TTS -> audio out
│   │   └── README.md               # architecture diagram (Checkpoint 2 deliverable)
│   ├── asr/                       # Whisper / faster-whisper integration
│   │   ├── transcribe.py          # audio file -> Transcript (text, language, timestamped segments)
│   │   └── config.py              # WHISPER_MODEL_SIZE / WHISPER_DEVICE / WHISPER_COMPUTE_TYPE
│   ├── tts/                        # Azure Speech integration
│   │   ├── synthesize.py           # text -> WAV file via Azure Speech
│   │   └── config.py               # AZURE_SPEECH_KEY / AZURE_SPEECH_REGION / AZURE_SPEECH_VOICE
│   ├── api/                         # FastAPI backend for the frontend
│   │   ├── app.py                   # GET /health, POST /transcribe, /query, /speak
│   │   ├── config.py                # API_HOST / API_PORT / API_CORS_ORIGINS
│   │   └── README.md                # endpoint schemas
│   └── eval/                        # RAG eval harness (Checkpoint 2 deliverable)
│       ├── golden_queries.json      # hand-picked cases, one per retrieval-routing behavior
│       ├── run_eval.py              # runs cases against the real graph, checks + scores them
│       └── README.md                # methodology + latest real results (incl. a bug it caught)
├── notebooks/
│   ├── 00_eda.ipynb              # exploratory analysis justifying ingestion choices
│   └── 01_data_ingestion.ipynb   # step-through version of the pipeline
├── frontend/                     # React (Vite) UI — mic capture, transcript, comparison table
│   └── src/
│       ├── App.jsx                # orchestrates the record -> transcribe -> query -> answer flow
│       ├── api.js                 # fetch wrappers for src/api's three endpoints
│       └── components/
│           ├── Recorder.jsx       # mic capture (record) + file upload
│           ├── AgentTrace.jsx     # agent step log
│           ├── ComparisonTable.jsx # evidence table
│           └── AnswerPanel.jsx    # answer text, citations, Play TTS button
├── prompts/                      # System prompts for router/planner/answerer (read directly by src/agents)
├── data/
│   ├── raw/                      # raw Kaggle CSV(s)
│   ├── processed/                # products.parquet
│   └── chroma_db/                # persistent Chroma collection
├── logs/
│   └── mcp_requests.log          # MCP tool call log (timestamp, tool, query, doc_ids/source_urls)
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

1. Clone the repository and install dependencies for the backend (`src/agents/`, `src/mcp_server/`, `src/asr/`, `src/tts/` — one `requirements.txt` at the repo root covers all of `src/`) and frontend (`frontend/`).
2. Copy `.env.example` to `.env` and populate:
   - LLM provider + API key (Claude API)
   - Web search API key (Serper.dev or Brave Search API)
   - Azure Speech credentials
   - Vector DB config — `CHROMA_DIR`, `CHROMA_COLLECTION` (see [Data Ingestion](#data-ingestion))
3. Run the data ingestion pipeline (below) to build the Chroma index from the Amazon Product Dataset 2020.
4. Start the MCP server (stdio or HTTP/SSE) — see [MCP Server](#mcp-server).
5. Start the backend agent graph service and the React frontend.
6. Record or upload a voice query in the UI to trigger the full pipeline.

## Data Ingestion

Turns the raw Kaggle Amazon Product Dataset 2020 dump into the Chroma
vector index `rag.search` queries — the full dataset (10,002 products, all
categories), not a single-category slice; `category_top_level` is stored
as filterable metadata instead. Embeddings run fully local, no API key
needed beyond a Kaggle token for the initial download.

```bash
cd src/ingestion
python download_data.py && python clean.py && python build_index.py
```

Full pipeline stages, schema, column mapping, category organization, and
known data-quality caveats: [src/ingestion/README.md](src/ingestion/README.md).

## MCP Server

Built with the MCP Python SDK (`mcp==2.0.0`), exposing `rag.search` (wraps
`RagRetriever` from [Data Ingestion](#data-ingestion)) and `web.search`
(Serper.dev Shopping, falling back to domain-allowlisted/`robots.txt`-respecting
organic search, or Brave; cached, rate-limited) to the LangGraph agent
graph. Runs over stdio by default, or HTTP (SSE / streamable-http) via
`.env`.

```bash
cd src/mcp_server
python server.py
```

Full tool schemas, config, and enforcement details: [src/mcp_server/README.md](src/mcp_server/README.md).

## Agent Graph

LangGraph state graph (`langgraph==1.2.10`) implementing the
Router → Planner → Retriever → Answerer/Critic flow from
[System Architecture](#system-architecture). Every node calls Claude
(`anthropic==0.120.2`) through a single `llm_client` module, forcing
structured output via native tool-calling — including the Retriever, which
uses a small relevance-judgment call to decide whether the private catalog
search genuinely satisfies the request before falling back to live search
(see [Retrieval routing](src/agents/README.md#retrieval-routing)). The
Retriever never calls a search API directly, though — it talks only to the
[MCP Server](#mcp-server) as a client, over the same `rag.search`/`web.search`
tools.

The graph also supports follow-ups: the Router resolves a follow-up
against the conversation's prior turns (see
[src/agents/README.md](src/agents/README.md#graph)'s Follow-ups note),
and a pure selection over already-shown results ("the cheapest one")
skips retrieval entirely rather than re-querying.

```bash
cd src/agents
python main.py "eco-friendly stainless steel cleaner under fifteen dollars"
```

Full graph diagram, grounding-enforcement details, and prompt mapping:
[src/agents/README.md](src/agents/README.md). System prompts themselves are
in [prompts/](prompts/), per [Prompt Disclosure](#prompt-disclosure).

## RAG Evaluation

A small hand-picked golden query set (`src/eval/golden_queries.json`) run
against the real graph — real Claude, real Chroma, real web search — with
automatic checks for category-routing accuracy, correct web-fallback
triggering, price-constraint compliance, and citation grounding.

```bash
cd src/eval
python run_eval.py
```

This isn't just a checklist: the first run caught a real bug (rejected
private catalog hits were leaking into the Answerer's evidence even after
being judged irrelevant) that got fixed as a direct result. Methodology,
per-case rationale, and the actual bug it found:
[src/eval/README.md](src/eval/README.md).

A second, complementary eval (`src/eval/proofagent_eval.py`) uses the
third-party [proofagent-harness](https://pypi.org/project/proofagent-harness/)
library to adversarially probe the same live agent graph — jailbreaks,
injected fake context, requests to state unverified facts as certain —
scoring manipulation-resistance, hallucination-resistance, and safety.
It caught a real crash bug (an unhandled Serper API error was taking down
the whole agent turn) that's now fixed; see the same eval README for the
full writeup and latest SILVER-certified results.

## Voice Pipeline

Fragment-based (record/upload → transcribe; synthesize → play), per
[System Architecture](#system-architecture):

- **`src/asr/transcribe.py`** — Whisper via `faster-whisper` (`WHISPER_MODEL_SIZE`
  in `.env`, default `small`). Language is auto-detected, not forced. Returns
  full text plus timestamped segments.
- **`src/tts/synthesize.py`** — Azure Speech (`AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`/
  `AZURE_SPEECH_VOICE` in `.env`). Synthesizes to a WAV file; the caller
  decides how to play it back.
- **`src/agents/voice_main.py`** — ties both to the [Agent Graph](#agent-graph):
  audio in → `transcribe()` → graph → `synthesize()` → audio out.

```bash
cd src/agents
python voice_main.py path/to/question.wav response.wav
```

`src/asr` and `src/tts` each have their own `config.py` (bare-imported by
name, matching `src/ingestion`'s convention); `voice_main.py` loads both
into the `src/agents` process without them colliding, the same way
`src/mcp_server/rag_tool.py` loads `src/ingestion` — see that file's
docstring for why a plain `sys.path` insert isn't enough here.

## Backend API

FastAPI service (`src/api/app.py`) exposing ASR → agent graph → TTS over
HTTP, so the [frontend](#user-interface) has something to call — `main.py`/
`voice_main.py` are CLI-only. Endpoints map 1:1 to the UI feature list:
mic upload → `POST /transcribe`, live transcript/agent step log/comparison
table/citations → `POST /query`, "Play TTS" button → `POST /speak`.

```bash
cd src/api
python app.py
```

The agent graph and its MCP client are built once at startup (FastAPI
`lifespan`) and reused across requests. Full endpoint schemas:
[src/api/README.md](src/api/README.md).

## Frontend

React (Vite) app in `frontend/`, calling [Backend API](#backend-api) via
`fetch`. Each component maps to one item in the
[User Interface](#user-interface) feature list:

| Feature | Component |
|---|---|
| Mic capture (record/upload) | `Recorder.jsx` — `MediaRecorder` for recording, a file input as a fallback |
| Live transcript | `App.jsx` — shown as soon as `/transcribe` returns |
| Agent step log | `AgentTrace.jsx` — renders `/query`'s `trace` array |
| Comparison table | `ComparisonTable.jsx` — renders `/query`'s `evidence` array |
| Citations | `AnswerPanel.jsx` |
| Play TTS button | `AnswerPanel.jsx` — calls `/speak` only when clicked, not automatically |

`App.jsx` also accepts typed text as an alternative to voice (skips
`/transcribe`, goes straight to `/query`) — useful for testing without a
working microphone.

**Follow-ups**: `App.jsx` keeps the last few turns (transcript, intent,
evidence, answer) and sends them along with `/query` as `history`, so a
follow-up asked through the exact same mic/text input ("the cheapest
one", "what about under $10") is resolved against the previous turn
instead of starting from nothing — see [Agent Graph](#agent-graph)'s
Follow-ups note for how the Router/Retriever handle it. "New Question"
clears the conversation and starts fresh.

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL if the API isn't on localhost:8080
npm run dev
```

Requires [Backend API](#backend-api) running separately. `VITE_API_BASE_URL`
must be in `API_CORS_ORIGINS` (`.env` at the repo root) for the browser to
be allowed to call it — verified directly: a `POST /query` from origin
`http://localhost:5173` (Vite's default dev port, `API_CORS_ORIGINS`'s
default) returns `access-control-allow-origin: http://localhost:5173`.

## Safety Notes

- Domain allowlist and `robots.txt` enforced for `web.search`'s organic-search fallback (arbitrary URLs from the open web); its Google Shopping results are a licensed, curated commercial product feed via Serper's API and are exempt from both — see [src/mcp_server/README.md](src/mcp_server/README.md#websearch) for why the two need different treatment
- No unsafe chemical or product-safety advice generated. Safety concerns raised in a request are extracted by the Router into `intent.safety_flags`, echoed into the UI's agent step log so a flagged request is *visibly* flagged, and acted on by the Answerer under the Safety rules in [`prompts/answerer_system.md`](prompts/answerer_system.md): a flagged concern must be addressed in the answer and grounded in the evidence like any other claim; a safety property the evidence doesn't actually establish must be reported as unconfirmed rather than reassured away; and workarounds for a hazard the user raised (mixing, diluting, off-label use) are never suggested — recommend a product or decline, and point at the manufacturer's guidance
- No secrets logged; only request/response metadata (timestamp, source URL) is recorded
- Brand and ingredient fields are empty in the private catalog (see [Known data-quality limitations](src/ingestion/README.md#known-data-quality-limitations)); the Answerer agent must not fabricate these facts and should surface `None`/"not available" rather than guessing
- No rating data exists in the private catalog; rating-based comparisons should rely on `web.search` results only, clearly attributed as live/external data

## Milestones

- **Checkpoint 1 (Week 6):** One-page proposal (problem, data slice, tools), ingestion notebook, brief related work
- **Checkpoint 2 (Week 8):** Architecture diagram (graph + MCP calls), UI wireframe, RAG eval plan, MCP README (schemas)
- **Final (Week 10):** Live demo (≤7 min); clean repository with README and build scripts for index & MCP server; short presentation

## Presentation

Slide-by-slide outline of the final deck — architecture walkthrough, the
two live-demo queries (chosen to show the relevance-check/web-fallback
path, not just the happy path), eval results, and honest limitations:
[presentation/slide_builder_outline.md](presentation/slide_builder_outline.md).
The built deck lives in the same folder.

## Prompt Disclosure

All key prompts are in `prompts/`, mapped to the LangGraph node that reads
them (each node loads its prompt file directly at import time — the file
*is* the runtime prompt, not a copy kept in sync by hand):

| file | node |
|---|---|
| `router_system.md` | `src/agents/router.py` |
| `planner_system.md` | `src/agents/planner.py` |
| `retriever_system.md` | `src/agents/retriever.py` (relevance judgment gating the web-search fallback — see [Agent Graph's Retrieval routing](src/agents/README.md#retrieval-routing)) |
| `answerer_system.md` | `src/agents/answerer.py` |
