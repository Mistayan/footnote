"""Post-hoc paired nDCG intervals for the expanded Helix diagnostic."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
import fetch  # noqa: E402
import metrics  # noqa: E402

STORAGE = BENCH / "work/storage/helixdb-3.7.0"
OUT = STORAGE / "remaining-bootstrap-20261116.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise RuntimeError("Existing bootstrap result is preserved")
    output = []
    for dataset in ("nfcorpus", "scifact", "alloprof", "mix-fr-en"):
        folder = STORAGE / ("embedded-" + dataset + "-hybrid-remaining")
        path = folder / "rankings.json"
        rankings = json.loads(path.read_text(encoding="utf-8"))
        _, _, qrels = fetch.load(dataset, "test")
        reference, candidate = rankings["reference"], rankings["helix"][0]
        scored = [q for q in reference if q in qrels and any(v > 0 for v in qrels[q].values())]
        delta = np.asarray([metrics.ndcg_at_k(candidate[q], qrels[q], 10) - metrics.ndcg_at_k(reference[q], qrels[q], 10)
                            for q in scored], dtype=np.float64)
        rng = np.random.default_rng(20261116)
        bootstrap = np.asarray([delta[rng.integers(0, len(delta), size=len(delta))].mean() for _ in range(10000)])
        output.append({"dataset": dataset, "queries": len(scored), "mean_difference": float(delta.mean()),
                       "ci95": [float(v) for v in np.quantile(bootstrap, [0.025, 0.975])],
                       "ranking_sha256": digest(path)})
    result = {"method": "post-hoc paired query bootstrap; 10000 resamples; seed 20261116", "rows": output,
              "runner_sha256": digest(Path(__file__)), "caveat": "reused benchmark test sets; not a fresh holdout"}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
