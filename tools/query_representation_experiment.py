"""Offline, public-only query representation diagnostic; never a runtime default."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HISTORY = REPO / 'artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4'


def lexical_representation(query):
    """Project lexical query onto syntactically technical atoms, else keep original.

    No translation, language detector, domain dictionary or relevance labels.
    Original case and identifier punctuation are retained for audit. FTS5 still
    applies its existing tokenizer; this is not a new exact-identifier index.
    """
    atoms = re.findall(r'\w+(?:\.\w+)*', query, re.UNICODE)
    chosen = [a for a in atoms if '_' in a or '.' in a or any(c.isdigit() for c in a)
              or any(c.isupper() for c in a[1:])]
    return ' '.join(dict.fromkeys(chosen)) if chosen else query


def replay_request(query, dense, lexical, documents, states):
    """Fixed incumbent fusion/gates with citation-only field allowlist; no labels."""
    import hashlib
    from fusion_experiment import rank_fusion
    from retrieval_budget_benchmark import select_candidates, present
    order, scores = rank_fusion(dense, lexical, 'equal')
    pool = order[:20]
    candidates = select_candidates(pool, states, True, 20)
    top5 = present(candidates, states, True)
    evidence = []
    for name in top5:
        doc = {k: documents[name][k] for k in ('id', 'text', 'start', 'end', 'source', 'sha256')}
        if hashlib.sha256(doc['text'].encode()).hexdigest() != doc['sha256']:
            raise ValueError('source passage hash mismatch')
        evidence.append(doc)
    return dict(pool20=pool, candidates=candidates, top5=top5, evidence=evidence, fusion_scores=scores)


def run_experiment(run):
    """Frozen raw-dense-rank algorithm replay plus separately timed server smoke."""
    import datetime
    import json
    import shutil
    import statistics
    import time
    import numpy as np
    import technical_quality as tq
    from qdrant_quality import review_row, rank_parents
    from retrieval_ablation import lexical_or
    from retrieval_budget_benchmark import eligibility
    from multilingual_embedding_experiment import sha, verified_encoder
    from server_benchmark import Server, SERVER, save, percentile
    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/query-representation') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('new owned non-symlink directory required')
    run.mkdir(parents=True, exist_ok=False)
    load = lambda name: json.loads((HISTORY / name).read_bytes())
    manifest = load('evidence-sha256.json')
    for name, digest in manifest.items():
        assert sha(HISTORY / name) == digest, name
    corpus, queries, sources = load('corpus.json'), load('judgments.json'), load('source-receipts.json')
    historical = {r['id']: r for r in load('raw-results.json') if r['variant'] == 'minilm_parent128' and r['mode'] == 'ann128' and r['block'] == 0}
    assert len(historical) == len(queries) == 32
    documents = {d['id']: d for d in corpus}
    for d in corpus:
        text = (HISTORY / 'sources' / (d['source'] + '.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']] == d['text']
        assert sha(HISTORY / 'sources' / (d['source'] + '.txt'))
    inputs = [Path(__file__), REPO / 'tests/query_representation_experiment_test.py', SERVER]
    inputs += [REPO / 'tools' / n for n in ['fusion_experiment.py', 'retrieval_budget_benchmark.py', 'retrieval_ablation.py', 'technical_quality.py', 'qdrant_quality.py', 'multilingual_embedding_experiment.py', 'server_benchmark.py']]
    inputs += [HISTORY / 'evidence-sha256.json'] + [HISTORY / n for n in manifest]
    inputs += [REPO / 'artifacts/models/minilm' / n for n in ['manifest.json', 'model.onnx', 'tokenizer.json']]
    hashes = {p.relative_to(REPO).as_posix(): sha(p) for p in inputs}
    freeze = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), inputs=hashes,
        branches=['baseline', 'technical_projection'], model='existing pinned MiniLM parent128',
        acquisition=dict(dense=60, lexical=20, pool=20, present=5, rrf_k=60), reranker='NONE in BOTH branches',
        intervention='Only FTS5 query changed: retain underscores/dotted/numeric/internal-uppercase atoms, else original. No dictionary, translation, labels or rewritten dense query.',
        protocol='Raw saved ANN dense60 algorithm replay, two reverse-order repetitions. Same original-query source-version gate after pool and at presentation. No refill. Separate four actual query smoke requests, not full-server E2E benchmark.',
        labels='REUSED incomplete selected diagnostic, UNKNOWN not irrelevant; not 80%/90% certification',
        deadline_seconds=120)
    save(run / 'freeze.json', freeze)
    for name in ['corpus.json', 'judgments.json', 'source-receipts.json']:
        shutil.copyfile(HISTORY / name, run / name)
    shutil.copytree(HISTORY / 'sources', run / 'sources')
    (run / 'code').mkdir()
    for p in inputs[:10]:
        if p.suffix == '.py':
            shutil.copyfile(p, run / 'code' / p.name)
    save(run / 'raw-dense-control.json', historical)
    db, rows = tq.lexical_index(corpus), []
    started = time.monotonic()
    try:
        for block in range(2):
            for q in (queries if block == 0 else reversed(queries)):
                for branch in (freeze['branches'] if block == 0 else reversed(freeze['branches'])):
                    assert time.monotonic() - started < 120
                    t = time.perf_counter()
                    lexical_query = q['query'] if branch == 'baseline' else lexical_representation(q['query'])
                    lexical = lexical_or(db, lexical_query)
                    states = eligibility(q['query'], documents, sources)
                    result = replay_request(q['query'], historical[q['id']]['dense'], lexical, documents, states)
                    # Independently rerun presentation applicability, without query rewriting.
                    from retrieval_budget_benchmark import present
                    assert result['top5'] == present(result['candidates'], eligibility(q['query'], documents, sources), True)
                    row = review_row(q, result['top5'], 'minilm_parent128', 'algorithm_replay', branch, documents, corpus, sources)
                    row.update(result, block=block, branch=branch, lexical_query=lexical_query, lexical=lexical,
                               dense=historical[q['id']]['dense'], eligibility=states,
                               pool_recall=len(set(result['pool20']) & set(q['relevant'])) / len(q['relevant']) if q['relevant'] else None)
                    json.dumps(row, ensure_ascii=False)
                    row['replay_ms'] = (time.perf_counter() - t) * 1000
                    rows.append(row)
    finally:
        db.close()
    save(run / 'raw-results.json', rows)
    smoke = []
    encoder = verified_encoder(REPO / 'artifacts/models/minilm', cap=128)
    matrix = np.load(HISTORY / 'minilm_parent128-vectors.npy')
    server = Server(run)
    db = tq.lexical_index(corpus)
    try:
        server.start()
        identity = server.request('GET', '/')
        config = load('freeze.json')['collection_config']
        server.request('PUT', '/collections/query_representation', config)
        server.request('PUT', '/collections/query_representation/points?wait=true', {'points': [dict(id=i+1,vector=v.tolist(),payload=dict(parent_id=d['id'],document_id=d['id'])) for i,(v,d) in enumerate(zip(matrix,corpus))]})
        back = server.request('POST', '/collections/query_representation/points', {'ids':list(range(1,len(corpus)+1)), 'with_vector':True,'with_payload':True})['result']
        back.sort(key=lambda p:p['id'])
        assert len(back) == len(corpus)
        assert float(np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix))) < 1e-6
        assert all(p['payload']['document_id'] == corpus[i]['id'] for i,p in enumerate(back))
        save(run / 'smoke-readback.json', dict(identity=identity,points=back))
        for q in [queries[1], next(q for q in queries if q['id']=='holdout-09')]:
            for branch in freeze['branches']:
                t = time.perf_counter()
                vector = encoder.encode([q['query']], 'query')[0]
                response = server.request('POST','/collections/query_representation/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=128)))
                dense = rank_parents(response['result']['points'],corpus)
                lexical_query = q['query'] if branch=='baseline' else lexical_representation(q['query'])
                lexical = lexical_or(db,lexical_query)
                result = replay_request(q['query'],dense,lexical,documents,eligibility(q['query'],documents,sources))
                json.dumps(result,ensure_ascii=False)
                e2e = (time.perf_counter()-t)*1000
                replay = next(r for r in rows if r['id']==q['id'] and r['branch']==branch and r['block']==0)
                assert dense == replay['dense'] and result['top5'] == replay['top5']
                smoke.append(dict(id=q['id'],branch=branch,dense=dense,server_response=response,top5=result['top5'],e2e_ms=e2e))
    finally:
        db.close()
        cleanup = server.close()
    save(run / 'smoke.json',smoke)
    save(run / 'cleanup.json',cleanup)
    summaries=[]
    french = {'development-01','development-05','development-07','development-10','development-11','holdout-00','holdout-02','holdout-07','holdout-09'}
    for branch in freeze['branches']:
        unique = [r for r in rows if r['branch']==branch and r['block']==0]
        for subset in ['all','fr','en','technical_constraints']:
            selected = [r for r in unique if r['relevant'] and (subset=='all' or subset=='fr' and r['id'] in french or subset=='en' and r['id'] not in french or subset=='technical_constraints' and r['id'] in {'development-01','holdout-00','holdout-09'})]
            metrics = {k:statistics.mean(r[k] for r in selected) for k in ['p1','p3','p5','pool_recall']}
            metrics['r5'] = statistics.mean(len(set(r['top5']) & set(r['relevant']))/len(r['relevant']) for r in selected)
            metrics['mrr5'] = statistics.mean(next((1/i for i,n in enumerate(r['top5'],1) if n in r['relevant']),0) for r in selected)
            summaries.append(dict(branch=branch,subset=subset,n=len(selected),**metrics))
    matches=sum(r['top5']==historical[r['id']]['top5'] for r in rows if r['branch']=='baseline' and r['block']==0)
    assert matches == 32
    report=dict(task_status='OPEN_PENDING_PARENT_VERIFICATION',measurement='ALGORITHM_REPLAY plus separate actual smoke',
        replay_rows=len(rows),baseline_historical_matches=matches,smoke_requests=len(smoke),cleanup=cleanup,summaries=summaries,
        no_answer_false_accept={b:sum(bool(r['top5']) for r in rows if r['block']==0 and r['branch']==b and not r['relevant']) for b in freeze['branches']},
        unknown_top5={b:sum(n not in r['relevant'] and n not in r['incompatible'] for r in rows if r['block']==0 and r['branch']==b for n in r['top5']) for b in freeze['branches']},
        incompatible_top5={b:sum(n in r['incompatible'] for r in rows if r['block']==0 and r['branch']==b for n in r['top5']) for b in freeze['branches']},
        replay_latency={b:{'p50':statistics.median([r['replay_ms'] for r in rows if r['branch']==b]),'p95':percentile([r['replay_ms'] for r in rows if r['branch']==b],.95)} for b in freeze['branches']})
    save(run / 'report.json',report)
    changes=[]
    lines=['# Per-query review: REUSED diagnostics, not acceptance','', 'Algorithm replay latency excludes dense encoding/HTTP. Scores are rank scores, not confidence. No reranker or abstention in either branch.','']
    for q in queries:
        lines += ['## '+q['id']+' — '+q['query'],'']
        pair=[next(r for r in rows if r['id']==q['id'] and r['branch']==b and r['block']==0) for b in freeze['branches']]
        changes.append(dict(id=q['id'],baseline=pair[0]['top5'],intervention=pair[1]['top5'],p1_delta=pair[1]['p1']-pair[0]['p1'],lexical_query=pair[1]['lexical_query']))
        for r in pair:
            lines += [f"### {r['branch']}: lexical `{r['lexical_query']}`",f"P1/P3/P5={r['p1']}/{r['p3']}/{r['p5']}; pool recall={r['pool_recall']}; replay ms={r['replay_ms']:.3f}; no-answer nonempty={not bool(q['relevant']) and bool(r['top5'])}",'']
            for i,d in enumerate(r['evidence'],1):
                status='SELECTED' if d['id'] in q['relevant'] else 'INCOMPATIBLE' if d['id'] in q['incompatible'] else 'UNKNOWN'
                lines += [f"{i}. {d['id']} **{status}**, RRF={r['fusion_scores'][d['id']]['score']:.8f}; {sources[d['source']]['url']}; offsets [{d['start']},{d['end']}); SHA256 {d['sha256']}",'', '> '+d['text'][:600].replace('\n','\n> '),'']
    save(run / 'paired-changes.json',changes)
    (run / 'PER-QUERY-REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    assert all(sha(REPO / p)==digest for p,digest in hashes.items())
    save(run / 'evidence-sha256.json',{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file() and p.name not in {'evidence-sha256.json','server.log'} and 'storage' not in p.parts})
    return report


def verify_run(run):
    """Verify byte integrity, replay ranking and source-bound citations/metrics."""
    import json
    import hashlib
    import technical_quality as tq
    from multilingual_embedding_experiment import sha
    from retrieval_ablation import lexical_or
    from retrieval_budget_benchmark import eligibility
    run = Path(run)
    load = lambda name: json.loads((run / name).read_bytes())
    for name,digest in load('evidence-sha256.json').items():
        assert sha(run / name)==digest,name
    for name,digest in load('freeze.json')['inputs'].items():
        assert sha(REPO / name)==digest,name
    corpus,queries,sources=load('corpus.json'),load('judgments.json'),load('source-receipts.json')
    docs={d['id']:d for d in corpus}; qs={q['id']:q for q in queries}
    for d in corpus:
        text=(run/'sources'/(d['source']+'.txt')).read_text(encoding='utf-8')
        assert text[d['start']:d['end']]==d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest()==d['sha256']
    rows=load('raw-results.json')
    assert len(rows)==128
    assert len({(r['id'],r['branch'],r['block']) for r in rows})==128
    db=tq.lexical_index(corpus)
    try:
        for r in rows:
            q=qs[r['id']]
            query=q['query'] if r['branch']=='baseline' else lexical_representation(q['query'])
            assert r['lexical_query']==query and r['lexical']==lexical_or(db,query)
            result=replay_request(q['query'],r['dense'],r['lexical'],docs,eligibility(q['query'],docs,sources))
            assert all(r[k]==v for k,v in result.items())
            assert r['metrics']==tq.score(r['top5'],q)
    finally:
        db.close()
    assert load('cleanup.json')['process_exited'] and load('cleanup.json')['port_closed']
    return True


if __name__ == '__main__':
    import argparse
    import json
    import uuid
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify:
        print(verify_run(args.verify))
    else:
        run=REPO/'artifacts/query-representation'/('paired-'+uuid.uuid4().hex)
        print(json.dumps(run_experiment(run),indent=2))
        print('VERIFIED',verify_run(run),str(run))
