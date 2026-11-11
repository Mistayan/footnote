"""Real release CLI vs isolated Qdrant-local, identical corpus/vectors/RRF.
No live service/storage is opened. Raw outputs persist per call in a unique run.
"""
import hashlib
import json
import math
import os
import sqlite3
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path
import psutil
from hybrid_dataset import DOCS, QUERIES

REPO=Path(__file__).resolve().parents[1]
BINARY=REPO/'target/release/borg-knowledge.exe'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path, value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def percentile(values,p):return sorted(values)[math.ceil(p*len(values))-1] if values else None

def score(names, q):
    names=names[:5]; relevant=set(q['relevant']); found=set(names)&relevant
    dcg=sum(1/math.log2(i+2) for i,n in enumerate(names) if n in relevant)
    ideal=sum(1/math.log2(i+2) for i in range(min(5,len(relevant))))
    return {'precision_at_5':len(found)/5 if relevant else None,
            'recall_at_5':len(found)/len(relevant) if relevant else None,
            'reciprocal_rank':next((1/(i+1) for i,n in enumerate(names) if n in relevant),0) if relevant else None,
            'ndcg_at_5':dcg/ideal if ideal else None,
            'forbidden_at_5':len(set(names)&set(q['forbidden'])),
            'no_answer_false_positive':int(bool(names)) if not relevant else None}

def aggregate(rows):
    out={'queries':len(rows)}
    for key in ['precision_at_5','recall_at_5','reciprocal_rank','ndcg_at_5']:
        vals=[r[key] for r in rows if r[key] is not None]
        out[key]=statistics.mean(vals) if vals else None
    unknown=[r['no_answer_false_positive'] for r in rows if r['no_answer_false_positive'] is not None]
    out['no_answer_queries']=len(unknown)
    out['no_answer_false_positive_rate']=statistics.mean(unknown) if unknown else None
    out['forbidden_results_at_5']=sum(r['forbidden_at_5'] for r in rows)
    return out

def directory_bytes(path):return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())

def main():
    from embed import encode
    from qdrant_client import QdrantClient, models
    import importlib.metadata
    run=REPO/'artifacts/hybrid'/uuid.uuid4().hex
    run.mkdir(parents=True); notes=run/'notes'; notes.mkdir()
    source_paths=[*REPO.glob('src/*.rs'),*REPO.glob('tools/*.py'),*REPO.glob('tests/*.rs'),*REPO.glob('tests/*.py'),*REPO.glob('scripts/*.sh'),REPO/'requirements-hybrid.lock',REPO/'Cargo.lock',REPO/'Cargo.toml']
    source_before={str(p.relative_to(REPO)):sha(p) for p in source_paths}
    binary_before=sha(BINARY)
    save(run/'source-before.json',source_before)
    corpus=dict(DOCS)
    corpus.update({f'distractor-{i:04}':f'# Garden fixture {i}\nPlant flowers, water vegetables and prune fruit trees. Unrelated synthetic fixture {i}.' for i in range(1000-len(corpus))})
    for key,text in corpus.items():(notes/(key+'.md')).write_text(text,encoding='utf-8')
    save(run/'judgments.json',QUERIES)
    save(run/'corpus.json',{k:{'text':v,'sha256':sha(notes/(k+'.md'))} for k,v in corpus.items()})
    db=run/'knowledge.db'; call_count=0
    def call(*args):
        nonlocal call_count
        start=time.perf_counter(); peak=0
        p=subprocess.Popen([str(BINARY),'--db',str(db),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stop=threading.Event()
        def sample():
            nonlocal peak
            while not stop.is_set():
                try:
                    process=psutil.Process(p.pid)
                    peak=max(peak, sum(x.memory_info().rss for x in [process,*process.children(recursive=True)] if x.is_running()))
                except (psutil.NoSuchProcess, psutil.AccessDenied):pass
                stop.wait(.01)
        watcher=threading.Thread(target=sample);watcher.start()
        try:stdout,stderr=p.communicate(timeout=900)
        finally:stop.set();watcher.join()
        elapsed=(time.perf_counter()-start)*1000
        call_count+=1; prefix=run/f'call-{call_count:04}'
        prefix.with_suffix('.stdout.json').write_bytes(stdout);prefix.with_suffix('.stderr.txt').write_bytes(stderr)
        save(prefix.with_suffix('.meta.json'),{'args':list(map(str,args)),'exit':p.returncode,'ms':elapsed,'peak_process_tree_rss_bytes_sampled':peak,'stdout_bytes':len(stdout)})
        if p.returncode:raise RuntimeError(stderr.decode(errors='replace'))
        return json.loads(stdout), {'ms':elapsed,'bytes':len(stdout),'peak_rss':peak,'raw':prefix.name}
    index,index_cost=call('index','--root',notes,'--allow',notes)
    _,incremental_cost=call('index','--root',notes,'--allow',notes)
    conn=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True)
    chunks={r[0]:{'path':r[1],'sha256':r[2],'revision':r[3],'heading':r[4],'page':r[5],'line':r[6],'text':r[7]} for r in conn.execute('SELECT c.id,s.path,s.sha256,s.revision,c.heading,c.page,c.line,c.text FROM chunks c JOIN sources s ON s.id=c.source_id')}
    assert len(chunks)==1000
    conn.close()
    def names(value):return [Path(r['path']).stem for r in value['results']]
    def citations(value):
        checks=[]
        for item in value['results']:
            expected=chunks[item['id']]
            checks.append(all(item[k]==expected[k] for k in ['path','sha256','revision','heading','page','line']) and item['text']==expected['text'][:500] and sha(item['path'])==item['sha256'] and item['freshness']=='current')
        return {'checked':len(checks),'correct':sum(checks)}
    raw=[];lexical_candidates={}
    for q in QUERIES:
        candidates,_=call('search',q['query'],'--limit','20');lexical_candidates[q['id']]=candidates
        samples=[]
        for _ in range(2):top,cost=call('search',q['query'],'--limit','5');samples.append(cost)
        raw.append(dict(q,engine='fts5',model=None,top=names(top),metrics=score(names(top),q),cost=cost,samples=samples,citations=citations(top)))
    storage_before=db.stat().st_size
    indexing={};models_receipts={}
    for model_name in ['e5-small','minilm']:
        model=REPO/'artifacts/models'/model_name
        models_receipts[model_name]={'manifest':json.loads((model/'manifest.json').read_bytes()),'manifest_sha256':sha(model/'manifest.json'),'directory_bytes':directory_bytes(model)}
        v,cost=call('rebuild-embeddings','--model',model)
        conn=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True)
        vectors=[(r[0],json.loads(r[1])) for r in conn.execute('SELECT id,vector FROM embeddings WHERE model=? AND kind=\'chunk\' ORDER BY id',[v['model_sha256']])]
        vector_json_bytes=conn.execute('SELECT sum(length(vector)) FROM embeddings WHERE model=?',[v['model_sha256']]).fetchone()[0]
        conn.close();assert len(vectors)==1000
        qpath=run/('qdrant-'+model_name)
        client=QdrantClient(path=str(qpath))
        start=time.perf_counter();client.create_collection('comparison',vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
        for i in range(0,len(vectors),128):client.upsert('comparison',[models.PointStruct(id=n,vector=vec) for n,vec in vectors[i:i+128]],wait=True)
        qindex_ms=(time.perf_counter()-start)*1000
        indexing[model_name]={'sqlite_rebuild':v,'sqlite_cost':cost,'sqlite_file_bytes_after_model':db.stat().st_size,'vector_json_bytes':vector_json_bytes,'qdrant_seed_from_same_vectors_ms':qindex_ms,'qdrant_seed_excludes_embedding':True}
        for q in QUERIES:
            # Two real CLI samples/query; quality from the second identical request.
            samples=[]
            for _ in range(2):h,hcost=call('search',q['query'],'--mode','hybrid','--model',model,'--limit','5');samples.append(hcost)
            raw.append(dict(q,engine='sqlite_hybrid',model=model_name,top=names(h),metrics=score(names(h),q),cost=hcost,samples=samples,citations=citations(h)))
            start=time.perf_counter();encoded=encode(model,{'kind':'query','texts':[q['query']]});encoding_ms=(time.perf_counter()-start)*1000
            save(run/f'query-vector-{model_name}-{q["id"]}.json',encoded)
            start=time.perf_counter()
            sem=client.query_points('comparison',query=encoded['vectors'][0],limit=60,search_params=models.SearchParams(exact=True),with_payload=False,with_vectors=False).points
            # Qdrant local ties are explicitly ordered by ID, matching SQLite.
            sem=sorted(sem,key=lambda p:(-p.score,p.id))
            ranking={}
            for candidates in [[p.id for p in sem],[p['id'] for p in lexical_candidates[q['id']]['results']]]:
                for rank,n in enumerate(candidates):ranking[n]=ranking.get(n,0)+1/(61+rank)
            ids=sorted(ranking,key=lambda n:(-ranking[n],n))[:5]
            core_ms=(time.perf_counter()-start)*1000
            top=[Path(chunks[n]['path']).stem for n in ids]
            qresponse={'ids':ids,'top':top,'cosine_top60':[{'id':p.id,'score':p.score} for p in sem],'rrf_scores':{str(n):ranking[n] for n in ids}}
            save(run/f'qdrant-{model_name}-{q["id"]}.json',qresponse)
            raw.append(dict(q,engine='qdrant_local_hybrid',model=model_name,top=top,metrics=score(top,q),cost={'embedding_model_load_encode_ms':encoding_ms,'vector_search_rrf_ms':core_ms,'lexical_cli_ms':next(r['cost']['ms'] for r in raw if r['engine']=='fts5' and r['id']==q['id']),'process_rss_bytes':psutil.Process().memory_info().rss},sqlite_top5_equal=top==names(h),citations={'checked':0,'correct':0,'note':'Python adapter returns IDs resolved to SQLite corpus snapshot; no Qdrant citation API claimed'}))
            save(run/'raw-results.json',raw)
        client.close();indexing[model_name]['qdrant_local_directory_bytes_closed']=directory_bytes(qpath)
        print('completed',model_name,flush=True)
    summaries=[]
    for engine,model in [('fts5',None),('sqlite_hybrid','e5-small'),('sqlite_hybrid','minilm'),('qdrant_local_hybrid','e5-small'),('qdrant_local_hybrid','minilm')]:
        rows=[r for r in raw if r['engine']==engine and r['model']==model]
        for split in ['development','holdout']:
            rs=[r for r in rows if r['split']==split];s={'engine':engine,'model':model,'split':split,**aggregate([r['metrics'] for r in rs])}
            times=[c['ms'] for r in rs for c in r.get('samples',[r['cost']]) if 'ms' in c]
            s['cli_samples']=len(times);s['cli_p50_ms']=statistics.median(times) if times else None;s['cli_p95_ms']=percentile(times,.95)
            s['citation_checks']=sum(r['citations']['checked'] for r in rs);s['citation_correct']=sum(r['citations']['correct'] for r in rs)
            s['max_response_bytes']=max((r['cost'].get('bytes',0) for r in rs),default=0)
            s['max_cli_sampled_process_tree_rss_bytes']=max((c.get('peak_rss',0) for r in rs for c in r.get('samples',[r['cost']])),default=0)
            if engine=='qdrant_local_hybrid':
                for key in ['embedding_model_load_encode_ms','vector_search_rrf_ms']:
                    s[key+'_p50']=statistics.median(r['cost'][key] for r in rs)
                s['sqlite_top5_equal_queries']=sum(r['sqlite_top5_equal'] for r in rs)
            summaries.append(s)
    assert source_before=={str(p.relative_to(REPO)):sha(p) for p in source_paths}, 'sources changed during benchmark'
    assert binary_before==sha(BINARY), 'binary changed during benchmark'
    report={'run':run.as_posix(),'corpus_documents':len(corpus),'labeled_queries':len(QUERIES),'cli_calls':call_count,'binary_sha256':sha(BINARY),'source_hashes':source_before,'sources_stable':True,'model_receipts':models_receipts,'qdrant_client':importlib.metadata.version('qdrant-client'),'index':index,'index_cost':index_cost,'incremental_cost':incremental_cost,'lexical_db_bytes':storage_before,'final_sqlite_bytes_two_models':db.stat().st_size,'indexing':indexing,'summaries':summaries,'limitations':['Owned synthetic documents, manually declared evidence labels; not real-vault precision or production quality.','Holdout queries/topics frozen before first run; no model or ranking tuning, but not independent human evaluation.','P@5 denominator is five, missing slots count irrelevant; R@5 uses all labeled relevant evidence. nDCG binary judgments.','No-answer false positive means any candidate returned, not an answer generated. Hybrid does not abstain.','Forbidden results count version-incompatible/withdrawn evidence retrieved, even when labeled withdrawn; not recommendations made. Documents have no enforced compatibility filters.','Contradictory sources both labeled relevant as evidence, not equally authoritative advice.','Qdrant-client local exact in-process mode, NOT a Qdrant server/HNSW/network benchmark; existing service/storage untouched.','SQLite timing includes process spawn, artifact hashing, model/session load, encoding, JSON scan and citation hashing. Qdrant stage timings exclude spawn/citation serialization; not apples-to-apples end-to-end latency.','FTS5 and SQLite hybrid both measure limit5, twice per query; lexical top20 additionally collected for identical RRF candidate inputs.','Qdrant uses identical stored vectors and independently encoded query; floating-point ties may affect parity.','SQLite stores JSON float64 vectors with bounded exact scans, not sqlite-vec. Disk sizes include different formats, not a storage-engine verdict.','Sampled RSS every10ms is a lower-bound process-tree maximum; shared native pages may be double-counted. Qdrant RSS is whole benchmark process, not incremental server memory.','No reranker implemented/evaluated; no global activation or vault ingestion.']}
    save(run/'report.json',report)
    save(REPO/'artifacts/hybrid/latest.json',{'run':run.as_posix(),'report_sha256':sha(run/'report.json')})
    print(json.dumps({'run':run.as_posix(),'summaries':summaries},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
