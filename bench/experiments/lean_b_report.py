"""Table and horizontal stacked-bar chart for lean_b runs.jsonl (#239). Usage: lean_b_report.py runs.jsonl out.png"""
import collections, json, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
A = collections.defaultdict(list)
for r in rows: A[r["arm"]].append(r)
order = [a for a in ("bare", "ponytail", "lean-b-code", "lean-b-full", "base-dev", "footnote") if a in A]
m = lambda a, k: sum(r[k] for r in A[a]) / len(A[a])
def tok(a): return m(a, "uncached_in") + m(a, "cache_write"), m(a, "cache_read"), m(a, "output")
def rel(v, b, word):
    p = round(100 * (v - b) / b) if b else 0
    return "baseline" if v == b else f"{abs(p)}% {word[0] if p < 0 else word[1]}"
base = order[0]; print("| arm | runs | uncached in (incl. cache write) | cached in | output | time | accepted |\n|---|---|---|---|---|---|---|")
for a in order:
    u, c, o = tok(a); bu, bc, bo = tok(base); t = m(a, "seconds"); ok = sum(r["accepted"] for r in A[a])
    print(f"| {a} | {len(A[a])} | {u:,.0f} ({rel(u,bu,('less','more'))}) | {c:,.0f} ({rel(c,bc,('less','more'))}) | {o:,.0f} ({rel(o,bo,('less','more'))}) "
          f"| {t:.0f} s ({rel(t,m(base,'seconds'),('faster','slower'))}) | {ok}/{len(A[a])} ({rel(ok/len(A[a]),sum(r['accepted'] for r in A[base])/len(A[base]),('lower','higher'))}) |")
print("\n| arm | cost per accepted delivery | fixed overhead | read tokens | turns before first edit | turns |\n|---|---|---|---|---|---|")
cpa = lambda a: sum(r["usd"] or 0 for r in A[a]) / max(1, sum(r["accepted"] for r in A[a]))  # failed runs count against their arm
for a in order:
    print(f"| {a} | ${cpa(a):.3f} ({rel(cpa(a),cpa(base),('less','more'))}) " + " ".join(
        f"| {m(a,k):,.0f} ({rel(m(a,k),m(base,k),('less','more'))})" for k in ("fixed_overhead", "read_tokens", "turns_before_edit", "turns")) + " |")
fig, ax = plt.subplots(figsize=(11, 3.6)); y = range(len(order))[::-1]
for yy, a in zip(y, order):
    u, c, o = tok(a); l = 0; pct = lambda v, b, w: "" if a == base else f"\n({rel(v, b, w)})"
    for v, bv, col, n in ((u, tok(base)[0], "#c0392b", "uncached in"), (c, tok(base)[1], "#7fb3d5", "cached in"), (o, tok(base)[2], "#27ae60", "output")):
        ax.barh(yy, v, left=l, color=col, label=n if yy == max(y) else None)
        if n != "output": ax.text(l + v / 2, yy, f"{v:,.0f}" + pct(v, bv, ("less", "more")), ha="center", va="center", fontsize=8)
        l += v
    ok = sum(r["accepted"] for r in A[a]); t = m(a, "seconds"); sp = lambda s: s.replace("\n", " ")
    ax.text(l * 1.01, yy, f"output {o:,.0f}{sp(pct(o, tok(base)[2], ('less', 'more')))}\n{t:.0f} s{sp(pct(t, m(base, 'seconds'), ('faster', 'slower')))}, "
            f"{ok}/{len(A[a])} accepted", va="center", fontsize=9)
ax.set_yticks(list(y)); ax.set_yticklabels(order); ax.set_xlim(0, ax.get_xlim()[1] * 1.3); ax.set_xlabel("mean tokens per run"); ax.legend(loc="lower right")
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=130)
