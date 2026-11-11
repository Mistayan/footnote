"""Independent stdlib rank/source/metric/provenance audit; no harness imports."""
from pathlib import Path
import json,hashlib,statistics
ROOT=Path(__file__).resolve().parents[2]
SNAPSHOT=ROOT/'artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92'

def audit(run):
    run=Path(run); load=lambda p:json.loads(p.read_bytes())
    for n,h in load(run/'hashes.json').items(): assert hashlib.sha256((run/n).read_bytes()).hexdigest()==h,n
    rows=load(run/'raw-results.json'); corpus=load(SNAPSHOT/'corpus.json'); docs={d['id']:d for d in corpus}; labels={q['id']:q for q in load(SNAPSHOT/'judgments.json')}
    seen=set(); groups={}; count=0
    for r in rows:
        key=(r['id'],r['variant']); assert key not in seen; seen.add(key)
        q=labels[r['id']]
        for k in ('query','split','relevant','incompatible'): assert r[k]==q[k],(key,k)
        assert len(r['candidates'])<=20 and len(set(r['candidates']))==len(r['candidates'])
        assert set(r['logits'])==set(r['candidates'])
        assert r['ranked']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
        if r['variant'].endswith('_threshold0'):
            expected_top=r['ranked'][:5] if r['ranked'] and r['logits'][r['ranked'][0]]>=0 else []
            assert r['top5']==expected_top
        else:
            assert r['top5']==r['ranked'][:5]
        expected=list(dict.fromkeys(r['exact'][:2]+r['dense'][0][:6]+r['dense'][1][:6]+r['lexical'][:6]+r['dense'][0]+r['dense'][1]+r['lexical']+r['exact']))[:20]
        assert r['pool20']==expected
        valid=[n for n in expected if r['eligibility'][n]['allowed']] if isinstance(next(iter(r['eligibility'].values())),dict) and 'allowed' in next(iter(r['eligibility'].values())) else None
        if valid is not None: assert r['candidates']==valid
        for branch,response in r['server_responses'].items():
            raw=response['result']['points']; assert all(raw[i]['score']>=raw[i+1]['score'] for i in range(len(raw)-1))
            rawparents=list(dict.fromkeys(p['payload']['document_id'] for p in raw))
            assert rawparents==r['dense'][0 if branch=='minilm' else 1]
        relevant=set(q['relevant']); incompatible=set(q['incompatible']); top=r['top5']
        expected_metrics={**{'p'+str(k):sum(n in relevant for n in top[:k])/k for k in (1,3,5)},'mrr':next((1/(i+1) for i,n in enumerate(top) if n in relevant),0),'recall5':len(set(top)&relevant)/len(relevant) if relevant else None,'candidate_recall':len(set(r['candidates'])&relevant)/len(relevant) if relevant else None,'incompatible_top1':int(bool(top) and top[0] in incompatible),'incompatible_top5':len(set(top)&incompatible),'accepted':int(bool(top)),'noanswer_false_accept':int(not relevant and bool(top))}
        assert r['metrics']==expected_metrics
        for e,n in zip(r['evidence'],top):
            assert e['id']==n
            d=docs[n]
            for k,v in d.items(): assert e[k]==v
            source=(SNAPSHOT/'sources'/(d['source']+'.txt')).read_text(encoding='utf8')
            assert source[d['start']:d['end']]==d['text']
            assert hashlib.sha256(e['text'].encode()).hexdigest()==e['sha256']; count+=1
        old=groups.setdefault(r['id'],r['candidates']); assert old==r['candidates']
    report=load(run/'report.json')
    for s in report['summaries']:
        selected=[r for r in rows if r['variant']==s['variant'] and r['split']==s['split'] and (s['language']=='all' or r['language']==s['language'])]; yes=[r for r in selected if r['relevant']]; no=[r for r in selected if not r['relevant']]
        assert s['answerable']==len(yes) and s['correct_top1']==sum(r['metrics']['p1'] for r in yes)
        assert s['noanswer_false_accept']==sum(bool(r['top5']) for r in no)
        assert s['answerable_accepted']==sum(bool(r['top5']) for r in yes)
        for k in ('p1','p3','p5','mrr','recall5','candidate_recall'): assert s[k]==statistics.mean(r['metrics'][k] for r in yes)
    return dict(rows=len(rows),queries=len(groups),evidence_records=count,source_offsets_verified=True,all_assertions_passed=True)
