import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # stdio | sse | streamable-http
MCP_HTTP_HOST = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
MCP_HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8000"))

WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "serper")  # serper | brave
SERPER_API_KEY = os.getenv("SERPER_API_KEY") or None
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY") or None

WEB_SEARCH_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.getenv(
        "WEB_SEARCH_ALLOWED_DOMAINS",
        "amazon.com,walmart.com,target.com,bestbuy.com,homedepot.com",
    ).split(",")
    if d.strip()
]
ROBOTS_USER_AGENT = os.getenv("ROBOTS_USER_AGENT", "AgenticVoiceAssistantBot/1.0")

WEB_SEARCH_CACHE_TTL_SECONDS = float(os.getenv("WEB_SEARCH_CACHE_TTL_SECONDS", "120"))
WEB_SEARCH_RATE_LIMIT_CALLS = int(os.getenv("WEB_SEARCH_RATE_LIMIT_CALLS", "20"))
WEB_SEARCH_RATE_LIMIT_PERIOD_SECONDS = float(
    os.getenv("WEB_SEARCH_RATE_LIMIT_PERIOD_SECONDS", "60")
)

LOG_PATH = PROJECT_ROOT / "logs" / "mcp_requests.log"
