"""Second multilingual checkpoint with explicit noncommercial evaluation boundary."""
from pathlib import Path
import json,time,datetime,statistics,sys
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate,threshold_diagnostic
from tools.accuracy_iteration.ranker import ResidentRanker
from tools.accuracy_iteration.review import render_review

def experiment(run):
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    from retrieval_budget_benchmark import present
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False)
    seed=BASE/'int8-live-v1'; allseeds=json.loads((seed/'raw-results.json').read_bytes()); seeds=[r for r in allseeds if r['variant']=='baseline']; assert len(seeds)==32
    docs={d['id']:d for d in json.loads((seed/'corpus.json').read_bytes())}; sources=json.loads((seed/'sources.json').read_bytes()); model=BASE/'jina-int8'
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),variants=['jina512','jina1024'],model_receipt_sha256=sha(model/'receipt.json'),seed_raw_sha256=sha(seed/'raw-results.json'),selection='old DEVELOPMENT all-answerable P1 then MRR, baseline tie preference; no fresh test read',caps=[512,1024],license='CC-BY-NC-4.0 research/evaluation only; no commercial deployment authorization',mode='frozen actual Qdrant pool replay; resident new logits; NOT new server E2E',budget='64 resident calls,1000s cap, no more checkpoint download total1.93GB',code_sha256=sha(Path(__file__)))
    save(run/'freeze.json',freeze); rankers={f'jina{cap}':ResidentRanker(model,cap) for cap in (512,1024)}; rows=[]; started=time.monotonic()
    with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
        for split in ('development','holdout'):
            if split=='holdout':
                all_dev=[r for r in allseeds if r['split']=='development']+rows
                summaries=aggregate(all_dev); candidates=[g for g in summaries if g['split']=='development' and g['language']=='all']
                winner=max(candidates,key=lambda g:(g['p1'],g['mrr'],g['variant']=='baseline',g['variant']))['variant']
                save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,summary=summaries,threshold_diagnostic=threshold_diagnostic(all_dev,[None,0,.25,.5,1,2,3,4,6,8])))
            for old in [r for r in seeds if r['split']==split]:
                for variant,ranker in rankers.items():
                    if time.monotonic()-started>1000: raise TimeoutError('Jina finite1000s bound')
                    result=ranker.evaluate(old['query'],[docs[n] for n in old['candidates']]); top=present(result['ranked'],old['eligibility'],True)
                    row=old|dict(variant=variant,ranked=result['ranked'],logits=result['scores'],pair_tokens=result['pair_tokens'],top5=top,metrics=metrics(top,old,old['candidates']),rerank_ms=result['wall_ms'],evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top])
                    if 'qfilter-not' in old['candidates']: row['operator_visible']={n:result['visible'][n] for n in old['candidates'] if n in ('qfilter-not','qfilter-must')}
                    rows.append(row); out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush(); print(old['id'],variant,row['metrics']['p1'],round(result['wall_ms']),flush=True)
    save(run/'raw-results.json',rows); report=dict(rows=len(rows),same_candidates=all(r['candidates']==next(s['candidates'] for s in seeds if s['id']==r['id']) for r in rows),summaries=aggregate(rows),wall_seconds=time.monotonic()-started,selection=json.loads((run/'selection-freeze.json').read_bytes()))
    save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8'); save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
