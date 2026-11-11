"""Development-selected simpler control: NO translation model loaded or used.
Original query, slice96 dense100, original FTS top10, pool20, mMARCO512.
"""
import sys,time,uuid,json,statistics
from pathlib import Path
from tools.acquisition_repair.evaluator import SearchSession,SEED,SNAPSHOT,ROOT,f
CONTROL=ROOT/'artifacts/acquisition-repair/pivot-identity-bff14d2bf3eb4b368b65e251750efce0'


class IdentitySearchSession(SearchSession):
    def __init__(self,config,run):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        self.run=Path(run).resolve()
        if not self.run.is_relative_to(ROOT/'artifacts/acquisition-repair'):raise ValueError('new owned artifact required')
        self.run.mkdir(parents=True,exist_ok=False);self.config=f.load(config);self.seed=Path(self.config['run']);self.server=None;self.translator=None;self.db=None
        for n,h in self.config['code_inputs'].items():assert f.sha(ROOT/n)==h,n
        manifest=f.load(self.seed/'artifact-sha256.json')
        for n in ('slice96-records.json','slice96-vectors.npy'):assert f.sha(self.seed/n)==manifest[n]
        f.verify_snapshot(SNAPSHOT)
        self.docs={d['id']:d for d in f.load(SNAPSHOT/'corpus.json')};self.sources=f.load(SNAPSHOT/'source-receipts.json');self.records=f.load(self.seed/'slice96-records.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER);self.db=lexical_index(list(self.docs.values()))
        try:
            self.server=Server(self.run);self.server.start();self.server.request('PUT','/collections/selected',dict(vectors=dict(size=384,distance='Cosine',on_disk=False),shard_number=1,hnsw_config=dict(m=16,ef_construct=100,full_scan_threshold=10),optimizers_config=dict(indexing_threshold=1,default_segment_number=1)))
            matrix=np.load(self.seed/'slice96-vectors.npy')
            for offset in range(0,len(self.records),128):
                self.server.request('PUT','/collections/selected/points?wait=true',dict(points=[dict(id=i+1,vector=matrix[i].tolist(),payload={'record_id':self.records[i]['id']}) for i in range(offset,min(offset+128,len(self.records)))]))
            deadline=time.monotonic()+90
            while True:
                info=self.server.request('GET','/collections/selected')['result']
                if info['status']=='green' and info['indexed_vectors_count']==len(self.records):break
                if time.monotonic()>deadline:raise TimeoutError('identity selected index')
                time.sleep(.2)
            self.index_info=info
        except Exception:self.close();raise

    def search(self,query,language='en'):
        if language not in ('en','fr'):raise ValueError('explicit supported language required')
        # English/identity branch means both lexical10 lists contain original
        # query terms. Their .5+.5 masses equal single original top10 weight1.
        result=super().search(query,'en');result['language']=language
        result['translation']['reason']='NO translation: identity lexical-slot control'
        return result


def verify_identity():
    run=ROOT/'artifacts/acquisition-repair'/('identity-callable-'+uuid.uuid4().hex)
    freeze=dict(utc=f.now(),before_inference=True,selection='development identity control ties pivot P1/MRR; prefer no transformation/model cost',code_sha256=f.sha(Path(__file__)),parent_callable_sha256=f.sha(ROOT/'tools/acquisition_repair/evaluator.py'),control_report_sha256=f.sha(CONTROL/'report.json'),test_sha256=f.sha(ROOT/'tests/test_acquisition_repair_identity.py'),fresh_acceptance=False)
    f.save(run.with_suffix('.freeze.json'),freeze)
    old={r['id']:r for r in f.load(CONTROL/'results.json')};queries=f.load(SNAPSHOT/'development-judgments.json');rows=[];started=time.perf_counter()
    with IdentitySearchSession(SEED/'selected-config.json',run) as session:
        startup=(time.perf_counter()-started)*1000
        for q in queries:
            r=session.search(q['query'],q['language']);e=old[q['id']]
            assert r['pool']==e['pool'] and r['ranked']==e['ranking'] and r['scores']==e['logits'],q['id']
            rows.append(dict(id=q['id'],**r))
        f.save(run/'results.json',rows)
    assert f.sha(Path(__file__))==freeze['code_sha256']
    report=dict(verified=True,exact_parity_requests=len(rows),run=str(run),translation_models_loaded=0,translation_requests=0,startup_ms=startup,cleanup=session.cleanup,e2e_ms=dict(p50=statistics.median(r['timing_ms']['e2e'] for r in rows),p95=sorted(r['timing_ms']['e2e'] for r in rows)[19]),fresh_acceptance=False)
    assert report['cleanup']['server']['process_exited'] and report['cleanup']['server']['port_closed']
    f.save(run/'report.json',report)
    f.save(run/'selected-config.json',dict(name='slice96_original_lexical10_pool20',status='DEVELOPMENT SELECTED, NOT ACCEPTED',seed_input_config=str(SEED/'selected-config.json'),run=str(SEED),callable='tools.acquisition_repair.identity_evaluator.IdentitySearchSession(seed_input_config, new_owned_run).search(original_query, language)',config=dict(slice_cap=96,overlap=24,point_limit=400,dense_parent_limit=100,original_parent_fts_limit=10,rrf_k=60,pool=20,ranker='original pinned mMARCO512',translation=False,abstention='NONE'),wrapper_freeze=freeze,parity_report_sha256=f.sha(run/'report.json'),development_control_report=str(CONTROL/'report.json')))
    print(json.dumps(report,indent=2),flush=True);return report

if __name__=='__main__':verify_identity()
