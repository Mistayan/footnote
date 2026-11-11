"""Offline-only pinned adapter for the already provisioned benchmark ranker."""
from tools.agent_knowledge_runtime import digest, no_links
from tools.retrieval_ablation import CrossEncoder

RECEIPT_SHA256 = '4f18f4adefa4156052c8c32804b0e5b02b9c1c1d91bbd4587d7f6c11f49ebf6d'
RECIPE = 'mmarco-mMiniLMv2-L12-H384-v1@1427fd652930e4ba29e8149678df786c240d8825-quint8-avx2-max512-longest-first-batch4-cpu2-1-logits-v1'


class ResidentReranker(CrossEncoder):
    """One CPU session; exact frozen receipt and all file hashes validated offline.

    Reuse the incumbent recipe rather than fork tokenization/inference semantics.
    Neither this adapter nor the incumbent loader has a download path.
    """
    def __init__(self, directory):
        directory = no_links(directory)
        if digest(no_links(directory / 'receipt.json').read_bytes()) != RECEIPT_SHA256:
            raise ValueError('reranker pinned receipt mismatch')
        for name in ('README.md', 'config.json', 'tokenizer.json', 'model.onnx'):
            no_links(directory / name)
        super().__init__(directory)
        self.identity = RECEIPT_SHA256
        self.recipe = RECIPE
        self.loads = 1