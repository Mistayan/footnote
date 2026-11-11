"""Offline CLI and bounded resident JSONL transport; never starts a service."""
import argparse
import json
import sys
from tools.vault_knowledge.core import Vault

def main(runtime_class=Vault):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('ingest','search','get','stats','sync','rebuild','backup','serve'):
        p=sub.add_parser(name)
        for option in ('state','root','model','qdrant-url','collection'):p.add_argument('--'+option,required=True)
        p.add_argument('--max-file-bytes',type=int,default=64*1024*1024)
        if name=='ingest':
            p.add_argument('--manifest',required=True);p.add_argument('--complete-manifest',action='store_true')
        if name in ('search','serve'):
            p.add_argument('--reranker');p.add_argument('--query-view',action='store_true')
        if name=='search':
            p.add_argument('--query',required=True);p.add_argument('--limit',type=int,default=5)
            p.add_argument('--mode',choices=('hybrid','bm25','dense'),default='hybrid');p.add_argument('--constraints',default='{}')
        if name in ('search','get','serve'):p.add_argument('--scope',choices=('all','knowledge','instruction'),default='all')
        if name=='get':p.add_argument('--id',required=True);p.add_argument('--constraints',default='{}')
        if name=='stats':p.add_argument('--verify-sources',action='store_true')
        if name=='backup':p.add_argument('--target',required=True)
        if name=='serve':p.add_argument('--write',action='store_true')
    args=parser.parse_args()
    writer=args.command in ('ingest','sync','rebuild') or getattr(args,'write',False)
    runtime=None
    try:
        runtime=runtime_class(state=args.state,root=args.root,model=args.model,qdrant_url=args.qdrant_url,collection=args.collection,write=writer,max_file_bytes=args.max_file_bytes)
        ranker=None
        if getattr(args,'reranker',None):
            from tools.knowledge_runtime.rerank import ResidentReranker
            from pathlib import Path
            ranker=ResidentReranker(Path(args.reranker))
        def run(request):
            if not isinstance(request,dict):raise ValueError('request must be object')
            op=request.get('op')
            allowed={'search':{'op','query','limit','mode','constraints','query_view','scope'},'get':{'op','id','constraints','scope'},'stats':{'op','verify_sources'},'sync':{'op'},'ingest':{'op','manifest','complete_manifest'}}
            if op not in allowed or set(request)-allowed[op]:raise ValueError('unknown operation/fields')
            scope_kw={'scope':request.get('scope',getattr(args,'scope','all'))} if runtime.archive_only else {}
            if op=='search':return runtime.search(request['query'],request.get('limit',5),request.get('mode','hybrid'),constraints=request.get('constraints'),reranker=ranker,query_view=request.get('query_view',getattr(args,'query_view',False)),**scope_kw)
            if op=='get':return runtime.get(request['id'],constraints=request.get('constraints'),**scope_kw)
            if op=='stats':return runtime.stats(request.get('verify_sources',False))
            if op=='sync':runtime.sync();return runtime.stats()
            if op=='ingest':return runtime.ingest(request['manifest'],request.get('complete_manifest',False),progress=lambda r:print(json.dumps(dict(progress=r)),file=sys.stderr,flush=True))
        if args.command=='serve':
            while True:
                line=sys.stdin.buffer.readline(65537)
                if not line:break
                if len(line)>65536:raise ValueError('JSONL request exceeds 64KiB')
                try:response={'ok':True,'result':run(json.loads(line))}
                except (ValueError,KeyError,OSError,RuntimeError) as e:response={'ok':False,'error':str(e)}
                print(json.dumps(response,ensure_ascii=True),flush=True)
        else:
            if args.command=='ingest':result=run(dict(op='ingest',manifest=args.manifest,complete_manifest=args.complete_manifest))
            elif args.command=='search':result=run(dict(op='search',query=args.query,limit=args.limit,mode=args.mode,constraints=json.loads(args.constraints)))
            elif args.command=='get':result=run(dict(op='get',id=args.id,constraints=json.loads(args.constraints)))
            elif args.command=='stats':result=run(dict(op='stats',verify_sources=args.verify_sources))
            elif args.command=='sync':result=run(dict(op='sync'))
            elif args.command=='rebuild':runtime.rebuild_index();result=runtime.stats()
            else:runtime.backup(args.target);result={'backup':args.target}
            print(json.dumps({'ok':True,'result':result},ensure_ascii=True))
        return 0
    except (ValueError,KeyError,OSError,RuntimeError) as e:
        print(json.dumps({'ok':False,'error':str(e)}),file=sys.stderr);return 1
    finally:
        if runtime:runtime.close()

if __name__=='__main__':raise SystemExit(main())
