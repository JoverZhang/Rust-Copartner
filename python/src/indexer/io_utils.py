from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator


def discover_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".json", ".jsonl"}:
            files.append(p)
    return files


def iter_records_from_file(path: Path) -> Iterator[dict]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".jsonl":
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    yield obj
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSONL at {path}:{i}: {e}")
    elif suffix == ".json":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON at {path}: {e}")
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    yield item
        elif isinstance(obj, dict):
            yield obj
    else:
        raise ValueError(f"Unsupported file type: {path}")

