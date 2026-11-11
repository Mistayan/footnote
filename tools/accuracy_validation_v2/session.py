"""Corpus-binding adapter only: IdentitySearchSession.search is inherited unchanged.
Original constructor hardcodes old snapshot and refuses v2 paths. This constructor
binds label-free supplied sources/parents/child vectors; ranking is NOT reimplemented.
"""
import time,uuid,json
from pathlib import Path
from tools.acquisition_repair.identity_evaluator import IdentitySearchSession,CONTROL
from tools.acquisition_repair.evaluator import ROOT,SEED,SNAPSHOT,f
from tools.acquisition_repair.core import source_slices

class CorpusIdentitySession(IdentitySearchSession):
    def __init__(self,snapshot,run,records=None,matrix=None):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        from tokenizers import Tokenizer
        self.run=Path(run).resolve()
        if not self.run.is_relative_to(ROOT/'artifacts/accuracy-validation-v2'):raise ValueError('owned v2 directory required')
        self.run.mkdir(parents=True,exist_ok=False);self.server=None;self.translator=None;self.db=None
        self.docs={d['id']:d for d in f.load(snapshot/'corpus.json')};self.sources=f.load(snapshot/'source-receipts.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER)
        if records is None:
            texts={s:(snapshot/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in self.sources}
            tok=Tokenizer.from_file(str(ROOT/'artifacts/models/minilm/tokenizer.json'));tok.no_truncation();tok.no_padding()
            records=source_slices(texts,list(self.docs.values()),tok,96,24)
        self.records=records;f.save(self.run/'slice96-records.json',records)
        if matrix is None:matrix=self.encoder.encode([r['text'] for r in records],'passage')
        np.save(self.run/'slice96-vectors.npy',matrix)
        self.db=lexical_index(list(self.docs.values()))
        try:
            self.server=Server(self.run);self.server.start();self.index_info=self.index('selected',records,matrix)
        except Exception:self.close();raise

    def index(self,name,records,matrix):
        import numpy as np
        from qdrant_quality import fresh_connection
        fresh_connection(self.server)
        self.server.request('PUT','/collections/'+name,dict(vectors=dict(size=384,distance='Cosine',on_disk=False),shard_number=1,hnsw_config=dict(m=16,ef_construct=100,full_scan_threshold=10),optimizers_config=dict(indexing_threshold=1,default_segment_number=1)))
        for offset in range(0,len(records),128):
            self.server.request('PUT','/collections/'+name+'/points?wait=true',dict(points=[dict(id=i+1,vector=matrix[i].tolist(),payload={'record_id':records[i]['id']}) for i in range(offset,min(offset+128,len(records)))]))
        deadline=time.monotonic()+90
        while True:
            info=self.server.request('GET','/collections/'+name)['result']
            if info['status']=='green' and info['indexed_vectors_count']==len(records):break
            if time.monotonic()>deadline:raise TimeoutError(name)
            time.sleep(.2)
        back=[]
        for offset in range(0,len(records),128):
            back+=self.server.request('POST','/collections/'+name+'/points',dict(ids=list(range(offset+1,min(offset+128,len(records))+1)),with_vector=True,with_payload=True))['result']
        back.sort(key=lambda p:p['id']);assert len(back)==len(records)
        assert all(p['payload']['record_id']==records[i]['id'] for i,p in enumerate(back))
        error=float(np.max(np.abs(matrix-np.asarray([p['vector'] for p in back]))));assert error<1e-6
        f.save(self.run/(name+'-readback.json'),dict(info=info,max_abs_error=error,points=back))
        return info


def verify_adapter():
    import numpy as np
    # Exact old vectors/records, not a re-encoding ablation.
    run=ROOT/'artifacts/accuracy-validation-v2'/('adapter-parity-'+uuid.uuid4().hex)
    f.save(run.with_suffix('.freeze.json'),dict(utc=f.now(),adapter_sha256=f.sha(Path(__file__)),before_inference=True,method='inherited IdentitySearchSession.search; exact constructor-binding parity over old dev21'))
    old={r['id']:r for r in f.load(CONTROL/'results.json')};count=0
    with CorpusIdentitySession(SNAPSHOT,run,f.load(SEED/'slice96-records.json'),np.load(SEED/'slice96-vectors.npy')) as session:
        assert CorpusIdentitySession.search is IdentitySearchSession.search
        for q in f.load(SNAPSHOT/'development-judgments.json'):
            r=session.search(q['query'],q['language']);e=old[q['id']]
            assert r['pool']==e['pool'] and r['scores']==e['logits'] and r['ranked']==e['ranking'];count+=1
    f.save(run/'report.json',dict(exact_parity_requests=count,cleanup=session.cleanup,inherited_search_unchanged=True))
    print('ADAPTER PARITY',run,count,flush=True)
    return count==21 and session.cleanup['server']['process_exited'] and session.cleanup['server']['port_closed']
