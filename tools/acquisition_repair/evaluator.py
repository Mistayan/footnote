"""Callable selected development configuration. No judgments enter SearchSession.

with SearchSession(selected_config_path, NEW_owned_run_directory) as session:
    result = session.search(original_query, language='fr')

Original sources are always the evidence; generated pivot is query text only.
"""
import sys, time, re, json, uuid, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
import fresh_retrieval_evaluation as f
from tools.acquisition_repair.core import acquire
SEED=ROOT/'artifacts/acquisition-repair/ar-40915afaca8b4fcdb699e70d7ad1b5bf'
SNAPSHOT=ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'


def preserve_query(original,pivot):
    from pivot_language_experiment import protect
    spans=[s for _,s in protect(original)[1]]
    spans += re.findall(r'--[\w-]+(?:=[\w.-]+)?|\b\w+=(?:True|False|None|\w+)\b',original)
    for span in spans:
        if pivot.count(span)!=original.count(span):return False
    # Preserve ordering of protected spans too, not just membership.
    pos=0
    for _,span in protect(original)[1]:
        at=pivot.find(span,pos)
        if at<0:return False
        pos=at+len(span)
    neg=bool(re.search(r'\b(ne|pas|jamais|sans|aucun|non)\b',original,re.I))
    return not neg or bool(re.search(r'\b(not|no|never|without|none|non)\b|n.t\b',pivot,re.I))


class SearchSession:
    def __init__(self,config,run):
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        from tools.accuracy_iteration.pivot_control import Translator
        import numpy as np
        self.run=Path(run).resolve()
        if not self.run.is_relative_to(ROOT/'artifacts/acquisition-repair'):raise ValueError('owned new artifact required')
        self.run.mkdir(parents=True,exist_ok=False)
        self.config=f.load(config);self.seed=Path(self.config['run']);self.server=None;self.translator=None;self.db=None
        if self.config['name']!='slice96_pivot_20':raise ValueError('this callable exports only frozen slice96_pivot20')
        for n,h in self.config['code_inputs'].items():
            if f.sha(ROOT/n)!=h:raise ValueError('changed selected input '+n)
        artifacts=f.load(self.seed/'artifact-sha256.json')
        for n in ('slice96-records.json','slice96-vectors.npy','selected-config.json'):
            assert f.sha(self.seed/n)==artifacts[n]
        f.verify_snapshot(SNAPSHOT)
        self.docs={d['id']:d for d in f.load(SNAPSHOT/'corpus.json')}
        self.sources=f.load(SNAPSHOT/'source-receipts.json')
        self.records=f.load(self.seed/'slice96-records.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER)
        self.db=lexical_index(list(self.docs.values()))
        try:
            self.server=Server(self.run);self.server.start();self.server.request('PUT','/collections/selected',dict(vectors=dict(size=384,distance='Cosine',on_disk=False),shard_number=1,hnsw_config=dict(m=16,ef_construct=100,full_scan_threshold=10),optimizers_config=dict(indexing_threshold=1,default_segment_number=1)))
            matrix=np.load(self.seed/'slice96-vectors.npy')
            for offset in range(0,len(self.records),128):
                self.server.request('PUT','/collections/selected/points?wait=true',dict(points=[dict(id=i+1,vector=matrix[i].tolist(),payload={'record_id':self.records[i]['id']}) for i in range(offset,min(offset+128,len(self.records)))]))
            deadline=time.monotonic()+90
            while True:
                info=self.server.request('GET','/collections/selected')['result']
                if info['status']=='green' and info['indexed_vectors_count']==len(self.records):break
                if time.monotonic()>deadline:raise TimeoutError('selected index')
                time.sleep(.2)
            self.translator=Translator(self.run/'translator.log')
            self.index_info=info
        except Exception:
            self.close();raise

    def search(self,query,language='en'):
        from retrieval_ablation import lexical_or
        from qdrant_quality import fresh_connection
        if language not in ('en','fr'):raise ValueError('explicit supported language required')
        t=time.perf_counter(); tr=self.translator.translate(query) if language=='fr' else dict(pivot=query,ok=True,reason='identity English')
        tr['preservation_checks_pass']=tr['ok'] and preserve_query(query,tr['pivot'])
        if not tr['preservation_checks_pass']:tr['pivot']=query;tr['fallback']='original retained after preservation failure'
        translated=time.perf_counter();vector=self.encoder.encode([query],'query')[0];encoded=time.perf_counter()
        fresh_connection(self.server)
        response=self.server.request('POST','/collections/selected/points/query',dict(query=vector.tolist(),limit=400,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=512)))
        searched=time.perf_counter();orig=lexical_or(self.db,query);pivot=lexical_or(self.db,tr['pivot'])
        dense=acquire(response['result']['points'],self.records,[],100)['dense'];contributions={}
        for branch,names,weight in [('dense',dense,1),('original',orig[:10],.5),('pivot',pivot[:10],.5)]:
            for rank,n in enumerate(names,1):contributions.setdefault(n,{})[branch]=dict(rank=rank,contribution=weight/(60+rank))
        union=sorted(contributions,key=lambda n:(-sum(x['contribution'] for x in contributions[n].values()),n));pool=union[:20];acquired=time.perf_counter()
        ranking,scores=self.ranker.rank(query,[self.docs[n] for n in pool]);ranked=time.perf_counter()
        evidence=[self.docs[n]|dict(url=self.sources[self.docs[n]['source']]['url'],raw_sha256=self.sources[self.docs[n]['source']]['sha256'],judgment='UNKNOWN; callable has no labels') for n in ranking[:5]]
        json.dumps(evidence,ensure_ascii=False).encode('utf8');ended=time.perf_counter()
        return dict(query=query,language=language,translation=tr,pool=pool,ranked=ranking,scores=scores,top5=ranking[:5],accepted=bool(ranking),evidence=evidence,contributions=contributions,server_response=response,timing_ms=dict(translation=(translated-t)*1000,encode=(encoded-translated)*1000,backend=(searched-encoded)*1000,lexical_fusion=(acquired-searched)*1000,rerank=(ranked-acquired)*1000,evidence_serialization=(ended-ranked)*1000,e2e=(ended-t)*1000))

    def close(self):
        receipt={}
        if self.translator:receipt['translator']=self.translator.close();self.translator=None
        if self.server:receipt['server']=self.server.close();self.server=None
        if self.db:self.db.close();self.db=None
        f.save(self.run/'cleanup.json',receipt)
        return receipt

    def __enter__(self):return self
    def __exit__(self,*args):self.cleanup=self.close()


def verify_callable():
    run=ROOT/'artifacts/acquisition-repair'/('callable-'+uuid.uuid4().hex)
    # New wrapper checks are frozen BEFORE inference; source experiment untouched.
    freeze=dict(utc=f.now(),before_inference=True,status='development callable parity, NOT fresh',config_sha256=f.sha(SEED/'selected-config.json'),code_sha256=f.sha(Path(__file__)),tests_sha256=f.sha(ROOT/'tests/test_acquisition_repair_callable.py'),preservation='strengthened failclosed CLI/assignment/version/order/negation checks; no score/model/selection changes')
    # SearchSession owns mkdir, preserve declaration in adjacent unique file.
    f.save(run.with_suffix('.freeze.json'),freeze)
    old={r['id']:r for r in f.load(SEED/'rerank.json') if r['variant']=='slice96_pivot_20'}
    queries=f.load(SNAPSHOT/'development-judgments.json');rows=[];started=time.perf_counter()
    with SearchSession(SEED/'selected-config.json',run) as session:
        startup=(time.perf_counter()-started)*1000
        for q in queries:
            r=session.search(q['query'],q['language']); expected=old[q['id']]
            assert r['pool']==expected['pool'],q['id']
            assert r['ranked']==expected['ranking'] and r['scores']==expected['logits'],q['id']
            rows.append(dict(id=q['id'],**r));print(q['id'],'live callable exact parity',flush=True)
        f.save(run/'results.json',rows)
        info=session.index_info
    report=dict(verified=True,run=str(run),requests=len(rows),exact_scores_ranks_pools=len(rows),fresh_acceptance=False,index=info,startup_ms=startup,cleanup=session.cleanup,latency_ms={stage:dict(p50=statistics.median([r['timing_ms'][stage] for r in rows]),p95=sorted(r['timing_ms'][stage] for r in rows)[math_ceil95(len(rows))]) for stage in rows[0]['timing_ms']})
    assert report['cleanup']['server']['process_exited'] and report['cleanup']['server']['port_closed']
    assert f.sha(Path(__file__))==freeze['code_sha256']
    f.save(run/'report.json',report)
    declaration=dict(name='slice96_pivot_20_callable',status='experimental development-selected; no acceptance',seed_selected_config=str(SEED/'selected-config.json'),seed_selected_config_sha256=freeze['config_sha256'],callable='tools.acquisition_repair.evaluator.SearchSession(config, new_owned_run).search(original_query, language)',wrapper_sha256=freeze['code_sha256'],parity_report=str(run/'report.json'),parity_report_sha256=f.sha(run/'report.json'))
    f.save(run/'callable-config.json',declaration)
    print(json.dumps(report,indent=2),flush=True)
    return report


def math_ceil95(n):
    import math
    return math.ceil(.95*n)-1

if __name__=='__main__':verify_callable()
