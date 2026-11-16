"""Matched hybrid check: pgvector exact candidates, shared Tantivy and CC."""
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

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
STORAGE = BENCH / "work/storage"
sys.path[:0] = [str(STORAGE / "pg-python"), str(BENCH), str(BENCH / "competitors")]
import psycopg  # noqa: E402
import fetch  # noqa: E402
import metrics  # noqa: E402
from matched_engine import MatchedEngine, combine, INPUTS, POOL  # noqa: E402

BIN = STORAGE / "postgres-pgvector-env/Library/bin"
DATA = STORAGE / "postgres-fixture-20261116/data"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    args = parser.parse_args()
    output = STORAGE / ("postgres-" + args.dataset + "-hybrid-check")
    output.mkdir(exist_ok=False)
    engine = MatchedEngine()
    corpus, queries, qrels = fetch.load(args.dataset, "test")
    engine.prepare(args.dataset, corpus)
    folder = INPUTS / args.dataset
    rows = json.loads((folder / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(folder / "vectors.npy", allow_pickle=False)
    query_ids = list(engine.queries)[:100]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env["PATH"]
    with (output / "server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([str(BIN / "postgres.exe"), "-D", str(DATA), "-c", "listen_addresses=127.0.0.1",
                                 "-p", str(port)], env=env, stdout=log, stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(60):
                try:
                    connection = psycopg.connect(host="127.0.0.1", port=port, user="bench", dbname="postgres", connect_timeout=3)
                    break
                except psycopg.OperationalError:
                    if proc.poll() is not None:
                        raise RuntimeError(f"Postgres exited {proc.returncode}")
                    time.sleep(0.5)
            else:
                raise RuntimeError("Postgres startup timed out")
            with connection:
                with connection.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    cur.execute(f"CREATE TEMP TABLE chunks (id bigint PRIMARY KEY, doc_id text, text text, embedding vector({engine.meta['dimension']}))")
                    with cur.copy("COPY chunks (id, doc_id, text, embedding) FROM STDIN") as copy:
                        for row, vector in zip(rows, vectors):
                            copy.write_row((int(row["chunk_id"]), row["doc_id"], row["text"], str(vector.tolist()).replace(" ", "")))
                    reference = {qid: engine.search(qid, queries[qid], 20) for qid in query_ids}
                    runs = []
                    for _ in range(2):
                        ranked = {}
                        for qid in query_ids:
                            text, qvec = engine.queries[qid]
                            query = " ".join(dict.fromkeys(re.findall(r"[^\W_]+", text.lower())))
                            hits = engine.searcher.search(engine.index.parse_query(query, ["text"]), POOL).hits if query else []
                            lexical = [(engine.searcher.doc(addr)["chunk_id"][0], score) for score, addr in hits]
                            cur.execute("SELECT id, embedding <#> %s::vector AS distance FROM chunks ORDER BY distance, id LIMIT %s",
                                        (str(qvec.tolist()).replace(" ", ""), POOL))
                            dense = [(int(row[0]), -float(row[1])) for row in cur.fetchall()]
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
                      "postgres_exe_sha256": digest(BIN / "postgres.exe"),
                      "reference_metrics": metrics.evaluate(reference, judged), "pgvector_metrics": metrics.evaluate(runs[0], judged),
                      "rankings_differ_from_reference": sum(reference[q] != runs[0][q] for q in query_ids),
                      "repeat_rankings_differ": sum(runs[0][q] != runs[1][q] for q in query_ids),
                      "scope": "100 queries; exact pgvector candidates, shared SQLite IDs, Tantivy and CC; no timing claim"}
            (output / "rankings.json").write_text(json.dumps({"reference": reference, "pgvector": runs}, ensure_ascii=False), encoding="utf-8")
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result), flush=True)
        finally:
            subprocess.run(["rtk", "proxy", str(BIN / "pg_ctl.exe"), "stop", "-D", str(DATA), "-m", "fast", "-w"],
                           env=env, capture_output=True, text=True)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=30)
            engine.close()


if __name__ == "__main__":
    main()
