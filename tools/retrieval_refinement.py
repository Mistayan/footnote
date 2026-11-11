"""Prespecified personal local-knowledge retrieval refinement; no runtime wiring."""
from retrieval_ablation import admissibility
from technical_quality import fuse


def select_candidates(query, dense, lexical, documents, metadata, budget, gated, reranker=None):
    """Source-defined gate before fusion/selection, never label-derived."""
    import time
    started = time.perf_counter()
    eligibility = {name: admissibility(query, {
        'version': metadata.get(doc['source'], {}).get('version', 'UNKNOWN'),
        'product': metadata.get(doc['source'], {}).get('product', 'UNKNOWN')})
        for name, doc in documents.items()}
    def allowed(name):
        return not gated or not eligibility[name].startswith('REJECT')
    pool = fuse([n for n in dense if allowed(n)], [n for n in lexical if allowed(n)])[:budget]
    gate_fuse_ms = (time.perf_counter() - started) * 1000
    scores = {}
    ranked = pool
    started = time.perf_counter()
    if reranker and pool:
        ranked, scores = reranker.rank(query, [documents[n] for n in pool])
    rerank_ms = (time.perf_counter() - started) * 1000 if reranker else 0.0
    # Revalidate output; a reranker must not reintroduce excluded/out-of-pool IDs.
    final = list(dict.fromkeys(n for n in ranked if n in pool and allowed(n)))[:5]
    return {'pool': pool, 'top5': final, 'eligibility': eligibility, 'logits': scores,
            'gate_fuse_ms': gate_fuse_ms, 'rerank_ms': rerank_ms}


def experiment(run):
    """Freeze factorial comparisons, then execute independent timed requests."""
    import datetime
    import json
    import platform
    import random
    import shutil
    import socket
    import statistics
    import sys
    import time
    from pathlib import Path
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import CrossEncoder, source_metadata, lexical_or
    from server_benchmark import Server, SERVER, sha, save, percentile

    repo = Path(__file__).resolve().parents[1]
    run = Path(run).resolve()
    if not run.is_relative_to(repo / 'artifacts/retrieval-refinement'):
        raise ValueError('new owned retrieval-refinement directory required')
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('symlink artifact path')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    previous = repo / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
    reranker_dir = previous.parent / 'reranker-model'
    source_freeze = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, expected in source_freeze['files'].items():
        if sha(snapshot / name) != expected:
            raise ValueError('retained source changed: ' + name)
    # Verify predecessor execution inputs, not just its narrative report.
    predecessor = json.loads((previous / 'freeze.json').read_bytes())
    for name, expected in predecessor['inputs'].items():
        if sha(repo / name) != expected:
            raise ValueError('predecessor input changed: ' + name)
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    documents = {d['id']: d for d in corpus}
    metadata = {name: source_metadata(source) for name, source in sources.items()}
    for doc in corpus:
        text = (snapshot / 'sources' / (doc['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[doc['start']:doc['end']] == doc['text']
        assert tq.digest(doc['text'].encode()) == doc['sha256']
    variants = [dict(name=f'{"gated" if gated else "ungated"}_{"rerank" if rerank else "control"}_{budget}',
                     gated=gated, rerank=rerank, budget=budget)
                for budget in (5, 10, 20) for gated in (False, True) for rerank in (False, True)]
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False},
              'shard_number': 1, 'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    receipt = json.loads((reranker_dir / 'receipt.json').read_bytes())
    inputs = [Path(__file__), repo / 'tests/retrieval_refinement_test.py',
              repo / 'tools/retrieval_ablation.py', repo / 'tools/technical_quality.py',
              repo / 'tools/qdrant_quality.py', repo / 'tools/server_benchmark.py',
              repo / 'tools/hybrid_dataset.py', repo / 'requirements-hybrid.lock', SERVER,
              repo / '.git/index', snapshot / 'freeze.json', previous / 'freeze.json',
              previous / 'raw-results.json', previous / 'original-vectors.npy', previous / 'query-vectors.npy']
    inputs += [snapshot / name for name in source_freeze['files']]
    inputs += [repo / 'artifacts/models/minilm' / name for name in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    inputs += [reranker_dir / name for name in receipt['files']] + [reranker_dir / 'receipt.json']
    before = {p.relative_to(repo).as_posix(): sha(p) for p in inputs}
    for name, value in [('corpus.json', corpus), ('judgments.json', queries),
                        ('source-receipts.json', sources), ('metadata.json', metadata)]:
        save(run / name, value)
    (run / 'source').mkdir()
    for p in inputs[:8]:
        shutil.copyfile(p, run / 'source' / p.name)
    # Fixed seed determines all execution order before inference; no adaptive budget.
    rng = random.Random(20261017)
    schedule = []
    for repeat in range(3):
        order = list(queries)
        rng.shuffle(order)
        for query in order:
            choices = list(variants)
            rng.shuffle(choices)
            schedule.extend({'repeat': repeat, 'query_id': query['id'], 'variant': v['name']} for v in choices)
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'before_inference': True,
              'inputs': before, 'variants': variants, 'schedule': schedule, 'repeats': 3,
              'collection_config': config, 'mode': 'ann128', 'seed': 20261017,
              'scope': 'PERSONAL local knowledge storage and agent evidence retrieval only',
              'labels': 'REUSED DIAGNOSTIC; historical development/holdout names; selected incomplete labels; UNKNOWN is not false',
              'budgets': 'same original dense60 + literal BM25 OR20; RRF k60 equal weights ID ties; pool 5/10/20; top5; no refill',
              'gate': 'source URL explicit Python version family only; known different REJECT_VERSION; absent/unknown REJECT_UNKNOWN; otherwise NOT_ASSESSED. Filter BOTH branches BEFORE fusion/pool and reapply at final output; never infer compatibility',
              'reranker': 'same pinned mMARCO multilingual mMiniLM checkpoint, original text, max512 longest-first, batches4, CPU threads2/1, logits not probability',
              'timing': 'independent wall E2E each request from before query encode through JSON evidence serialization; actual resident encode/HTTP/lexical/gate/rerank stages; no shared-stage sums; model load/offline indexing/artifact I/O excluded',
              'abstention': 'none: any no-answer candidates are candidate false acceptance, not generated answers; no score threshold',
              'artifact_inputs': {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}}
    save(run / 'freeze.json', freeze)
    report = {'run': str(run), 'freeze_sha256': sha(run / 'freeze.json'), 'rows': 0,
              'status': freeze['labels'], 'environment': {'python': sys.version, 'platform': platform.platform(),
              'cpu_logical': psutil.cpu_count(), 'cpu_physical': psutil.cpu_count(logical=False),
              'memory_bytes': psutil.virtual_memory().total}, 'blockers': []}
    started = time.perf_counter()
    encoder = tq.ResidentEncoder(repo / 'artifacts/models/minilm')
    report['encoder_load_validate_ms'] = (time.perf_counter() - started) * 1000
    report['environment'].update(encoder.runtime)
    started = time.perf_counter()
    reranker = CrossEncoder(reranker_dir)
    report['reranker_load_validate_ms'] = (time.perf_counter() - started) * 1000
    server = Server(run)
    db = tq.lexical_index(corpus)
    rows = []
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc'] <= report['first_inference_utc']
        started = time.perf_counter()
        vectors = encoder.encode([d['text'] for d in corpus], 'passage')
        report['offline_encode_ms'] = (time.perf_counter() - started) * 1000
        assert np.array_equal(vectors, np.load(previous / 'original-vectors.npy'))
        np.save(run / 'passage-vectors.npy', vectors)
        expected_queries = np.load(previous / 'query-vectors.npy')
        expected_vector = {q['id']: expected_queries[i] for i, q in enumerate(queries)}
        paired.fresh_connection(server)
        server.request('PUT', '/collections/refinement', config)
        server.request('PUT', '/collections/refinement/points?wait=true', {'points': [
            {'id': i + 1, 'vector': vectors[i].tolist(), 'payload': {'document_id': d['id']}}
            for i, d in enumerate(corpus)]})
        deadline = time.monotonic() + 120
        while True:
            collection = server.request('GET', '/collections/refinement')['result']
            if collection['status'] == 'green' and collection['indexed_vectors_count'] == len(corpus):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('index did not cover corpus')
            time.sleep(.2)
        report['collection'] = collection
        readback = server.request('POST', '/collections/refinement/points', {
            'ids': list(range(1, len(corpus) + 1)), 'with_vector': True, 'with_payload': True})['result']
        readback.sort(key=lambda p: p['id'])
        assert len(readback) == len(corpus)
        assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(readback))
        report['readback_max_abs_error'] = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - vectors)))
        assert report['readback_max_abs_error'] < 1e-6
        save(run / 'server-readback.json', readback)
        encoder.encode([queries[0]['query']], 'query')
        reranker.rank(queries[0]['query'], corpus[:4])
        paired.fresh_connection(server)
        query_by_id = {q['id']: q for q in queries}
        variant_by_name = {v['name']: v for v in variants}
        with (run / 'raw-results.jsonl').open('w', encoding='utf-8') as output, (run / 'raw-server.jsonl').open('w', encoding='utf-8') as raw:
            for item in schedule:
                query = query_by_id[item['query_id']]
                variant = variant_by_name[item['variant']]
                # Independent invocation per variant: E2E is wall clock, NOT sum.
                start = time.perf_counter()
                qvector = encoder.encode([query['query']], 'query')[0]
                encoded = time.perf_counter()
                assert np.array_equal(qvector, expected_vector[query['id']])
                response = server.request('POST', '/collections/refinement/points/query', {
                    'query': qvector.tolist(), 'limit': 60, 'with_payload': True, 'with_vector': False,
                    'params': {'exact': False, 'hnsw_ef': 128}})
                fetched = time.perf_counter()
                dense = paired.rank_parents(response['result']['points'], corpus)
                lexical = lexical_or(db, query['query'])
                lexed = time.perf_counter()
                chosen = select_candidates(query['query'], dense, lexical, documents, metadata,
                                           variant['budget'], variant['gated'], reranker if variant['rerank'] else None)
                row = paired.review_row(query, chosen['top5'], variant['name'], 'ann128', 'or_rrf', documents, corpus, sources)
                row.update(repeat=item['repeat'], budget=variant['budget'], gated=variant['gated'],
                           reranked=variant['rerank'], pool=chosen['pool'], logits=chosen['logits'],
                           eligibility=chosen['eligibility'], dense=dense, lexical=lexical,
                           query_vector_sha256=tq.digest(qvector.tobytes()))
                row['known_wrong_version_top5'] = sum(chosen['eligibility'][n] == 'REJECT_VERSION' for n in row['top5'])
                row['unknown_version_top5'] = sum(chosen['eligibility'][n] == 'REJECT_UNKNOWN' for n in row['top5'])
                row['useful_coverage'] = bool(row['hits']) if query['relevant'] else None
                row['candidate_recall'] = len(set(chosen['pool']) & set(query['relevant'])) / len(query['relevant']) if query['relevant'] else None
                for snippet in row['snippets_sources']:
                    snippet['sha256'] = documents[snippet['parent_id']]['sha256']
                    snippet['metadata'] = metadata[snippet['source']]
                json.dumps(row, ensure_ascii=False)  # Included evidence hydration/serialization.
                end = time.perf_counter()
                row['timing_ms'] = {'encoding': (encoded - start) * 1000,
                    'backend': (fetched - encoded) * 1000, 'lexical_and_dense_sort': (lexed - fetched) * 1000,
                    'gate_fusion': chosen['gate_fuse_ms'], 'reranking': chosen['rerank_ms'],
                    'e2e_wall': (end - start) * 1000}
                rows.append(row)
                output.write(json.dumps(row, ensure_ascii=False) + '\n')
                raw.write(json.dumps(dict(item, response=response, query_vector_sha256=row['query_vector_sha256'])) + '\n')
                output.flush()
                raw.flush()
        report['encoder_at_limit'] = encoder.truncated
        report['reranker_at_limit'] = reranker.at_limit
        report['rows'] = len(rows)
        assert len(rows) == len(queries) * len(variants) * 3
        # Do not multiply relevance sample size by timing repetitions.
        unique = [r for r in rows if r['repeat'] == 0]
        report['summaries'] = []
        for variant in variants:
            for split in ('development', 'holdout'):
                group = [r for r in unique if r['variant'] == variant['name'] and r['split'] == split]
                answerable = [r for r in group if r['relevant']]
                summary = dict(variant, split=split, **tq.summarize(group))
                summary.update({k: statistics.mean(r[k] for r in answerable) for k in ('p1', 'p3', 'p5')})
                summary.update(useful_coverage=statistics.mean(r['useful_coverage'] for r in answerable),
                    known_wrong_version_top5=sum(r['known_wrong_version_top5'] for r in group),
                    unknown_version_top5=sum(r['unknown_version_top5'] for r in group),
                    unknown_relevance_top5=sum(len(r['unjudged']) for r in group),
                    candidate_recall=statistics.mean(r['candidate_recall'] for r in answerable))
                measured = [r for r in rows if r['variant'] == variant['name'] and r['split'] == split]
                for stage in measured[0]['timing_ms']:
                    values = [r['timing_ms'][stage] for r in measured]
                    summary[stage + '_p50_ms'] = statistics.median(values)
                    summary[stage + '_p95_ms'] = percentile(values, .95)
                report['summaries'].append(summary)
        report['pair_pool_checks'] = 0
        for row in rows:
            matches = [r for r in rows if r['id'] == row['id'] and r['repeat'] == row['repeat']]
            assert all(r['dense'] == row['dense'] and r['lexical'] == row['lexical'] and r['query_vector_sha256'] == row['query_vector_sha256'] for r in matches)
            if row['reranked']:
                control = next(r for r in matches if r['gated'] == row['gated'] and r['budget'] == row['budget'] and not r['reranked'])
                assert row['pool'] == control['pool']
                assert set(row['logits']) == set(row['pool'])
                report['pair_pool_checks'] += 1
        report['repeat_top5_stable'] = sum(len({tuple(r['top5']) for r in rows if r['id'] == q['id'] and r['variant'] == v['name']}) == 1 for q in queries for v in variants)
        assert report['repeat_top5_stable'] == len(queries) * len(variants)
        report['gated_known_wrong'] = sum(r['known_wrong_version_top5'] for r in rows if r['gated'])
        report['gated_unknown_version'] = sum(r['unknown_version_top5'] for r in rows if r['gated'])
        assert report['gated_known_wrong'] == report['gated_unknown_version'] == 0
        old_rows = json.loads((previous / 'raw-results.json').read_bytes())
        old = {r['id']: r for r in old_rows if r['variant'] == 'rerank_pool20' and r['mode'] == 'ann128'}
        report['previous_reranker_top5_parity'] = sum(r['top5'] == old[r['id']]['top5'] for r in unique if r['variant'] == 'ungated_rerank_20')
        assert report['previous_reranker_top5_parity'] == len(queries)
        paired.fresh_connection(server)
        save(run / 'telemetry.json', server.request('GET', '/telemetry?details_level=3'))
        lines = ['# Personal knowledge retrieval — REUSED DIAGNOSTIC', '', 'Selected labels incomplete; UNKNOWN is not false. Repeats only for timing. Full text/hashes/offsets/logits: raw-results.jsonl.', '']
        for query in queries:
            lines += [f"## {query['id']} — {query['query']}", '', f"Selected relevant: {query['relevant']}; explicit incompatibilities: {query['incompatible']}", '', '| Variant | P1/P3/P5 | RR/R5 | Useful | Known wrong/unknown version | Top5 |', '|---|---|---|---|---|---|']
            group = [r for r in unique if r['id'] == query['id']]
            for row in sorted(group, key=lambda r: r['variant']):
                lines += [f"| {row['variant']} | {row['p1']:.4f}/{row['p3']:.4f}/{row['p5']:.4f} | {row['metrics']['mrr']}/{row['metrics']['recall_at_5']} | {row['useful_coverage']} | {row['known_wrong_version_top5']}/{row['unknown_version_top5']} | {', '.join(row['top5'])} |"]
            lines += ['', '### Actual returned proof excerpts (deduplicated across variants)', '']
            seen = set()
            for row in group:
                for snippet in row['snippets_sources']:
                    if snippet['parent_id'] in seen:
                        continue
                    seen.add(snippet['parent_id'])
                    lines += [f"**{snippet['parent_id']}** {snippet['status']} — [{snippet['source']}]({snippet['url']}) [{snippet['start']},{snippet['end']}); version={snippet['metadata']['version']}; SHA256 `{snippet['sha256']}`", '', '> ' + snippet['snippet'].replace('\n', '\n> '), '']
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        save(run / 'paired-query-metrics.json', [{k: r[k] for k in ('id', 'variant', 'split', 'p1', 'p3', 'p5', 'metrics', 'useful_coverage', 'candidate_recall', 'known_wrong_version_top5', 'unknown_version_top5', 'top5')} for r in unique])
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error), 'rows': len(rows)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = before == {name: sha(repo / name) for name in before}
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', report['cleanup']['port'])) != 0
    report['manifest_verified'] = True
    save(run / 'report.json', report)
    hashes = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', hashes)
    assert all(sha(run / name) == expected for name, expected in hashes.items())
    print(json.dumps({'run': str(run), 'rows': report['rows'], 'cleanup': report['cleanup'], 'report_sha256': sha(run / 'report.json')}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    import uuid
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    experiment(args.run or Path(__file__).resolve().parents[1] / 'artifacts/retrieval-refinement' / uuid.uuid4().hex)
