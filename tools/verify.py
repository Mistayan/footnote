"""Source-bound local acceptance. Produces real receipts; no fabricated responses."""
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'artifacts/verification'/uuid.uuid4().hex
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest():
    paths=[REPO/'Cargo.toml',REPO/'Cargo.lock',REPO/'requirements-extract.lock']
    for directory,pattern in [('src','*.rs'),('tests','*.rs'),('tests','*.py'),('tools','*.py'),('scripts','*.sh')]:
        paths.extend((REPO/directory).glob(pattern))
    return {p.relative_to(REPO).as_posix():digest(p) for p in sorted(paths)}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    scratch=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.cache'))/'hermes/cache/scratch';scratch.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TMPDIR=str(scratch),TMP=str(scratch),TEMP=str(scratch))
    before=manifest();steps=[]
    for name,args in [
        ('gate',['bash','scripts/check.sh']),
        ('import',[sys.executable,'tools/import_archperf.py']),
        ('demo',[sys.executable,'tools/demo.py']),
        ('benchmark',[sys.executable,'tools/benchmark.py']),
    ]:
        started=time.perf_counter()
        result=subprocess.run(args,cwd=REPO,env=env,capture_output=True)
        (OUT/(name+'.log')).write_bytes(result.stdout+result.stderr)
        steps.append({'step':name,'exit_code':result.returncode,'seconds':time.perf_counter()-started,'log':str(OUT/(name+'.log'))})
        if result.returncode:
            print(result.stdout.decode(errors='replace'));print(result.stderr.decode(errors='replace'));raise SystemExit(result.returncode)
    after=manifest();assert before==after,'execution sources changed during verification'
    benchmark=json.loads((REPO/'artifacts/benchmark/results.json').read_text(encoding='utf-8'))
    imported=json.loads((REPO/'artifacts/import-receipt.json').read_text(encoding='utf-8'))
    demo=json.loads((REPO/'artifacts/demo-receipt.json').read_text(encoding='utf-8'))
    report={'verdict':'PASS','sources_stable':True,'source_sha256':before,'binary':str(REPO/'target/release/borg-knowledge.exe'),'binary_sha256':digest(REPO/'target/release/borg-knowledge.exe'),'platform':platform.platform(),'cpu_count':os.cpu_count(),'steps':steps,'benchmark':benchmark,'import':imported,'demo':demo,'scope':'Local pilot only. No live vault/trading-registry writes. Campaign preservation NOT_CERTIFIED; production health UNKNOWN.'}
    file=OUT/'receipt.json';file.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (OUT.parent/'latest.json').write_text(json.dumps({'receipt':str(file),'sha256':digest(file)},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'verdict':report['verdict'],'sources_stable':True,'receipt':str(file),'binary_sha256':report['binary_sha256'],'steps':steps,'stats':demo['stats'],'p50_process_ms':benchmark['p50_ms'],'p95_process_ms':benchmark['p95_ms'],'index_ms':benchmark['index_ms'],'incremental_ms':benchmark['incremental_ms']},indent=2))
if __name__=='__main__':main()
