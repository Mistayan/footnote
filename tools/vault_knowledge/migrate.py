"""Finite offline vault migration/replay with owned loopback service and receipts.
No source writes, downloads, answer generation or precision certification.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import uuid

from tools.vault_migration_inventory import inventory
from tools.vault_knowledge.core import Vault

REPO = Path(__file__).resolve().parents[2]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.new')
    temp.write_text(json.dumps(value, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
    os.replace(temp, path)

def run(root, output, tasks, resume=False):
    # Existing server harness owns exactly its subprocess and strips QDRANT_*.
    sys.path.insert(0, str(REPO/'tools'))
    from tools.server_benchmark import Server
    root, output, tasks = Path(root).absolute(), Path(output).absolute(), Path(tasks).absolute()
    if output.is_relative_to(root): raise ValueError('output outside source required')
    if not resume: output.mkdir(parents=True, exist_ok=False)
    elif not output.is_dir(): raise ValueError('resume output missing')
    started = time.perf_counter()
    receipts = output/'commands.jsonl'
    server = Server(output)
    vault = None
    report = {'status':'running','root':str(root),'output':str(output),'precision_certified':False}
    save(output/'status.json', report)
    def command(op, extra=()):
        argv = [sys.executable,'-m','tools.vault_knowledge',op]
        for key,value in config.items(): argv.extend(['--'+key.replace('_','-'),str(value)])
        argv += list(extra)
        t=time.perf_counter()
        with (output/(op+'-stderr.log')).open('a',encoding='utf-8') as err:
            process=subprocess.run(argv,cwd=REPO,stdout=subprocess.PIPE,stderr=err,text=True,timeout=3600)
        receipt={'argv':argv,'returncode':process.returncode,'stdout':process.stdout,'seconds':time.perf_counter()-t}
        with receipts.open('a',encoding='utf-8') as f:f.write(json.dumps(receipt)+'\n')
        if process.returncode:raise RuntimeError(op+' failed; see '+str(output/(op+'-stderr.log')))
        return json.loads(process.stdout)['result']
    try:
        # Inventory is re-frozen for every invocation, including resumed runs.
        snapshot=output/('inventory-'+uuid.uuid4().hex)
        inv=inventory(root,snapshot,64*1024*1024)
        if not inv['import_ready']:raise ValueError('inventory changed or unreadable; rerun --resume after source writers finish')
        manifest=snapshot/'manifest.jsonl'
        save(output/'inventory-current.json',{'directory':str(snapshot),'sha256':sha(manifest),'summary':inv})
        if resume and (output/'config.json').exists():
            config=json.loads((output/'config.json').read_bytes())
            port=int(config['qdrant_url'].rsplit(':',1)[1])
            server.reservation.close()
            server.reservation=socket.socket();server.reservation.bind(('127.0.0.1',port))
            server.port=port;server.config['service']['http_port']=port
            if Path(config['root'])!=root:raise ValueError('resume root mismatch')
        else:
            config=dict(state=str(output/'authority.sqlite'),root=str(root),model=str(REPO/'artifacts/models/minilm'),qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex)
            save(output/'config.json',config)
        inputs=[REPO/'tools/vault_migration_inventory.py',*sorted((REPO/'tools/vault_knowledge').glob('*.py')),REPO/'tools/agent_knowledge_runtime.py',REPO/'tools/acquisition_repair/core.py',REPO/'tools/server_benchmark.py',REPO/'tools/knowledge_runtime/lexical.py',REPO/'tools/knowledge_runtime/metadata.py',REPO/'artifacts/models/minilm/manifest.json',REPO/'artifacts/models/minilm/model.onnx',REPO/'artifacts/models/minilm/tokenizer.json',REPO/'artifacts/server-provision/qdrant-1.19.2/qdrant.exe',tasks]
        hashes={str(p):sha(p) for p in inputs}
        save(output/'input-hashes.json',hashes)
        server.start()
        print(json.dumps({'event':'ingest_started','eligible':inv['status_counts'].get('eligible',0),'output':str(output)}),flush=True)
        report['ingest']=command('ingest',['--manifest',str(manifest),'--complete-manifest'])
        report['idempotency']=command('ingest',['--manifest',str(manifest),'--complete-manifest'])
        if report['idempotency']['ingested'] or report['idempotency']['deleted']:raise ValueError('idempotency failure')
        # Resident actual model, real SQLite FTS5 + remote dense + RRF, no cloud path.
        vault=Vault(**config)
        report['stats']=vault.stats(verify_sources=True)
        if report['stats']['stale_sources'] or report['stats']['pending']:raise ValueError('stale/pending after ingest')
        if report['stats']['sources']!=inv['status_counts'].get('eligible',0):raise ValueError('eligible coverage mismatch')
        count=vault.remote.request('POST','/points/count',{'exact':True})['count']
        if count!=report['stats']['chunks']+1:raise ValueError('remote exact point count mismatch')
        # Validate every remote signature against SQLite, not only a search sample.
        offset=None;verified=0
        while True:
            body={'limit':128,'with_payload':True,'with_vector':False}
            if offset is not None:body['offset']=offset
            page=vault.remote.request('POST','/points/scroll',body)
            for p in page['points']:
                if p['id']==vault.owner:
                    if p['payload']!=vault.owner_payload():raise ValueError('owner signature mismatch')
                    continue
                row=vault.db.execute('select * from chunks where id=? and active=1',(p['id'],)).fetchone()
                if row is None or p['payload']!=vault.chunk_payload(row):raise ValueError('point signature mismatch')
                verified+=1
            offset=page['next_page_offset']
            if offset is None:break
        report['remote']={'exact_points':count,'verified_chunk_payloads':verified}
        if verified!=report['stats']['chunks']:raise ValueError('remote coverage mismatch')
        selected=json.loads(tasks.read_bytes())['tasks']
        task_counts=Counter(t['origin'] for t in selected)
        replay=[]
        for task in selected:
            for mode in ('bm25','dense','hybrid'):
                t=time.perf_counter();hits=vault.search(task['benchmark_question'],mode=mode,limit=5)
                row={'task_id':task['id'],'origin':task['origin'],'ready_for_scoring':task.get('ready_for_scoring',False),'mode':mode,'query':task['benchmark_question'],'milliseconds':(time.perf_counter()-t)*1000,'hits':hits,'relevance_judgment':None}
                # Byte-pinned fetch verification is provenance, never relevance.
                for hit in hits:
                    full=vault.get(hit['id'])
                    if full is None:raise ValueError('stale replay get')
                    data=(root/full['path']).read_bytes()
                    if hashlib.sha256(data).hexdigest()!=full['sha'] or data.decode('utf-8-sig')[full['start']:full['stop']]!=full['text']:raise ValueError('replay citation mismatch')
                replay.append(row)
                with (output/'replay.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=True)+'\n')
        latencies=sorted(r['milliseconds'] for r in replay)
        report['replay']={'tasks':len(selected),'origin_counts':dict(task_counts),'scoring_ready_tasks':sum(t.get('ready_for_scoring',False) for t in selected),'mode_rows':len(replay),'nonempty_rows':sum(bool(r['hits']) for r in replay),'p50_ms':latencies[len(latencies)//2] if latencies else None,'max_ms':max(latencies) if latencies else None,'precision':None,'limitations':'Only retrieval/provenance smoke. Historical source adjudication pending; reconstructed tasks are not genuine history; current corpus is not a historical snapshot. No generated answers or scored precision.'}
        # Fresh JSONL CLI instance validates actual agent transport and restart.
        vault.close();vault=None
        argv=[sys.executable,'-m','tools.vault_knowledge','serve']
        for key,value in config.items():argv.extend(['--'+key.replace('_','-'),str(value)])
        requests=[{'op':'stats','verify_sources':True},{'op':'search','query':selected[0]['benchmark_question'] if selected else 'knowledge','mode':'hybrid','limit':5}]
        cli=subprocess.run(argv,input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,cwd=REPO,timeout=120)
        save(output/'transport.json',dict(argv=argv,requests=requests,stdout=cli.stdout,stderr=cli.stderr,returncode=cli.returncode))
        responses=[json.loads(line) for line in cli.stdout.splitlines()]
        if cli.returncode or len(responses)!=len(requests) or not all(r['ok'] for r in responses):raise ValueError('CLI restart transport failed')
        after=inventory(root,output/('inventory-after-'+uuid.uuid4().hex),64*1024*1024)
        before_rows={r['path']:r for r in map(json.loads,manifest.read_text().splitlines())}
        after_snapshot=sorted(output.glob('inventory-after-*'))[-1]
        after_rows={r['path']:r for r in map(json.loads,(after_snapshot/'manifest.jsonl').read_text().splitlines())}
        changed=[name for name in before_rows.keys()|after_rows.keys() if before_rows.get(name)!=after_rows.get(name)]
        report['source_verification']={'post_inventory_ready':after['import_ready'],'changed_observed_entries':changed,'eligible_sha256_preserved':not changed,'scope':'reachable observed metadata and eligible bytes; excluded descendants and unsupported bytes not certified'}
        if changed or not after['import_ready']:raise ValueError('source changed during full run; rerun --resume')
        with closing(sqlite3.connect(Path(config['state']).as_uri()+'?mode=ro',uri=True)) as db:
            report['sqlite_integrity']=db.execute('pragma integrity_check').fetchone()[0]
            report['original_revision_bytes']=db.execute('select sum(length(original)) from revisions').fetchone()[0]
            for row in db.execute("select r.sha,r.original from revisions r where r.original is not null"):
                if hashlib.sha256(row[1]).hexdigest()!=row[0]:raise ValueError('retained original hash mismatch')
        if report['sqlite_integrity']!='ok':raise ValueError('SQLite integrity failed')
        if any(sha(p)!=h for p,h in hashes.items()):raise ValueError('implementation/model/task changed during run')
        report['authority_sha256']=sha(config['state'])
        report['inventory']=inv
        report['seconds']=time.perf_counter()-started
        report['status']='completed'
    except BaseException as e:
        report.update(status='failed',error_type=type(e).__name__,error=str(e),seconds=time.perf_counter()-started)
        raise
    finally:
        if vault:vault.close()
        report['cleanup']=server.close()
        save(output/'report.json',report);save(output/'status.json',{'status':report['status'],'seconds':report.get('seconds')})
    print(json.dumps({'status':report['status'],'stats':report['stats'],'cleanup':report['cleanup'],'output':str(output)}),flush=True)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--tasks',required=True);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();run(args.root,args.output,args.tasks,args.resume)

if __name__=='__main__':main()
