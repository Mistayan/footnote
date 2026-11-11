"""Post-run structural diagnosis, NOT semantic verdicts or acceptance scoring."""
import json,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'artifacts/evidence-completion/diagnostic-4d656d0e6d954964aadbf9deb9478a2b'
SNAP=ROOT/'artifacts/accuracy-validation-v2/validation-45b7cf7377844257ab27dc02c46662fb'
rows=json.loads((RUN/'results-DO-NOT-SEND.json').read_text(encoding='utf8'))
# These are diagnostic support spans from the published prior audit, never inference input.
probes={
 'v2-006-en':">>> PurePath('a/b.py').full_match('*.py')\nFalse",
 'v2-013-en':'Note that the global side effect on sys.stdout means that this\ncontext manager is not suitable for use in library code and most threaded\napplications. It also has no effect on the output of subprocesses.',
 'v2-020-en':'When and if you commit the transaction block, the committed actions become visible as a unit to other sessions, while the rolled-back actions never become visible at all.'}
ledger=[]
for q,quote in probes.items():
    original=next(r for r in rows if r['id']==q and r['variant']=='completion0_constraint0')['evidence'][0]
    completed=next(r for r in rows if r['id']==q and r['variant']=='completion1_constraint0')['evidence'][0]
    source=(SNAP/'sources'/(original['original']['source']+'.txt')).read_text(encoding='utf8')
    at=source.index(quote);assert quote in completed['presentation']['text'];assert quote not in original['presentation']['text']
    ledger.append(dict(query_id=q,source=original['original']['source'],structural_result='previously cut support span now wholly included; SEMANTIC REVIEW PENDING',quote=quote,quote_start=at,quote_end=at+len(quote),quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),original=original,intervention_v2=completed))
q='v2-011-en';language=[]
for r in rows:
    if r['id']==q:language.append(dict(variant=r['variant'],top1=r['ranked'][0],language=r['evidence'][0]['provenance']['language'],accepted=r['accepted'],score=r['scores'][r['ranked'][0]]))
extra={}
for variant in sorted({r['variant'] for r in rows}):
    subset=[r for r in rows if r['variant']==variant]
    top=[r['evidence'][0] for r in subset if r['evidence']]
    extra[variant]=dict(top1_changed_hashes=sum(e['presentation']['sha256']!=e['original']['sha256'] for e in top),top1_budget_exceeded=sum(e['presentation'].get('budget_exceeded',False) for e in top),all_answerable_denominator=40,rejected_answerables=[r['id'] for r in subset if r['relevant'] and not r['accepted']],directions={lang:dict(requests=len(g:=[r for r in subset if r['language']==lang]),accepted=sum(r['accepted'] for r in g),answerable=sum(bool(r['relevant']) for r in g)) for lang in ['en','fr']})
samples=json.loads((RUN/'resource-samples.json').read_text())
resources={kind:dict(peak_rss_bytes=max(r[kind]['rss'] for r in samples),cpu_seconds=samples[-1][kind]['cpu_s']-samples[0][kind]['cpu_s'],max_threads=max(r[kind]['threads'] for r in samples)) for kind in ['harness','server']}
report=json.loads((RUN/'report.json').read_text())
cost={}
for constraint in [0,1]:
    old=report['costs'][f'completion0_constraint{constraint}'];new=report['costs'][f'completion1_constraint{constraint}']
    cost[str(constraint)]={k:dict(delta=new[k]-old[k],percent=100*(new[k]-old[k])/old[k]) for k in ['top1_chars','top5_chars','envelope_bytes']}
output=dict(structural_crossing_probes=ledger,explicit_source_constraint=language,additional_counts=extra,resources=resources,cost_delta=cost,semantic_correctness='NOT SCORED. Three exact proof spans newly included, not three independently judged passes; no original evidence upgraded.',normalization_risks='Pinned normalized sources strip HTML pre/paragraph semantics; sentence punctuation and recognized REPL/fenced-code boundaries are heuristic, not a full language parser. 2500-char overbudget leaves original untouched and explicitly incomplete. No 512-token cap is claimed; presentation may exceed reranker capacity, but it is never reranked.')
(RUN/'structural-diagnosis-DO-NOT-SEND.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
config=dict(status='FROZEN CANDIDATE FOR NEXT FRESH EVALUATION, NOT SELECTED/ACCEPTED',candidate='source-completion-v2-explicit-constraint-2500chars',factors='retain separate original, completion-only, constraint-only, both controls',retrieval=report['run'],code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'tools/evidence_completion/core.py',ROOT/'tools/evidence_completion/experiment.py']},refusal_cutoff=2.5,request_contract='Caller supplied source_language en/fr; optional narrow generic parser tested; never infer source constraint from query language',fresh_protocol='NEW independent facts/questions/judgments, corpus-wide bilingual applicability coverage frozen before inference. No selection from these old 52. Review only blind-packet+RUBRIC first. All-answerable P@1 goals80/90; coverage/noanswer contract must be declared separately; no implicit acceptance.',blocking_risks=['independent semantic review pending','overbudget fallback','normalized code-block structure lossy','one correctly supported French parents query still refused under frozen cutoff'])
(RUN/'next-fresh-candidate-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
files=['structural-diagnosis-DO-NOT-SEND.json','next-fresh-candidate-config.json']
manifest={p:hashlib.sha256((RUN/p).read_bytes()).hexdigest() for p in files}
manifest['diagnosis_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(RUN/'supplement-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps(dict(structural_probes=len(ledger),additional_counts=extra,resources=resources,cost_delta=cost,supplement_hashes=manifest),indent=2))
