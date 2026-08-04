"""FastAPI backend wrapping the voice pipeline: ASR (src/asr) -> agent
graph (src/agents) -> TTS (src/tts). Endpoints map directly to the
top-level README's UI feature list:

    mic upload            -> POST /transcribe
    live transcript, agent
    step log, comparison
    table, citations       -> POST /query
    "Play TTS" button      -> POST /speak

The agent graph and its MCP client are built once at startup (see
`lifespan`) and reused across requests, rather than spawning a fresh MCP
server subprocess per call.
"""
import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from config import API_CORS_ORIGINS

_SRC_DIR = Path(__file__).resolve().parents[1]


def _load_sibling(dir_name: str, module_name: str) -> Any:
    """Import `module_name` from a sibling flat-script directory (src/agents,
    src/asr, src/tts). Each has its own bare-imported config.py, which would
    collide with this directory's own config.py — swap sys.modules['config']
    out for the duration of the import, then restore it. Same trick as
    src/agents/voice_main.py and src/mcp_server/rag_tool.py.
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


_graph_module = _load_sibling("agents", "graph")
_transcribe_module = _load_sibling("asr", "transcribe")
_synthesize_module = _load_sibling("tts", "synthesize")

build_graph = _graph_module.build_graph
LLMClient = _graph_module.LLMClient
MCPToolClient = _graph_module.MCPToolClient
transcribe = _transcribe_module.transcribe
synthesize = _synthesize_module.synthesize
TTSError = _synthesize_module.TTSError


class _AppState:
    mcp_client: Optional[Any] = None
    graph: Optional[Any] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm = LLMClient()
    mcp_client = MCPToolClient()
    await mcp_client.__aenter__()
    _state.mcp_client = mcp_client
    _state.graph = build_graph(llm, mcp_client)
    try:
        yield
    finally:
        await mcp_client.__aexit__(None, None, None)


app = FastAPI(title="Product Discovery Voice Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe_endpoint(audio: UploadFile) -> dict:
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await audio.read())
        # transcribe() is a blocking, CPU-bound faster-whisper call — calling
        # it directly here would freeze this process's single event loop for
        # the full transcription, including /health, for as long as it takes.
        # On a memory/CPU-constrained host that's long enough to look like a
        # hung instance to an external health check.
        result = await asyncio.to_thread(transcribe, path)
    finally:
        os.unlink(path)

    return {
        "text": result.text,
        "language": result.language,
        "language_probability": result.language_probability,
        "segments": [asdict(s) for s in result.segments],
    }


class HistoryTurn(BaseModel):
    transcript: str
    intent: dict
    evidence: list[dict]
    answer: str


class QueryRequest(BaseModel):
    transcript: str
    history: list[HistoryTurn] = []


@app.post("/query")
async def query_endpoint(request: QueryRequest) -> dict:
    if _state.graph is None:
        raise HTTPException(status_code=503, detail="agent graph not ready")

    history = [turn.model_dump() for turn in request.history]
    result = await _state.graph.ainvoke(
        {"transcript": request.transcript, "history": history, "trace": []}
    )
    return {
        "transcript": request.transcript,
        "intent": result.get("intent"),
        "plan": result.get("plan"),
        "evidence": result.get("evidence"),
        "answer": result.get("answer"),
        "citations": result.get("citations"),
        "trace": result.get("trace"),
    }


class SpeakRequest(BaseModel):
    text: str


@app.post("/speak")
async def speak_endpoint(request: SpeakRequest) -> Response:
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        # synthesize() blocks on the Azure Speech SDK's own future (.get()) —
        # same event-loop-freezing concern as transcribe() above.
        await asyncio.to_thread(synthesize, request.text, path)
        audio_bytes = Path(path).read_bytes()
    except TTSError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        os.unlink(path)

    return Response(content=audio_bytes, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    from config import API_HOST, API_PORT

    uvicorn.run(app, host=API_HOST, port=API_PORT)
