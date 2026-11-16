"""Validate Qdrant's exact dot-product search against frozen matched inputs."""
import hashlib
import json
import argparse
from pathlib import Path
import os
import socket
import subprocess
import time

import numpy as np
from qdrant_client import QdrantClient, models

ROOT = Path(__file__).resolve().parents[2]
QDRANT_DIR = ROOT / "bench/work/storage/qdrant-1.20.1"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    inputs = ROOT / "bench/work/matched-inputs" / args.dataset
    meta = json.loads((inputs / "meta.json").read_text(encoding="utf-8"))
    for name, expected in meta["files_sha256"].items():
        if digest(inputs / name) != expected:
            raise RuntimeError(f"Frozen input hash mismatch: {name}")
    rows = json.loads((inputs / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(inputs / "vectors.npy", allow_pickle=False)
    queries = np.load(inputs / "queries.npy", allow_pickle=False)[:100]
    ids = np.asarray([row["chunk_id"] for row in rows], dtype=np.int64)
    if len(set(ids)) != len(rows) or vectors.shape != (len(rows), meta["dimension"]) or queries.shape[1] != meta["dimension"]:
        raise RuntimeError("Frozen input IDs or dimensions differ")
    run = QDRANT_DIR / (args.dataset + ("-exact-diagnostic" if args.diagnostic else "-exact-check"))
    run.mkdir(exist_ok=False)
    http, grpc = port(), port()
    while grpc == http:
        grpc = port()
    env = os.environ.copy()
    env.update({"QDRANT__SERVICE__HOST": "127.0.0.1", "QDRANT__SERVICE__HTTP_PORT": str(http),
                "QDRANT__SERVICE__GRPC_PORT": str(grpc), "QDRANT__TELEMETRY_DISABLED": "true"})
    with (run / "server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([str(QDRANT_DIR / "unpacked/qdrant.exe")], cwd=run, env=env, stdout=log,
                                stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            client = QdrantClient(url=f"http://127.0.0.1:{http}", timeout=30)
            for _ in range(60):
                try:
                    client.get_collections()
                    break
                except Exception:
                    if proc.poll() is not None:
                        raise RuntimeError(f"Qdrant exited: {proc.returncode}")
                    time.sleep(0.5)
            else:
                raise RuntimeError("Qdrant startup timed out")
            client.create_collection("chunks", vectors_config=models.VectorParams(size=meta["dimension"], distance=models.Distance.DOT))
            for start in range(0, len(rows), 256):
                client.upsert("chunks", wait=True, points=[models.PointStruct(id=int(ids[i]), vector=vectors[i].tolist(),
                    payload={"doc_id": rows[i]["doc_id"], "text": rows[i]["text"]})
                    for i in range(start, min(start + 256, len(rows)))])
            overlaps = []
            mismatches = []
            for query_index, vector in enumerate(queries):
                scores = vectors @ vector
                expected = set(ids[np.lexsort((ids, -scores))[:10]].tolist())
                points = client.query_points("chunks", query=vector.tolist(),
                    search_params=models.SearchParams(exact=True), limit=10).points
                actual = {p.id for p in points}
                overlaps.append(len(expected & actual) / 10)
                if expected != actual:
                    differences = expected ^ actual
                    mismatches.append({"query_index": query_index, "only_numpy": sorted(expected - actual),
                        "only_qdrant": sorted(actual - expected),
                        "numpy_scores": {str(int(ids[i])): float(scores[i]) for i in range(len(ids)) if ids[i] in differences},
                        "qdrant_scores": {str(p.id): p.score for p in points if p.id in differences}})
            result = {"dataset": args.dataset, "input_meta_sha256": digest(inputs / "meta.json"),
                      "queries": len(queries), "chunks": len(rows), "top10_mean_overlap": float(np.mean(overlaps)),
                      "top10_min_overlap": min(overlaps), "qdrant_exe_sha256": digest(QDRANT_DIR / "unpacked/qdrant.exe"),
                      "runner_sha256": digest(Path(__file__)), "scope": "exact dense IDs only; no latency claim",
                      "mismatches": mismatches}
            (run / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result), flush=True)
        finally:
            proc.terminate()
            proc.wait(timeout=30)


if __name__ == "__main__":
    main()
