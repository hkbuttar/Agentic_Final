"""Voice-to-voice CLI: recorded/uploaded audio -> transcript -> agent graph
-> spoken answer. Ties together src/asr, src/agents (this dir), and
src/tts — the fragment-based pipeline from the top-level README.

Usage:
    cd src/agents
    python voice_main.py path/to/question.wav [output.wav]

Requires ANTHROPIC_API_KEY and AZURE_SPEECH_KEY/AZURE_SPEECH_REGION in
.env, and the ingestion pipeline already run.
"""
import sys
from pathlib import Path
from typing import Any

_SRC_DIR = Path(__file__).resolve().parents[1]


def _load_sibling(dir_name: str, module_name: str) -> Any:
    """Import `module_name` from a sibling flat-script directory (src/asr,
    src/tts). Those directories import their own config.py by bare name
    (`from config import ...`), which would collide with this directory's
    own config.py if both ended up cached in sys.modules under "config" at
    once — swap it out for the duration of the import, then restore it.
    Same trick src/mcp_server/rag_tool.py uses for src/ingestion.
    """
    original_config = sys.modules.pop("config", None)
    sibling_dir = str(_SRC_DIR / dir_name)
    sys.path.insert(0, sibling_dir)
    try:
        return __import__(module_name)
    finally:
        sys.path.remove(sibling_dir)
        sys.modules.pop("config", None)
        if original_config is not None:
            sys.modules["config"] = original_config


_transcribe_module = _load_sibling("asr", "transcribe")
_synthesize_module = _load_sibling("tts", "synthesize")

transcribe = _transcribe_module.transcribe
synthesize = _synthesize_module.synthesize

import asyncio  # noqa: E402

from graph import build_graph  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from mcp_client import MCPToolClient  # noqa: E402


async def run_voice_query(audio_in_path: str, audio_out_path: str) -> dict:
    result = transcribe(audio_in_path)
    print(f"[asr] ({result.language}, p={result.language_probability:.2f}) {result.text}")

    llm = LLMClient()
    async with MCPToolClient() as mcp_client:
        graph = build_graph(llm, mcp_client)
        state = await graph.ainvoke({"transcript": result.text, "trace": []})

    for line in state.get("trace", []):
        print("-", line)

    answer = state.get("answer", "")
    print(f"[answerer] {answer}")

    synthesize(answer, audio_out_path)
    print(f"[tts] wrote {audio_out_path}")

    return state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python voice_main.py <input.wav> [output.wav]", file=sys.stderr)
        raise SystemExit(1)

    audio_in = sys.argv[1]
    audio_out = sys.argv[2] if len(sys.argv) > 2 else "response.wav"
    asyncio.run(run_voice_query(audio_in, audio_out))
