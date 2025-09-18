#!/usr/bin/env python3
"""
Embedding script for text vectorization using FastEmbed.
Useful for generating query vectors for Qdrant dashboard searches.

Usage:
    python -m python.src.bin.embed "your text here"
    python -m python.src.bin.embed --model BAAI/bge-small-en-v1.5 "your text here"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv
from ..indexer.embeddings import FastEmbedProvider


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate embeddings for text using FastEmbed"
    )
    parser.add_argument("text", help="Text to embed")
    parser.add_argument(
        "--model",
        default=None,
        help="FastEmbed model name (default: from EMBED_MODEL env or BAAI/bge-small-en-v1.5)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (default: comma-separated values)"
    )

    args = parser.parse_args()

    # Initialize FastEmbed provider
    model_name = args.model or os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

    try:
        provider = FastEmbedProvider(model_name)
        print(f"Using FastEmbedProvider (model: {model_name})", file=sys.stderr)
    except Exception as e:
        print(f"Failed to initialize FastEmbed: {e}", file=sys.stderr)
        return 1

    # Generate embedding
    try:
        embeddings = provider.embed_texts([args.text])
        vector = embeddings[0]

        print(f"Generated embedding with dimension: {len(vector)}", file=sys.stderr)

        # Output the vector
        if args.json:
            print(json.dumps(vector))
        else:
            print(",".join(map(str, vector)))

    except Exception as e:
        print(f"Error generating embedding: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())