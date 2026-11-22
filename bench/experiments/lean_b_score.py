"""Cost per accepted task per arm (#239). Usage: lean_b_score.py runs.jsonl [--price in,write,read,out] (USD per Mtok)."""
import collections, json, sys

def score(rows, price):
    a = collections.defaultdict(lambda: dict(n=0, ok=0, cost=0.0, out=0, turns=0, read_tokens=0, turns_before_edit=0,
                                             fixed_overhead=0, cache_read_cost=0.0, recall_hits=0, recall_misses=0,
                                             recall_skips=0, recall_anchor_hits=0, prose_checked=0, prose_violations=0))
    for r in rows:
        s = a[r["arm"]]
        for k in ("read_tokens", "turns_before_edit", "fixed_overhead", "recall_hits", "recall_misses",
                  "recall_skips", "recall_anchor_hits", "prose_checked", "prose_violations"):  # #239, #240, #241, #242; older rows have none
            s[k] += r.get(k, 0)
        s["cache_read_cost"] += r["cache_read"] * price[2] / 1e6
        s["n"] += 1
        s["ok"] += bool(r["accepted"])
        s["out"] += r["output"]
        s["turns"] += r["turns"]
        s["cost"] += sum(r[k] * p for k, p in zip(("uncached_in", "cache_write", "cache_read", "output"), price)) / 1e6
    # failed runs stay in the numerator: their spend counts against the arm
    out = {k: dict(v, per_accepted=v["cost"] / v["ok"] if v["ok"] else None,
                   cache_read_share=round(v["cache_read_cost"] / v["cost"], 3) if v["cost"] else None) for k, v in a.items()}
    base = (out.get("bare") or {}).get("per_accepted")
    for v in out.values():
        v["vs_bare_pct"] = None if not base or v["per_accepted"] is None else round(100 * (v["per_accepted"] / base - 1), 1)
    return out

if __name__ == "__main__":
    price = (5, 6.25, 0.5, 25)  # placeholder list prices; pass --price to override
    if "--price" in sys.argv:
        price = tuple(float(x) for x in sys.argv[sys.argv.index("--price") + 1].split(","))
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    for arm, v in score(rows, price).items():
        print(arm, v)
