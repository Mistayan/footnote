"""Frozen fresh OR-RRF20 acquisition to the already-selected ranking callable.

No selection, label routing, corpus-specific transform, or new applicability gate.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))

import json,math,time,uuid,statistics,os,platform,hashlib
import fresh_retrieval_evaluation as fresh
SELECTED=ROOT/'artifacts/accuracy-iteration/ai-20261020-gte/selected-config.json'
SELECTED_SHA='33e5a3974892c743f8ed44c4790955f13f17cb3f829cc9794b57edbc81f4df78'
SNAPSHOT=ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'
BASE=ROOT/'artifacts/fresh-challenger-bridge'
VARIANTS=['mmarco_or_pool20','frozen_jina512_cutoff0']


def evaluate(run,split='development',candidate=None):
    import numpy as np
    import technical_quality as tq
    from qdrant_quality import fresh_connection,rank_parents
    from retrieval_ablation import CrossEncoder,lexical_or
    from server_benchmark import Server
    from tools.accuracy_iteration.evaluator import create_evaluator
    run=Path(run).resolve()
    if not run.is_relative_to(BASE):raise ValueError('new owned artifact run required')
    fresh.verify_snapshot(SNAPSHOT)
    fresh.authorize_split(SNAPSHOT,split)
    if split=='test' and candidate is None:raise ValueError('frozen declaration required')
    dec=fresh.load(candidate) if candidate else declaration()
    for n,h in dec['files'].items():
        if fresh.sha(ROOT/n)!=h:raise ValueError('changed candidate '+n)
    for n,h in dec['runtime_artifacts'].items():
        if fresh.sha(n)!=h:raise ValueError('changed runtime '+n)
    run.mkdir(parents=True,exist_ok=False)
    fresh.save(run/'candidate-declaration.json',dec)
    queries=fresh.queries_for(SNAPSHOT,split)
    corpus=fresh.load(SNAPSHOT/'corpus.json');sources=fresh.load(SNAPSHOT/'source-receipts.json');documents={d['id']:d for d in corpus}
    fresh.save(run/'execution-freeze.json',dict(utc=fresh.now(),before_inference=True,split=split,snapshot_freeze_sha256=fresh.sha(SNAPSHOT/'freeze.json'),declaration_sha256=fresh.sha(run/'candidate-declaration.json'),expected_rows=2*len(queries),variants=VARIANTS))
    report=dict(run=str(run),snapshot=str(SNAPSHOT),split=split,blockers=[],latency_contract='one actual shared acquisition per question; separate actual full-candidate reranks; acquisition+rerank is attributed pipeline sum, NOT independently measured E2E requests',selection='none; frozen Jina unchanged regardless of development/final metrics')
    rows=[];server=None;db=None;parity=[]
    try:
        start=time.perf_counter();encoder=tq.ResidentEncoder(ROOT/'artifacts/models/minilm');baseline=CrossEncoder(fresh.RANKER);selected=create_evaluator(SELECTED)
        report['model_load_validate_ms']=(time.perf_counter()-start)*1000;report['first_inference_utc']=fresh.now()
        assert fresh.load(run/'execution-freeze.json')['utc']<=report['first_inference_utc']
        start=time.perf_counter();matrix=encoder.encode([d['text'] for d in corpus],'passage');np.save(run/'passage-vectors.npy',matrix)
        report['passage_token_counts']=[encoder.token_count(d['text'],'passage') for d in corpus]
        db=tq.lexical_index(corpus);server=Server(run);server.start();report['server_identity']=server.request('GET','/');assert report['server_identity']['version']=='1.19.2'
        cfg={'vectors':{'size':384,'distance':'Cosine','on_disk':False},'shard_number':1,'hnsw_config':{'m':16,'ef_construct':100,'full_scan_threshold':10},'optimizers_config':{'indexing_threshold':1,'default_segment_number':1}}
        server.request('PUT','/collections/fresh',cfg)
        for offset in range(0,len(corpus),128):
            server.request('PUT','/collections/fresh/points?wait=true',{'points':[dict(id=i+1,vector=matrix[i].tolist(),payload={'document_id':corpus[i]['id']}) for i in range(offset,min(offset+128,len(corpus)))]})
        deadline=time.monotonic()+120
        while True:
            info=server.request('GET','/collections/fresh')['result']
            if info['status']=='green' and info['indexed_vectors_count']==len(corpus):break
            if time.monotonic()>deadline:raise TimeoutError('HNSW index incomplete')
            time.sleep(.2)
        back=server.request('POST','/collections/fresh/points',{'ids':list(range(1,len(corpus)+1)),'with_vector':True,'with_payload':True})['result'];back.sort(key=lambda p:p['id'])
        assert len(back)==len(corpus) and all(p['payload']['document_id']==corpus[i]['id'] for i,p in enumerate(back))
        error=float(np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix)));assert error<1e-6
        fresh.save(run/'server-readback.json',dict(collection=info,max_abs_error=error,points=back));report['offline_encoding_indexing_ms']=(time.perf_counter()-start)*1000
        previous={r['id']:r for r in fresh.load(ROOT/'artifacts/fresh-multilingual-evaluation/runs/eae052500e3f4ee6ba4bfabba50b3a9f/raw-results.json') if r['variant']=='mmarco_or_pool20'} if split=='development' else {}
        started=time.monotonic()
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
            for q in queries:
                if time.monotonic()-started>1200:raise TimeoutError('query workload1200s cap')
                fresh_connection(server);start=time.perf_counter();vector=encoder.encode([q['query']],'query')[0];encoded=time.perf_counter()
                response=server.request('POST','/collections/fresh/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params={'exact':False,'hnsw_ef':128}));searched=time.perf_counter()
                dense=rank_parents(response['result']['points'],corpus);lexical=lexical_or(db,q['query']);fused=tq.fuse(dense,lexical);pool=fused[:20];acquired=time.perf_counter()
                candidates=[documents[n] for n in pool]
                shared=dict(acquisition=(acquired-start)*1000,encode=(encoded-start)*1000,backend=(searched-encoded)*1000,lexical_fusion=(acquired-searched)*1000)
                if previous:
                    old=previous[q['id']];assert old['pool20']==pool;assert np.array_equal(old['query_vector'],vector)
                for variant in VARIANTS:
                    before=fresh.sha(SELECTED);rank_start=time.perf_counter()
                    if variant=='mmarco_or_pool20':
                        ranking,scores=baseline.rank(q['query'],candidates);result=dict(ranked=ranking,scores=scores,top5=ranking[:5],accepted=bool(ranking),score_kind='uncalibrated raw logit',pair_tokens=[])
                    else:result=invoke(selected,q['query'],candidates)
                    rank_end=time.perf_counter()
                    assert before==SELECTED_SHA==fresh.sha(SELECTED)
                    if split=='development' and variant!='mmarco_or_pool20':
                        direct=selected(q['query'],candidates)
                        equal=all(result[k]==direct[k] for k in ('ranked','scores','top5','accepted','pair_tokens','score_kind'))
                        assert equal;parity.append(dict(id=q['id'],exact_scores_ranks_presentation_equal=equal,candidate20=pool))
                    if previous and variant=='mmarco_or_pool20':
                        assert result['ranked']==previous[q['id']]['ranking']
                        assert result['scores']==previous[q['id']]['logits']
                    row=dict(q,variant=variant,top5=result['top5'],ranking=result['ranked'],logits=result['scores'],accepted=result['accepted'],score_kind=result['score_kind'],pair_tokens=result['pair_tokens'],pool20=pool,dense=dense,lexical=lexical,server_response=response,query_vector=vector.tolist(),constraints={'applicability_gate':'NONE baseline unchanged','threshold':0 if variant!='mmarco_or_pool20' else None,'pool_budget':20,'same_candidates_for_both':True},utc=fresh.now())
                    row['candidate_evidence']=[documents[n]|{'url':sources[documents[n]['source']]['url'],'raw_sha256':sources[documents[n]['source']]['sha256']} for n in pool]
                    fresh.decorate_rows([row],documents,sources);serialization_start=time.perf_counter();json.dumps(row['evidence'],ensure_ascii=False).encode('utf8');serialization_ms=(time.perf_counter()-serialization_start)*1000
                    row['timing_ms']=shared|{'rerank':(rank_end-rank_start)*1000,'citations_serialization':serialization_ms,'attributed_pipeline':shared['acquisition']+(rank_end-rank_start)*1000+serialization_ms}
                    rows.append(row);out.write(json.dumps(row,ensure_ascii=False)+'\n');out.flush()
                print(split,q['id'],'paired actual inference complete',flush=True)
        report['measurement_seconds']=time.monotonic()-started
        report['resident_sessions']={'encoders':1,'baseline_rankers':1,'challenger_rankers':1};report['actual_acquisitions']=len(queries);report['actual_primary_rerank_requests']=len(rows);report['development_parity_additional_requests']=len(parity)
        if split=='development':fresh.save(run/'development-callable-parity.json',dict(pass_all=len(parity)==len(queries),rows=parity,baseline_original_pool_query_vector_ranks_logits_equal=True,config_unchanged=SELECTED_SHA))
        for n,h in dec['files'].items():assert fresh.sha(ROOT/n)==h,n
        fresh.verify_snapshot(SNAPSHOT);report['frozen_inputs_unchanged']=True
    except Exception as e:
        report['blockers'].append(repr(e));raise
    finally:
        if server is not None:report['cleanup']=server.close()
        if db is not None:db.close()
        report['latency_summary']={v:{k:{'p50':statistics.median([r['timing_ms'][k] for r in rows if r['variant']==v]),'p95':sorted(r['timing_ms'][k] for r in rows if r['variant']==v)[math.ceil(.95*sum(r['variant']==v for r in rows))-1]} for k in ('acquisition','rerank','attributed_pipeline')} for v in VARIANTS if any(r['variant']==v for r in rows)}
        fresh.write_outputs(run,rows,report)
    print(json.dumps({'run':str(run),'summaries':[s for s in report['summaries'] if s['language']=='all']},indent=2),flush=True)
    return report


def audit(run):
    import numpy as np
    import technical_quality as tq
    from qdrant_quality import rank_parents
    from retrieval_ablation import lexical_or
    import socket,psutil
    run=Path(run);manifest=fresh.load(run/'evidence-sha256.json')
    for n,h in manifest.items():assert fresh.sha(run/n)==h,n
    freeze=fresh.load(run/'execution-freeze.json');dec=fresh.load(run/'candidate-declaration.json');report=fresh.load(run/'report.json');rows=fresh.load(run/'raw-results.json');corpus=fresh.load(SNAPSHOT/'corpus.json');docs={d['id']:d for d in corpus};sources=fresh.load(SNAPSHOT/'source-receipts.json')
    fresh.verify_snapshot(SNAPSHOT);assert fresh.sha(SNAPSHOT/'freeze.json')==freeze['snapshot_freeze_sha256'];assert fresh.sha(run/'candidate-declaration.json')==freeze['declaration_sha256']
    for n,h in dec['files'].items():assert fresh.sha(ROOT/n)==h,n
    for n,h in dec['runtime_artifacts'].items():assert fresh.sha(n)==h,n
    queries={q['id']:q for q in fresh.queries_for(SNAPSHOT,freeze['split'])}
    assert len(rows)==freeze['expected_rows']==2*len(queries);assert len({(r['id'],r['variant']) for r in rows})==len(rows)
    db=tq.lexical_index(corpus)
    for r in rows:
        q=queries[r['id']]
        for k in q:assert r[k]==q[k],(r['id'],k)
        assert r['dense']==rank_parents(r['server_response']['result']['points'],corpus)
        assert r['lexical']==lexical_or(db,r['query']);assert r['pool20']==tq.fuse(r['dense'],r['lexical'])[:20]
        assert set(r['logits'])==set(r['pool20']);assert r['ranking']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
        accepted=bool(r['ranking']) and (r['variant']=='mmarco_or_pool20' or r['logits'][r['ranking'][0]]>=0)
        assert r['accepted']==accepted;assert r['top5']==(r['ranking'][:5] if accepted else [])
        other=next(x for x in rows if x['id']==r['id'] and x['variant']!=r['variant']);assert other['pool20']==r['pool20'];assert other['query_vector']==r['query_vector']
        copy=dict(r);fresh.decorate_rows([copy],docs,sources);assert copy['evidence']==r['evidence']
        assert r['candidate_evidence']==[docs[n]|{'url':sources[docs[n]['source']]['url'],'raw_sha256':sources[docs[n]['source']]['sha256']} for n in r['pool20']]
    db.close();assert fresh.summaries(rows)==report['summaries'];assert not report['blockers']
    matrix=np.load(run/'passage-vectors.npy');back=fresh.load(run/'server-readback.json');assert back['collection']['indexed_vectors_count']==len(corpus);assert np.max(np.abs(matrix-np.asarray([p['vector'] for p in back['points']])))<1e-6
    cleanup=report['cleanup'];assert cleanup['process_exited'] and cleanup['port_closed'];assert not psutil.pid_exists(cleanup['pid'])
    with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',cleanup['port']))!=0
    if freeze['split']=='development':
        parity=fresh.load(run/'development-callable-parity.json');assert parity['pass_all'];assert len(parity['rows'])==len(queries)
    return dict(**{'pass':True},utc=fresh.now(),run=str(run),rows=len(rows),queries=len(queries),evidence_records=sum(len(r['evidence']) for r in rows),candidate_records=sum(len(r['candidate_evidence']) for r in rows),cleanup=cleanup,manifest_entries=len(manifest),unchanged_candidate_files=len(dec['files']),runtime_artifacts=len(dec['runtime_artifacts']))


def freeze_and_release(development,output):
    development=Path(development).resolve();output=Path(output).resolve()
    if not output.is_relative_to(BASE) or output.exists():raise ValueError('new owned declaration path required')
    receipt=audit(development)
    assert fresh.load(development/'execution-freeze.json')['split']=='development'
    assert not (SNAPSHOT/'test-exposure.json').exists() and not (SNAPSHOT/'release-test.json').exists()
    dec=declaration();devdec=fresh.load(development/'candidate-declaration.json')
    assert dec['files']==devdec['files'] and dec['config']==devdec['config'] and dec['runtime_artifacts']==devdec['runtime_artifacts']
    dec['development_bridge_verification']=receipt;dec['snapshot_freeze_sha256']=fresh.sha(SNAPSHOT/'freeze.json')
    dec['config']['runtime_artifacts']=dec['runtime_artifacts']
    output.parent.mkdir(parents=True,exist_ok=True);fresh.save(output,dec)
    fresh.release_test(SNAPSHOT,output)
    release=fresh.load(SNAPSHOT/'release-test.json');assert release['candidate_declaration_sha256']==fresh.sha(output);assert release['candidate_files']==dec['files']
    return release


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['run','audit','release']);p.add_argument('--run',type=Path);p.add_argument('--split',default='development',choices=['development','test']);p.add_argument('--candidate',type=Path);p.add_argument('--development',type=Path)
    a=p.parse_args()
    if a.action=='run':evaluate(a.run,a.split,a.candidate)
    elif a.action=='audit':print(json.dumps(audit(a.run),indent=2))
    else:print(json.dumps(freeze_and_release(a.development,a.candidate),indent=2))


def invoke(selected,question,candidates):
    ids=[d['id'] for d in candidates]
    if len(ids)>20 or len(ids)!=len(set(ids)):raise ValueError('unique original candidate20 required')
    result=selected(question,candidates)
    ranked=result['ranked'];scores=result['scores'];top=result['top5']
    if set(ranked)!=set(ids) or len(ranked)!=len(ids) or set(scores)!=set(ids):raise ValueError('callable changed candidate identity')
    if not all(math.isfinite(s) for s in scores.values()):raise ValueError('nonfinite score')
    if ranked!=sorted(scores,key=lambda n:(-scores[n],n)):raise ValueError('nonfrozen score ordering')
    if top!=(ranked[:5] if result['accepted'] else []):raise ValueError('nonfrozen presentation')
    return result

def declaration():
    from server_benchmark import SERVER
    if fresh.sha(SELECTED)!=SELECTED_SHA:raise ValueError('selected config differs from parent freeze')
    names=['tools/fresh_challenger_bridge.py','tests/fresh_challenger_bridge_test.py','tools/fresh_retrieval_evaluation.py','tools/technical_quality.py','tools/qdrant_quality.py','tools/retrieval_ablation.py','tools/server_benchmark.py','tools/hybrid_dataset.py','tools/accuracy_iteration/evaluator.py','tools/accuracy_iteration/ranker.py','tools/accuracy_iteration/preparation.py','tools/accuracy_iteration/experiment.py','tools/accuracy_iteration/review.py','requirements-hybrid.lock']
    paths=[ROOT/n for n in names]+[SELECTED,SERVER]
    paths += [ROOT/'artifacts/models/minilm'/n for n in ('manifest.json','model.onnx','tokenizer.json')]
    config=fresh.load(SELECTED)
    for directory in [fresh.RANKER]+[Path(s['path']) for s in config['models']]:
        paths += [directory/'receipt.json']+[directory/n for n in fresh.load(directory/'receipt.json')['files']]
    import numpy,onnxruntime,tokenizers,psutil
    runtime_paths=[Path(sys.executable)]
    for package in (numpy,onnxruntime,tokenizers,psutil):
        runtime_paths += [p for p in Path(package.__file__).parent.rglob('*') if p.is_file() and p.suffix in ('.py','.pyd','.dll') and '__pycache__' not in p.parts]
    runtime_paths += list(Path(sys.base_prefix).glob('python*.dll'))
    runtime_hashes={str(p):fresh.sha(p) for p in sorted(set(runtime_paths))}
    return dict(runtime_artifacts=runtime_hashes,name='frozen-jina512-frontmatter-cutoff0-fresh-OR-RRF20',selection_used_development_only=True,utc=fresh.now(),config=dict(selected=config,selected_config_sha256=SELECTED_SHA,ranking_semantics='DIRECT original create_evaluator; no config rewrite; candidate_contract metadata not enforced by callable',acquisition=dict(encoder='MiniLM128 manifest; attention-mask-mean-l2; prefixes from bound manifest',dense_limit=60,hnsw_ef=128,exact=False,lexical='existing lexical_or technical_tokens FTS5 BM25 limit20',fusion='equal RRF k60 one-based ranks; ID ties',pool=20,applicability_gate='NONE, identical to fresh baseline',segmentation='unchanged416 original windows width1800 stride900'),baseline='original mMARCO512 longest-first CPU2/1 batch4, no abstention',runtime=dict(provider='CPUExecutionProvider',intra_threads=2,inter_threads=1,batch=4,jina_pair_cap=512,jina_padding=1,truncation='longest_first',score='raw scalar logits; >=0 accept; not probability'),acceptance=dict(p1_all_answerable=.8,stretch=.9,answerable_coverage=.8,noanswer_falseaccept_max=.1,status='personal evaluation; no automatic activation; selected-positive incomplete labels'),license='Jina CC-BY-NC-4.0 personal evaluation only'),files={p.relative_to(ROOT).as_posix():fresh.sha(p) for p in paths})

if __name__=='__main__':main()
