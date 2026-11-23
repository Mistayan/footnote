"""Same vectors from two builds (#517): every model in a folder, the workload queries as queries and as passages.

    python -I bench/experiments/daemon_ram_vectors.py <base footnote.exe> <new footnote.exe> <models dir>

Prints, per model and kind, whether the two builds return bit-identical vectors, and the largest absolute difference.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from daemon_ram import QUERIES  # noqa: E402


def embed(exe: str, model: Path, kind: str) -> list[list[float]]:
    out = subprocess.run([exe, "embed", "--model", str(model), "--kind", kind], input=json.dumps(QUERIES),
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return json.loads(out)["vectors"]


def main() -> None:
    base, new, models_dir = sys.argv[1:4]
    report = {}
    for m in sorted(Path(models_dir).iterdir()):
        if not (m / "manifest.json").is_file():
            continue
        for kind in ("query", "passage"):
            a, b = embed(base, m, kind), embed(new, m, kind)
            diff = max(abs(x - y) for va, vb in zip(a, b) for x, y in zip(va, vb))
            report[f"{m.name}/{kind}"] = {"texts": len(a), "identical": a == b, "max_abs_diff": diff}
    print(json.dumps(report, indent=1))
    if not all(r["identical"] for r in report.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
