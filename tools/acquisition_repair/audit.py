"""Independent deterministic audit and failure distinctions for saved run."""
import sys,json,hashlib,collections,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
import fresh_retrieval_evaluation as f
from tools.acquisition_repair.core import acquire
SNAPSHOT=ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'


def audit(run):
    import numpy as np
    from tokenizers import Tokenizer
    from technical_quality import lexical_index
    from retrieval_ablation import lexical_or
    run=Path(run);manifest=f.load(run/'artifact-sha256.json')
    for n,h in manifest.items():assert f.sha(run/n)==h,n
    protocol=f.load(run/'execution-freeze.json')
    for n,h in protocol['inputs'].items():assert f.sha(ROOT/n)==h,n
    assert protocol['before_inference'] and not protocol['fresh_acceptance']
    f.verify_snapshot(SNAPSHOT);assert f.sha(SNAPSHOT/'freeze.json')==protocol['snapshot_sha']
    qs={q['id']:q for split in ('development','test') for q in f.load(SNAPSHOT/(split+'-judgments.json'))}
    texts={s:(SNAPSHOT/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in f.load(SNAPSHOT/'source-receipts.json')}
    records={kind:f.load(run/(kind+'-records.json')) for kind in ('parent','slice96','slice112')}
    docs={d['id']:d for d in records['parent']}
    tok=Tokenizer.from_file(str(ROOT/'artifacts/models/minilm/tokenizer.json'));tok.no_truncation();tok.no_padding()
    count=0
    for kind,items in records.items():
        for d in items:
            count+=1;assert d['text']==texts[d['source']][d['start']:d['end']]
            assert hashlib.sha256(d['text'].encode()).hexdigest()==d['sha256']
            if kind!='parent':
                assert len(tok.encode(d['text']).ids)==d['token_count']<=int(kind[5:])
                expected=sorted(p['id'] for p in docs.values() if p['source']==d['source'] and p['start']<=d['start'] and d['end']<=p['end'])
                assert expected==d['parent_ids'] and expected
        vectors=np.load(run/(kind+'-vectors.npy'));back=f.load(run/(kind+'-readback.json'))
        assert len(vectors)==len(back)==len(items)
        assert all(p['id']==i+1 and p['payload']['record_id']==items[i]['id'] for i,p in enumerate(back))
        assert np.max(np.abs(vectors-np.array([p['vector'] for p in back])))<1e-6
    db=lexical_index(records['parent']);rows=f.load(run/'acquisition.json');rankrows=f.load(run/'rerank.json')
    for row in rows:
        q=qs[row['id']]
        assert all(row[k]==v for k,v in q.items() if k!='split')
        lexical=lexical_or(db,q['query']);kind=row['kind']
        response=f.load(run/(q['id']+'-'+kind+'-response.json'))
        points=response['result']['points']
        assert all(records[kind][p['id']-1]['id']==p['payload']['record_id'] for p in points)
        if '_pivot_' in row['variant']:
            original=lexical[:10];pivot=lexical_or(db,row['translation']['pivot'])[:10]
            dense=acquire(points,records[kind],[],100)['dense'];contrib={}
            for branch,names,weight in [('dense',dense,1),('original',original,.5),('pivot',pivot,.5)]:
                for rank,n in enumerate(names,1):contrib.setdefault(n,{})[branch]=dict(rank=rank,contribution=weight/(60+rank))
            union=sorted(contrib,key=lambda n:(-sum(x['contribution'] for x in contrib[n].values()),n))
            assert row['pool']==union[:row['budget']] and row['contributions']==contrib
        else:
            acq=acquire(points[:60] if row['variant']=='legacy20' else points,records[kind],lexical,row['budget'],60 if row['variant']=='legacy20' else 100)
            for k,v in acq.items():assert row[k]==v,(q['id'],row['variant'],k)
        assert row['parent_pool_hit']==bool(set(row['pool'])&set(q['relevant']))
        if row['wholequote_child_hit'] is not None:
            children=[records[kind][p['id']-1] for p in points]
            hit=any(c['source']==s['source'] and c['start']<=s['start'] and s['end']<=c['end'] and set(c['parent_ids'])&set(row['pool']) for c in children for s in q['expected_spans'])
            assert hit==row['wholequote_child_hit']
    db.close()
    for row in rankrows:
        q=qs[row['id']];assert row['relevant']==q['relevant'] and row['query']==q['query']
        assert row['ranking']==sorted(row['logits'],key=lambda n:(-row['logits'][n],n))
        assert row['top5']==row['ranking'][:5] and set(row['pool'])==set(row['ranking'])
        for e in row['candidate_evidence']:
            p=docs[e['id']];assert all(e[k]==v for k,v in p.items())
            assert e['judgment']==('EXPECTED_QUOTE_HIT' if e['id'] in q['relevant'] else 'UNKNOWN')
    report=f.load(run/'report.json');assert len(rows)==report['counts']['acquisition_rows'];assert len(rankrows)==report['counts']['rerank_rows']
    assert report['rerank_summaries']==[dict(split=split,**s) for split in ('development','diagnostic') for s in f.summaries([r for r in rankrows if r['split']==split])]
    # Paired improvements never silently relabel UNKNOWN competitors.
    coverage=f.load(run/'proof-input-coverage.json')
    distinctions=[]
    historic=f.load(ROOT/'artifacts/fresh-challenger-bridge/fcb-20261020-acceptance-01-final/raw-results.json')
    for q in qs.values():
        if not q['relevant']:continue
        split='development' if q['split']=='development' else 'diagnostic'
        legacy=next(r for r in rows if r['id']==q['id'] and r['variant']=='legacy20')
        old=next(r for r in (rankrows if split=='development' else historic) if r['id']==q['id'] and r['variant']==('legacy20' if split=='development' else 'mmarco_or_pool20'))
        oracle=next(r for r in rankrows if r['id']==q['id'] and r['variant']=='oracle_supplied')
        proof=[c for c in coverage if c['id']==q['id']]
        distinction=dict(id=q['id'],split=split,language=q['language'],evidence_language=q['evidence_language'],query=q['query'],expected=q['relevant'],legacy_pool_hit=legacy['parent_pool_hit'],legacy_top1_hit=old['top5'][0] in q['relevant'],oracle_top1_hit=oracle['top5'][0] in q['relevant'],oracle_best_relevant_rank=min(oracle['ranking'].index(n)+1 for n in q['relevant']),any_original_dense_wholequote=any(c['dense_wholequote'] for c in proof),any_ranker_wholequote=any(c['ranker_wholequote'] for c in proof),oracle_top1=oracle['top5'][0],oracle_top1_judgment='EXPECTED' if oracle['top5'][0] in q['relevant'] else 'UNKNOWN')
        distinction['baseline_failure']='none' if distinction['legacy_top1_hit'] else 'candidate_missing' if not legacy['parent_pool_hit'] else 'proof_not_visible_to_ranker' if not distinction['any_ranker_wholequote'] else 'ranking_or_incomplete_judgment'
        distinctions.append(distinction)
    failure_counts={split:dict(collections.Counter(r['baseline_failure'] for r in distinctions if r['split']==split)) for split in ('development','diagnostic')}
    allproof={split:dict(answerable=sum(r['split']==split for r in distinctions),original_dense_wholequote=sum(r['any_original_dense_wholequote'] for r in distinctions if r['split']==split),ranker_wholequote=sum(r['any_ranker_wholequote'] for r in distinctions if r['split']==split),oracle_failures_with_visible_quote=sum(not r['oracle_top1_hit'] and r['any_ranker_wholequote'] for r in distinctions if r['split']==split)) for split in ('development','diagnostic')}
    cleanup=report['cleanup'];assert cleanup['process_exited'] and cleanup['port_closed']
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',cleanup['port']))!=0
    return dict(verified=True,run=str(run),acquisition_rows=len(rows),rerank_rows=len(rankrows),validated_source_records=count,manifest_files=len(manifest),failure_counts=failure_counts,proof_visibility=allproof,per_query_distinctions=distinctions,warning='ranking_or_incomplete_judgment != semantically wrong; oracle supplied labels not deployable; only development selected')

if __name__=='__main__':
    run=Path(sys.argv[1]);result=audit(run);f.save(run/'independent-audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='per_query_distinctions'},indent=2))
