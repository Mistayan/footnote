"""Controlled-folder API built on the existing revision-safe authority adapter.

No network listener: construct with an explicit incumbent Runtime, or use the
resident JSONL module. Sources and returned excerpts are untrusted data.
"""
from tools.agent_knowledge_runtime import Runtime, digest
from .rerank import ResidentReranker
import math
import time


def fuse_ranks(dense, lexical):
    """Equal RRF k60, one-based unique ranks; deterministic identity ties."""
    scores = {}
    for branch in (dense, lexical):
        for rank, identity in enumerate(dict.fromkeys(branch), 1):
            scores[identity] = scores.get(identity, 0.0) + 1.0 / (60 + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def compact_evidence(result):
    """Versioned, reversible factoring of equal metadata, never evidence removal."""
    envelope = {'contract_version': 2, 'evidence_format': 'compact'}
    if 'hits' not in result:
        return dict(envelope, evidence=dict(result))
    hits = result['hits']
    keys = ('owner', 'model', 'path', 'revision', 'sha256', 'freshness', 'usable', 'trust', 'applicability')
    shared = {key: hits[0][key] for key in keys if len(hits) > 1 and key in hits[0]
              and all(key in hit and hit[key] == hits[0][key] for hit in hits)}
    return dict(result, **envelope, shared=shared,
                hits=[{key: value for key, value in hit.items() if key not in shared} for hit in hits])


class KnowledgeRuntime:
    """Combine explicit allowlist observation and durable derived reconciliation.

    The wrapped authority owns model, SQLite, exclusive lock and Qdrant identity.
    Requests are serial; callers must not share this object between threads.
    """

    def __init__(self, authority: Runtime, *, reranker_model=None, source_manifest=None):
        self.authority = authority
        from pathlib import Path
        from .metadata import MetadataIndex
        if source_manifest is None and hasattr(authority, 'path') and Path(str(authority.path) + '.metadata.json').exists():
            raise ValueError('metadata-bound runtime requires explicit source_manifest on restart')
        self.metadata = MetadataIndex(authority, source_manifest) if source_manifest is not None else None
        self.lexical = None
        self.reranker = ResidentReranker(reranker_model) if reranker_model is not None else None
        self.selected_mode = None
        self.selected_budget = None

    def session_stats(self):
        return {'reranker_loads': self.reranker.loads if self.reranker else 0,
                'reranker_model': self.reranker.identity if self.reranker else None,
                'reranker_recipe': self.reranker.recipe if self.reranker else None,
                'selected_search_mode': self.selected_mode, 'selected_rerank_budget': self.selected_budget}

    def evidence(self, identity, constraints=None):
        hit = self.authority.hydrate(identity)
        return self.metadata.present(hit, constraints or {}) if self.metadata else hit

    def rerank_candidates(self, query, fused, limit, budget, stages, constraints=None):
        started = time.perf_counter()
        documents = []
        # Freeze pool20, recheck eligibility, then spend the named budget.
        # No refill outside this pool and no unscored tail after inference.
        for identity, _ in fused[:20]:
            try:
                documents.append(self.evidence(identity, constraints))
            except ValueError:
                continue
        eligible_count = len(documents)
        documents = documents[:int(budget[6:])]
        stages['eligibility_ms'] = (time.perf_counter()-started)*1000
        started = time.perf_counter()
        ranked, logits = self.reranker.rank(query, documents) if documents else ([], {})
        expected = {d['id'] for d in documents}
        if len(ranked) != len(expected) or set(ranked) != expected or set(logits) != expected or not all(math.isfinite(v) for v in logits.values()):
            raise ValueError('invalid reranker candidate permutation/logits')
        stages['rerank_ms'] = (time.perf_counter()-started)*1000
        started = time.perf_counter()
        hits, scores = [], dict(fused)
        for identity in ranked[:limit]:
            try:
                hits.append(dict(self.evidence(identity, constraints), score=scores[identity], rerank_logit=logits[identity]))
            except ValueError:
                continue
        stages['presentation_ms'] = (time.perf_counter()-started)*1000
        return hits, {'budget': budget, 'candidate_count': len(documents), 'eligible_pool_count': eligible_count,
                      'model': self.reranker.identity, 'recipe': self.reranker.recipe,
                      'score_semantics': 'logits_not_confidence', 'stages': stages}

    def lexical_search(self, request):
        query, limit = request.get('query'), request.get('limit', 5)
        if set(request) - {'op', 'request_id', 'mode', 'query', 'limit', 'rerank_budget', 'constraints'}:
            raise ValueError('unknown search fields')
        request_id = request.get('request_id', '')
        if not isinstance(request_id, str) or len(request_id) > 64:
            raise ValueError('request_id must be a string of at most 64 characters')
        if not isinstance(query, str) or not 1 <= len(query) <= 1024 or type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError('query bound 1..1024 characters; limit 1..8')
        started = time.perf_counter()
        stages = {}
        constraints = request.get('constraints', {})
        eligible = None
        if self.metadata:
            eligible = []
            for identity in self.metadata.eligible(constraints):
                try:
                    self.evidence(identity, constraints)
                    eligible.append(identity)
                except ValueError:
                    continue
        mode = request.get('mode', 'semantic')
        if self.lexical is None and mode != 'semantic':
            from .lexical import LexicalIndex
            self.lexical = LexicalIndex(self.authority)
        hits = []
        lexical_rows = self.lexical.search(query, 20 if mode == 'hybrid_rrf' else 64, eligible=eligible) if mode != 'semantic' else []
        if mode in ('hybrid_rrf', 'semantic'):
            lexical_ids = []
            for identity, _ in lexical_rows:
                try:
                    self.evidence(identity, constraints)
                    lexical_ids.append(identity)
                except ValueError:
                    continue
            stages['lexical_ms'] = (time.perf_counter()-started)*1000
            started = time.perf_counter()
            vector = self.authority.encoder.encode([query], 'query')[0]
            stages['query_encode_ms'] = (time.perf_counter()-started)*1000
            started = time.perf_counter()
            body = {'query': vector, 'limit': 60 if mode == 'hybrid_rrf' else 64, 'with_payload': True, 'with_vector': False}
            if eligible is not None:
                body['filter'] = {'must': [{'has_id': eligible}]}
            points = self.authority.remote.request('POST', '/points/query', body)['points'] if eligible != [] else []
            stages['backend_ms'] = (time.perf_counter()-started)*1000
            started = time.perf_counter()
            dense_ids = []
            for point in sorted(points, key=lambda p: (-p['score'], p['id'])):
                try:
                    hit = self.evidence(point['id'], constraints)
                except ValueError:
                    continue
                if point['payload'] != {k: hit[k] for k in ('owner', 'model', 'id', 'revision', 'sha256')}:
                    continue
                dense_ids.append(point['id'])
            fused = fuse_ranks(dense_ids, lexical_ids) if mode == 'hybrid_rrf' else [(p['id'], p['score']) for p in points if p['id'] in dense_ids]
            stages['dense_validate_fuse_ms'] = (time.perf_counter()-started)*1000
            if 'rerank_budget' in request:
                hits, reranking = self.rerank_candidates(query, fused, limit, request['rerank_budget'], stages, constraints)
                self.selected_mode, self.selected_budget = mode, request['rerank_budget']
                return {'hits': hits, 'mode': mode, 'answerability': 'not_estimated',
                        'pending': self.authority.pending(), 'reranking': reranking}
            for identity, score in fused[:limit]:
                # Revalidate at presentation, even if lexical/dense hydration was earlier.
                try:
                    hits.append(dict(self.evidence(identity, constraints), score=score))
                except ValueError:
                    continue
        else:
            for identity, score in lexical_rows:
                try:
                    hits.append(dict(self.evidence(identity, constraints), score=score))
                except ValueError:
                    continue
                if len(hits) == limit:
                    break
        self.selected_mode, self.selected_budget = mode, None
        return {'hits': hits, 'mode': mode, 'answerability': 'not_estimated',
                'pending': self.authority.pending()}

    def handle(self, request: dict) -> dict:
        if isinstance(request, dict) and 'constraints' in request:
            from .metadata import validate_fields
            validate_fields(request['constraints'])
            if not self.metadata or request.get('op') not in ('search', 'get'):
                raise ValueError('constraints require explicit source manifest and search/get')
        if isinstance(request, dict) and 'rerank_budget' in request:
            if request.get('op') != 'search' or request.get('mode') != 'hybrid_rrf':
                raise ValueError('rerank_budget supported only for explicit hybrid_rrf search')
            if request['rerank_budget'] not in ('budget5', 'budget10', 'budget20'):
                raise ValueError('rerank_budget must be budget5, budget10 or budget20')
            if self.reranker is None:
                raise ValueError('reranker not loaded; explicit --reranker-model required')
        if isinstance(request, dict) and 'response_format' in request:
            if request.get('op') not in ('search', 'get') or request['response_format'] != 'compact_v2':
                raise ValueError('response_format compact_v2 is supported only for search/get')
            plain = {key: value for key, value in request.items() if key != 'response_format'}
            return compact_evidence(self.handle(plain))
        if isinstance(request, dict) and request.get('op') == 'search' and request.get('mode') in ('bm25_or', 'hybrid_rrf'):
            return self.lexical_search(request)
        if self.metadata and isinstance(request, dict) and request.get('op') == 'search':
            if request.get('mode', 'semantic') != 'semantic':
                raise ValueError('metadata mode supports semantic/bm25_or/hybrid_rrf, not legacy overlap')
            return self.lexical_search(request)
        if self.metadata and isinstance(request, dict) and request.get('op') == 'get':
            hit = self.authority.handle({k: v for k, v in request.items() if k != 'constraints'})
            return self.metadata.present(hit, request.get('constraints', {}))
        if isinstance(request, dict) and request.get('op') == 'sync':
            if set(request) - {'op', 'request_id'}:
                raise ValueError('sync accepts no paths or additional fields')
            request_id = request.get('request_id', '')
            if not isinstance(request_id, str) or len(request_id) > 64:
                raise ValueError('request_id must be a string of at most 64 characters')
            if not self.authority.write:
                raise ValueError('writes not authorized; --write required')
            if self.metadata:
                self.metadata.snapshot()
            expected = {name: digest(data) if data is not None else None
                        for name in self.authority.allowed
                        for data in [self.authority.read_source(name)]}
            indexed = self.authority.handle({'op': 'ingest', 'expected': expected})
            if self.metadata:
                self.metadata.reconcile()
            # Once opted in, reconcile the derived snapshot even before a failed
            # vector sync. Reopen persistent lexical state on writer restarts.
            from pathlib import Path
            if self.lexical is None and hasattr(self.authority, 'path') and Path(str(self.authority.path) + '.lexical.sqlite').exists():
                from .lexical import LexicalIndex
                self.lexical = LexicalIndex(self.authority)
            if self.lexical is not None:
                self.lexical.reconcile()
            reconciled = self.authority.handle({'op': 'sync'})
            return {'changed': indexed['changed'], 'pending': reconciled['pending']}
        result = self.authority.handle(request)
        if request.get('op') == 'stats':
            return dict(result, **self.session_stats())
        if request.get('op') == 'search':
            self.selected_mode, self.selected_budget = result['mode'], None
        return result

    def close(self) -> None:
        try:
            if self.lexical is not None:
                self.lexical.close()
                self.lexical = None
        finally:
            self.reranker = None
            self.authority.close()
