"""Finite actual Qdrant/resident inference; historical corpus only, no fresh reads."""
from pathlib import Path
import sys,json,hashlib,time,datetime,statistics
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
BASE=ROOT/'artifacts/accuracy-iteration/ai-20261020-gte'
MODEL=BASE/'gte-int8'
INCUMBENT=ROOT/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'

def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def aggregate(rows):
    groups=[]
    for split in ('development','holdout'):
        for variant in sorted({r['variant'] for r in rows}):
            for lang in ('all','fr','en_or_mixed'):
                chosen=[r for r in rows if r['split']==split and r['variant']==variant and (lang=='all' or r['language']==lang)]
                yes=[r for r in chosen if r['relevant']]; no=[r for r in chosen if not r['relevant']]
                if not chosen: continue
                groups.append(dict(split=split,variant=variant,language=lang,answerable=len(yes),correct_top1=sum(r['metrics']['p1'] for r in yes),answerable_accepted=sum(bool(r['top5']) for r in yes),noanswer=len(no),noanswer_false_accept=sum(bool(r['top5']) for r in no),incompatible_top1=sum(r['metrics']['incompatible_top1'] for r in chosen),incompatible_top5=sum(r['metrics']['incompatible_top5'] for r in chosen),p50_rerank_ms=statistics.median(r['rerank_ms'] for r in chosen),**{k:statistics.mean(r['metrics'][k] for r in yes) if yes else None for k in ('p1','p3','p5','mrr','recall5','candidate_recall')}))
    return groups

def experiment(run):
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import lexical_or
    from relevance_candidate_experiment import exact_index,exact_search
    from retrieval_budget_benchmark import eligibility,select_candidates,present
    from accuracy_stepping_stone import union_pool,metrics
    from server_benchmark import Server
    from tools.accuracy_iteration.ranker import ResidentRanker
    run=Path(run).resolve()
    if not run.is_relative_to(BASE): raise ValueError('owned project run only')
    run.mkdir(parents=True,exist_ok=False)
    corpus=json.loads((paired.SNAPSHOT/'corpus.json').read_bytes()); queries=json.loads((paired.SNAPSHOT/'judgments.json').read_bytes()); sources=json.loads((paired.SNAPSHOT/'source-receipts.json').read_bytes()); docs={d['id']:d for d in corpus}
    save(run/'corpus.json',corpus); save(run/'judgments.json',queries); save(run/'sources.json',sources)
    variants={'baseline':(INCUMBENT,512),'gte512':(MODEL,512),'gte1024':(MODEL,1024)}
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),variants={n:dict(model=str(p),cap=c,receipt_sha256=sha(p/'receipt.json')) for n,(p,c) in variants.items()},selection='old development only: top1 all-answerable then MRR, baseline exact tie preference; noanswer threshold finite grid development only separately',threshold_grid=[None,0,.25,.5,1,2,3,4,6,8],gates={'p1_all_answerable':.8,'answerable_coverage':.8,'noanswer_false_accept_max':.1},labels='ALL historical/reused incomplete selected labels, no fresh sealed reads',candidate_contract='incumbent union exact2+MiniLM6+E5six+lexical6,20 unique gated, same for each reranker',inputs={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'tools/accuracy_iteration/ranker.py',ROOT/'tests/test_accuracy_iteration.py',paired.SNAPSHOT/'corpus.json',paired.SNAPSHOT/'judgments.json']})
    save(run/'freeze.json',freeze)
    report={'rows':0}; rows=[]; server=None; db=None; exact=None
    try:
        encoders={n:tq.ResidentEncoder(ROOT/'artifacts/models'/n) for n in ('minilm','e5-small')}
        rankers={n:ResidentRanker(p,c) for n,(p,c) in variants.items()}
        server=Server(run); server.start(); report['server']=server.request('GET','/')
        db=tq.lexical_index(corpus); exact=exact_index(corpus)
        for name,encoder in encoders.items():
            matrix=encoder.encode([d['text'] for d in corpus],'passage'); np.save(run/(name+'-vectors.npy'),matrix); paired.fresh_connection(server)
            server.request('PUT','/collections/'+name,{'vectors':{'size':384,'distance':'Cosine','on_disk':False},'shard_number':1,'hnsw_config':{'m':16,'ef_construct':100,'full_scan_threshold':10},'optimizers_config':{'indexing_threshold':1,'default_segment_number':1}})
            server.request('PUT','/collections/'+name+'/points?wait=true',{'points':[dict(id=i+1,vector=v.tolist(),payload={'document_id':d['id']}) for i,(d,v) in enumerate(zip(corpus,matrix))]})
            deadline=time.monotonic()+90
            while True:
                info=server.request('GET','/collections/'+name)['result']
                if info['status']=='green' and info['indexed_vectors_count']==len(corpus): break
                if time.monotonic()>deadline: raise TimeoutError('index deadline')
                time.sleep(.2)
            back=server.request('POST','/collections/'+name+'/points',{'ids':list(range(1,len(corpus)+1)),'with_payload':True,'with_vector':True})['result']; back.sort(key=lambda p:p['id'])
            assert len(back)==len(corpus) and np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix))<1e-6
            save(run/(name+'-readback.json'),dict(info=info,points=back))
        started=time.monotonic()
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as output:
            for split in ('development','holdout'):
                if split=='holdout':
                    dev=[r for r in rows if r['split']=='development' and r['relevant']]
                    winner=max(variants,key=lambda n:(statistics.mean(r['metrics']['p1'] for r in dev if r['variant']==n),statistics.mean(r['metrics']['mrr'] for r in dev if r['variant']==n),n=='baseline',n))
                    save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,development=aggregate(rows),thresholds=threshold_diagnostic(rows,freeze['threshold_grid'])))
                for q in [q for q in queries if q['split']==split]:
                    paired.fresh_connection(server); dense=[]; responses={}; vectors={}; start=time.perf_counter()
                    for name,e in encoders.items():
                        v=e.encode([q['query']],'query')[0]; vectors[name]=v.tolist()
                        response=server.request('POST','/collections/'+name+'/points/query',dict(query=v.tolist(),limit=60,with_payload=True,with_vector=False,params={'exact':False,'hnsw_ef':128})); responses[name]=response
                        dense.append(paired.rank_parents(response['result']['points'],corpus))
                    lex=lexical_or(db,q['query']); ex=exact_search(exact,q['query']); pool=union_pool(*dense,lex,ex); states=eligibility(q['query'],docs,sources); candidates=select_candidates(pool,states,True,20); acquisition=(time.perf_counter()-start)*1000
                    for variant,r in rankers.items():
                        if time.monotonic()-started>1000: raise TimeoutError('1000s measured work cap')
                        result=r.evaluate(q['query'],[docs[n] for n in candidates]); top=present(result['ranked'],states,True)
                        row=dict(q,variant=variant,language='fr' if q.get('category')=='fr_to_en' or any(x in q['query'] for x in ['Pourquoi','Quel','Comment','exclure']) else 'en_or_mixed',pool20=pool,candidates=candidates,eligibility=states,dense=dense,lexical=lex,exact=ex,server_responses=responses,query_vectors=vectors,ranked=result['ranked'],logits=result['scores'],pair_tokens=result['pair_tokens'],top5=top,metrics=metrics(top,q,candidates),rerank_ms=result['wall_ms'],shared_acquisition_ms=acquisition,evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top])
                        if any(n in ('qfilter-not','qfilter-must') for n in candidates): row['operator_visible']={n:result['visible'][n] for n in candidates if n in ('qfilter-not','qfilter-must')}
                        rows.append(row); output.write(json.dumps(row,ensure_ascii=False)+'\n'); output.flush(); print(q['id'],variant,row['metrics']['p1'],round(row['rerank_ms']),flush=True)
        report.update(rows=len(rows),summaries=aggregate(rows),wall_seconds=time.monotonic()-started,rss_bytes=psutil.Process().memory_info().rss)
    finally:
        if server: report['cleanup']=server.close()
        if db: db.close()
        if exact: exact.close()
        save(run/'raw-results.json',rows); save(run/'report.json',report)
        save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report

def threshold_diagnostic(rows,grid):
    out=[]
    for v in sorted({r['variant'] for r in rows}):
        subset=[r for r in rows if r['variant']==v and r['split']=='development']
        for threshold in grid:
            accepted=lambda r: bool(r['top5']) and (threshold is None or r['logits'][r['top5'][0]]>=threshold)
            yes=[r for r in subset if r['relevant']]; no=[r for r in subset if not r['relevant']]
            out.append(dict(variant=v,threshold=threshold,answerable=len(yes),correct_top1=sum(r['metrics']['p1']*accepted(r) for r in yes),answerable_accepted=sum(accepted(r) for r in yes),noanswer=len(no),noanswer_false_accept=sum(accepted(r) for r in no)))
    return out

def verify(run):
    from accuracy_stepping_stone import union_pool,metrics
    run=Path(run); rows=json.loads((run/'raw-results.json').read_bytes()); report=json.loads((run/'report.json').read_bytes())
    for n,h in json.loads((run/'hashes.json').read_bytes()).items(): assert sha(run/n)==h,n
    assert len(rows)==96 and report['summaries']==aggregate(rows)
    groups={}
    for r in rows:
        assert r['pool20']==union_pool(*r['dense'],r['lexical'],r['exact'])
        assert r['ranked']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
        assert r['metrics']==metrics(r['top5'],r,r['candidates'])
        for e in r['evidence']: assert hashlib.sha256(e['text'].encode()).hexdigest()==e['sha256']
        key=r['id']; previous=groups.setdefault(key,r['candidates']); assert previous==r['candidates']
    assert report['cleanup']['port_closed']
    return True

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path); p.add_argument('--verify',type=Path); a=p.parse_args()
    if a.verify: print(verify(a.verify))
    else: print(json.dumps(experiment(a.run),indent=2))
