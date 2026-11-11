"""FP32 numerical control on exact live-run historical admissible pools."""
from pathlib import Path
import json,time,datetime,statistics
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate,threshold_diagnostic
from tools.accuracy_iteration.ranker import ResidentRanker
from tools.accuracy_iteration.review import render_review

def experiment(run):
    import sys
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    from retrieval_budget_benchmark import present
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False)
    seed=BASE/'int8-live-v1'
    seeds=[r for r in json.loads((seed/'raw-results.json').read_bytes()) if r['variant']=='gte512']
    assert len(seeds)==32
    docs={d['id']:d for d in json.loads((seed/'corpus.json').read_bytes())}
    model=BASE/'gte-fp32'
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),model_receipt_sha256=sha(model/'receipt.json'),seed_raw_sha256=sha(seed/'raw-results.json'),variants=['gtefp32','rrf_incumbent_gtefp32','rrf_incumbent_gteint8'],fusion='equal reciprocal ranks 1/(60+rank), deterministic ID ties; separate saved-rank algorithm replay not independent inference',selection='old DEVELOPMENT only; never sealed test; numerical FP32 control plus fixed equal-rank ensemble after failed larger-model controls',cap=512,budget='32 resident FP32 calls <=1000s; downloaded total<=2GB',code_sha256=sha(Path(__file__)))
    save(run/'freeze.json',freeze)
    ranker=ResidentRanker(model,512); rows=[]; started=time.monotonic()
    controls={r['id']:r for r in json.loads((seed/'raw-results.json').read_bytes()) if r['variant']=='baseline'}
    with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
        for split in ('development','holdout'):
            if split=='holdout':
                dev=[r for r in rows if r['relevant']]
                all_dev=[r for r in json.loads((seed/'raw-results.json').read_bytes()) if r['split']=='development']+rows
                summaries=aggregate(all_dev)
                candidates=[g for g in summaries if g['split']=='development' and g['language']=='all']
                winner=max(candidates,key=lambda g:(g['p1'],g['mrr'],g['variant']=='baseline',g['variant']))['variant']
                save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,summary=summaries,threshold_diagnostic=threshold_diagnostic(all_dev,[None,0,.25,.5,1,2,3,4,6,8])))
            for old in [r for r in seeds if r['split']==split]:
                if time.monotonic()-started>1000: raise TimeoutError('FP32 finite time bound')
                result=ranker.evaluate(old['query'],[docs[n] for n in old['candidates']])
                maps={'gtefp32':result['scores']}
                for label,ranking in [('rrf_incumbent_gtefp32',result['ranked']),('rrf_incumbent_gteint8',old['ranked'])]:
                    base=controls[old['id']]['ranked']
                    maps[label]={n:1/(61+base.index(n))+1/(61+ranking.index(n)) for n in old['candidates']}
                for variant,scores in maps.items():
                    ranked=sorted(scores,key=lambda n:(-scores[n],n)); top=present(ranked,old['eligibility'],True)
                    row=old|dict(variant=variant,ranked=ranked,logits=scores,pair_tokens=result['pair_tokens'],top5=top,metrics=metrics(top,old,old['candidates']),rerank_ms=result['wall_ms'],evidence=[docs[n]|dict(url=next(e['url'] for e in old['evidence'] if e['source']==docs[n]['source']) if any(e['source']==docs[n]['source'] for e in old['evidence']) else json.loads((seed/'sources.json').read_bytes())[docs[n]['source']]['url']) for n in top])
                    rows.append(row); out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush()
                print(old['id'],'FP32',rows[-3]['metrics']['p1'],'fusion',rows[-2]['metrics']['p1'],rows[-1]['metrics']['p1'],round(result['wall_ms']),flush=True)
    save(run/'raw-results.json',rows)
    report=dict(rows=len(seeds),result_rows=len(rows),same_candidates=all(r['candidates']==next(s['candidates'] for s in seeds if s['id']==r['id']) for r in rows),summaries=aggregate(rows),wall_seconds=time.monotonic()-started,mode='resident FP32 inference; fixed pool replay from real Qdrant, NOT repeated server E2E',selection=json.loads((run/'selection-freeze.json').read_bytes()))
    save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8')
    save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
