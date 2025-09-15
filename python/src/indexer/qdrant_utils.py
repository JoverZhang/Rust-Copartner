from __future__ import annotations

from typing import Any


def ensure_collection(client: Any, collection_name: str, vector_dim: int) -> None:
    """Create the multi-vector collection if it doesn't exist."""
    try:
        client.get_collection(collection_name=collection_name)
        return
    except Exception:
        pass

    try:
        # Try new qdrant-client API (1.7+)
        from qdrant_client.models import VectorParams, Distance

        vp = VectorParams(size=vector_dim, distance=Distance.COSINE)
        vectors_config = {
            "signature": vp,
            "identifiers": vp,
            "code_body": vp,
            "doc_comment": vp,
        }
        client.create_collection(collection_name=collection_name, vectors_config=vectors_config)
    except ImportError:
        # Fallback for older versions or mocked clients
        models = getattr(client, "models", None)
        if models is None:
            raise RuntimeError("Qdrant client missing 'models' attribute for collection creation")

        vp = models.VectorParams(size=vector_dim, distance=models.Distance.COSINE)
        vectors_config = {
            "signature": vp,
            "identifiers": vp,
            "code_body": vp,
            "doc_comment": vp,
        }
        client.create_collection(collection_name=collection_name, vectors=vectors_config)

