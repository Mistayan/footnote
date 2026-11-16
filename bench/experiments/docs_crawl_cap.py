"""Diagnostic capped search on an already-built minimal crawl; keeps original C results intact."""
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
    base = c.WORK / "minimal"
    qs = c.queries()
    manifest = {}
    for lib in g.RECIPE:
        manifest.update(c.urls_of("minimal", lib))
    paths = [Path(g.FOOTNOTE), g.REPO / "bench/work/gd/dataset.yaml", c.GD / "gd-hybrid.json",
             base / "endtoend.json", Path(__file__), *[Path(m) / "manifest.json" for m in g.MODELS],
             *[base / "footnote" / f"{lib}.db" for lib in g.RECIPE],
             *[base / lib / "urls.json" for lib in g.RECIPE]]
    hashes = {str(p): sha(p) for p in paths}
    (OUT / "inputs.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    def one(i):
        q = qs[i]
        args = ["search", q["query"], "--limit", "5", "--per-source", "1", "--mode", "hybrid",
                *[a for m in g.MODELS for a in ("--model", m)]]
        hits = g.fn(base / "footnote" / f"{q['library']}.db", *args)["results"]
        urls = []
        for hit in hits:
            key = g.key(hit["path"])
            if key not in manifest:
                raise RuntimeError(f"result without URL mapping: {key}")
            urls.append(manifest[key])
        return str(i), urls

    runs = []
    for n in (1, 2):
        with ThreadPoolExecutor(max_workers=8) as ex:
            result = dict(ex.map(one, range(len(qs))))
        (OUT / f"rankings-pass{n}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        runs.append(result)
        print(f"pass {n}: {len(result)} queries", flush=True)
    if runs[0] != runs[1]:
        raise RuntimeError("ranking differs between passes")
    if any(sha(Path(path)) != h for path, h in hashes.items()):
        raise RuntimeError("input changed")
    gd = json.loads((c.GD / "gd-hybrid.json").read_text(encoding="utf-8"))
    nd = lambda r: [g.metrics(r[str(i)], q["qrels"])["ndcg_at_5"] for i, q in enumerate(qs)]
    values = [g.metrics(runs[0][str(i)], q["qrels"]) for i, q in enumerate(qs)]
    diff, low, high = g.bootstrap(nd(runs[0]), nd(gd))
    summary = {k: sum(m[k] for m in values) / len(values) for k in values[0]}
    duplicates = sum(len({g.normalize_url(u) for u in r}) < len(r) for r in runs[0].values())
    result = {"summary": summary, "diff_vs_grounded": diff, "ci95": [low, high],
              "queries_with_duplicate_normalized_urls": duplicates, "repeat_rankings_identical": True,
              "independent_holdout": False}
    (OUT / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
