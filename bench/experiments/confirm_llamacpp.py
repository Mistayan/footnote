"""Test 5, stage B condition 2: held-out confirmation of the frozen survivors (LLAMACPP-MODELS.md, scope cut of 15 November).

Run in bench/.labenv: `python -I experiments/confirm_llamacpp.py [label-substring ...]`. Reuses the shipped pair's existing
`models2_baseline` held-out receipts (same configuration as the test 5 dev baseline). Appends to LLAMACPP-CONFIRMATION.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from confirm_models import BENCH, GROUPS, run_receipt  # noqa: E402

SURVIVORS = {"T5 gguf-embeddinggemma alone in the hybrid": ("English", "French/mixed"),
             "T5 gguf-jina-v5-small alone in the hybrid": ("French/mixed",),
             "T5 gguf-jina-v5-nano alone in the hybrid": ("French/mixed",)}


def baseline(dataset: str) -> Path:
    hits = sorted((BENCH / "receipts/heldout").glob(f"*-{dataset}-lab_models2_baseline-heldout.json"))
    assert hits, f"no baseline held-out receipt for {dataset}"
    return hits[-1]


def main() -> None:
    only = sys.argv[1:]
    rows = [json.loads(line) for name in ("llamacpp", "llamacpp2")
            for line in (BENCH / f"sweeps/{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cfgs = {(r["dataset"], r["label"]): r["cfg"] for r in rows if r["split"] == "dev" and "error" not in r}
    output = BENCH / "experiments/LLAMACPP-CONFIRMATION.md"
    if not output.exists():
        output.write_text("# Test 5 held-out confirmation\n\nCondition 2 of `LLAMACPP-MODELS.md`: paired bootstrap 95 % interval of the "
                          "nDCG@10 difference above zero on each corpus of the group. Configurations frozen from the dev sweep.\n\n",
                          encoding="utf-8")
    for label, groups in SURVIVORS.items():
        if only and not any(s in label for s in only):
            continue
        for dataset in {d for g in groups for d in GROUPS[g]}:
            cfg = cfgs[(dataset, label)]
            name = "llamacpp_" + hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]
            first, second = baseline(dataset), run_receipt(dataset, name, cfg)
            result = subprocess.run(["rtk", "proxy", sys.executable, "-I", str(BENCH / "compare.py"), dataset,
                                     str(first.with_suffix(".rankings.json.gz")), str(second.with_suffix(".rankings.json.gz")),
                                     "--split", "heldout"], check=True, capture_output=True, text=True)
            with output.open("a", encoding="utf-8") as sink:
                sink.write(f"## {label}, {dataset}\n\n```text\n{result.stdout.strip()}\n```\n\n"
                           f"[Baseline receipt](../receipts/heldout/{first.name}), [candidate receipt](../receipts/heldout/{second.name}).\n\n")
            print(result.stdout, flush=True)


if __name__ == "__main__":
    main()
