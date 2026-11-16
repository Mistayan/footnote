"""Crawl the same five documentation sites with the isolated Spider probe, then measure coverage.

Run after building bench/spider_probe: python -I bench/experiments/docs_spider.py <probe-exe> <new-variant>
Network fetches are independent of the minimal crawl; see DOCS-FOLLOWUPS-2026-11-15.md.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

PROBE, VARIANT = Path(sys.argv[1]).resolve(), sys.argv[2]
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent))
import docs_crawl as crawl  # noqa: E402

if not VARIANT.startswith("spider-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in VARIANT):
    raise ValueError("variant must be a simple spider- name")
if not PROBE.is_file():
    raise FileNotFoundError(PROBE)

scopes = {
    "react": ("https://react.dev", r"^https://react\.dev(?:/|$)"),
    "python": ("https://docs.python.org/3/", r"^https://docs\.python\.org/3(?:/|$)"),
    "fastapi": ("https://fastapi.tiangolo.com/", r"^https://fastapi\.tiangolo\.com(?:/|$)"),
    # The configured vitejs.dev start redirects to vite.dev; use the effective host and same path.
    "vite": ("https://vite.dev/guide/", r"^https://vite\.dev/guide(?:/|$)"),
    "tailwindcss": ("https://tailwindcss.com/docs", r"^https://tailwindcss\.com/docs(?:/|$)"),
}
work = crawl.WORK / VARIANT
work.mkdir(parents=True, exist_ok=False)
with PROBE.open("rb") as f:
    binary_hash = hashlib.file_digest(f, "sha256").hexdigest()
(work / "inputs.json").write_text(json.dumps({"binary": str(PROBE), "sha256": binary_hash, "scopes": scopes,
                                              "minimal_coverage_is_independent_fetch": True}, indent=2), encoding="utf-8")
for lib, (_, budget, exclude) in crawl.g.RECIPE.items():
    start, allow = scopes[lib]
    output = work / lib
    pattern = exclude[1:-1] if exclude else "-"
    began = time.monotonic()
    result = subprocess.run([str(PROBE), start, str(output), str(budget), allow, pattern],
                            capture_output=True, text=True, encoding="utf-8", timeout=7200)
    crawl.log(VARIANT, f"spider {lib}: exit {result.returncode}, {time.monotonic() - began:.1f} s, {result.stdout.strip()[-500:]} {result.stderr.strip()[-500:]}")
    if result.returncode or not (output / "urls.json").is_file():
        raise RuntimeError(f"Spider crawl failed for {lib}; incomplete files retained")
    report = json.loads(result.stdout)
    if not report["pages"] or report["pages"] > budget:
        raise RuntimeError(f"Spider invalid page count for {lib}: {report}")
crawl.coverage(VARIANT)
