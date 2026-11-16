"""EmbeddingGemma same-weights diagnostic on Grounded Docs' exported pages.

Run: bench/.labenv/Scripts/python.exe -I bench/experiments/docs_same_weights.py <new-output-dir>
Protocol: DOCS-FOLLOWUPS-2026-11-15.md. CPU/GGUF; indexing can take a long time.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

OUT = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent))
import docs_vs_grounded as g  # noqa: E402

ROOT = g.REPO
SOURCE = g.RUN
BIN = ROOT / "target/llama/release/footnote.exe"
MODEL = ROOT / "bench/work/gd/gemma-profile"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def cli(*args):
    result = subprocess.run([str(BIN), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                            timeout=7200, creationflags=NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f"exit {result.returncode}: {result.stdout[-1000:]} {result.stderr[-1000:]}")
    data = json.loads(result.stdout)
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


class Client:
    def __init__(self, db, state):
        self.seq = 0
        self.p = subprocess.Popen([str(BIN), "--db", str(db), "serve", "--mcp"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                  env=dict(os.environ, FOOTNOTE_STATE_DIR=str(state)), creationflags=NO_WINDOW)
        self.messages = queue.Queue()
        def read():
            for line in self.p.stdout:
                self.messages.put(line)
            self.messages.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "same-weights-diagnostic", "version": "1"}})
            self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            self.p.stdin.flush()
        except Exception:
            self.close()
            raise

    def call(self, method, params):
        self.seq += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        deadline = time.monotonic() + 120
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MCP response exceeded 120 seconds")
            try:
                line = self.messages.get(timeout=remaining)
            except queue.Empty as e:
                raise TimeoutError("MCP response exceeded 120 seconds") from e
            if line is None:
                raise RuntimeError("MCP server closed")
            reply = json.loads(line)
            if reply.get("id") == self.seq:
                if reply.get("error") or reply.get("result", {}).get("isError"):
                    raise RuntimeError(str(reply))
                return reply["result"]

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait(timeout=10)
        self.reader.join(timeout=2)
        self.p.stdout.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "results.json").exists():
        raise FileExistsError("completed run is immutable; choose a new output directory")
    sources = {lib: SOURCE / "footnote" / f"{lib}.db" for lib in g.RECIPE}
    inputs = [BIN, MODEL / "manifest.json", MODEL / "model.gguf", g.DATASET,
              SOURCE / "manifest.json", SOURCE / "gd-hybrid.json", ROOT / "bench/experiments/DOCS-FOLLOWUPS-2026-11-15.md",
              Path(__file__), *sources.values()]
    hashes = {str(p): sha(p) for p in inputs}
    if hashes[str(MODEL / "model.gguf")] != "b5ce9d77a3fc4b3b39ccb5643c36777911cc4eb46a66962eadfa3f5f60490d63":
        raise RuntimeError("not the GGUF file used by Grounded Docs")
    receipt = OUT / "inputs.json"
    if receipt.exists() and json.loads(receipt.read_text(encoding="utf-8")) != hashes:
        raise RuntimeError("cannot resume: an input or runner changed")
    if not receipt.exists():
        receipt.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    profile = OUT / "profile.json"
    if not profile.exists():
        profile.write_text((MODEL / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    dbs = {}
    for lib in ("vite", "tailwindcss", "fastapi", "react", "python"):
        source = sources[lib]
        db = OUT / f"{lib}.db"
        source_index = Path(str(source) + ".tantivy")
        index = Path(str(db) + ".tantivy")
        marker = OUT / f"{lib}.build.json"
        if marker.exists():
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if sha(db) != previous["db_sha256"]:
                raise RuntimeError(f"completed database changed: {lib}")
            dbs[lib] = db
            print(f"reusing verified {lib} build", flush=True)
            continue
        if not db.exists():
            temp = OUT / f"{lib}.db-copying"
            if temp.exists():
                raise RuntimeError(f"incomplete copy needs inspection: {temp}")
            shutil.copy2(source, temp)
            if sha(temp) != hashes[str(source)]:
                raise RuntimeError(f"copy differs for {lib}")
            temp.replace(db)
        if not index.exists():
            temp_index = OUT / f"{lib}.tantivy-copying"
            if temp_index.exists():
                raise RuntimeError(f"incomplete index copy needs inspection: {temp_index}")
            shutil.copytree(source_index, temp_index)
            temp_index.replace(index)
        print(f"building {lib} with EmbeddingGemma", flush=True)
        t = time.monotonic()
        build = cli("--db", db, "rebuild-embeddings", "--model", MODEL)
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as c:
            chunks = c.execute("SELECT count(*) FROM chunks c JOIN sources s ON s.id=c.source_id WHERE s.status='indexed'").fetchone()[0]
            vectors = c.execute("SELECT count(*) FROM embeddings WHERE kind='chunk' AND model=?", [sha(MODEL / "manifest.json")]).fetchone()[0]
        if not chunks or vectors != chunks:
            raise RuntimeError(f"incomplete {lib}: {chunks} chunks vs {vectors} vectors")
        marker.write_text(json.dumps({"report": build, "chunks": chunks, "db_sha256": sha(db),
                                      "seconds_contended": time.monotonic() - t}, indent=2), encoding="utf-8")
        print(f"built {lib}: {chunks} vectors, {time.monotonic() - t:.1f} s", flush=True)
        dbs[lib] = db

    questions = [e["vars"] for e in yaml.safe_load((g.DATASET).read_text(encoding="utf-8"))["entries"]]
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    grounded = json.loads((SOURCE / "gd-hybrid.json").read_text(encoding="utf-8"))
    runs = []
    for repeat in (1, 2):
        ranking = {}
        for lib, db in dbs.items():
            client = Client(db, OUT)
            try:
                for i, q in enumerate(questions):
                    if q["library"] != lib:
                        continue
                    result = client.call("tools/call", {"name": "footnote_recall", "arguments": {
                        "query": q["query"], "mode": "hybrid", "model": [str(MODEL)], "limit": 5, "per_source": 1}})
                    value = json.loads(result["content"][0]["text"])
                    urls = []
                    for hit in value["results"]:
                        key = g.key(hit["path"])
                        if key not in manifest:
                            raise RuntimeError(f"missing page mapping for {key}")
                        urls.append(manifest[key])
                    ranking[str(i)] = urls
            finally:
                client.close()
        path = OUT / f"rankings-pass{repeat}.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != ranking:
            raise RuntimeError(f"stored ranking changed: {path}")
        if not path.exists():
            path.write_text(json.dumps(ranking, indent=2), encoding="utf-8")
        runs.append(ranking)
        print(f"ranking pass {repeat}: {len(ranking)} questions", flush=True)
    if runs[0] != runs[1]:
        raise RuntimeError("rankings differed on repeat")
    nd = lambda result: [g.metrics(result[str(i)], q["qrels"])["ndcg_at_5"] for i, q in enumerate(questions)]
    values = nd(runs[0])
    diff, lo, hi = g.bootstrap(values, nd(grounded))
    ms = [g.metrics(runs[0][str(i)], q["qrels"]) for i, q in enumerate(questions)]
    summary = {k: sum(m[k] for m in ms) / len(ms) for k in ms[0]}
    if any(sha(Path(p)) != h for p, h in hashes.items()):
        raise RuntimeError("an input changed during measurement")
    report = {"summary": summary, "diff_vs_grounded": diff, "ci95": [lo, hi], "repeat_rankings_identical": True,
              "same_weights_only": True, "independent_holdout": False,
              "confounders": ["different chunking and indexing", "different tokenizer runtime and truncation", "different fusion and result assembly", "CPU and GPU quantization/runtime differences"]}
    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
