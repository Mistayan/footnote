"""Actually exercise the frozen exported callable on all historical pools.

Complete pairs are rerun: dynamic-quantization batching may make an incremental
changed-pairs ablation non-identical to a complete request. Never hide that delta.
"""
from pathlib import Path
import json,time,datetime,sys
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate
from tools.accuracy_iteration.evaluator import create_evaluator
from tools.accuracy_iteration.review import render_review

def experiment(run):
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False); config=BASE/'selected-config.json'; before=sha(config)
    save(run/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),config_sha256=before,variants=['jina_no_frontmatter_full','jina_no_frontmatter_full_threshold0'],purpose='Full paired-input inference verification of exported callable, NOT retuning or fresh-test evaluation',code_sha256=sha(Path(__file__))))
    evaluate=create_evaluator(config); seeds=[r for r in json.loads((BASE/'int8-live-v1/raw-results.json').read_bytes()) if r['variant']=='baseline']; previous={r['id']:r for r in json.loads((BASE/'preparation-v1/raw-results.json').read_bytes()) if r['variant']=='jina_no_frontmatter'}; docs={d['id']:d for d in json.loads((BASE/'int8-live-v1/corpus.json').read_bytes())}; sources=json.loads((BASE/'int8-live-v1/sources.json').read_bytes()); rows=[]; deltas=[]; actual_pairs=0; started=time.monotonic()
    with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
        for old in seeds:
            result=evaluate(old['query'],[docs[n] for n in old['candidates']]); actual_pairs+=len(old['candidates'])
            delta=max(abs(result['scores'][n]-previous[old['id']]['logits'][n]) for n in old['candidates']); deltas.append(dict(id=old['id'],max_logit_delta=delta,rank_equal=result['ranked']==previous[old['id']]['ranked'],top1_equal=result['ranked'][:1]==previous[old['id']]['top5'][:1]))
            for name,top in [('jina_no_frontmatter_full',result['ranked'][:5]),('jina_no_frontmatter_full_threshold0',result['top5'])]:
                row=old|dict(variant=name,ranked=result['ranked'],logits=result['scores'],pair_tokens=result['pair_tokens'][0],top5=top,metrics=metrics(top,old,old['candidates']),rerank_ms=result['wall_ms'],evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top]); rows.append(row); out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush()
            print(old['id'],'ranking',rows[-2]['metrics']['p1'],'accepted',result['accepted'],'thresholded',rows[-1]['metrics']['p1'],'delta',round(delta,5),flush=True)
    save(run/'raw-results.json',rows); report=dict(rows=len(seeds),result_rows=len(rows),actual_pairs=actual_pairs,config_unchanged=before==sha(config),summaries=aggregate(rows),incremental_vs_full_deltas=deltas,wall_seconds=time.monotonic()-started)
    save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8'); save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
