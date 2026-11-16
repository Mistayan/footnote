"""Bounded exact candidate benchmark; never run alongside other benchmarks."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

# Fix the in-process reference's BLAS thread count before importing NumPy.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
STORAGE = BENCH / "work/storage"
sys.path.insert(0, str(STORAGE / "pg-python"))
import psycopg  # noqa: E402
from qdrant_client import QdrantClient, models  # noqa: E402

INPUT = BENCH / "work/matched-inputs/mix-fr-en"
OUT = STORAGE / "exact-speed-mix-20261116"
QEXE = STORAGE / "qdrant-1.20.1/unpacked/qdrant.exe"
PGBIN = STORAGE / "postgres-pgvector-env/Library/bin"
PGDATA = STORAGE / "postgres-fixture-20261116/data"


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
    meta = json.loads((INPUT / "meta.json").read_text(encoding="utf-8"))
    for name, expected in meta["files_sha256"].items():
        if digest(INPUT / name) != expected:
            raise RuntimeError(f"Input hash mismatch: {name}")
    rows = json.loads((INPUT / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(INPUT / "vectors.npy", allow_pickle=False)
    queries = np.load(INPUT / "queries.npy", allow_pickle=False)[:100]
    ids = np.asarray([row["chunk_id"] for row in rows], dtype=np.int64)
    if vectors.shape != (len(rows), meta["dimension"]) or len(set(ids)) != len(rows) or len(queries) != 100:
        raise RuntimeError("Unexpected input IDs or dimensions")
    OUT.mkdir(exist_ok=False)
    qdir = OUT / "qdrant"
    qdir.mkdir()
    used = set()
    while len(used) < 3:
        used.add(port())
    http, grpc, pgport = sorted(used)
    qenv = os.environ.copy()
    qenv.update({"QDRANT__SERVICE__HOST": "127.0.0.1", "QDRANT__SERVICE__HTTP_PORT": str(http),
                 "QDRANT__SERVICE__GRPC_PORT": str(grpc), "QDRANT__TELEMETRY_DISABLED": "true"})
    penv = os.environ.copy()
    penv["PATH"] = str(PGBIN) + os.pathsep + penv["PATH"]
    with (OUT / "qdrant.log").open("w", encoding="utf-8") as qlog, (OUT / "postgres.log").open("w", encoding="utf-8") as plog:
        qproc = subprocess.Popen([str(QEXE)], cwd=qdir, env=qenv, stdout=qlog, stderr=qlog, creationflags=subprocess.CREATE_NO_WINDOW)
        pproc = None
        try:
            client = QdrantClient(url=f"http://127.0.0.1:{http}", timeout=30)
            for _ in range(60):
                try:
                    client.get_collections()
                    break
                except Exception:
                    if qproc.poll() is not None:
                        raise RuntimeError(f"Qdrant exited {qproc.returncode}")
                    time.sleep(0.5)
            else:
                raise RuntimeError("Qdrant startup timed out")
            client.create_collection("chunks", vectors_config=models.VectorParams(size=meta["dimension"], distance=models.Distance.DOT),
                                     optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0))
            for start in range(0, len(rows), 256):
                client.upsert("chunks", wait=True, points=[models.PointStruct(id=int(ids[i]), vector=vectors[i].tolist())
                    for i in range(start, min(start + 256, len(rows)))])
            pproc = subprocess.Popen([str(PGBIN / "postgres.exe"), "-D", str(PGDATA), "-c", "listen_addresses=127.0.0.1",
                                      "-p", str(pgport)], env=penv, stdout=plog, stderr=plog, creationflags=subprocess.CREATE_NO_WINDOW)
            for _ in range(60):
                try:
                    connection = psycopg.connect(host="127.0.0.1", port=pgport, user="bench", dbname="postgres", connect_timeout=3)
                    break
                except psycopg.OperationalError:
                    if pproc.poll() is not None:
                        raise RuntimeError(f"Postgres exited {pproc.returncode}")
                    time.sleep(0.5)
            else:
                raise RuntimeError("Postgres startup timed out")
            with connection:
                with connection.cursor() as cur:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                    cur.execute(f"CREATE TEMP TABLE chunks (id bigint PRIMARY KEY, embedding vector({meta['dimension']}))")
                    with cur.copy("COPY chunks (id, embedding) FROM STDIN") as copy:
                        for chunk_id, vector in zip(ids, vectors):
                            copy.write_row((int(chunk_id), str(vector.tolist()).replace(" ", "")))
                    cur.execute("ANALYZE chunks")
                    lists = [q.tolist() for q in queries]
                    literals = [str(q).replace(" ", "") for q in lists]

                    def query(method, i):
                        if method == "numpy":
                            scores = vectors @ queries[i]
                            return ids[np.lexsort((ids, -scores))[:10]].tolist()
                        if method == "qdrant":
                            return [p.id for p in client.query_points("chunks", query=lists[i],
                                search_params=models.SearchParams(exact=True), limit=10).points]
                        cur.execute("SELECT id FROM chunks ORDER BY embedding <#> %s::vector, id LIMIT 10", (literals[i],))
                        return [r[0] for r in cur.fetchall()]

                    methods = ("numpy", "qdrant", "pgvector")
                    for method in methods:
                        for i in range(10):
                            query(method, i)
                    samples = {m: [] for m in methods}
                    rankings = {m: [] for m in methods}
                    for round_index in range(3):
                        for method in (methods if round_index != 1 else tuple(reversed(methods))):
                            for i in range(100):
                                start = time.perf_counter_ns()
                                ranking = query(method, i)
                                samples[method].append((time.perf_counter_ns() - start) / 1e6)
                                rankings[method].append(ranking)
                    summary = {}
                    for method in methods:
                        values = sorted(samples[method])
                        overlap = [len(set(rankings[method][j]) & set(rankings["numpy"][j])) / 10 for j in range(300)]
                        summary[method] = {"p50_ms": float(np.median(values)), "p95_ms": values[int(0.95 * len(values)) - 1],
                                           "mean_top10_overlap": float(np.mean(overlap)), "min_top10_overlap": min(overlap)}
                    result = {"dataset": meta["dataset"], "chunks": len(rows), "queries": len(queries), "rounds": 3,
                              "input_meta_sha256": digest(INPUT / "meta.json"), "runner_sha256": digest(Path(__file__)),
                              "qdrant_exe_sha256": digest(QEXE), "postgres_exe_sha256": digest(PGBIN / "postgres.exe"),
                              "numpy": np.__version__, "numpy_blas_threads": 1, "psycopg": psycopg.__version__,
                              "summary": summary, "scope": "exact top-10 IDs; servers include transport; no embeddings or hybrid"}
                    (OUT / "samples.json").write_text(json.dumps({"milliseconds": samples, "rankings": rankings}), encoding="utf-8")
                    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                    print(json.dumps(result), flush=True)
        finally:
            if pproc is not None:
                subprocess.run(["rtk", "proxy", str(PGBIN / "pg_ctl.exe"), "stop", "-D", str(PGDATA), "-m", "fast", "-w"],
                               env=penv, capture_output=True, text=True)
                try:
                    pproc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pproc.terminate()
                    pproc.wait(timeout=30)
            qproc.terminate()
            qproc.wait(timeout=30)


if __name__ == "__main__":
    main()
