"""Local embedding backend via sentence-transformers.
Runs on-device (CPU/MPS/CUDA), no API key needed. Default model is
all-MiniLM-L6-v2 (22M params, 384-dim) — small enough to embed the full
slice in a few seconds; Qwen's own embedding line only goes down to 0.6B,
which is much slower for no accuracy benefit at this dataset size."""
from config import EMBEDDING_MODEL


class LocalEmbedding:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, show_progress_bar=False, batch_size=64).tolist()


def get_embedder() -> LocalEmbedding:
    return LocalEmbedding()
