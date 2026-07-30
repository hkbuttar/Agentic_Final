"""Async MCP client — spawns src/mcp_server/server.py over stdio and
exposes rag.search / web.search as plain async methods. One MCPToolClient
is opened per graph run (or per process) and reused across node calls
rather than spawning a subprocess per tool call.
"""
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from config import MCP_SERVER_DIR


class MCPToolClient:
    def __init__(self):
        self._stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None

    async def __aenter__(self) -> "MCPToolClient":
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable, args=["server.py"], cwd=str(MCP_SERVER_DIR)
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._stack.aclose()
        self._stack = None
        self._session = None

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> list[dict]:
        assert self._session is not None, "MCPToolClient used outside 'async with'"
        result = await self._session.call_tool(tool_name, arguments)
        if result.is_error:
            text = "; ".join(getattr(block, "text", str(block)) for block in result.content)
            raise RuntimeError(f"{tool_name} failed: {text}")
        return result.structured_content["result"]

    async def rag_search(
        self,
        query: str,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        k: int = 5,
    ) -> list[dict]:
        args: dict[str, Any] = {"query": query, "k": k}
        if max_price is not None:
            args["max_price"] = max_price
        if min_rating is not None:
            args["min_rating"] = min_rating
        if brand is not None:
            args["brand"] = brand
        if category is not None:
            args["category"] = category
        return await self._call("rag.search", args)

    async def web_search(self, query: str, k: int = 5) -> list[dict]:
        return await self._call("web.search", {"query": query, "k": k})
