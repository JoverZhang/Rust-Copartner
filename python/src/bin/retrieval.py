#!/usr/bin/env python3
"""
Retrieval script for retrieving code fragments from Qdrant.
Useful for searching code fragments using vector similarity across multiple fields.

Usage:
    python -m python.src.bin.retrieval "Point struct"
    python -m python.src.bin.retrieval "Point struct" --fields signature,identifiers
    python -m python.src.bin.retrieval "Point struct" --json --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from dotenv import load_dotenv

from ..indexer.embeddings import FastEmbedProvider
from ..indexer.retrieval import RetrievalConfig, retrieve_similar_code


def format_result_text(results, show_details: bool = True) -> str:
    """Format retrieval results as human-readable text."""
    if not results.results:
        return f"No results found for query: '{results.query_text}'"

    output = []
    output.append(f"Query: '{results.query_text}'")
    output.append(f"Fields searched: {', '.join(results.fields_searched)}")
    output.append(f"Total results: {results.total_results}")
    output.append("")

    for i, result in enumerate(results.results, 1):
        output.append(f"Result {i} (score: {result.score:.4f}, field: {result.field_name}):")

        # Show metadata
        meta = result.meta
        if 'qual_symbol' in meta:
            output.append(f"  Symbol: {meta['qual_symbol']}")
        if 'kind' in meta:
            output.append(f"  Kind: {meta['kind']}")
        if 'path' in meta:
            output.append(f"  Path: {meta['path']}")
        if 'start_line' in meta and 'end_line' in meta:
            output.append(f"  Lines: {meta['start_line']}-{meta['end_line']}")

        # Show vector field content if requested
        if show_details:
            vector_fields = result.vector_fields
            field_content = vector_fields.get(result.field_name, "")
            if field_content:
                # Truncate long content
                max_length = 200
                if len(field_content) > max_length:
                    field_content = field_content[:max_length] + "..."
                output.append(f"  {result.field_name.title()}: {field_content}")

        if 'text' in meta and show_details:
            text = meta['text']
            if len(text) > 300:
                text = text[:300] + "..."
            output.append(f"  Code: {text}")

        output.append("")

    return "\n".join(output)


def parse_fields(fields_str: str) -> List[str]:
    """Parse comma-separated field names and validate them."""
    valid_fields = {"signature", "identifiers", "code_body", "doc_comment"}

    if fields_str.lower() == "all":
        return list(valid_fields)

    fields = [f.strip() for f in fields_str.split(",")]
    invalid_fields = set(fields) - valid_fields

    if invalid_fields:
        raise ValueError(f"Invalid field names: {invalid_fields}. Valid fields: {valid_fields}")

    return fields


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Retrieve code fragments from Qdrant using vector similarity search"
    )
    parser.add_argument("text", help="Text to search for")
    parser.add_argument(
        "--fields",
        default="all",
        help="Vector fields to search (comma-separated). Options: signature,identifiers,code_body,doc_comment or 'all' (default: all)"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="FastEmbed model name (default: from EMBED_MODEL env or BAAI/bge-small-en-v1.5)"
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Qdrant collection name (default: from QDRANT_COLLECTION env or 'code_items')"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to return (default: 10)"
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.0,
        help="Minimum similarity score threshold (default: 0.0)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Show brief output (less detail)"
    )
    parser.add_argument(
        "--qdrant-url",
        help="Qdrant server URL (default: from QDRANT_URL env or http://localhost:6333)"
    )

    args = parser.parse_args()

    # Parse and validate fields
    try:
        fields = parse_fields(args.fields)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Configuration from environment and CLI args
    collection = args.collection or os.getenv("QDRANT_COLLECTION", "code_items")
    model_name = args.model or os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    qdrant_url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")

    # Initialize embeddings provider
    try:
        embeddings = FastEmbedProvider(model_name)
        print(f"Using FastEmbedProvider (model: {model_name})", file=sys.stderr)
    except Exception as e:
        print(f"Failed to initialize FastEmbed: {e}", file=sys.stderr)
        return 1

    # Initialize Qdrant client
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("Error: qdrant-client not available. Install with: pip install qdrant-client", file=sys.stderr)
        return 1

    try:
        print(f"Connecting to Qdrant at {qdrant_url}...", file=sys.stderr)
        client = QdrantClient(url=qdrant_url, prefer_grpc=False, timeout=10)
        # Test connection
        client.get_collections()
        print(f"Successfully connected to Qdrant", file=sys.stderr)
    except Exception as e:
        print(f"Failed to connect to Qdrant server at {qdrant_url}: {e}", file=sys.stderr)
        print("Make sure Qdrant server is running and accessible", file=sys.stderr)
        return 1

    # Check if collection exists
    try:
        client.get_collection(collection)
        print(f"Using collection: {collection}", file=sys.stderr)
    except Exception as e:
        print(f"Collection '{collection}' not found: {e}", file=sys.stderr)
        print(f"Make sure the collection exists. You can build it with:", file=sys.stderr)
        print(f"  python -m python.src.bin.build --input /path/to/data.ndjson --collection {collection}", file=sys.stderr)
        return 1

    # Configure retrieval
    cfg = RetrievalConfig(
        collection=collection,
        limit=args.limit,
        score_threshold=args.score_threshold
    )

    # Perform retrieval
    try:
        print(f"Searching for: '{args.text}' in fields: {', '.join(fields)}", file=sys.stderr)
        results = retrieve_similar_code(
            query_text=args.text,
            embeddings=embeddings,
            client=client,
            cfg=cfg,
            fields=fields
        )

        # Output results
        if args.json:
            # Convert to JSON-serializable format
            results_dict = {
                "query_text": results.query_text,
                "fields_searched": results.fields_searched,
                "total_results": results.total_results,
                "results": [
                    {
                        "id": result.id,
                        "score": result.score,
                        "field_name": result.field_name,
                        "vector_fields": result.vector_fields,
                        "meta": result.meta
                    }
                    for result in results.results
                ]
            }
            print(json.dumps(results_dict, indent=2))
        else:
            print(format_result_text(results, show_details=not args.brief))

    except Exception as e:
        print(f"Error during retrieval: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())