"""ICM (rtk-ai/icm) as a bench engine: local HTTP server, fresh SQLite database per corpus, keyword-only v2 recall.

    bench/.dbenv/Scripts/python.exe -I bench/run.py syntec ext:icm

Binary: ICM 0.11.5 built from source commit 3b9fcd7 with `--no-default-features --features backend-sqlite,http-api`, so it has no
embedding model. This measures ICM's keyword path (FTS5 BM25 + date arm, fused by RRF), not its default hybrid with multilingual E5
large. Server handling follows bench/experiments/longmem_icm.py: explicit empty config, no extraction, no LLM, no host setup.
One memory per document. ICM may merge identical memories; merged documents share one ID and are all returned, in corpus order.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
WORK = BENCH / "work"
BINARY = BENCH / ".cache" / "icm-source" / "target" / "release" / "icm.exe"
MAX_BYTES = 60000  # same split as the LongMemEval runner


def _bytes(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _split(text: str):
    data = text.encode("utf-8")
    while data:
        end = min(MAX_BYTES, len(data))
        while end < len(data) and data[end] & 0xC0 == 0x80:  # never cut inside a UTF-8 character
            end -= 1
        yield data[:end].decode("utf-8")
        data = data[end:]


class IcmEngine:
    id = "icm"
    latency_scope = "localhost HTTP POST /recall to a resident ICM server (keyword-only v2, no embeddings)"

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.root: Path | None = None
        self.ids: dict[str, list[str]] = {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.config = {"product": "ICM 0.11.5", "mode": "keyword-only (--no-embeddings), recall engine v2",
                       "lexical": "SQLite FTS5 BM25", "fusion": "ICM v2 RRF over FTS and date arms", "chunking": "none (one memory per document, split above 60,000 UTF-8 bytes)",
                       "query_clip_bytes": 500, "caveat": "not ICM's default hybrid with multilingual-e5-large; no extraction, no LLM"}

    def versions(self) -> dict:
        out = subprocess.run([str(BINARY), "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        return {"icm": out, "source_commit": "3b9fcd7d726d82268f3d67a11ab63fb645442536",
                "binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest(),
                "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def _post(self, path: str, payload: dict):
        req = urllib.request.Request(f"{self.base}{path}?format=json", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with self.opener.open(req, timeout=120) as r:
            return json.load(r)

    def _start(self) -> None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        cfg = self.root / "config.toml"
        cfg.write_text('[extraction.summarizer]\nprovider = "none"\n', encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("ICM_")}
        env.update({"ICM_CONFIG": str(cfg), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
        cmd = [str(BINARY), "--db", str(self.root / "memory.db"), "--no-embeddings", "serve", "--http", f"127.0.0.1:{port}"]
        self.log = (self.root / "server.log").open("wb")
        self.proc = subprocess.Popen(cmd, cwd=str(self.root), env=env, stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        atexit.register(self.close)  # bench/run.py never calls close(); the server must not outlive the run
        deadline = time.monotonic() + 120
        while True:
            if self.proc.poll() is not None:
                raise RuntimeError(f"ICM exited with code {self.proc.returncode}; see {self.root / 'server.log'}")
            try:
                with self.opener.open(self.base + "/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except (urllib.error.URLError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("ICM server did not become healthy")
                time.sleep(0.1)
        try:  # refuse an old binary silently ignoring the v2 engine
            self._post("/recall", {"query": "capability probe", "engine": "__invalid_engine__"})
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
        else:
            raise RuntimeError("ICM did not reject an invalid engine; v2 support unverified")

    def prepare(self, dataset: str, corpus: dict) -> dict:
        self.close()
        self.root = WORK / dataset / self.id
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        self._start()
        self.ids = {}
        skipped = merged = units = 0
        t = time.perf_counter()
        for doc_id, (title, text) in corpus.items():
            body = f"{title}\n{text}".strip() if title else text.strip()
            if not body:
                skipped += 1
                continue
            for part in _split(body):
                stored = self._post("/store", {"topic": "benchmark", "content": part})
                if not isinstance(stored, list) or not stored or "id" not in stored[0]:
                    raise ValueError(f"unexpected ICM store response: {stored!r:.200}")
                docs = self.ids.setdefault(stored[0]["id"], [])
                merged += bool(docs) and doc_id not in docs
                if doc_id not in docs:
                    docs.append(doc_id)
                units += 1
        build_ms = (time.perf_counter() - t) * 1000
        store = sum(_bytes(self.root / f"memory.db{s}") for s in ("", "-wal", "-shm"))
        return {"documents": len(corpus), "skipped_empty": skipped, "build_ms": build_ms, "embed_ms": None, "disk_bytes": store,
                "store_bytes": store, "model_cache_bytes": 0, "chunks": units, "merged_documents": merged}

    def search(self, qid: str, text: str, k: int) -> list[str]:
        q = text.encode("utf-8")[:500].decode("utf-8", errors="ignore")
        rows = self._post("/recall", {"query": q, "limit": 2 * k, "engine": "v2"})
        if isinstance(rows, dict) and rows.get("results") == []:  # ICM's shape for "No memories found."
            return []
        if not isinstance(rows, list):
            raise ValueError(f"unexpected ICM recall response: {rows!r:.200}")
        out: list[str] = []
        for row in rows:
            if row["id"] not in self.ids:
                raise ValueError("unknown memory ID from ICM")
            out += [d for d in self.ids[row["id"]] if d not in out]
        return out[:k]

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        self.proc = None
        if getattr(self, "log", None):
            self.log.close()
            self.log = None


ENGINES = {IcmEngine.id: IcmEngine}
