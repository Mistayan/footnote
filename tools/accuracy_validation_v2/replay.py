"""Independent live 21-request parity, dev-only refusal and old diagnostic. No tuning."""
import uuid,json
from pathlib import Path
from tools.acquisition_repair.identity_evaluator import IdentitySearchSession,CONTROL
from tools.acquisition_repair.evaluator import ROOT,SEED,SNAPSHOT,f
from tools.accuracy_validation_v2.protocol import summarize,fit_refusal
CUTOFFS=[-100,-10,-7.5,-5,-2.5,0,2.5,5,7.5,10,100]

def run():
    output=ROOT/'artifacts/accuracy-validation-v2'/('replay-'+uuid.uuid4().hex);output.mkdir(parents=True)
    live=ROOT/'artifacts/acquisition-repair'/('v2-diagnostic-'+uuid.uuid4().hex)
    freeze=dict(utc=f.now(),before_inference=True,cutoffs=CUTOFFS,fit='development only, balanced accepted-correct/16 and noanswer rejection/5; ties coverage then lower cutoff',no_diagnostic_tuning=True,selected_sha256=f.sha(ROOT/'artifacts/acquisition-repair/identity-callable-291d5b8e58d24f50b91a34b97a8a473c/selected-config.json'),files={str(p.relative_to(ROOT)).replace('\\','/'):f.sha(p) for p in [Path(__file__),ROOT/'tools/accuracy_validation_v2/protocol.py',ROOT/'tools/acquisition_repair/identity_evaluator.py',ROOT/'tools/acquisition_repair/evaluator.py']})
    f.save(output/'execution-freeze.json',freeze)
    old={r['id']:r for r in f.load(CONTROL/'results.json')};dev=[];diagnostic=[]
    with IdentitySearchSession(SEED/'selected-config.json',live) as session:
        for q in f.load(SNAPSHOT/'development-judgments.json'):
            r=session.search(q['query'],q['language']);e=old[q['id']]
            assert r['pool']==e['pool'] and r['ranked']==e['ranking'] and r['scores']==e['logits'],q['id']
            dev.append(dict(q,**{k:v for k,v in r.items() if k not in q}));print(q['id'],'exact parity',flush=True)
        f.save(output/'development-results.json',dev)
        refusal=fit_refusal(dev,CUTOFFS);f.save(output/'refusal-frozen.json',dict(utc=f.now(),before_diagnostic_and_fresh=True,**refusal))
        with (output/'diagnostic-results.jsonl').open('w',encoding='utf8') as stream:
            for q in f.load(SNAPSHOT/'test-judgments.json'):
                r=session.search(q['query'],q['language']);r=dict(q,**{k:v for k,v in r.items() if k not in q});diagnostic.append(r);stream.write(json.dumps(r,ensure_ascii=False)+'\n');stream.flush()
        f.save(output/'diagnostic-results.json',diagnostic)
    report=dict(run=str(output),live=str(live),exact_parity_requests=len(dev),development=summarize(dev,-100),development_refusal=summarize(dev,refusal['cutoff']),diagnostic=summarize(diagnostic,-100),diagnostic_refusal=summarize(diagnostic,refusal['cutoff']),refusal_cutoff=refusal['cutoff'],diagnostic_directions={a+b:summarize([r for r in diagnostic if r['language']==a and r['evidence_language']==b],-100) for a,b in [('en','en'),('fr','en'),('en','fr'),('fr','fr')]},cleanup=session.cleanup,no_fresh_acceptance=True)
    for n,h in freeze['files'].items():assert f.sha(ROOT/n)==h
    assert report['cleanup']['server']['port_closed'] and report['cleanup']['server']['process_exited']
    f.save(output/'report.json',report);print(json.dumps(report,indent=2),flush=True);return report

if __name__=='__main__':run()
