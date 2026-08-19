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

Vector + metadata search over the full private product catalog, all
categories (`src/ingestion` → `data/chroma_db/`, 10,002 products).
Preferred for factual/catalog questions. Requires the
[ingestion pipeline](../ingestion/README.md) to have been run first —
this tool imports `RagRetriever` from `src/ingestion/retriever.py` directly
and opens the same Chroma collection.

**Input**

| field | type | required | notes |
|---|---|---|---|
| `query` | string | yes | natural-language search text |
| `max_price` | number | no | filter: `price <= max_price` |
| `min_rating` | number | no | filter: `rating >= min_rating` (always empty in this catalog — see below) |
| `brand` | string | no | exact-match filter (always empty in this catalog) |
| `category` | string | no | exact-match filter against `category_top_level` (e.g. `"Home & Kitchen"`, `"Toys & Games"`); omit to search across all categories — see [Category organization](../ingestion/README.md#category-organization) |
| `k` | integer | no, default 5 | number of hits to return |

**Output** — list of up to `k` hits:

```json
{
  "sku": "...", "title": "...", "price": 12.49, "rating": null,
  "brand": null, "brand_inferred": "LoftWorks",
  "category": "Home & Kitchen | Kitchen & Dining | ...",
  "category_top_level": "Home & Kitchen", "ingredients": null,
  "model_number": "...", "url": "https://www.amazon.com/dp/...",
  "doc_id": "...", "score": 0.83
}
```

`brand`, `ingredients`, and `rating` are `None` for every product in this
catalog — see the ingestion README's
[Known data-quality limitations](../ingestion/README.md#known-data-quality-limitations).
`brand_inferred` is a heuristic guess from the title (see
[Brand inference](../ingestion/README.md#brand-inference)), *not* verified
data — callers must not present it the same way as a real `brand` value.
`category_top_level` is `""` for the ~8% of products with no `Category`
value in the raw data (still searchable unfiltered, just won't match a
`category` filter). `url` is the product's real Amazon listing page —
populated for the vast majority of rows (`Product Url` in the raw CSV).
The Answerer agent must not fabricate the fields that are genuinely absent
(`brand`/`ingredients`/`rating`).

### `web.search`

Live search via Serper.dev (Google Shopping first, organic web search as
fallback) or Brave Search (organic only) — `WEB_SEARCH_PROVIDER` in `.env`.
Used when the router/planner decide the request needs current price,
availability, or "latest" info the private catalog can't answer — or, via
the [agent graph's relevance check](../agents/README.md#retrieval-routing),
whenever the private catalog simply doesn't have the right *kind* of
product.

**Why Shopping first:** organic search for a product query mostly surfaces
best-seller/category listing pages ("Best Throw Pillow Covers"), not
individual products with prices. Shopping returns actual product listings
(title, merchant, price). It's tried first, up to twice — the endpoint is
flaky, not just sparse: the same exact query has returned a full page of
results on one call and an empty list moments later, repeatedly, in
testing. Organic search only runs if both Shopping attempts come back
empty.

**Input**

| field | type | required | notes |
|---|---|---|---|
| `query` | string | yes | search text |
| `k` | integer | no, default 5 | number of results to return |

**Output** — list of up to `k` results:

```json
{
  "title": "...", "url": "...", "snippet": null,
  "price": 12.49, "availability": null,
  "brand": "West Elm", "rating": 4.5
}
```

`price`, `brand` (merchant name), and `rating` are populated for Shopping
results when Google has them; all three are always `null` for
organic-fallback results, which have no structured data to draw them
from — `snippet` is the inverse, populated only for organic results.
`availability` is always `null` — neither source provides it.

**Enforcement, before any result is returned:**

- **Domain allowlist + `robots.txt`** — apply to *organic* results only.
  `WEB_SEARCH_ALLOWED_DOMAINS` in `.env` (comma-separated registrable
  domains, subdomains included) drops anything outside the list;
  `robots.txt` is fetched per-origin (cached 1h) and checked with
  `can_fetch(ROBOTS_USER_AGENT, url)`, treating a missing/unreachable file
  as allow-all. **Shopping results skip both checks** — their `url` is a
  Google Shopping redirect, not the merchant's own domain, and the results
  come from a licensed commercial product feed via Serper's API contract
  rather than us crawling an arbitrary page, so there's nothing to check
  them against. See `web_tool.py`'s module docstring for the full reasoning.
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
No API keys or full response bodies are logged.

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
