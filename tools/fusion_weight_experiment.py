"""Frozen finite weighted-RRF public diagnostic; no production activation."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEIGHTS = {'dense_only': (1, 0), 'lexical_only': (0, 1), 'rrf_1_1': (1, 1),
           'rrf_2_1': (2, 1), 'rrf_4_1': (4, 1), 'rrf_1_2': (1, 2)}
VARIANTS = ['minilm_parent128', 'e5_parent512', 'e5_parent128']
HISTORY = REPO / 'artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4'


def fusion(dense, lexical, weights):
    """One-based RRF k60, fixed branch budgets, inactive branches contribute zero."""
    ranks = [{name: rank for rank, name in enumerate(branch[:limit], 1)}
             for branch, limit in ((dense, 60), (lexical, 20))]
    detail = {}
    for name in sorted(set(ranks[0]) | set(ranks[1])):
        dr, lr = ranks[0].get(name), ranks[1].get(name)
        dc = weights[0] / (60 + dr) if dr else 0
        lc = weights[1] / (60 + lr) if lr else 0
        if dc + lc:
            detail[name] = dict(dense_rank=dr, lexical_rank=lr, dense_contribution=dc,
                                lexical_contribution=lc, score=dc + lc)
    return sorted(detail, key=lambda n: (-detail[n]['score'], n)), detail


def encoders():
    from multilingual_embedding_experiment import verified_encoder
    return {VARIANTS[0]: verified_encoder(REPO / 'artifacts/models/minilm'),
            VARIANTS[1]: verified_encoder(REPO / 'artifacts/models/e5-small'),
            VARIANTS[2]: verified_encoder(REPO / 'artifacts/models/e5-small', cap=128)}


def verify_run(run):
    """Replay frozen formula, gates, citations, query identity and all evidence hashes."""
    import hashlib
    import json
    import numpy as np
    import technical_quality as tq
    from multilingual_embedding_experiment import sha
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    run = Path(run)
    load = lambda n: json.loads((run / n).read_bytes())
    for name, digest in load('evidence-sha256.json').items():
        assert sha(run / name) == digest, name
    freeze = load('freeze.json')
    assert all(sha(REPO / n) == h for n, h in freeze['inputs'].items())
    corpus, queries, sources = load('corpus.json'), load('judgments.json'), load('source-receipts.json')
    docs = {d['id']: d for d in corpus}
    qs = {q['id']: q for q in queries}
    for name, source in sources.items():
        assert sha(run / 'sources' / (name + '.raw')) == source['sha256']
        # Snapshot text_sha256 binds normalized Unicode LF text; raw .txt bytes may be CRLF on Windows.
        assert hashlib.sha256((run / 'sources' / (name + '.txt')).read_text(encoding='utf-8').encode()).hexdigest() == source['text_sha256']
    for d in corpus:
        text = (run / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']] == d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    matrices = {n: np.load(run / (n + '-query-vectors.npy')) for n in VARIANTS}
    hashes = {(n, q['id']): hashlib.sha256(matrices[n][i].tobytes()).hexdigest() for n in VARIANTS for i, q in enumerate(queries)}
    rows, stable = load('raw-results.json'), {}
    assert len(rows) == len(queries) * len(VARIANTS) * len(WEIGHTS) * 2
    keys = set()
    for r in rows:
        q = qs[r['id']]
        key = (r['block'], r['id'], r['variant'], r['fusion'])
        assert key not in keys
        keys.add(key)
        assert r['query_vector_sha256'] == hashes[r['variant'], r['id']]
        ranked, detail = fusion(r['dense'], r['lexical'], WEIGHTS[r['fusion']])
        assert ranked == r['fused_ranking'] and detail == r['contributions']
        assert r['pool20'] == ranked[:20]
        states = eligibility(q['query'], docs, sources)
        assert r['eligibility'] == states
        assert r['candidates'] == select_candidates(r['pool20'], states, True, 20)
        assert r['top5'] == present(r['candidates'], states, True)
        assert r['metrics'] == tq.score(r['top5'], q)
        for k in (1, 3, 5):
            assert r['p' + str(k)] == sum(n in q['relevant'] for n in r['top5'][:k]) / k
        assert r['candidate_recall'] == (len(set(r['pool20']) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None)
        assert all(not states[n].startswith('REJECT') for n in r['candidates'] + r['top5'])
        assert r['timing_ms']['attributed_sum'] <= r['timing_ms']['e2e']
        for snippet in r['snippets_sources']:
            d = docs[snippet['parent_id']]
            assert snippet['text'] == d['text'] and snippet['sha256'] == d['sha256']
            assert snippet['source_raw_sha256'] == sources[d['source']]['sha256']
            assert snippet['url'] == sources[d['source']]['url']
            assert (snippet['start'], snippet['end']) == (d['start'], d['end'])
        k = (r['id'], r['variant'], r['fusion'])
        if k in stable:
            assert stable[k] == r['top5']
        stable[k] = r['top5']
    for n in VARIANTS:
        matrix = np.load(run / (n + '-vectors.npy'))
        back = load(n + '-readback.json')['points']
        assert len(back) == len(matrix) == len(corpus)
        assert np.max(np.abs(np.asarray([p['vector'] for p in back]) - matrix)) < 1e-6
        assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(back))
        np.testing.assert_array_equal(matrix, np.load(HISTORY / (n + '-vectors.npy')))
        np.testing.assert_array_equal(matrices[n], np.load(HISTORY / (n + '-query-vectors.npy')))
    cleanup = load('cleanup.json')
    assert cleanup['process_exited'] and cleanup['port_closed']
    return True


def experiment(run):
    """Independent resident requests per finite matrix cell, two counterordered blocks."""
    import datetime
    import hashlib
    import json
    import platform
    import shutil
    import statistics
    import sys
    import time
    import numpy as np
    import technical_quality as tq
    import qdrant_quality as paired
    from multilingual_embedding_experiment import audited_recipe, SOURCE_DIR, sha
    from retrieval_ablation import lexical_or
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    from server_benchmark import Server, SERVER, save, percentile
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/fusion-weights') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('owned NEW non-symlink artifact directory required')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    load = lambda p: json.loads(p.read_bytes())
    oldfreeze = load(snapshot / 'freeze.json')
    assert all(sha(snapshot / n) == h for n, h in oldfreeze['files'].items())
    corpus, queries, sources = [load(snapshot / n) for n in ('corpus.json', 'judgments.json', 'source-receipts.json')]
    identities = load(SOURCE_DIR / 'identities.json')
    recipes = {n: audited_recipe(REPO / 'artifacts/models' / n, identities[key]) for n, key in [('minilm', 'minilm'), ('e5-small', 'e5')]}
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
              'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    inputs = [Path(__file__), REPO / 'tests/fusion_weight_experiment_test.py', SERVER, REPO / 'requirements-hybrid.lock', snapshot / 'freeze.json']
    inputs += [snapshot / n for n in oldfreeze['files']]
    inputs += [p for p in (snapshot / 'sources').iterdir() if p.is_file()]
    inputs += [REPO / 'tools' / n for n in ['multilingual_embedding_experiment.py', 'technical_quality.py', 'qdrant_quality.py', 'server_benchmark.py', 'retrieval_ablation.py', 'retrieval_budget_benchmark.py', 'hybrid_dataset.py']]
    inputs += list(SOURCE_DIR.glob('*'))
    inputs += [HISTORY / (n + suffix) for n in VARIANTS for suffix in ['-vectors.npy', '-query-vectors.npy']]
    inputs += [HISTORY / 'raw-results.json', HISTORY / 'freeze.json']
    inputs += [REPO / 'artifacts/models' / n / f for n in recipes for f in ['manifest.json', 'model.onnx', 'tokenizer.json']]
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    for n in ('corpus.json', 'judgments.json', 'source-receipts.json'):
        shutil.copyfile(snapshot / n, run / n)
    shutil.copytree(snapshot / 'sources', run / 'sources')
    (run / 'code').mkdir()
    for p in inputs:
        if p.suffix == '.py':
            shutil.copyfile(p, run / 'code' / p.name)
    save(run / 'model-recipes.json', recipes)
    freeze = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), inputs=before, variants=VARIANTS,
                  weights=WEIGHTS, rrf_k=60, blocks=2, mode='ann128', collection_config=config,
                  budgets=dict(dense=60, lexical=20, pool=20, present=5),
                  gates='Existing source-family version gate before selection and independently at presentation; explicit-version unknown rejected, otherwise NOT_ASSESSED; no refill.',
                  labels='Reused incomplete selected diagnostics, UNKNOWN not wrong. Builder consumes original corpus text only; no query or ranking labels. No fresh holdout, no90% claim.',
                  controls='Native E5 changes model+context; E5_128 separate length control. No downloads, reranker, translation, expansion, abstention or query-specific fixes.',
                  timing='Each cell independently encodes, calls HTTP dense60 and lexical20 even for single-branch controls (common acquisition overhead). Independent E2E includes ranking, both gates, citations and response JSON. Stage sums are attributed, not E2E; branch-attribution evidence/logging excluded. Two counterordered blocks; 600s finite measurement cap.')
    save(run / 'freeze.json', freeze)  # Freeze finite matrix BEFORE model initialization/inference.
    report = dict(run=str(run), task_status='OPEN_PENDING_PARENT_VERIFICATION', freeze_sha256=sha(run / 'freeze.json'),
                  environment=dict(python=sys.version, platform=platform.platform()), rows=0, summaries=[])
    started = time.perf_counter()
    resident = encoders()
    report['load_validation_ms'] = (time.perf_counter() - started) * 1000
    report['environment'].update(resident[VARIANTS[0]].runtime)
    report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert freeze['utc'] <= report['first_inference_utc']
    vectors = {}
    report['passage_encoding_ms'] = {}
    for n in VARIANTS:
        started = time.perf_counter()
        # Labels are not passed to encoder or indexed payloads.
        vectors[n] = resident[n].encode([d['text'] for d in corpus], 'passage')
        report['passage_encoding_ms'][n] = (time.perf_counter() - started) * 1000
        np.save(run / (n + '-vectors.npy'), vectors[n])
        np.testing.assert_array_equal(vectors[n], np.load(HISTORY / (n + '-vectors.npy')))
    documents = {d['id']: d for d in corpus}
    db, server, rows, query_vectors = tq.lexical_index(corpus), Server(run), [], {}
    oldrows = load(HISTORY / 'raw-results.json')
    baseline = {(r['id'], r['variant']): r for r in oldrows if r['mode'] == 'ann128' and r['block'] == 0}
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        for n in VARIANTS:
            server.request('PUT', '/collections/' + n, config)
            server.request('PUT', '/collections/' + n + '/points?wait=true', {'points': [dict(id=i+1, vector=v.tolist(), payload=dict(document_id=d['id'], parent_id=d['id'])) for i, (v, d) in enumerate(zip(vectors[n], corpus))]})
            time.sleep(1)
            info = server.request('GET', '/collections/' + n)['result']
            assert info['status'] == 'green' and info['indexed_vectors_count'] == len(corpus)
            back = server.request('POST', '/collections/' + n + '/points', {'ids': list(range(1, len(corpus)+1)), 'with_vector': True, 'with_payload': True})['result']
            back.sort(key=lambda p: p['id'])
            assert np.max(np.abs(np.asarray([p['vector'] for p in back]) - vectors[n])) < 1e-6
            save(run / (n + '-readback.json'), dict(collection=info, points=back))
        for encoder in resident.values():
            encoder.encode(['public technical retrieval warmup'], 'query')
        measurement = time.monotonic()
        with (run / 'raw-results.jsonl').open('w', encoding='utf-8') as output:
            for block in range(2):
                for q in (queries if block == 0 else reversed(queries)):
                    for n in (VARIANTS if block == 0 else reversed(VARIANTS)):
                        for weight in (list(WEIGHTS) if block == 0 else reversed(WEIGHTS)):
                            if time.monotonic() - measurement > 600:
                                raise TimeoutError('600s measurement budget exceeded')
                            start = time.perf_counter()
                            vector = resident[n].encode([q['query']], 'query')[0]
                            encoded = time.perf_counter()
                            response = server.request('POST', '/collections/' + n + '/points/query', dict(query=vector.tolist(), limit=60, with_payload=True, with_vector=False, params=dict(exact=False, hnsw_ef=128)))
                            fetched = time.perf_counter()
                            dense = paired.rank_parents(response['result']['points'], corpus)
                            lexical = lexical_or(db, q['query'])
                            acquired = time.perf_counter()
                            ranked, detail = fusion(dense, lexical, WEIGHTS[weight])
                            pool = ranked[:20]
                            states = eligibility(q['query'], documents, sources)
                            candidates = select_candidates(pool, states, True, 20)
                            top5 = present(candidates, eligibility(q['query'], documents, sources), True)
                            gated = time.perf_counter()
                            row = paired.review_row(q, top5, n, 'ann128', weight, documents, corpus, sources)
                            row.update(block=block, fusion=weight, pool20=pool, candidates=candidates,
                                       candidate_recall=len(set(pool) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None,
                                       gated_candidate_recall=len(set(candidates) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None)
                            for snippet in row['snippets_sources']:
                                snippet['sha256'] = documents[snippet['parent_id']]['sha256']
                            wire = json.dumps(row, ensure_ascii=False).encode()
                            end = time.perf_counter()
                            stages = dict(encode=(encoded-start)*1000, http=(fetched-encoded)*1000,
                                          lexical_parent=(acquired-fetched)*1000, fusion_gates=(gated-acquired)*1000,
                                          citations_json=(end-gated)*1000)
                            row['timing_ms'] = stages | dict(attributed_sum=sum(stages.values()), e2e=(end-start)*1000)
                            # Diagnostic attribution/extra raw serialization is NOT resident-request E2E.
                            row.update(dense=dense, lexical=lexical, fused_ranking=ranked, contributions=detail,
                                       eligibility=states, server_response=response, citation_wire_bytes=len(wire),
                                       query_vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest())
                            key = (n, q['id'])
                            if key in query_vectors:
                                np.testing.assert_array_equal(vector, query_vectors[key])
                            query_vectors[key] = vector
                            assert dense == baseline[q['id'], n]['dense'] and lexical == baseline[q['id'], n]['lexical']
                            if weight == 'rrf_1_1':
                                assert top5 == baseline[q['id'], n]['top5']
                            rows.append(row)
                            output.write(json.dumps(row, ensure_ascii=False) + '\n')
                            output.flush()
                print(json.dumps(dict(block=block, rows=len(rows))), flush=True)
        report['measurement_seconds'] = time.monotonic() - measurement
        report['rows'] = report['actual_http_query_calls'] = len(rows)
        report['gate_violations'] = sum(r['eligibility'][n].startswith('REJECT') for r in rows for n in r['candidates'] + r['top5'])
        assert report['gate_violations'] == 0
        for n in VARIANTS:
            np.save(run / (n + '-query-vectors.npy'), np.stack([query_vectors[n, q['id']] for q in queries]))
        save(run / 'raw-results.json', rows)
        first = [r for r in rows if r['block'] == 0]
        for n in VARIANTS:
            for weight in WEIGHTS:
                for subset in ('all', 'fr_to_en', 'negation', 'no_answer'):
                    group = [r for r in first if r['variant'] == n and r['fusion'] == weight and (subset == 'all' or r['category'] == subset or (subset == 'negation' and 'qfilter-not' in r['relevant']))]
                    yes = [r for r in group if r['relevant']]
                    times = [r['timing_ms']['e2e'] for r in rows if r['variant'] == n and r['fusion'] == weight and r['id'] in {g['id'] for g in group}]
                    report['summaries'].append(dict(variant=n, fusion=weight, subset=subset, queries=len(group), answerable=len(yes),
                        **{k: statistics.mean(r[k] for r in yes) if yes else None for k in ['p1', 'p3', 'p5', 'candidate_recall', 'gated_candidate_recall']},
                        **{k: statistics.mean(r['metrics'][k] for r in yes) if yes else None for k in ['mrr', 'recall_at_5']},
                        incompatible_top1=sum(r['metrics']['incompatible_at_1'] for r in group), incompatible_top5=sum(len(r['incompatible_returned']) for r in group),
                        unknown_top5=sum(len(r['unjudged']) for r in group), noanswer_false_accepts=sum(bool(r['top5']) for r in group if not r['relevant']),
                        e2e_p50_ms=statistics.median(times) if times else None, e2e_p95_ms=percentile(times, .95) if times else None,
                        attributed_sum_p50_ms=statistics.median([r['timing_ms']['attributed_sum'] for r in rows if r['variant'] == n and r['fusion'] == weight and r['id'] in {g['id'] for g in group}]) if times else None))
        changes, targets, lines = [], [], ['# Per-query frozen fusion diagnostic', '', 'Reused incomplete selected labels. UNKNOWN is unjudged, not wrong. No acceptance or default selection.', '']
        for r in first:
            b = next(x for x in first if x['id'] == r['id'] and x['variant'] == r['variant'] and x['fusion'] == 'rrf_1_1')
            changes.append(dict(id=r['id'], variant=r['variant'], fusion=r['fusion'], category=r['category'], baseline_top5=b['top5'], top5=r['top5'], p1_delta=r['p1']-b['p1'], p5_delta=r['p5']-b['p5'], recall5_delta=(r['metrics']['recall_at_5']-b['metrics']['recall_at_5']) if r['relevant'] else None))
            for target in r['relevant']:
                pos = r['fused_ranking'].index(target)+1 if target in r['fused_ranking'] else None
                targets.append(dict(id=r['id'], variant=r['variant'], fusion=r['fusion'], target=target, fused_rank=pos,
                                    target_contribution=r['contributions'].get(target),
                                    competitors_above=[dict(id=name, **r['contributions'][name]) for name in r['fused_ranking'][:pos-1]] if pos else [dict(id=name, **r['contributions'][name]) for name in r['fused_ranking']]))
            lines += [f"## {r['id']} / {r['variant']} / {r['fusion']}", '', r['query'], '',
                      f"Selected={r['relevant']}; incompatible={r['incompatible']}; unjudged={r['unjudged']}",
                      f"P1/P3/P5={r['p1']}/{r['p3']}/{r['p5']}; metrics={r['metrics']}; pool recall={r['candidate_recall']}", '']
            for i, s in enumerate(r['snippets_sources'], 1):
                lines += [f"{i}. **{s['parent_id']}** {s['status']} [{s['source']}]({s['url']}) offsets [{s['start']},{s['end']}) SHA256={s['sha256']}; raw source SHA256={s['source_raw_sha256']}", '', '> ' + s['snippet'].replace('\n', '\n> '), '']
        save(run / 'paired-changes.json', changes)
        save(run / 'target-attribution.json', targets)
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    except Exception as error:
        save(run / 'failure.json', dict(error=repr(error), rows=len(rows)))
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = all(sha(REPO / n) == h for n, h in before.items())
        save(run / 'partial-report.json', report)
    assert report['inputs_stable'] and report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    save(run / 'report.json', report)
    save(run / 'evidence-sha256.json', {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()})
    assert verify_run(run)
    print(json.dumps(dict(run=str(run), rows=len(rows), cleanup=report['cleanup'])), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    if args.verify:
        print(verify_run(args.verify))
    else:
        experiment(args.run or REPO / 'artifacts/fusion-weights' / ('paired-' + uuid.uuid4().hex))
