"""Syntec approximate-vector diagnostic in the isolated Helix embedded engine."""
import hashlib
import json
import argparse
import os
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
sys.path.insert(0, str(BENCH / "work/storage/helix-python"))
os.environ["HELIX_TELEMETRY_LEVEL"] = "off"
from helixdb import Client, InMemory, PropertyValue, VectorDistanceMetric, g, read_batch, write_batch  # noqa: E402


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    args = parser.parse_args()
    inputs = BENCH / "work/matched-inputs" / args.dataset
    suffix = "-transformed-batched-check" if args.dataset == "mix-fr-en" else "-transformed-main-check"
    transformed = BENCH / "work/storage/omnigraph-0.15.0" / (args.dataset + suffix)
    out = BENCH / "work/storage/helixdb-3.7.0" / ("embedded-" + args.dataset + "-check")
    meta = json.loads((inputs / "meta.json").read_text(encoding="utf-8"))
    for name, expected in meta["files_sha256"].items():
        if digest(inputs / name) != expected:
            raise RuntimeError(f"Input mismatch: {name}")
    source = json.loads((transformed / "result.json").read_text(encoding="utf-8"))
    if source["input_meta_sha256"] != digest(inputs / "meta.json"):
        raise RuntimeError("Transformation input mismatch")
    data = [json.loads(line) for line in (transformed / "data.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = json.loads((inputs / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(inputs / "vectors.npy", allow_pickle=False)
    queries = np.load(inputs / "queries.npy", allow_pickle=False)[:100]
    ids = np.array([row["chunk_id"] for row in rows], dtype=np.int64)
    if len(data) != len(rows) or len(set(ids)) != len(rows):
        raise RuntimeError("Unexpected input length or IDs")
    out.mkdir(exist_ok=False)
    client = Client.embedded(InMemory("footnote-" + args.dataset + "-vector-check"))
    try:
        for start in range(0, len(data), 100):
            batch = write_batch()
            names = []
            for i in range(start, min(start + 100, len(data))):
                item = data[i]
                name = f"n{i}"
                names.append(name)
                props = {"chunk": int(item["data"]["chunk"]), "embedding": PropertyValue.f32_array(item["data"]["embedding"])}
                batch = batch.var_as(name, g().add_n("Chunk", props))
            client.query(batch.returning(names).to_query_request())
        print(f"{args.dataset}: inserted {len(data)} vectors; building index", flush=True)
        index = write_batch().var_as("index", g().create_vector_index_nodes(
            "Chunk", "embedding", source["vector_dimension_after"], VectorDistanceMetric.EUCLIDEAN)).returning(["index"]).to_query_request()
        receipt = client.query(index)
        op_id = receipt["index"]["operation_id"]
        status_query = read_batch().var_as("status", g().get_index_operation(op_id)).returning(["status"]).to_query_request()
        for attempt in range(1500):
            status = client.query(status_query)["status"]
            if status.get("status") == "succeeded":
                break
            if status.get("status") in ("blocked", "aborted"):
                raise RuntimeError(f"Index operation failed: {status}")
            if attempt and attempt % 150 == 0:
                print(f"{args.dataset}: index status {status.get('status')}", flush=True)
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Index did not finish: {status}")
        def search(vector, count):
            request = read_batch().var_as("hits", g().vector_search_nodes("Chunk", "embedding",
                [*vector.tolist(), 0.0], count).value_map(["chunk"])).returning(["hits"]).to_query_request()
            return [item["chunk"] for item in client.query(request)["hits"]]

        visible = client.query(read_batch().var_as("count", g().n_with_label("Chunk").count()).returning(["count"]).to_query_request())
        print(f"{args.dataset}: stored count {visible}", flush=True)
        if visible.get("count") != len(rows):
            raise RuntimeError(f"Stored node count mismatch: {visible}")
        passes, overlaps = [], []
        for _ in range(2):
            ranking = []
            for vector in queries:
                expected = ids[np.lexsort((ids, -(vectors @ vector)))[:10]].tolist()
                actual = search(vector, 10)
                ranking.append({"expected": expected, "actual": actual})
                overlaps.append(len(set(expected) & set(actual)) / 10)
            passes.append(ranking)
        differences = sum(a["actual"] != b["actual"] for a, b in zip(*passes))
        result = {"dataset": args.dataset, "queries": len(queries), "chunks": len(rows), "passes": 2,
                  "mean_top10_overlap": float(np.mean(overlaps)), "min_top10_overlap": min(overlaps),
                  "repeat_order_differences": differences, "input_meta_sha256": digest(inputs / "meta.json"),
                  "transform_sha256": digest(transformed / "data.jsonl"), "runner_sha256": digest(Path(__file__)),
                  "scope": "Helix 0.3.3 embedded in-memory approximate Euclidean index on transformed vectors; no timing claim"}
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (out / "rankings.json").write_text(json.dumps(passes), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
