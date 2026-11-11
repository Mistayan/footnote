"""Explicit provisioning only: fetch immutable PUBLIC model artifacts, never documents."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = {
    "e5-small": ("Xenova/multilingual-e5-small", "761b726dd34fb83930e26aab4e9ac3899aa1fa78", "query: ", "passage: ", 512),
    "minilm": ("Xenova/paraphrase-multilingual-MiniLM-L12-v2", "2c4055b12046f11709e9df2c122e59ffbdc2f900", "", "", 128),
}


def provision(name):
    repo, revision, query_prefix, passage_prefix, max_length = CANDIDATES[name]
    destination = ROOT / "artifacts/models" / name
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for remote, local in [("tokenizer.json", "tokenizer.json"), ("onnx/model_quantized.onnx", "model.onnx")]:
        path = destination / local
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{remote}"
        if not path.exists():
            partial = path.with_suffix(".partial")
            urllib.request.urlretrieve(url, partial)
            partial.replace(path)
        artifacts[local] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size, "url": url}
    manifest = {"repository": repo, "revision": revision, "files": artifacts, "pooling": "attention-mask-mean-l2", "query_prefix": query_prefix, "passage_prefix": passage_prefix, "max_length": max_length, "dimension": 384, "quantization": "onnx-dynamic-int8"}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"name": name, "path": destination.as_posix(), "manifest": manifest}))


if __name__ == "__main__":
    for name in CANDIDATES:
        provision(name)
