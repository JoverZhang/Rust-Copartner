from __future__ import annotations

from typing import Protocol, List


class EmbeddingsProvider(Protocol):
    def embed_texts(self, texts: list[str], *, batch_size: int = 128) -> list[list[float]]:
        ...

    def dimension(self) -> int:
        ...


class MockEmbedProvider:
    """Mock embeddings provider for dry-run mode."""

    def __init__(self, dim: int = 384):
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: List[str], *, batch_size: int = 128) -> List[List[float]]:
        # Return zero vectors for dry-run
        return [[0.0] * self._dim for _ in texts]


class FastEmbedProvider:
    """LangChain FastEmbed-backed embeddings provider.

    Import is deferred to avoid model downloads during unit tests.
    """

    def __init__(self, model_name: str):
        from langchain_community.embeddings import FastEmbedEmbeddings  # deferred import

        self._embed = FastEmbedEmbeddings(model_name=model_name, cache_dir='/tmp/fastembed')
        self._dim: int | None = None

    def dimension(self) -> int:
        if self._dim is None:
            # Infer by probing a tiny input
            vecs = self.embed_texts(["dim-probe"], batch_size=1)
            self._dim = len(vecs[0]) if vecs else 0
        return self._dim or 0

    def embed_texts(self, texts: List[str], *, batch_size: int = 128) -> List[List[float]]:
        # The LC interface supports embedding in batches transparently, but we still chunk.
        vectors: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            chunk_vecs = self._embed.embed_documents(chunk)
            vectors.extend(chunk_vecs)
        return vectors

