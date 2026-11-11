"""Frozen candidate recall diagnostic; no production activation or downloads."""
import re
import datetime
import hashlib
import json
from pathlib import Path
import socket
import statistics
import time
import uuid

import numpy as np
import psutil
import technical_quality as tq
import qdrant_quality as paired
from retrieval_ablation import source_metadata, admissibility
from server_benchmark import Server, SERVER, save, sha

REPO = Path(__file__).resolve().parents[1]
HISTORY = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
VARIANTS = [(f'{kind}_{budget}', kind == 'exact', budget)
            for kind in ('original', 'exact') for budget in (20, 50, 100)]
BLOCKS = 3
import sqlite3
from retrieval_ablation import technical_tokens


def literal_spans(text):
    """Source-anchored sidecar spans; no identifier/negation splitting.

    Markup/code angle brackets are retained as operators, never guessed as HTML.
    Operators longest-first; other punctuation delimits. Source is untouched.
    """
    pattern = r'\w+(?:\.\w+)*|!=|==|<=|>=|&&|\|\||->|=>|[=<>!+*/%-]'
    return [{'raw': m[0], 'token': m[0].casefold(), 'start': m.start(), 'end': m.end()}
            for m in re.finditer(pattern, text, re.UNICODE)]


def exact_index(corpus):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED, text)')
    # Opaque ASCII tokens prevent unicode61 from splitting underscores/operators.
    db.executemany('INSERT INTO documents VALUES (?, ?)', [
        (d['id'], ' '.join('x' + s['token'].encode('utf-8').hex() for s in literal_spans(d['text'])))
        for d in corpus])
    return db


def fuse_candidates(dense, lexical):
    """Explicit acquisition budgets are set by callers, never silently capped."""
    scores = {}
    for names in (dense, lexical):
        for rank, name in enumerate(dict.fromkeys(names), 1):
            scores[name] = scores.get(name, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda n: (-scores[n], n))


def diagnose(query, pool):
    """Labels are used only AFTER ranking, never to select/filter candidates."""
    relevant, incompatible = set(query['relevant']), set(query['incompatible'])
    top = pool[:5]
    return {'candidate_recall': len(relevant & set(pool)) / len(relevant) if relevant else None,
            'recall5': len(relevant & set(top)) / len(relevant) if relevant else None,
            'top1': int(bool(top) and top[0] in relevant) if relevant else None,
            'mrr5': next((1 / rank for rank, name in enumerate(top, 1) if name in relevant), 0) if relevant else None,
            'missing_pool': sorted(relevant - set(pool)),
            'incompatible': [n for n in top if n in incompatible],
            'unknown': [n for n in top if n not in relevant | incompatible],
            'noanswer_false_acceptance': bool(top) if not relevant else None}


def lexical(db, query, limit, exact=False):
    tokens = (['x' + s['token'].encode('utf-8').hex() for s in literal_spans(query)]
              if exact else technical_tokens(query))
    if not tokens:
        return []
    expression = ' OR '.join('"' + t.replace('"', '""') + '"' for t in dict.fromkeys(tokens))
    return [r[0] for r in db.execute(
        'SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents), id LIMIT ?',
        (expression, limit))]


def truncation_summary(rows, cap):
    """Trailing whitespace lacks token offsets without implying token truncation."""
    return {'over_token_cap': sum(r['tokens'] > cap for r in rows),
            'at_or_above_cap': sum(r['tokens'] >= cap for r in rows),
            'omitted_nonwhitespace': sum(bool(r['omitted_text'].strip()) for r in rows),
            'unencoded_tail': sum(bool(r['omitted_text']) for r in rows)}


def experiment(run):
    """Finite six-variant matrix, actual resident encode and owned server only."""
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/candidate-recall') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('NEW non-symlink candidate-recall run required')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    snapshot_freeze = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, expected in snapshot_freeze['files'].items():
        assert sha(snapshot / name) == expected
    old = json.loads((HISTORY / 'freeze.json').read_bytes())
    for name, expected in old['inputs'].items():
        if '/models/' in name or name.endswith('qdrant.exe'):
            assert sha(REPO / name) == expected
    inputs = [Path(__file__), REPO / 'tests/candidate_recall_benchmark_test.py', SERVER,
              REPO / '.git/index', snapshot / 'freeze.json', HISTORY / 'freeze.json']
    inputs += [snapshot / name for name in snapshot_freeze['files']]
    inputs += [HISTORY / name for name in ('original-vectors.npy', 'query-vectors.npy', 'raw-results.json')]
    inputs += [REPO / 'tools' / name for name in ('technical_quality.py', 'qdrant_quality.py', 'server_benchmark.py', 'retrieval_ablation.py', 'hybrid_dataset.py')]
    inputs += [REPO / 'artifacts/models/minilm' / name for name in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    before = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
              'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': before,
              'variants': VARIANTS, 'blocks': BLOCKS, 'collection_config': config,
              'scope': 'Personal agent base, 1-2 month horizon; public reused diagnostics only; no bank qualification',
              'labels': 'Frozen old incomplete selected labels; UNKNOWN not false; no relabeling or 90% acceptance',
              'ranking': 'Same parent units/offsets/dense vectors. Baseline pool20: dense60 lexical20 OR RRF60. Pool50: dense60 lexical50. Pool100: dense100 lexical100. Parent de-dup before equal RRF. No filtering/refill/abstention/reranker.',
              'ablation': 'Exact sidecar uniformly casefolds literal words with underscores/dots and operators; retains markup/code tokens without guessing tags; UTF8 hex tokens prevent FTS splitting. Other punctuation delimits. No stemming, expansion, query rules, label-derived metadata or source edits.',
              'timing': 'Three independent fully executed sequential requests per query/variant; reversed order in odd block. Every query freshly encoded; encode/HTTP/lexical/fusion/citation+serialization measured, no cached stage sums. No reranking. Offline original vectors reused; zero document inference cost claimed.'}
    save(run / 'freeze.json', freeze)  # Frozen before model load/inference.
    for name, data in [('corpus.json', corpus), ('judgments.json', queries), ('sources.json', sources)]:
        save(run / name, data)
    report = {'freeze_sha256': sha(run / 'freeze.json'), 'rows': 0}
    started = time.perf_counter()
    encoder = tq.ResidentEncoder(REPO / 'artifacts/models/minilm')
    report['model_load_validate_ms'] = (time.perf_counter() - started) * 1000
    report['environment'] = {'python': __import__('sys').version, **encoder.runtime}
    # Independent untruncated offsets plus actual truncated offsets, same tokenizer recipe.
    from tokenizers import Tokenizer
    full = Tokenizer.from_file(str(REPO / 'artifacts/models/minilm/tokenizer.json'))
    full.no_padding()
    full.no_truncation()
    short = Tokenizer.from_str(full.to_str())
    short.enable_truncation(max_length=encoder.manifest['max_length'])
    truncation = []
    literal_sidecar = []
    for doc in corpus:
        source_text = (snapshot / 'sources' / (doc['source'] + '.txt')).read_text(encoding='utf-8')
        assert source_text[doc['start']:doc['end']] == doc['text']
        assert hashlib.sha256(doc['text'].encode()).hexdigest() == doc['sha256']
        tokens, encoded = full.encode(doc['text']), short.encode(doc['text'])
        end = max((b for a, b in encoded.offsets), default=0)
        truncation.append({'id': doc['id'], 'tokens': len(tokens.ids), 'encoded_char_end': end,
                           'encoded_source_end': doc['start'] + end, 'omitted_chars': len(doc['text']) - end,
                           'visible_text': doc['text'][:end], 'omitted_text': doc['text'][end:],
                           'encoded_ids': encoded.ids, 'full_offsets': tokens.offsets,
                           'operator_occurrences': [{'raw': s['raw'], 'start': doc['start'] + s['start'],
                               'end': doc['start'] + s['end'], 'visible': s['end'] <= end}
                               for s in literal_spans(doc['text']) if '_' in s['raw'] or not s['raw'].isalnum()]})
        literal_sidecar.append({'id': doc['id'], 'source': doc['source'], 'source_start': doc['start'],
                                'spans': literal_spans(doc['text'])})
    save(run / 'truncation-diagnostics.json', truncation)
    save(run / 'literal-sidecar.json', literal_sidecar)
    documents = {d['id']: d for d in corpus}
    vectors = np.load(HISTORY / 'original-vectors.npy')
    historical_queries = np.load(HISTORY / 'query-vectors.npy')
    history = {r['id']: r for r in json.loads((HISTORY / 'raw-results.json').read_bytes())
               if r['variant'] == 'or_rrf' and r['mode'] == 'ann128'}
    started = time.perf_counter()
    dbs = {False: tq.lexical_index(corpus), True: exact_index(corpus)}
    report['lexical_index_build_ms'] = (time.perf_counter() - started) * 1000
    server, rows = Server(run), []
    parity = set()
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        server.request('PUT', '/collections/candidates', config)
        server.request('PUT', '/collections/candidates/points?wait=true', {'points': [
            {'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id']}}
            for i, (d, v) in enumerate(zip(corpus, vectors))]})
        deadline = time.monotonic() + 120
        while True:
            info = server.request('GET', '/collections/candidates')['result']
            if info['status'] == 'green' and info['indexed_vectors_count'] == len(corpus):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('index not ready')
            time.sleep(.2)
        save(run / 'collection-readback.json', info)
        points = server.request('POST', '/collections/candidates/points', {
            'ids': list(range(1, len(corpus) + 1)), 'with_payload': True, 'with_vector': True})['result']
        points.sort(key=lambda p: p['id'])
        assert [p['payload']['document_id'] for p in points] == [d['id'] for d in corpus]
        assert np.max(np.abs(np.asarray([p['vector'] for p in points]) - vectors)) < 1e-6
        save(run / 'vectors-readback.json', points)
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc'] <= report['first_inference_utc']
        encoder.encode([queries[0]['query']], 'query')  # Warm resident session, outside measurements.
        for block in range(BLOCKS):
            order = queries if block % 2 == 0 else list(reversed(queries))
            variants = VARIANTS if block % 2 == 0 else list(reversed(VARIANTS))
            for query in order:
                for variant, exact, budget in variants:
                    start = mark = time.perf_counter()
                    vector = encoder.encode([query['query']], 'query')[0]
                    assert np.array_equal(vector, historical_queries[queries.index(query)])
                    timings = {'encode': (time.perf_counter() - mark) * 1000}
                    mark = time.perf_counter()
                    response = server.request('POST', '/collections/candidates/points/query', {
                        'query': vector.tolist(), 'limit': max(60, budget), 'with_payload': True,
                        'with_vector': False, 'params': {'exact': False, 'hnsw_ef': 128}})
                    timings['qdrant_http'] = (time.perf_counter() - mark) * 1000
                    mark = time.perf_counter()
                    lex = lexical(dbs[exact], query['query'], budget, exact)
                    timings['lexical'] = (time.perf_counter() - mark) * 1000
                    mark = time.perf_counter()
                    dense = paired.rank_parents(response['result']['points'], corpus)
                    pool = fuse_candidates(dense, lex)[:budget]
                    timings['fusion'] = (time.perf_counter() - mark) * 1000
                    if variant == 'original_20':
                        assert pool == history[query['id']]['pool20']
                        assert pool[:5] == history[query['id']]['top5']
                        parity.add(query['id'])
                    mark = time.perf_counter()
                    row = paired.review_row(query, pool[:5], variant, 'ann128', 'candidate_recall', documents, corpus, sources)
                    row.update(block=block, budget=budget, pool=pool, diagnostic=diagnose(query, pool),
                               dense=dense, lexical=lex, server_response=response,
                               query_vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest())
                    for snippet in row['snippets_sources']:
                        snippet['sha256'] = documents[snippet['parent_id']]['sha256']
                        snippet['metadata'] = source_metadata(sources[snippet['source']])
                        snippet['version_state'] = admissibility(query['query'], snippet['metadata'])
                    row['known_wrong_version'] = [s['parent_id'] for s in row['snippets_sources'] if s['version_state'] == 'REJECT_VERSION']
                    json.dumps(row, ensure_ascii=False)
                    timings['diagnostic_citation_serialize'] = (time.perf_counter() - mark) * 1000
                    timings['e2e'] = (time.perf_counter() - start) * 1000
                    row['timing_ms'] = timings
                    rows.append(row)
            save(run / f'block-{block}.json', rows[-len(queries) * len(VARIANTS):])
        save(run / 'raw-results.json', rows)
        report.update(rows=len(rows), baseline_parity=len(parity), summaries=[])
        differences, review = [], ['# Per-query reused diagnostic review', '', 'UNKNOWN is not false; old labels frozen; no acceptance. No reranker or abstention.', '']
        for query in queries:
            group = [r for r in rows if r['id'] == query['id'] and r['block'] == 0]
            baseline = next(r for r in group if r['variant'] == 'original_20')
            review += ['## ' + query['id'], '', query['query'], '', 'Selected proofs: ' + str(query['relevant']), '']
            for row in group:
                delta = {'id': query['id'], 'variant': row['variant'],
                         'candidate_gained': sorted((set(row['pool']) - set(baseline['pool'])) & set(query['relevant'])),
                         'candidate_lost': sorted((set(baseline['pool']) - set(row['pool'])) & set(query['relevant'])),
                         'final_gained': sorted((set(row['top5']) - set(baseline['top5'])) & set(query['relevant'])),
                         'final_lost': sorted((set(baseline['top5']) - set(row['top5'])) & set(query['relevant']))}
                differences.append(delta)
                review += ['### ' + row['variant'], json.dumps(row['diagnostic']), json.dumps(delta), '']
                for rank, s in enumerate(row['snippets_sources'], 1):
                    review += [f"{rank}. {s['parent_id']} — {s['status']}; [{s['source']}]({s['url']}); [{s['start']},{s['end']}); {s['sha256']}", '> ' + s['snippet'].replace('\n', '\n> '), '']
        save(run / 'per-query-differences.json', differences)
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(review) + '\n', encoding='utf-8')
        for variant, _, _ in VARIANTS:
            for split in ('development', 'holdout'):
                group = [r for r in rows if r['variant'] == variant and r['split'] == split]
                unique = [r for r in group if r['block'] == 0]
                ans = [r for r in unique if r['relevant']]
                item = {'variant': variant, 'split': split, 'answerable': len(ans)}
                item.update({k: statistics.mean(r['diagnostic'][k] for r in ans) for k in ('candidate_recall', 'top1', 'recall5', 'mrr5')})
                item.update(incompatible=sum(len(r['diagnostic']['incompatible']) for r in unique),
                            unknown=sum(len(r['diagnostic']['unknown']) for r in unique),
                            noanswer_false_acceptance=sum(bool(r['diagnostic']['noanswer_false_acceptance']) for r in unique),
                            wrong_version=sum(len(r['known_wrong_version']) for r in unique),
                            timing_p50_ms={k: statistics.median(r['timing_ms'][k] for r in group) for k in group[0]['timing_ms']})
                report['summaries'].append(item)
    finally:
        for db in dbs.values():
            db.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = before == {name: sha(REPO / name) for name in before}
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', server.port)) != 0
    report['truncation'] = truncation_summary(truncation, encoder.manifest['max_length'])
    save(run / 'report.json', report)
    manifest = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', manifest)
    assert all(sha(run / name) == expected for name, expected in manifest.items())
    print(json.dumps({'run': str(run), 'rows': len(rows), 'cleanup': report['cleanup']}), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    experiment(args.run or REPO / 'artifacts/candidate-recall' / uuid.uuid4().hex)
