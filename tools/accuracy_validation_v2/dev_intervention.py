"""One finite DEV-ONLY ranking intervention; fresh validation is NEVER loaded.
Uniform 600-char stride400 parent views, unchanged original pool20; rank each
view with same resident pinned mMARCO, parent=max view score. No label-centering.
Original parent remains citation/evidence. This is not the fresh selected method.
"""
import uuid,time,json
from pathlib import Path
from tools.acquisition_repair.evaluator import ROOT,SNAPSHOT,f
from tools.accuracy_validation_v2.protocol import summarize,fit_refusal
from tools.accuracy_validation_v2.replay import CUTOFFS


def views(documents,width=600,stride=400):
    if not 0<stride<=width:raise ValueError('invalid windows')
    result=[]
    for d in documents:
        for start in range(0,len(d['text']),stride):
            body=d['text'][start:start+width]
            result.append(dict(id=d['id']+'::rankview'+str(start),parent_id=d['id'],text=body,source=d['source'],start=d['start']+start,end=d['start']+start+len(body)))
    return result


def run():
    from retrieval_ablation import CrossEncoder
    replay=ROOT/'artifacts/accuracy-validation-v2/replay-9afbb1909b3d4677abe8899b859b8a6d'
    rows=f.load(replay/'development-results.json');docs={d['id']:d for d in f.load(SNAPSHOT/'corpus.json')}
    output=ROOT/'artifacts/accuracy-validation-v2'/('dev-view-'+uuid.uuid4().hex);output.mkdir()
    paths=[Path(__file__),ROOT/'tools/accuracy_validation_v2/protocol.py',ROOT/'tests/test_accuracy_validation_v2_dev.py',f.RANKER/'receipt.json']+[f.RANKER/n for n in f.load(f.RANKER/'receipt.json')['files']]
    freeze=dict(utc=f.now(),before_inference=True,scope='old development ONLY; new validation not opened; NO test reselect',variant=dict(width=600,stride=400,aggregation='max raw snippet logit per original parent, ID ties',candidates='exact saved previously verified identity pool20; no backend measurement',evidence='full unchanged parent, not label-derived view; no headings or query-added text'),reason='fresh selected method below80 with pool-present UNKNOWN top1; isolate ranking evidence granularity before more acquisition; source-language duplicate labels remain a separate limitation',refusal=dict(cutoffs=CUTOFFS,fit='DEV balanced score identical finite rule; also frozen existing2.5 control'),bound=dict(seconds=240,max_requests=21,max_model_replacements=0,max_test_queries=0),inputs={p.relative_to(ROOT).as_posix():f.sha(p) for p in paths},dev_results_sha256=f.sha(replay/'development-results.json'))
    f.save(output/'execution-freeze.json',freeze);ranker=CrossEncoder(f.RANKER);results=[];start=time.perf_counter()
    for r in rows:
        if time.perf_counter()-start>240:raise TimeoutError('dev intervention240s')
        chunks=views([docs[n] for n in r['pool']]);ranking,scores=ranker.rank(r['query'],chunks)
        parent_scores={n:max(scores[c['id']] for c in chunks if c['parent_id']==n) for n in r['pool']}
        ordered=sorted(parent_scores,key=lambda n:(-parent_scores[n],n))
        results.append(dict(id=r['id'],query=r['query'],language=r['language'],evidence_language=r['evidence_language'],relevant=r['relevant'],pool=r['pool'],ranked=ordered,scores=parent_scores,top5=ordered[:5],view_ranking=ranking,view_scores=scores,views=chunks))
    fit=fit_refusal(results,CUTOFFS)
    for n,h in freeze['inputs'].items():assert f.sha(ROOT/n)==h
    report=dict(run=str(output),requests=len(results),fresh_test_not_loaded=True,backend_replayed_not_live=True,old_dev_original_raw=summarize(rows,-100),old_dev_original_cutoff2_5=summarize(rows,2.5),views_raw=summarize(results,-100),views_cutoff2_5=summarize(results,2.5),views_dev_refit=summarize(results,fit['cutoff']),dev_refit_cutoff=fit['cutoff'],wall_seconds=time.perf_counter()-start,at_pair_cap=ranker.at_limit,status='DEVELOPMENT ONLY; no fresh claim; no incumbent change')
    report['selected_for_next_fresh']=report['views_dev_refit']['p1_all_answerable']>report['old_dev_original_cutoff2_5']['p1_all_answerable'] and report['views_dev_refit']['noanswer_falseaccept_rate']<=report['old_dev_original_cutoff2_5']['noanswer_falseaccept_rate']
    f.save(output/'results.json',results);f.save(output/'refusal-dev-fit.json',fit);f.save(output/'report.json',report)
    print(json.dumps(report,indent=2),flush=True);return report

if __name__=='__main__':run()
