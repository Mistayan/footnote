"""Additive hybrid acceptance: never rewrites the original demo or old receipts."""
import hashlib
import json
import os
import platform
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
BINARY=REPO/'target/release/borg-knowledge.exe'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def inputs():
    paths=[REPO/'Cargo.toml',REPO/'Cargo.lock',REPO/'requirements-hybrid.lock',REPO/'requirements-extract.lock']
    for directory,pattern in [('src','*.rs'),('tests','*.rs'),('tests','*.py'),('tools','*.py'),('scripts','*.sh')]:paths.extend((REPO/directory).glob(pattern))
    return {p.relative_to(REPO).as_posix():digest(p) for p in sorted(paths)}
def main():
    out=REPO/'artifacts/hybrid-acceptance'/uuid.uuid4().hex;out.mkdir(parents=True)
    before=inputs();steps=[];env=os.environ.copy()
    local=REPO/'artifacts/toolchain/installed/bin'
    if local.is_dir():
        env['PATH']=str(local)+os.pathsep+env['PATH'];env['RUSTC']=str(local/'rustc.exe')
    def step(name,args):
        started=time.perf_counter();result=subprocess.run(list(map(str,args)),cwd=REPO,env=env,capture_output=True,timeout=1200)
        (out/(name+'.stdout')).write_bytes(result.stdout);(out/(name+'.stderr')).write_bytes(result.stderr)
        steps.append({'step':name,'exit':result.returncode,'seconds':time.perf_counter()-started,'command':list(map(str,args))})
        if result.returncode:
            save(out/'failed.json',{'steps':steps,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')})
            raise RuntimeError(f'{name} failed; see {out}')
        return result.stdout
    step('fmt',['cargo','fmt'])
    # Formatting must happen before establishing the source-bound gate snapshot.
    before=inputs();save(out/'source-before.json',before)
    step('gate',['bash','scripts/check.sh'])
    step('python-lock',['uv','pip','sync','--dry-run','--python',sys.executable,'requirements-hybrid.lock'])
    compiler=step('rustc',['rustc','-Vv']).decode();cargo=step('cargo',['cargo','-V']).decode()
    step('benchmark',[sys.executable,'tools/hybrid_benchmark.py'])
    navigation=json.loads((REPO/'artifacts/hybrid/latest.json').read_bytes())
    report_path=Path(navigation['run'])/'report.json';assert digest(report_path)==navigation['report_sha256']
    report=json.loads(report_path.read_bytes());raw=json.loads(report_path.with_name('raw-results.json').read_bytes())
    assert len(raw)==160
    assert report['labeled_queries']==32 and report['corpus_documents']==1000 and report['cli_calls']==228
    assert sum(s['queries'] for s in report['summaries'])==160
    metas=list(report_path.parent.glob('call-*.meta.json'));assert len(metas)==report['cli_calls']
    assert all(json.loads(p.read_bytes())['exit']==0 for p in metas)
    assert all(r['citations']['checked']==r['citations']['correct'] for r in raw)
    # Copy via SQLite backup from a read-only source connection, then exercise
    # schema3->4 on that copy. Do not initialize/migrate the historical pilot.
    pilot=REPO/'artifacts/demo/knowledge.db';pilot_hash=digest(pilot)
    source=sqlite3.connect(f'file:{pilot.as_posix()}?mode=ro',uri=True)
    copy=out/'pilot-copy.db';target=sqlite3.connect(copy);source.backup(target);target.close();source.close()
    def snapshot(path):
        c=sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)
        result={table:c.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() for table in ['records','record_history','sources','chunks']}
        version=c.execute('PRAGMA user_version').fetchone()[0];c.close();return result,version
    authoritative,old_schema=snapshot(copy)
    step('pilot-rebuild',[BINARY,'--db',copy,'rebuild-embeddings','--model',REPO/'artifacts/models/minilm'])
    migrated,new_schema=snapshot(copy);assert authoritative==migrated and new_schema==4
    readback=json.loads(step('pilot-query',[BINARY,'--db',copy,'search','réduire le coût des reçus inutilisés','--mode','hybrid','--model',REPO/'artifacts/models/minilm','--technology','Python/SQLite','--tested-version','sqlite=3.53.1','--status','proposal','--limit','1']))
    assert len(readback['records'])==1 and readback['records'][0]['id']==2
    for n in [1,2]:
        r=json.loads(step(f'pilot-record-{n}',[BINARY,'--db',copy,'get-record',str(n)]))
        assert r['status']=='proposal' and r['evidence_freshness']=='current'
    restored=out/'restored.db';step('backup',[BINARY,'--db',copy,'backup','--output',restored])
    stat=json.loads(step('restored-stats',[BINARY,'--db',restored,'stats']))
    assert stat['records']==2 and stat['schema']==4 and stat['embeddings']>0
    assert snapshot(restored)==snapshot(copy) and digest(pilot)==pilot_hash
    with socket.socket() as sock:
        sock.settimeout(1);qdrant_tcp=sock.connect_ex(('127.0.0.1',6333))
    assert before==inputs(),'execution sources changed during acceptance'
    receipt={'verdict':'PASS_LOCAL_SYNTHETIC_ONLY','source_hashes':before,'sources_stable':True,'binary_sha256':digest(BINARY),'binary_bytes':BINARY.stat().st_size,'platform':platform.platform(),'logical_cpus':os.cpu_count(),'rustc':compiler,'cargo':cargo,'python':sys.version,'steps':steps,'benchmark_report':str(report_path),'benchmark_report_sha256':digest(report_path),'benchmark_summary':report['summaries'],'original_pilot_sha256_before_after':pilot_hash,'pilot_copy':str(copy),'pilot_migration':{'from_schema':old_schema,'to_schema':new_schema,'records_history_sources_chunks_preserved':True,'original_unmodified':True},'qdrant_loopback_6333_connect_ex':qdrant_tcp,'scope':'Isolated local Qdrant-client only; no existing storage/service modifications, no global activation. No real-vault quality or production preservation certificate.'}
    # Bind raw bytes as well as summaries; Qdrant databases are closed already.
    receipt['raw_evidence_sha256']={p.relative_to(report_path.parent).as_posix():digest(p) for p in report_path.parent.glob('*') if p.is_file() and p.suffix in ['.json','.txt']}
    save(out/'receipt.json',receipt)
    save(out.parent/'latest.json',{'receipt':str(out/'receipt.json'),'sha256':digest(out/'receipt.json')})
    print(json.dumps({'receipt':str(out/'receipt.json'),'benchmark':str(report_path),'verdict':receipt['verdict'],'binary_sha256':receipt['binary_sha256'],'steps':steps},indent=2))
if __name__=='__main__':main()
