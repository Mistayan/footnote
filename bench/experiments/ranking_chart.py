"""Write the head-to-head ranking chart from the latest complete test receipts (same selection as headtohead_table.py).

    python bench/experiments/ranking_chart.py --since 20261113T070000Z

Output: bench/experiments/RANKING.html, built from ranking_template.html. Missing dataset/engine cells show as "no result".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import headtohead_table as table  # noqa: E402
ENGINES = table.ENGINES + ["icm"]
MULTILINGUAL_ONLY = ("shipped-ensemble-mcp", "mem0-multilingual", "cognee-multilingual", "icm")  # mix-fr-en schedule


def row(receipt: dict) -> dict:
    det = receipt["determinism"]
    return {"ds": receipt["dataset"]["id"], "eng": receipt["engine"]["id"], "q": round(receipt["metrics"]["ndcg@10"], 4),
            "p50": round(receipt["latency_ms"]["p50"], 1), "n": receipt["metrics"]["queries_scored"],
            "det": bool(det["checked"] and det["identical_rankings"])}


def render(template: str, rows: list[dict]) -> str:
    if template.count("__DATA__") != 1:
        raise ValueError("template must contain exactly one __DATA__ placeholder")
    return template.replace("__DATA__", json.dumps(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="")
    ap.add_argument("--output", type=Path, default=HERE / "RANKING.html")
    args = ap.parse_args()
    rows = []
    for ds in table.DATASETS:
        for eng in ENGINES:
            if ds == "mix-fr-en" and eng not in MULTILINGUAL_ONLY:
                continue
            hit = table.latest(ds, eng, args.since)
            if hit:
                rows.append(row(hit[1]))
    args.output.write_text(render((HERE / "ranking_template.html").read_text(encoding="utf-8"), rows), encoding="utf-8")
    print(f"wrote {args.output} with {len(rows)} receipts")


if __name__ == "__main__":
    main()
