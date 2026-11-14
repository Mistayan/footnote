"""Freeze dev-qualified model configurations and run their heldout checks.

Run after the dev sweep and model timings, in bench/.labenv. This never changes
the product defaults. Runtime/production integration remains a separate gate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

BENCH = Path(__file__).resolve().parents[1]
GROUPS = {"English": ("scifact", "nfcorpus"), "French/mixed": ("alloprof", "mix-fr-en")}
BASE = "M0 shipped pair: bekko-a8m + gte-small"


def select_candidates(rows: list[dict]) -> list[dict]:
    latest = {(row["dataset"], row["label"]): row for row in rows if row["split"] == "dev"}
    chosen = []
    for group, datasets in GROUPS.items():
        baselines = [latest.get((dataset, BASE)) for dataset in datasets]
        if any(row is None or "error" in row for row in baselines):
            raise ValueError(f"missing or failed dev baseline: {group}")
        labels = sorted({label for dataset, label in latest if dataset in datasets and label != BASE})
        for label in labels:
            candidates = [latest.get((dataset, label)) for dataset in datasets]
            if any(row is None or "error" in row for row in candidates):
                continue
            if candidates[0]["cfg"] != candidates[1]["cfg"]:
                raise ValueError(f"candidate configuration changed across {group}: {label}")
            gains = [row["ndcg@10"] - base["ndcg@10"] for row, base in zip(candidates, baselines)]
            if all(gain >= .01 - 1e-9 for gain in gains):
                chosen.append({"group": group, "datasets": datasets, "label": label, "cfg": candidates[0]["cfg"], "dev_gains": gains})
    return chosen


def run_receipt(dataset: str, name: str, cfg: dict) -> Path:
    folder = BENCH / "receipts/heldout"
    before = set(folder.glob("*.json"))
    subprocess.run(["rtk", "proxy", sys.executable, "-I", str(BENCH / "run.py"), dataset, f"lab:{name}",
                    "--split", "heldout", "--lab-json", json.dumps(cfg)], check=True)
    hits = []
    for path in set(folder.glob("*.json")) - before:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt["dataset"]["id"] == dataset and receipt["engine"]["id"] == f"lab:{name}":
            if receipt["partial"] or not receipt["determinism"]["identical_rankings"]:
                raise ValueError(f"incomplete or non-deterministic heldout receipt: {path}")
            hits.append(path)
    if len(hits) != 1:
        raise ValueError(f"expected one new heldout receipt, found {len(hits)}")
    return hits[0]


def main() -> None:
    rows = [json.loads(line) for line in (BENCH / "sweeps/models2.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen = select_candidates(rows)
    output = BENCH / "experiments/MODEL-CONFIRMATION.md"
    output.write_text("# Model heldout confirmation\n\nCandidates must gain at least 0.01 nDCG@10 on both dev corpora of a language group. "
                      "Configurations are frozen before heldout scoring. Positive bootstrap intervals alone do not authorize a production change; "
                      "latency, memory and integration checks still apply. Failed or incomplete dev configurations are ineligible. "
                      "Intervals are per comparison, without multiplicity correction.\n\n", encoding="utf-8")
    if not chosen:
        with output.open("a", encoding="utf-8") as sink:
            sink.write("No complete candidate cleared the dev threshold in either language group. No heldout tuning or product change.\n")
        print("No model candidate qualifies for heldout confirmation.", flush=True)
        return
    baselines = {(row["dataset"]): row["cfg"] for row in rows if row["split"] == "dev" and row["label"] == BASE and "error" not in row}
    references = {}
    for candidate in chosen:
        name = "models2_" + hashlib.sha256(json.dumps(candidate["cfg"], sort_keys=True).encode()).hexdigest()[:12]
        with output.open("a", encoding="utf-8") as sink:
            sink.write(f"## {candidate['group']}: {candidate['label']}\n\nDev gains: {candidate['dev_gains']}.\n\n")
        for dataset in candidate["datasets"]:
            if dataset not in references:
                references[dataset] = run_receipt(dataset, "models2_baseline", baselines[dataset])
            receipt = run_receipt(dataset, name, candidate["cfg"])
            first, second = references[dataset], receipt
            result = subprocess.run(["rtk", "proxy", sys.executable, "-I", str(BENCH / "compare.py"), dataset,
                                     str(first.with_suffix(".rankings.json.gz")), str(second.with_suffix(".rankings.json.gz")),
                                     "--split", "heldout"], check=True, capture_output=True, text=True)
            with output.open("a", encoding="utf-8") as sink:
                sink.write(f"```text\n{result.stdout.strip()}\n```\n\n")
                sink.write(f"[Baseline receipt](../receipts/heldout/{first.name}), [candidate receipt](../receipts/heldout/{second.name}).\n\n")
            print(result.stdout, flush=True)


if __name__ == "__main__":
    main()
