"""Finite old-development-only matched-pool experiment; never runs archive helpers."""
import json,sys,time,hashlib,uuid,datetime,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.support_verification_probe.core import QA,counts


def run():
    started=time.perf_counter()
    owned=ROOT/'tools/support_verification_probe'
    out=owned/('run-'+uuid.uuid4().hex);out.mkdir()
    dev=ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'
    prior=ROOT/'artifacts/rank-input-repair/diagnostic-3b7f3be280804fa6b6a82c81a4b21b09/development-results-DO-NOT-SEND.jsonl'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    save=lambda n,v:(out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
    inputs=[prior,dev/'corpus.json',dev/'development-judgments.json',dev/'source-receipts.json']
    history={str(p):sha(p) for p in inputs}
    questions=json.loads(inputs[2].read_bytes()); docs={d['id']:d for d in json.loads(inputs[1].read_bytes())};sources=json.loads(inputs[3].read_bytes())
    old={r['id']:r for r in [json.loads(l) for l in prior.read_text(encoding='utf8').splitlines()] if r['variant']=='full2'}
    assert len(questions)==21 and sum(bool(q['relevant']) for q in questions)==16
    assert all(len(old[q['id']]['pool'])==20 for q in questions)
    model=owned/'model';modelhash={p.name:sha(p) for p in model.iterdir() if p.is_file()}
    assert modelhash['model.onnx']=='b0694fd87735fb57ec96afb3f41198512eb304c61b02fc9ebedfe035d1d0d45e'
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),split='OLD DEVELOPMENT 16 answerable + 5 noanswer; incomplete selected-positive labels; no fresh evaluation',inputs=history,model=modelhash,code={p.name:sha(p) for p in [Path(__file__),owned/'core.py']},pool='exact ordered historical full2 20-parent acquisition; no retrieval or labels used to change pool',baseline='current pinned mMARCO full original query and document once, batch4, max512; 2.5 incumbent threshold',qa='question + original body first384 tokens, only_second; max48 answer tokens; no title/pivot; one pair/parent; CLS null minus best valid joint span; no probability/confidence',variants=['baseline','baseline_cut2.5','baseline_QA_gate_zero','QA_rerank_zero','QA_rerank_unthresholded'],calibration='development only: fit margin cutoff per baseline gate and QA rerank. Require zero false accepts among 5 noanswer then maximize selected-label correct accepted, coverage, prefer higher cutoff. Candidate rule frozen after dev; not acceptance.',acceptance='user80 lower/90 stretch over all answerable; diagnostic cannot certify either; experimental zero-noanswer rule not user-approved; require at least baseline correct-accepted and coverage for recommending new independently judged field trial')
    save('execution-freeze.json',freeze)
    save('frozen-questions.json',questions);save('frozen-pools.json',{k:v['pool'] for k,v in old.items()})
    from retrieval_ablation import CrossEncoder
    import fresh_retrieval_evaluation as f
    ranker=CrossEncoder(f.RANKER);qa=QA(model);records=[];variants={k:[] for k in freeze['variants']};gate=[];rerank=[];baseline_seconds=0;qa_seconds=0
    with (out/'pairs.jsonl').open('w',encoding='utf8') as pf, (out/'per-query.jsonl').open('w',encoding='utf8') as qf:
        for q in questions:
            pool=old[q['id']]['pool'];t=time.perf_counter();ranked,scores=ranker.rank(q['query'],[docs[n] for n in pool]);baseline_seconds+=time.perf_counter()-t
            answers={};t=time.perf_counter()
            for n in pool:
                d=docs[n];a=qa.answer(q['query'],d['text']);assert a['text']==d['text'][a['start']:a['end']]
                a.update(parent=n,source=d['source'],source_start=d['start']+a['start'],source_end=d['start']+a['end'],url=sources[d['source']]['url'],source_raw_sha256=sources[d['source']]['sha256'],parent_sha256=d['sha256'],query_id=q['id'],mmarco_logit=scores[n]);answers[n]=a
                pf.write(json.dumps(a,ensure_ascii=False)+'\n');pf.flush()
            qa_seconds+=time.perf_counter()-t
            qarank=sorted(pool,key=lambda n:(answers[n]['null_minus_span'],n));base=ranked[0];candidate=qarank[0]
            row=dict(id=q['id'],query=q['query'],language=q['language'],answerable=bool(q['relevant']),relevant=q['relevant'],baseline_ranked=ranked,baseline_scores=scores,qa_ranked=qarank,baseline_top=answers[base],qa_top=answers[candidate],baseline_exact_historical_scores=scores==old[q['id']]['scores'],baseline_exact_historical_ranks=ranked==old[q['id']]['ranked'],top5_evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url'],qa=answers[n]) for n in qarank[:5]])
            records.append(row);qf.write(json.dumps(row,ensure_ascii=False)+'\n');qf.flush()
            for name,top,accepted in [('baseline',base,True),('baseline_cut2.5',base,scores[base]>=2.5),('baseline_QA_gate_zero',base,answers[base]['null_minus_span']<=0),('QA_rerank_zero',candidate,answers[candidate]['null_minus_span']<=0),('QA_rerank_unthresholded',candidate,True)]:
                variants[name].append(dict(answerable=bool(q['relevant']),correct=top in q['relevant'],accepted=accepted))
            gate.append(dict(answerable=bool(q['relevant']),correct=base in q['relevant'],margin=-answers[base]['null_minus_span']))
            rerank.append(dict(answerable=bool(q['relevant']),correct=candidate in q['relevant'],margin=-answers[candidate]['null_minus_span']))
            print('DEV',q['id'],'baseline',base,'QA',candidate,'margin',-answers[candidate]['null_minus_span'],flush=True)
    summary={k:counts(v) for k,v in variants.items()};calibrated={}
    for name,rr in [('baseline_QA_gate',gate),('QA_rerank',rerank)]:
        cuts=sorted(set([0.0]+[r['margin'] for r in rr]+[max(r['margin'] for r in rr)+1]))
        table=[dict(cutoff=c,**counts([r|dict(accepted=r['margin']>=c) for r in rr])) for c in cuts]
        valid=[r for r in table if r['noanswer_false_accept']==0]
        chosen=max(valid,key=lambda r:(r['correct_accepted'],r['answerable_accepted'],r['cutoff']))
        calibrated[name]=chosen;save(name+'-calibration.json',table)
    save('selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),calibrated=calibrated,scope='development only; no fresh exposure authorized',rule='no promotion on incomplete selected labels'))
    unchanged=all(sha(Path(p))==h for p,h in history.items());assert unchanged
    report=dict(run=str(out),queries=len(records),answerable=16,noanswer=5,qa_pairs=qa.pairs,mmarco_pairs=420,qa_sessions=1,mmarco_sessions=1,qa_session_ids=sorted(set(r['qa_top']['session_id'] for r in records)),historical_unchanged=unchanged,baseline_exact_historical_scores=sum(r['baseline_exact_historical_scores'] for r in records),baseline_exact_historical_ranks=sum(r['baseline_exact_historical_ranks'] for r in records),summary=summary,development_calibrated=calibrated,baseline_seconds=baseline_seconds,qa_seconds=qa_seconds,wall_seconds=time.perf_counter()-started,qa_overflow_pairs=sum(json.loads(l)['overflow_windows_omitted']>0 for l in (out/'pairs.jsonl').read_text(encoding='utf8').splitlines()),downloaded_bytes=sum(p.stat().st_size for p in model.iterdir() if p.is_file()),limitations=['selected-positive IDs incomplete; unknown IDs not judged false','extractive span may be partial especially why/multipart; no semantic complete-answer labels','first384 only; omitted overflow is a bounded negative-control limitation','same development used for fitting and reporting, not fresh80','export has no explicit license/card; upstream CC-BY-4.0 attribution verified, conversion provenance only config _name_or_path; no independent upstream weight parity','Qdrant acquisition replayed fixed pool, not measured live runtime'],cleanup='no servers/children spawned; sessions released at process exit; model retained local for replay; no environment changes')
    del ranker,qa;gc.collect()
    save('report.json',report);save('historical-verification.json',history)
    save('artifact-sha256.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':run()
