"""Standalone frozen scoped-query2 adapter, NOT a shipped-runtime activation."""
import hashlib
import json
import time
from pathlib import Path
from .core import validate_evidence
from tools.rank_input_repair.runner import acquire, rerank
from tools.request_scope_repair.runner import Resident, SNAP
from tools.request_scope_repair.compiler import build_catalog, compile_scope, get_evidence


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PublicRetrieval:
    def __init__(self, run, record=lambda x: None):
        self.record = record
        self.paths = {s: SNAP/'sources'/(s+'.txt') for s in load(SNAP/'source-receipts.json')}
        self.hashes = {s: sha(p) for s,p in self.paths.items()}
        self.texts = {s:p.read_text(encoding='utf8') for s,p in self.paths.items()}
        self.sources = load(SNAP/'source-receipts.json')
        for s,r in self.sources.items():
            if sha(SNAP/'sources'/(s+'.raw')) != r['sha256'] or self.hashes[s] != r['text_sha256']:
                raise ValueError('frozen source receipt mismatch')
        raw = {s:(SNAP/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in self.sources}
        self.catalog = build_catalog(self.sources, raw)
        self.session = Resident(run/'resident')

    def bind(self, original):
        return BoundRetrieval(self, original)

    def close(self):
        self.session.cleanup = self.session.close()


class BoundRetrieval:
    def __init__(self, adapter, original):
        self.adapter = adapter
        self.scope = compile_scope(original, adapter.catalog)
        self.seen = {}

    def present(self, document_id):
        a = self.adapter
        e = get_evidence(a.session.docs[document_id], a.texts, a.catalog, self.scope)
        v = e['presentation']
        source = e['original']['source']
        if sha(a.paths[source]) != a.hashes[source]:
            raise ValueError('source changed since freeze')
        handle = 'H' + hashlib.sha256((source+str(v['start'])+str(v['end'])+v['sha256']).encode()).hexdigest()[:16]
        hit = dict(handle=handle, source=source, text=v['text'], start=v['start'], end=v['end'], sha256=v['sha256'],
                   source_sha256=a.hashes[source], provenance=e['provenance'], freshness='current',
                   trust='untrusted_source_data', boundary_complete=v.get('boundary_complete'),
                   scope=self.scope['constraints'])
        validate_evidence(hit, a.texts)
        self.seen[handle] = document_id
        return hit

    def search(self, query):
        a = self.adapter
        t = time.perf_counter()
        acquisition = acquire(a.session, query, a.catalog, self.scope)
        result = rerank(a.session, query, self.scope, acquisition['pool'], 'query2')
        hits = [self.present(n) for n in result['ranked'][:5]]
        a.record(dict(kind='retrieval', query=query, scope=self.scope, acquisition=acquisition,
                      ranking=result, hits=hits, elapsed_seconds=time.perf_counter()-t))
        return hits

    def get(self, handle):
        if handle not in self.seen:
            raise ValueError('unknown citation handle')
        return self.present(self.seen[handle])
