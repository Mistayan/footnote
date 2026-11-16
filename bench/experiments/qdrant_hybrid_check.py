"""Compare matched hybrid rankings using Qdrant exact candidates and Tantivy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import numpy as np
from qdrant_client import QdrantClient, models

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
sys.path[:0] = [str(BENCH), str(BENCH / "competitors")]
import fetch  # noqa: E402
import metrics  # noqa: E402
from matched_engine import MatchedEngine, combine, INPUTS, POOL  # noqa: E402

QDRANT_DIR = BENCH / "work/storage/qdrant-1.20.1"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    args = parser.parse_args()
    output = QDRANT_DIR / (args.dataset + "-hybrid-check")
    output.mkdir(exist_ok=False)
    engine = MatchedEngine()
    corpus, queries, qrels = fetch.load(args.dataset, "test")
    engine.prepare(args.dataset, corpus)  # validates all frozen hashes and input coverage
    folder = INPUTS / args.dataset
    rows = json.loads((folder / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(folder / "vectors.npy", allow_pickle=False)
    query_ids = list(engine.queries)[:100]
    http, grpc = port(), port()
    while grpc == http:
        grpc = port()
    env = os.environ.copy()
    env.update({"QDRANT__SERVICE__HOST": "127.0.0.1", "QDRANT__SERVICE__HTTP_PORT": str(http),
                "QDRANT__SERVICE__GRPC_PORT": str(grpc), "QDRANT__TELEMETRY_DISABLED": "true"})
    with (output / "server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([str(QDRANT_DIR / "unpacked/qdrant.exe")], cwd=output, env=env, stdout=log,
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
            client.create_collection("chunks", vectors_config=models.VectorParams(size=engine.meta["dimension"], distance=models.Distance.DOT))
            for start in range(0, len(rows), 256):
                client.upsert("chunks", wait=True, points=[models.PointStruct(id=int(rows[i]["chunk_id"]),
                    vector=vectors[i].tolist(), payload={"doc_id": rows[i]["doc_id"], "text": rows[i]["text"]})
                    for i in range(start, min(start + 256, len(rows)))])
            reference, runs = {}, []
            for qid in query_ids:
                reference[qid] = engine.search(qid, queries[qid], 20)
            for _ in range(2):
                ranked = {}
                for qid in query_ids:
                    text, qvec = engine.queries[qid]
                    query = " ".join(dict.fromkeys(re.findall(r"[^\W_]+", text.lower())))
                    hits = engine.searcher.search(engine.index.parse_query(query, ["text"]), POOL).hits if query else []
                    lexical = [(engine.searcher.doc(addr)["chunk_id"][0], score) for score, addr in hits]
                    dense = [(int(p.id), float(p.score)) for p in client.query_points("chunks", query=qvec.tolist(),
                             search_params=models.SearchParams(exact=True), limit=POOL).points]
                    ordered = combine(lexical, dense, 2 * POOL)
                    docs = engine._fetch(ordered)
                    seen, ranking = set(), []
                    for chunk_id in ordered:
                        doc = docs.get(chunk_id)
                        if doc is not None and doc not in seen:
                            seen.add(doc)
                            ranking.append(doc)
                            if len(ranking) == 20:
                                break
                    ranked[qid] = ranking
                runs.append(ranked)
            judged = {qid: qrels[qid] for qid in query_ids}
            result = {"dataset": args.dataset, "queries": len(query_ids), "chunks": len(rows),
                      "input_meta_sha256": digest(folder / "meta.json"), "runner_sha256": digest(Path(__file__)),
                      "reference_metrics": metrics.evaluate(reference, judged),
                      "qdrant_metrics": metrics.evaluate(runs[0], judged),
                      "rankings_differ_from_reference": sum(reference[q] != runs[0][q] for q in query_ids),
                      "repeat_rankings_differ": sum(runs[0][q] != runs[1][q] for q in query_ids),
                      "scope": "100 queries; exact dense candidates, shared Tantivy and CC; no timing claim"}
            (output / "rankings.json").write_text(json.dumps({"reference": reference, "qdrant": runs}, ensure_ascii=False), encoding="utf-8")
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result), flush=True)
        finally:
            proc.terminate()
            proc.wait(timeout=30)
            engine.close()


if __name__ == "__main__":
    main()
