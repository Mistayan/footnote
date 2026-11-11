"""Isolated Qdrant server public-corpus retrieval experiment (not production)."""
import csv
import datetime
import hashlib
import json
import socket
import sqlite3
import statistics
import time
import uuid
from pathlib import Path

import numpy as np

import technical_quality as tq
from server_benchmark import Server, SERVER, sha, save

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO / 'artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92'
MODES = [('sqlite_exact', True, 128), ('exact', True, 128), ('ann128', False, 128),
         ('ann256', False, 256), ('ann512', False, 512)]


def rank_parents(points, documents):
    """Max-child ranking, stable document-ID ties, first occurrence per parent."""
    ordered = sorted(points, key=lambda p: (-p['score'], documents[p['id'] - 1]['id']))
    return list(dict.fromkeys(documents[p['id'] - 1].get('parent_id', documents[p['id'] - 1]['id'])
                              for p in ordered))


def fresh_connection(server):
    """Explicit unmeasured connection lifecycle, never a retry of a measured call."""
    connection = getattr(server.local, 'connection', None)
    if connection:
        connection.close()
        del server.local.connection


def review_row(query, top5, variant, mode, ranking, candidates, corpus, sources):
    relevant, incompatible = set(query['relevant']), set(query['incompatible'])
    parents = {p['id']: p for p in corpus}
    hits = [name for name in top5 if name in relevant]
    snippets = []
    for name in top5:
        doc = candidates.get(name, parents[name])
        source = sources[doc['source']]
        snippets.append({'parent_id': name, 'passage_id': doc['id'], 'source': doc['source'],
                         'url': source['url'], 'source_raw_sha256': source['sha256'],
                         'start': doc['start'], 'end': doc['end'], 'text': doc['text'],
                         'snippet': doc['text'][:500],
                         'status': 'selected relevant' if name in relevant else
                         'explicit incompatible' if name in incompatible else 'UNKNOWN/unjudged'})
    return dict(query, variant=variant, mode=mode, ranking=ranking, top5=top5, hits=hits,
                answerability='answerable (selected evidence)' if relevant else
                'NO ANSWER: public corpus cannot answer this deployment/private/unsupported question',
                p1=sum(n in relevant for n in top5[:1]),
                p3=sum(n in relevant for n in top5[:3]) / 3,
                p5=len(hits) / 5, ideal_p5=min(len(relevant), 5) / 5,
                incompatible_returned=[n for n in top5 if n in incompatible],
                unjudged=[n for n in top5 if n not in relevant | incompatible],
                snippets_sources=snippets, metrics=tq.score(top5, query))


def write_review(run, rows):
    fields = ['id', 'split', 'query', 'variant', 'mode', 'ranking', 'answerability', 'relevant',
              'top5', 'hits', 'p1', 'p3', 'p5', 'ideal_p5', 'recall5', 'reciprocal_rank',
              'incompatible_returned', 'unjudged', 'snippets_sources']
    with (run / 'per-query.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            values = {k: row.get(k) for k in fields}
            values.update(recall5=row['metrics']['recall_at_5'], reciprocal_rank=row['metrics']['mrr'])
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in values.items()})
    lines = ['# Per-query evidence review — harmonized SQLite and Qdrant', '',
             'PRIMARY: current parent MiniLM SQLite exact hybrid versus Qdrant ANN ef128 hybrid. All other layouts/models/modes are exploratory appendices, not replacements for this baseline.',
             '90% acceptance gate: REJECTED. Incomplete selected labels cannot certify exhaustive semantic precision. Not LAD/RAD certification.',
             'All SQLite/exact variant/ranking combinations and primary Qdrant ANN below. Every ANN query, metric and full returned passage text is in per-query.csv and raw-results.json.',
             'Selected, incomplete agent labels are NOT exhaustive semantic relevance. UNKNOWN/unjudged is not proven wrong. No relabeling after inference.',
             'P@k uses denominator k, absent slots count zero; ideal P@5 is min(positive label count,5)/5. No-answer P metrics are label-count diagnostics, not confidence.',
             'Old holdout is REUSED/observed, not independent validation; no winner selection.', '']
    primary = [r for r in rows if r['variant'] == 'parent-minilm' and r['ranking'] == 'hybrid'
               and r['mode'] in ('sqlite_exact', 'ann128')]
    ordered_rows = sorted(primary, key=lambda r: (r['id'], r['mode'])) + [r for r in rows if r not in primary]
    primary_lines = list(lines)
    for row in ordered_rows:
        if row['mode'] not in ('exact', 'sqlite_exact') and row not in primary:
            continue
        section = [f"## {row['variant']} / {row['mode']} / {row['ranking']} / {row['id']}", '',
                  f"**Query:** {row['query']}", '', row['answerability'], '',
                  f"Selected relevant: {row['relevant']}; ordered top5: {row['top5']}; hits: {row['hits']}", '',
                  f"P@1={row['p1']:.3f}; P@3={row['p3']:.3f}; P@5={row['p5']:.3f}; ideal P@5={row['ideal_p5']:.3f}; recall5={row['metrics']['recall_at_5']}; RR@5={row['metrics']['mrr']}", '',
                  f"Explicit incompatible returned: {row['incompatible_returned']}; UNKNOWN/unjudged: {row['unjudged']}", '']
        for rank, passage in enumerate(row['snippets_sources'], 1):
            section += [f"{rank}. **{passage['parent_id']}** — {passage['status']}; actual retrieved passage `{passage['passage_id']}`; chars [{passage['start']},{passage['end']}) of [{passage['source']}]({passage['url']}).",
                      '', '> ' + passage['snippet'].replace('\n', '\n> '), '']
        lines += section
        if row in primary:
            primary_lines += section
    (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (run / 'PRIMARY-PAIRED-REVIEW.md').write_text('\n'.join(primary_lines) + '\n', encoding='utf-8')


def experiment():
    """Freeze then execute all prespecified variants, preserving raw server evidence."""
    base = REPO / 'artifacts/qdrant-quality'
    if any(p.is_symlink() for p in (base, *base.parents)):
        raise ValueError('owned artifact root must not traverse symlinks')
    run = base / uuid.uuid4().hex
    run.mkdir(parents=True, exist_ok=False)
    corpus = json.loads((SNAPSHOT / 'corpus.json').read_bytes())
    queries = json.loads((SNAPSHOT / 'judgments.json').read_bytes())
    sources = json.loads((SNAPSHOT / 'source-receipts.json').read_bytes())
    old_freeze = json.loads((SNAPSHOT / 'freeze.json').read_bytes())
    for name, expected in old_freeze['files'].items():
        if sha(SNAPSHOT / name) != expected:
            raise ValueError('retained frozen input changed: ' + name)
    for doc in corpus:
        normalized = (SNAPSHOT / 'sources' / (doc['source'] + '.txt')).read_text(encoding='utf-8')
        assert normalized[doc['start']:doc['end']] == doc['text']
        assert hashlib.sha256(doc['text'].encode()).hexdigest() == doc['sha256']
    started = time.perf_counter()
    encoders = {name: tq.ResidentEncoder(REPO / 'artifacts/models' / name)
                for name in ('minilm', 'e5-small')}
    load_ms = (time.perf_counter() - started) * 1000
    children = tq.child_chunks(corpus, list(encoders.values()))
    layouts = [('parent-minilm', 'minilm', 'parents', corpus),
               ('child-minilm', 'minilm', 'children', children),
               ('child-e5-small', 'e5-small', 'children', children)]
    save(run / 'corpus.json', corpus)
    save(run / 'children.json', children)
    save(run / 'judgments.json', queries)
    save(run / 'source-receipts.json', sources)
    inputs = [Path(__file__), REPO / 'tests/qdrant_quality_test.py',
              REPO / 'tools/technical_quality.py', REPO / 'tools/server_benchmark.py',
              REPO / 'tools/hybrid_dataset.py', REPO / 'requirements-hybrid.lock', SERVER,
              SNAPSHOT / 'freeze.json']
    inputs += [SNAPSHOT / name for name in old_freeze['files']]
    inputs += [REPO / 'artifacts/models' / name / file for name in encoders
               for file in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    before = {str(p.relative_to(REPO).as_posix()): sha(p) for p in inputs}
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False},
              'shard_number': 1, 'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    variants = [dict(name=name, model=model, layout=layout, documents=len(docs),
                     token_overflow=sum(encoders[model].token_count(d['text'], 'passage') >=
                                        encoders[model].manifest['max_length'] for d in docs))
                for name, model, layout, docs in layouts]
    freeze = {'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'before_inference': True, 'files': before, 'variants': variants, 'modes': MODES,
              'primary_comparison': 'CURRENT parent MiniLM SQLite JSON float64 exact hybrid vs Qdrant ANN ef128 hybrid; children/E5 exploratory only',
              'required_precision': .9,
              'holdout_status': 'REUSED/observed; not independent validation',
              'selection': 'No holdout-based winner selection; no label, question or score-based chunk tuning',
              'ranking': 'cosine top60 raw point candidates; deterministic score desc/document ID asc; max-child first-occurrence parent dedup; semantic-only plus parent FTS5 whitespace-literal AND top20; equal RRF k60 rank1, parent ID ties; top5. Dedup BEFORE fusion; child top60 may yield fewer than60 unique parents.',
              'collection_config': config, 'abstention': 'none; always return candidates, never confidence',
              'model_manifests': {k: e.manifest for k, e in encoders.items()},
              'artifact_inputs': {p.name: sha(p) for p in run.iterdir() if p.is_file()}}
    save(run / 'freeze.json', freeze)
    report = {'run': run.as_posix(), 'snapshot': SNAPSHOT.as_posix(),
              'freeze_sha256': sha(run / 'freeze.json'), 'variants': variants,
              'model_load_validate_ms': load_ms, 'collections': [], 'summaries': [],
              'variant_timings': [], 'holdout_status': freeze['holdout_status'],
              'environment': {k: e.runtime for k, e in encoders.items()},
              'paired_sqlite_qdrant': True, 'primary_comparison': freeze['primary_comparison'],
              'acceptance_status': 'REJECTED: below 90% observed selected-label precision; incomplete labels cannot certify exhaustive precision; NOT LAD/RAD certification',
              'timing_contract': 'One shared measured resident encode and parent lexical stage per query/model, reused unchanged by both engines. backend_roundtrip separately measures SQLite disk JSON read/decode/dot/sort or Qdrant JSON/HTTP query. Same parent resolution/fusion/citation construction/serialization is measured per result. Combined component sum is attributed resident pipeline time, NOT independently executed E2E latency.'}
    server = Server(run)
    db = tq.lexical_index(corpus)
    sqlite_backend = None
    rows, raw, ann_comparisons = [], [], []
    try:
        server.start()
        identity = server.request('GET', '/')
        assert identity['version'] == '1.19.2'
        report.update(server_identity=identity, server_binary_sha256=sha(SERVER),
                      server_pid=server.process.pid, server_port=server.port)
        report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Encode queries once per model, identically reused across layouts/modes.
        qvectors = {}
        qtimings = {}
        for model, encoder in encoders.items():
            vectors, durations = [], []
            for query in queries:
                start = time.perf_counter()
                vectors.append(encoder.encode([query['query']], 'query')[0])
                durations.append((time.perf_counter() - start) * 1000)
            qvectors[model], qtimings[model] = np.asarray(vectors), durations
            np.save(run / (model + '-query-vectors.npy'), qvectors[model])
        for name, model, layout, docs in layouts:
            encoder = encoders[model]
            start = time.perf_counter()
            vectors = encoder.encode([d['text'] for d in docs], 'passage')
            embedding_ms = (time.perf_counter() - start) * 1000
            np.save(run / (name + '-passage-vectors.npy'), vectors)
            sqlite_backend = sqlite3.connect(run / (name + '-sqlite.db'))
            sqlite_backend.execute('CREATE TABLE documents(id INTEGER PRIMARY KEY, document_id TEXT, parent_id TEXT, source TEXT, start INTEGER, end INTEGER, text TEXT, vector TEXT)')
            sqlite_backend.executemany('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)', [
                (i + 1, d['id'], d.get('parent_id', d['id']), d['source'], d['start'], d['end'],
                 d['text'], json.dumps(vectors[i].tolist())) for i, d in enumerate(docs)])
            sqlite_backend.commit()
            assert sqlite_backend.execute('SELECT count(*) FROM documents').fetchone()[0] == len(docs)
            fresh_connection(server)  # Expensive embedding invalidates readiness keepalive.
            start = time.perf_counter()
            server.request('PUT', '/collections/' + name, config)
            for offset in range(0, len(docs), 128):
                server.request('PUT', '/collections/' + name + '/points?wait=true', {'points': [
                    {'id': i + 1, 'vector': vectors[i].tolist(), 'payload': {'document_id': docs[i]['id'],
                     'parent_id': docs[i].get('parent_id', docs[i]['id'])}}
                    for i in range(offset, min(offset + 128, len(docs)))]})
            deadline = time.monotonic() + 120
            while True:
                collection = server.request('GET', '/collections/' + name)['result']
                if collection['status'] == 'green' and collection.get('indexed_vectors_count') == len(docs):
                    break
                if time.monotonic() > deadline:
                    save(run / (name + '-index-timeout.json'), collection)
                    raise TimeoutError('actual HNSW index did not cover all points')
                time.sleep(.2)
            report['collections'].append(dict(name=name, **collection))
            report['variant_timings'].append(dict(name=name, embedding_ms=embedding_ms,
                                                  seed_index_ms=(time.perf_counter() - start) * 1000))
            readback = server.request('POST', '/collections/' + name + '/points', {
                'ids': list(range(1, len(docs) + 1)), 'with_payload': True, 'with_vector': True})['result']
            readback.sort(key=lambda p: p['id'])
            assert len(readback) == len(docs)
            error = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - vectors)))
            assert error < 1e-6
            save(run / (name + '-server-readback.json'), {'points': readback, 'max_abs_error': error})
            for qi, query in enumerate(queries):
                qvector = qvectors[model][qi]
                query_hash = hashlib.sha256(qvector.tobytes()).hexdigest()
                lexical_start = time.perf_counter()
                lexical = tq.lexical_search(db, query['query'])
                lexical_ms = (time.perf_counter() - lexical_start) * 1000
                exact_points = None
                for mode, exact, ef in MODES:
                    start = time.perf_counter()
                    if mode == 'sqlite_exact':
                        stored = sqlite_backend.execute('SELECT id,vector FROM documents ORDER BY id').fetchall()
                        matrix = np.asarray([json.loads(v) for _, v in stored], dtype=np.float64)
                        scores = np.einsum('ij,j->i', matrix, qvector)
                        indices = sorted(range(len(docs)), key=lambda i: (-float(scores[i]), docs[i]['id']))[:60]
                        response = {'result': {'points': [dict(id=i + 1, score=float(scores[i]),
                            payload=dict(document_id=docs[i]['id'], parent_id=docs[i].get('parent_id', docs[i]['id'])))
                            for i in indices]}, 'engine': 'SQLite disk JSON float64 exact; NOT production Rust CLI'}
                    else:
                        response = server.request('POST', '/collections/' + name + '/points/query', {
                            'query': qvector.tolist(), 'limit': 60, 'with_payload': True, 'with_vector': False,
                            'params': {'exact': exact, 'hnsw_ef': ef}})
                    query_ms = (time.perf_counter() - start) * 1000
                    resolution_started = time.perf_counter()
                    points = response['result']['points']
                    semantic = rank_parents(points, docs)
                    ordered_points = sorted(points, key=lambda p: (-p['score'], docs[p['id'] - 1]['id']))
                    best = {}
                    for p in ordered_points:
                        doc = docs[p['id'] - 1]
                        best.setdefault(doc.get('parent_id', doc['id']), doc)
                    if exact:
                        exact_points = {p['id'] for p in points}
                    else:
                        ann_comparisons.append(dict(variant=name, query_id=query['id'], mode=mode,
                            strict_recall60=len(exact_points & {p['id'] for p in points}) / len(exact_points)))
                    fusion_start = time.perf_counter()
                    fused = tq.fuse(semantic, lexical)
                    fusion_ms = (time.perf_counter() - fusion_start) * 1000
                    resolution_ms = (fusion_start - resolution_started) * 1000
                    raw.append(dict(variant=name, model=model, query_id=query['id'], mode=mode,
                                    query_vector_sha256=query_hash, response=response, semantic_parents=semantic,
                                    lexical_parents=lexical, hybrid_parents=fused,
                                    timing_ms=dict(query_encode=qtimings[model][qi], lexical=lexical_ms,
                                                   backend_roundtrip=query_ms, parent_resolution=resolution_ms,
                                                   fusion=fusion_ms),
                                    rrf_scores={n: sum(1 / (60 + c.index(n) + 1) for c in (semantic, lexical)
                                                       if n in c) for n in fused}))
                    for ranking, ids in [('semantic', semantic), ('hybrid', fused)]:
                        hydrate_started = time.perf_counter()
                        row = review_row(query, ids[:5], name, mode, ranking, best, corpus, sources)
                        json.dumps(row, ensure_ascii=False)
                        hydrate_ms = (time.perf_counter() - hydrate_started) * 1000
                        row['timing_ms'] = dict(raw[-1]['timing_ms'], hydrate_serialize=hydrate_ms)
                        row['timing_ms']['attributed_pipeline'] = (qtimings[model][qi] + lexical_ms + query_ms +
                            resolution_ms + (fusion_ms if ranking == 'hybrid' else 0) + hydrate_ms)
                        rows.append(row)
            sqlite_backend.close()
            sqlite_backend = None
            save(run / 'raw-server-rankings.json', raw)
            save(run / 'raw-results.json', rows)
        fresh_connection(server)
        save(run / 'telemetry.json', server.request('GET', '/telemetry?details_level=3'))
        for variant in variants:
            for mode, _, _ in MODES:
                for ranking in ('semantic', 'hybrid'):
                    for split in ('development', 'holdout'):
                        group = [r for r in rows if r['variant'] == variant['name'] and r['mode'] == mode
                                 and r['ranking'] == ranking and r['split'] == split]
                        summary = dict(variant=variant['name'], mode=mode, ranking=ranking, split=split,
                                       **tq.summarize(group))
                        summary['p1'] = statistics.mean(r['p1'] for r in group if r['relevant'])
                        summary['p3'] = statistics.mean(r['p3'] for r in group if r['relevant'])
                        summary['p5'] = statistics.mean(r['p5'] for r in group if r['relevant'])
                        summary['no_answer_false_acceptance_count'] = sum(
                            r['metrics']['no_answer_false_acceptance'] or 0 for r in group)
                        summary['backend_roundtrip_p50_ms'] = statistics.median(r['timing_ms']['backend_roundtrip'] for r in group)
                        summary['attributed_pipeline_p50_ms'] = statistics.median(r['timing_ms']['attributed_pipeline'] for r in group)
                        summary['query_encode_p50_ms'] = statistics.median(r['timing_ms']['query_encode'] for r in group)
                        report['summaries'].append(summary)
        report['ann_vs_exact'] = ann_comparisons
        report['at_token_limit'] = {k: e.truncated for k, e in encoders.items()}
        primary_pair = []
        for q in queries:
            pair = {mode: next(r for r in rows if r['id'] == q['id'] and r['variant'] == 'parent-minilm'
                              and r['mode'] == mode and r['ranking'] == 'hybrid')
                    for mode in ('sqlite_exact', 'ann128')}
            left, right = pair['sqlite_exact'], pair['ann128']
            primary_pair.append(dict(query_id=q['id'], query=q['query'], split=q['split'],
                relevant=q['relevant'], sqlite_top5=left['top5'], qdrant_top5=right['top5'],
                ordered_top5_equal=left['top5'] == right['top5'],
                sqlite_metrics=left['metrics'], qdrant_metrics=right['metrics'],
                sqlite_precision={k: left[k] for k in ('p1','p3','p5')},
                qdrant_precision={k: right[k] for k in ('p1','p3','p5')},
                sqlite_timing=left['timing_ms'], qdrant_timing=right['timing_ms'],
                sqlite_passages=left['snippets_sources'], qdrant_passages=right['snippets_sources']))
        report['primary_pair_per_query'] = primary_pair
        save(run / 'primary-pair-per-query.json', primary_pair)
        write_review(run, rows)
    except Exception as error:
        save(run / 'failure.json', {'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        db.close()
        if sqlite_backend is not None:
            sqlite_backend.close()
        report['cleanup'] = server.close()
        after = {name: sha(REPO / name) for name in before}
        report['sources_stable'] = before == after
        save(run / 'source-after.json', after)
        save(run / 'partial-report.json', report)
    assert report['sources_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    # Independently read exact cleanup target and probe owned port after shutdown.
    assert json.loads((run / 'cleanup.json').read_bytes()) == report['cleanup']
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1', server.port)) != 0
    save(run / 'report.json', report)
    receipt = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', receipt)
    assert all(sha(run / name) == expected for name, expected in receipt.items())
    print(json.dumps({'run': run.as_posix(), 'report_sha256': sha(run / 'report.json'),
                      'cleanup': report['cleanup']}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    experiment()
