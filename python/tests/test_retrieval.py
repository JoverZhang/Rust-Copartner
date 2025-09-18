from __future__ import annotations

import pytest
from unittest.mock import MagicMock, Mock

from src.indexer.retrieval import (
    RetrievalConfig,
    SearchResult,
    RetrievalResults,
    retrieve_similar_code,
    retrieve_by_field
)
from src.indexer.embeddings import MockEmbedProvider


@pytest.fixture
def mock_embeddings():
    """Mock embeddings provider for testing"""
    return MockEmbedProvider(dim=384)


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client with sample response"""
    client = MagicMock()

    # Create mock search result
    mock_result = Mock()
    mock_result.id = "test_id_1"
    mock_result.score = 0.95
    mock_result.payload = {
        "vector_fields": {
            "signature": "struct Point { x: f64, y: f64 }",
            "identifiers": "Point x y f64",
            "code_body": "struct Point {\n    x: f64,\n    y: f64,\n}",
            "doc_comment": "A point in 2D space with x and y coordinates"
        },
        "meta": {
            "repo_id": "test/repo",
            "path": "src/point.rs",
            "kind": "struct",
            "qual_symbol": "Point",
            "start_line": 1,
            "end_line": 4,
            "text": "struct Point {\n    x: f64,\n    y: f64,\n}"
        }
    }

    # Mock query_points response
    mock_response = Mock()
    mock_response.points = [mock_result]
    client.query_points.return_value = mock_response

    return client


@pytest.fixture
def retrieval_config():
    """Default retrieval configuration for testing"""
    return RetrievalConfig(
        collection="test_collection",
        limit=5,
        score_threshold=0.0
    )


def test_retrieve_similar_code_all_fields(mock_embeddings, mock_qdrant_client, retrieval_config):
    """Test retrieving similar code across all vector fields"""
    query_text = "Point struct"

    results = retrieve_similar_code(
        query_text=query_text,
        embeddings=mock_embeddings,
        client=mock_qdrant_client,
        cfg=retrieval_config,
        fields=None  # Should default to all fields
    )

    # Verify the results
    assert isinstance(results, RetrievalResults)
    assert results.query_text == query_text
    assert len(results.fields_searched) == 4  # All fields
    assert set(results.fields_searched) == {"signature", "identifiers", "code_body", "doc_comment"}
    assert results.total_results > 0

    # Check that query_points was called for each field
    assert mock_qdrant_client.query_points.call_count == 4

    # Verify first result structure
    if results.results:
        result = results.results[0]
        assert isinstance(result, SearchResult)
        assert result.id == "test_id_1"
        assert result.score == 0.95
        assert "Point" in result.vector_fields.get("signature", "")
        assert "Point" in result.meta.get("qual_symbol", "")


def test_retrieve_similar_code_specific_fields(mock_embeddings, mock_qdrant_client, retrieval_config):
    """Test retrieving similar code from specific vector fields"""
    query_text = "Point struct"
    fields = ["signature", "identifiers"]

    results = retrieve_similar_code(
        query_text=query_text,
        embeddings=mock_embeddings,
        client=mock_qdrant_client,
        cfg=retrieval_config,
        fields=fields
    )

    # Verify the results
    assert results.query_text == query_text
    assert results.fields_searched == fields
    assert len(results.fields_searched) == 2

    # Check that query_points was called only for specified fields
    assert mock_qdrant_client.query_points.call_count == 2


def test_retrieve_by_field(mock_embeddings, mock_qdrant_client, retrieval_config):
    """Test retrieving similar code from a single field"""
    query_text = "Point struct"
    field_name = "signature"

    results = retrieve_by_field(
        query_text=query_text,
        field_name=field_name,
        embeddings=mock_embeddings,
        client=mock_qdrant_client,
        cfg=retrieval_config
    )

    # Verify the results
    assert isinstance(results, list)
    assert len(results) > 0

    # Check that the field name is set correctly
    if results:
        result = results[0]
        assert result.field_name == field_name


def test_invalid_field_names(mock_embeddings, mock_qdrant_client, retrieval_config):
    """Test error handling for invalid field names"""
    query_text = "Point struct"
    invalid_fields = ["invalid_field", "another_invalid"]

    with pytest.raises(ValueError, match="Invalid field names"):
        retrieve_similar_code(
            query_text=query_text,
            embeddings=mock_embeddings,
            client=mock_qdrant_client,
            cfg=retrieval_config,
            fields=invalid_fields
        )


def test_search_result_model():
    """Test SearchResult model validation"""
    result = SearchResult(
        id="test_id",
        score=0.95,
        vector_fields={"signature": "struct Point"},
        meta={"kind": "struct", "path": "src/point.rs"},
        field_name="signature"
    )

    assert result.id == "test_id"
    assert result.score == 0.95
    assert result.vector_fields["signature"] == "struct Point"
    assert result.meta["kind"] == "struct"
    assert result.field_name == "signature"


def test_retrieval_config():
    """Test RetrievalConfig defaults and validation"""
    # Test defaults
    config = RetrievalConfig()
    assert config.collection == "code_items"
    assert config.limit == 10
    assert config.score_threshold == 0.0
    assert config.embed_batch == 128

    # Test custom values
    config = RetrievalConfig(
        collection="custom_collection",
        limit=20,
        score_threshold=0.5,
        embed_batch=64
    )
    assert config.collection == "custom_collection"
    assert config.limit == 20
    assert config.score_threshold == 0.5
    assert config.embed_batch == 64


def test_error_handling_client_failure(mock_embeddings, retrieval_config):
    """Test error handling when Qdrant client fails"""
    # Create a client that raises an exception
    failing_client = MagicMock()
    failing_client.query_points.side_effect = Exception("Connection failed")

    query_text = "Point struct"

    # Should not raise an exception, but should handle errors gracefully
    results = retrieve_similar_code(
        query_text=query_text,
        embeddings=mock_embeddings,
        client=failing_client,
        cfg=retrieval_config,
        fields=["signature"]
    )

    # Should return empty results when all searches fail
    assert results.total_results == 0
    assert len(results.results) == 0
    assert results.query_text == query_text