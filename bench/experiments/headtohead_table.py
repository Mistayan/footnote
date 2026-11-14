"""Report the latest complete test receipt per scheduled dataset/engine pair.

    python bench/experiments/headtohead_table.py --since 20261113T070000Z
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

RECEIPTS = Path(__file__).resolve().parents[1] / "receipts"
DATASETS = ["syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"]
ENGINES = ["shipped-ensemble-mcp", "mem0", "mem0-multilingual", "cognee", "cognee-lexical", "cognee-multilingual"]
MATCHED = ["matched-sqlite-tantivy", "matched-lance-rrf", "matched-lance-cc", "matched-lance-tantivy"]
MIB = 1024 * 1024


def latest(ds: str, eng: str, since: str = "") -> tuple[Path, dict] | None:
    for path in sorted(RECEIPTS.glob(f"*-{ds}-{eng}.json"), reverse=True):
        if path.name[:16] < since:
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (not receipt.get("partial") and receipt["dataset"]["split"] == "test"
                and receipt["dataset"]["id"] == ds and receipt["engine"]["id"] == eng):
            return path, receipt
    return None


def mib(value: int | None) -> str:
    return "n/a" if value is None else f"{value / MIB:.2f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="", help="earliest receipt filename timestamp, UTC YYYYMMDDTHHMMSSZ")
    ap.add_argument("--matched", action="store_true", help="report the four matched backend controls instead of competitors")
    args = ap.parse_args()
    if args.since:
        dt.datetime.strptime(args.since, "%Y%m%dT%H%M%SZ")

    rows, pending, sources, identities = [], [], [], {}
    for ds in DATASETS:
        for eng in MATCHED if args.matched else ENGINES:
            # The scheduled mixed-language run only includes multilingual variants.
            if not args.matched and ds == "mix-fr-en" and eng not in ("shipped-ensemble-mcp", "mem0-multilingual", "cognee-multilingual"):
                continue
            hit = latest(ds, eng, args.since)
            if hit is None:
                pending.append(f"{ds}/{eng}")
                continue
            path, r = hit
            identity = (r["protocol"], r["dataset"], r["code"]["harness_sha256"], r["code"]["metrics_sha256"],
                        r["engine"].get("versions", {}).get("input", {}).get("files_sha256"))
            if ds in identities and identity != identities[ds]:
                raise ValueError(f"incomparable inputs or harness for {ds}: {path.name}")
            identities[ds] = identity
            m, lat, b = r["metrics"], r["latency_ms"], r["build"]
            index = b.get("tantivy_bytes", b.get("lancedb_bytes", b.get("qdrant_bytes")))
            model = b.get("model_bytes", b.get("model_cache_bytes"))
            det = r["determinism"]
            checked = str(det["queries_checked"]) if det["checked"] and det["identical_rankings"] else "unchecked/failed"
            rows.append(f"| {ds} | {eng} | {m['ndcg@10']:.3f} | {m['recall@10']:.3f} | {lat['p50']:.2f} | {lat['p95']:.2f} | "
                        f"{b['build_ms'] / 1000:.1f} | {mib(b.get('store_bytes'))} | {mib(index)} | {mib(model)} | {checked} |")
            sources.append(f"- [{path.name}](../receipts/{path.name}), {m['queries_scored']} scored queries; latency: {lat['scope']}.")

    print("# Matched backend results\n" if args.matched else "# Head-to-head retrieval results\n")
    print(f"Complete receipts: {len(rows)}/{len(rows) + len(pending)}. Missing: {len(pending)}."
          + (f" Receipt window starts at {args.since}." if args.since else " Latest receipts, no time window.") + "\n")
    if args.matched:
        print("Identical exported chunks and a8m vectors; exact retrieval with precomputed query embeddings. "
              "Encoding is excluded from every latency. These are component controls, not the production two-model pipeline.\n")
    else:
        print("Same documents, queries and scoring; each product keeps its own models, chunking and ranking. "
              "This is a configured retrieval comparison, not an isolated database test. "
              "mem0 LLM extraction and Cognee graph retrieval are excluded.\n")
    index_label = "Tantivy within store MiB" if args.matched else "Index within store MiB"
    print(f"| Dataset | Engine | nDCG@10 | R@10 | p50 ms | p95 ms | Build s | Store MiB | {index_label} | Models/cache MiB | Determinism queries |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    print("\n".join(rows))
    print("\nStore includes the backend index; do not add it twice. Model/cache files are separate, "
          "may contain shared downloads, and exclude the Python environment and executable. Unknown sizes are n/a. "
          + ("Native FTS is included in LanceDB store bytes. Common frozen input artifacts are excluded. " if args.matched else
             "Latency includes Footnote MCP transport; competitors use in-process calls. ")
          + "Builds are measured as recorded, without a cold filesystem-cache guarantee.\n")
    if pending:
        print("Missing receipts, still pending or failed:\n")
        print("\n".join(f"- {name}" for name in pending))
        print()
    print("Receipt provenance:\n")
    print("\n".join(sources))


if __name__ == "__main__":
    main()
