"""Recheck the official Qwen3-4B GGUF without the duplicate terminal token."""
from pathlib import Path
import sys

BENCH = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import lab  # noqa: E402
import models  # noqa: E402
import sweep  # noqa: E402
import sweeps  # noqa: E402

SPEC = dict(models.MODELS["gguf-qwen3-4b-gpu"])
SPEC.pop("suffix", None)  # llama-server already appends the GGUF terminal token
models.MODELS["qwen3-4b-single-token-20261116"] = SPEC


def candidate(_dataset, base):
    base = lab.merge(base, {"chunker": {"kind": "whole"}, "lexical": {"tokenizer": {"stem": "en"}},
                            "fusion": {"kind": "cc", "norm": "zscore", "alpha": 0.55}})
    return [("Qwen3-4B single-token hybrid", lab.merge(base, {"dense": {
        "model": "qwen3-4b-single-token-20261116", "extra": {"model": ""}}}))]


if __name__ == "__main__":
    sweeps.SWEEPS["qwen4-single-token-20261116"] = candidate
    raise SystemExit(sweep.main())
