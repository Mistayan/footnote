"""Existing offline OPUS translation with NEW multilingual rankers, same pools."""
from pathlib import Path
import json,time,datetime,statistics,sys,os,subprocess,re
from tools.accuracy_iteration.experiment import BASE,ROOT,save,sha,aggregate,threshold_diagnostic
from tools.accuracy_iteration.ranker import ResidentRanker
from tools.accuracy_iteration.review import render_review

class Translator:
    def __init__(self,logpath):
        research=ROOT/'artifacts/pivot-language/pivot-20261019-a'
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}; env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(research/'hf-offline'),PYTHONIOENCODING='utf-8')
        self.log=Path(logpath).open('w',encoding='utf8')
        self.worker=subprocess.Popen([str(research/'translation-env/Scripts/python.exe'),'-B',str(ROOT/'tools/pivot_language_experiment.py'),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf8',env=env,cwd=ROOT)
        ready=self.worker.stdout.readline()
        if not ready: raise RuntimeError('offline translator initialization failed')
        self.ready=json.loads(ready)
    def translate(self,query):
        self.worker.stdin.write(json.dumps({'query':query,'language':'fr'},ensure_ascii=False)+'\n'); self.worker.stdin.flush(); reply=self.worker.stdout.readline()
        if not reply: raise RuntimeError('translator exited')
        return json.loads(reply)
    def close(self):
        self.worker.stdin.close()
        try:self.worker.wait(timeout=15)
        except subprocess.TimeoutExpired:self.worker.kill(); self.worker.wait(timeout=15)
        self.worker.stdout.close(); self.log.close()
        return dict(translator_pid=self.worker.pid,translator_exited=self.worker.poll() is not None,returncode=self.worker.returncode)

def is_french(query):
    return bool(re.search(r'^(Pourquoi|Comment|Quel|Quelle|Depuis quelle)\b',query))

def experiment(run):
    sys.path.insert(0,str(ROOT/'tools'))
    from accuracy_stepping_stone import metrics
    from retrieval_budget_benchmark import present
    run=Path(run).resolve(); run.mkdir(parents=True,exist_ok=False); seed=BASE/'int8-live-v1'; jina=BASE/'jina-control-v1'
    allseeds=json.loads((seed/'raw-results.json').read_bytes())+json.loads((jina/'raw-results.json').read_bytes()); chosen=[r for r in allseeds if r['variant'] in ('gte512','jina512')]; assert len(chosen)==64
    docs={d['id']:d for d in json.loads((seed/'corpus.json').read_bytes())}; sources=json.loads((seed/'sources.json').read_bytes())
    freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),variants=['gte_pivot','gte_combined','jina_pivot','jina_combined'],combination='.5 original raw logit + .5 pivot raw logit, fixed; English exact identity and actual original score reuse',mode='same frozen actual Qdrant pools, actual local translation/new resident rankers; no repeated backend or E2E claim',selection='old DEVELOPMENT only; all answerable P1 then MRR; baseline ties; sealed final test not accessed',language='uniform anchored French question-word regex; includes Depuis quelle, no question-ID or label lookup',seed_hashes={str(p):sha(p) for p in [seed/'raw-results.json',jina/'raw-results.json',ROOT/'tools/pivot_language_experiment.py',ROOT/'artifacts/pivot-language/pivot-20261019-a/model-receipt.json']},budget='<=32 translation RPCs,<=32 new ranker calls,500s; zero downloads',code_sha256=sha(Path(__file__)))
    save(run/'freeze.json',freeze); translator=None; rows=[]; report={}; started=time.monotonic(); actual=0
    try:
        translator=Translator(run/'translator.log'); rankers={'gte512':ResidentRanker(BASE/'gte-int8',512),'jina512':ResidentRanker(BASE/'jina-int8',512)}
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as out:
            for split in ('development','holdout'):
                if split=='holdout':
                    dev=[r for r in allseeds+rows if r['split']=='development']; summaries=aggregate(dev); candidates=[g for g in summaries if g['split']=='development' and g['language']=='all']; winner=max(candidates,key=lambda g:(g['p1'],g['mrr'],g['variant']=='baseline',g['variant']))['variant']
                    save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=winner,summaries=summaries,threshold_diagnostic=threshold_diagnostic(dev,[None,0,.25,.5,1,2,3,4,6,8])))
                for old in [r for r in chosen if r['split']==split]:
                    if time.monotonic()-started>500:raise TimeoutError('pivot500s bound')
                    fr=is_french(old['query']); translated=translator.translate(old['query']) if fr else dict(pivot=old['query'],ok=True,reason='non-French identity')
                    result=rankers[old['variant']].evaluate(translated['pivot'],[docs[n] for n in old['candidates']]) if fr else dict(scores=old['logits'],pair_tokens=old['pair_tokens'],wall_ms=0)
                    actual+=int(fr); prefix='gte' if old['variant']=='gte512' else 'jina'
                    for suffix,scores in [('pivot',result['scores']),('combined',{n:.5*old['logits'][n]+.5*result['scores'][n] for n in old['candidates']})]:
                        ranked=sorted(scores,key=lambda n:(-scores[n],n)); top=present(ranked,old['eligibility'],True)
                        row=old|dict(variant=prefix+'_'+suffix,language='fr' if fr else 'en',translation=translated,ranked=ranked,logits=scores,pair_tokens=result['pair_tokens'],top5=top,metrics=metrics(top,old,old['candidates']),rerank_ms=result['wall_ms'],evidence=[docs[n]|dict(url=sources[docs[n]['source']]['url']) for n in top])
                        rows.append(row); out.write(json.dumps(row,ensure_ascii=False)+'\n'); out.flush()
                    print(old['id'],prefix,'fr',fr,'pivot',rows[-2]['metrics']['p1'],'combined',rows[-1]['metrics']['p1'],translated['pivot'],flush=True)
        report.update(rows=len(rows),actual_new_ranker_calls=actual,summaries=aggregate(rows),wall_seconds=time.monotonic()-started)
    finally:
        if translator:report['cleanup']=translator.close()
        save(run/'raw-results.json',rows); save(run/'report.json',report); (run/'PER-QUERY-REVIEW.md').write_text(render_review(rows),encoding='utf8'); save(run/'hashes.json',{p.name:sha(p) for p in run.iterdir() if p.is_file() and p.name!='hashes.json'})
    return report
