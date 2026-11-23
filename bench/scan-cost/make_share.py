#!/usr/bin/env python3
"""Generate a synthetic file share for the change scan cost bench (issue #549).

Usage: python make_share.py OUT_DIR --files 50000 --gib 20 --seed 549

Deterministic for a given seed. 40% .pdf, 15% .png, 15% .jpg (random bytes), 20% .md, 10% .txt (ASCII words, at
most 1,000,000 bytes, the text indexer's limit); log-normal sizes clipped to the product's 16 MiB file limit; 1,000
folders (50 x 20); modification times spread over the past year. Each file starts with a unique header and continues
with a slice of a shared random pool, so contents differ without generating 20 GiB of fresh random numbers.
Refuses to write into a non-empty folder. Prints a JSON summary.
"""
import argparse
import json
import math
import os
import pathlib
import random
import sys
import time

MAX_FILE = 16 * 1024 * 1024  # footnote_core::MAX_FILE
MAX_TEXT = 1_000_000  # crates/library: longer text files are not indexed
KINDS = [("pdf", 0.40), ("png", 0.15), ("jpg", 0.15), ("md", 0.20), ("txt", 0.10)]
WORDS = ("contract invoice report policy share budget review audit project meeting minutes summary appendix figure "
         "table section clause party payment delivery schedule annex revision approval signature quarter").split()


def sizes(rng, kinds, total):
    """Log-normal sizes scaled so they sum to about `total`, each clipped to its kind's limit."""
    raw = [rng.lognormvariate(0, 1.3) for _ in kinds]
    caps = [MAX_TEXT if k in ("md", "txt") else MAX_FILE - 1 for k in kinds]
    out = raw
    for _ in range(20):  # rescale the unclipped files until the clipped total converges
        scale = total / max(1.0, sum(raw))
        out = [max(1024, min(cap, int(r * scale))) for r, cap in zip(raw, caps)]
        got = sum(out)
        if abs(got - total) < total * 0.002:
            break
        raw = [r * total / got if o < cap else r for r, o, cap in zip(raw, out, caps)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--files", type=int, default=50_000)
    ap.add_argument("--gib", type=float, default=20.0)
    ap.add_argument("--seed", type=int, default=549)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    kinds = rng.choices([k for k, _ in KINDS], weights=[w for _, w in KINDS], k=a.files)
    lens = sizes(rng, kinds, int(a.gib * 1024**3))
    pool = rng.randbytes(MAX_FILE * 2)
    text = " ".join(rng.choice(WORDS) for _ in range(400_000)).encode()
    text = (text * math.ceil(2 * MAX_TEXT / len(text)))[: 2 * MAX_TEXT]
    now = time.time()
    t0 = time.perf_counter()
    for i, (kind, n) in enumerate(zip(kinds, lens)):
        folder = out / f"d{i % 50:02d}" / f"s{(i // 50) % 20:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"f{i:06d}.{kind}"
        if kind in ("md", "txt"):
            head = f"# document {i} seed {a.seed}\n".encode()
            src = text
        else:
            head = f"FN549 {i:08d} {a.seed}\n".encode()
            src = pool
        off = rng.randrange(0, len(src) - n)
        path.write_bytes(head + src[off : off + n - len(head)])
        mtime = now - rng.uniform(86_400, 365 * 86_400)
        os.utime(path, ns=(int(mtime * 1e9), int(mtime * 1e9)))
    counts = {k: kinds.count(k) for k, _ in KINDS}
    print(json.dumps({"out": str(out), "files": a.files, "bytes": sum(lens), "gib": round(sum(lens) / 1024**3, 2),
                      "seed": a.seed, "by_kind": counts, "max_file": max(lens),
                      "seconds": round(time.perf_counter() - t0, 1)}))


if __name__ == "__main__":
    main()
