from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator

from .embeddings import EmbeddingsProvider, FastEmbedProvider, MockEmbedProvider
from .io_utils import discover_input_files, iter_records_from_file
from .qdrant_utils import ensure_collection


class VectorFieldsModel(BaseModel):
    signature: str
    identifiers: str
    code_body: str
    doc_comment: str


class PayloadModel(BaseModel):
    repo_id: str
    path: str
    kind: str
    qual_symbol: str
    start_line: int
    end_line: int
    text: str

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {"struct", "impl", "fn"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {allowed}")
        return v

    @field_validator("start_line", "end_line", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        return int(v)

    @field_validator("end_line")
    @classmethod
    def validate_line_order(cls, v: int, info):
        start = info.data.get("start_line", 0)
        if isinstance(start, str):
            try:
                start = int(start)
            except Exception:
                start = 0
        if start and v < start:
            raise ValueError("end_line must be >= start_line")
        return v


class RecordModel(BaseModel):
    id: str
    vector_fields: VectorFieldsModel
    payload: PayloadModel


@dataclass
class BuildConfig:
    input_path: Path
    batch_size: int = 256
    strict: bool = False
    dry_run: bool = False
    collection: str = "code_items"
    embed_batch: int = 128


def _batched(seq: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def build_index(
    cfg: BuildConfig,
    embeddings: EmbeddingsProvider,
    client: Optional[Any] = None,
) -> int:
    """Ingest records into Qdrant. Returns number of upserted points."""

    files = discover_input_files(cfg.input_path)
    dim = embeddings.dimension()

    total_upserted = 0

    if not cfg.dry_run and client is not None:
        ensure_collection(client, cfg.collection, dim)

    # Gather records from all files
    valid_records: List[RecordModel] = []
    for f in files:
        try:
            for obj in iter_records_from_file(f):
                try:
                    valid_records.append(RecordModel.model_validate(obj))
                except ValidationError as e:
                    if cfg.strict:
                        raise
                    print(f"[indexer] Invalid record in {f}: {e}", file=sys.stderr)
        except Exception as e:
            if cfg.strict:
                raise
            print(f"[indexer] Failed to read {f}: {e}", file=sys.stderr)

    if not valid_records:
        return 0

    # Prepare embeddings per field; batch per vector field for efficiency
    sig_texts = [r.vector_fields.signature for r in valid_records]
    idf_texts = [r.vector_fields.identifiers for r in valid_records]
    body_texts = [r.vector_fields.code_body for r in valid_records]
    doc_texts = [r.vector_fields.doc_comment for r in valid_records]

    sig_vecs = embeddings.embed_texts(sig_texts, batch_size=cfg.embed_batch)
    idf_vecs = embeddings.embed_texts(idf_texts, batch_size=cfg.embed_batch)
    body_vecs = embeddings.embed_texts(body_texts, batch_size=cfg.embed_batch)
    doc_vecs = embeddings.embed_texts(doc_texts, batch_size=cfg.embed_batch)

    # Split into upsert batches
    for batch_indices in _batched(list(range(len(valid_records))), cfg.batch_size):
        points = []
        for i in batch_indices:
            rec = valid_records[i]
            point = {
                "id": rec.id,
                "vectors": {
                    "signature": sig_vecs[i],
                    "identifiers": idf_vecs[i],
                    "code_body": body_vecs[i],
                    "doc_comment": doc_vecs[i],
                },
                "payload": {
                    "vector_fields": rec.vector_fields.model_dump(),
                    "meta": rec.payload.model_dump(),
                },
            }
            points.append(point)

        if not cfg.dry_run and client is not None:
            client.upsert(collection_name=cfg.collection, points=points)
            total_upserted += len(points)
    return total_upserted


def main(argv: Optional[list[str]] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build Qdrant multi-vector index from NDJSON")
    parser.add_argument("--input", required=True, help="Input file or directory")
    parser.add_argument("--strict", action="store_true", help="Fail fast on invalid lines")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    strict = bool(args.strict)
    batch_size = int(args.batch_size)
    dry_run = bool(args.dry_run)

    # Env config
    collection = os.getenv("QDRANT_COLLECTION", "code_items")
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
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
        client = QdrantClient(url=url, api_key=api_key)  # type: ignore

    cfg = BuildConfig(
        input_path=input_path,
        batch_size=batch_size,
        strict=strict,
        dry_run=dry_run,
        collection=collection,
        embed_batch=embed_batch,
    )

    try:
        build_index(cfg, embeddings, client)
    except Exception as e:
        print(f"[indexer] Failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

