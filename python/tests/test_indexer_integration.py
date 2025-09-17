from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from src.indexer.build import BuildConfig, build_index
from src.indexer.embeddings import FastEmbedProvider


@pytest.fixture
def integration_test_collection():
    """Fixture providing unique collection name for integration tests"""
    return "rust-copartner-integration-test"


@pytest.fixture
def qdrant_client(integration_test_collection):
    """Fixture providing real Qdrant client with cleanup"""
    load_dotenv()

    try:
        from qdrant_client import QdrantClient
    except ImportError:
        pytest.skip("qdrant-client not available")

    # Get Qdrant URL from environment
    qdrant_url = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")

    try:
        client = QdrantClient(url=qdrant_url, prefer_grpc=False, timeout=10)
        # Test connection
        client.get_collections()
    except Exception as e:
        pytest.skip(f"Qdrant not available at {qdrant_url}: {e}")

    yield client

    # Cleanup: Delete test collection after test
    try:
        client.delete_collection(collection_name=integration_test_collection)
    except Exception:
        pass  # Collection might not exist or already deleted


@pytest.fixture
def vectors_json_path():
    """Fixture providing path to existing vectors.json test data"""
    path = Path(__file__).parent.parent.parent / "rust" / "tests" / "fixtures" / "vectors.json"
    if not path.exists():
        pytest.skip(f"Test data not found: {path}")
    return path


def test_indexer_integration_workflow(qdrant_client, integration_test_collection, vectors_json_path):
    """
    Integration test: Build index from vectors.json -> Store to Qdrant -> Retrieve from Qdrant
    """
    # Step 1: Build index from existing test data
    cfg = BuildConfig(
        input_path=vectors_json_path,
        batch_size=10,
        strict=True,
        dry_run=False,
        collection=integration_test_collection,
        embed_batch=32
    )

    # Use real FastEmbed embeddings
    embeddings = FastEmbedProvider("BAAI/bge-small-en-v1.5")

    # Build and store index
    num_upserted = build_index(cfg, embeddings, qdrant_client)

    # Verify points were upserted
    assert num_upserted > 0, "No points were upserted to Qdrant"

    # Step 2: Verify collection was created and contains data
    collection_info = qdrant_client.get_collection(integration_test_collection)
    assert collection_info is not None, "Collection was not created"

    # Get collection stats
    collection_stats = qdrant_client.get_collection(integration_test_collection)
    points_count = collection_stats.points_count if hasattr(collection_stats, 'points_count') else None

    # Note: vectors.json has 5 records but only 4 unique IDs (2 records share the same ID)
    # Qdrant will store only unique points, so we expect 4 points to be stored
    expected_unique_points = 4
    if points_count is not None:
        assert points_count == expected_unique_points, f"Expected {expected_unique_points} unique points, found {points_count}"

    # Step 3: Test vector retrieval by searching for similar vectors
    # Generate a query vector using the same embeddings provider
    query_text = "Point struct"
    query_embedding = embeddings.embed_texts([query_text])[0]

    # Search in the signature vector field (most likely to match "Point struct")
    search_results = qdrant_client.query_points(
        collection_name=integration_test_collection,
        query=query_embedding,
        using="signature",
        limit=5,
        with_payload=True
    ).points

    # Verify we got search results
    assert len(search_results) > 0, "No search results returned from Qdrant"

    # Verify search results have expected structure
    for result in search_results:
        assert hasattr(result, 'id'), "Search result missing id"
        assert hasattr(result, 'score'), "Search result missing score"
        assert hasattr(result, 'payload'), "Search result missing payload"

        # Verify payload structure matches our expected format
        payload = result.payload
        assert 'vector_fields' in payload, "Missing vector_fields in payload"
        assert 'meta' in payload, "Missing meta in payload"

        # Verify meta structure
        meta = payload['meta']
        required_meta_fields = ['repo_id', 'path', 'kind', 'qual_symbol', 'start_line', 'end_line', 'text']
        for field in required_meta_fields:
            assert field in meta, f"Missing required meta field: {field}"

    # Verify at least one result relates to Point (should be high similarity for "Point struct" query)
    point_related_results = [
        r for r in search_results
        if 'Point' in r.payload.get('meta', {}).get('qual_symbol', '') or
           'Point' in r.payload.get('vector_fields', {}).get('signature', '')
    ]
    assert len(point_related_results) > 0, "No Point-related results found for 'Point struct' query"

    print(f"✓ Integration test successful:")
    print(f"  - Processed {num_upserted} records, stored {expected_unique_points} unique points to collection '{integration_test_collection}'")
    print(f"  - Retrieved {len(search_results)} search results")
    print(f"  - Found {len(point_related_results)} Point-related results")


def test_multi_vector_field_search(qdrant_client, integration_test_collection, vectors_json_path):
    """
    Test searching across different vector fields (signature, identifiers, code_body, doc_comment)
    """
    # First ensure data is indexed (reuse from previous test or build again)
    cfg = BuildConfig(
        input_path=vectors_json_path,
        collection=integration_test_collection
    )
    embeddings = FastEmbedProvider("BAAI/bge-small-en-v1.5")

    # Check if collection already exists from previous test
    try:
        qdrant_client.get_collection(integration_test_collection)
    except Exception:
        # Collection doesn't exist, build it
        build_index(cfg, embeddings, qdrant_client)

    # Test searches on different vector fields
    test_queries = [
        ("signature", "struct Point"),  # Should find struct definitions
        ("identifiers", "new Point"),   # Should find constructor functions
        ("code_body", "impl Point"),    # Should find implementation blocks
        ("doc_comment", "coordinate")   # Should find documented fields
    ]

    for field_name, query_text in test_queries:
        query_embedding = embeddings.embed_texts([query_text])[0]

        search_results = qdrant_client.query_points(
            collection_name=integration_test_collection,
            query=query_embedding,
            using=field_name,
            limit=3,
            with_payload=True
        ).points

        # Should get at least one result for each field type
        assert len(search_results) > 0, f"No results for {field_name} field query: '{query_text}'"

        # Verify all results have proper structure
        for result in search_results:
            assert result.score > 0, f"Invalid score for {field_name} search"
            assert 'vector_fields' in result.payload
            assert 'meta' in result.payload

    print(f"✓ Multi-vector field search test successful")
    print(f"  - Tested searches on {len(test_queries)} different vector fields")