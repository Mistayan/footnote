"""Post-observation diagnostic: group the top 20 crawl hits by normalized source URL."""
from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path(sys.argv[1]).resolve()
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent))
import docs_crawl as c  # noqa: E402
g = c.g


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    base, qs = c.WORK / "minimal", c.queries()
    manifest = {}
    for lib in g.RECIPE:
        manifest.update(c.urls_of("minimal", lib))
    paths = [Path(g.FOOTNOTE), g.REPO / "bench/work/gd/dataset.yaml", c.GD / "gd-hybrid.json", Path(__file__),
             *[Path(m) / "manifest.json" for m in g.MODELS],
             *[base / "footnote" / f"{lib}.db" for lib in g.RECIPE],
             *[base / lib / "urls.json" for lib in g.RECIPE]]
    hashes = {str(p): sha(p) for p in paths}
    (OUT / "inputs.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    def one(i):
        q = qs[i]
        args = ["search", q["query"], "--limit", "20", "--mode", "hybrid",
                *[a for m in g.MODELS for a in ("--model", m)]]
        hits = g.fn(base / "footnote" / f"{q['library']}.db", *args)["results"]
        unique = {}
        for hit in hits:
            key = g.key(hit["path"])
            if key not in manifest:
                raise RuntimeError(f"result without URL mapping: {key}")
            url = manifest[key]
            unique.setdefault(g.normalize_url(url), url)
        return str(i), list(unique.values())[:5]

    runs = []
    for repeat in (1, 2):
        with ThreadPoolExecutor(max_workers=8) as pool:
            ranking = dict(pool.map(one, range(len(qs))))
        (OUT / f"rankings-pass{repeat}.json").write_text(json.dumps(ranking, indent=2), encoding="utf-8")
        runs.append(ranking)
        print(f"pass {repeat}: {len(ranking)} queries", flush=True)
    if runs[0] != runs[1]:
        raise RuntimeError("repeated rankings differ")
    if any(sha(Path(path)) != h for path, h in hashes.items()):
        raise RuntimeError("input changed during run")
    gd = json.loads((c.GD / "gd-hybrid.json").read_text(encoding="utf-8"))
    scores = [g.metrics(runs[0][str(i)], q["qrels"]) for i, q in enumerate(qs)]
    baseline = [g.metrics(gd[str(i)], q["qrels"])["ndcg_at_5"] for i, q in enumerate(qs)]
    d, low, high = g.bootstrap([m["ndcg_at_5"] for m in scores], baseline)
    report = {"summary": {k: sum(m[k] for m in scores) / len(scores) for k in scores[0]},
              "diff_vs_grounded": d, "ci95": [low, high], "repeat_rankings_identical": True,
              "candidate_limit": 20, "independent_holdout": False}
    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
