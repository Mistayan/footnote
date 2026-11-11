"""Uniform frontmatter ablation; original evidence and all pool memberships retained."""
from pathlib import Path
import json,re,time,datetime,sys,statistics
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate,threshold_diagnostic
from tools.accuracy_iteration.ranker import ResidentRanker
from tools.accuracy_iteration.review import render_review

def strip_frontmatter(text):
    return re.sub(r'\A---\r?\n.*?\r?\n---(?:\r?\n|\Z)','',text,count=1,flags=re.S)

def experiment(run):
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    from retrieval_budget_benchmark import present
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False); seed=BASE/'int8-live-v1'; jina=BASE/'jina-control-v1'
    allseeds=json.loads((seed/'raw-results.json').read_bytes())+json.loads((jina/'raw-results.json').read_bytes()); chosen=[r for r in allseeds if r['variant'] in ('gte512','jina512')]; assert len(chosen)==64
    docs={d['id']:d for d in json.loads((seed/'corpus.json').read_bytes())}; sources=json.loads((seed/'sources.json').read_bytes()); transformed={n:strip_frontmatter(d['text']) for n,d in docs.items()}
    save(run/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),variants=['gte_no_frontmatter','jina_no_frontmatter'],hypothesis='broad YAML metadata inflates generic filtering introduction over actual operator/range/threshold evidence; uniform input-only de-frontmatter ablation',semantics='only complete opening --- frontmatter removed, body bytes unchanged; citations always full original; unchanged pairs reuse exact original logits; not full independently measured latency',selection='old DEVELOPMENT only; sealed test untouched',code_sha256=sha(Path(__file__)),seed_sha256=sha(seed/'raw-results.json'),changed_document_ids=[n for n,d in docs.items() if transformed[n]!=d['text']]))
    rankers={'gte512':ResidentRanker(BASE/'gte-int8',512),'jina512':ResidentRanker(BASE/'jina-int8',512)}; rows=[]; changed=0; started=time.monotonic()
    with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
        for split in ('development','holdout'):
            if split=='holdout':
                dev=[r for r in allseeds+rows if r['split']=='development']; summaries=aggregate(dev); candidates=[g for g in summaries if g['split']=='development' and g['language']=='all']; winner=max(candidates,key=lambda g:(g['p1'],g['mrr'],g['variant']=='baseline',g['variant']))['variant']
                save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,summaries=summaries,threshold_diagnostic=threshold_diagnostic(dev,[None,0,.25,.5,1,2,3,4,6,8])))
            for old in [r for r in chosen if r['split']==split]:
                changed_docs=[docs[n]|{'text':transformed[n]} for n in old['candidates'] if transformed[n]!=docs[n]['text']]
                result=rankers[old['variant']].evaluate(old['query'],changed_docs); scores=old['logits']|result['scores']; changed+=len(changed_docs)
                ranked=sorted(scores,key=lambda n:(-scores[n],n)); top=present(ranked,old['eligibility'],True); variant=('gte' if old['variant']=='gte512' else 'jina')+'_no_frontmatter'
                row=old|dict(variant=variant,ranked=ranked,logits=scores,pair_tokens=old['pair_tokens']|result['pair_tokens'],top5=top,metrics=metrics(top,old,old['candidates']),rerank_ms=result['wall_ms'],changed_input_ids=[d['id'] for d in changed_docs],original_full_rerank_ms=old['rerank_ms'],evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top]); rows.append(row); out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush(); print(old['id'],variant,row['metrics']['p1'],'changed',len(changed_docs),flush=True)
    save(run/'raw-results.json',rows); report=dict(rows=len(rows),changed_pairs=changed,summaries=aggregate(rows),wall_seconds=time.monotonic()-started); save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8'); save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
