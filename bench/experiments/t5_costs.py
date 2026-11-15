"""Test 5, stage B conditions 3 to 5 for the survivors (LLAMACPP-MODELS.md): query p95 on the CPU, download size, GPU indexing
agreement, and the servers' RAM and VRAM. Run in bench/.labenv after confirm_llamacpp.py, on a quiet machine:

    python -I experiments/t5_costs.py [label-substring ...]

Rows append to sweeps/t5_costs.jsonl; GPU-built held-out receipts and their comparisons append to LLAMACPP-CONFIRMATION.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from confirm_models import BENCH, GROUPS, run_receipt  # noqa: E402

sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import fetch  # noqa: E402
from run import pct  # noqa: E402
import lab  # noqa: E402
import models  # noqa: E402

SURVIVORS = {"gguf-embeddinggemma": ("English", "French/mixed"), "gguf-jina-v5-nano": ("French/mixed",),
             "gguf-jina-v5-small": ("French/mixed",)}
LABEL = "T5 {} alone in the hybrid"


def memory(pid: int) -> dict:
    """Working set and dedicated VRAM of one process (Windows counters); best effort, reported and never pass/fail."""
    ps = (f"$p = Get-Process -Id {pid}; $v = (Get-Counter '\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage' -ErrorAction "
          f"SilentlyContinue).CounterSamples | Measure-Object CookedValue -Sum; "
          "@{ram=$p.WorkingSet64; peak=$p.PeakWorkingSet64; vram=$v.Sum} | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    try:
        return {k: round((v or 0) / 2**20) for k, v in json.loads(out).items()}  # MiB
    except ValueError:
        return {}


def query_cost(name: str, datasets: list[str]) -> list[dict]:
    enc = lab.LlamaEncoder(name)
    rows = []
    try:
        for dataset in datasets:
            _, queries, _ = fetch.load(dataset, "dev")
            texts = [t.encode("utf-8")[:500].decode("utf-8", errors="ignore") for _, t in sorted(queries.items())[:100]]
            for t in texts[:3]:
                enc.embed([t], "query")
            times = []
            for t in texts:
                start = time.perf_counter()
                enc.embed([t], "query")
                times.append((time.perf_counter() - start) * 1000)
            rows.append({"dataset": dataset, "queries": len(times), "p50": round(statistics.median(times), 3),
                         "p95": round(pct(times, 0.95), 3), "cpu_server": memory(enc.servers[0][0].pid)})
    finally:
        enc.close()
    return rows


def gpu_memory(name: str) -> dict:
    enc = lab.LlamaEncoder(name + "-gpu")
    try:
        corpus, _, _ = fetch.load("mix-fr-en", "dev")
        enc.embed([f"{a} {b}" for a, b in list(corpus.values())[:512]], "passage")
        return memory(enc.servers[99][0].pid)
    finally:
        enc.close()


def receipt_for(dataset: str, cfg: dict) -> Path:
    name = "llamacpp_" + hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
    hits = sorted((BENCH / "receipts/heldout").glob(f"*-{dataset}-lab_{name}-heldout.json"))
    assert hits, f"run confirm_llamacpp.py first: no CPU held-out receipt for {dataset} {name}"
    return hits[-1]


def gpu_agreement(name: str, dataset: str, cfg: dict) -> dict:
    gcfg = json.loads(json.dumps(cfg))
    gcfg["dense"]["model"] = name + "-gpu"
    gname = "llamacpp_" + hashlib.sha256(json.dumps(gcfg, sort_keys=True).encode()).hexdigest()[:12]
    cpu_receipt, gpu_receipt = receipt_for(dataset, cfg), run_receipt(dataset, gname, gcfg)
    result = subprocess.run(["rtk", "proxy", sys.executable, "-I", str(BENCH / "compare.py"), dataset,
                             str(cpu_receipt.with_suffix(".rankings.json.gz")), str(gpu_receipt.with_suffix(".rankings.json.gz")),
                             "--split", "heldout"], check=True, capture_output=True, text=True)
    with (BENCH / "experiments/LLAMACPP-CONFIRMATION.md").open("a", encoding="utf-8") as sink:
        sink.write(f"## GPU-built index (condition 5): {name}, {dataset} (A = CPU-built, B = GPU-built)\n\n"
                   f"```text\n{result.stdout.strip()}\n```\n\n[GPU receipt](../receipts/heldout/{gpu_receipt.name}).\n\n")
    ndcg = [_ndcg(p) for p in (cpu_receipt, gpu_receipt)]
    # both matrices come from the lab cache written by the two held-out runs, so nothing is re-encoded here
    engine = lab.LabEngine(gname, gcfg)
    engine.prepare(dataset, fetch.load(dataset, "heldout")[0])
    cpu = lab.cached_embed(lab.get_encoder(name, None), engine.texts, "passage")
    cos = (engine.emb * cpu).sum(axis=1)
    return {"dataset": dataset, "ndcg_cpu": ndcg[0], "ndcg_gpu": ndcg[1], "ndcg_diff": round(ndcg[1] - ndcg[0], 5),
            "cos_min": float(cos.min()), "cos_below_0.9999": int((cos < 0.9999).sum()), "documents": int(len(cos)),
            "nan": int((~np.isfinite(engine.emb)).sum())}


def _ndcg(path: Path) -> float:
    def walk(node):
        if isinstance(node, dict):
            if "ndcg@10" in node:
                return node["ndcg@10"]
            for v in node.values():
                if (found := walk(v)) is not None:
                    return found
        return None
    return walk(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    only = sys.argv[1:]
    rows = [json.loads(line) for name in ("llamacpp", "llamacpp2")
            for line in (BENCH / f"sweeps/{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cfgs = {(r["dataset"], r["label"]): r["cfg"] for r in rows if r["split"] == "dev" and "error" not in r}
    out = BENCH / "sweeps/t5_costs.jsonl"
    for name, groups in SURVIVORS.items():
        if only and not any(s in name for s in only):
            continue
        datasets = sorted({d for g in groups for d in GROUPS[g]})
        row = {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "model": name,
               "file_bytes": models.gguf_path(name).stat().st_size, "query_cpu": query_cost(name, datasets),
               "gpu_server": gpu_memory(name),
               "gpu_index": [gpu_agreement(name, d, cfgs[(d, LABEL.format(name))]) for d in datasets]}
        with out.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(row) + "\n")
        print(json.dumps(row, indent=1), flush=True)


if __name__ == "__main__":
    main()
