"""Independent saved-run audit; no labels or ranked outputs changed."""
import json,hashlib,math
from pathlib import Path
from collections import Counter
from tools.acquisition_repair.evaluator import ROOT,f
from tools.accuracy_validation_v2.validate import SNAPSHOT
from tools.accuracy_validation_v2.protocol import verify_seal


def audit():
    import numpy as np
    from tokenizers import Tokenizer
    verify_seal(SNAPSHOT)
    run=Path(f.load(SNAPSHOT/'recovery-first-inference.json')['run']);rows=f.load(run/'results.json');report=f.load(run/'report.json')
    manifest=f.load(run/'artifact-sha256.json')
    for n,h in manifest.items():assert f.sha(run/n)==h,n
    frozen=f.load(SNAPSHOT/'freeze.json');sources=f.load(SNAPSHOT/'source-receipts.json');corpus=f.load(SNAPSHOT/'corpus.json');docs={d['id']:d for d in corpus};questions={q['id']:q for q in f.load(SNAPSHOT/'test-judgments.json')}
    texts={s:(SNAPSHOT/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    for s,text in texts.items():
        assert hashlib.sha256(text.encode()).hexdigest()==sources[s]['text_sha256']
        assert f.sha(SNAPSHOT/'sources'/(s+'.raw'))==sources[s]['sha256']
    for d in corpus:
        assert texts[d['source']][d['start']:d['end']]==d['text']
        assert hashlib.sha256(d['text'].encode()).hexdigest()==d['sha256']
    for q in questions.values():
        if not q['relevant']:continue
        expected=sorted({d['id'] for s in q['expected_spans'] for d in corpus if d['source']==s['source'] and s['quote'] in d['text']})
        assert q['relevant']==expected
        for s in q['expected_spans']:assert texts[s['source']][s['start']:s['end']]==s['quote']
    children=f.load(run/'slice96-records.json');tok=Tokenizer.from_file(str(ROOT/'artifacts/models/minilm/tokenizer.json'));tok.no_truncation();tok.no_padding()
    for c in children:
        assert c['text']==texts[c['source']][c['start']:c['end']]
        assert c['parent_ids']==sorted(d['id'] for d in corpus if d['source']==c['source'] and d['start']<=c['start'] and c['end']<=d['end'])
        assert len(tok.encode(c['text']).ids)==c['token_count']<=96
        assert hashlib.sha256(c['text'].encode()).hexdigest()==c['sha256']
    seen=set()
    for r in rows:
        assert (r['id'],r['variant']) not in seen;seen.add((r['id'],r['variant']))
        q=questions[r['id']]
        assert r['query']==q['query'] and r['relevant']==q['relevant']
        assert r['ranked']==sorted(r['scores'],key=lambda n:(-r['scores'][n],n))
        assert set(r['scores'])==set(r['pool']) and r['top5']==r['ranked'][:5]
        assert r['raw_hit1']==(r['ranked'][0] in q['relevant'])
        assert r['accepted']==(r['variant']=='baseline' or max(r['scores'].values())>=2.5)
        if r['variant']=='selected':
            dense=[]
            for pt in sorted(r['server_response']['result']['points'],key=lambda p:(-p['score'],p['id'])):
                for n in children[pt['id']-1]['parent_ids']:
                    if n not in dense:dense.append(n)
            assert dense[:100]==[n for n,c in sorted(r['contributions'].items(),key=lambda kv:kv[1].get('dense',{'rank':100000})['rank']) if 'dense' in c]
            order=sorted(r['contributions'],key=lambda n:(-sum(v['contribution'] for v in r['contributions'][n].values()),n))
            assert order[:20]==r['pool']
        for e in r['evidence']:
            assert all(e[k]==docs[e['id']][k] for k in docs[e['id']])
            assert e['url']==sources[e['source']]['url'] and e['raw_sha256']==sources[e['source']]['sha256']
    assert len(rows)==104
    selected=[r for r in rows if r['variant']=='selected'];a=[r for r in selected if r['relevant']];n=[r for r in selected if not r['relevant']]
    correct=sum(r['accepted'] and r['ranked'][0] in r['relevant'] for r in a)
    assert correct==report['selected']['accepted_correct'] and correct/len(a)==report['selected']['p1_all_answerable']
    assert sum(r['accepted'] for r in a)==report['selected']['answerable_accepted']
    assert sum(r['accepted'] for r in n)==report['selected']['noanswer_falseaccepts']
    for name,records,vectorfile in [('selected',children,'slice96-vectors.npy'),('baseline',corpus,'baseline-vectors.npy')]:
        matrix=np.load(run/vectorfile);back=f.load(run/(name+'-readback.json'))
        assert len(back['points'])==len(records)==back['info']['indexed_vectors_count']
        assert np.max(np.abs(matrix-np.asarray([p['vector'] for p in back['points']])))<1e-6
        assert all(p['payload']['record_id']==records[i]['id'] for i,p in enumerate(back['points']))
    cleanup=report['cleanup']['server'];assert cleanup['process_exited'] and cleanup['port_closed']
    # Recovery wrapper executed successfully but its final source-file hash assertion
    # compared LF source text against Windows write_text CRLF bytes. Verify BOTH
    # exact persisted bytes and canonical executed text, preserving the failed test.
    amendment=f.load(SNAPSHOT/'infrastructure-retry-freeze.json');script=SNAPSHOT/'retry-executed-validate.py'
    normalized_hash=hashlib.sha256(script.read_text(encoding='utf8').encode()).hexdigest()
    assert normalized_hash==amendment['executed_source_sha256']
    assert f.sha(ROOT/'tools/accuracy_validation_v2/recover.py')==amendment['wrapper_sha256']
    # Preserve the exact initially frozen protocol version: later additive seal
    # helpers changed this module before fresh freeze, not any dev/refusal scoring.
    replay=ROOT/'artifacts/accuracy-validation-v2/replay-9afbb1909b3d4677abe8899b859b8a6d'
    old_source=(ROOT/'tools/accuracy_validation_v2/protocol.py').read_text(encoding='utf8')
    old_source='"""Exact-positive, UNKNOWN-preserving evaluation contracts."""\n\n'+old_source[old_source.index('def expected_windows'):]
    assert hashlib.sha256(old_source.encode()).hexdigest()==f.load(replay/'execution-freeze.json')['files']['tools/accuracy_validation_v2/protocol.py']
    archive=replay/'protocol-at-replay.py'
    if not archive.exists():archive.write_bytes(old_source.encode())
    assert f.sha(archive)==hashlib.sha256(old_source.encode()).hexdigest()
    global_omissions=[]
    for q in questions.values():
        matches=sorted({d['id'] for d in corpus for span in q['expected_spans'] if span['quote'] in d['text']})
        extra=sorted(set(matches)-set(q['relevant']))
        if extra:global_omissions.append(dict(id=q['id'],unlabeled_exact_quote_windows=extra,status='FROZEN LABELS NOT CHANGED; acceptance-design defect'))
    result=dict(utc=f.now(),rows=len(rows),answerable=len(a),noanswer=len(n),sources=len(sources),parents=len(corpus),slice96=len(children),all_hashes_and_offsets_verified=True,all_source_scoped_selected_quote_windows_verified=True,global_quote_label_complete=not global_omissions,global_quote_label_omissions=global_omissions,all_vector_readbacks_verified=True,cleanup_verified=True,original_freeze_unchanged=True,recovery=dict(raw_file_sha256=f.sha(script),canonical_executed_sha256=normalized_hash,final_assertion_issue='CRLF persistence versus LF compiled source; independently verified canonical executable; original failure preserved'),frozen_code_snapshot=str(SNAPSHOT/'code'),p1=correct/len(a),correlated_query_warning=True)
    f.save(run/'independent-audit.json',result)
    print(json.dumps(result,indent=2),flush=True);return result

if __name__=='__main__':audit()
