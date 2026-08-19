# Backend API

FastAPI service wrapping ASR ([src/asr](../asr)) → agent graph
([src/agents](../agents)) → TTS ([src/tts](../tts)) over HTTP, for the
[frontend](../../frontend) to call. The agent graph and its MCP client are
built once at startup and reused across requests — no per-request subprocess
spawn.

## Running

```bash
cd src/api
python app.py
```

Or with auto-reload during development: `uvicorn app:app --reload --host 127.0.0.1 --port 8080`
(run from `src/api/`). Requires `ANTHROPIC_API_KEY`, `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`
in `.env`, and the ingestion pipeline already run.

## Endpoints

Each endpoint maps directly to one item in the top-level README's
[Interface](../../README.md#interface) feature list.

### `GET /health`

`{"status": "ok"}` — no dependencies checked, just confirms the process is up.

### `POST /transcribe`

Mic upload → transcript. `multipart/form-data`, field `audio` (WAV/MP3).

```json
{
  "text": "Recommend an eco-friendly stainless-steel cleaner under fifteen dollars.",
  "language": "en",
  "language_probability": 0.99,
  "segments": [{"start": 0.0, "end": 3.2, "text": "..."}]
}
```

### `POST /query`

Live transcript → agent step log, comparison table, citations. Runs the
full Router → Planner → Retriever → Answerer graph.

Request: `{"transcript": "...", "history": [...]}` — `history` is
optional (defaults to `[]`) and carries prior turns for follow-ups ("the
cheapest one", "what about under $10"): each entry is
`{"transcript": "...", "intent": {...}, "evidence": [...], "answer": "..."}`,
i.e. the shape of a previous `/query` response's own `transcript`/`intent`/
`evidence`/`answer` fields. The frontend builds this by appending each
response to a capped list (`frontend/src/App.jsx`'s `HISTORY_LIMIT`). See
[src/agents/README.md](../agents/README.md#graph)'s Follow-ups note for how
the Router/Retriever use it.

Response — the full `AgentState` (minus internal-only fields):

```json
{
  "transcript": "...",
  "intent": {"task": "...", "constraints": {...}, "wants_live_data": false, "safety_flags": []},
  "plan": {"sources": ["private"], "fields": [...], "criteria": [...]},
  "evidence": [{"sku": "...", "title": "...", "price": 10.99, "doc_id": "...", "source": "private", ...}],
  "answer": "...",
  "citations": [{"title": "...", "doc_id": "...", "url": null}],
  "trace": ["router: '...'", "planner: sources=['private']", "retriever: 5 evidence items (...)", "answerer: 2/2 citations grounded"]
}
```

`trace` is what the UI's agent step log renders directly; `evidence` is
what the comparison table renders; `citations` is already filtered to only
what's grounded in `evidence` (see [src/agents/README.md](../agents/README.md#grounding-enforcement)).

### `POST /speak`

"Play TTS" button. Request: `{"text": "..."}`. Response: raw `audio/wav`
bytes (not JSON) — the frontend plays this directly, e.g. via an `<audio>`
element's `src` set from a blob URL.

## Design notes

- **CORS**: `API_CORS_ORIGINS` in `.env` (comma-separated). Add the
  frontend's dev origin (and any other origin it's served from).
- **Why three endpoints instead of one**: matches the UI's actual
  interaction shape — a user records once, sees the transcript/answer, and
  only *optionally* clicks "Play" to hear it. Bundling ASR+graph+TTS into
  one call would force synthesizing audio the user might never play.
- **Sibling imports**: like `src/agents/voice_main.py`, this file loads
  `src/agents`, `src/asr`, and `src/tts` as sibling flat-script directories
  via `_load_sibling()`, swapping `sys.modules['config']` around each
  import so the four directories' own `config.py` files don't collide.
