from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.indexer.build import BuildConfig, build_index
from src.indexer.embeddings import EmbeddingsProvider, FastEmbedProvider
from src.indexer.qdrant_utils import ensure_collection


class FakeEmbeddings(EmbeddingsProvider):
    def __init__(self, dim: int = 384):
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str], *, batch_size: int = 128) -> list[list[float]]:
        def h(t: str) -> float:
            return (hash(t) % 1000) / 1000.0

        return [[h(t)] * self._dim for t in texts]


class DummyDistance:
    COSINE = "COSINE"


class DummyVectorParams:
    def __init__(self, size: int, distance: Any):
        self.size = size
        self.distance = distance


class DummyModels:
    Distance = DummyDistance
    VectorParams = DummyVectorParams


class DummyClient:
    def __init__(self):
        self.models = DummyModels()
        self.created = False
        self.upserts: list[dict] = []

    def get_collection(self, collection_name: str):
        if not self.created:
            raise Exception("not found")
        return {"name": collection_name}

    def create_collection(self, collection_name: str, vectors: dict = None, vectors_config: dict = None):
        self.created = True
        # Handle both old and new API parameter names
        vectors_dict = vectors or vectors_config
        # basic validation
        assert set(vectors_dict.keys()) == {"signature", "identifiers", "code_body", "doc_comment"}
        sizes = {vectors_dict[k].size for k in vectors_dict}
        dists = {vectors_dict[k].distance for k in vectors_dict}
        assert len(sizes) == 1
        # Handle both string and enum Distance values
        dist_values = list(dists)
        assert len(dist_values) == 1
        dist_value = dist_values[0]
        # Accept either string "COSINE" or real Distance.COSINE enum
        assert (dist_value == DummyDistance.COSINE or
                (hasattr(dist_value, 'name') and dist_value.name == 'COSINE') or
                str(dist_value).endswith("'Cosine'>"))

    def upsert(self, collection_name: str, points: list[dict]):
        self.upserts.append({"collection": collection_name, "points": points})


def rec(i: int) -> dict:
    return {
        "id": f"id-{i}",
        "vector_fields": {
            "signature": f"sig {i}",
            "identifiers": f"ids {i}",
            "code_body": f"body {i}",
            "doc_comment": f"doc {i}",
        },
        "payload": {
            "repo_id": "r",
            "path": f"p{i}.rs",
            "kind": "fn",
            "qual_symbol": f"crate::m::{i}",
            "start_line": 1,
            "end_line": 2,
            "text": "...",
        },
    }


def write_jsonl(tmp: Path, name: str, rows: list[dict]):
    p = tmp / name
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def write_json(tmp: Path, name: str, obj: Any):
    p = tmp / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_bootstrap_and_single_file_ingest(tmp_path: Path):
    client = DummyClient()
    files = [rec(i) for i in range(3)]
    p = write_json(tmp_path, "project_analyzer_test.json", files)

    cfg = BuildConfig(input_path=p, batch_size=10, strict=True, dry_run=False, collection="code_items")
    # Use real FastEmbedProvider for integration testing
    embeddings = FastEmbedProvider("sentence-transformers/all-MiniLM-L6-v2")
    n = build_index(cfg, embeddings, client)
    assert n == 3

    # ensure collection created once
    assert client.created is True
    # one upsert call
    assert len(client.upserts) == 1
    call = client.upserts[0]
    assert call["collection"] == "code_items"
    pts = call["points"]
    assert len(pts) == 3
    for i, pt in enumerate(pts):
        assert pt["id"] == f"id-{i}"
        assert set(pt["vectors"].keys()) == {"signature", "identifiers", "code_body", "doc_comment"}
        assert len(pt["vectors"]["signature"]) == 384
        assert "vector_fields" in pt["payload"] and "meta" in pt["payload"]


def test_malformed_line_non_strict(tmp_path: Path):
    client = DummyClient()
    good = rec(1)
    bad = {"foo": "bar"}
    p = write_jsonl(tmp_path, "mixed.jsonl", [good, bad])

    cfg = BuildConfig(input_path=p, batch_size=10, strict=False, dry_run=False)
    n = build_index(cfg, FakeEmbeddings(), client)
    assert n == 1
    assert len(client.upserts) == 1
    assert len(client.upserts[0]["points"]) == 1
    assert client.upserts[0]["points"][0]["id"] == "id-1"


def test_malformed_line_strict_raises(tmp_path: Path):
    client = DummyClient()
    good = rec(1)
    bad = {"foo": "bar"}
    p = write_jsonl(tmp_path, "mixed.jsonl", [good, bad])

    cfg = BuildConfig(input_path=p, batch_size=10, strict=True, dry_run=False)
    with pytest.raises(Exception):
        build_index(cfg, FakeEmbeddings(), client)


def test_directory_ingest_with_batching(tmp_path: Path):
    client = DummyClient()
    # create 5 small files with 1 record each
    for i in range(5):
        write_json(tmp_path, f"f{i}.json", [rec(i)])

    cfg = BuildConfig(input_path=tmp_path, batch_size=2, strict=True, dry_run=False)
    n = build_index(cfg, FakeEmbeddings(), client)
    assert n == 5
    # Upserts should be ceil(5/2) = 3 calls
    assert len(client.upserts) == 3
    sizes = [len(call["points"]) for call in client.upserts]
    assert sizes == [2, 2, 1]


def test_real_fastembed_embeddings_integration(tmp_path: Path):
    """Test with real FastEmbedEmbeddings - requires model download, marked as slow."""
    client = DummyClient()
    files = [rec(i) for i in range(2)]  # Use fewer records for speed
    p = write_json(tmp_path, "test_real_embed.json", files)

    cfg = BuildConfig(input_path=p, batch_size=10, strict=True, dry_run=False, collection="test_real")

    # Use real FastEmbedProvider with a small model
    embeddings = FastEmbedProvider("sentence-transformers/all-MiniLM-L6-v2")
    n = build_index(cfg, embeddings, client)

    assert n == 2
    assert client.created is True
    assert len(client.upserts) == 1
    call = client.upserts[0]
    assert call["collection"] == "test_real"
    pts = call["points"]
    assert len(pts) == 2

    for i, pt in enumerate(pts):
        assert pt["id"] == f"id-{i}"
        assert set(pt["vectors"].keys()) == {"signature", "identifiers", "code_body", "doc_comment"}
        # Real embeddings should have proper dimensions (384 for all-MiniLM-L6-v2)
        assert len(pt["vectors"]["signature"]) == 384
        # Check that we got real float values, not just hash-based ones
        sig_vec = pt["vectors"]["signature"]
        assert all(isinstance(x, float) for x in sig_vec)
        assert not all(x == sig_vec[0] for x in sig_vec)  # Should not be all identical values
