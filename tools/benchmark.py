"""Repeatable lexical baseline, not a hybrid or production performance claim."""
from pathlib import Path
import hashlib
import json
import math
import statistics
import subprocess
import time
import uuid

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'artifacts/benchmark'
BINARY=REPO/'target/release/borg-knowledge.exe'
RUN=OUT/'runs'/uuid.uuid4().hex
QUERIES=[
    ('SQL_NEEDED_BODY','sql','exact identifier','development'),
    ('substr','sql','exact function','development'),
    ('controller cancellation','sse','two terms','development'),
    ('sqlite 3.53.1','sql','version literal','held-out'),
    ('checkpoint','wal','technical word','held-out'),
    ('avoid paying for unused receipt text','sql','English paraphrase','held-out'),
    ('réduire le coût des reçus inutilisés','sql','French cross-language','held-out'),
    ('nonexistentvolcanicunicorn',None,'unanswerable','held-out'),
]
def call(*args):
    start=time.perf_counter_ns()
    result=subprocess.run([str(BINARY),'--db',str(RUN/'knowledge.db'),*args],capture_output=True,check=True)
    return json.loads(result.stdout), (time.perf_counter_ns()-start)/1e6, len(result.stdout)
def main():
    RUN.mkdir(parents=True,exist_ok=True)
    notes=OUT/'notes';notes.mkdir(parents=True,exist_ok=True)
    corpus={
        'sql':'# SQLite 3.53.1\n## SQL_NEEDED_BODY\nCASE skips unused SQL receipt body substr evaluation for heartbeat rows. Synthetic parity evidence only.\n',
        'sse':'# Node v24.20.0\n## Controller cancellation\nCapture the owning controller and remove the stream subscriber on cancellation.\n',
        'wal':'# SQLite WAL\n## Checkpoint\nCheckpoint latency amortized through transaction batching.\n',
    }
    for name,text in corpus.items():(notes/(name+'.md')).write_text(text,encoding='utf-8')
    for n in range(997):(notes/f'distractor-{n:04}.md').write_text(f'# Synthetic unrelated {n}\nSynthetic document about gardening and unique fixture {n}.\n',encoding='utf-8')
    first,index_ms,_=call('index','--root',str(notes),'--allow',str(notes))
    second,incremental_ms,_=call('index','--root',str(notes),'--allow',str(notes))
    results=[];latencies=[];sizes=[]
    for query,expected,category,split in QUERIES:
        samples=[]
        for _ in range(15):
            value,ms,size=call('search',query,'--limit','5');samples.append(ms);latencies.append(ms);sizes.append(size)
        paths=[Path(v['path']).stem for v in value['results']]
        results.append({'query':query,'expected':expected,'category':category,'split':split,'top_paths':paths,'recall_at_5':None if expected is None else int(expected in paths),'unanswerable_correct':not paths if expected is None else None,'p50_process_ms':statistics.median(samples),'p95_process_ms':sorted(samples)[math.ceil(.95*len(samples))-1]})
    report={'mode':'lexical_fts5_only','semantic':'not_implemented','hybrid':'not_evaluated_no_embedder','corpus':'1000 owned synthetic Markdown documents','queries':len(QUERIES),'measured_process_calls':len(latencies),'index':first,'index_ms':index_ms,'incremental':second,'incremental_ms':incremental_ms,'process_startup_included':True,'p50_ms':statistics.median(latencies),'p95_ms':sorted(latencies)[math.ceil(.95*len(latencies))-1],'max_response_bytes':max(sizes),'answerable_recall_at_5':sum(r['recall_at_5'] for r in results if r['recall_at_5'] is not None)/sum(r['recall_at_5'] is not None for r in results),'results':results,'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'limitations':['Small synthetic corpus; no claim of real-vault recall or speedup.','No semantic vectors, rank fusion, or reranker executed.','Exact literals and incompatible-version filters are separate from semantic relevance.']}
    (OUT/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
