"""Frozen candidate/abstention diagnostic, isolated from all runtime workers."""
import re
import sqlite3


def literal_tokens(text):
    """Whole identifiers and operators, never negate or split underscore names."""
    return list(dict.fromkeys(re.findall(r'\w+(?:\.\w+)*|!=|==|<=|>=|&&|\|\||->|=>|[!<>=+*/%-]', text.casefold())))


def exact_index(documents):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE VIRTUAL TABLE exact USING fts5(id UNINDEXED, text)')
    db.executemany('INSERT INTO exact VALUES (?, ?)', [(d['id'], ' '.join('x' + t.encode().hex() for t in literal_tokens(d['text']))) for d in documents])
    return db


def exact_search(db, query):
    # Only syntactically technical atoms: natural words stay on incumbent OR branch.
    terms = [t for t in literal_tokens(query) if '_' in t or '.' in t or not re.fullmatch(r'\w+', t)]
    if not terms:
        return []
    expression = ' OR '.join('"x' + t.encode().hex() + '"' for t in terms)
    return [r[0] for r in db.execute('SELECT id FROM exact WHERE exact MATCH ? ORDER BY bm25(exact), id LIMIT 20', (expression,))]


def quota_pool(dense, lexical, exact):
    # Reservation prevents an unmatched dense proof being demoted by branch overlap.
    chosen = list(dict.fromkeys(exact[:2] + dense[:10] + lexical[:8]))
    for name in dense + lexical + exact:
        if name not in chosen:
            chosen.append(name)
        if len(chosen) >= 20:
            break
    return chosen[:20]


def source_headings(text):
    """Uniform Markdown ATX, RST/setext underline and YAML title scanner."""
    lines = text.splitlines(keepends=True)
    out, offset = [], 0
    for i, line in enumerate(lines):
        stripped = line.rstrip('\r\n')
        atx = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', stripped)
        yaml = re.match(r'^title:\s*(.+)$', stripped) if text.startswith('---\n') else None
        underline = (i + 1 < len(lines) and re.fullmatch(r'[=~^`:+#*-]{3,}\s*', lines[i + 1]) and stripped.strip())
        if atx or yaml or underline:
            title = atx[2] if atx else yaml[1] if yaml else stripped
            start = offset + stripped.find(title)
            out.append({'start': start, 'end': start + len(title), 'text': title,
                        'level': len(atx[1]) if atx else 1 if yaml or lines[i + 1].startswith('=') else 2})
        offset += len(line)
    return out


def structural_chunks(documents, source_texts, encoder):
    """Lossless body slices; context consumes only remaining budget, never proof."""
    headings = {name: source_headings(text) for name, text in source_texts.items()}
    chunks = []
    for doc in documents:
        assert source_texts[doc['source']][doc['start']:doc['end']] == doc['text']
        offset = 0
        while offset < len(doc['text']):
            remaining = doc['text'][offset:]
            low, high = 1, len(remaining)
            limit = encoder.manifest['max_length']
            while low < high:
                mid = (low + high + 1) // 2
                if encoder.token_count(remaining[:mid], 'passage') < limit:
                    low = mid
                else:
                    high = mid - 1
            body = remaining[:low]
            assert encoder.token_count(body, 'passage') < limit
            start = doc['start'] + offset
            stack = []
            for heading in headings[doc['source']]:
                if heading['start'] > start:
                    break
                while stack and stack[-1]['level'] >= heading['level']:
                    stack.pop()
                stack.append(heading)
            encoded = body
            # A suffix cannot push original body tokens out of a prefix-truncating model.
            for heading in reversed(stack):
                candidate = encoded + '\n' + heading['text']
                if encoder.token_count(candidate, 'passage') < limit:
                    encoded = candidate
            chunks.append({'id': f"{doc['id']}::s{offset}", 'parent_id': doc['id'],
                           'source': doc['source'], 'start': start, 'end': start + low,
                           'text': body, 'encoded_text': encoded, 'headings': stack})
            offset += low
    return chunks


def fit_abstention(rows):
    """Experimental development answerability threshold, NOT probability fitting."""
    import statistics
    if not rows or any(r['split'] != 'development' for r in rows):
        raise ValueError('development only')
    yes, no = [r for r in rows if r['relevant']], [r for r in rows if not r['relevant']]
    if not yes or not no:
        raise ValueError('both answerability classes required')
    candidates = {r['signal'] for r in rows} | {float('-inf'), float('inf')}
    def balanced(t):
        return (statistics.mean(r['signal'] >= t for r in yes) + statistics.mean(r['signal'] < t for r in no)) / 2
    return max(candidates, key=lambda t: (balanced(t), t))


def experiment(run):
    """Finite paired real-server diagnostic, no runtime integration or installs."""
    import datetime
    import hashlib
    import json
    from pathlib import Path
    import platform
    import shutil
    import statistics
    import sys
    import time
    import numpy as np
    import psutil
    from tokenizers import Tokenizer
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import CrossEncoder, lexical_or
    from retrieval_budget_benchmark import eligibility, select_candidates, present, proof_audit
    from server_benchmark import Server, SERVER, save, sha, percentile
    repo = Path(__file__).resolve().parents[1]
    run = Path(run).resolve()
    if not run.is_relative_to(repo / 'artifacts/relevance-candidate') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('NEW owned non-symlink relevance-candidate path required')
    run.mkdir(parents=True, exist_ok=False)
    snapshot = paired.SNAPSHOT
    previous = repo / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3'
    model = previous.parent / 'reranker-model'
    frozen = json.loads((snapshot / 'freeze.json').read_bytes())
    for name, expected in frozen['files'].items():
        assert sha(snapshot / name) == expected, name
    prior = json.loads((previous / 'freeze.json').read_bytes())
    for name, expected in prior['inputs'].items():
        if '/models/' in name or '/reranker-model/' in name or name.endswith('qdrant.exe'):
            assert sha(repo / name) == expected, name
    corpus = json.loads((snapshot / 'corpus.json').read_bytes())
    queries = json.loads((snapshot / 'judgments.json').read_bytes())
    sources = json.loads((snapshot / 'source-receipts.json').read_bytes())
    texts = {name: (snapshot / 'sources' / (name + '.txt')).read_text(encoding='utf-8') for name in sources}
    documents = {d['id']: d for d in corpus}
    for d in corpus:
        assert texts[d['source']][d['start']:d['end']] == d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest() == d['sha256']
    families = ['or_rrf', 'quota_or', 'quota_exact', 'split_quota_exact', 'heading_quota_exact']
    variants = [(f, b) for f in families for b in (5, 20)]
    config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False}, 'shard_number': 1,
              'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
              'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
    inputs = [Path(__file__), repo / 'tests/relevance_candidate_experiment_test.py', SERVER,
              repo / 'requirements-hybrid.lock', repo / '.git/index', snapshot / 'freeze.json']
    inputs += [repo / 'tools' / n for n in ('technical_quality.py', 'qdrant_quality.py', 'retrieval_ablation.py', 'retrieval_budget_benchmark.py', 'server_benchmark.py', 'hybrid_dataset.py')]
    inputs += [snapshot / n for n in frozen['files']]
    inputs += [previous / n for n in ('freeze.json', 'raw-results.json', 'original-vectors.npy', 'query-vectors.npy')]
    receipt = json.loads((model / 'receipt.json').read_bytes())
    inputs += [model / n for n in receipt['files']] + [model / 'receipt.json']
    inputs += [repo / 'artifacts/models/minilm' / n for n in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    before = {p.relative_to(repo).as_posix(): sha(p) for p in inputs}
    for name, data in [('corpus.json', corpus), ('judgments.json', queries), ('source-receipts.json', sources)]:
        save(run / name, data)
    (run / 'code').mkdir()
    for p in inputs:
        if p.suffix == '.py':
            shutil.copyfile(p, run / 'code' / p.name)
    freeze = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': before,
        'variants': variants, 'repeats': 2, 'collection_config': config,
        'scope': 'PERSONAL Qdrant goal 1-2 months; not runtime integration or bank qualification',
        'labels': 'REUSED DIAGNOSTIC; incomplete selected labels; UNKNOWN unchanged; no 90% acceptance',
        'candidates': 'OR-RRF baseline dense60+OR20 RRF60 pool20. quota_or reserves dense10+OR8 fills dense-first to20. quota_exact additionally reserves up to2 exact technical atoms FIRST. No translation, query-specific expansion or labels.',
        'structure': 'Uniform source ATX/RST/setext/YAML headings, all parents split below128 tokens with original offsets. split control body only; heading variant appends fitting suffix only, no body displacement. Not late chunking. Point top60 can yield fewer parents; no refill.',
        'gate': 'Existing raw source Python family gate AFTER family pool20 BEFORE budget/reranking AND at presentation; UNKNOWN rejected on explicit version requests, otherwise NOT_ASSESSED.',
        'reranker': 'Pinned mMARCO ONNX CPU 2/1 batch4 longest-first512 raw logits, unchanged parent evidence; top5 no tail refill',
        'abstention': 'OPTIONAL separately labeled rule on PRESPECIFIED quota_exact_20 only. Fit max-logit threshold maximizing balanced answerability accuracy on block0 development, higher threshold ties. Save calibration before first reused holdout request. No pipeline selection. Not probability calibration or semantic precision.',
        'timing': 'Two independent E2E repeats encode/HTTP/lexical/gates/rerank/citations/JSON, reverse order repeat1. Dev before holdout. No shared-stage sums. Disk exports/hashes excluded. 600s measurement deadline.',
        'new_questions': False, 'artifact_inputs': {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}}
    save(run / 'freeze.json', freeze)
    report = {'run': str(run), 'freeze_sha256': sha(run / 'freeze.json'), 'environment': {'python': sys.version, 'platform': platform.platform()}, 'blockers': []}
    start = time.perf_counter()
    encoder = tq.ResidentEncoder(repo / 'artifacts/models/minilm')
    reranker = CrossEncoder(model)
    report['model_load_hash_validation_ms'] = (time.perf_counter() - start) * 1000
    report['environment'].update(encoder.runtime)
    report['first_inference_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert freeze['utc'] <= report['first_inference_utc']
    children = structural_chunks(corpus, texts, encoder)
    save(run / 'structural-children.json', children)
    report['structural_children'] = len(children)
    report['heading_suffix_added'] = sum(c['text'] != c['encoded_text'] for c in children)
    report['source_heading_counts'] = {n: len(source_headings(t)) for n, t in texts.items()}
    vectors = {'original': np.load(previous / 'original-vectors.npy')}
    start = time.perf_counter()
    for name, field in [('split', 'text'), ('heading', 'encoded_text')]:
        vectors[name] = encoder.encode([c[field] for c in children], 'passage')
    report['offline_structural_encoding_ms'] = (time.perf_counter() - start) * 1000
    for name, matrix in vectors.items():
        np.save(run / (name + '-vectors.npy'), matrix)
    expected_queries = np.load(previous / 'query-vectors.npy')
    expected_query = {q['id']: v for q, v in zip(queries, expected_queries)}
    np.save(run / 'query-vectors.npy', expected_queries)
    old = {r['id']: r for r in json.loads((previous / 'raw-results.json').read_bytes()) if r['variant'] == 'or_rrf' and r['mode'] == 'ann128'}
    tokenizer = Tokenizer.from_file(str(repo / 'artifacts/models/minilm/tokenizer.json'))
    tokenizer.no_padding()
    tokenizer.no_truncation()
    visibility = {}
    for d in corpus:
        full = tokenizer.encode(encoder.manifest['passage_prefix'] + d['text'])
        limited = encoder.tokenizer.encode(encoder.manifest['passage_prefix'] + d['text'])
        end = max((b for a, b in limited.offsets), default=0)
        visibility[d['id']] = {'tokens': len(full.ids), 'visible_end_relative': end,
            'omitted_text': d['text'][end:], 'visible_text': d['text'][:end],
            'technical_atoms': [t for t in literal_tokens(d['text']) if '_' in t or '.' in t or not re.fullmatch(r'\w+', t)],
            'visible_subtokens': limited.tokens, 'visible_offsets': limited.offsets}
    save(run / 'embedding-visibility.json', visibility)
    server, db, exact = Server(run), tq.lexical_index(corpus), exact_index(corpus)
    rows, calibration = [], None
    try:
        server.start()
        report['server_identity'] = server.request('GET', '/')
        assert report['server_identity']['version'] == '1.19.2'
        for name, matrix in vectors.items():
            docs = corpus if name == 'original' else children
            server.request('PUT', '/collections/' + name, config)
            server.request('PUT', '/collections/' + name + '/points?wait=true', {'points': [
                {'id': i + 1, 'vector': v.tolist(), 'payload': {'document_id': d['id'], 'parent_id': d.get('parent_id', d['id'])}}
                for i, (v, d) in enumerate(zip(matrix, docs))]})
            deadline = time.monotonic() + 90
            while True:
                info = server.request('GET', '/collections/' + name)['result']
                if info['status'] == 'green' and info['indexed_vectors_count'] == len(docs):
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('index incomplete ' + name)
                time.sleep(.2)
            readback = server.request('POST', '/collections/' + name + '/points', {'ids': list(range(1, len(docs) + 1)), 'with_vector': True, 'with_payload': True})['result']
            readback.sort(key=lambda p: p['id'])
            assert len(readback) == len(docs)
            assert all(p['payload']['document_id'] == docs[i]['id'] for i, p in enumerate(readback))
            error = float(np.max(np.abs(np.asarray([p['vector'] for p in readback]) - matrix)))
            assert error < 1e-6
            save(run / (name + '-readback.json'), {'collection': info, 'points': readback, 'max_abs_error': error})
        encoder.encode([queries[0]['query']], 'query')
        reranker.rank(queries[0]['query'], corpus[:4])
        measurement_start = time.monotonic()
        with (run / 'raw-results.jsonl').open('w', encoding='utf-8') as output, (run / 'raw-server.jsonl').open('w', encoding='utf-8') as raw:
            for repeat in range(2):
                for split in ('development', 'holdout'):
                    if split == 'holdout' and repeat == 0:
                        dev = [r for r in rows if r['variant'] == 'quota_exact_20' and r['split'] == 'development']
                        calibration = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'threshold': fit_abstention(dev),
                            'pipeline': 'quota_exact_20', 'fit_query_ids': [r['id'] for r in dev],
                            'fit_signals': [{'id': r['id'], 'signal': r['signal'], 'answerable': bool(r['relevant'])} for r in dev],
                            'variant_freeze_sha256': sha(run / 'freeze.json'), 'before_first_holdout': True}
                        save(run / 'calibration-freeze.json', calibration)
                    order = [q for q in queries if q['split'] == split]
                    if repeat:
                        order.reverse()
                    for query in order:
                        for family, budget in (variants if repeat == 0 else reversed(variants)):
                            if time.monotonic() - measurement_start > 600:
                                raise TimeoutError('bounded measurement deadline exceeded')
                            begin = time.perf_counter()
                            vector = encoder.encode([query['query']], 'query')[0]
                            encoded = time.perf_counter()
                            assert np.array_equal(vector, expected_query[query['id']])
                            collection = 'heading' if family.startswith('heading') else 'split' if family.startswith('split') else 'original'
                            dense_docs = corpus if collection == 'original' else children
                            response = server.request('POST', '/collections/' + collection + '/points/query', {
                                'query': vector.tolist(), 'limit': 60, 'with_payload': True, 'with_vector': False,
                                'params': {'exact': False, 'hnsw_ef': 128}})
                            fetched = time.perf_counter()
                            dense = paired.rank_parents(response['result']['points'], dense_docs)
                            lexical = lexical_or(db, query['query'])
                            atoms = exact_search(exact, query['query']) if 'exact' in family else []
                            pool = tq.fuse(dense, lexical)[:20] if family == 'or_rrf' else quota_pool(dense, lexical, atoms)
                            states = eligibility(query['query'], documents, sources)
                            candidates = select_candidates(pool, states, True, budget)
                            selected = time.perf_counter()
                            ranked, logits = reranker.rank(query['query'], [documents[n] for n in candidates]) if candidates else ([], {})
                            reranked = time.perf_counter()
                            final_states = eligibility(query['query'], documents, sources)
                            top5 = present([n for n in ranked if n in candidates], final_states, True)
                            row = paired.review_row(query, top5, f'{family}_{budget}', 'ann128', family, documents, corpus, sources)
                            row.update(repeat=repeat, family=family, budget=budget, pool20=pool, candidates=candidates,
                                ranked=ranked, logits=logits, signal=max(logits.values(), default=-1e30), eligibility=final_states,
                                dense=dense, lexical=lexical, exact=atoms,
                                query_vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),
                                proof_audit=proof_audit(query['relevant'], states, pool, candidates, top5),
                                candidate_recall=len(set(pool) & set(query['relevant'])) / len(query['relevant']) if query['relevant'] else None,
                                rerank_candidate_recall=len(set(candidates) & set(query['relevant'])) / len(query['relevant']) if query['relevant'] else None,
                                candidate_judgments={n: 'selected relevant' if n in query['relevant'] else 'explicit incompatible' if n in query['incompatible'] else 'UNKNOWN' for n in candidates})
                            for snippet in row['snippets_sources']:
                                snippet['sha256'] = documents[snippet['parent_id']]['sha256']
                            json.dumps(row, ensure_ascii=False)
                            end = time.perf_counter()
                            row['timing_ms'] = {'encode': (encoded - begin) * 1000, 'http': (fetched - encoded) * 1000,
                                'lexical_fusion_gate': (selected - fetched) * 1000, 'rerank': (reranked - selected) * 1000,
                                'citation_final_gate': (end - reranked) * 1000, 'e2e': (end - begin) * 1000}
                            rows.append(row)
                            output.write(json.dumps(row, ensure_ascii=False) + '\n')
                            raw.write(json.dumps({'id': query['id'], 'variant': row['variant'], 'repeat': repeat, 'response': response}) + '\n')
                            output.flush()
                            raw.flush()
                    print(json.dumps({'repeat': repeat, 'split': split, 'rows': len(rows)}), flush=True)
        report['measurement_seconds'] = time.monotonic() - measurement_start
        save(run / 'raw-results.json', rows)
        assert len(rows) == len(queries) * len(variants) * 2 == 640
        unique = [r for r in rows if r['repeat'] == 0]
        report['baseline_pool_parity'] = sum(r['pool20'] == old[r['id']]['pool20'] for r in unique if r['variant'] == 'or_rrf_20')
        assert report['baseline_pool_parity'] == len(queries)
        stable = {}
        for row in rows:
            assert row['metrics'] == tq.score(row['top5'], row)
            assert all(not row['eligibility'][n].startswith('REJECT') for n in row['candidates'] + row['top5'])
            key = (row['id'], row['variant'])
            if key in stable:
                assert stable[key] == row['top5']
            stable[key] = row['top5']
            for s in row['snippets_sources']:
                d = documents[s['parent_id']]
                assert s['text'] == texts[d['source']][d['start']:d['end']]
                assert s['sha256'] == hashlib.sha256(s['text'].encode()).hexdigest()
        report.update(rows=len(rows), stable_ranks=True, gate_violations=0)
        report['summaries'] = []
        for family, budget in variants:
            for split in ('development', 'holdout'):
                group = [r for r in unique if r['variant'] == f'{family}_{budget}' and r['split'] == split]
                yes = [r for r in group if r['relevant']]
                times = [r['timing_ms']['e2e'] for r in rows if r['variant'] == f'{family}_{budget}' and r['split'] == split]
                report['summaries'].append({'variant': f'{family}_{budget}', 'split': split, 'questions': len(group), 'answerable': len(yes),
                    **{k: statistics.mean(r[k] for r in yes) for k in ('p1', 'p3', 'p5', 'candidate_recall', 'rerank_candidate_recall')},
                    **{k: statistics.mean(r['metrics'][k] for r in yes) for k in ('mrr', 'recall_at_5')},
                    'incompatible_top5': sum(len(r['incompatible_returned']) for r in group),
                    'unknown_top5': sum(len(r['unjudged']) for r in group),
                    'noanswer_false_accepts': sum(bool(r['top5']) for r in group if not r['relevant']),
                    'e2e_p50_ms': statistics.median(times), 'e2e_p95_ms': percentile(times, .95)})
        abstention = []
        for row in unique:
            if row['variant'] != 'quota_exact_20':
                continue
            accepted = bool(row['top5']) and row['signal'] >= calibration['threshold']
            abstention.append(paired.review_row(row, row['top5'] if accepted else [], 'EXPERIMENTAL_DEV_ONLY_ABSTENTION', 'ann128', 'quota_exact_20', documents, corpus, sources) | {'accepted': accepted, 'signal': row['signal']})
        save(run / 'experimental-abstention.json', abstention)
        report['abstention'] = []
        for split in ('development', 'holdout'):
            group = [r for r in abstention if r['split'] == split]
            accepted = [r for r in group if r['accepted']]
            report['abstention'].append({'split': split, 'queries': len(group), 'accepted': len(accepted), 'coverage': len(accepted) / len(group),
                'selected_top1_precision_among_accepted': sum(bool(r['top5']) and r['top5'][0] in r['relevant'] for r in accepted) / len(accepted) if accepted else None,
                'answerable_rejections': sum(bool(r['relevant']) and not r['accepted'] for r in group),
                'noanswer_false_accepts': sum(not r['relevant'] and r['accepted'] for r in group),
                'explicit_incompatible_top5': sum(len(r['incompatible_returned']) for r in group),
                'unknown_top5': sum(len(r['unjudged']) for r in group)})
        diagnostics = []
        for row in unique:
            diagnostics.append({'id': row['id'], 'query': row['query'], 'variant': row['variant'],
                'proofs': {n: {**{branch + '_rank': row[branch].index(n) + 1 if n in row[branch] else None for branch in ('dense', 'lexical', 'exact', 'pool20', 'top5')},
                    'raw_text': documents[n]['text'], 'source': documents[n]['source'], 'visibility': visibility[n]} for n in row['relevant']},
                'candidate_errors': [{'id': n, 'status': row['candidate_judgments'][n], 'text': documents[n]['text'], 'source': documents[n]['source'], 'logit': row['logits'][n]} for n in row['candidates'] if n not in row['relevant']]})
        save(run / 'candidate-errors-and-proofs.json', diagnostics)
        lines = ['# Reused diagnostic per-query evidence', '', 'UNKNOWN remains unjudged. Pk selected hits/k, not exhaustive truth. No 90% acceptance.', '']
        for query in queries:
            lines += ['## ' + query['id'], '', query['query'], '', 'Selected positives: ' + str(query['relevant']) + '; incompatible: ' + str(query['incompatible']), '']
            baseline = next(r for r in unique if r['id'] == query['id'] and r['variant'] == 'or_rrf_20')
            for row in [r for r in unique if r['id'] == query['id']]:
                lines += [f"### {row['variant']}: P1/P3/P5={row['p1']:.4f}/{row['p3']:.4f}/{row['p5']:.4f}; MRR5={row['metrics']['mrr']}; R5={row['metrics']['recall_at_5']}",
                    'Pool recall: ' + str(row['candidate_recall']) + '; proofs: ' + json.dumps(row['proof_audit']),
                    'vs OR20 added=' + str(sorted(set(row['top5']) - set(baseline['top5']))) + '; removed=' + str(sorted(set(baseline['top5']) - set(row['top5']))),
                    'E2E ms: ' + str([r['timing_ms']['e2e'] for r in rows if r['id'] == row['id'] and r['variant'] == row['variant']]), '']
                for rank, s in enumerate(row['snippets_sources'], 1):
                    lines += [f"{rank}. **{s['parent_id']}** {s['status']} [{s['source']}]({s['url']}) [{s['start']},{s['end']}) SHA256={s['sha256']}", '', '> ' + s['snippet'].replace('\n', '\n> '), '']
            abst = next(r for r in abstention if r['id'] == query['id'])
            lines += ['Experimental abstention accepted=' + str(abst['accepted']) + '; output=' + str(abst['top5']), '']
        (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        report.update(encoder_recipe=encoder.manifest, reranker_recipe=reranker.receipt,
                      truncation_counters=encoder.truncated, reranker_at_limit_pairs=reranker.at_limit)
    except Exception as error:
        save(run / 'failure.json', {'error': repr(error), 'rows': len(rows)})
        raise
    finally:
        db.close()
        exact.close()
        report['cleanup'] = server.close()
        report['inputs_stable'] = all(sha(repo / name) == value for name, value in before.items())
        save(run / 'partial-report.json', report)
    assert report['inputs_stable']
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    assert not psutil.pid_exists(report['cleanup']['pid'])
    save(run / 'report.json', report)
    manifest = {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', manifest)
    assert all(sha(run / name) == expected for name, expected in manifest.items())
    print(json.dumps({'run': str(run), 'rows': report['rows'], 'cleanup': report['cleanup']}), flush=True)
    return report


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    import uuid
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    experiment(args.run or Path(__file__).resolve().parents[1] / 'artifacts/relevance-candidate' / uuid.uuid4().hex)
