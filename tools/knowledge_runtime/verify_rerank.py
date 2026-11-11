"""Finite isolated reranker/runtime gate: python -m tools.knowledge_runtime.verify_rerank.

Uses only already provisioned local models/server and the executing interpreter.
Writes immutable UUID evidence; never installs, downloads, stages or activates.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import uuid

REPO = Path(__file__).resolve().parents[2]
BASE = REPO/'artifacts/knowledge-rerank'
SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    run = BASE/'executions'/uuid.uuid4().hex
    run.mkdir(parents=True)
    def save(name,value):
        (run/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    protected = json.loads((BASE/'protected-before.json').read_bytes())
    assert all(sha(REPO/name)==value for name,value in protected.items()), 'protected input changed before run'
    sources = [p for p in (REPO/'tools/knowledge_runtime').glob('*.py')]
    sources += list((REPO/'tests').glob('test_knowledge_runtime*.py'))
    sources += [REPO/'docs/KNOWLEDGE-RUNTIME.md', REPO/'tools/retrieval_ablation.py']
    before = {p.relative_to(REPO).as_posix():sha(p) for p in sources}
    save('freeze.json',{'protected':protected,'source_sha256':before,'scope':'personal knowledge; no relevance qualification'})
    commands, evidence = [], []
    for name,pattern in [('runtime','test_knowledge_runtime*.py'),('incumbent','agent_knowledge_runtime_test.py'),
                         ('budget-contract','retrieval_budget_benchmark_test.py')]:
        runtime_base = REPO/'artifacts/knowledge-runtime'
        old_runtime_runs = set(runtime_base.iterdir()) if runtime_base.exists() else set()
        argv = [sys.executable,'-W','error::ResourceWarning','-m','unittest','discover','-s','tests','-p',pattern,'-v']
        env = {k:v for k,v in os.environ.items() if k not in ('BUDGET_REAL_RUN','AKR_EVIDENCE')}
        incumbent = Path(tempfile.mkdtemp(prefix='rerank-incumbent-',dir=SCRATCH)) if name=='incumbent' else None
        if incumbent:
            env['AKR_EVIDENCE'] = str(incumbent)
        result = subprocess.run(argv,cwd=REPO,env=env,capture_output=True,text=True,timeout=240)
        if name=='runtime':
            for folder in set(runtime_base.iterdir())-old_runtime_runs:
                evidence.extend(p.parent for p in folder.rglob('cleanup.json'))
        if incumbent:
            archive = run/'incumbent-evidence'
            shutil.copytree(incumbent,archive,ignore=shutil.ignore_patterns('storage','snapshots','temp'))
            shutil.rmtree(incumbent)
            cleanup = json.loads((archive/'cleanup.json').read_bytes())
            cleanup['scratch_removed'] = not incumbent.exists()
            (archive/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
            evidence.append(archive)
        (run/(name+'-stdout.txt')).write_text(result.stdout,encoding='utf-8')
        (run/(name+'-stderr.txt')).write_text(result.stderr,encoding='utf-8')
        commands.append({'argv':argv,'exit':result.returncode,'stdout':name+'-stdout.txt','stderr':name+'-stderr.txt'})
        save('commands.json',commands)
        assert result.returncode==0,result.stderr
        for line in result.stdout.splitlines():
            if line.startswith(('RERANK_EVIDENCE=','RERANK_REPLAY_EVIDENCE=','HYBRID_EVIDENCE=')):
                evidence.append(Path(line.split('=',1)[1]))
    cleanups = {}
    for folder in evidence:
        cleanup = json.loads((folder/'cleanup.json').read_bytes())
        assert cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed']
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(('127.0.0.1',cleanup['port']))!=0,'owned port still open'
        cleanups[folder.relative_to(REPO).as_posix()] = cleanup
    measured = next(p for p in evidence if (p/'measurements.json').exists() and 'knowledge-rerank' in p.as_posix())
    data = json.loads((measured/'measurements.json').read_bytes())
    summary = {}
    for budget in ('budget5','budget10','budget20'):
        rows = [r['reranking'] for r in data['requests'] if r['reranking']['budget']==budget]
        assert rows and all(r['candidate_count']==int(budget[6:]) for r in rows)
        summary[budget] = {'n':len(rows),'candidate_counts':sorted({r['candidate_count'] for r in rows}),
                           'median_stage_ms':{key:statistics.median(r['stages'][key] for r in rows) for key in rows[0]['stages']}}
    assert all(sha(REPO/name)==value for name,value in protected.items()),'protected input changed during run'
    assert all(sha(REPO/name)==value for name,value in before.items()),'source changed during run'
    diff = subprocess.run(['git','diff','--check'],cwd=REPO,capture_output=True,text=True)
    assert diff.returncode==0,diff.stdout+diff.stderr
    receipt = {'passed':True,'verification_path':str((run/'verification.json').relative_to(REPO)),
               'commands':commands,'protected_inputs_unchanged':protected,'source_sha256':before,
               'cleanup':cleanups,'measurements':summary,'cold':data['cold'],
               'limits':'Initial five alternating fresh requests, tiny synthetic lifecycle, no relevance/precision/throughput claim. Budget benchmark integration intentionally not rerun; its opt-in test is skipped.'}
    save('verification.json',receipt)
    files = [p for folder in [run,*evidence] for p in folder.rglob('*') if p.is_file() and p.name!='manifest-sha256.json']
    save('manifest-sha256.json',{p.relative_to(REPO).as_posix():sha(p) for p in files})
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    main()