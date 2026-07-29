import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY") or None
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION") or None
AZURE_SPEECH_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-US-AriaNeural")
