"""CLI entrypoint: run one query through the full agent graph.

Usage:
    cd src/agents
    python main.py "eco-friendly stainless steel cleaner under $15"

Requires ANTHROPIC_API_KEY in .env and the ingestion pipeline already run
(see top-level README's Data Ingestion section) so rag.search has an index
to query.
"""
import asyncio
import sys

from graph import build_graph
from llm_client import LLMClient
from mcp_client import MCPToolClient

_DEFAULT_TRANSCRIPT = "Recommend an eco-friendly stainless-steel cleaner under fifteen dollars."


async def run_query(transcript: str) -> dict:
    llm = LLMClient()
    async with MCPToolClient() as mcp_client:
        graph = build_graph(llm, mcp_client)
        return await graph.ainvoke({"transcript": transcript, "trace": []})


if __name__ == "__main__":
    transcript = " ".join(sys.argv[1:]) or _DEFAULT_TRANSCRIPT
    result = asyncio.run(run_query(transcript))

    for line in result.get("trace", []):
        print("-", line)
    print()
    print(result.get("answer"))
    print()
    for citation in result.get("citations", []):
        print(" *", citation)
