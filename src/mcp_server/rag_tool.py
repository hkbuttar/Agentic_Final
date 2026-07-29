"""rag.search — thin wrapper around ingestion's RagRetriever.

src/ingestion is a flat script directory: its modules import each other by
bare name (`from config import ...`), expecting itself to be on sys.path.
src/mcp_server/ has its own unrelated config.py, so a plain sys.path insert
would collide — whichever `config` module gets imported first "wins" and
poisons the other. _import_retriever() swaps sys.modules['config'] out for
the duration of the ingestion import, then restores it, so both config.py
files can coexist.
"""
import sys
from pathlib import Path
from typing import Optional

_INGESTION_DIR = Path(__file__).resolve().parents[1] / "ingestion"


def _import_retriever():
    original_config = sys.modules.pop("config", None)
    sys.path.insert(0, str(_INGESTION_DIR))
    try:
        import retriever as ingestion_retriever

        return ingestion_retriever
    finally:
        sys.path.remove(str(_INGESTION_DIR))
        sys.modules.pop("config", None)
        if original_config is not None:
            sys.modules["config"] = original_config


_ingestion_retriever = _import_retriever()
RagRetriever = _ingestion_retriever.RagRetriever
build_where = _ingestion_retriever.build_where

from log_utils import log_event  # noqa: E402

_retriever: Optional[RagRetriever] = None


def _get_retriever() -> RagRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RagRetriever()
    return _retriever


def rag_search(
    query: str,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    brand: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    where = build_where(max_price=max_price, min_rating=min_rating, brand=brand)
    hits = _get_retriever().search(query, k=k, where=where)
    log_event("rag.search", query=query, doc_ids=[h["doc_id"] for h in hits])
    return hits
