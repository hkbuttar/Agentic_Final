import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
# Render (and most PaaS hosts) inject PORT and require binding to it; API_PORT
# is the local-dev override (see .env). PORT wins when both are present.
API_PORT = int(os.getenv("PORT") or os.getenv("API_PORT", "8080"))
API_CORS_ORIGINS = [
    o.strip() for o in os.getenv("API_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
