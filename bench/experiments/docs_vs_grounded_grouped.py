"""Exploratory follow-up of DOCS-VS-GROUNDED.md (written after the results): Footnote hits grouped by page.

    bench/.labenv/Scripts/python.exe -I bench/experiments/docs_vs_grounded_grouped.py
"""

import json, sys, time, yaml
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import docs_vs_grounded as g
qs = [e["vars"] for e in yaml.safe_load(g.DATASET.read_text(encoding="utf-8"))["entries"]]
manifest = json.loads((g.RUN / "manifest.json").read_text())
db = lambda lib: g.RUN / "footnote" / f"{lib}.db"
out = {}
for mode in ("hybrid", "keyword"):
    def one(i):
        q = qs[i]
        args = ["search", q["query"], "--limit", "20"]
        if mode == "hybrid":
            args += ["--mode", "hybrid", *[a for m in g.MODELS for a in ("--model", m)]]
        urls = [manifest.get(g.key(h["path"]), h["path"]) for h in g.fn(db(q["library"]), *args)["results"]]
        return str(i), list(dict.fromkeys(urls))[:5]
    t = time.time()
    with ThreadPoolExecutor(8) as ex:  # quality only: concurrency does not change the ranking
        out[mode] = dict(ex.map(one, range(len(qs))))
    print(f"{mode}: {len(qs)} queries, 8 at a time, {time.time() - t:.0f} s", flush=True)
(g.RUN / "fn-grouped.json").write_text(json.dumps(out), encoding="utf-8")
gh = json.loads((g.RUN / "gd-hybrid.json").read_text(encoding="utf-8"))
fh = json.loads((g.RUN / "fn-hybrid.json").read_text(encoding="utf-8"))
nd = lambda r: [g.metrics(r[str(i)], q["qrels"])["ndcg_at_5"] for i, q in enumerate(qs)]
base = nd(gh)
for name, r in (("footnote_hybrid (as run)", fh), ("footnote_hybrid grouped", out["hybrid"]), ("footnote_keyword grouped", out["keyword"])):
    d, lo, hi = g.bootstrap(nd(r), base)
    ms = [g.metrics(r[str(i)], q["qrels"]) for i, q in enumerate(qs)]
    print(f"{name:26} " + " ".join(f"{k} {sum(m[k] for m in ms)/len(ms):.3f}" for k in ms[0]) + f" | vs grounded_hybrid {d:+.4f} [{lo:+.4f}, {hi:+.4f}]")
