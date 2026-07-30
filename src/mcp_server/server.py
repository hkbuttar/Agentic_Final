"""MCP server exposing rag.search and web.search to the LangGraph agent
graph. Run with `python server.py` from this directory (or `cd mcp_server &&
python server.py`) — transport is stdio by default, sse/streamable-http via
MCP_TRANSPORT in .env. See README.md in this directory for tool schemas.
"""
from typing import Optional

from mcp.server.mcpserver import MCPServer

from config import MCP_HTTP_HOST, MCP_HTTP_PORT, MCP_TRANSPORT
from rag_tool import rag_search
from web_tool import web_search

server = MCPServer("product-discovery")


@server.tool(name="rag.search")
def rag_search_tool(
    query: str,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    """Vector + metadata search over the full private product catalog.

    Preferred for factual/catalog questions. `category` filters exactly
    against the top-level category (e.g. "Home & Kitchen", "Toys & Games")
    — pass it when the user's request names or clearly implies a category,
    omit it to search across all categories. Returns up to k ranked hits:
    {sku, title, price, rating, brand, category, category_top_level,
    ingredients, model_number, doc_id, score}. `ingredients` and `rating`
    are None for every product in this catalog (see top-level README's
    Known data-quality limitations) — do not treat None as "value unknown,
    ask again."
    """
    return rag_search(query, max_price=max_price, min_rating=min_rating, brand=brand, category=category, k=k)


@server.tool(name="web.search")
def web_search_tool(query: str, k: int = 5) -> list[dict]:
    """Live web search, for current price/availability/"now"/"latest"
    questions the private catalog can't answer.

    Domain-allowlisted and robots.txt-respecting: results outside the
    configured allowlist or disallowed by the source site's robots.txt are
    silently dropped before reaching the agent. Cached (TTL from config) and
    rate-limited; raises on quota exhaustion rather than returning partial
    results silently. Returns up to k hits:
    {title, url, snippet, price, availability} — price/availability are
    currently always None (not parsed from snippet yet).
    """
    return web_search(query, k=k)


if __name__ == "__main__":
    server.run(transport=MCP_TRANSPORT, host=MCP_HTTP_HOST, port=MCP_HTTP_PORT)
