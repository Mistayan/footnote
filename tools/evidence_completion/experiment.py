"""Standalone 2x2 diagnostic; never updates selected/runtime code or old evidence."""
import sys,json,time,uuid,random,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.evidence_completion.core import eligible,get_evidence,request_metadata
from tools.accuracy_validation_v2.session import CorpusIdentitySession
from tools.accuracy_validation_v2.protocol import summarize
from tools.acquisition_repair.evaluator import f
SNAP=ROOT/'artifacts/accuracy-validation-v2/validation-45b7cf7377844257ab27dc02c46662fb'
OLD=ROOT/'artifacts/accuracy-validation-v2/run-9090a031e1014818b42a6df066b68eb1'

class Session(CorpusIdentitySession):
    def __init__(self,run):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        self.run=run;run.mkdir();self.server=None;self.translator=None;self.db=None
        self.docs={d['id']:d for d in f.load(SNAP/'corpus.json')};self.sources=f.load(SNAP/'source-receipts.json')
        self.records=f.load(OLD/'slice96-records.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER)
        self.db=lexical_index(list(self.docs.values()))
        try:
            self.server=Server(run);self.server.start()
            self.index_info=self.index('selected',self.records,np.load(OLD/'slice96-vectors.npy'))
        except Exception:self.close();raise

    def constrained(self,query,request,vector):
        from retrieval_ablation import lexical_or
        from tools.acquisition_repair.core import acquire
        from qdrant_quality import fresh_connection
        allowed={d['id'] for d in eligible(list(self.docs.values()),self.sources,request)}
        pointids=[i+1 for i,r in enumerate(self.records) if eligible([r],self.sources,request)]
        fresh_connection(self.server)
        payload=dict(query=vector.tolist(),limit=400,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=512),filter={'must':[{'has_id':pointids}]})
        response=self.server.request('POST','/collections/selected/points/query',payload)
        dense=acquire(response['result']['points'],self.records,[],100)['dense']
        assert all(n in allowed for n in dense)
        lexical=[n for n in lexical_or(self.db,query) if n in allowed][:10]
        contributions={}
        for branch,names in [('dense',dense),('lexical',lexical)]:
            for rank,n in enumerate(names,1):contributions.setdefault(n,{})[branch]=dict(rank=rank,contribution=1/(60+rank))
        pool=sorted(contributions,key=lambda n:(-sum(x['contribution'] for x in contributions[n].values()),n))[:20]
        ranking,scores=self.ranker.rank(query,[self.docs[n] for n in pool])
        return dict(pool=pool,ranked=ranking,scores=scores,top5=ranking[:5],contributions=contributions,server_response=response,server_request=payload,allowed_parent_count=len(allowed),allowed_point_count=len(pointids),lexical=lexical,dense=dense)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def historical():
    files=[]
    for base in [ROOT/'artifacts/accuracy-validation-v2',ROOT/'tools/accuracy_validation_v2',ROOT/'tools/acquisition_repair']:
        files += [p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'storage' not in p.parts and 'temp' not in p.parts]
    files += [ROOT/'docs/benchmarks/BILINGUAL-EVIDENCE-AUDIT.md']
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def run():
    started=time.perf_counter();run=ROOT/'artifacts/evidence-completion'/('diagnostic-'+uuid.uuid4().hex);run.mkdir(parents=True)
    original=f.load(OLD/'results.json');old={r['id']:r for r in original if r['variant']=='selected'}
    questions=f.load(SNAP/'test-judgments.json');assert len(questions)==52
    requests=[dict(id=q['id'],query=q['query'],metadata=request_metadata(q['query'])) for q in questions]
    dump(run/'requests.json',requests)
    before=historical();dump(run/'historical-before.json',before)
    rubric=dict(status='new evidence; review pending; not acceptance',support='Complete answer from presented text ONLY, correct version/scope and explicit source edition; no outside context. pass/fail/uncertain with verbatim support offsets; multipart support required.',boundaries='Structural completion is not semantic correctness. Original windows receive no credit from added spans.',review='Send only rubric and blind-packet to independent reviewer; freeze verdicts before mapping release. No labels, pipeline, scores or acceptance in packet.')
    dump(run/'RUBRIC.json',rubric)
    protocol=dict(before_inference=True,utc=f.now(),diagnostic_only=True,fresh_acceptance=False,queries=52,factors={'completion':[False,True],'explicit_source_constraint':[False,True]},retrieval='actual resident Qdrant slice96/dense point400 parent100 + original FTS10 RRF60 pool20 original resident mMARCO512; original parent rank input unchanged',completion='Exact normalized original source sentence/paragraph/fenced-code/REPL outer boundaries; max2500 Unicode characters; no crop if overbudget: original with incomplete flag. No generated evidence, no labels/query input to completion.',constraints='Explicit request metadata from narrow generic EN/FR source-edition parser, frozen requests.json; authoritative receipts.language, not query language or body-language detection; failclosed unknown; before Qdrant400, dense100, lexical10, pool20 AND presentation/get',refusal='original max candidate reranker logit >=2.5, never fitted; same unchanged rank input; completion cannot affect scores',limits={'wall_seconds':1200,'downloads':False,'cpu_threads':'pinned existing encoder/ranker settings'},code={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'tools/evidence_completion/core.py',ROOT/'tests/test_evidence_completion.py']},requests_sha256=sha(run/'requests.json'),rubric_sha256=sha(run/'RUBRIC.json'),historical_sha256=sha(run/'historical-before.json'))
    dump(run/'protocol-freeze.json',protocol)
    texts={s:(SNAP/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in f.load(SNAP/'source-receipts.json')}
    results=[];raw=[]
    from server_benchmark import ResourceSampler
    with Session(run/'live') as session:
        sampler=ResourceSampler(session.server);sampler.thread.start()
        try:
            for q,req in zip(questions,requests):
                if time.perf_counter()-started>1100:raise TimeoutError('experiment wall budget')
                control=session.search(q['query'],q['language'])
                assert control['pool']==old[q['id']]['pool'] and control['ranked']==old[q['id']]['ranked'] and control['scores']==old[q['id']]['scores'],q['id']
                constrained=session.constrained(q['query'],req['metadata'],session.encoder.encode([q['query']],'query')[0]) if req['metadata'] else control
                raw.append(dict(id=q['id'],control=control,constraint=constrained,request=req))
                for gated,r in [(False,control),(True,constrained)]:
                    for completed in [False,True]:
                        evidence=[get_evidence(session.docs[n],texts,session.sources,req['metadata'] if gated else {},completed) for n in r['ranked'][:5]]
                        accepted=bool(r['ranked']) and max(r['scores'].values(),default=float('-inf'))>=2.5
                        results.append(dict(q,variant=f'completion{int(completed)}_constraint{int(gated)}',request=req['metadata'],pool=r['pool'],ranked=r['ranked'],scores=r['scores'],accepted=accepted,evidence=evidence))
                with (run/'progress.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(raw[-1],ensure_ascii=False)+'\n')
                print(q['id'],'live+original parity',flush=True)
        finally:
            sampler.stop.set();sampler.thread.join()
            dump(run/'resource-samples.json',sampler.rows)
    dump(run/'cleanup.json',session.cleanup)
    assert session.cleanup['server']['port_closed'] and session.cleanup['server']['process_exited']
    dump(run/'retrieval-records-DO-NOT-SEND.json',raw);dump(run/'results-DO-NOT-SEND.json',results)
    # Candidate-only review packet: exact query/full presented evidence/provenance. No answer labels.
    pairs={};mapping=[]
    for r in results:
        if not r['evidence']:continue
        e=r['evidence'][0];view=e['presentation'];doc=e['original'];key=(r['query'],view['text'],doc['source'],view['start'],view['end'])
        pairs.setdefault(key,dict(query=r['query'],text=view['text'],source_url=e['provenance']['url'],source_language=e['provenance']['language'],source_version=e['provenance']['version'],source_raw_sha256=e['provenance']['sha256'],normalized_source_sha256=e['provenance']['text_sha256'],excerpt_sha256=view['sha256'],start=view['start'],end=view['end']))
        mapping.append(dict(id=r['id'],variant=r['variant'],key=key,accepted=r['accepted']))
    keys=list(pairs);random.Random(20261020).shuffle(keys);ids={key:f'E{i:03}' for i,key in enumerate(keys,1)}
    dump(run/'blind-packet.json',[dict(review_id=ids[k],**pairs[k]) for k in keys])
    dump(run/'mapping-DO-NOT-SEND.json',[dict(id=m['id'],variant=m['variant'],review_id=ids[m['key']],accepted=m['accepted']) for m in mapping])
    metrics={v:summarize([r for r in results if r['variant']==v],2.5) for v in sorted({r['variant'] for r in results})}
    costs={}
    for v in metrics:
        rows=[r for r in results if r['variant']==v];views=[e for r in rows for e in r['evidence']]
        costs[v]=dict(top5_chars=sum(len(e['presentation']['text']) for e in views),top1_chars=sum(len(r['evidence'][0]['presentation']['text']) for r in rows if r['evidence']),envelope_bytes=len(json.dumps([r['evidence'] for r in rows],ensure_ascii=False).encode()),max_chars=max(len(e['presentation']['text']) for e in views),incomplete=sum(e['presentation'].get('budget_exceeded',False) for e in views),changed_hashes=sum(e['presentation']['sha256']!=e['original'].get('sha256') for e in views))
    for r in results:
        for e in r['evidence']:
            p=e['presentation'];d=e['original'];assert texts[d['source']][p['start']:p['end']]==p['text'];assert hashlib.sha256(p['text'].encode()).hexdigest()==p['sha256'];assert p['start']<=d['start'] and p['end']>=d['end']
    after=historical();assert before==after
    for path,h in protocol['code'].items():assert sha(ROOT/path)==h
    dump(run/'historical-verification.json',dict(unchanged=True,files=len(before),before_sha256=sha(run/'historical-before.json')))
    report=dict(run=str(run),diagnostic_only=True,fresh_acceptance=False,queries=52,factor_rows=len(results),live_original_parity=52,explicit_requests=[r for r in requests if r['metadata']],metrics=metrics,costs=costs,blind_pairs=len(pairs),historical_files_unchanged=len(before),cleanup=session.cleanup,wall_seconds=time.perf_counter()-started,semantic_review='PENDING; no expanded source gets original-presentation credit')
    dump(run/'report.json',report)
    manifest={str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and 'storage' not in p.parts and 'temp' not in p.parts}
    dump(run/'artifact-sha256.json',manifest)
    assert all(sha(run/p)==h for p,h in manifest.items())
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return run

if __name__=='__main__':run()
