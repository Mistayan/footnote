"""Frozen personal-knowledge retrieval budget diagnostic; no production activation."""
from retrieval_ablation import admissibility, source_metadata


def eligibility(query, documents, sources):
    """No judgment or query-relevance inference enters source version metadata."""
    return {name: admissibility(query, source_metadata(sources[doc['source']]))
            for name, doc in documents.items()}


def select_candidates(pool, states, gated, budget):
    """Filter the fixed pool BEFORE budget selection/reranking; never refill."""
    eligible = [name for name in pool if not gated or not states[name].startswith('REJECT')]
    return eligible[:budget] if budget else eligible


def present(ranked, states, gated):
    """Independent final boundary: do not trust the ranker's returned ordering."""
    return [name for name in ranked if not gated or not states[name].startswith('REJECT')][:5]


def proof_audit(relevant, states, pool, candidates, top5):
    """Counts are selected-label diagnostics, not an exhaustive evidence oracle."""
    eligible = sorted(n for n in relevant if not states[n].startswith('REJECT'))
    return {'eligible_selected_proofs': eligible,
            'selected_ineligible_proofs': sorted(set(relevant) - set(eligible)),
            'missing_from_pool': sorted(set(eligible) - set(pool)),
            'lost_to_budget_or_gate': sorted(set(eligible) & set(pool) - set(candidates)),
            'lost_at_presentation': sorted(set(eligible) & set(candidates) - set(top5)),
            'missed_eligible_proof_count': len(set(eligible) - set(top5))}


# Experiments are deliberately separate from the production retrieval path.
import datetime
import hashlib
import json
from pathlib import Path
import socket
import statistics
import time

import numpy as np
import psutil
import technical_quality as tq
import qdrant_quality as paired
from retrieval_ablation import CrossEncoder, lexical_or
from server_benchmark import Server, SERVER, ResourceSampler, save, sha, percentile

REPO = Path(__file__).resolve().parents[1]
HISTORY = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e'
MEASURED = HISTORY / 'measured-v3'
VARIANTS = [(f'{"gated" if gate else "ungated"}_{budget or "none"}', gate, budget)
            for budget in (0, 5, 10, 20) for gate in (False, True)]
BLOCKS = 4


class ResidentRequest:
    """One actual request, including its own encode, FTS, HTTP and citations."""
    def __init__(self, encoder, reranker, server, db, corpus, sources):
        self.encoder, self.reranker, self.server, self.db = encoder, reranker, server, db
        self.corpus, self.sources = corpus, sources
        self.documents = {d['id']: d for d in corpus}

    def execute(self, query, variant, gated, budget, block):
        started = time.perf_counter()
        stages = {}
        mark = time.perf_counter()
        vector = self.encoder.encode([query['query']], 'query')[0]
        stages['encode'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        lexical = lexical_or(self.db, query['query'])
        stages['lexical'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        response = self.server.request('POST', '/collections/budgets/points/query', {
            'query': vector.tolist(), 'limit': 60, 'with_payload': True,
            'with_vector': False, 'params': {'exact': False, 'hnsw_ef': 128}})
        stages['qdrant_http'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        dense = paired.rank_parents(response['result']['points'], self.corpus)
        pool = tq.fuse(dense, lexical)[:20]
        # States are freshly derived per request, not borrowed from another timing row.
        states = eligibility(query['query'], self.documents, self.sources)
        candidates = select_candidates(pool, states, gated, budget)
        stages['fusion_metadata_gate'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        ranked, logits = candidates, {}
        if budget and candidates:
            ranked, logits = self.reranker.rank(query['query'], [self.documents[n] for n in candidates])
        stages['rerank'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        # Recheck from raw source labels at the presentation trust boundary.
        final_states = eligibility(query['query'], self.documents, self.sources)
        top5 = present(ranked, final_states, gated)
        stages['presentation_gate'] = (time.perf_counter() - mark) * 1000
        mark = time.perf_counter()
        row = paired.review_row(query, top5, variant, 'ann128', 'or_rrf_pool20',
                                self.documents, self.corpus, self.sources)
        row.update(block=block, gated=gated, budget=budget, pool20=pool,
                   candidates=candidates, reranked=ranked, logits=logits,
                   eligibility=final_states,
                   rejected_pool=[n for n in pool if states[n].startswith('REJECT')],
                   proof_audit=proof_audit(query['relevant'], states, pool, candidates, top5))
        for snippet in row['snippets_sources']:
            snippet['sha256'] = self.documents[snippet['parent_id']]['sha256']
            snippet['metadata'] = source_metadata(self.sources[snippet['source']])
        # Actual outgoing citation/evidence JSON work is inside the measured boundary.
        wire = json.dumps(row, ensure_ascii=False).encode('utf-8')
        stages['citation_serialize'] = (time.perf_counter() - mark) * 1000
        stages['e2e'] = (time.perf_counter() - started) * 1000
        stages['unattributed'] = stages['e2e'] - sum(v for k, v in stages.items() if k != 'e2e')
        row['timing_ms'] = stages
        # Evidence logging below is outside request E2E, never shared into another request.
        row['citation_wire_bytes'] = len(wire)
        row['query_vector_sha256'] = hashlib.sha256(vector.tobytes()).hexdigest()
        row['server_response'] = response
        row['dense'], row['lexical'] = dense, lexical
        return row


def verify_rows(rows, corpus, queries, sources, historical):
    """Recompute metrics/provenance from saved rows, not aggregate claims."""
    documents = {d['id']: d for d in corpus}
    judgments = {q['id']: q for q in queries}
    old = {r['id']: r for r in historical if r['variant'] == 'or_rrf' and r['mode'] == 'ann128'}
    vectors = np.load(MEASURED / 'query-vectors.npy')
    hashes = {q['id']: hashlib.sha256(v.tobytes()).hexdigest() for q, v in zip(queries, vectors)}
    stable, gate_violations, pairs = {}, 0, 0
    assert len(rows) == len(queries) * len(VARIANTS) * BLOCKS
    for row in rows:
        q = judgments[row['id']]
        states = eligibility(q['query'], documents, sources)
        assert row['query_vector_sha256'] == hashes[q['id']]
        assert row['pool20'] == old[q['id']]['pool20']
        assert row['candidates'] == select_candidates(row['pool20'], states, row['gated'], row['budget'])
        assert set(row['reranked']) == set(row['candidates'])
        assert row['top5'] == present(row['reranked'], states, row['gated'])
        assert row['metrics'] == tq.score(row['top5'], q)
        for k in (1, 3, 5):
            assert row['p' + str(k)] == sum(n in q['relevant'] for n in row['top5'][:k]) / k
        assert row['unjudged'] == [n for n in row['top5'] if n not in set(q['relevant'] + q['incompatible'])]
        assert row['proof_audit'] == proof_audit(q['relevant'], states, row['pool20'], row['candidates'], row['top5'])
        for s in row['snippets_sources']:
            doc, source = documents[s['parent_id']], sources[s['source']]
            assert s['text'] == doc['text'] and s['url'] == source['url']
            assert s['sha256'] == sha_text(doc['text'])
            assert s['source_raw_sha256'] == source['sha256']
            assert (s['start'], s['end']) == (doc['start'], doc['end'])
        if row['gated']:
            gate_violations += sum(states[n].startswith('REJECT') for n in row['candidates'] + row['top5'])
        if row['variant'] == 'ungated_none':
            assert row['top5'] == old[q['id']]['top5']
            pairs += 1
        key = (q['id'], row['variant'])
        if key in stable:
            assert stable[key] == row['top5']
        stable[key] = row['top5']
        assert row['timing_ms']['e2e'] >= sum(v for k, v in row['timing_ms'].items() if k not in ('e2e', 'unattributed'))
    assert gate_violations == 0
    return {'verified_rows': len(rows), 'gate_violations': gate_violations,
            'same_pool_pairs': pairs, 'ranks_stable_across_blocks': True,
            'all_query_vectors_equal_historical': True, 'provenance_verified': True}


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def export_review(run, rows):
    """Per-query precision, snippets, raw citations, rank deltas and actual costs."""
    unique = [r for r in rows if r['block'] == 0]
    lines = ['# Personal retrieval: reused diagnostic per-query evidence', '',
             'Selected labels are incomplete; UNKNOWN is not false. P@k = selected hits/k, not exhaustive precision. No 90% acceptance or calibrated probability.',
             'Full raw source text, exact offsets, source/passages hashes, logits, pools and all repeated timings: raw-results.json.', '']
    differences = []
    for qid in dict.fromkeys(r['id'] for r in unique):
        group = [r for r in unique if r['id'] == qid]
        baseline = next(r for r in group if r['variant'] == 'ungated_none')
        lines += ['## ' + qid, '', baseline['query'], '',
                  f"Selected positives: {baseline['relevant']}; explicit incompatibilities: {baseline['incompatible']}", '']
        for row in group:
            timings = [r['timing_ms']['e2e'] for r in rows if r['id'] == qid and r['variant'] == row['variant']]
            delta = {'id': qid, 'variant': row['variant'], 'baseline_top5': baseline['top5'],
                     'top5': row['top5'], 'added': sorted(set(row['top5']) - set(baseline['top5'])),
                     'removed': sorted(set(baseline['top5']) - set(row['top5'])),
                     'p1_delta': row['p1'] - baseline['p1'], 'p5_delta': row['p5'] - baseline['p5'],
                     'e2e_repeated_ms': timings, 'proof_audit': row['proof_audit']}
            differences.append(delta)
            lines += [f"### {row['variant']} — P1/P3/P5 {row['p1']:.4f}/{row['p3']:.4f}/{row['p5']:.4f}; RR={row['metrics']['mrr']}; R5={row['metrics']['recall_at_5']}",
                      f"E2E four requests ms: {', '.join(f'{x:.3f}' for x in timings)}; incompatible={row['incompatible_returned']}; UNKNOWN={row['unjudged']}",
                      'Proof losses: ' + json.dumps(row['proof_audit']), '']
            for rank, s in enumerate(row['snippets_sources'], 1):
                lines += [f"{rank}. **{s['parent_id']}** — {s['status']}; [{s['source']}]({s['url']}); offsets [{s['start']},{s['end']}); version={s['metadata']['version']}; SHA256={s['sha256']}",
                          '', '> ' + s['snippet'].replace('\n', '\n> '), '']
    save(run / 'per-query-differences.json', differences)
    (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def summarize(rows):
    summaries = []
    for variant, _, _ in VARIANTS:
        for split in ('development', 'holdout'):
            group = [r for r in rows if r['variant'] == variant and r['split'] == split]
            first = [r for r in group if r['block'] == 0]
            answerable = [r for r in first if r['relevant']]
            item = {'variant': variant, 'split': split, 'unique_queries': len(first),
                    'repeated_requests': len(group), 'answerable': len(answerable)}
            for k in ('p1', 'p3', 'p5'):
                item[k] = statistics.mean(r[k] for r in answerable)
            for k in ('mrr', 'recall_at_5'):
                item[k] = statistics.mean(r['metrics'][k] for r in answerable)
            item.update(incompatible_top5=sum(len(r['incompatible_returned']) for r in first),
                        unknown_top5=sum(len(r['unjudged']) for r in first),
                        known_wrong_version_top5=sum(r['eligibility'][n] == 'REJECT_VERSION' for r in first for n in r['top5']),
                        rejected_unknown_top5=sum(r['eligibility'][n] == 'REJECT_UNKNOWN' for r in first for n in r['top5']),
                        no_answer_false_acceptance=sum(r['metrics']['no_answer_false_acceptance'] or 0 for r in first),
                        answerable_nonempty=sum(bool(r['top5']) for r in answerable),
                        missed_eligible_proofs=sum(r['proof_audit']['missed_eligible_proof_count'] for r in answerable),
                        proofs_missing_pool=sum(len(r['proof_audit']['missing_from_pool']) for r in answerable),
                        proofs_lost_budget=sum(len(r['proof_audit']['lost_to_budget_or_gate']) for r in answerable),
                        proofs_lost_presentation=sum(len(r['proof_audit']['lost_at_presentation']) for r in answerable),
                        eligible_selected_proofs=sum(len(r['proof_audit']['eligible_selected_proofs']) for r in answerable))
            item['timing_ms'] = {k: {'p50': statistics.median(r['timing_ms'][k] for r in group),
                                   'p95': percentile([r['timing_ms'][k] for r in group], .95)}
                                 for k in group[0]['timing_ms']}
            item['e2e_block_medians_ms'] = [statistics.median(r['timing_ms']['e2e'] for r in group if r['block'] == b) for b in range(BLOCKS)]
            item['rerank_pair_counts'] = sorted(set(len(r['candidates']) if r['budget'] else 0 for r in group))
            summaries.append(item)
    return summaries


def experiment(run):
    """Freeze finite matrix, then exercise resident models and owned real Qdrant."""
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/retrieval-budgets'):
        raise ValueError('new owned retrieval-budgets path required')
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('symlink run forbidden')
    run.mkdir(parents=True, exist_ok=False)
    corpus = json.loads((paired.SNAPSHOT / 'corpus.json').read_bytes())
    queries = json.loads((paired.SNAPSHOT / 'judgments.json').read_bytes())
    sources = json.loads((paired.SNAPSHOT / 'source-receipts.json').read_bytes())
    historical = json.loads((MEASURED / 'raw-results.json').read_bytes())
    snapshot_freeze = json.loads((paired.SNAPSHOT / 'freeze.json').read_bytes())
    for name, expected in snapshot_freeze['files'].items():
        assert sha(paired.SNAPSHOT / name) == expected
    old_freeze = json.loads((MEASURED / 'freeze.json').read_bytes())
    # Check retained model/server identities against the earlier measured freeze.
    for name, expected in old_freeze['inputs'].items():
        if '/models/' in name or '/reranker-model/' in name or name.endswith('qdrant.exe'):
            assert sha(REPO / name) == expected
    for d in corpus:
        normalized = (paired.SNAPSHOT / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert normalized[d['start']:d['end']] == d['text']
        assert sha_text(d['text']) == d['sha256']
    inputs = [Path(__file__), REPO / 'tests/retrieval_budget_benchmark_test.py', SERVER, REPO / '.git/index',
              REPO / 'requirements-hybrid.lock', paired.SNAPSHOT / 'freeze.json']
    inputs += [REPO / 'tools' / p for p in ('retrieval_ablation.py', 'technical_quality.py', 'qdrant_quality.py', 'server_benchmark.py', 'hybrid_dataset.py')]
    inputs += [paired.SNAPSHOT / name for name in snapshot_freeze['files']]
    inputs += [MEASURED / p for p in ('raw-results.json', 'original-vectors.npy', 'query-vectors.npy', 'freeze.json', 'report.json')]
    model = HISTORY / 'reranker-model'
    receipt = json.loads((model / 'receipt.json').read_bytes())
    inputs += [model / p for p in receipt['files']] + [model / 'receipt.json']
    inputs += [REPO / 'artifacts/models/minilm' / p for p in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': before,
              'before_inference': True, 'variants': VARIANTS, 'blocks': BLOCKS,
              'scope': 'PERSONAL knowledge and agent workflow; public technical diagnostic only',
              'labels': 'REUSED DIAGNOSTIC; incomplete selected positives; UNKNOWN not false; no 90% acceptance',
              'candidate_contract': 'Original MiniLM dense60 + literal technical OR BM25 top20, equal RRF60; common pool20 frozen before gate; no refill. Budgets select first 5/10/20 eligible members; none keeps eligible pool20. No tail append after reranking.',
              'gates': 'gated variants reject known wrong Python family and UNKNOWN on explicit Python version requests, before budget/rerank AND independently at presentation. Other queries NOT_ASSESSED. Ungated variants observational controls only.',
              'versions': 'Only pinned CPython raw source labels; never relevance, titles, dates or query terms in documents',
              'ranking': 'Same resident pinned mMARCO ONNX CPU, batches4 max512 logits; no probabilities',
              'abstention': 'NONE; optional calibration deliberately not run; no-answer nonempty is candidate false acceptance, not generated-answer accuracy',
              'timing': 'Four fully executed sequential blocks; query order and variant order reversed in odd blocks. Every request freshly executes encode, lexical, Qdrant, metadata/gates, rerank, original citations and serialization. No component sharing or caching. File export and evidence hashing outside E2E. Model hash validation/load and warm-up separate.',
              'qdrant': {'version': '1.19.2', 'hnsw_ef': 128, 'exact': False, 'M': 16, 'ef_construct': 100}}
    save(run / 'freeze.json', freeze)
    report = {'run': str(run), 'freeze_sha256': sha(run / 'freeze.json'), 'status': freeze['labels']}
    start = time.perf_counter()
    encoder = tq.ResidentEncoder(REPO / 'artifacts/models/minilm')
    report['encoder_load_validate_ms'] = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    reranker = CrossEncoder(model)
    report['reranker_load_validate_ms'] = (time.perf_counter() - start) * 1000
    report['environment'] = {'python': __import__('sys').version, 'platform': __import__('platform').platform(),
                             'logical_cpus': psutil.cpu_count(), 'physical_cpus': psutil.cpu_count(logical=False),
                             'memory_bytes': psutil.virtual_memory().total, **encoder.runtime}
    server, db, rows = Server(run), tq.lexical_index(corpus), []
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
                  'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
                  'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
        vectors = np.load(MEASURED / 'original-vectors.npy')
        server.request('PUT', '/collections/budgets', config)
        server.request('PUT', '/collections/budgets/points?wait=true', {'points': [
            {'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id']}}
            for i, (d, v) in enumerate(zip(corpus, vectors))]})
        deadline = time.monotonic() + 120
        while True:
            info = server.request('GET', '/collections/budgets')['result']
            if info['status'] == 'green' and info['indexed_vectors_count'] == len(corpus):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('HNSW index incomplete')
            time.sleep(.2)
        save(run / 'collection-readback.json', info)
        readback = server.request('POST', '/collections/budgets/points', {
            'ids': list(range(1, len(corpus) + 1)), 'with_payload': True, 'with_vector': True})['result']
        readback.sort(key=lambda p: p['id'])
        assert len(readback) == len(corpus)
        assert all(p['payload']['document_id'] == corpus[i]['id'] for i, p in enumerate(readback))
        error = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - vectors)))
        assert error < 1e-6
        save(run / 'server-readback.json', {'points': readback, 'max_abs_error': error})
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc'] <= report['first_inference_utc']
        pipeline = ResidentRequest(encoder, reranker, server, db, corpus, sources)
        warm = time.perf_counter()
        pipeline.execute(queries[0], 'warmup', True, 20, -1)
        report['warmup_ms'] = (time.perf_counter() - warm) * 1000
        paired.fresh_connection(server)
        with ResourceSampler(server) as sampler:
            for block in range(BLOCKS):
                order = list(queries) if block % 2 == 0 else list(reversed(queries))
                variants = VARIANTS if block % 2 == 0 else list(reversed(VARIANTS))
                for query in order:
                    for variant, gate, budget in variants:
                        rows.append(pipeline.execute(query, variant, gate, budget, block))
                save(run / f'block-{block}.json', rows[-len(queries) * len(VARIANTS):])
                print(json.dumps({'completed_block': block, 'requests': len(rows)}), flush=True)
        report['resources'] = sampler.report
        save(run / 'resource-samples.json', sampler.rows)
        save(run / 'raw-results.json', rows)
        # Read saved evidence back, then verify every row and original citation.
        stored = json.loads((run / 'raw-results.json').read_bytes())
        report['verification'] = verify_rows(stored, corpus, queries, sources, historical)
        report['rows'], report['baseline_top5_parity'] = len(rows), len(queries)
        report['summaries'] = summarize(stored)
        export_review(run, stored)
        report['reranker_at_limit_pairs_including_warmup'] = reranker.at_limit
        paired.fresh_connection(server)
        save(run / 'telemetry.json', server.request('GET', '/telemetry?details_level=3'))
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error)})
        raise
    finally:
        db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = before == {name: sha(REPO / name) for name in before}
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert json.loads((run / 'cleanup.json').read_bytes()) == report['cleanup']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', server.port)) != 0
    save(run / 'report.json', report)
    manifest = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', manifest)
    assert all(sha(run / name) == value for name, value in manifest.items())
    print(json.dumps({'run': str(run), 'rows': len(rows), 'cleanup': report['cleanup'],
                      'manifest_entries_verified': len(manifest)}), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    experiment(args.run or REPO / 'artifacts/retrieval-budgets' / uuid.uuid4().hex)
