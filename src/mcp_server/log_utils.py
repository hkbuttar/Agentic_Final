"""Request/response logging for MCP tool calls.

Only timestamp, tool name, query, and result source identifiers (URLs for
web.search, doc_ids for rag.search) are recorded — never API keys or full
response bodies, per the Safety Notes in the top-level README.
"""
import json
import time

from config import LOG_PATH


def log_event(tool: str, **fields) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": time.time(), "tool": tool, **fields}
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")
