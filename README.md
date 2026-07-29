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
- **`rag.search(query, filters)`** — vector + metadata search over the Amazon 2020 slice → returns `{sku, title, price, rating, brand?, ingredients?, doc_id}`.

All requests/responses are logged with timestamp and source URL. A domain allowlist is enforced and `robots.txt`/ToS are respected.

### ASR (Speech-to-Text)

- **Model:** Whisper (`faster-whisper` for lower CPU latency)
- **Mode:** Fragment-based — record → upload WAV/MP3 → transcribe
- **Output:** Transcript with timestamps; basic multilingual accent handling

### TTS (Text-to-Speech)

- **Provider:** Azure Speech (current)
- **Output:** ≤15-second spoken summary aligned to on-screen citations

### Retrieval Corpus

- **Source:** Amazon Product Dataset 2020 (Kaggle), curated slice
- **Schema:** `products.parquet` — `id, title, brand, category, price, rating, features, ingredients`
- **Embeddings:** Title + features + ingredients via `sentence-transformers` (`all-MiniLM-L6-v2`); stored in a persistent Chroma collection (cosine distance)
- **Normalization:** Units normalized (e.g., price per oz) for fair comparison

Full ingestion pipeline, schema decisions, and known data-quality caveats are documented below in [Data Ingestion](#data-ingestion).

### User Interface

- **Framework:** React, deployed via GitHub → Vercel
- **Features:** Mic capture (record/upload), live transcript, agent step log, comparison table, citations, Play TTS button

## LLM & Configuration

- **Provider:** Claude API (Anthropic), model-agnostic by design — swappable via `.env`/config (provider + model name) through a single `llm_client` module
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
│   │   └── config.py             # ingestion env/config (CHROMA_DIR, CATEGORY_TOP_LEVEL, ...)
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
│   └── api/                        # FastAPI backend for the frontend
│       ├── app.py                  # GET /health, POST /transcribe, /query, /speak
│       ├── config.py                # API_HOST / API_PORT / API_CORS_ORIGINS
│       └── README.md                # endpoint schemas
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
   - Vector DB / category config (see [Data Ingestion](#data-ingestion))
3. Run the data ingestion pipeline (below) to build the Chroma index from the Amazon 2020 dataset slice.
4. Start the MCP server (stdio or HTTP/SSE) — see [MCP Server](#mcp-server).
5. Start the backend agent graph service and the React frontend.
6. Record or upload a voice query in the UI to trigger the full pipeline.

## Data Ingestion

Ingestion pipeline for the voice-to-voice product discovery assistant. Turns the raw Kaggle dump into a Chroma vector index that the `rag.search` MCP tool queries.

### Ingestion Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # embeddings run fully local, no API key needed
```

Requires a Kaggle API token at `~/.kaggle/kaggle.json` (from kaggle.com/settings → API → Create New Token).

### Pipeline

Run in order (or step through `notebooks/00_eda.ipynb` then `notebooks/01_data_ingestion.ipynb`):

```bash
cd src/ingestion
python download_data.py    # kagglehub -> data/raw/*.csv
python inspect_schema.py   # confirm real column names (see notebooks/00_eda.ipynb for the full analysis)
python clean.py            # data/raw -> data/processed/products.parquet
python build_index.py      # products.parquet -> data/chroma_db/ (Chroma collection)
python retriever.py        # sanity-check query
```

| Stage | Input | Output | What it does |
|---|---|---|---|
| `download_data.py` | Kaggle | `data/raw/*.csv` | Fetches `promptcloud/amazon-product-dataset-2020` via `kagglehub` |
| `inspect_schema.py` | `data/raw/*.csv` | stdout | Prints real column names/dtypes |
| `clean.py` | `data/raw/*.csv` | `data/processed/products.parquet` | Reads the known columns directly (see [Column names](#column-names)), parses price, strips boilerplate text, filters to the category slice, derives `price_per_unit` |
| `build_index.py` | `products.parquet` | `data/chroma_db/` | Embeds `title + features + ingredients` with `all-MiniLM-L6-v2`, upserts into a persistent Chroma collection (cosine distance) with filterable metadata |
| `retriever.py` | `data/chroma_db/` | — | `RagRetriever.search(query, k, where)` — the function the `rag.search` MCP tool should import directly |

`notebooks/00_eda.ipynb` is the exploratory pass that justifies every choice below (column completeness, category distribution, price distribution) — run it first if you want the reasoning, not just the conclusions.

Verified end-to-end against the real download: 10,002 raw rows → 708 products in the Home & Kitchen slice → indexed and queryable (see [Known data-quality limitations](#known-data-quality-limitations)).

### Schema

`products.parquet` columns: `id, title, brand, category, price, rating, ingredients, model_number, features, unit_qty, unit, price_per_unit, url, doc_id`.

`doc_id` is the stable citation key used by the Answerer agent and surfaced in the UI's citation panel.

### Column names

`clean.py` reads these raw CSV columns directly by name — no alias/fuzzy matching, since this file's schema is fixed and already confirmed via `inspect_schema.py`:

| target field | raw column |
|---|---|
| `id` | `Uniq Id` |
| `title` | `Product Name` |
| `brand` | `Brand Name` (always empty — see below) |
| `category` | `Category` |
| `price` | `Selling Price` ($-anchored parse — see below) |
| `ingredients` | `Ingredients` (always empty — see below) |
| `model_number` | `Model Number` (82% populated, not embedded, kept as a lookup/citation aid) |
| `url` | `Product Url` |
| `features` | `About Product` + `Technical Details`, boilerplate-stripped (see below) |
| `unit_qty` / `unit` | parsed from `Product Name` / `Shipping Weight` / `About Product` |
| `rating` | none — no such column exists in this file, hardcoded to `None` |

If the team swaps in a different PromptCloud CSV with a different schema, update the `COL_*` constants at the top of `clean.py` — run `inspect_schema.py` against the new file first.

**Why `Technical Details` instead of `Product Specification`?** `Product Specification` looked useful at first glance but turned out to be ~100% boilerplate — every populated row is just `Shipping Weight: X (View shipping rates and policies)|ASIN: Y|#rank in Z` with the words run together (no spaces: `ProductDimensions:5.7x4.9x1.2inches`), which adds noise, not signal, to an embedding. `Technical Details` (92% populated) has genuine free-text product descriptions instead, so it's what actually goes into `features`.

### Category slice

`CATEGORY_TOP_LEVEL` in `.env` (default `Home & Kitchen`) is matched exactly against the top-level segment of each product's `|`-delimited `Category` breadcrumb — e.g. the `Home & Kitchen` in `Home & Kitchen | Bedding | ...`.

**Do products carry multiple categories?** Checked directly in `notebooks/00_eda.ipynb` / `_matches_category`'s docstring: no. Every `Category` value in this file is a single hierarchical breadcrumb (top → leaf, 1–6 levels deep, `|`-delimited) — there's no second delimiter (`;`, `||`, newline) joining independent category assignments, no row repeats a top-level segment, and every `Uniq Id` appears exactly once (no duplicate rows representing the same product filed under a second category). Matching the top-level breadcrumb segment is therefore a correct 1:1 filter for this file, not a lossy approximation of a many-to-many relationship. (Caveat: a product can still be topically relevant to Home & Kitchen while filed under a different top-level, e.g. a kids' play-kitchen set under Toys & Games — that's a taxonomy/relevance tradeoff, not a parsing bug.)

**Why not Household Cleaning, per the original spec's suggestion?** The actual `promptcloud/amazon-product-dataset-2020` file `kagglehub` returns (`marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv`, 10,002 rows) is a general marketplace sample dominated by Toys & Games (6,662 rows). Only 23 rows fall under Health & Household at all, and just 7 have "cleaning" anywhere in their category breadcrumb — too thin for a meaningful comparison demo. Home & Kitchen (708 rows: Home Décor, Furniture, Bedding, Event & Party Supplies, Kitchen & Dining) is the closest well-populated category to the spec's product-discovery use case. Swap `CATEGORY_TOP_LEVEL` back to `Health & Household` (or any other top-level category) if the team decides a thinner, on-spec slice is preferable — the pipeline doesn't care which one you pick.

An earlier version of this filter matched the keyword "clean" against title/description text directly, which pulled in unrelated products (plush toys, blankets) because their marketing copy says things like "wipe clean" or "easy to clean." Matching only the structured category breadcrumb's top-level segment avoids that false-positive problem regardless of which category is chosen.

### Known data-quality limitations

Confirmed against the real downloaded file — worth stating explicitly in the writeup/safety notes:

- **Brand Name and Ingredients are 100% empty** across all 10,002 raw rows, not just this slice. The Answerer agent should not claim brand or ingredient facts for these products; `retriever.py` already returns `None` for both rather than fabricating a value.
- **No rating/review-count column exists** in this file at all (`clean.py` leaves `rating` as `None`). If the team wants ratings for the demo, either source a `reviews.parquet` from a different PromptCloud file or drop rating-based comparisons from the example queries.
- **Selling Price has ~4% garbage values** dataset-wide ("from 2 sellers", "Total price:", free-text shipping blurbs, "$8.25 - $31.95" ranges). `_parse_price` requires the value to start with `$` before extracting a number — this matters: an earlier, unanchored version of the parser mis-read "from 2 sellers" as $2.00 and pulled a random $5 out of an unrelated shipping-policy sentence. For genuine ranges ("$8.25 - $31.95"), the low end is used as the representative price.
- **`price_per_unit` is only derived when a quantity+unit** (oz, lb, ct, etc.) is parseable from the title/weight/description text — 597 of 708 rows (84%) in the current slice. `price` itself is populated for 695/708.
- **`About Product` / `Technical Details` contain recurring boilerplate** ("Make sure this fits by entering your model number." in 76% of rows, a return-policy blurb in 43% of `Technical Details` rows) that `clean.py` strips before building `features`, so it doesn't dilute the embedding for every product identically.
- **`Is Amazon Seller`** (Y/N, 100% populated) isn't currently surfaced — could be worth exposing as a trust signal if the Answerer agent wants to flag third-party vs. Amazon-fulfilled listings.

### Embedding backend

`all-MiniLM-L6-v2` via `sentence-transformers` (`embeddings.py`), runs fully local (CPU/MPS/CUDA) — no API key, no external calls. 22M params, 384-dim vectors, embeds the full 708-product slice in a few seconds. Override the model name with `EMBEDDING_MODEL` in `.env` if the team wants something different; `build_index.py`/`retriever.py` only depend on the `.embed(texts) -> list[list[float]]` interface, not on this model specifically.

**Why not Qwen?** Qwen's embedding line (Qwen3-Embedding) only ships in 0.6B/4B/8B — there's no smaller Qwen option, and 0.6B is ~30x the parameter count of MiniLM for no meaningful accuracy benefit at this dataset size (708 products). MiniLM is fast enough to rebuild the index from scratch in seconds during dev, which matters far more than marginal retrieval-quality gains here.

### Handing off to the MCP layer

`rag.search` should be a thin wrapper:

```python
from retriever import RagRetriever, build_where

retriever = RagRetriever()
retriever.search(query, k=5, where=build_where(max_price=15, min_rating=4.0, brand="Method"))
```

Returned dicts already match the `{sku, title, price, rating, brand, ingredients, doc_id}` contract from the project spec (plus `model_number` as an extra field).

## MCP Server

Built with the MCP Python SDK (`mcp==2.0.0`), exposing `rag.search` (wraps
`RagRetriever` from [Data Ingestion](#data-ingestion)) and `web.search`
(Serper.dev or Brave, domain-allowlisted, `robots.txt`-respecting, cached,
rate-limited) to the LangGraph agent graph. Runs over stdio by default, or
HTTP (SSE / streamable-http) via `.env`.

```bash
cd src/mcp_server
python server.py
```

Full tool schemas, config, and enforcement details: [src/mcp_server/README.md](src/mcp_server/README.md).

## Agent Graph

LangGraph state graph (`langgraph==1.2.10`) implementing the
Router → Planner → Retriever → Answerer/Critic flow from
[System Architecture](#system-architecture). Router/Planner/Answerer call
Claude (`anthropic==0.120.2`) through a single `llm_client` module, forcing
structured output via native tool-calling; the Retriever never calls a
search API directly — it talks only to the [MCP Server](#mcp-server) as a
client, over the same `rag.search`/`web.search` tools.

```bash
cd src/agents
python main.py "eco-friendly stainless steel cleaner under fifteen dollars"
```

Full graph diagram, grounding-enforcement details, and prompt mapping:
[src/agents/README.md](src/agents/README.md). System prompts themselves are
in [prompts/](prompts/), per [Prompt Disclosure](#prompt-disclosure).

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

- Domain allowlist enforced for `web.search`
- `robots.txt` / ToS respected for all live queries
- No unsafe chemical or product-safety advice generated
- No secrets logged; only request/response metadata (timestamp, source URL) is recorded
- Brand and ingredient fields are empty in the private catalog (see [Known data-quality limitations](#known-data-quality-limitations)); the Answerer agent must not fabricate these facts and should surface `None`/"not available" rather than guessing
- No rating data exists in the private catalog; rating-based comparisons should rely on `web.search` results only, clearly attributed as live/external data

## Milestones

- **Checkpoint 1 (Week 6):** One-page proposal (problem, data slice, tools), ingestion notebook, brief related work
- **Checkpoint 2 (Week 8):** Architecture diagram (graph + MCP calls), UI wireframe, RAG eval plan, MCP README (schemas)
- **Final (Week 10):** Live demo (≤7 min); clean repository with README and build scripts for index & MCP server; short presentation

## Prompt Disclosure

All key prompts are in `prompts/`, mapped to the LangGraph node that reads
them (each node loads its prompt file directly at import time — the file
*is* the runtime prompt, not a copy kept in sync by hand):

| file | node |
|---|---|
| `router_system.md` | `src/agents/router.py` |
| `planner_system.md` | `src/agents/planner.py` |
| `answerer_system.md` | `src/agents/answerer.py` |

The Retriever (`src/agents/retriever.py`) makes no LLM calls, so it has no
prompt file — it only calls `rag.search`/`web.search` via the MCP client.
