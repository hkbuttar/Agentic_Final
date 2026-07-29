import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

PROMPTS_DIR = PROJECT_ROOT / "prompts"
MCP_SERVER_DIR = PROJECT_ROOT / "src" / "mcp_server"
