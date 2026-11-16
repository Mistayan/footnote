"""Compare the existing per-source cap on the previously observed Grounded Docs data.

Run: bench/.labenv/Scripts/python.exe -I bench/experiments/docs_page_cap.py <new-output-dir>
Rules and limitations: DOCS-FOLLOWUPS-2026-11-15.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

OUT = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent))
import docs_vs_grounded as g  # noqa: E402


def sha(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    source = g.REPO / "bench/work/gd/run1"
    dataset = g.REPO / "bench/work/gd/dataset.yaml"
    questions = [e["vars"] for e in yaml.safe_load(dataset.read_text(encoding="utf-8"))["entries"]]
    files = {"dataset": dataset, "binary": Path(g.FOOTNOTE), "page_manifest": source / "manifest.json",
             "grounded_hybrid": source / "gd-hybrid.json", "original_hybrid": source / "fn-hybrid.json",
             "previous_grouped": source / "fn-grouped.json", "protocol": Path(__file__).with_name("DOCS-FOLLOWUPS-2026-11-15.md"),
             "runner": Path(__file__), "metric_runner": Path(g.__file__)}
    files.update({f"db_{lib}": source / "footnote" / f"{lib}.db" for lib in g.RECIPE})
    files.update({f"model_{i}": Path(model) / "manifest.json" for i, model in enumerate(g.MODELS)})
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing benchmark inputs: {missing}")
    hashes = {name: {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for name, p in files.items()}
    (OUT / "inputs.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    manifest = json.loads(files["page_manifest"].read_text(encoding="utf-8"))
    baseline = json.loads(files["grounded_hybrid"].read_text(encoding="utf-8"))
    original = json.loads(files["original_hybrid"].read_text(encoding="utf-8"))
    old_grouped = json.loads(files["previous_grouped"].read_text(encoding="utf-8"))

    def query_one(item: tuple[int, dict], mode: str) -> tuple[str, list[str]]:
        i, q = item
        cmd = [g.FOOTNOTE, "--db", str(files[f"db_{q['library']}"]), "search", q["query"], "--limit", "5", "--per-source", "1"]
        if mode == "hybrid":
            cmd += ["--mode", "hybrid", *[arg for m in g.MODELS for arg in ("--model", m)]]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
        if proc.returncode:
            raise RuntimeError(f"query {i} {mode}: exit {proc.returncode}: {proc.stderr[-500:]} {proc.stdout[-500:]}")
        result = json.loads(proc.stdout)
        if "error" in result or "results" not in result:
            raise RuntimeError(f"query {i} {mode}: {result}")
        urls = []
        for hit in result["results"]:
            key = g.key(hit["path"])
            if key not in manifest:
                raise RuntimeError(f"query {i}: page missing from manifest: {key}")
            urls.append(manifest[key])
        return str(i), urls

    rankings = {}
    for mode in ("lexical", "hybrid"):
        passes = []
        for pass_no in (1, 2):
            with ThreadPoolExecutor(max_workers=8) as pool:
                result = dict(pool.map(lambda item: query_one(item, mode), enumerate(questions)))
            (OUT / f"{mode}-pass{pass_no}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            passes.append(result)
            print(f"{mode} pass {pass_no}: {len(result)} queries", flush=True)
        if passes[0] != passes[1]:
            raise RuntimeError(f"{mode}: repeated rankings differ; results are not deterministic")
        rankings[mode] = passes[0]

    variants = {"grounded_hybrid": baseline, "original_hybrid": original,
                "prior_top20_grouped_hybrid": old_grouped["hybrid"],
                "native_cap_hybrid": rankings["hybrid"], "native_cap_lexical": rankings["lexical"]}
    per_query = {name: [g.metrics(run[str(i)], q["qrels"]) for i, q in enumerate(questions)] for name, run in variants.items()}
    base = [m["ndcg_at_5"] for m in per_query["grounded_hybrid"]]
    summary = {}
    for name, ms in per_query.items():
        metrics = {key: sum(m[key] for m in ms) / len(ms) for key in ms[0]}
        diff, lo, hi = g.bootstrap([m["ndcg_at_5"] for m in ms], base)
        by_library = {}
        for lib in g.RECIPE:
            items = [m["ndcg_at_5"] for m, q in zip(ms, questions) if q["library"] == lib]
            by_library[lib] = sum(items) / len(items)
        summary[name] = {"metrics": metrics, "difference_vs_grounded": diff, "ci95": [lo, hi], "ndcg_by_library": by_library}
    changed_inputs = [name for name, entry in hashes.items() if sha(Path(entry["path"])) != entry["sha256"]]
    if changed_inputs:
        raise RuntimeError(f"inputs changed while measuring: {changed_inputs}")
    (OUT / "results.json").write_text(json.dumps({"summary": summary, "per_query": per_query, "repeat_rankings_identical": True,
                                                  "independent_holdout": False}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
