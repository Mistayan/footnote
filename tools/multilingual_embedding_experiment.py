"""Finite multilingual-model diagnostic. Public snapshot only; no runtime edits."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO / 'artifacts/multilingual-embeddings/sources-8f28a3576bc24f32a685ec765c8d3f93'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audited_recipe(model, identity):
    """Bind a locally pinned conversion to the fetched upstream card, not its name."""
    model = Path(model)
    manifest = json.loads((model / 'manifest.json').read_bytes())
    if any(manifest[k] != identity[k] for k in ('repository', 'revision')):
        raise ValueError('source identity mismatch')
    if len(manifest['revision']) != 40 or manifest['pooling'] != 'attention-mask-mean-l2':
        raise ValueError('unsupported recipe')
    for name, receipt in manifest['files'].items():
        if (model / name).is_symlink() or sha(model / name) != receipt['sha256']:
            raise ValueError('artifact hash mismatch: ' + name)
    return manifest | {'upstream': identity['upstream'],
                       'conversion_license': identity['license'] or 'NOT_DECLARED_IN_CONVERSION_CARD',
                       'manifest_sha256': sha(model / 'manifest.json')}


def verified_encoder(model, cap=None):
    """Use proven CPU helper without altering its files or default native recipe."""
    from technical_quality import ResidentEncoder
    encoder = ResidentEncoder(model)
    if cap is not None:
        if not 4 <= cap <= encoder.manifest['max_length']:
            raise ValueError('only shorter diagnostic caps allowed')
        encoder.manifest = encoder.manifest | {'max_length': cap}
        encoder.tokenizer.enable_truncation(max_length=cap)
    return encoder


def audit_query_vectors(run, rows, queries):
    """Bind every timed request to the actually saved per-model query vector."""
    import numpy as np
    indices = {q['id']: i for i, q in enumerate(queries)}
    matrices = {n: np.load(Path(run) / (n + '-query-vectors.npy')) for n in {r['variant'] for r in rows}}
    for r in rows:
        vector = matrices[r['variant']][indices[r['id']]]
        assert r['query_vector_sha256'] == hashlib.sha256(vector.tobytes()).hexdigest()
    return True


def verify_run(run):
    """Recompute evidence hashes, metrics, gates and source offsets."""
    import numpy as np
    import technical_quality as tq
    from retrieval_budget_benchmark import eligibility, present, select_candidates
    run = Path(run)
    load = lambda n: json.loads((run / n).read_bytes())
    for name, digest in load('evidence-sha256.json').items():
        assert sha(run / name) == digest, name
    freeze = load('freeze.json')
    assert all(sha(REPO / n) == h for n, h in freeze['inputs'].items())
    docs = {d['id']: d for d in load('corpus.json')}
    sources = load('source-receipts.json')
    queries = {q['id']: q for q in load('judgments.json')}
    rows, stable = load('raw-results.json'), {}
    assert audit_query_vectors(run, rows, list(queries.values()))
    assert len(rows) == len(queries) * len(freeze['variants']) * 4
    for r in rows:
        q = queries[r['id']]
        assert r['metrics'] == tq.score(r['top5'], q)
        states = eligibility(q['query'], docs, sources)
        assert r['pool20'] == tq.fuse(r['dense'], r['lexical'])[:20]
        assert r['candidates'] == select_candidates(r['pool20'], states, True, 20)
        assert r['top5'] == present(r['candidates'], states, True)
        for k in (1, 3, 5):
            assert r['p' + str(k)] == sum(n in q['relevant'] for n in r['top5'][:k]) / k
        key = (r['id'], r['variant'], r['mode'])
        if key in stable:
            assert stable[key] == r['top5']
        stable[key] = r['top5']
        for s in r['snippets_sources']:
            d = docs[s['parent_id']]
            text = (run / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
            assert s['text'] == text[d['start']:d['end']] == d['text']
            assert s['sha256'] == hashlib.sha256(s['text'].encode()).hexdigest()
        assert all(not states[n].startswith('REJECT') for n in r['candidates'] + r['top5'])
    for name in freeze['variants']:
        matrix = np.load(run / (name + '-vectors.npy'))
        back = load(name + '-readback.json')['points']
        assert len(back) == len(matrix)
        assert np.max(np.abs(np.asarray([p['vector'] for p in back]) - matrix)) < 1e-6
    assert load('cleanup.json')['process_exited'] and load('cleanup.json')['port_closed']
    return True


def experiment(run):
    """Freeze four variants before inference; measure actual paired requests."""
    import datetime
    import platform
    import shutil
    import statistics
    import sys
    import time
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import lexical_or
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    from server_benchmark import Server, SERVER, save, percentile
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/multilingual-embeddings') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('owned NEW non-symlink artifact directory required')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    frozen = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, digest in frozen['files'].items():
        assert sha(snapshot / name) == digest, name
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    identities = json.loads((SOURCE_DIR / 'identities.json').read_bytes())
    recipes = {n: audited_recipe(REPO / 'artifacts/models' / n, identities[k]) for n, k in [('minilm', 'minilm'), ('e5-small', 'e5')]}
    variants = ['minilm_parent128', 'e5_parent512', 'e5_parent128', 'minilm_child127']
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
              'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    inputs = [Path(__file__), REPO / 'tests/multilingual_embedding_experiment_test.py', SERVER,
              REPO / 'requirements-hybrid.lock', snapshot / 'freeze.json']
    inputs += [snapshot / n for n in frozen['files']] + list(SOURCE_DIR.glob('*'))
    history = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
    inputs += [history / n for n in ['freeze.json', 'original-vectors.npy', 'query-vectors.npy']]
    inputs += [REPO / 'tools' / n for n in ['technical_quality.py', 'qdrant_quality.py', 'server_benchmark.py', 'retrieval_ablation.py', 'retrieval_budget_benchmark.py', 'hybrid_dataset.py']]
    inputs += [REPO / 'artifacts/models' / n / f for n in recipes for f in ['manifest.json', 'model.onnx', 'tokenizer.json']]
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    for n in ['corpus.json', 'judgments.json', 'source-receipts.json']:
        shutil.copyfile(snapshot / n, run / n)
    (run / 'sources').mkdir()
    for n in sources:
        shutil.copyfile(snapshot / 'sources' / (n + '.txt'), run / 'sources' / (n + '.txt'))
    (run / 'code').mkdir()
    for p in inputs:
        if p.suffix == '.py':
            shutil.copyfile(p, run / 'code' / p.name)
    save(run / 'model-recipes.json', recipes)
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': before, 'recipes': recipes,
        'variants': variants, 'blocks': 2, 'modes': ['ann128', 'exact'], 'collection_config': config,
        'budgets': {'dense_points': 60, 'lexical_parents': 20, 'rrf_k': 60, 'pool': 20, 'present': 5},
        'method': 'Same parents/source text. Native E5_512 vs MiniLM_128 changes model AND native context, not pure weights. E5_128 is separately declared length-matched ablation. MiniLM_child127 is separate segmentation-only, source slices, no headings, max-child parent collapse, no refill. No labels in passage builder.',
        'gates': 'Existing raw-source Python-family gate AFTER pool20 before selection AND again at presentation. Unknown rejected on explicit versions, otherwise NOT_ASSESSED. No additional applicability inference.',
        'labels': 'REUSED DIAGNOSTIC; incomplete selected labels; UNKNOWN not wrong; no independent holdout and no 90% claim.',
        'reranker': 'NONE; no abstention, translation, query expansion or label-derived builder metadata',
        'timing': 'Independent query encode, HTTP, FTS5 OR, RRF, gates, citations and JSON each request. Two blocks, reverse query/variant/mode order in second. 600s deadline. Load/offline encoding excluded.',
        'downloads': 'No model download/dependency installation; existing pinned multilingual E5. Public metadata only. Conversion license not declared; upstream license recorded separately.'}
    save(run / 'freeze.json', freeze)  # Before encoder initialization or any inference.
    report = {'run': str(run), 'freeze_sha256': sha(run / 'freeze.json'), 'task_status': 'OPEN_PENDING_PARENT_VERIFICATION',
              'environment': {'python': sys.version, 'platform': platform.platform()}, 'summaries': []}
    documents = {d['id']: d for d in corpus}
    for d in corpus:
        text = (run / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']] == d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    start = time.perf_counter()
    mini = verified_encoder(REPO / 'artifacts/models/minilm')
    e5 = verified_encoder(REPO / 'artifacts/models/e5-small')
    short = verified_encoder(REPO / 'artifacts/models/e5-small', cap=128)
    encoders = dict(zip(variants, [mini, e5, short, mini]))
    report['load_validation_ms'] = (time.perf_counter() - start) * 1000
    report['environment'].update(mini.runtime)
    report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert freeze['utc'] <= report['first_inference_utc']
    children = tq.child_chunks(corpus, [mini])
    save(run / 'baseline-token-safe-children.json', children)
    layouts = {n: children if 'child' in n else corpus for n in variants}
    report.update(parent_count=len(corpus), child_count=len(children), query_count=len(queries), passage_encoding_ms={}, truncation={})
    vectors = {}
    for n in variants:
        enc, docs = encoders[n], layouts[n]
        start = time.perf_counter()
        vectors[n] = enc.encode([d['text'] for d in docs], 'passage')
        report['passage_encoding_ms'][n] = (time.perf_counter() - start) * 1000
        np.save(run / (n + '-vectors.npy'), vectors[n])
        visibility = []
        for d in docs:
            count = enc.token_count(d['text'], 'passage')
            limited = enc.tokenizer.encode(enc.manifest['passage_prefix'] + d['text'])
            end = max((b for a, b in limited.offsets), default=0) - len(enc.manifest['passage_prefix'])
            end = max(0, min(len(d['text']), end))
            visibility.append({'id': d['id'], 'tokens': count, 'truncated': count > enc.manifest['max_length'],
                'at_limit': count >= enc.manifest['max_length'], 'visible_end_relative': end, 'omitted_suffix': d['text'][end:]})
        counts = [{'id': q['id'], 'tokens': enc.token_count(q['query'], 'query')} for q in queries]
        report['truncation'][n] = {'passages': sum(v['truncated'] for v in visibility), 'passage_inputs': len(docs),
            'passages_at_limit': sum(v['at_limit'] for v in visibility), 'queries': sum(v['tokens'] > enc.manifest['max_length'] for v in counts),
            'query_inputs': len(queries), 'max_length': enc.manifest['max_length'], 'query_token_counts': counts}
        save(run / (n + '-visibility.json'), visibility)
    history = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
    report['historical_passage_vector_parity'] = bool(np.array_equal(vectors[variants[0]], np.load(history / 'original-vectors.npy')))
    assert report['historical_passage_vector_parity']
    server, db, rows = Server(run), tq.lexical_index(corpus), []
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        for n in variants:
            matrix, docs = vectors[n], layouts[n]
            server.request('PUT', '/collections/' + n, config)
            server.request('PUT', '/collections/' + n + '/points?wait=true', {'points': [
                {'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id'], 'parent_id': d.get('parent_id', d['id'])}}
                for i, (v, d) in enumerate(zip(matrix, docs))]})
            time.sleep(1)  # One finite optimizer allowance; no process polling loop.
            info = server.request('GET', '/collections/' + n)['result']
            assert info['status'] == 'green' and info['indexed_vectors_count'] == len(docs), info
            back = server.request('POST', '/collections/' + n + '/points', {'ids': list(range(1, len(docs) + 1)), 'with_vector': True, 'with_payload': True})['result']
            back.sort(key=lambda p: p['id'])
            error = float(np.max(np.abs(np.asarray([p['vector'] for p in back]) - matrix)))
            assert len(back) == len(docs) and error < 1e-6
            assert all(p['payload']['document_id'] == docs[i]['id'] for i, p in enumerate(back))
            save(run / (n + '-readback.json'), {'collection': info, 'points': back, 'max_abs_error': error})
        report['rss_before_measurement_bytes'] = {'harness': psutil.Process().memory_info().rss, 'server': psutil.Process(server.process.pid).memory_info().rss}
        for enc in [mini, e5, short]:
            enc.encode(['public technical retrieval warmup'], 'query')
        measurement, query_vectors = time.monotonic(), {}
        with (run / 'raw-results.jsonl').open('w', encoding='utf-8') as output:
            for block in range(2):
                for q in (queries if block == 0 else reversed(queries)):
                    for n in (variants if block == 0 else reversed(variants)):
                        for mode in (['ann128', 'exact'] if block == 0 else ['exact', 'ann128']):
                            if time.monotonic() - measurement > 600:
                                raise TimeoutError('600s measurement budget exceeded')
                            start = time.perf_counter()
                            vector = encoders[n].encode([q['query']], 'query')[0]
                            encoded = time.perf_counter()
                            response = server.request('POST', '/collections/' + n + '/points/query', {
                                'query': vector.tolist(), 'limit': 60, 'with_payload': True, 'with_vector': False,
                                'params': {'exact': mode == 'exact', 'hnsw_ef': 128}})
                            fetched = time.perf_counter()
                            dense = paired.rank_parents(response['result']['points'], layouts[n])
                            lexical = lexical_or(db, q['query'])
                            pool = tq.fuse(dense, lexical)[:20]
                            states = eligibility(q['query'], documents, sources)
                            candidates = select_candidates(pool, states, True, 20)
                            top5 = present(candidates, eligibility(q['query'], documents, sources), True)
                            row = paired.review_row(q, top5, n, mode, 'or_rrf_pool20_no_rerank', documents, corpus, sources)
                            row.update(block=block, pool20=pool, candidates=candidates, dense=dense, lexical=lexical, eligibility=states,
                                candidate_recall=len(set(pool) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None,
                                gated_candidate_recall=len(set(candidates) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None)
                            for s in row['snippets_sources']:
                                s['sha256'] = documents[s['parent_id']]['sha256']
                            wire = json.dumps(row, ensure_ascii=False).encode()
                            end = time.perf_counter()
                            row['timing_ms'] = {'encode': (encoded - start) * 1000, 'http': (fetched - encoded) * 1000,
                                'lexical_fusion_gate_citations_json': (end - fetched) * 1000, 'e2e': (end - start) * 1000}
                            row['citation_wire_bytes'] = len(wire)
                            row['query_vector_sha256'] = hashlib.sha256(vector.tobytes()).hexdigest()
                            row['server_response'] = response
                            key = (n, q['id'])
                            if key in query_vectors:
                                assert np.array_equal(vector, query_vectors[key])
                            query_vectors[key] = vector
                            rows.append(row)
                            output.write(json.dumps(row, ensure_ascii=False) + '\n')
                            output.flush()
                print(json.dumps({'block': block, 'rows': len(rows)}), flush=True)
        report['measurement_seconds'] = time.monotonic() - measurement
        report['rss_after_measurement_bytes'] = {'harness': psutil.Process().memory_info().rss, 'server': psutil.Process(server.process.pid).memory_info().rss}
        for n in variants:
            np.save(run / (n + '-query-vectors.npy'), np.stack([query_vectors[n, q['id']] for q in queries]))
        report['historical_query_vector_parity'] = bool(np.array_equal(np.stack([query_vectors[variants[0], q['id']] for q in queries]), np.load(history / 'query-vectors.npy')))
        assert report['historical_query_vector_parity']
        save(run / 'raw-results.json', rows)
        assert len(rows) == len(queries) * len(variants) * 4
        report['rows'] = len(rows)
        report['gate_violations'] = sum(r['eligibility'][n].startswith('REJECT') for r in rows for n in r['candidates'] + r['top5'])
        assert report['gate_violations'] == 0
        first = [r for r in rows if r['block'] == 0]
        for n in variants:
            for mode in ['ann128', 'exact']:
                for subset in ['all', 'development', 'holdout', 'fr_to_en', 'exact', 'no_answer']:
                    group = [r for r in first if r['variant'] == n and r['mode'] == mode and (subset == 'all' or r['split'] == subset or r['category'] == subset)]
                    yes = [r for r in group if r['relevant']]
                    times = [r['timing_ms']['e2e'] for r in rows if r['variant'] == n and r['mode'] == mode and r['id'] in {g['id'] for g in group}]
                    report['summaries'].append({'variant': n, 'mode': mode, 'subset': subset, 'queries': len(group), 'answerable': len(yes),
                        **{k: statistics.mean(r[k] for r in yes) if yes else None for k in ['p1', 'p3', 'p5', 'candidate_recall', 'gated_candidate_recall']},
                        **{k: statistics.mean(r['metrics'][k] for r in yes) if yes else None for k in ['mrr', 'recall_at_5']},
                        'incompatible_top1': sum(r['metrics']['incompatible_at_1'] for r in group),
                        'incompatible_top5': sum(len(r['incompatible_returned']) for r in group), 'unknown_top5': sum(len(r['unjudged']) for r in group),
                        'noanswer_queries': sum(not r['relevant'] for r in group), 'noanswer_false_accepts': sum(bool(r['top5']) for r in group if not r['relevant']),
                        'e2e_p50_ms': statistics.median(times), 'e2e_p95_ms': percentile(times, .95)})
        report['ann_exact_top5_parity'] = {n: sum(next(r['top5'] for r in first if r['id'] == q['id'] and r['variant'] == n and r['mode'] == 'ann128') == next(r['top5'] for r in first if r['id'] == q['id'] and r['variant'] == n and r['mode'] == 'exact') for q in queries) for n in variants}
        lines = ['# Frozen multilingual per-query reused diagnostic', '', 'UNKNOWN is unjudged, not irrelevant. Pk=selected hits/k; RR truncated at5. No-answer false acceptance means nonempty retrieval, not generated-answer error. No 90% claim.', '']
        changes = []
        for r in first:
            b = next(x for x in first if x['id'] == r['id'] and x['variant'] == variants[0] and x['mode'] == r['mode'])
            changes.append({'id': r['id'], 'variant': r['variant'], 'mode': r['mode'], 'category': r['category'], 'p1_delta': r['p1'] - b['p1'], 'p5_delta': r['p5'] - b['p5'], 'baseline_top5': b['top5'], 'top5': r['top5']})
            lines += [f"## {r['id']} / {r['variant']} / {r['mode']}", '', r['query'], '',
                f"Selected={r['relevant']}; incompatible={r['incompatible']}; category={r['category']}",
                f"P1/P3/P5={r['p1']:.4f}/{r['p3']:.4f}/{r['p5']:.4f}; MRR5={r['metrics']['mrr']}; R5={r['metrics']['recall_at_5']}; candidate recall={r['candidate_recall']}; noanswer FA={r['metrics']['no_answer_false_acceptance']}",
                'Repeated E2E ms=' + str([x['timing_ms']['e2e'] for x in rows if x['id'] == r['id'] and x['variant'] == r['variant'] and x['mode'] == r['mode']]), '']
            for i, s in enumerate(r['snippets_sources'], 1):
                lines += [f"{i}. **{s['parent_id']}** {s['status']} [{s['source']}]({s['url']}) offsets [{s['start']},{s['end']}) SHA256={s['sha256']}", '', '> ' + s['snippet'].replace('\n', '\n> '), '']
        save(run / 'paired-changes.json', changes)
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error), 'rows': len(rows)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = all(sha(REPO / n) == h for n, h in before.items())
        save(run / 'partial-report.json', report)
    assert report['inputs_stable'] and report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    save(run / 'report.json', report)
    save(run / 'evidence-sha256.json', {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()})
    assert verify_run(run)
    print(json.dumps({'run': str(run), 'rows': len(rows), 'cleanup': report['cleanup']}), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        print(verify_run(args.verify))
    else:
        experiment(args.run or REPO / 'artifacts/multilingual-embeddings' / ('paired-' + uuid.uuid4().hex))
