"""Benchmark dual relevance floors, pointer packing and binding subagent pack (#356).

Protocol & fixed decision rule: bench/experiments/MEMORY-RECALL-PACKING-2026-11-22.md.

  collect  --split dev|heldout --output X.jsonl [--limit N] [--workers W]
  analyse  --dev dev.jsonl [--heldout heldout.jsonl]
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import random
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path

import memory_cutoff_collect as old

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = Path(
    os.environ.get(
        "FOOTNOTE_LONGMEM_DATA",
        str(ROOT / "bench/.cache/longmemeval_s/longmemeval_s_cleaned.json"),
    )
)
FALLBACK_DATA = Path(r"D:\Projets\BorgKnowledge\bench\.cache\longmemeval_s\longmemeval_s_cleaned.json")
LOCAL_MODELS = Path(os.environ.get("LOCALAPPDATA", "")) / "footnote" / "models"
DEFAULT_MODELS = [LOCAL_MODELS / "bekko-a8m", LOCAL_MODELS / "gte-small"]
FALLBACK_MODELS = [
    Path(r"D:\Projets\BorgKnowledge\artifacts\models\bekko-a8m"),
    Path(r"D:\Projets\BorgKnowledge\artifacts\models\gte-small"),
]


def resolve_data(arg):
    if arg:
        return Path(arg)
    if DEFAULT_DATA.is_file():
        return DEFAULT_DATA
    if FALLBACK_DATA.is_file():
        return FALLBACK_DATA
    raise FileNotFoundError(f"LongMemEval dataset not found at {DEFAULT_DATA} or {FALLBACK_DATA}")


def resolve_models(arg):
    if arg:
        return [Path(p) for p in arg]
    if all((m / "model.onnx").is_file() for m in DEFAULT_MODELS):
        return DEFAULT_MODELS
    if all((m / "model.onnx").is_file() for m in FALLBACK_MODELS):
        return FALLBACK_MODELS
    raise FileNotFoundError("Default embedding models (bekko-a8m, gte-small) not found")


def resolve_bin(arg):
    p = Path(arg) if arg else (ROOT / "target/release/footnote.exe")
    if not p.is_file():
        raise FileNotFoundError(f"Release binary not found at {p}; run cargo build --release")
    return p


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call_bin(bin_path, db, args, state, stdin=None):
    env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state))
    p = subprocess.run(
        [str(bin_path), "--db", str(db), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if p.returncode:
        raise RuntimeError(f"{args[0]}: {p.stderr[-1000:]} {p.stdout[-1000:]}")
    result = json.loads(p.stdout)
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def collect_one(bin_path, models, q, other, directory):
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        temp = Path(temp)
        db = temp / "memory.db"
        batch = old.memories(q)
        if not batch:
            raise ValueError("no memories for " + q["question_id"])
        for i in range(0, len(batch), 50):
            call_bin(bin_path, db, ["remember"], temp, json.dumps(batch[i : i + 50]))
        model_args = [v for m in models for v in ("--model", str(m))]
        call_bin(bin_path, db, ["rebuild-embeddings", *model_args], temp)
        with closing(sqlite3.connect(db)) as c:
            sessions = dict(
                c.execute(
                    "SELECT c.id,m.session FROM memories m JOIN chunks c ON c.source_id=m.source_id"
                )
            )

        def row(query, label, gold):
            text = old.query_text(query)
            hits = call_bin(
                bin_path,
                db,
                ["memory-recall", "--project", "longmem", "--limit", "4", *model_args, "--", text],
                temp,
            )["memories"]
            return {
                "question_id": query["question_id"],
                "label": label,
                "hits": [
                    {
                        "id": h["id"],
                        "score": h.get("score"),
                        "dense_cosine": h.get("dense_cosine"),
                        "chars": len(h.get("text") or ""),
                        "relevant": sessions.get(h["id"]) in gold,
                    }
                    for h in hits
                ],
            }

        own = "abs" if q["question_id"].endswith("_abs") else "positive"
        answer = set() if own == "abs" else set(q["answer_session_ids"])
        return [row(q, own, answer), row(other, "cross", set())]


def collect(args):
    data_path = resolve_data(args.data)
    models = resolve_models(args.models)
    bin_path = resolve_bin(args.bin)
    data = sorted(json.loads(data_path.read_text(encoding="utf-8")), key=lambda q: q["question_id"])
    selected = [q for q in data if old.split(q["question_id"]) == args.split]
    selected = selected[: args.limit] if args.limit else selected

    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.output.exists():
        done = {
            json.loads(line)["source_id"]
            for line in args.output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def run(q):
        options = [
            x
            for x in data
            if x["question_id"] != q["question_id"]
            and old.split(x["question_id"]) == args.split
            and not set(x["answer_session_ids"]) & set(q["haystack_session_ids"])
            and not x["question_id"].endswith("_abs")
        ]
        other = options[int(hashlib.sha256(q["question_id"].encode()).hexdigest(), 16) % len(options)]
        return {"source_id": q["question_id"], "rows": collect_one(bin_path, models, q, other, args.output.parent)}

    remaining = [q for q in selected if q["question_id"] not in done]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for idx, res in enumerate(pool.map(run, remaining), len(done) + 1):
            with args.output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(res) + "\n")
            if idx % 20 == 0 or idx == len(selected):
                print(f"{idx}/{len(selected)} {res['source_id']}", flush=True)


def render_chars_flat(hits):
    # Matches src/hook.rs render(..., short=true): "- [id N · kind · YYYY-MM-DD] " (~32 chars) + min(chars, 200)
    if not hits:
        return 0
    header = 128
    return header + sum(32 + min(h["chars"], 200) + 1 for h in hits)


def render_chars_packed(hits, full_top_k=2, budget=600):
    if not hits:
        return 0, 0
    used = 0
    kept = 0
    for idx, h in enumerate(hits):
        cap = 200 if idx < full_top_k else 60
        line_len = 32 + min(h["chars"], cap)
        if kept > 0 and used + line_len > budget:
            break
        used += line_len
        kept += 1
    header = 128
    return header + used + kept, kept


def measures(records, cos_floor=None, inject_floor=None, packed=False):
    fam = []
    for rec in records:
        f = {
            "pos": 0,
            "pos_hit": 0,
            "abs": 0,
            "abs_inj": 0,
            "cross": 0,
            "cross_inj": 0,
            "prompts": 0,
            "chars": 0,
            "multi_prompts": 0,
            "multi_chars": 0,
        }
        for row in rec["rows"]:
            kept = [
                h
                for h in row["hits"]
                if (cos_floor is None or (h.get("dense_cosine") is not None and h["dense_cosine"] >= cos_floor))
                and (inject_floor is None or (h.get("score") is not None and h["score"] >= inject_floor))
            ]
            if packed:
                chars, n_kept = render_chars_packed(kept)
                kept = kept[:n_kept]
            else:
                chars = render_chars_flat(kept)
            f["prompts"] += 1
            f["chars"] += chars
            if len(row["hits"]) >= 3:
                f["multi_prompts"] += 1
                f["multi_chars"] += chars
            if row["label"] == "positive":
                f["pos"] += 1
                f["pos_hit"] += any(h["relevant"] for h in kept)
            else:
                f[row["label"]] += 1
                f[row["label"] + "_inj"] += bool(kept)
        fam.append(f)
    return fam


def rates(fam):
    s = {k: sum(f[k] for f in fam) for k in fam[0]}
    neg = s["abs"] + s["cross"]
    return {
        "any4": s["pos_hit"] / s["pos"],
        "neg_injection": (s["abs_inj"] + s["cross_inj"]) / neg,
        "abs_injection": s["abs_inj"] / s["abs"] if s["abs"] else None,
        "cross_injection": s["cross_inj"] / s["cross"],
        "mean_chars": s["chars"] / s["prompts"],
        "mean_tokens_est": (s["chars"] / s["prompts"]) / 4.0,
        "multi_mean_chars": s["multi_chars"] / s["multi_prompts"] if s["multi_prompts"] else 0.0,
        "positives": s["pos"],
        "no_answer": neg,
    }


def bootstrap(gated, ungated, key, seed=20261122, n=10_000):
    rng, vals = random.Random(seed), []
    for _ in range(n):
        idx = [rng.randrange(len(gated)) for _ in gated]
        g, u = rates([gated[i] for i in idx]), rates([ungated[i] for i in idx])
        vals.append(g[key] - u[key])
    vals.sort()
    return [round(vals[int(0.025 * n)], 4), round(vals[int(0.975 * n) - 1], 4)]


def quantiles(vals, steps=25):
    vals = sorted(vals)
    if not vals:
        return [None]
    return [None] + [vals[int(i * (len(vals) - 1) / steps)] for i in range(steps + 1)]


def bench_binding_pack(bin_path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        db = tmp / "memory.db"
        items = [
            {"text": "Always write a decision rule before seeing heldout benchmark results.", "kind": "preference", "scope": "global", "observed_at": "2026-11-14"},
            {"text": "Never mention analyzed third-party inspiration tool names in public GitHub issues.", "kind": "preference", "scope": "global", "observed_at": "2026-11-20"},
            {"text": "Prefer concise GitHub-style markdown responses with clickable file links.", "kind": "preference", "scope": "global", "observed_at": "2026-11-18"},
            {"text": "In footnote, run cargo fmt and clippy -D warnings before opening a PR.", "kind": "preference", "scope": "footnote", "observed_at": "2026-11-19"},
            {"text": "Footnote uses SQLite plus Tantivy for local lexical search and int8 vectors for dense search across bekko-a8m and gte-small.", "kind": "fact", "scope": "footnote", "observed_at": "2026-11-15"},
            {"text": "Fixed Windows background spawning in hook.rs by calling CreateProcessW with bInheritHandles=FALSE so agent pipes are not inherited.", "kind": "fix", "scope": "footnote", "observed_at": "2026-11-17"},
            {"text": "Session 2026-11-21: completed site QLoop pass 2, merged #451 and #452, verified clean-machine install CI in #482, remaining items tracked in Footnote-Marketing.", "kind": "session", "scope": "footnote", "observed_at": "2026-11-21"},
        ]
        # Pad with additional facts/sessions to exceed 3000 chars for full pack realism
        for i in range(12):
            items.append({
                "text": f"Historical project note {i}: detailed benchmark setup and intermediate findings for sprint {i}, including hardware specs, feature flags, and cache layout notes.",
                "kind": "fact" if i % 2 == 0 else "session",
                "scope": "footnote",
                "observed_at": f"2026-11-{10 + (i % 10):02d}",
            })
        call_bin(bin_path, db, ["remember"], tmp, json.dumps(items))
        full = call_bin(bin_path, db, ["memory-pack", "--project", "footnote", "--max-chars", "3000"], tmp)
        binding = call_bin(bin_path, db, ["memory-pack", "--project", "footnote", "--max-chars", "800", "--binding"], tmp)
        return {
            "full_count": len(full["memories"]),
            "full_chars": full["chars"],
            "full_tokens_est": round(full["chars"] / 4.0, 1),
            "binding_count": len(binding["memories"]),
            "binding_chars": binding["chars"],
            "binding_tokens_est": round(binding["chars"] / 4.0, 1),
            "binding_all_preferences": all(m["kind"] == "preference" for m in binding["memories"]),
            "binding_reduction_pct": round(100.0 * (1.0 - binding["chars"] / max(full["chars"], 1)), 1),
        }


def analyse(args):
    dev_recs = [json.loads(l) for l in args.dev.read_text(encoding="utf-8").splitlines() if l.strip()]
    dev_base_fam = measures(dev_recs)
    dev_base = rates(dev_base_fam)

    cos_vals = [h["dense_cosine"] for r in dev_recs for row in r["rows"] for h in row["hits"] if h.get("dense_cosine") is not None]
    fus_vals = [h["score"] for r in dev_recs for row in r["rows"] for h in row["hits"] if h.get("score") is not None]
    best = None
    for cf in quantiles(cos_vals, 25):
        for sf in quantiles(fus_vals, 25):
            r = rates(measures(dev_recs, cf, sf))
            if dev_base["any4"] - r["any4"] <= 0.05 + 1e-12:
                if best is None or r["neg_injection"] < best[2]["neg_injection"]:
                    best = (cf, sf, r)
    cf, sf, dev_gated = best
    dev_packed = rates(measures(dev_recs, None, None, packed=True))
    out = {
        "dev": {
            "ungated": dev_base,
            "selected_floors": {"cos_floor": cf, "inject_floor": sf},
            "dual_floor": dev_gated,
            "any4_loss_points": round(100 * (dev_base["any4"] - dev_gated["any4"]), 2),
            "pointer_packing": dev_packed,
            "pointer_packing_multi_reduction_pct": round(
                100 * (1 - dev_packed["multi_mean_chars"] / max(dev_base["multi_mean_chars"], 1)), 2
            ),
        }
    }
    if args.heldout:
        ho_recs = [json.loads(l) for l in args.heldout.read_text(encoding="utf-8").splitlines() if l.strip()]
        ho_base_fam = measures(ho_recs)
        ho_base = rates(ho_base_fam)
        ho_gated_fam = measures(ho_recs, cf, sf)
        ho_gated = rates(ho_gated_fam)
        ho_packed_fam = measures(ho_recs, None, None, packed=True)
        ho_packed = rates(ho_packed_fam)
        loss_pp = round(100 * (ho_base["any4"] - ho_gated["any4"]), 2)
        out["heldout"] = {
            "ungated": ho_base,
            "dual_floor": ho_gated,
            "any4_loss_points": loss_pp,
            "any4_diff_ci95": bootstrap(ho_gated_fam, ho_base_fam, "any4"),
            "neg_injection_diff_ci95": bootstrap(ho_gated_fam, ho_base_fam, "neg_injection"),
            "dual_floor_passes": ho_gated["neg_injection"] <= 0.50 and loss_pp <= 5.0,
            "pointer_packing": ho_packed,
            "pointer_packing_any4_loss_points": round(100 * (ho_base["any4"] - ho_packed["any4"]), 2),
            "pointer_packing_multi_reduction_pct": round(
                100 * (1 - ho_packed["multi_mean_chars"] / max(ho_base["multi_mean_chars"], 1)), 2
            ),
        }
    if args.bin:
        out["binding_pack"] = bench_binding_pack(resolve_bin(args.bin))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--split", choices=["dev", "heldout"], required=True)
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--data", type=Path)
    c.add_argument("--models", nargs="+")
    c.add_argument("--bin", type=Path)
    c.add_argument("--limit", type=int, default=0)
    c.add_argument("--workers", type=int, default=4)
    a = sub.add_parser("analyse")
    a.add_argument("--dev", type=Path, required=True)
    a.add_argument("--heldout", type=Path)
    a.add_argument("--bin", type=Path)
    args = p.parse_args()
    {"collect": collect, "analyse": analyse}[args.cmd](args)
