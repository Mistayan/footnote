"""Finite full archive migration and native replay; exclusively new UUID output."""
import argparse
from collections import Counter
import json
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch
from .core import Store,save,digest,no_links

REPO=Path(__file__).resolve().parents[2]

def refresh_archive(*,archive,root,model,output):
    """Revalidate the approved historical allowlist; version changes separately.

    No directory expansion: historical quarantines/boundaries remain excluded.
    This is an archive-only snapshot, never a SQLite retrieval backend.
    """
    import re
    import sqlite3
    from contextlib import closing
    from .core import Encoder, Vault
    from tools.acquisition_repair.core import source_slices
    from tokenizers import Tokenizer
    archive,root,model,output=map(no_links,(archive,root,model,output))
    if output.is_relative_to(root):raise ValueError('snapshot outside source root required')
    output.mkdir(parents=True,exist_ok=False)
    before=digest(archive.read_bytes())
    reader=object.__new__(Vault);reader.root=root;reader.max_file_bytes=64*1024*1024
    with closing(sqlite3.connect(archive.as_uri()+'?mode=ro&immutable=1',uri=True)) as old:
        old.row_factory=sqlite3.Row
        sources=[dict(r) for r in old.execute("SELECT s.*,r.original FROM sources s JOIN revisions r ON s.path=r.path AND s.revision=r.revision WHERE s.status='active' ORDER BY s.path")]
        revisions=[tuple(r) for r in old.execute('SELECT path,revision,sha,size,status,original FROM revisions')]
        chunks=[tuple(r) for r in old.execute('SELECT id,path,revision,sha,start,stop,text,heading,active FROM chunks')]
    live={s['path']:reader.read(s['path']) for s in sources}
    for s in sources:
        if digest(s['original'])!=s['sha'] or len(s['original'])!=s['size']:raise ValueError('invalid archived original')
    changed=[s['path'] for s in sources if digest(live[s['path']])!=s['sha']]
    tokenizer=Tokenizer.from_str(Encoder(model).tokenizer.to_str());tokenizer.no_truncation();tokenizer.no_padding()
    target=output/'archive.sqlite'
    with closing(sqlite3.connect(target)) as db:
        db.executescript('CREATE TABLE sources(path TEXT PRIMARY KEY,revision INTEGER,sha TEXT,size INTEGER,status TEXT,metadata TEXT); CREATE TABLE revisions(path TEXT,revision INTEGER,sha TEXT,size INTEGER,status TEXT,original BLOB,PRIMARY KEY(path,revision)); CREATE TABLE chunks(id TEXT UNIQUE,path TEXT,revision INTEGER,sha TEXT,start INTEGER,stop INTEGER,text TEXT,heading TEXT,active INTEGER); CREATE INDEX chunks_active ON chunks(active);')
        db.executemany('INSERT INTO revisions VALUES(?,?,?,?,?,?)',revisions)
        db.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?)',chunks)
        for s in sources:
            name=s['path'];data=live[name];revision=s['revision'];sha=s['sha']
            if name in changed:
                revision+=1;sha=digest(data);text=data.decode('utf-8-sig')
                db.execute('UPDATE chunks SET active=0 WHERE path=?',(name,))
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(name,revision,sha,len(data),'active',data))
                slices=source_slices({name:text},[dict(source=name,id=name,start=0,end=len(text),text=text)],tokenizer,96,24)
                headings=[(m.start(),m.group(1)) for m in re.finditer(r'^#{1,6}\s+(.+)$',text,re.M)]
                for c in slices:
                    heading=next((h for pos,h in reversed(headings) if pos<=c['start']),'')
                    cid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{before}\0{name}\0{revision}\0{c["start"]}\0{c["end"]}'))
                    db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,1)',(cid,name,revision,sha,c['start'],c['end'],c['text'],heading))
            db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?)',(name,revision,sha,len(data),'active',s['metadata']))
        for name,data in live.items():
            if reader.read(name)!=data:raise ValueError('source changed during snapshot: '+name)
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('snapshot integrity failed')
        count=db.execute('SELECT count(*) FROM chunks WHERE active=1').fetchone()[0]
    if digest(archive.read_bytes())!=before:raise ValueError('historical archive changed')
    receipt=dict(archive=str(target),archive_sha=digest(target.read_bytes()),historical_archive=str(archive),historical_sha=before,changed=changed,sources=len(sources),chunks=count,original_bytes=sum(map(len,live.values())),scope='historical approved allowlist only; exclusions not expanded',live_hashes={name:digest(data) for name,data in live.items()})
    save(output/'snapshot.json',receipt)
    return receipt


def run(*,archive,root,model,executable,output_parent,tasks):
    sys.path.insert(0,str(REPO/'tools'))
    from tools import server_benchmark as harness
    archive,root,model,executable=map(no_links,(archive,root,model,executable))
    # Qdrant's Windows gridstore index paths exceed MAX_PATH with a full UUID
    # directory. Exclusive short UUID prefix allocation plus full run identity
    # preserves isolation without changing global Windows path configuration.
    run_id=str(uuid.uuid4())
    out=no_links(output_parent)/run_id.replace('-','')[:12];out.mkdir(parents=True,exist_ok=False)
    if out.is_relative_to(root):raise ValueError('output must be outside sources')
    harness.SERVER=executable
    server=harness.Server(out);started=time.perf_counter();report=dict(status='running',run_id=run_id,output=str(out),globally_activated=False,relevance_accepted=False)
    before=digest(archive.read_bytes());save(out/'archive-before.json',dict(path=str(archive),sha=before))
    print(json.dumps(dict(output=str(out),event='starting')),flush=True)
    def command(op,extra=(),stdin=None,deny_sqlite=False):
        launch=['-m','tools.qdrant_knowledge']
        if deny_sqlite:
            # Guard installed in the actual new CLI interpreter, before imports.
            launch=['-c',"import sqlite3,runpy; from unittest.mock import patch; guard=patch('sqlite3.connect',side_effect=AssertionError('SQLite forbidden in fresh retrieval process')); guard.start(); runpy.run_module('tools.qdrant_knowledge',run_name='__main__')"]
        argv=[sys.executable,*launch,op,'--state',str(out/'registry.json'),*map(str,extra)]
        t=time.perf_counter();p=subprocess.run(argv,cwd=REPO,input=stdin,text=True,capture_output=True,timeout=3600)
        receipt=dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,seconds=time.perf_counter()-t)
        with (out/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(receipt)+'\n')
        if p.returncode:raise RuntimeError('CLI failed: '+p.stdout+' '+p.stderr)
        return json.loads(p.stdout)['result'] if op!='serve' else [json.loads(line) for line in p.stdout.splitlines()]
    try:
        files=[*sorted((REPO/'tools/qdrant_knowledge').glob('*.py')),REPO/'tools/agent_knowledge_runtime.py',REPO/'tools/vault_knowledge/core.py',REPO/'tools/vault_migration_inventory.py',REPO/'tools/server_benchmark.py',REPO/'tests/test_qdrant_knowledge.py',model/'manifest.json',model/'model.onnx',model/'tokenizer.json',executable,Path(tasks)]
        hashes={str(p):digest(p.read_bytes()) for p in files};save(out/'inputs.json',hashes)
        collection='akr_'+uuid.uuid4().hex
        server.start()
        report['import']=command('import',['--create','--archive',archive,'--root',root,'--model',model,'--qdrant-url',f'http://127.0.0.1:{server.port}','--collection',collection])
        print(json.dumps(dict(event='imported',counts=report['import'])),flush=True)
        report['idempotency']=command('import',['--archive',archive])
        report['coverage']=command('verify',['--archive',archive])
        s=Store(state=out/'registry.json');report.update(collection=collection,owner=s.owner,registry=str(s.state),snapshot=s.registry['snapshot'])
        # Real read paths under a connect function that always raises: archive is not
        # consulted, moved or copied; this also protects the original evidence directory.
        selected=json.loads(Path(tasks).read_bytes())['tasks'];rows=[]
        with patch('sqlite3.connect',side_effect=AssertionError('SQLite unavailable for retrieval')):
            independent=Store(state=out/'registry.json')
            for task in selected:
                for mode in ('bm25','dense','hybrid'):
                    t=time.perf_counter();hits=independent.search(task['benchmark_question'],mode=mode)
                    row=dict(task_id=task['id'],origin=task['origin'],query=task['benchmark_question'],mode=mode,milliseconds=(time.perf_counter()-t)*1000,hits=hits,relevance=None)
                    for hit in hits:
                        if independent.get(hit['id']) is None or independent.get(hit['source_id']) is None:raise ValueError('read-without-SQLite citation failure')
                    rows.append(row)
                    with (out/'replay.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
            report['read_without_sqlite']=dict(constructed_new_reader=True,connect_always_raises=True,stats=independent.stats(),rows=len(rows),all_gets_checked=True)
        report['replay']=dict(rows=len(rows),tasks=len(selected),origins=dict(Counter(t['origin'] for t in selected)),nonempty=sum(bool(r['hits']) for r in rows),precision=None,latency={mode:dict(rows=len(v),p50_ms=sorted(v)[len(v)//2],max_ms=max(v)) for mode in ('bm25','dense','hybrid') if (v:=[r['milliseconds'] for r in rows if r['mode']==mode])})
        # Explicit named instruction route versus user-knowledge route, not universal exclusion.
        knowledge=s.search('skills verification workflow',scope='knowledge');instruction=s.search('skills verification workflow',scope='instruction')
        if any(h['scope']!='knowledge' for h in knowledge) or any(h['scope']!='instruction' for h in instruction):raise ValueError('scope enforcement failed')
        save(out/'scope-proof.json',dict(query='skills verification workflow',knowledge=knowledge,instruction=instruction,meaning='mechanical path-policy only; not relevance judgments'))
        report['scope_proof']=dict(knowledge=len(knowledge),instruction=len(instruction),prefilter_in_both_branches=True)
        query=selected[0]['benchmark_question']
        hits=command('search',['--query',query]);first=hits[0] if hits else rows[0]['hits'][0]
        report['fresh_cli_get_id']=command('get',['--id',first['id']])['id']
        requests=[dict(op='stats'),dict(op='search',query=query),dict(op='get',id=first['source_id']),dict(op='get',id=first['id'])]
        responses=command('serve',stdin=''.join(json.dumps(r)+'\n' for r in requests),deny_sqlite=True)
        if len(responses)!=4 or not all(r['ok'] for r in responses):raise ValueError('fresh resident transport failure')
        report['fresh_subprocess_sqlite_guard']=True
        save(out/'transport.json',dict(requests=requests,responses=responses))
        # Real server process restart against same storage; exact port must be free.
        report['first_cleanup']=server.close()
        (out/'server-initial.log').write_bytes((out/'server.log').read_bytes())
        server=harness.Server(out);server.reservation.close();server.reservation=socket.socket();server.reservation.bind(('127.0.0.1',s.remote.port));server.port=s.remote.port;server.config['service']['http_port']=server.port;server.start()
        report['restart_stats']=command('stats',deny_sqlite=True)
        command('search',['--query',query],deny_sqlite=True);command('get',['--id',first['source_id']],deny_sqlite=True)
        report['archive_after']=digest(archive.read_bytes())
        if before!=report['archive_after']:raise ValueError('protected archive changed')
        if any(digest(Path(p).read_bytes())!=sha for p,sha in hashes.items()):raise ValueError('execution input changed')
        save(out/'final-handles.json',dict(registry=str(s.state),config=s.config,owner=s.owner,collection=collection,archive=str(archive),archive_sha=before,snapshot=s.registry['snapshot']))
        report['status']='completed'
    except BaseException as e:
        report.update(status='failed',error=type(e).__name__+': '+str(e));raise
    finally:
        report['cleanup']=server.close();report['seconds']=time.perf_counter()-started
        save(out/'report.json',report)
    print(json.dumps(report),flush=True)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','root','model','executable','output-parent','tasks'):p.add_argument('--'+name,required=True)
    run(**vars(p.parse_args()))

if __name__=='__main__':main()
