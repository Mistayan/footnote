"""Hybrid diagnostic using Helix's approximate transformed-L2 candidates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
sys.path[:0] = [str(BENCH / "work/storage/helix-python"), str(BENCH), str(BENCH / "competitors")]
os.environ["HELIX_TELEMETRY_LEVEL"] = "off"
from helixdb import Client, InMemory, PropertyValue, VectorDistanceMetric, g, read_batch, write_batch  # noqa: E402
import fetch  # noqa: E402
import metrics  # noqa: E402
from matched_engine import MatchedEngine, combine, INPUTS, POOL  # noqa: E402


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    args = parser.parse_args()
    storage = BENCH / "work/storage"
    suffix = "-transformed-batched-check" if args.dataset == "mix-fr-en" else "-transformed-main-check"
    source = storage / "omnigraph-0.15.0" / (args.dataset + suffix)
    out = storage / "helixdb-3.7.0" / ("embedded-" + args.dataset + "-hybrid-check")
    folder = INPUTS / args.dataset
    source_result = json.loads((source / "result.json").read_text(encoding="utf-8"))
    if source_result["input_meta_sha256"] != digest(folder / "meta.json"):
        raise RuntimeError("Transformed input identity mismatch")
    data = [json.loads(line) for line in (source / "data.jsonl").read_text(encoding="utf-8").splitlines()]
    out.mkdir(exist_ok=False)
    engine = MatchedEngine()
    client = None
    try:
        corpus, queries, qrels = fetch.load(args.dataset, "test")
        engine.prepare(args.dataset, corpus)
        if len(data) != len(engine.ids):
            raise RuntimeError("Unexpected transformed row count")
        client = Client.embedded(InMemory("footnote-" + args.dataset + "-hybrid"))
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
        count = client.query(read_batch().var_as("count", g().n_with_label("Chunk").count()).returning(["count"]).to_query_request())
        if count.get("count") != len(data):
            raise RuntimeError(f"Stored node count mismatch: {count}")
        index = write_batch().var_as("index", g().create_vector_index_nodes("Chunk", "embedding",
            source_result["vector_dimension_after"], VectorDistanceMetric.EUCLIDEAN)).returning(["index"]).to_query_request()
        op_id = client.query(index)["index"]["operation_id"]
        status_query = read_batch().var_as("status", g().get_index_operation(op_id)).returning(["status"]).to_query_request()
        for attempt in range(3000):
            status = client.query(status_query)["status"]
            if status.get("status") == "succeeded":
                break
            if status.get("status") in ("blocked", "aborted"):
                raise RuntimeError(f"Index failed: {status}")
            if attempt and attempt % 150 == 0:
                print(f"{args.dataset}: index status {status.get('status')}", flush=True)
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Index timed out: {status}")
        query_ids = list(engine.queries)[:100]
        reference = {qid: engine.search(qid, queries[qid], 20) for qid in query_ids}
        radius2 = source_result["radius_squared"]
        runs = []
        for _ in range(2):
            ranking_pass = {}
            for qid in query_ids:
                text, qvec = engine.queries[qid]
                query = " ".join(dict.fromkeys(re.findall(r"[^\W_]+", text.lower())))
                hits = engine.searcher.search(engine.index.parse_query(query, ["text"]), POOL).hits if query else []
                lexical = [(engine.searcher.doc(addr)["chunk_id"][0], score) for score, addr in hits]
                request = read_batch().var_as("hits", g().vector_search_nodes("Chunk", "embedding",
                    [*qvec.tolist(), 0.0], POOL).value_map(["chunk", "$distance"])).returning(["hits"]).to_query_request()
                found = client.query(request)["hits"]
                norm2 = float(np.sum(qvec.astype(np.float64) ** 2))
                dense = [(int(item["chunk"]), (radius2 + norm2 - float(item["$distance"])) / 2) for item in found]
                ordered = combine(lexical, dense, 2 * POOL)
                docs = engine._fetch(ordered)
                seen, ranked = set(), []
                for chunk_id in ordered:
                    doc = docs.get(chunk_id)
                    if doc is not None and doc not in seen:
                        seen.add(doc)
                        ranked.append(doc)
                        if len(ranked) == 20:
                            break
                ranking_pass[qid] = ranked
            runs.append(ranking_pass)
        judged = {qid: qrels[qid] for qid in query_ids}
        result = {"dataset": args.dataset, "queries": len(query_ids), "chunks": len(data),
                  "input_meta_sha256": digest(folder / "meta.json"), "transform_sha256": digest(source / "data.jsonl"),
                  "runner_sha256": digest(Path(__file__)), "reference_metrics": metrics.evaluate(reference, judged),
                  "helix_metrics": metrics.evaluate(runs[0], judged),
                  "rankings_differ_from_reference": sum(reference[q] != runs[0][q] for q in query_ids),
                  "repeat_rankings_differ": sum(runs[0][q] != runs[1][q] for q in query_ids),
                  "scope": "100 queries; transformed approximate L2 candidates, shared SQLite IDs, Tantivy and CC; no timing claim"}
        (out / "rankings.json").write_text(json.dumps({"reference": reference, "helix": runs}, ensure_ascii=False), encoding="utf-8")
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        if client is not None:
            client.close()
        engine.close()


if __name__ == "__main__":
    main()
