"""Finite local Qdrant import/search/get; no downloads, cloud or global activation."""
import argparse
import json
import sys
import time
from .core import Store

def operation(s,r):
    op=r['op']
    if op=='stats':return s.stats()
    if op=='get':return s.get(r['id'],start=r.get('start',0),max_chars=r.get('max_chars'))
    if op=='search':return s.search(r['query'],limit=r.get('limit',5),mode=r.get('mode','hybrid'),scope=r.get('scope','auto'),constraints=r.get('constraints'),dedup=r.get('dedup',True))
    raise ValueError('unknown read operation')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='op',required=True)
    for op in ('import','search','get','stats','serve','verify'):
        p=sub.add_parser(op);p.add_argument('--state',required=True)
        if op=='import':
            p.add_argument('--archive',required=True);p.add_argument('--create',action='store_true');p.add_argument('--root');p.add_argument('--model');p.add_argument('--qdrant-url');p.add_argument('--collection')
        if op=='verify':p.add_argument('--archive',required=True)
        if op=='search':
            p.add_argument('--query',required=True);p.add_argument('--mode',choices=('bm25','dense','hybrid'),default='hybrid');p.add_argument('--scope',choices=('auto','knowledge','instruction','all'),default='auto');p.add_argument('--limit',type=int,default=5);p.add_argument('--constraints',type=json.loads);p.add_argument('--no-dedup',dest='dedup',action='store_false')
        if op=='get':
            p.add_argument('--id',required=True);p.add_argument('--start',type=int,default=0);p.add_argument('--max-chars',type=int)
    a=vars(parser.parse_args());op=a.pop('op');started=time.perf_counter()
    try:
        state=a.pop('state')
        if op=='import':
            archive=a.pop('archive');s=Store(state=state,**a);result=s.import_archive(archive)
        else:
            s=Store(state=state)
            if op=='serve':
                for line in sys.stdin:
                    if len(line)>65536:raise ValueError('JSONL request exceeds bound')
                    t=time.perf_counter()
                    try:print(json.dumps(dict(ok=True,result=operation(s,json.loads(line)),milliseconds=(time.perf_counter()-t)*1000),ensure_ascii=True),flush=True)
                    except Exception as e:print(json.dumps(dict(ok=False,error=str(e))),flush=True)
                return 0
            result=s.verify_archive(a['archive']) if op=='verify' else operation(s,dict(op=op,**a))
        print(json.dumps(dict(ok=True,result=result,milliseconds=(time.perf_counter()-started)*1000),ensure_ascii=True));return 0
    except Exception as e:
        print(json.dumps(dict(ok=False,error=type(e).__name__+': '+str(e))));return 1

if __name__=='__main__':raise SystemExit(main())
