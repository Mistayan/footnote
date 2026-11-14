"""Batch encoding on ONNX Runtime CPU against DirectML (GPU), same lab Encoder, same model files, same texts.

    bench/.gpuenv/Scripts/python.exe -I bench/experiments/gpu_encode.py --dataset scifact --model bekko-a8m --smoke
    bench/.gpuenv/Scripts/python.exe -I bench/experiments/gpu_encode.py --dataset scifact --model bekko-a8m --model embeddinggemma-300m

Reports texts per second for each provider, per-text cosine between CPU and GPU vectors, and dense-only nDCG@10 with each provider's
document and query vectors. GPU is a candidate for index builds and model sweeps only; latency stays measured on CPU.
Run on a quiet machine: the CPU timing is invalid if another heavy job shares the cores.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import fetch  # noqa: E402
import metrics  # noqa: E402
from lab import Encoder  # noqa: E402

FIXED_PAD = 0  # set by --fixed-pad; GPU side only
PROVIDER = "DmlExecutionProvider"  # set by --provider


def on_gpu(obj):
    """Swap an already built lab Encoder or CrossEncoder onto the accelerated provider (DirectML or OpenVINO), same model file."""
    import onnxruntime as ort
    so = ort.SessionOptions()
    if PROVIDER == "DmlExecutionProvider":
        so.enable_mem_pattern = False  # DirectML requirements
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options = [{}]
    else:
        options = [{"device_type": "CPU"}]  # OpenVINO on the same CPU: compares runtimes, not devices
    obj.sess = ort.InferenceSession(obj.sess._model_path, so, providers=[PROVIDER], provider_options=options)
    if obj.sess.get_providers()[0] != PROVIDER:
        raise SystemExit(f"{PROVIDER} not active: {obj.sess.get_providers()}")
    if FIXED_PAD:  # one input shape per batch size, so DirectML compiles once instead of once per padded length
        p = obj.tok.padding
        obj.tok.enable_padding(pad_id=p["pad_id"], pad_token=p["pad_token"], length=FIXED_PAD)
    return obj


def single_query_ms(enc: Encoder, texts: list[str]) -> dict:
    """What a user waits for: one query at a time, batch 1, after warm-up."""
    for t in texts[:5]:
        enc.embed([t], "query", 1)
    ms = []
    for t in texts:
        s = time.perf_counter()
        enc.embed([t], "query", 1)
        ms.append((time.perf_counter() - s) * 1000)
    return {"p50": round(float(np.percentile(ms, 50)), 2), "p95": round(float(np.percentile(ms, 95)), 2)}


def rerank(name: str, qtexts: list[str], pools: list[list[str]]) -> dict:
    """E12-style second stage: score each query against its candidate pool on CPU and on GPU."""
    from lab import CrossEncoder
    out = {"reranker": name, "queries": len(qtexts), "pool": len(pools[0]) if pools else 0}
    scores = {}
    for label, ce in (("cpu", CrossEncoder(name)), ("gpu", on_gpu(CrossEncoder(name)))):
        ce.score(qtexts[0], pools[0])  # warm-up
        ms, scores[label] = [], []
        for q, pool in zip(qtexts, pools):
            s = time.perf_counter()
            scores[label].append(ce.score(q, pool))
            ms.append((time.perf_counter() - s) * 1000)
        out[f"{label}_ms_per_query_p50"] = round(float(np.percentile(ms, 50)), 1)
    out["max_abs_score_diff"] = round(float(max(np.abs(a - b).max() for a, b in zip(scores["cpu"], scores["gpu"]))), 5)
    out["top10_order_identical"] = round(float(np.mean([list(np.argsort(-a)[:10]) == list(np.argsort(-b)[:10])
                                                        for a, b in zip(scores["cpu"], scores["gpu"])])), 4)
    return out


def timed(enc: Encoder, texts: list[str], kind: str, batch: int) -> tuple[np.ndarray, float]:
    enc.embed(texts[:batch], kind, batch)  # warm-up: session init and first shapes
    t = time.perf_counter()
    vecs = enc.embed(texts, kind, batch)
    return vecs, time.perf_counter() - t


def ndcg(doc_ids: list[str], docs: np.ndarray, qids: list[str], qv: np.ndarray, qrels: dict) -> float:
    scores = qv @ docs.T
    top = np.argsort(-scores, axis=1)[:, :10]
    return float(np.mean([metrics.ndcg_at_k([doc_ids[i] for i in row], qrels[q], 10) for q, row in zip(qids, top)]))


def run(dataset: str, model: str, batch: int, smoke: bool, reranker: str | None) -> dict:
    corpus, queries, qrels = fetch.load(dataset, "test")
    doc_ids = sorted(corpus)
    texts = [f"{corpus[d][0]}\n{corpus[d][1]}".strip() for d in doc_ids]
    qids = sorted(q for q in queries if q in qrels and any(v > 0 for v in qrels[q].values()))
    qtexts = [queries[q] for q in qids]
    if smoke:
        texts, doc_ids, qtexts, qids = texts[:32], doc_ids[:32], [], []
    cpu, gpu = Encoder(model), on_gpu(Encoder(model))
    out = {"dataset": dataset, "model": model, "batch": batch, "docs": len(texts), "queries": len(qtexts), "smoke": smoke}
    dc, tc = timed(cpu, texts, "passage", batch)
    dg, tg = timed(gpu, texts, "passage", batch)
    cos = (dc * dg).sum(1)
    out.update(cpu_docs_per_s=round(len(texts) / tc, 1), gpu_docs_per_s=round(len(texts) / tg, 1), speedup=round(tc / tg, 2),
               cosine_min=round(float(cos.min()), 6), cosine_mean=round(float(cos.mean()), 6))
    if qtexts:
        qc, _ = timed(cpu, qtexts, "query", batch)
        qg, _ = timed(gpu, qtexts, "query", batch)
        out.update(ndcg_cpu=round(ndcg(doc_ids, dc, qids, qc, qrels), 4), ndcg_gpu=round(ndcg(doc_ids, dg, qids, qg, qrels), 4),
                   top10_identical=round(float(np.mean([set(a) == set(b) for a, b in zip(
                       np.argsort(-(qc @ dc.T), axis=1)[:, :10], np.argsort(-(qg @ dg.T), axis=1)[:, :10])])), 4))
        sample = qtexts[:100]
        out.update(single_query_cpu_ms=single_query_ms(cpu, sample), single_query_gpu_ms=single_query_ms(gpu, sample))
        if reranker:
            top = np.argsort(-(qc[:20] @ dc.T), axis=1)[:, :50]  # pool of 50 dense candidates for 20 queries
            out["rerank"] = rerank(reranker, qtexts[:20], [[texts[i] for i in row] for row in top])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="scifact")
    ap.add_argument("--model", action="append", required=True)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--smoke", action="store_true", help="32 documents, no queries: checks that DirectML runs and agrees")
    ap.add_argument("--reranker", help="also time a cross-encoder (lab RERANKERS name) over 50 candidates for 20 queries")
    ap.add_argument("--provider", choices=("dml", "openvino"), default="dml",
                    help="accelerated side: DirectML GPU (bench/.gpuenv) or OpenVINO on the CPU (bench/.ovenv); the other side is ORT CPU")
    ap.add_argument("--fixed-pad", type=int, default=0, help="pad every GPU input to this many tokens (fixed shapes)")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    global FIXED_PAD, PROVIDER
    FIXED_PAD = args.fixed_pad
    PROVIDER = {"dml": "DmlExecutionProvider", "openvino": "OpenVINOExecutionProvider"}[args.provider]
    if args.provider == "openvino" and sys.platform == "win32":  # the wheel needs OpenVINO's DLLs (openvino 2025.4 for ORT 1.24)
        import onnxruntime.tools.add_openvino_win_libs as ov_libs
        ov_libs.add_openvino_libs_to_path()
    import onnxruntime as ort
    report = {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "machine": platform.processor(),
              "onnxruntime": ort.__version__, "providers": ort.get_available_providers(), "accelerated": PROVIDER, "gpu_fixed_pad": FIXED_PAD,
              "results": [run(args.dataset, m, args.batch, args.smoke, args.reranker if i == 0 else None)
                          for i, m in enumerate(args.model)]}
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite {args.output}")
        args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
