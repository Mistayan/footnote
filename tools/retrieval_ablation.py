"""Frozen public-corpus ablations; no production/vault integration."""
import re
import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse


class CrossEncoder:
    """Pinned public mMARCO ONNX logits; never interpreted as probabilities."""
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        receipt = json.loads((directory / 'receipt.json').read_bytes())
        if receipt['status'] != 'downloaded' or receipt['license'] != 'apache-2.0':
            raise ValueError('unqualified optional checkpoint')
        for name, item in receipt['files'].items():
            if hashlib.sha256((directory / name).read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('reranker hash mismatch: ' + name)
        self.receipt = receipt
        self.tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=512, strategy='longest_first')
        self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / 'model.onnx'), sess_options=options,
                                            providers=['CPUExecutionProvider'])
        self.at_limit = 0

    def rank(self, query, documents):
        import numpy as np
        scores = {}
        for offset in range(0, len(documents), 4):
            batch = documents[offset:offset + 4]
            tokens = self.tokenizer.encode_batch([(query, doc['text']) for doc in batch])
            ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
            mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
            self.at_limit += int((mask.sum(axis=1) >= 512).sum())
            inputs = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
            logits = self.session.run(None, {i.name: inputs[i.name] for i in self.session.get_inputs()})[0].reshape(-1)
            if len(logits) != len(batch) or not np.isfinite(logits).all():
                raise ValueError('invalid crossencoder output')
            scores.update({doc['id']: float(score) for doc, score in zip(batch, logits)})
        return sorted(scores, key=lambda name: (-scores[name], name)), scores


def technical_tokens(query):
    """Keep API underscores and dotted versions; no expansion or stopword tuning."""
    return list(dict.fromkeys(re.findall(r'\w+(?:\.\w+)*', query, flags=re.UNICODE)))


def lexical_or(db, query):
    """FTS5 BM25 OR terms, identifiers remain literal phrases, limit20."""
    terms = technical_tokens(query)
    if not terms:
        return []
    expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
    return [r[0] for r in db.execute(
        'SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents), id LIMIT 20',
        (expression,))]


def source_metadata(source):
    """A documentation revision is NOT a product compatibility declaration."""
    url = source['url']
    path = urlparse(url).path
    python = re.fullmatch(r'/python/cpython/v(\d+\.\d+\.\d+)/Doc/.+', path)
    pinned = re.fullmatch(r'/[^/]+/[^/]+/([0-9a-f]{40})/.+', path)
    trusted = urlparse(url).netloc == 'raw.githubusercontent.com'
    return {'version': python[1] if trusted and python else 'UNKNOWN',
            'revision': pinned[1] if trusted and pinned else 'UNKNOWN',
            'product': 'Python' if trusted and python else 'UNKNOWN',
            'compatibility': 'UNKNOWN; no inferred cross-version compatibility'}


def admissibility(query, metadata):
    """Narrow Python version-family gate, not an API compatibility oracle."""
    request = re.search(r'\bPython\s+(\d+\.\d+(?:\.\d+)?)\b', query, re.I)
    if not request:
        return 'NOT_ASSESSED'
    if metadata['version'] == 'UNKNOWN' or metadata['product'] != 'Python':
        return 'REJECT_UNKNOWN'
    requested = request[1]
    return ('MATCH_EXPLICIT_FAMILY' if metadata['version'] == requested or
            metadata['version'].startswith(requested + '.') else 'REJECT_VERSION')


def source_title(text):
    """Extract source-level headings identically for selected and unjudged windows."""
    yaml_title = re.search(r'^title:\s*(.+)$', text[:2000], re.M)
    if text.startswith('---\n') and yaml_title:
        return yaml_title[1].strip().strip('"')
    rst_title = re.search(r'^([^\n]+)\n[=]{4,}\s*$', text[:2000], re.M)
    if rst_title:
        return rst_title[1].strip()
    if ' Small. Fast. Reliable.' in text[:300]:
        return text.split(' Small. Fast. Reliable.', 1)[0]
    return 'UNKNOWN'


def context_text(doc, source):
    metadata = source_metadata(source)
    return (f"Title: {source.get('title', 'UNKNOWN')}\nSource: {source['url']}\n"
            f"Version: {metadata['version']}\nRevision: {metadata['revision']}\n\n{doc['text']}")


def experiment(run, reranker_directory=None):
    """Freeze isolated effects before inference, then exercise real Qdrant paths."""
    import csv
    import datetime
    import platform
    import socket
    import sqlite3
    import statistics
    import sys
    import time
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from server_benchmark import Server, SERVER, ResourceSampler, sha, save, percentile

    repo = Path(__file__).resolve().parents[1]
    run = Path(run).resolve()
    if not run.is_relative_to(repo / 'artifacts/retrieval-ablations'):
        raise ValueError('run must be a NEW project-local retrieval-ablations directory')
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('run must not traverse symlinks')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    historical = repo / 'artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d'
    old_freeze = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, expected in old_freeze['files'].items():
        if sha(snapshot / name) != expected:
            raise ValueError('snapshot changed: ' + name)
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    for name, source in sources.items():
        text = (snapshot / 'sources' / (name + '.txt')).read_text(encoding='utf-8')
        source['title'] = source_title(text)
        source['title_provenance'] = {'normalized_text_sha256': tq.digest(text.encode()),
                                     'start': text.find(source['title']),
                                     'end': text.find(source['title']) + len(source['title'])}
    metadata = {name: source_metadata(source) for name, source in sources.items()}
    documents = {doc['id']: doc for doc in corpus}
    for doc in corpus:
        normalized = (snapshot / 'sources' / (doc['source'] + '.txt')).read_text(encoding='utf-8')
        assert normalized[doc['start']:doc['end']] == doc['text']
        assert tq.digest(doc['text'].encode()) == doc['sha256']
    texts = {'original': [d['text'] for d in corpus],
             'context': [context_text(d, sources[d['source']]) for d in corpus]}
    variants = ['dense', 'baseline_and_rrf', 'context_dense', 'context_and_rrf',
                'lexical_and', 'lexical_or', 'or_rrf', 'version_gate_baseline',
                'version_gate_or_rrf', 'rerank_control_pool20']
    report = {'run': str(run), 'blockers': [], 'query_count': len(queries),
              'status': 'REUSED DIAGNOSTIC ONLY; incomplete judgments; no 90% or bank qualification claim'}
    start = time.perf_counter()
    encoder = tq.ResidentEncoder(repo / 'artifacts/models/minilm')
    report['minilm_load_validate_ms'] = (time.perf_counter() - start) * 1000
    reranker = None
    if reranker_directory:
        start = time.perf_counter()
        try:
            reranker = CrossEncoder(Path(reranker_directory))
            variants.append('rerank_pool20')
            report['reranker_receipt'] = reranker.receipt
        except Exception as error:
            report['blockers'].append('optional reranker load: ' + repr(error))
        report['reranker_load_validate_ms'] = (time.perf_counter() - start) * 1000
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False},
              'shard_number': 1, 'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    inputs = [Path(__file__), repo / 'tests/retrieval_ablation_test.py',
              repo / 'tools/technical_quality.py', repo / 'tools/qdrant_quality.py',
              repo / 'tools/server_benchmark.py', repo / 'tools/hybrid_dataset.py',
              repo / 'requirements-hybrid.lock', SERVER, snapshot / 'freeze.json',
              historical / 'raw-results.json', historical / 'minilm-query-vectors.npy',
              historical / 'parent-minilm-passage-vectors.npy']
    inputs += [snapshot / name for name in old_freeze['files']]
    inputs += [repo / 'artifacts/models/minilm' / name for name in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    if reranker:
        inputs += [Path(reranker_directory) / name for name in reranker.receipt['files']]
        inputs.append(Path(reranker_directory) / 'receipt.json')
    before = {p.relative_to(repo).as_posix(): sha(p) for p in inputs}
    for name, data in [('corpus.json', corpus), ('judgments.json', queries),
                       ('source-receipts.json', sources), ('metadata.json', metadata), ('encoded-texts.json', texts)]:
        save(run / name, data)
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'before_inference': True,
              'inputs': before, 'variants': variants, 'seed': 0, 'model_manifest': encoder.manifest,
              'modes': [('exact', True), ('ann128', False)], 'collection_config': config,
              'holdout': 'REUSED DIAGNOSTIC; no independence or statistical winner selection',
              'units': 'unchanged parent passage IDs and source offsets; no chunk boundary/expansion changes',
              'budgets': {'dense': 60, 'lexical': 20, 'presented': 5, 'reranker_pairs': 20},
              'ranking': 'score-desc ID-asc, equal RRF k60; baseline FTS5 whitespace literal AND vs OR technical tokens; no stopword tuning',
              'context_effect': 'only deterministic source-level title/source URL/explicit pinned version/revision prefix; titles extracted uniformly from pinned source text with offsets, never selected evidence anchor; no generated context',
              'applicability': 'Python explicit version requests only; strict source family match, reject known different and UNKNOWN; all other requests NOT_ASSESSED. Apply to both branches BEFORE fusion, no candidate refill. No compatibility inference.',
              'reranker': 'optional mMARCO quantized AVX2 ONNX logits longest-first max512; same ungated OR-RRF pool top20 as control; original evidence; no sigmoid/confidence',
              'abstention': 'NONE: nonempty retrieval = candidate false acceptance for no-answer, NOT generated answer',
              'labels': 'selected positives and explicit incompatibilities incomplete; others UNKNOWN not false; Pk = positive labels/k',
              'artifact_inputs': {p.name: sha(p) for p in run.iterdir() if p.is_file()}}
    save(run / 'freeze.json', freeze)  # MUST precede all embedding/reranking inference.
    report.update(variants=variants, freeze_sha256=sha(run / 'freeze.json'),
                  environment={'python': sys.version, 'platform': platform.platform(),
                               'processor': platform.processor(), 'cpu_logical': psutil.cpu_count(),
                               'cpu_physical': psutil.cpu_count(logical=False),
                               'memory_bytes': psutil.virtual_memory().total,
                               'sqlite': sqlite3.sqlite_version, **encoder.runtime},
                  timing_contract='Resident component-attributed pipeline sum, NOT independent end-to-end latency. Shared single query encode and lexical measurement reused across variants/modes. One sequential diagnostic pass, no calibrated timing significance.')
    np.random.seed(0)
    server = Server(run)
    db = tq.lexical_index(corpus)
    rows, raw = [], []
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc'] <= report['first_inference_utc']
        with ResourceSampler(server) as sampler:
            qvectors, qtimes = [], []
            for query in queries:
                start = time.perf_counter()
                qvectors.append(encoder.encode([query['query']], 'query')[0])
                qtimes.append((time.perf_counter() - start) * 1000)
            qvectors = np.asarray(qvectors)
            np.save(run / 'query-vectors.npy', qvectors)
            report['baseline_query_vectors_equal'] = bool(np.array_equal(qvectors, np.load(historical / 'minilm-query-vectors.npy')))
            assert report['baseline_query_vectors_equal']
            report['collections'], report['offline'] = [], []
            for layout, encoded_texts in texts.items():
                start = time.perf_counter()
                vectors = encoder.encode(encoded_texts, 'passage')
                encode_ms = (time.perf_counter() - start) * 1000
                np.save(run / (layout + '-vectors.npy'), vectors)
                if layout == 'original':
                    report['baseline_passage_vectors_equal'] = bool(np.array_equal(vectors, np.load(historical / 'parent-minilm-passage-vectors.npy')))
                    assert report['baseline_passage_vectors_equal']
                counts = [encoder.token_count(t, 'passage') for t in encoded_texts]
                report['offline'].append({'layout': layout, 'encode_ms': encode_ms,
                                          'token_counts': counts, 'at_or_above_cap': sum(c >= 128 for c in counts)})
                paired.fresh_connection(server)
                server.request('PUT', '/collections/' + layout, config)
                server.request('PUT', '/collections/' + layout + '/points?wait=true', {'points': [
                    {'id': i + 1, 'vector': vectors[i].tolist(), 'payload': {'document_id': d['id']}}
                    for i, d in enumerate(corpus)]})
                deadline = time.monotonic() + 120
                while True:
                    collection = server.request('GET', '/collections/' + layout)['result']
                    if collection['status'] == 'green' and collection['indexed_vectors_count'] == len(corpus):
                        break
                    if time.monotonic() > deadline:
                        raise TimeoutError('HNSW index incomplete')
                    time.sleep(.2)
                report['collections'].append(dict(layout=layout, **collection))
                readback = server.request('POST', '/collections/' + layout + '/points',
                    {'ids': list(range(1, len(corpus) + 1)), 'with_vector': True, 'with_payload': True})['result']
                readback.sort(key=lambda p: p['id'])
                assert len(readback) == len(corpus)
                assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(readback))
                error = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - vectors)))
                assert error < 1e-6
                save(run / (layout + '-readback.json'), {'max_abs_error': error, 'points': readback})
            # Explicit warm-up, outside query stage measurements.
            encoder.encode([queries[0]['query']], 'query')
            if reranker:
                reranker.rank(queries[0]['query'], corpus[:2])
            paired.fresh_connection(server)
            for qi, query in enumerate(queries):
                lex, lex_ms = {}, {}
                for name, search in [('and', tq.lexical_search), ('or', lexical_or)]:
                    start = time.perf_counter()
                    lex[name] = search(db, query['query'])
                    lex_ms[name] = (time.perf_counter() - start) * 1000
                eligibility = {d['id']: admissibility(query['query'], metadata[d['source']]) for d in corpus}
                for mode, exact in [('exact', True), ('ann128', False)]:
                    dense, backend_ms, responses = {}, {}, {}
                    for layout in texts:
                        start = time.perf_counter()
                        response = server.request('POST', '/collections/' + layout + '/points/query', {
                            'query': qvectors[qi].tolist(), 'limit': 60, 'with_payload': True,
                            'with_vector': False, 'params': {'exact': exact, 'hnsw_ef': 128}})
                        backend_ms[layout] = (time.perf_counter() - start) * 1000
                        dense[layout] = paired.rank_parents(response['result']['points'], corpus)
                        responses[layout] = response
                    raw.append({'query_id': query['id'], 'mode': mode, 'responses': responses,
                                'dense': dense, 'lexical': lex, 'eligibility': eligibility,
                                'query_vector_sha256': tq.digest(qvectors[qi].tobytes())})
                    for variant in variants:
                        layout = 'context' if variant.startswith('context') else 'original'
                        lexical_kind = 'or' if variant in ('lexical_or', 'or_rrf', 'version_gate_or_rrf',
                                                          'rerank_control_pool20', 'rerank_pool20') else 'and'
                        sem, lexical = dense[layout], lex[lexical_kind]
                        start = time.perf_counter()
                        if variant.startswith('version_gate'):
                            sem = [n for n in sem if not eligibility[n].startswith('REJECT')]
                            lexical = [n for n in lexical if not eligibility[n].startswith('REJECT')]
                        filter_ms = (time.perf_counter() - start) * 1000
                        start = time.perf_counter()
                        if variant in ('dense', 'context_dense'):
                            ids = sem
                        elif variant.startswith('lexical_'):
                            ids = lexical
                        else:
                            ids = tq.fuse(sem, lexical)
                        fusion_ms = (time.perf_counter() - start) * 1000
                        pool = ids[:20]
                        candidate_recall = len(set(pool) & set(query['relevant'])) / len(query['relevant']) if query['relevant'] else None
                        scores, rerank_ms = {}, 0.0
                        if variant == 'rerank_control_pool20':
                            ids = pool
                        elif variant == 'rerank_pool20':
                            start = time.perf_counter()
                            ids, scores = reranker.rank(query['query'], [documents[n] for n in pool])
                            rerank_ms = (time.perf_counter() - start) * 1000
                        start = time.perf_counter()
                        row = paired.review_row(query, ids[:5], variant, mode, variant, documents, corpus, sources)
                        row.update(pool20=pool, candidate_recall20=candidate_recall, reranker_logits=scores,
                                   eligibility=eligibility,
                                   selected_label_note='UNKNOWN is not false; incomplete labels; REUSED DIAGNOSTIC')
                        for snippet in row['snippets_sources']:
                            snippet['metadata'] = metadata[snippet['source']]
                            snippet['sha256'] = documents[snippet['parent_id']]['sha256']
                        json.dumps(row, ensure_ascii=False)
                        hydrate_ms = (time.perf_counter() - start) * 1000
                        is_lexical = variant.startswith('lexical_')
                        is_dense = variant in ('dense', 'context_dense')
                        timing = {'query_encode': 0.0 if is_lexical else qtimes[qi],
                                  'backend_roundtrip': 0.0 if is_lexical else backend_ms[layout],
                                  'lexical': 0.0 if is_dense else lex_ms[lexical_kind],
                                  'filter': filter_ms, 'fusion': fusion_ms, 'rerank': rerank_ms,
                                  'hydrate_serialize': hydrate_ms}
                        timing['attributed_pipeline'] = sum(timing.values())
                        row['timing_ms'] = timing
                        rows.append(row)
                save(run / 'raw-results.json', rows)
                save(run / 'raw-server-rankings.json', raw)
        report['resources'] = sampler.report
        save(run / 'resource-samples.json', sampler.rows)
        report['rows'] = len(rows)
        report['summaries'] = []
        for variant in variants:
            for mode in ('exact', 'ann128'):
                for split in ('development', 'holdout'):
                    group = [r for r in rows if (r['variant'], r['mode'], r['split']) == (variant, mode, split)]
                    answerable = [r for r in group if r['relevant']]
                    summary = {'variant': variant, 'mode': mode, 'split': split,
                               'queries': len(group), 'answerable_count': len(answerable),
                               **tq.summarize(group)}
                    for key in ('p1', 'p3', 'p5'):
                        summary[key] = statistics.mean(r[key] for r in answerable)
                    summary['no_answer_candidate_false_acceptance_count'] = sum(r['metrics']['no_answer_false_acceptance'] or 0 for r in group)
                    summary['explicit_incompatible_top5_count'] = sum(len(r['incompatible_returned']) for r in group)
                    summary['unknown_top5_count'] = sum(len(r['unjudged']) for r in group)
                    summary['empty_lexical_count'] = sum(not item['lexical']['or' if variant in ('or_rrf', 'lexical_or', 'version_gate_or_rrf', 'rerank_pool20', 'rerank_control_pool20') else 'and'] for item in raw if item['mode'] == mode and item['query_id'] in {q['id'] for q in group})
                    for stage in rows[0]['timing_ms']:
                        values = [r['timing_ms'][stage] for r in group]
                        summary[stage + '_p50_ms'] = statistics.median(values)
                        summary[stage + '_p95_ms'] = percentile(values, .95)
                    report['summaries'].append(summary)
        previous = json.loads((historical / 'raw-results.json').read_bytes())
        old_baseline = {r['id']: r for r in previous if r['variant'] == 'parent-minilm' and r['mode'] == 'ann128' and r['ranking'] == 'hybrid'}
        baseline = [r for r in rows if r['variant'] == 'baseline_and_rrf' and r['mode'] == 'ann128']
        report['baseline_top5_parity'] = sum(r['top5'] == old_baseline[r['id']]['top5'] for r in baseline)
        assert report['baseline_top5_parity'] == len(queries)
        report['exact_ann_ordered_top5_equal'] = sum(
            r['top5'] == next(other['top5'] for other in rows if other['id'] == r['id'] and other['variant'] == r['variant'] and other['mode'] == 'exact')
            for r in rows if r['mode'] == 'ann128')
        report['encoder_at_limit'] = encoder.truncated
        report['reranker_at_limit'] = reranker.at_limit if reranker else None
        paired.fresh_connection(server)
        save(run / 'telemetry.json', server.request('GET', '/telemetry?details_level=3'))
        fields = ['id', 'query', 'split', 'variant', 'mode', 'p1', 'p3', 'p5', 'metrics',
                  'top5', 'hits', 'incompatible_returned', 'unjudged', 'pool20', 'candidate_recall20',
                  'eligibility', 'timing_ms', 'snippets_sources']
        with (run / 'per-query.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], (list, dict)) else row[k] for k in fields})
        lines = ['# REUSED DIAGNOSTIC per-query review', '',
                 'Incomplete selected labels; UNKNOWN is not false. P@k = positive labels/k, not exhaustive semantic precision. MRR is reciprocal rank, not correctness probability.',
                 'Full original passage bytes, provenance, offsets, hashes, pools, logits and timings: raw-results.json / per-query.csv. No answer generation or calibrated abstention. No 90%/bank qualification.', '']
        for row in rows:
            lines += [f"## {row['variant']} / {row['mode']} / {row['id']}", '', row['query'], '',
                      f"Selected relevant: {row['relevant']}; incompatible labels: {row['incompatible']}",
                      f"P1/P3/P5={row['p1']:.4f}/{row['p3']:.4f}/{row['p5']:.4f}; RR={row['metrics']['mrr']}; recall5={row['metrics']['recall_at_5']}",
                      f"{row['answerability']}; returned incompatibles={row['incompatible_returned']}; UNKNOWN={row['unjudged']}", '']
            for rank, snippet in enumerate(row['snippets_sources'], 1):
                lines += [f"{rank}. {snippet['parent_id']} — {snippet['status']} — [{snippet['source']}]({snippet['url']}) [{snippet['start']},{snippet['end']}); SHA256 {snippet['sha256']}; version={snippet['metadata']['version']}",
                          '', '> ' + snippet['snippet'].replace('\n', '\n> '), '']
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = before == {name: sha(repo / name) for name in before}
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert json.loads((run / 'cleanup.json').read_bytes()) == report['cleanup']
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', server.port)) != 0
    report['manifest_verified'] = True
    save(run / 'report.json', report)
    receipt = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', receipt)
    assert all(sha(run / name) == expected for name, expected in receipt.items())
    print(json.dumps({'run': str(run), 'rows': len(rows), 'report_sha256': sha(run / 'report.json'),
                      'cleanup': report['cleanup']}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--reranker', type=Path, help='Optional existing bounded checkpoint receipt directory; no auto-download')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'artifacts/retrieval-ablations'
    experiment(args.run or root / uuid.uuid4().hex, args.reranker)
