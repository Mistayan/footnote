"""Verify isolated localhost PostgreSQL + pgvector with a small fixture."""
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "bench/work/storage"
BIN = BASE / "postgres-pgvector-env/Library/bin"
DATA = BASE / "postgres-fixture-20261116/data"
LOG = BASE / "postgres-fixture-20261116/server.log"


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["PATH"] = str(BIN) + os.pathsep + env["PATH"]
    cmd = [str(BIN / "postgres.exe"), "-D", str(DATA), "-c", "listen_addresses=127.0.0.1", "-p", str(port)]
    with LOG.open("x", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            psql = ["rtk", "proxy", str(BIN / "psql.exe"), "-X", "-h", "127.0.0.1", "-p", str(port),
                    "-U", "bench", "-d", "postgres", "-tA", "-v", "ON_ERROR_STOP=1"]
            for _ in range(60):
                ready = subprocess.run([*psql, "-c", "SELECT 1"], env=env, capture_output=True, text=True)
                if ready.returncode == 0:
                    break
                if proc.poll() is not None:
                    raise RuntimeError(f"Postgres exited {proc.returncode}")
                time.sleep(0.5)
            else:
                raise RuntimeError("Postgres startup timed out")
            sql = ("CREATE EXTENSION IF NOT EXISTS vector; "
                   "CREATE TEMP TABLE items(id int, stack text, embedding vector(2)); "
                   "INSERT INTO items VALUES (1,'rust','[1,0]'),(2,'python','[0.8,0.6]'),(3,'rust','[0,1]'); "
                   "SELECT json_agg(id ORDER BY distance, id) FROM "
                   "(SELECT id, embedding <#> '[1,0]'::vector AS distance FROM items WHERE stack='rust') AS ranked;")
            result = subprocess.run([*psql, "-c", sql], env=env, capture_output=True, text=True, check=True)
            if "[1, 3]" not in result.stdout and "[1,3]" not in result.stdout:
                raise RuntimeError(f"Unexpected result: {result.stdout}")
            print("PostgreSQL 16.14 + pgvector 0.8.3: exact inner product and filter passed: [1, 3]", flush=True)
        finally:
            subprocess.run(["rtk", "proxy", str(BIN / "pg_ctl.exe"), "stop", "-D", str(DATA), "-m", "fast", "-w"],
                           env=env, capture_output=True, text=True)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=30)


if __name__ == "__main__":
    main()
