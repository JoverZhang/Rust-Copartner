#!/usr/bin/env python3
"""
Build script for creating Qdrant multi-vector index from NDJSON files.

Usage:
    python -m python.src.bin.build --input path/to/data.ndjson
    python -m python.src.bin.build --input path/to/directory/ --batch-size 512
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from ..indexer.build import BuildConfig, build_index
from ..indexer.embeddings import FastEmbedProvider, MockEmbedProvider


def main(argv: Optional[list[str]] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build Qdrant multi-vector index from NDJSON")
    parser.add_argument("--input", required=True, help="Input file or directory")
    parser.add_argument("--strict", action="store_true", help="Fail fast on invalid lines")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--dry-run", action="store_true", help="Skip Qdrant operations, use mock embeddings")
    parser.add_argument("--qdrant-url", help="Qdrant server URL (default: http://localhost:6333)")
    parser.add_argument("--collection", help="Qdrant collection name (default: code_items)")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    strict = bool(args.strict)
    batch_size = int(args.batch_size)
    dry_run = bool(args.dry_run)

    # Env config with CLI overrides
    collection = args.collection or os.getenv("QDRANT_COLLECTION", "code_items")
    url = args.qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    model_name = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    embed_batch = int(os.getenv("EMBED_BATCH", "128"))

    # Use mock embeddings in dry-run mode to avoid model downloads
    if dry_run:
        embeddings = MockEmbedProvider()
    else:
        embeddings = FastEmbedProvider(model_name)

    client = None
    if not dry_run:
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except Exception as e:
            print(f"qdrant-client not available: {e}", file=sys.stderr)
            return 2

        try:
            print(f"Connecting to Qdrant at {url}...", file=sys.stderr)
            client = QdrantClient(url=url, prefer_grpc=False, timeout=5, check_compatibility=False)
            # Test connection
            print(f"Testing connection...", file=sys.stderr)
            client.get_collections()
            print(f"Successfully connected to Qdrant", file=sys.stderr)
        except Exception as e:
            print(f"Failed to connect to Qdrant server at {url}: {e}", file=sys.stderr)
            print("Make sure Qdrant server is running and accessible", file=sys.stderr)
            print("Or use --dry-run to test without a real server", file=sys.stderr)
            return 2

    cfg = BuildConfig(
        input_path=input_path,
        batch_size=batch_size,
        strict=strict,
        dry_run=dry_run,
        collection=collection,
        embed_batch=embed_batch,
    )

    try:
        num_upserted = build_index(cfg, embeddings, client)
        print(f"[indexer] Successfully built index `{cfg.collection}` with {num_upserted} points", file=sys.stderr)
    except Exception as e:
        print(f"[indexer] Failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())