"""Independent Okapi BM25 and bounded frozen retrieval diagnostic (not production)."""
from collections import Counter
import math
import re


def tokens(text):
    """Unicode lower-case; preserve underscores and internal dotted identifiers/versions.

    No stopwords, stemming, accent stripping, identifier splitting or expansion.
    Trailing punctuation dots are excluded. Query term frequency is binary.
    """
    return re.findall(r'\w+(?:\.\w+)*', text.lower(), re.UNICODE)


class OkapiBM25:
    """Positive Robertson IDF log(1+(N-df+.5)/(df+.5)); explicit k1=1.2 b=.75."""
    def __init__(self, documents, k1=1.2, b=.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError('k1 must be positive and b in [0,1]')
        self.k1, self.b = k1, b
        self.counts = {d['id']: Counter(tokens(d['text'])) for d in documents}
        if len(self.counts) != len(documents):
            raise ValueError('duplicate document IDs')
        self.lengths = {name: sum(count.values()) for name, count in self.counts.items()}
        self.average = sum(self.lengths.values()) / len(documents) if documents else 0
        df = Counter(term for count in self.counts.values() for term in count)
        self.idf = {term: math.log(1 + (len(documents) - n + .5) / (n + .5)) for term, n in df.items()}

    def search(self, query, limit=20):
        terms = set(tokens(query))
        scores = {}
        for name, count in self.counts.items():
            score = 0.0
            for term in sorted(terms & count.keys()):
                tf = count[term]
                score += self.idf[term] * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * self.lengths[name] / self.average))
            if score > 0:
                scores[name] = score
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]


def representation(documents, sources, source_texts):
    """One original source heading uniformly prepended; originals never mutated.

    UNKNOWN heading adds nothing. No document IDs, query terms, labels or source keys
    become searchable metadata. This variant changes lexical representation only.
    """
    from retrieval_ablation import source_title
    result = []
    for doc in documents:
        title = source_title(source_texts[doc['source']])
        result.append(dict(doc, text=(title + '\n' if title != 'UNKNOWN' else '') + doc['text']))
    return result


def version_states(query, documents, sources):
    from retrieval_ablation import admissibility, source_metadata
    return {name: admissibility(query, source_metadata(sources[d['source']]))
            for name, d in documents.items()}


def gated_pool(ranked, states):
    """Same pool20 budget in every branch, gate before selection and at presentation.

    Reject wrong CPython version and unknown provenance on explicit Python version
    queries. No refill from outside pool20 and no confidence/abstention threshold.
    """
    pool = ranked[:20]
    candidates = [n for n in pool if not states[n].startswith('REJECT')]
    top5 = [n for n in candidates if not states[n].startswith('REJECT')][:5]
    return pool, candidates, top5


# Predeclared, not selected after viewing scores. Every branch uses the same gate.
VARIANTS = ('dense', 'fts5_or', 'okapi', 'okapi_title',
            'dense_fts5_rrf', 'dense_okapi_rrf', 'dense_okapi_title_rrf')
BLOCKS = 2


def compact_delivery(row):
    """Lossless full-text evidence envelope: remove duplicate previews and equal IDs.

    Keep judgment status explicit (not confidence), original full evidence, both
    source and passage hashes, offsets and applicability. No deferred get required.
    """
    evidence = []
    for citation in row['snippets_sources']:
        item = {k: v for k, v in citation.items() if k != 'snippet'}
        if item['passage_id'] == item['parent_id']:
            del item['passage_id']
        evidence.append(item)
    return {'query': row['query'], 'evidence': evidence}


def experiment(run):
    """Run seven fixed branches, two reversed blocks, owned real Qdrant only."""
    import datetime
    import hashlib
    import json
    from pathlib import Path
    import platform
    import socket
    import statistics
    import sys
    import time
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import lexical_or, source_title, source_metadata
    from server_benchmark import Server, SERVER, save, sha, percentile

    repo = Path(__file__).resolve().parents[1]
    run = Path(run).resolve()
    root = repo / 'artifacts/bm25-retrieval'
    if not run.is_relative_to(root) or run == root:
        raise ValueError('new owned bm25-retrieval subdirectory required')
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('symlink run forbidden')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    measured = repo / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
    old_freeze = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, expected in old_freeze['files'].items():
        assert sha(snapshot / name) == expected, name
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    assert len(corpus) == 136 and len(queries) == 32
    documents = {d['id']: d for d in corpus}
    source_texts = {n: (snapshot / 'sources' / (n + '.txt')).read_text(encoding='utf-8') for n in sources}
    for d in corpus:
        assert source_texts[d['source']][d['start']:d['end']] == d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    inherited = json.loads((measured / 'freeze.json').read_bytes())
    for name, expected in inherited['inputs'].items():
        if '/models/' in name or name.endswith('qdrant.exe'):
            assert sha(repo / name) == expected, name
    paths = [Path(__file__), repo / 'tests/bm25_retrieval_benchmark_test.py', SERVER,
             repo / 'requirements-hybrid.lock', snapshot / 'freeze.json', measured / 'freeze.json']
    paths += [repo / 'tools' / name for name in ('technical_quality.py', 'qdrant_quality.py',
              'server_benchmark.py', 'retrieval_ablation.py', 'hybrid_dataset.py')]
    paths += [snapshot / name for name in old_freeze['files']]
    paths += [measured / name for name in ('original-vectors.npy', 'query-vectors.npy')]
    paths += [repo / 'artifacts/models/minilm' / name for name in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    inputs = {p.relative_to(repo).as_posix(): sha(p) for p in paths}
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
              'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    freeze = {
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': inputs,
        'before_inference': True, 'variants': VARIANTS, 'blocks': BLOCKS,
        'documents': 136, 'queries': 32, 'model': 'unchanged resident pinned MiniLM CPU',
        'lexical': 'FTS5 existing unicode61 default BM25 OR vs independent Okapi k1=1.2 b=.75 positive Robertson IDF; binary query tf; both top20',
        'tokenization': 'Okapi Unicode lower; underscores and internal dots intact; no stopword/stemming/accent folding/splitting. FTS5 uses incumbent technical literal phrases and its default unicode61, which splits underscores/dots and removes accents.',
        'representation': 'body baseline; separate okapi_title uniformly prepends original full-source heading only if detected; no labels, query terms or document/source IDs added; original evidence unchanged',
        'pool': 'dense ANN ef128 top60, lexical top20; RRF equal weights k60 rank1 stable ID ties; common post-ranking pool20 then gate, top5 no refill',
        'gates': 'ALL branches reject wrong CPython family/exact requested patch and UNKNOWN on explicit Python version; gate independently at presentation. NOT_ASSESSED otherwise; narrow provenance gate not API oracle',
        'metrics': 'selected-label P1 P3 P5 denominators1/3/5; RR@5, recall@5, pool20 label hits, eligible pool hits, incompatible and UNKNOWN/unjudged, no-answer nonempty false acceptance; split/category aggregate',
        'labels': 'INCOMPLETE REUSED diagnostic labels; UNKNOWN not false; no independent validation or 90% certification; no calibration/abstention',
        'language': 'English public sources with mixed English/French queries; no translation. Language mismatch can favor dense and is not engine-only evidence',
        'timing': 'actual per-branch sequential requests two reversed blocks. Dense branches fresh encode verified byte-identical to historical query vectors, lexical branches need no encode. Ranking includes retrieval/fusion/gates; E2E includes encode if needed plus evaluation/citation JSON serialization; logging excluded. No component sums passed off as E2E; warmup separate',
        'qdrant': config, 'reranking': 'omitted to bound runtime; no downloads or model changes',
        'postgresql': 'separate UNPROVISIONED candidate; not measured',
        'tool_calls': 'one public search request yields five citations/excerpts and identity hashes in evidence envelope; internal query/fusion/citation counts reported, not agent/MCP benchmark',
        'delivery_ablation': 'after retrieval, serialize identical five full-evidence citations: baseline query+evidence with duplicate snippet and passage_id vs compact removal of snippet and identical passage_id only; same JSON separators. Full source references/hash/offset/text/status/version retained; all224 unique result envelopes; no retrieval, rank, proof truncation or extra get calls. Serializer microtiming is not agent/MCP latency'}
    save(run / 'freeze.json', freeze)
    save(run / 'corpus.json', corpus)
    save(run / 'judgments.json', queries)
    save(run / 'source-receipts.json', sources)
    title_audit = {n: {'title': source_title(text), 'normalized_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'start': text.find(source_title(text))} for n, text in source_texts.items()}
    save(run / 'title-provenance.json', title_audit)
    enriched = representation(corpus, sources, source_texts)
    save(run / 'lexical-title-representation.json', enriched)
    qvectors = np.load(measured / 'query-vectors.npy')
    vectors = np.load(measured / 'original-vectors.npy')
    assert qvectors.shape == (32, 384) and vectors.shape == (136, 384)
    np.save(run / 'query-vectors.npy', qvectors)
    np.save(run / 'original-vectors.npy', vectors)
    report = {'run': str(run), 'freeze_sha256': sha(run / 'freeze.json'),
              'environment': {'python': sys.version, 'platform': platform.platform()},
              'status': freeze['labels'], 'postgresql': freeze['postgresql']}
    started = time.perf_counter()
    encoder = tq.ResidentEncoder(repo / 'artifacts/models/minilm')
    report['encoder_load_validate_ms'] = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    db = tq.lexical_index(corpus)
    indices = {'okapi': OkapiBM25(corpus), 'okapi_title': OkapiBM25(enriched)}
    report['lexical_index_build_ms'] = (time.perf_counter() - started) * 1000
    report['representation_characters'] = {'body': sum(len(d['text']) for d in corpus),
                                          'title_body': sum(len(d['text']) for d in enriched)}
    server, rows = Server(run), []

    def request(query, expected_vector, variant, block):
        start = time.perf_counter()
        stages = {}
        dense_needed = variant == 'dense' or variant.startswith('dense_')
        lexical_kind = ('fts5_or' if 'fts5' in variant else 'okapi_title' if 'title' in variant
                        else 'okapi' if 'okapi' in variant else None)
        vector_hash = None
        mark = time.perf_counter()
        if dense_needed:
            vector = encoder.encode([query['query']], 'query')[0]
            assert vector.tobytes() == expected_vector.tobytes()
            vector_hash = hashlib.sha256(vector.tobytes()).hexdigest()
        stages['encode'] = (time.perf_counter() - mark) * 1000
        rank_start = time.perf_counter()
        dense, lexical, response, lexical_scores = [], [], None, []
        mark = time.perf_counter()
        if dense_needed:
            response = server.request('POST', '/collections/bm25/points/query', {
                'query': vector.tolist(), 'limit': 60, 'with_payload': True,
                'with_vector': False, 'params': {'exact': False, 'hnsw_ef': 128}})
            dense = paired.rank_parents(response['result']['points'], corpus)
        stages['qdrant_http_parent'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        if lexical_kind == 'fts5_or':
            lexical = lexical_or(db, query['query'])
        elif lexical_kind:
            lexical_scores = indices[lexical_kind].search(query['query'], 20)
            lexical = [n for n, _ in lexical_scores]
        stages['lexical'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        ranked = tq.fuse(dense, lexical) if variant.endswith('_rrf') else dense if dense_needed else lexical
        states = version_states(query['query'], documents, sources)
        pool, candidates, _ = gated_pool(ranked, states)
        # Independent final trust boundary: rederive from original pinned source URLs.
        final_states = version_states(query['query'], documents, sources)
        top5 = [n for n in candidates if not final_states[n].startswith('REJECT')][:5]
        stages['fusion_gates'] = (time.perf_counter() - mark) * 1000
        stages['ranking'] = (time.perf_counter() - rank_start) * 1000
        mark = time.perf_counter()
        row = paired.review_row(query, top5, variant, 'ann128' if dense_needed else 'lexical',
                                'all_gated_pool20', documents, corpus, sources)
        for s in row['snippets_sources']:
            s['sha256'] = documents[s['parent_id']]['sha256']
            s['metadata'] = source_metadata(sources[s['source']])
        row.update(block=block, pool20=pool, candidates=candidates, eligibility=final_states,
                   selected_pool_hits=sorted(set(pool) & set(query['relevant'])),
                   eligible_pool_hits=sorted(set(candidates) & set(query['relevant'])),
                   selected_pool_recall=len(set(pool) & set(query['relevant'])) / len(query['relevant']) if query['relevant'] else None,
                   rejected_pool=[n for n in pool if states[n].startswith('REJECT')])
        wire = json.dumps(row, ensure_ascii=False).encode()
        stages['evaluation_citation_serialize'] = (time.perf_counter() - mark) * 1000
        stages['e2e'] = (time.perf_counter() - start) * 1000
        row.update(timing_ms=stages, query_vector_sha256=vector_hash, dense=dense, lexical=lexical,
                   lexical_scores=lexical_scores, server_response=response, citation_wire_bytes=len(wire),
                   internal_calls={'encode': int(dense_needed), 'qdrant_query': int(dense_needed),
                                   'lexical_query': int(bool(lexical_kind)), 'citation_envelope': 1})
        return row

    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        server.request('PUT', '/collections/bm25', config)
        server.request('PUT', '/collections/bm25/points?wait=true', {'points': [
            {'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id']}}
            for i, (d, v) in enumerate(zip(corpus, vectors))]})
        deadline = time.monotonic() + 90
        while True:
            info = server.request('GET', '/collections/bm25')['result']
            if info['status'] == 'green' and info['indexed_vectors_count'] == len(corpus):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('HNSW not ready in 90 seconds')
            time.sleep(.2)
        save(run / 'collection-readback.json', info)
        readback = server.request('POST', '/collections/bm25/points', {
            'ids': list(range(1, 137)), 'with_payload': True, 'with_vector': True})['result']
        readback.sort(key=lambda p: p['id'])
        assert len(readback) == 136
        assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(readback))
        error = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - vectors)))
        assert error < 1e-6
        save(run / 'server-readback.json', {'points': readback, 'max_abs_error': error})
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc'] <= report['first_inference_utc']
        started = time.perf_counter()
        for variant in VARIANTS:
            request(queries[0], qvectors[0], variant, -1)
        report['warmup_ms'] = (time.perf_counter() - started) * 1000
        paired.fresh_connection(server)
        for block in range(BLOCKS):
            order = list(enumerate(queries))
            if block % 2:
                order.reverse()
            for i, q in order:
                for variant in VARIANTS if not block % 2 else reversed(VARIANTS):
                    rows.append(request(q, qvectors[i], variant, block))
            save(run / f'block-{block}.json', rows[-32 * len(VARIANTS):])
            print(json.dumps({'completed_block': block, 'requests': len(rows)}), flush=True)
        save(run / 'raw-results.json', rows)
        stored = json.loads((run / 'raw-results.json').read_bytes())
        stable, violations = {}, 0
        assert len(stored) == 448
        qmap = {q['id']: (q, qvectors[i]) for i, q in enumerate(queries)}
        for r in stored:
            q, v = qmap[r['id']]
            assert r['metrics'] == tq.score(r['top5'], q)
            for k in (1, 3, 5):
                assert r['p' + str(k)] == sum(n in q['relevant'] for n in r['top5'][:k]) / k
            states = version_states(q['query'], documents, sources)
            assert r['eligibility'] == states
            ranked = tq.fuse(r['dense'], r['lexical']) if r['variant'].endswith('_rrf') else r['dense'] if r['variant'] == 'dense' else r['lexical']
            assert (r['pool20'], r['candidates'], r['top5']) == gated_pool(ranked, states)
            if r['server_response'] is not None:
                assert r['dense'] == paired.rank_parents(r['server_response']['result']['points'], corpus)
                assert r['query_vector_sha256'] == hashlib.sha256(v.tobytes()).hexdigest()
            if r['variant'] in ('fts5_or', 'dense_fts5_rrf'):
                assert r['lexical'] == lexical_or(db, q['query'])
            if 'okapi' in r['variant']:
                kind = 'okapi_title' if 'title' in r['variant'] else 'okapi'
                assert r['lexical'] == [n for n, _ in indices[kind].search(q['query'])]
            assert r['selected_pool_hits'] == sorted(set(r['pool20']) & set(q['relevant']))
            assert r['eligible_pool_hits'] == sorted(set(r['candidates']) & set(q['relevant']))
            assert r['unjudged'] == [n for n in r['top5'] if n not in set(q['relevant'] + q['incompatible'])]
            violations += sum(states[n].startswith('REJECT') for n in r['candidates'] + r['top5'])
            for s in r['snippets_sources']:
                d = documents[s['parent_id']]
                assert s['text'] == d['text'] and s['sha256'] == d['sha256']
                assert (s['start'], s['end']) == (d['start'], d['end'])
                assert s['url'] == sources[d['source']]['url']
                assert s['source_raw_sha256'] == sources[d['source']]['sha256']
            key = (r['id'], r['variant'])
            if key in stable:
                assert stable[key] == r['top5']
            stable[key] = r['top5']
            assert r['timing_ms']['e2e'] >= r['timing_ms']['ranking']
        assert violations == 0
        report['verification'] = {'verified_rows': len(stored), 'gate_violations': violations,
                                  'ranks_stable_across_blocks': True, 'original_citations_verified': True,
                                  'historical_query_vectors_byte_identical': True,
                                  'server_vector_max_abs_error': error}
        report['rows'] = len(stored)
        summaries = []
        for variant in VARIANTS:
            for split in ('all', 'development', 'holdout'):
                group = [r for r in stored if r['variant'] == variant and (split == 'all' or r['split'] == split)]
                unique = [r for r in group if r['block'] == 0]
                answerable = [r for r in unique if r['relevant']]
                noanswer = [r for r in unique if not r['relevant']]
                item = {'variant': variant, 'split': split, 'queries': len(unique), 'answerable': len(answerable), 'noanswer': len(noanswer)}
                for key in ('p1', 'p3', 'p5'):
                    item[key] = statistics.mean(r[key] for r in answerable)
                for key in ('mrr', 'recall_at_5'):
                    item[key] = statistics.mean(r['metrics'][key] for r in answerable)
                item.update(selected_pool_recall=statistics.mean(r['selected_pool_recall'] for r in answerable),
                            selected_pool_hits=sum(len(r['selected_pool_hits']) for r in unique),
                            eligible_pool_hits=sum(len(r['eligible_pool_hits']) for r in unique),
                            incompatible_top5=sum(len(r['incompatible_returned']) for r in unique),
                            unknown_top5=sum(len(r['unjudged']) for r in unique),
                            noanswer_nonempty=sum(bool(r['top5']) for r in noanswer),
                            answerable_nonempty=sum(bool(r['top5']) for r in answerable))
                item['timing_ms'] = {key: {'p50': statistics.median(r['timing_ms'][key] for r in group),
                                          'p95': percentile([r['timing_ms'][key] for r in group], .95)} for key in group[0]['timing_ms']}
                item['citation_bytes_p50'] = statistics.median(r['citation_wire_bytes'] for r in group)
                summaries.append(item)
        report['summaries'] = summaries
        # Category breakdown makes the cross-language limitation visible without guessing language.
        delivery = []
        for r in stored:
            if r['block'] != 0:
                continue
            base = {'query': r['query'], 'evidence': r['snippets_sources']}
            mark = time.perf_counter()
            baseline_wire = json.dumps(base, ensure_ascii=False, separators=(',', ':')).encode()
            base_ms = (time.perf_counter() - mark) * 1000
            mark = time.perf_counter()
            compact = compact_delivery(r)
            compact_wire = json.dumps(compact, ensure_ascii=False, separators=(',', ':')).encode()
            compact_ms = (time.perf_counter() - mark) * 1000
            decoded = json.loads(compact_wire)
            for original, packed in zip(base['evidence'], decoded['evidence']):
                assert all(packed[k] == v for k, v in original.items() if k not in ('snippet', 'passage_id'))
                assert packed.get('passage_id', packed['parent_id']) == original['passage_id']
            delivery.append({'id': r['id'], 'variant': r['variant'],
                             'baseline_bytes': len(baseline_wire), 'compact_bytes': len(compact_wire),
                             'baseline_serialize_ms': base_ms, 'compact_pack_serialize_ms': compact_ms,
                             'full_evidence_citations_preserved': True, 'envelope': decoded})
        save(run / 'delivery-ablation.json', delivery)
        report['delivery'] = {'envelopes': len(delivery),
                              'baseline_bytes': sum(d['baseline_bytes'] for d in delivery),
                              'compact_bytes': sum(d['compact_bytes'] for d in delivery),
                              'baseline_serialize_p50_ms': statistics.median(d['baseline_serialize_ms'] for d in delivery),
                              'compact_pack_serialize_p50_ms': statistics.median(d['compact_pack_serialize_ms'] for d in delivery),
                              'full_evidence_citations_preserved': True, 'agent_mcp_calls_measured': False}
        report['category_p1'] = {variant: {cat: statistics.mean(r['p1'] for r in stored if r['block'] == 0 and r['variant'] == variant and r['category'] == cat)
                                          for cat in sorted({q['category'] for q in queries})} for variant in VARIANTS}
        paired.write_review(run, stored)
        paired.fresh_connection(server)
        save(run / 'telemetry.json', server.request('GET', '/telemetry?details_level=3'))
    except Exception as exc:
        save(run / 'failure.json', {'error': repr(exc)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = inputs == {name: sha(repo / name) for name in inputs}
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', server.port)) != 0
    assert json.loads((run / 'cleanup.json').read_bytes()) == report['cleanup']
    save(run / 'report.json', report)
    # Write a dedicated review: incumbent exporter uses unrelated primary-variant names.
    lines = ['# BM25 paired diagnostic — per-query review', '', freeze['labels'],
             'All branches gated; no threshold. Full excerpts, pool hits, raw scores, timings and citations: raw-results.json / per-query.csv.', '']
    for r in stored:
        if r['block'] != 0:
            continue
        lines += [f"## {r['id']} / {r['variant']}", r['query'],
                  f"Selected={r['relevant']}; pool hits={r['selected_pool_hits']}; eligible={r['eligible_pool_hits']}",
                  f"P1/P3/P5={r['p1']:.4f}/{r['p3']:.4f}/{r['p5']:.4f}; RR@5={r['metrics']['mrr']}; R5={r['metrics']['recall_at_5']}",
                  f"Incompatible={r['incompatible_returned']}; UNKNOWN={r['unjudged']}; {r['answerability']}",
                  f"Ranking={r['timing_ms']['ranking']:.3f}ms; E2E={r['timing_ms']['e2e']:.3f}ms", '']
        for i, s in enumerate(r['snippets_sources'], 1):
            lines += [f"{i}. **{s['parent_id']}** {s['status']}; [{s['source']}]({s['url']}); [{s['start']},{s['end']}); SHA256 {s['sha256']}",
                      '> ' + s['snippet'].replace('\n', '\n> '), '']
    (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    # Remove misleading unrelated incumbent primary-review output inside this owned run only.
    (run / 'PRIMARY-PAIRED-REVIEW.md').unlink()
    manifest = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', manifest)
    retained_manifest = json.loads((run / 'evidence-sha256.json').read_bytes())
    assert all(sha(run / name) == value for name, value in retained_manifest.items())
    print(json.dumps({'run': str(run), 'rows': len(rows), 'verified_manifest_entries': len(manifest), 'cleanup': report['cleanup']}), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    experiment(args.run or Path(__file__).resolve().parents[1] / 'artifacts/bm25-retrieval' / uuid.uuid4().hex)
