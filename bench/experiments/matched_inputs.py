"""Freeze public product chunks and a8m vectors for the matched backend experiment.

    bench/.labenv/Scripts/python.exe -I bench/experiments/matched_inputs.py syntec

Source indexes are read-only. No model or data is sent to a remote service.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import struct
import sys
import time

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH / "lab"))
import fetch  # noqa: E402
from engines import clip, doc_id_of, sha256_file  # noqa: E402
import models  # noqa: E402
from lab import Encoder  # noqa: E402

ROOT = BENCH / "work/matched-inputs"


def decode(blob: bytes, dimension: int) -> np.ndarray:
    if len(blob) != 4 + dimension:
        raise ValueError("corrupt source vector length")
    scale = struct.unpack("<f", blob[:4])[0]
    vector = np.frombuffer(blob[4:], dtype=np.int8).astype(np.float32) * scale
    if not np.isfinite(scale) or scale <= 0 or abs(float(np.linalg.norm(vector)) - 1) > .05:
        raise ValueError("corrupt source vector scale or norm")
    return vector


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dataset", choices=["syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"])
    args = ap.parse_args()
    dataset = args.dataset
    folder = ROOT / dataset
    if folder.exists():
        raise ValueError(f"matched input already exists; refusing to overwrite {folder}")
    started = time.perf_counter()
    corpus, queries, _ = fetch.load(dataset, "test")
    source = BENCH / "work" / dataset / "ens/k.db"
    source_hash = sha256_file(source)
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        candidates = [(identity, json.loads(raw), dimension) for identity, raw, dimension in
                      connection.execute("SELECT identity,manifest,dimension FROM embedding_models")]
        identity, manifest, dimension = next(row for row in candidates if row[1]["repository"] == "hotchpotch/bekko-embedding-v1-a8m")
        lock = models.lock_entry("bekko-a8m")
        if lock["revision"] != manifest["revision"] or lock["files"] != {key: value["sha256"] for key, value in manifest["files"].items()}:
            raise ValueError("lab query encoder and stored passage model differ")
        rows = connection.execute("SELECT c.id,s.path,c.heading,c.text,e.vector FROM chunks c JOIN sources s ON s.id=c.source_id "
                                  "JOIN embeddings e ON e.id=c.id AND e.kind='chunk' AND e.model=? WHERE s.status='indexed' ORDER BY c.id",
                                  (identity,)).fetchall()
        expected = connection.execute("SELECT count(*) FROM chunks c JOIN sources s ON s.id=c.source_id WHERE s.status='indexed'").fetchone()[0]
    documents = [{"chunk_id": row[0], "doc_id": doc_id_of(row[1]), "text": f"{row[2]}\n{row[3]}"} for row in rows]
    if len(rows) != expected or {row["doc_id"] for row in documents} != set(corpus):
        raise ValueError("source chunk/vector/document coverage mismatch")
    vectors = np.stack([decode(row[4], dimension) for row in rows])
    items = [(qid, clip(text)) for qid, text in queries.items()]
    encoder = Encoder("bekko-a8m")
    query_vectors = encoder.embed([text for _, text in items], "query")
    if query_vectors.shape != (len(items), dimension):
        raise ValueError("query and passage vector dimensions differ")
    if sha256_file(source) != source_hash:
        raise ValueError("source index changed during export")
    folder.mkdir(parents=True)
    (folder / "documents.json").write_text(json.dumps(documents, ensure_ascii=False), encoding="utf-8")
    (folder / "queries.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    np.save(folder / "vectors.npy", vectors, allow_pickle=False)
    np.save(folder / "queries.npy", query_vectors, allow_pickle=False)
    meta = {"dataset": dataset, "split": "test", "dataset_pin": fetch.dataset_pin(dataset), "model_lock": lock,
            "source_database_sha256": source_hash, "documents": len(corpus), "chunks": len(rows), "dimension": dimension,
            "export_ms": (time.perf_counter() - started) * 1000, "exporter_sha256": sha256_file(Path(__file__)),
            "encoder_sha256": sha256_file(BENCH / "lab/lab.py"),
            "files_sha256": {name: sha256_file(folder / name) for name in ("documents.json", "queries.json", "vectors.npy", "queries.npy")}}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"{dataset}: {len(rows)} chunks, {len(items)} queries, {meta['export_ms']:.0f} ms", flush=True)


if __name__ == "__main__":
    main()
