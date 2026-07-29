# MCP Tool Server

Exposes two tools — `rag.search` and `web.search` — to the LangGraph agent
graph (`agents/`), built with the [MCP Python SDK](https://modelcontextprotocol.io)
(`mcp==2.0.0`). Tool discovery is via JSON schema, generated automatically
from each tool function's type hints and docstring.

## Running

```bash
pip install -r ../../requirements.txt   # from src/mcp_server/, or -r requirements.txt from repo root
cd src/mcp_server
python server.py
```

Transport defaults to **stdio** (for a local agent-graph process that spawns
this server directly). Set `MCP_TRANSPORT=sse` or `MCP_TRANSPORT=streamable-http`
in `.env` to run it as a standalone HTTP server instead (`MCP_HTTP_HOST` /
`MCP_HTTP_PORT`, default `127.0.0.1:8000`).

## Tools

### `rag.search`

Vector + metadata search over the private product catalog (`src/ingestion` →
`data/chroma_db/`). Preferred for factual/catalog questions. Requires the
[ingestion pipeline](../../README.md#data-ingestion) to have been run first —
this tool imports `RagRetriever` from `src/ingestion/retriever.py` directly
and opens the same Chroma collection.

**Input**

| field | type | required | notes |
|---|---|---|---|
| `query` | string | yes | natural-language search text |
| `max_price` | number | no | filter: `price <= max_price` |
| `min_rating` | number | no | filter: `rating >= min_rating` (always empty in this catalog slice — see below) |
| `brand` | string | no | exact-match filter (always empty in this catalog slice) |
| `k` | integer | no, default 5 | number of hits to return |

**Output** — list of up to `k` hits:

```json
{
  "sku": "...", "title": "...", "price": 12.49, "rating": null,
  "brand": null, "ingredients": null, "model_number": "...",
  "doc_id": "...", "score": 0.83
}
```

`brand`, `ingredients`, and `rating` are `None` for every product in this
catalog slice — see the top-level README's
[Known data-quality limitations](../../README.md#known-data-quality-limitations).
The Answerer agent must not fabricate these facts.

### `web.search`

Live web search via Serper.dev or Brave Search (`WEB_SEARCH_PROVIDER` in
`.env`). Used when the router/planner decide the request needs current
price, availability, or "latest" info the private catalog can't answer.

**Input**

| field | type | required | notes |
|---|---|---|---|
| `query` | string | yes | search text |
| `k` | integer | no, default 5 | number of results to return |

**Output** — list of up to `k` results:

```json
{
  "title": "...", "url": "...", "snippet": "...",
  "price": null, "availability": null
}
```

`price`/`availability` are always `null` for now — not yet parsed out of
the snippet text; comparisons should treat this as "unknown," not "$0" /
"unavailable."

**Enforcement, before any result is returned:**

- **Domain allowlist** — `WEB_SEARCH_ALLOWED_DOMAINS` in `.env` (comma-separated
  registrable domains; subdomains of a listed domain are allowed too). Results
  outside the list are dropped silently.
- **`robots.txt`** — fetched per-origin (cached 1h) and checked with
  `can_fetch(ROBOTS_USER_AGENT, url)`. A missing/unreachable `robots.txt` is
  treated as allow-all, matching standard convention.
- **Cache** — successful queries cached `WEB_SEARCH_CACHE_TTL_SECONDS`
  (default 120s, spec range 60–300s), keyed by exact query string.
- **Rate limit** — sliding window, `WEB_SEARCH_RATE_LIMIT_CALLS` per
  `WEB_SEARCH_RATE_LIMIT_PERIOD_SECONDS` (default 20/60s). Raises
  `WebSearchError` when exceeded rather than returning a partial/empty
  result silently — the caller should treat that as "try again shortly,"
  not "no results."

## Logging

Every `rag.search` / `web.search` call appends one JSON line to
`../../logs/mcp_requests.log`: `{timestamp, tool, query, doc_ids | source_urls}`.
No API keys or full response bodies are logged, per the top-level README's
[Safety Notes](../../README.md#safety-notes).

## Files

| file | role |
|---|---|
| `server.py` | registers both tools on an `MCPServer` instance, runs the chosen transport |
| `rag_tool.py` | thin wrapper around `src/ingestion/retriever.RagRetriever` |
| `web_tool.py` | Serper/Brave client + domain allowlist + robots.txt + cache + rate limit |
| `config.py` | reads all of the above from `.env` |
| `cache.py` | small in-process TTL cache |
| `rate_limit.py` | sliding-window rate limiter |
| `log_utils.py` | appends request/response log lines |
