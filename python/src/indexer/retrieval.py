from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Union

from pydantic import BaseModel

from .embeddings import EmbeddingsProvider


@dataclass
class RetrievalConfig:
    collection: str = "code_items"
    limit: int = 10
    score_threshold: float = 0.0
    embed_batch: int = 128


class SearchResult(BaseModel):
    id: Union[int, str]
    score: float
    vector_fields: dict[str, str]
    meta: dict[str, Any]
    field_name: str  # Which vector field was searched


class RetrievalResults(BaseModel):
    results: List[SearchResult]
    query_text: str
    fields_searched: List[str]
    total_results: int


def retrieve_similar_code(
    query_text: str,
    embeddings: EmbeddingsProvider,
    client: Any,
    cfg: RetrievalConfig,
    fields: Optional[List[str]] = None,
) -> RetrievalResults:
    """Retrieve similar code fragments from Qdrant using vector similarity search.

    Args:
        query_text: Text to search for
        embeddings: Provider for text embeddings
        client: Qdrant client instance
        cfg: Retrieval configuration
        fields: Vector fields to search in. If None, searches all fields.
                Options: ['signature', 'identifiers', 'code_body', 'doc_comment']

    Returns:
        RetrievalResults containing search results across all specified fields
    """
    # Default to all vector fields if none specified
    if fields is None:
        fields = ["signature", "identifiers", "code_body", "doc_comment"]

    # Validate field names
    valid_fields = {"signature", "identifiers", "code_body", "doc_comment"}
    invalid_fields = set(fields) - valid_fields
    if invalid_fields:
        raise ValueError(f"Invalid field names: {invalid_fields}. Valid fields: {valid_fields}")

    # Generate query embedding
    query_embeddings = embeddings.embed_texts([query_text], batch_size=cfg.embed_batch)
    query_vector = query_embeddings[0]

    all_results: List[SearchResult] = []

    # Search each specified vector field
    for field_name in fields:
        try:
            search_results = client.query_points(
                collection_name=cfg.collection,
                query=query_vector,
                using=field_name,
                limit=cfg.limit,
                with_payload=True,
                score_threshold=cfg.score_threshold
            ).points

            # Convert Qdrant results to our SearchResult model
            for result in search_results:
                payload = result.payload or {}
                vector_fields = payload.get("vector_fields", {})
                meta = payload.get("meta", {})

                search_result = SearchResult(
                    id=result.id,
                    score=result.score,
                    vector_fields=vector_fields,
                    meta=meta,
                    field_name=field_name
                )
                all_results.append(search_result)

        except Exception as e:
            # Log error but continue with other fields
            print(f"Warning: Search failed for field '{field_name}': {e}")
            continue

    # Sort results by score (highest first)
    all_results.sort(key=lambda x: x.score, reverse=True)

    # Apply global limit across all fields
    final_results = all_results[:cfg.limit]

    return RetrievalResults(
        results=final_results,
        query_text=query_text,
        fields_searched=fields,
        total_results=len(final_results)
    )


def retrieve_by_field(
    query_text: str,
    field_name: str,
    embeddings: EmbeddingsProvider,
    client: Any,
    cfg: RetrievalConfig,
) -> List[SearchResult]:
    """Retrieve similar code fragments from a specific vector field.

    Args:
        query_text: Text to search for
        field_name: Vector field to search ('signature', 'identifiers', 'code_body', 'doc_comment')
        embeddings: Provider for text embeddings
        client: Qdrant client instance
        cfg: Retrieval configuration

    Returns:
        List of SearchResult objects for the specified field
    """
    result = retrieve_similar_code(
        query_text=query_text,
        embeddings=embeddings,
        client=client,
        cfg=cfg,
        fields=[field_name]
    )
    return result.results