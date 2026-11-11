"""Offline CPU ONNX embeddings. Input/output are local bounded JSON snapshots."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


def encode(model_path, request):
    model = Path(model_path)
    manifest_bytes = (model / "manifest.json").read_bytes()
    m = json.loads(manifest_bytes)
    if m["pooling"] != "attention-mask-mean-l2" or not 1 <= m["max_length"] <= 512 or m["dimension"] != 384:
        raise ValueError("unsupported embedding recipe")
    for name in ["model.onnx", "tokenizer.json"]:
        path = model / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != m["files"][name]["sha256"]:
            raise ValueError("model artifact hash mismatch: " + name)
    texts = request["texts"]
    if not 1 <= len(texts) <= 10000 or any(not isinstance(t, str) or len(t.encode()) > 64000 for t in texts):
        raise ValueError("embedding input bound exceeded")
    tokenizer = Tokenizer.from_file(str(model / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=m["max_length"])
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model / "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
    prefix = m["query_prefix"] if request["kind"] == "query" else m["passage_prefix"]
    result = []
    truncated = 0
    for start in range(0, len(texts), 8):
        tokens = tokenizer.encode_batch([prefix + t for t in texts[start:start + 8]])
        ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
        mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
        truncated += int((mask.sum(axis=1) >= m["max_length"]).sum())
        inputs = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        output = session.run(None, {i.name: inputs[i.name] for i in session.get_inputs()})[0]
        vectors = (output * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        if vectors.shape[1] != m["dimension"] or not np.isfinite(vectors).all():
            raise ValueError("invalid embedding output")
        result.extend(vectors.tolist())
    return {"vectors": result, "model_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "truncated_at_limit": truncated, "runtime": {"onnxruntime": ort.__version__, "numpy": np.__version__}}


if __name__ == "__main__":
    try:
        request_path = Path(sys.argv[2])
        if request_path.stat().st_size > 64000000:
            raise ValueError("request exceeds 64 MB")
        print(json.dumps(encode(sys.argv[1], json.loads(request_path.read_text(encoding="utf-8")))))
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
