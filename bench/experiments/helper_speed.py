"""Shipped embedding helper (tools/embed.py) against batching variants, same model files and texts: speed and vector agreement.

    .venv/Scripts/python.exe -I bench/experiments/helper_speed.py --models C:/.../bekko-a8m C:/.../gte-small --docs 2000

Variant "shipped" is tools/embed.py itself. Others re-run the same tokenizer and session code with sorted texts, another
batch size and thread count. Prints docs/s and the minimum cosine against the shipped vectors (BUILD-SPEED.md test 1b).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "bench")]
import embed  # noqa: E402
import fetch  # noqa: E402


def bulk(e: embed.Embedder, texts: list[str], batch: int, threads: int, keep_order: bool = False) -> np.ndarray:
    """Same tokenizer, pooling and normalisation as embed.Embedder.encode; sorted by length unless `keep_order`, own batch
    and thread count. Int8 models quantize activations per batch, so their vectors depend on which texts share a batch."""
    so = ort.SessionOptions()
    so.intra_op_num_threads, so.inter_op_num_threads = threads, 1
    sess = ort.InferenceSession(e.session._model_path, sess_options=so, providers=["CPUExecutionProvider"])
    names = [i.name for i in sess.get_inputs()]
    prefix = e.m["passage_prefix"]
    order = np.arange(len(texts)) if keep_order else np.argsort([len(t) for t in texts], kind="stable")
    out = np.zeros((len(texts), e.m["dimension"]), dtype=np.float64)
    for s in range(0, len(texts), batch):
        idx = order[s:s + batch]
        tokens = e.tokenizer.encode_batch([prefix + texts[i] for i in idx])
        ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
        mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
        inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        h = sess.run(None, {n: inputs[n] for n in names})[0]
        v = (h * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
        out[idx] = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True, help="provisioned model folders (with manifest.json)")
    ap.add_argument("--dataset", default="scifact")
    ap.add_argument("--docs", type=int, default=2000)
    ap.add_argument("--variants", default="8:2,32:2,32:8,32:12,32:24,64:12",
                    help="batch:threads pairs; a third field 'keep' keeps corpus order (batch:threads:keep)")
    args = ap.parse_args()
    corpus, _, _ = fetch.load(args.dataset, "test")
    texts = [f"{corpus[d][0]}\n{corpus[d][1]}".strip()[:2000] for d in sorted(corpus)[:args.docs]]
    for m in args.models:
        e = embed.Embedder(m)
        e.encode({"texts": texts[:8], "kind": "passage"})  # warm-up
        t = time.perf_counter()
        ref = np.asarray(e.encode({"texts": texts, "kind": "passage"})["vectors"])
        base = time.perf_counter() - t
        print(json.dumps({"model": Path(m).name, "variant": "shipped (batch 8, 2 threads, corpus order)",
                          "docs_per_s": round(len(texts) / base, 1)}), flush=True)
        for v in args.variants.split(","):
            parts = v.split(":")
            batch, threads, keep = int(parts[0]), int(parts[1]), parts[2:] == ["keep"]
            bulk(e, texts[:64], batch, threads, keep)  # warm-up
            t = time.perf_counter()
            vec = bulk(e, texts, batch, threads, keep)
            s = time.perf_counter() - t
            print(json.dumps({"model": Path(m).name, "variant": f"{'corpus order' if keep else 'sorted'}, batch {batch}, {threads} threads",
                              "docs_per_s": round(len(texts) / s, 1), "speedup": round(base / s, 2),
                              "cosine_min": round(float((vec * ref).sum(1).min()), 8)}), flush=True)


if __name__ == "__main__":
    main()
