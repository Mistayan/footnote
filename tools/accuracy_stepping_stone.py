"""Bounded project-local multilingual accuracy diagnostic; never production activation."""
from pathlib import Path
import hashlib,json,datetime
REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'artifacts/accuracy-stepping-stone'
RESEARCH=BASE/'lrk-research'

def union_pool(dense1,dense2,lexical,exact):
    reserved=exact[:2]+dense1[:6]+dense2[:6]+lexical[:6]
    return list(dict.fromkeys(reserved+dense1+dense2+lexical+exact))[:20]

def choose_development(rows):
    import statistics
    if not rows or any(r['split']!='development' for r in rows):
        raise ValueError('nonempty development only')
    variants=sorted({r['variant'] for r in rows})
    return max(variants,key=lambda v:(statistics.mean(r['metrics']['p1'] for r in rows if r['variant']==v),statistics.mean(r['metrics']['mrr'] for r in rows if r['variant']==v),v=='baseline',v))


def metrics(top,query,pool):
    relevant=set(query['relevant']); incompatible=set(query['incompatible'])
    hits=[n in relevant for n in top[:5]]
    return {**{'p'+str(k):sum(n in relevant for n in top[:k])/k for k in (1,3,5)},
            'mrr':next((1/(i+1) for i,h in enumerate(hits) if h),0),
            'recall5':len(set(top[:5])&relevant)/len(relevant) if relevant else None,
            'candidate_recall':len(set(pool)&relevant)/len(relevant) if relevant else None,
            'incompatible_top1':int(bool(top) and top[0] in incompatible),
            'incompatible_top5':len(set(top[:5])&incompatible),'accepted':int(bool(top)),
            'noanswer_false_accept':int(not relevant and bool(top))}


def heading_context(query,doc,texts,tokenizer,cap=512):
    """Append source-parsed scope only within spare capacity; never replace body."""
    from relevance_candidate_experiment import source_headings
    from tokenizers import Tokenizer
    counter=tokenizer
    if tokenizer.truncation is not None or tokenizer.padding is not None:
        counter=Tokenizer.from_str(tokenizer.to_str()); counter.no_padding(); counter.no_truncation()
    headings=source_headings(texts[doc['source']])
    prior=[h for h in headings if h['start']<=doc['start']]
    selected=list(dict.fromkeys(([headings[0]['text']] if headings else [])+([prior[-1]['text']] if prior else [])))
    body=doc['text']
    suffix='\nSource headings: '+' / '.join(selected)
    return body+suffix if selected and len(counter.encode(query,body+suffix).ids)<=cap else body


def experiment(run, cap=512, diagnostic=False, context=False, fresh_only=False):
    """Two resident rerankers, identical fixed admissible union20, finite run."""
    import time,sys,platform,shutil,statistics
    import numpy as np
    import psutil
    import technical_quality as tq
    import qdrant_quality as paired
    from retrieval_ablation import CrossEncoder,lexical_or
    from relevance_candidate_experiment import exact_index,exact_search
    from retrieval_budget_benchmark import eligibility,select_candidates,present
    from server_benchmark import Server,SERVER,save,sha,percentile
    run=Path(run).resolve()
    if not run.is_relative_to(BASE) or any(p.is_symlink() for p in (run,*run.parents)):
        raise ValueError('NEW owned non-symlink project-local run required')
    if cap not in (512,1024): raise ValueError('bounded cap512 or diagnostic1024 only')
    if cap!=512 and not diagnostic: raise ValueError('follow-up must be declared diagnostic')
    run.mkdir(parents=True,exist_ok=False)
    load=lambda p:json.loads(p.read_bytes())
    datasets={}
    for label,path in [('fresh',RESEARCH/'fresh')]+([] if fresh_only else [('old',paired.SNAPSHOT)]):
        frozen=load(path/'freeze.json')
        for n,h in frozen['files'].items(): assert sha(path/n)==h,(label,n)
        corpus=load(path/'corpus.json'); queries=load(path/'judgments.json'); sources=load(path/'source-receipts.json')
        target=run/label; target.mkdir(); (target/'sources').mkdir()
        for n,s in sources.items():
            sourcepath=path/(n+'.txt') if label=='fresh' else path/'sources'/(n+'.txt')
            text=sourcepath.read_text(encoding='utf8')
            for d in corpus:
                if d['source']==n:
                    assert text[d['start']:d['end']]==d['text']
                    assert hashlib.sha256(d['text'].encode()).hexdigest()==d['sha256']
            shutil.copyfile(sourcepath,target/'sources'/(n+'.txt'))
            raw=path/(n+'.raw') if label=='fresh' else path/'sources'/(n+'.raw')
            if raw.exists():
                assert sha(raw)==s['sha256']; shutil.copyfile(raw,target/'sources'/(n+'.raw'))
        for n,v in [('corpus',corpus),('judgments',queries),('source-receipts',sources)]: save(target/(n+'.json'),v)
        shutil.copyfile(path/'freeze.json',target/'input-freeze.json')
        datasets[label]=(corpus,queries,sources)
    oldmodel=REPO/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'
    newmodel=RESEARCH/'bge-model'
    paths=[Path(__file__),REPO/'tests/accuracy_stepping_stone_test.py',SERVER,REPO/'.git/index',REPO/'requirements-hybrid.lock']
    paths += [REPO/'tools'/n for n in ('technical_quality.py','retrieval_ablation.py','qdrant_quality.py','relevance_candidate_experiment.py','retrieval_budget_benchmark.py','server_benchmark.py')]
    paths += [p for p in newmodel.iterdir() if p.is_file()]+[oldmodel/'receipt.json']
    paths += [oldmodel/n for n in load(oldmodel/'receipt.json')['files']]
    for name in ('minilm','e5-small'):
        paths += [REPO/'artifacts/models'/name/n for n in ('manifest.json','model.onnx','tokenizer.json')]
    if context: paths.append(RESEARCH/'followup-declaration.json')
    before={p.relative_to(REPO).as_posix():sha(p) for p in paths}
    (run/'code').mkdir()
    for p in paths:
        if p.suffix=='.py': shutil.copyfile(p,run/'code'/p.name)
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=before,
        artifacts={p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file()},
        variants=['baseline','bge'],reranker_caps={'baseline':512,'bge':cap},diagnostic=diagnostic,datasets=list(datasets),expected_rows=32 if fresh_only else 96,heading_context=context,
        candidates='Same pool20: exact2, MiniLM dense6, E5 dense6, OR lexical6; deduplicate, fill dense1,dense2,lexical,exact. Union dense60 each,lexical20,exact20. No labels in acquisition.',
        selection='Fresh DEVELOPMENT answerable only: highest P1 then MRR; baseline tie preference. Freeze choice BEFORE fresh holdout or old inference. Both controls reported. No weights fitted.',
        coverage_floor=.8,thresholds={'stepping_stone':.8,'stretch':.9},abstention='NONE; all attempted. No precision-through-rejection acceptance.',
        labels='fresh family-disjoint Git dev/Rust holdout; implementing-agent incomplete, not independent human; old all reused diagnostic; UNKNOWN not negative',
        recipe='MiniLM128 E5small512 masked-mean L2 manifest prefixes CPU2/1 batch8; rerank raw classification logits longest_first CPU2/1 batch4; cap512 matched control. No embedding pooling for rankers.',
        budget='96 independent E2E requests; 1200s measurement cap; model load/offline indexing/evidence I/O excluded. No private input or external inference.')
    save(run/'freeze.json',freeze)
    report=dict(status='OPEN_PENDING_PARENT_VERIFICATION',rows=0,diagnostic=diagnostic,blockers=[],summaries=[],freeze_sha256=sha(run/'freeze.json'),environment={'python':sys.version,'platform':platform.platform(),'cpu':platform.processor(),'logical_cpus':psutil.cpu_count(),'physical_cpus':psutil.cpu_count(logical=False),'ram_bytes':psutil.virtual_memory().total})
    rows=[]; server=None; dbs=[]
    try:
        started=time.perf_counter()
        encoders={n:tq.ResidentEncoder(REPO/'artifacts/models'/n) for n in ('minilm','e5-small')}
        rankers={'baseline':CrossEncoder(oldmodel),'bge':CrossEncoder(newmodel)}
        rankers['bge'].tokenizer.enable_truncation(max_length=cap,strategy='longest_first')
        from tokenizers import Tokenizer
        context_counter=Tokenizer.from_file(str(newmodel/'tokenizer.json')); context_counter.no_padding(); context_counter.no_truncation()
        report['model_load_validate_ms']=(time.perf_counter()-started)*1000
        report['model_receipts']={n:r.receipt for n,r in rankers.items()}
        report['first_inference_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        assert freeze['utc']<=report['first_inference_utc']
        server=Server(run); server.start(); report['server']=server.request('GET','/')
        assert report['server']['version']=='1.19.2'
        setup={}; offline=time.perf_counter()
        for label,(corpus,queries,sources) in datasets.items():
            db=tq.lexical_index(corpus); exact=exact_index(corpus); dbs.extend([db,exact]); setup[label]=(db,exact)
            for name,encoder in encoders.items():
                matrix=encoder.encode([d['text'] for d in corpus],'passage'); np.save(run/(label+'-'+name+'-vectors.npy'),matrix)
                paired.fresh_connection(server)  # Offline encoding can exceed HTTP keep-alive idle timeout.
                collection=label+'_'+name
                server.request('PUT','/collections/'+collection,{'vectors':{'size':384,'distance':'Cosine','on_disk':False},'shard_number':1,'hnsw_config':{'m':16,'ef_construct':100,'full_scan_threshold':10},'optimizers_config':{'indexing_threshold':1,'default_segment_number':1}})
                server.request('PUT','/collections/'+collection+'/points?wait=true',{'points':[dict(id=i+1,vector=v.tolist(),payload={'document_id':d['id']}) for i,(d,v) in enumerate(zip(corpus,matrix))]})
                deadline=time.monotonic()+90
                while True:
                    info=server.request('GET','/collections/'+collection)['result']
                    if info['status']=='green' and info['indexed_vectors_count']==len(corpus):break
                    if time.monotonic()>deadline:raise TimeoutError(collection+' not indexed')
                    time.sleep(.2)
                back=server.request('POST','/collections/'+collection+'/points',{'ids':list(range(1,len(corpus)+1)),'with_payload':True,'with_vector':True})['result']; back.sort(key=lambda p:p['id'])
                assert len(back)==len(corpus)
                assert np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix))<1e-6
                assert all(p['payload']['document_id']==corpus[i]['id'] for i,p in enumerate(back))
                save(run/(collection+'-readback.json'),dict(collection=info,points=back))
        report['offline_encoding_indexing_ms']=(time.perf_counter()-offline)*1000
        measurement=time.monotonic()
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as output:
            for label,split in [('fresh','development'),('fresh','holdout'),('old','development'),('old','holdout')]:
                if label not in datasets: continue
                if label=='fresh' and split=='holdout':
                    dev=[r for r in rows if r['dataset']=='fresh' and r['split']=='development' and r['relevant']]
                    choice=choose_development(dev)
                    save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=choice,fit_ids=sorted({r['id'] for r in dev}),scores=[dict(variant=n,p1=statistics.mean(r['metrics']['p1'] for r in dev if r['variant']==n),mrr=statistics.mean(r['metrics']['mrr'] for r in dev if r['variant']==n)) for n in rankers],before_first_holdout=True))
                corpus,queries,sources=datasets[label]; documents={d['id']:d for d in corpus}; db,exact=setup[label]
                for q in [q for q in queries if q['split']==split]:
                    for variant,ranker in rankers.items():
                        if time.monotonic()-measurement>1200:raise TimeoutError('1200s measured work bound')
                        start=time.perf_counter(); dense=[]; responses={}; vectors={}
                        paired.fresh_connection(server)  # Explicit per-request connection, included in E2E.
                        for name,encoder in encoders.items():
                            vector=encoder.encode([q['query']],'query')[0]; vectors[name]=vector.tolist()
                            response=server.request('POST','/collections/'+label+'_'+name+'/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params={'exact':False,'hnsw_ef':128})); responses[name]=response
                            dense.append(paired.rank_parents(response['result']['points'],corpus))
                        lexical=lexical_or(db,q['query']); exact_hits=exact_search(exact,q['query'])
                        pool=union_pool(*dense,lexical,exact_hits)
                        states=eligibility(q['query'],documents,sources); candidates=select_candidates(pool,states,True,20)
                        acquired=time.perf_counter()
                        rankdocs=[documents[n] for n in candidates]
                        if context and variant=='bge':
                            texts={n:(run/label/'sources'/(n+'.txt')).read_text(encoding='utf8') for n in sources}
                            rankdocs=[d|{'text':heading_context(q['query'],d,texts,context_counter,cap)} for d in rankdocs]
                        ranked,logits=ranker.rank(q['query'],rankdocs); reranked=time.perf_counter()
                        top=present(ranked,eligibility(q['query'],documents,sources),True)
                        evidence=[documents[n]|{'url':sources[documents[n]['source']]['url'],'source_raw_sha256':sources[documents[n]['source']]['sha256'],'judgment':'selected relevant' if n in q['relevant'] else 'explicit incompatible' if n in q['incompatible'] else 'UNKNOWN/unjudged'} for n in top]
                        payload=json.dumps(dict(query=q['query'],evidence=evidence),ensure_ascii=False).encode(); end=time.perf_counter()
                        row=dict(q,dataset=label,variant=variant,language=q.get('language','fr' if q.get('category')=='fr_to_en' else 'en_or_mixed'),pool20=pool,candidates=candidates,top5=top,ranked=ranked,logits=logits,dense=dense,lexical=lexical,exact=exact_hits,eligibility=states,server_responses=responses,query_vectors=vectors,evidence=evidence,metrics=metrics(top,q,candidates),timing_ms={'acquisition':(acquired-start)*1000,'rerank':(reranked-acquired)*1000,'citations_json':(end-reranked)*1000,'e2e':(end-start)*1000},wire_bytes=len(payload),utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
                        row['reranker_inputs']={d['id']:d['text'] for d in rankdocs}
                        row['reranker_context_changed']=sum(d['text']!=documents[d['id']]['text'] for d in rankdocs)
                        rows.append(row); output.write(json.dumps(row,ensure_ascii=False)+'\n'); output.flush()
                        print(label,q['id'],variant,row['metrics']['p1'],round(row['timing_ms']['e2e']),flush=True)
        report['measurement_seconds']=time.monotonic()-measurement
        report['rows']=len(rows); assert len(rows)==freeze['expected_rows']
        for label in datasets:
            for split in ('development','holdout'):
                for variant in rankers:
                    for language in ('all','fr','en','en_or_mixed'):
                        chosen=[r for r in rows if r['dataset']==label and r['split']==split and r['variant']==variant and (language=='all' or r['language']==language)]
                        yes=[r for r in chosen if r['relevant']]; no=[r for r in chosen if not r['relevant']]
                        if not chosen:continue
                        item=dict(dataset=label,split=split,variant=variant,language=language,n=len(chosen),answerable=len(yes),accepted=sum(r['metrics']['accepted'] for r in chosen),correct_top1=sum(r['metrics']['p1'] for r in yes),answerable_coverage=sum(r['metrics']['accepted'] for r in yes)/len(yes) if yes else None,noanswer_count=len(no),noanswer_false_accept=sum(r['metrics']['noanswer_false_accept'] for r in no),incompatible_top1=sum(r['metrics']['incompatible_top1'] for r in chosen),incompatible_top5=sum(r['metrics']['incompatible_top5'] for r in chosen),unjudged_top5=sum(e['judgment']=='UNKNOWN/unjudged' for r in chosen for e in r['evidence']),e2e_p50_ms=statistics.median(r['timing_ms']['e2e'] for r in chosen),e2e_p95_ms=percentile([r['timing_ms']['e2e'] for r in chosen],.95))
                        for key in ('p1','p3','p5','mrr','recall5','candidate_recall'):item[key]=statistics.mean(r['metrics'][key] for r in yes) if yes else None
                        report['summaries'].append(item)
        report['resources']={'harness_rss_bytes':psutil.Process().memory_info().rss,'qdrant_rss_bytes':psutil.Process(server.process.pid).memory_info().rss,'reranker_at512_or_above_counts':{n:r.at_limit for n,r in rankers.items()}}
        report['frozen_inputs_unchanged']=all(sha(REPO/n)==h for n,h in before.items()); assert report['frozen_inputs_unchanged']
    except Exception as exc:
        report['blockers'].append(repr(exc)); raise
    finally:
        if server is not None:report['cleanup']=server.close()
        for db in dbs:db.close()
        save(run/'raw-results.json',rows); save(run/'report.json',report)
        lines=['# Per-query original-source evidence','', 'Selected incomplete implementing-agent labels; UNKNOWN is not wrong. P5 label ceiling disclosed. No independent human certification.','']
        for r in rows:
            lines += [f"## {r['dataset']} / {r['id']} / {r['variant']}",r['query'],json.dumps(r['metrics']),f"Relevant: {r['relevant']}; pool20: {r['pool20']}; ranked: {r['ranked']}",f"Timing ms: {r['timing_ms']}"]
            for i,e in enumerate(r['evidence'],1):lines += [f"### {i}. {e['id']} — {e['judgment']}",f"{e['url']} offsets[{e['start']},{e['end']}) SHA256 {e['sha256']}",'> '+e['text'].replace('\n','\n> ')]
        (run/'PER-QUERY-REVIEW.md').write_text('\n\n'.join(lines),encoding='utf8')
        save(run/'evidence-sha256.json',{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file() and not any(n in p.parts for n in ('storage','snapshots','temp')) and p.name!='evidence-sha256.json'})
    return report


def verify_run(run):
    """Replay ranks/metrics/source boundaries, fixed pool, dev choice and readback."""
    import numpy as np
    from server_benchmark import sha
    from retrieval_budget_benchmark import eligibility,select_candidates,present
    run=Path(run); load=lambda p:json.loads(p.read_bytes())
    for n,h in load(run/'evidence-sha256.json').items(): assert sha(run/n)==h,n
    freeze=load(run/'freeze.json')
    for n,h in freeze['inputs'].items():
        target=REPO/n
        if Path(n).name in ('accuracy_stepping_stone.py','accuracy_stepping_stone_test.py'):
            target=run/'code'/Path(n).name
        assert sha(target)==h,n
    for n,h in freeze['artifacts'].items():assert sha(run/n)==h,n
    rows=load(run/'raw-results.json'); assert len(rows)==freeze.get('expected_rows',96)
    pairs={}; keys=set()
    for r in rows:
        key=(r['dataset'],r['id'],r['variant']); assert key not in keys; keys.add(key)
        corpus=load(run/r['dataset']/'corpus.json'); sources=load(run/r['dataset']/'source-receipts.json'); docs={d['id']:d for d in corpus}
        assert r['pool20']==union_pool(*r['dense'],r['lexical'],r['exact'])
        states=eligibility(r['query'],docs,sources)
        assert r['candidates']==select_candidates(r['pool20'],states,True,20)
        assert r['ranked']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
        assert r['top5']==present(r['ranked'],states,True)
        assert r['metrics']==metrics(r['top5'],r,r['candidates'])
        if 'reranker_inputs' in r:
            from tokenizers import Tokenizer
            counter=Tokenizer.from_file(str(RESEARCH/'bge-model/tokenizer.json')); counter.no_padding(); counter.no_truncation()
            texts={n:(run/r['dataset']/'sources'/(n+'.txt')).read_text(encoding='utf8') for n in sources}
            for n,text in r['reranker_inputs'].items():
                expected=heading_context(r['query'],docs[n],texts,counter,freeze['reranker_caps']['bge']) if freeze.get('heading_context') and r['variant']=='bge' else docs[n]['text']
                assert text==expected and text.startswith(docs[n]['text'])
        for e in r['evidence']:
            d=docs[e['id']]; text=(run/r['dataset']/'sources'/(d['source']+'.txt')).read_text(encoding='utf8')
            assert text[e['start']:e['end']]==e['text']==d['text']
            assert hashlib.sha256(e['text'].encode()).hexdigest()==e['sha256']
            assert e['url']==sources[e['source']]['url']
        pair=(r['dataset'],r['id'])
        if pair in pairs:assert pairs[pair]==r['candidates']
        pairs[pair]=r['candidates']
    selection=load(run/'selection-freeze.json')
    assert selection['selected']==choose_development([r for r in rows if r['dataset']=='fresh' and r['split']=='development' and r['relevant']])
    assert all(selection['utc']<=r['utc'] for r in rows if r['dataset']=='fresh' and r['split']=='holdout')
    for label in freeze.get('datasets',['fresh','old']):
        for n in ('minilm','e5-small'):
            matrix=np.load(run/(label+'-'+n+'-vectors.npy')); back=load(run/(label+'_'+n+'-readback.json'))['points']
            assert np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix))<1e-6
    cleanup=load(run/'cleanup.json'); assert cleanup['process_exited'] and cleanup['port_closed']
    return True

if __name__=='__main__':
    import argparse,uuid
    parser=argparse.ArgumentParser(); parser.add_argument('--run'); parser.add_argument('--verify'); parser.add_argument('--cap',type=int,default=512); parser.add_argument('--diagnostic',action='store_true'); parser.add_argument('--context',action='store_true'); parser.add_argument('--fresh-only',action='store_true'); args=parser.parse_args()
    if args.verify: print(verify_run(args.verify))
    else: print(json.dumps(experiment(args.run or BASE/uuid.uuid4().hex,args.cap,args.diagnostic,args.context,args.fresh_only),indent=2))
