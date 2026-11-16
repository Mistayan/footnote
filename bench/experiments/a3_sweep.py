"""Register frozen A3 conversions in the lab without changing existing sweeps."""
from pathlib import Path
import sys

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH / "lab"))

import lab  # noqa: E402
import models  # noqa: E402
import sweep  # noqa: E402
import sweeps  # noqa: E402

WEB = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
QUESTION = "Instruct: Given a question, retrieve passages that can help answer the question.\nQuery: "

for name, repo, revision, filename, digest, prompt in (
    ("octen-4b", "seamon67/Octen-Embedding-4B-GGUF", "80cd80f8c5db1f1a77b053aab6d332b04db0a55a", "Octen-Embed-4B-Q8_0.gguf", "7bc93bb1a5a1f28ee89668e04d034a30c7cf1358195f1f1b2a8a8ace68bd2632", WEB),
    ("f2llm-1.7b", "seamon67/F2LLM-v2-1.7B-GGUF", "4c7707d0606d07f57efc730062f6fedf81ad26de", "F2LLM-V2-1.7B-Q8_0.gguf", "0aea1de64aed99b266680be0f3ddfc58c7e624b35971620f8b15b427da559a75", QUESTION),
    ("harrier-0.6b", "calculatortamer/harrier-oss-v1-0.6b-Q8_0-GGUF", "1e84dd3b4df5c8f9129b8b740a04d05c8cf95e95", "harrier-oss-v1-0.6b-q8_0.gguf", "3948d3b594931ba5c62479c09a2a0ad41c8008640d6280a79b346f0f18ef72e6", WEB),
):
    models.MODELS["a3v2-" + name] = {
        "gguf": {"repo": repo, "revision": revision, "file": filename, "sha256": digest},
        "pooling": "last", "max_len": 512,
        "q": prompt, "p": "", "lang": "multi", "ngl": 99, "qngl": 99,
    }

# The server adds each GGUF's terminal token automatically. The v2 model names
# prevent reuse of any cache produced by the interrupted double-token attempt.
models.MODELS["a3v2-octen-4b"]["q"] = WEB.rstrip()
models.MODELS["a3v2-octen-4b"]["p"] = " "


def candidates(_dataset: str, base: dict) -> list:
    base = lab.merge(base, {"chunker": {"kind": "whole"},
                            "lexical": {"tokenizer": {"stem": "en"}},
                            "fusion": {"kind": "cc", "norm": "zscore", "alpha": 0.55}})
    return [(f"A3 {name} alone in the hybrid", lab.merge(base, {"dense": {"model": name, "extra": {"model": ""}}}))
            for name in ("a3v2-harrier-0.6b", "a3v2-f2llm-1.7b", "a3v2-octen-4b")]


if __name__ == "__main__":
    sweeps.SWEEPS["a3-20261115"] = candidates
    raise SystemExit(sweep.main())
