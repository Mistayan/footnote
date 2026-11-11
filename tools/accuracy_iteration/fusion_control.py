"""Fixed weak lexical preservation AFTER cross-encoding; saved-rank replay only."""
from pathlib import Path
import json,time,datetime,statistics,sys
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate
from tools.accuracy_iteration.review import render_review

def experiment(run):
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    from retrieval_budget_benchmark import present
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False)
    files=[BASE/n/'raw-results.json' for n in ('int8-live-v1','jina-control-v1','preparation-v1')]; allrows=[r for f in files for r in json.loads(f.read_bytes())]; seeds=[r for r in allrows if r['variant'] in ('baseline','gte512','jina512','jina_no_frontmatter')]; assert len(seeds)==128
    save(run/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),variants={n:[.125,.25] for n in ('baseline','gte512','jina512','jina_no_frontmatter')},mechanism='retain weak exact lexical support lost by crossencoder; 1/(60+rerank) + weight/(60+original lexical rank); absent lexical contributes0, deterministic ID ties; unchanged pool20 and relevance labels',selection='old DEVELOPMENT only all-answerable P1 then MRR; keep baseline ties',mode='SAVED RANK ALGORITHM REPLAY, no model or Qdrant execution and no new E2E measurement',inputs={str(f):sha(f) for f in files},code_sha256=sha(Path(__file__))))
    rows=[]; started=time.perf_counter()
    docs={d['id']:d for d in json.loads((BASE/'int8-live-v1/corpus.json').read_bytes())}; sources=json.loads((BASE/'int8-live-v1/sources.json').read_bytes())
    for split in ('development','holdout'):
        if split=='holdout':
            dev=[r for r in allrows+rows if r['split']=='development']; summaries=aggregate(dev); candidates=[g for g in summaries if g['split']=='development' and g['language']=='all']; winner=max(candidates,key=lambda g:(g['p1'],g['mrr'],g['variant']=='baseline',g['variant']))['variant']
            save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,summaries=summaries))
        for old in [r for r in seeds if r['split']==split]:
            for weight in (.125,.25):
                contributions={n:dict(reranker=1/(61+old['ranked'].index(n)),lexical=weight/(61+old['lexical'].index(n)) if n in old['lexical'] else 0) for n in old['candidates']}; scores={n:sum(c.values()) for n,c in contributions.items()}; ranked=sorted(scores,key=lambda n:(-scores[n],n)); top=present(ranked,old['eligibility'],True)
                row=old|dict(variant=old['variant']+'_lex'+str(weight),ranked=ranked,logits=scores,score_kind='weighted RRF, not logit or confidence',contributions=contributions,top5=top,metrics=metrics(top,old,old['candidates']),evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top],rerank_ms=old['rerank_ms'],timing_scope='reused original rerank component, not new measured latency'); rows.append(row)
    save(run/'raw-results.json',rows); report=dict(rows=len(rows),actual_model_inference_calls=0,summaries=aggregate(rows),algorithm_wall_seconds=time.perf_counter()-started,selection=json.loads((run/'selection-freeze.json').read_bytes()))
    save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8'); save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
