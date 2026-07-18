"""Swappable embedding backends, selected via EMBEDDING_PROVIDER env var
so the pipeline stays model-agnostic per the project's LLM-choice requirement."""
from abc import ABC, abstractmethod

from config import EMBEDDING_PROVIDER, LOCAL_EMBEDDING_MODEL, OPENAI_EMBEDDING_MODEL


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, show_progress_bar=False, batch_size=64).tolist()


class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, model_name: str = OPENAI_EMBEDDING_MODEL):
        from openai import OpenAI

        self._client = OpenAI()
        self._model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model_name, input=texts)
        return [item.embedding for item in response.data]


def get_embedder(provider: str = EMBEDDING_PROVIDER) -> EmbeddingProvider:
    if provider == "local":
        return LocalEmbedding()
    if provider == "openai":
        return OpenAIEmbedding()
    raise ValueError(f"unknown EMBEDDING_PROVIDER: {provider!r}")
