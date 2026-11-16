"""Test a pinned local Qdrant server on a tiny, isolated exact-search fixture."""
from pathlib import Path
import os
import socket
import subprocess
import time

from qdrant_client import QdrantClient, models

ROOT = Path(__file__).resolve().parents[2]
QDRANT_DIR = ROOT / "bench/work/storage/qdrant-1.20.1"
EXE = QDRANT_DIR / "unpacked/qdrant.exe"


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    run = QDRANT_DIR / "fixture"
    run.mkdir(exist_ok=False)
    http, grpc = port(), port()
    while grpc == http:
        grpc = port()
    env = os.environ.copy()
    env.update({"QDRANT__SERVICE__HOST": "127.0.0.1", "QDRANT__SERVICE__HTTP_PORT": str(http),
                "QDRANT__SERVICE__GRPC_PORT": str(grpc), "QDRANT__TELEMETRY_DISABLED": "true"})
    with (run / "server.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen([str(EXE)], cwd=run, env=env, stdout=log, stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            client = QdrantClient(url=f"http://127.0.0.1:{http}", timeout=5)
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
            client.create_collection("fixture", vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
            client.upsert("fixture", wait=True, points=[
                models.PointStruct(id=1, vector=[1.0, 0.0], payload={"stack": "rust"}),
                models.PointStruct(id=2, vector=[0.8, 0.6], payload={"stack": "python"}),
                models.PointStruct(id=3, vector=[0.0, 1.0], payload={"stack": "rust"}),
            ])
            filt = models.Filter(must=[models.FieldCondition(key="stack", match=models.MatchValue(value="rust"))])
            result = client.query_points("fixture", query=[1.0, 0.0], query_filter=filt,
                                         search_params=models.SearchParams(exact=True), limit=3).points
            ids = [point.id for point in result]
            if ids != [1, 3]:
                raise RuntimeError(f"Unexpected filtered neighbor IDs: {ids}")
            print(f"Qdrant 1.20.1: exact search and payload filter passed: {ids}", flush=True)
        finally:
            proc.terminate()
            proc.wait(timeout=30)


if __name__ == "__main__":
    main()
