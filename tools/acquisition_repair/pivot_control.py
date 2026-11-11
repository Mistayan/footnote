"""Development-only identity-pivot lexical-slot control: saved acquisition replay,
actual full-candidate resident mMARCO scoring; NOT repeated backend/E2E work.
"""
import sys,time,uuid,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
import fresh_retrieval_evaluation as f
from tools.acquisition_repair.core import acquire
SEED=ROOT/'artifacts/acquisition-repair/ar-40915afaca8b4fcdb699e70d7ad1b5bf'
SNAPSHOT=ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'


def run_control():
    from retrieval_ablation import CrossEncoder,lexical_or
    from technical_quality import lexical_index
    run=ROOT/'artifacts/acquisition-repair'/('pivot-identity-'+uuid.uuid4().hex);run.mkdir(parents=True,exist_ok=False)
    f.verify_snapshot(SNAPSHOT)
    docs={d['id']:d for d in f.load(SNAPSHOT/'corpus.json')};sources=f.load(SNAPSHOT/'source-receipts.json');records=f.load(SEED/'slice96-records.json')
    queries=f.load(SNAPSHOT/'development-judgments.json');old=f.load(SEED/'rerank.json');manifest=f.load(SEED/'artifact-sha256.json')
    frozen_names=['acquisition.json','rerank.json','slice96-records.json']+[q['id']+'-slice96-response.json' for q in queries]
    for n in frozen_names:assert f.sha(SEED/n)==manifest[n]
    freeze=dict(utc=f.now(),before_inference=True,split='development',protocol='prespecified followup identity10+identity10 halfmass duplicate-slot control; equivalent original lexical top10 weight1; same original dense100, pool20, mMARCO512; no diagnostic exposure/selection',code_sha256=f.sha(Path(__file__)),test_sha256=f.sha(ROOT/'tests/test_acquisition_repair_pivot.py'),frozen_inputs={n:manifest[n] for n in frozen_names},label_changes=False,acquisition='saved actual Qdrant response replay; NOT new backend/E2E requests')
    f.save(run/'freeze.json',freeze);ranker=CrossEncoder(f.RANKER);db=lexical_index(list(docs.values()));rows=[]
    try:
        for q in queries:
            points=f.load(SEED/(q['id']+'-slice96-response.json'))['result']['points'];lexical=lexical_or(db,q['query'])[:10]
            acq=acquire(points,records,lexical,20);pool=acq['pool'];start=time.perf_counter();ranking,scores=ranker.rank(q['query'],[docs[n] for n in pool])
            row=dict(q,variant='slice96_identity10x2_20',pool=pool,pool20=pool,ranking=ranking,top5=ranking[:5],logits=scores,rerank_ms=(time.perf_counter()-start)*1000)
            f.decorate_rows([row],docs,sources);rows.append(row)
        f.save(run/'results.json',rows)
    finally:db.close()
    assert f.sha(Path(__file__))==freeze['code_sha256'];assert len(rows)==21
    for q in queries:
        if q['language']=='en':
            a=next(r for r in rows if r['id']==q['id']);b=next(r for r in old if r['id']==q['id'] and r['variant']=='slice96_pivot_20')
            assert a['pool']==b['pool'] and a['logits']==b['logits'] and a['ranking']==b['ranking']
    pairs=[]
    for r in rows:
        if not r['relevant']:continue
        pivot=next(x for x in old if x['id']==r['id'] and x['variant']=='slice96_pivot_20')
        pairs.append(dict(id=r['id'],language=r['language'],identity_hit=r['top5'][0] in r['relevant'],pivot_hit=pivot['top5'][0] in r['relevant']))
    report=dict(run=str(run),requests=len(rows),verified=True,mode='saved acquisition replay + actual new resident full-candidate mMARCO',summary=f.summaries(rows),paired=pairs,english_identity_exact_parity=sum(q['language']=='en' for q in queries),identity_to_pivot_gains=[p['id'] for p in pairs if p['pivot_hit'] and not p['identity_hit']],identity_to_pivot_losses=[p['id'] for p in pairs if p['identity_hit'] and not p['pivot_hit']],fresh_acceptance=False)
    f.save(run/'report.json',report);print(json.dumps(report,indent=2),flush=True);return report

if __name__=='__main__':run_control()
