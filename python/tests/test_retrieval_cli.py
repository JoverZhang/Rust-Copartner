from __future__ import annotations

import pytest
from unittest.mock import patch

from src.bin.retrieval import parse_fields, format_result_text
from src.indexer.retrieval import RetrievalResults, SearchResult


def test_parse_fields_all():
    """Test parsing 'all' fields"""
    fields = parse_fields("all")
    expected = ["signature", "identifiers", "code_body", "doc_comment"]
    assert set(fields) == set(expected)


def test_parse_fields_specific():
    """Test parsing specific fields"""
    fields = parse_fields("signature,identifiers")
    assert fields == ["signature", "identifiers"]


def test_parse_fields_with_spaces():
    """Test parsing fields with spaces"""
    fields = parse_fields("signature, identifiers , code_body")
    assert fields == ["signature", "identifiers", "code_body"]


def test_parse_fields_invalid():
    """Test parsing invalid field names"""
    with pytest.raises(ValueError, match="Invalid field names"):
        parse_fields("invalid_field,signature")


def test_format_result_text_empty():
    """Test formatting empty results"""
    results = RetrievalResults(
        results=[],
        query_text="test query",
        fields_searched=["signature"],
        total_results=0
    )

    output = format_result_text(results)
    assert "No results found for query: 'test query'" in output


def test_format_result_text_with_results():
    """Test formatting results with content"""
    result = SearchResult(
        id="test_id",
        score=0.95,
        vector_fields={
            "signature": "struct Point { x: f64, y: f64 }",
            "identifiers": "Point x y f64"
        },
        meta={
            "qual_symbol": "Point",
            "kind": "struct",
            "path": "src/point.rs",
            "start_line": 1,
            "end_line": 4,
            "text": "struct Point {\n    x: f64,\n    y: f64,\n}"
        },
        field_name="signature"
    )

    results = RetrievalResults(
        results=[result],
        query_text="Point struct",
        fields_searched=["signature"],
        total_results=1
    )

    output = format_result_text(results, show_details=True)

    # Check that key information is present
    assert "Query: 'Point struct'" in output
    assert "Fields searched: signature" in output
    assert "Total results: 1" in output
    assert "score: 0.9500" in output
    assert "Symbol: Point" in output
    assert "Kind: struct" in output
    assert "Path: src/point.rs" in output
    assert "Lines: 1-4" in output
    assert "Signature: struct Point { x: f64, y: f64 }" in output


def test_format_result_text_brief():
    """Test formatting results in brief mode"""
    result = SearchResult(
        id="test_id",
        score=0.95,
        vector_fields={"signature": "struct Point { x: f64, y: f64 }"},
        meta={
            "qual_symbol": "Point",
            "kind": "struct",
            "path": "src/point.rs",
            "text": "struct Point {\n    x: f64,\n    y: f64,\n}"
        },
        field_name="signature"
    )

    results = RetrievalResults(
        results=[result],
        query_text="Point struct",
        fields_searched=["signature"],
        total_results=1
    )

    output = format_result_text(results, show_details=False)

    # Brief mode should not include detailed content
    assert "Symbol: Point" in output
    assert "Kind: struct" in output
    assert "Signature:" not in output  # Should not show vector field content
    assert "Code:" not in output  # Should not show full code


def test_format_result_text_long_content():
    """Test formatting with long content that should be truncated"""
    long_text = "a" * 400  # Longer than 300 char limit
    long_signature = "b" * 300  # Longer than 200 char limit

    result = SearchResult(
        id="test_id",
        score=0.95,
        vector_fields={"signature": long_signature},
        meta={
            "qual_symbol": "LongStruct",
            "text": long_text
        },
        field_name="signature"
    )

    results = RetrievalResults(
        results=[result],
        query_text="test",
        fields_searched=["signature"],
        total_results=1
    )

    output = format_result_text(results, show_details=True)

    # Check truncation
    assert "..." in output  # Should contain truncation indicators
    assert len([line for line in output.split('\n') if 'Code:' in line and len(line) < 350]) > 0