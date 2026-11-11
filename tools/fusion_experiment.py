"""Frozen fixed-weight fusion diagnostics, public snapshot only, never runtime."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HISTORY = REPO / 'artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4'
BRANCHES = {'equal': (1, 1), 'dense2': (2, 1), 'lexical2': (1, 2), 'dense_only': (1, 0)}
MODELS = {'minilm_parent128': ('minilm', 128), 'e5_parent128': ('e5-small', 128), 'e5_parent512': ('e5-small', 512)}


def rank_fusion(dense, lexical, branch):
    """Fixed k60 rank-based scores, not probabilities; absent branch adds zero."""
    if branch not in BRANCHES:
        raise ValueError('branch not prespecified')
    evidence = {}
    for kind, names, weight, cap in [('dense', dense, BRANCHES[branch][0], 60), ('lexical', lexical, BRANCHES[branch][1], 20)]:
        if not weight:
            continue
        for rank, name in enumerate(names[:cap], 1):
            row = evidence.setdefault(name, {'dense_rank': None, 'lexical_rank': None, 'dense_score': 0., 'lexical_score': 0., 'score': 0.})
            row[kind + '_rank'] = rank
            row[kind + '_score'] = weight / (60 + rank)
            row['score'] += weight / (60 + rank)
    return sorted(evidence, key=lambda n: (-evidence[n]['score'], n)), evidence


def verify_run(run):
    """Replay fixed ranking/gates, vector identity, original source bytes and cleanup."""
    import numpy as np
    import technical_quality as tq
    from multilingual_embedding_experiment import sha, audit_query_vectors
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    from qdrant_quality import rank_parents
    run = Path(run)
    load = lambda name: json.loads((run / name).read_bytes())
    for name, digest in load('evidence-sha256.json').items():
        assert sha(run / name) == digest, name
    freeze = load('freeze.json')
    assert freeze['branches'] == {k: list(v) for k, v in BRANCHES.items()}
    assert all(sha(REPO / p) == h for p, h in freeze['inputs'].items())
    corpus, queries, sources = load('corpus.json'), load('judgments.json'), load('source-receipts.json')
    documents = {d['id']: d for d in corpus}
    for d in corpus:
        text = (run / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']] == d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    rows = load('raw-results.json')
    expected = {(q['id'], n, branch, block) for q in queries for n in MODELS for branch in BRANCHES for block in range(2)}
    assert len(rows) == len(expected) == 768
    assert {(r['id'], r['variant'], r['branch'], r['block']) for r in rows} == expected
    assert audit_query_vectors(run, rows, queries)
    judgments = {q['id']: q for q in queries}
    stable, shared = {}, {}
    for row in rows:
        q = judgments[row['id']]
        assert row['dense'] == rank_parents(row['server_response']['result']['points'], corpus)
        order, scores = rank_fusion(row['dense'], row['lexical'], row['branch'])
        assert row['fusion_evidence'] == scores
        assert row['pool20'] == order[:20]
        states = eligibility(q['query'], documents, sources)
        assert row['eligibility'] == states
        assert row['candidates'] == select_candidates(order[:20], states, True, 20)
        assert row['top5'] == present(row['candidates'], states, True)
        assert row['metrics'] == tq.score(row['top5'], q)
        from qdrant_quality import review_row
        reviewed = review_row(q, row['top5'], row['variant'], row['mode'], row['branch'], documents, corpus, sources)
        for s in reviewed['snippets_sources']:
            s['sha256'] = documents[s['parent_id']]['sha256']
        assert all(row[k] == value for k, value in reviewed.items())
        for k in [1, 3, 5]:
            assert row['p' + str(k)] == sum(n in q['relevant'] for n in row['top5'][:k]) / k
        recall = lambda names: len(set(names) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None
        assert row['candidate_recall'] == recall(row['pool20'])
        assert row['gated_candidate_recall'] == recall(row['candidates'])
        key = (row['id'], row['variant'], row['branch'])
        assert key not in stable or stable[key] == row['top5']
        stable[key] = row['top5']
        key = (row['id'], row['variant'])
        ranks = (row['dense'], row['lexical'])
        assert key not in shared or shared[key] == ranks
        shared[key] = ranks
        for s in row['snippets_sources']:
            d = documents[s['parent_id']]
            assert s['text'] == d['text'] and s['sha256'] == d['sha256']
            assert (s['start'], s['end'], s['source']) == (d['start'], d['end'], d['source'])
        assert all(not states[n].startswith('REJECT') for n in row['candidates'] + row['top5'])
    for n in MODELS:
        matrix = np.load(run / (n + '-vectors.npy'))
        assert np.array_equal(matrix, np.load(HISTORY / (n + '-vectors.npy')))
        back = load(n + '-readback.json')['points']
        assert len(back) == len(corpus)
        assert np.max(np.abs(np.asarray([p['vector'] for p in back]) - matrix)) < 1e-6
        assert all(p['payload'] == {'document_id': corpus[i]['id'], 'parent_id': corpus[i]['id']} for i, p in enumerate(back))
    cleanup = load('cleanup.json')
    assert cleanup['process_exited'] and cleanup['port_closed']
    return True


def experiment(run):
    """Fixed four-branch, three-model, two-block resident ANN diagnostic."""
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
    from multilingual_embedding_experiment import verified_encoder, sha
    from retrieval_ablation import lexical_or
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    from server_benchmark import Server, SERVER, save, percentile
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/fusion-experiments') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('owned NEW non-symlink artifact directory required')
    run.mkdir(parents=True, exist_ok=False)
    old_hashes = json.loads((HISTORY / 'evidence-sha256.json').read_bytes())
    for name, digest in old_hashes.items():
        assert sha(HISTORY / name) == digest, name
    load = lambda name: json.loads((HISTORY / name).read_bytes())
    corpus, queries, sources = load('corpus.json'), load('judgments.json'), load('source-receipts.json')
    assert len(corpus) == 136 and len(queries) == 32
    config = load('freeze.json')['collection_config']
    inputs = [Path(__file__), REPO / 'tests/fusion_experiment_test.py', SERVER, REPO / 'requirements-hybrid.lock']
    inputs += [REPO / 'tools' / n for n in ['technical_quality.py', 'qdrant_quality.py', 'multilingual_embedding_experiment.py', 'retrieval_ablation.py', 'retrieval_budget_benchmark.py', 'server_benchmark.py', 'hybrid_dataset.py']]
    inputs += [HISTORY / n for n in old_hashes] + [HISTORY / 'evidence-sha256.json']
    inputs += [REPO / 'artifacts/models' / n / p for n in ['minilm', 'e5-small'] for p in ['manifest.json', 'model.onnx', 'tokenizer.json']]
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    for name in ['corpus.json', 'judgments.json', 'source-receipts.json', 'model-recipes.json']:
        shutil.copyfile(HISTORY / name, run / name)
    shutil.copytree(HISTORY / 'sources', run / 'sources')
    (run / 'code').mkdir()
    for p in inputs:
        if p.suffix == '.py' and p.parent == REPO / 'tools':
            shutil.copyfile(p, run / 'code' / p.name)
    shutil.copyfile(REPO / 'tests/fusion_experiment_test.py', run / 'code/fusion_experiment_test.py')
    french = ['development-01', 'development-05', 'development-07', 'development-10', 'development-11', 'holdout-00', 'holdout-02', 'holdout-07', 'holdout-09']
    subsets = {'all': [q['id'] for q in queries], 'fr': french,
        'en': [q['id'] for q in queries if q['relevant'] and q['id'] not in french],
        'fr_to_en': [q['id'] for q in queries if q['category'] == 'fr_to_en'],
        'technical_negation': ['development-01', 'holdout-00', 'holdout-09'],
        'operators': ['development-02', 'development-06', 'holdout-08', 'holdout-09'],
        'exact': [q['id'] for q in queries if q['category'] == 'exact']}
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': before,
        'branches': BRANCHES, 'models': MODELS, 'blocks': 2, 'modes': ['ann128'], 'subsets': subsets,
        'collection_config': config, 'budgets': {'dense': 60, 'lexical': 20, 'rrf_k': 60, 'pool': 20, 'present': 5},
        'ranking': 'weighted sum w/(60+rank), absent branch zero; ID ascending ties. No thresholds. dense_only excludes lexical candidates.',
        'protocol': 'Same original parent bodies, FTS5 OR, raw-source version gate after pool and independently at presentation; no changed labels or metadata. Reverse query/model/branch order block2. Each branch independently encodes each request.',
        'labels': 'REUSED 32 diagnostics; incomplete selected labels; UNKNOWN not irrelevant; no independent holdout or 90% claim.',
        'scope': 'No reranker, heuristics, model download, dependency install, runtime edits or activation. First pass only; bounded fusion attribution, no posthoc winner.',
        'deadline_seconds': 600, 'goal': 'personal agent KB replacement within 1-2 months; not enterprise certification'}
    save(run / 'freeze.json', freeze)  # Code-order boundary BEFORE any encoder/session/inference.
    report = {'run': str(run), 'task_status': 'OPEN_PENDING_PARENT_VERIFICATION', 'freeze_sha256': sha(run / 'freeze.json'),
        'parent_count': len(corpus), 'query_count': len(queries), 'environment': {'python': sys.version, 'platform': platform.platform()},
        'summaries': [], 'passage_encoding_ms': {}, 'truncation': {}}
    documents = {d['id']: d for d in corpus}
    for d in corpus:
        text = (run / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']] == d['text'] and hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    start = time.perf_counter()
    encoders = {n: verified_encoder(REPO / 'artifacts/models' / model, cap=cap) for n, (model, cap) in MODELS.items()}
    report['load_validation_ms'] = (time.perf_counter() - start) * 1000
    report['environment'].update(next(iter(encoders.values())).runtime)
    report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert freeze['utc'] <= report['first_inference_utc']
    vectors = {}
    for n, encoder in encoders.items():
        start = time.perf_counter()
        vectors[n] = encoder.encode([d['text'] for d in corpus], 'passage')
        report['passage_encoding_ms'][n] = (time.perf_counter() - start) * 1000
        assert np.array_equal(vectors[n], np.load(HISTORY / (n + '-vectors.npy')))
        np.save(run / (n + '-vectors.npy'), vectors[n])
        visibility = []
        for d in corpus:
            count = encoder.token_count(d['text'], 'passage')
            limited = encoder.tokenizer.encode(encoder.manifest['passage_prefix'] + d['text'])
            end = max(0, min(len(d['text']), max((b for a, b in limited.offsets), default=0) - len(encoder.manifest['passage_prefix'])))
            visibility.append({'id': d['id'], 'tokens': count, 'truncated': count > encoder.manifest['max_length'], 'visible_end_relative': end, 'omitted_suffix': d['text'][end:]})
        save(run / (n + '-visibility.json'), visibility)
        report['truncation'][n] = {'passages': sum(d['truncated'] for d in visibility), 'max_length': encoder.manifest['max_length'], 'query_tokens': {q['id']: encoder.token_count(q['query'], 'query') for q in queries}}
    server, db, rows = Server(run), tq.lexical_index(corpus), []
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        for n, matrix in vectors.items():
            server.request('PUT', '/collections/' + n, config)
            server.request('PUT', '/collections/' + n + '/points?wait=true', {'points': [{'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id'], 'parent_id': d['id']}} for i, (v, d) in enumerate(zip(matrix, corpus))]})
            time.sleep(1)
            info = server.request('GET', '/collections/' + n)['result']
            assert info['status'] == 'green' and info['indexed_vectors_count'] == len(corpus), info
            back = server.request('POST', '/collections/' + n + '/points', {'ids': list(range(1, len(corpus) + 1)), 'with_vector': True, 'with_payload': True})['result']
            back.sort(key=lambda p: p['id'])
            error = float(np.max(np.abs(np.asarray([p['vector'] for p in back]) - matrix)))
            assert len(back) == len(corpus) and error < 1e-6
            assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(back))
            save(run / (n + '-readback.json'), {'collection': info, 'points': back, 'max_abs_error': error})
        report['rss_before_bytes'] = {'harness': psutil.Process().memory_info().rss, 'server': psutil.Process(server.process.pid).memory_info().rss}
        for enc in encoders.values():
            enc.encode(['public technical retrieval warmup'], 'query')
        measurement, query_vectors = time.monotonic(), {}
        with (run / 'raw-results.jsonl').open('w', encoding='utf-8') as output:
            for block in range(2):
                for q in (queries if block == 0 else reversed(queries)):
                    for n in (list(MODELS) if block == 0 else reversed(MODELS)):
                        for branch in (list(BRANCHES) if block == 0 else reversed(BRANCHES)):
                            if time.monotonic() - measurement > 600:
                                raise TimeoutError('measurement budget exhausted')
                            start = time.perf_counter()
                            vector = encoders[n].encode([q['query']], 'query')[0]
                            encoded = time.perf_counter()
                            response = server.request('POST', '/collections/' + n + '/points/query', {'query': vector.tolist(), 'limit': 60, 'with_payload': True, 'with_vector': False, 'params': {'exact': False, 'hnsw_ef': 128}})
                            fetched = time.perf_counter()
                            dense = paired.rank_parents(response['result']['points'], corpus)
                            lexical = lexical_or(db, q['query'])
                            lexical_done = time.perf_counter()
                            order, evidence = rank_fusion(dense, lexical, branch)
                            pool = order[:20]
                            states = eligibility(q['query'], documents, sources)
                            candidates = select_candidates(pool, states, True, 20)
                            top5 = present(candidates, eligibility(q['query'], documents, sources), True)
                            gated = time.perf_counter()
                            row = paired.review_row(q, top5, n, 'ann128', branch, documents, corpus, sources)
                            row.update(block=block, branch=branch, pool20=pool, candidates=candidates, dense=dense, lexical=lexical, eligibility=states, fusion_evidence=evidence,
                                candidate_recall=len(set(pool) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None,
                                gated_candidate_recall=len(set(candidates) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None)
                            for s in row['snippets_sources']:
                                s['sha256'] = documents[s['parent_id']]['sha256']
                            wire = json.dumps(row, ensure_ascii=False).encode()
                            end = time.perf_counter()
                            row['timing_ms'] = {'encode': (encoded-start)*1000, 'http': (fetched-encoded)*1000, 'lexical': (lexical_done-fetched)*1000, 'fusion_gates': (gated-lexical_done)*1000, 'citations_json': (end-gated)*1000, 'e2e': (end-start)*1000}
                            row.update(citation_wire_bytes=len(wire), query_vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest(), server_response=response)
                            key = (n, q['id'])
                            assert key not in query_vectors or np.array_equal(query_vectors[key], vector)
                            query_vectors[key] = vector
                            rows.append(row)
                            output.write(json.dumps(row, ensure_ascii=False) + '\n')
                            output.flush()
                print(json.dumps({'block': block, 'rows': len(rows)}), flush=True)
        report['measurement_seconds'] = time.monotonic() - measurement
        report['rss_after_bytes'] = {'harness': psutil.Process().memory_info().rss, 'server': psutil.Process(server.process.pid).memory_info().rss}
        assert len(rows) == 768
        for n in MODELS:
            matrix = np.stack([query_vectors[n, q['id']] for q in queries])
            assert np.array_equal(matrix, np.load(HISTORY / (n + '-query-vectors.npy')))
            np.save(run / (n + '-query-vectors.npy'), matrix)
        save(run / 'raw-results.json', rows)
        report['rows'] = len(rows)
        first = [r for r in rows if r['block'] == 0]
        historical = load('raw-results.json')
        report['baseline_history_top5_parity'] = {n: sum(next(r['top5'] for r in first if r['variant'] == n and r['branch'] == 'equal' and r['id'] == q['id']) == next(r['top5'] for r in historical if r['variant'] == n and r['block'] == 0 and r['mode'] == 'ann128' and r['id'] == q['id']) for q in queries) for n in MODELS}
        assert all(v == 32 for v in report['baseline_history_top5_parity'].values())
        changes = []
        for n in MODELS:
            for branch in BRANCHES:
                for subset, ids in subsets.items():
                    group = [r for r in first if r['variant'] == n and r['branch'] == branch and r['id'] in ids]
                    yes = [r for r in group if r['relevant']]
                    timed = [r for r in rows if r['variant'] == n and r['branch'] == branch and r['id'] in ids]
                    report['summaries'].append({'variant': n, 'branch': branch, 'subset': subset, 'queries': len(group), 'answerable': len(yes),
                        **{k: statistics.mean(r[k] for r in yes) if yes else None for k in ['p1', 'p3', 'p5', 'candidate_recall', 'gated_candidate_recall']},
                        **{k: statistics.mean(r['metrics'][k] for r in yes) if yes else None for k in ['mrr', 'recall_at_5']},
                        'incompatible_top1': sum(r['metrics']['incompatible_at_1'] for r in group), 'incompatible_top5': sum(len(r['incompatible_returned']) for r in group), 'unknown_top5': sum(len(r['unjudged']) for r in group),
                        'noanswer_queries': sum(not r['relevant'] for r in group), 'noanswer_false_accepts': sum(bool(r['top5']) for r in group if not r['relevant']),
                        'timing_ms': {stage: {'p50': statistics.median([r['timing_ms'][stage] for r in timed]), 'p95': percentile([r['timing_ms'][stage] for r in timed], .95)} for stage in timed[0]['timing_ms']}})
        lines = ['# Per-query frozen fusion diagnostic', '', 'REUSED labels. UNKNOWN is unjudged, not irrelevant. Pk selected hits/k; MRR truncated at5. No-answer FA is nonempty retrieval, not generated answer accuracy. RRF is not confidence.', '']
        causal = []
        for r in first:
            b = next(x for x in first if x['id'] == r['id'] and x['variant'] == r['variant'] and x['branch'] == 'equal')
            changes.append({'id': r['id'], 'variant': r['variant'], 'branch': r['branch'], 'category': r['category'], 'p1_delta': r['p1'] - b['p1'], 'p5_delta': r['p5'] - b['p5'], 'r5_delta': (r['metrics']['recall_at_5'] - b['metrics']['recall_at_5']) if r['relevant'] else None, 'baseline_top5': b['top5'], 'top5': r['top5']})
            if r['id'] == 'development-01':
                full, evidence = rank_fusion(r['dense'], r['lexical'], r['branch'])
                causal.append({'variant': r['variant'], 'branch': r['branch'], 'target': 'wal-network', 'target_rank': full.index('wal-network')+1, 'raw_dense_rank': r['dense'].index('wal-network')+1, 'raw_lexical_rank': r['lexical'].index('wal-network')+1, 'target_evidence': evidence['wal-network'], 'above_target': [{'id': name, **evidence[name]} for name in full[:full.index('wal-network')]], 'gate': r['eligibility']['wal-network']})
            lines += [f"## {r['id']} / {r['variant']} / {r['branch']}", '', r['query'], '', f"Selected={r['relevant']}; incompatible={r['incompatible']}; UNKNOWN={r['unjudged']}", f"P1/P3/P5={r['p1']}/{r['p3']}/{r['p5']}; MRR5={r['metrics']['mrr']}; R5={r['metrics']['recall_at_5']}; pool recall={r['candidate_recall']}; gated pool recall={r['gated_candidate_recall']}; noanswer FA={r['metrics']['no_answer_false_acceptance']}", '']
            for i, s in enumerate(r['snippets_sources'], 1):
                lines += [f"{i}. **{s['parent_id']}** {s['status']} [{s['source']}]({s['url']}) offsets [{s['start']},{s['end']}) SHA256={s['sha256']}", '', '> ' + s['snippet'].replace('\n', '\n> '), '']
        save(run / 'paired-changes.json', changes)
        save(run / 'wal-network-causality.json', causal)
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error), 'rows': len(rows)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = all(sha(REPO / p) == h for p, h in before.items())
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
        experiment(args.run or REPO / 'artifacts/fusion-experiments' / ('paired-' + uuid.uuid4().hex))
