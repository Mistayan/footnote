"""Local pivot-language experiment; immutable evidence and original dense queries."""
import re
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
SPAN=re.compile(r'`[^`\n]+`|\b\w+(?:[._]\w+)+\b|\b\d+(?:\.\d+)*\b|\b[A-Z][A-Z0-9_]+\b|!=|==|<=|>=|&&|\|\|')

def protect(text):
 if re.search(r'BKSPAN\d+Z',text):raise ValueError('reserved placeholder in input')
 spans=[]
 def replace(m):
  token='BKSPAN'+str(len(spans)).zfill(6)+'Z'; spans.append((token,m.group())); return token
 return SPAN.sub(replace,text),spans

def restore(text,spans):
 expected=[t for t,_ in spans]
 if re.findall(r'BKSPAN\d+Z',text)!=expected:raise ValueError('missing, reordered, duplicate or foreign immutable span')
 for token,original in spans:text=text.replace(token,original)
 return text

def pivot_query(query,language,translate):
 """Translate only natural fragments; placeholders never enter the checkpoint.

 Fragmenting loses cross-span context, explicitly measured rather than repaired.
 Any reserved-token intrusion or span roundtrip violation falls back to original.
 """
 if language!='fr':return dict(pivot=query,ok=True,fragments=[],reason='identity non-French')
 masked,spans=protect(query); fragments=[]
 try:
  parts=re.split(r'(BKSPAN\d+Z)',masked)
  for i,part in enumerate(parts):
   if i%2 or not any(c.isalpha() for c in part):continue
   leading=part[:len(part)-len(part.lstrip())]; trailing=part[len(part.rstrip()):]
   translated=translate(part.strip())
   if not translated.strip() or re.search(r'BKSPAN\d+Z',translated):raise ValueError('empty or reserved token in generated natural span')
   fragments.append(dict(original=part.strip(),translated=translated))
   parts[i]=leading+translated.strip()+trailing
  result=restore(''.join(parts),spans)
  return dict(pivot=result,ok=True,fragments=fragments,spans=spans,reason='local natural-span translation')
 except (ValueError,RuntimeError) as exc:
  return dict(pivot=query,ok=False,fragments=fragments,spans=spans,reason=repr(exc))

def rank_candidates(dense,original,pivot,variant):
 """Fixed raw acquisition60 dense+20 lexical slots, RRF60, pool20 later.

 Fusion splits lexical slots10/10 and mass1/2+1/2; no refill or hidden
 extra candidate budget. Duplicate lexical entries consume their original slots.
 """
 if variant=='baseline':branches=[('original',original[:20],1)]
 elif variant=='pivot':branches=[('pivot',pivot[:20],1)]
 elif variant=='fusion':branches=[('original',original[:10],.5),('pivot',pivot[:10],.5)]
 else:raise ValueError('undeclared variant')
 admitted=[n for _,names,_ in branches for n in names]; scores={}
 for kind,names,weight in [('dense',dense[:60],1)]+branches:
  for rank,name in enumerate(names,1):
   row=scores.setdefault(name,dict(score=0,branches={}))
   contribution=weight/(60+rank); row['score']+=contribution
   row['branches'][kind]=dict(rank=rank,weight=weight,contribution=contribution)
 return sorted(scores,key=lambda n:(-scores[n]['score'],n)),scores,admitted

RESEARCH=REPO/'artifacts/pivot-language/pivot-20261019-a'
VARIANTS=('baseline','pivot','fusion')

def translation_worker():
 """Dedicated project-local CPU process. No network or remote inference."""
 import sys,json,time,hashlib
 import torch
 from transformers import MarianMTModel,MarianTokenizer
 torch.set_num_threads(2); torch.set_num_interop_threads(1)
 receipt=json.loads((RESEARCH/'model-receipt.json').read_bytes())
 for name,item in receipt['files'].items():
  if hashlib.sha256((RESEARCH/'model'/name).read_bytes()).hexdigest()!=item['sha256']:raise ValueError('translator hash mismatch')
 started=time.perf_counter(); cpu=time.process_time()
 tokenizer=MarianTokenizer.from_pretrained(str(RESEARCH/'model'),local_files_only=True)
 model=MarianMTModel.from_pretrained(str(RESEARCH/'model'),local_files_only=True,use_safetensors=True).eval()
 print(json.dumps(dict(ready=True,load_ms=(time.perf_counter()-started)*1000,load_cpu_s=time.process_time()-cpu)),flush=True)
 for line in sys.stdin:
  item=json.loads(line); started=time.perf_counter(); cpu=time.process_time()
  def translate(text):
   tokens=tokenizer(text,return_tensors='pt',truncation=False)
   if tokens['input_ids'].shape[1]>256:raise ValueError('natural span exceeds fixed256 input tokens')
   with torch.inference_mode(): generated=model.generate(**tokens,num_beams=1,do_sample=False,max_new_tokens=96)
   if generated.shape[1]>=96 and generated[0,-1].item()!=tokenizer.eos_token_id:raise ValueError('translation output bound')
   return tokenizer.decode(generated[0],skip_special_tokens=True)
  result=pivot_query(item['query'],item['language'],translate)
  result.update(wall_ms=(time.perf_counter()-started)*1000,cpu_s=time.process_time()-cpu)
  print(json.dumps(result,ensure_ascii=False),flush=True)

def experiment(run):
 """180 real requests, baseline plus two predeclared representation variants."""
 import datetime,json,shutil,time,os,subprocess,statistics,sys,platform
 import numpy as np
 import psutil
 import technical_quality as tq
 import qdrant_quality as paired
 from retrieval_ablation import CrossEncoder,lexical_or
 from retrieval_budget_benchmark import eligibility,select_candidates,present
 from multilingual_embedding_experiment import verified_encoder
 from accuracy_stepping_stone import metrics
 from server_benchmark import Server,SERVER,save,sha,percentile,ResourceSampler
 run=Path(run).resolve(); base=REPO/'artifacts/pivot-language'
 if not run.is_relative_to(base) or any(p.is_symlink() for p in (run,*run.parents)):raise ValueError('new owned nonsymlink project artifact required')
 run.mkdir(parents=True,exist_ok=False)
 old=REPO/'artifacts/multilingual-embeddings/paired-fc703e012031447fb5066b8224f540b4'
 reused=REPO/'artifacts/accuracy-stepping-stone/lrk-research/fresh'
 datasets={}; inputpaths=[]
 french={'development-01','development-05','development-07','development-10','development-11','holdout-00','holdout-02','holdout-07','holdout-09'}
 for label,source in [('reused',reused),('fresh_go',RESEARCH/'fresh-go'),('old',old)]:
  target=run/label; target.mkdir(); (target/'sources').mkdir()
  load=lambda n:json.loads((source/n).read_bytes())
  frozen=load('freeze.json')
  for name,digest in frozen.get('files',{}).items():assert sha(source/name)==digest,(label,name)
  if label=='old':
   for name,digest in load('evidence-sha256.json').items():assert sha(source/name)==digest,name
  corpus,queries,sources=load('corpus.json'),load('judgments.json'),load('source-receipts.json')
  if label=='old':
   queries=[q|{'language':'fr' if q['id'] in french else 'en_or_mixed'} for q in queries]
  docs={d['id']:d for d in corpus}
  for name in sources:
   for suffix in ('.txt','.raw'):
    p=source/'sources'/(name+suffix)
    if not p.exists():p=source/(name+suffix)
    if p.exists():shutil.copyfile(p,target/'sources'/p.name)
  for d in corpus:
   text=(target/'sources'/(d['source']+'.txt')).read_text(encoding='utf8')
   assert text[d['start']:d['end']]==d['text'] and sha_bytes(d['text'].encode())==d['sha256']
  for name,value in [('corpus',corpus),('judgments',queries),('source-receipts',sources)]:save(target/(name+'.json'),value)
  inputpaths.append(source/'freeze.json'); datasets[label]=(corpus,queries,sources,docs)
 oldmodel=REPO/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'
 inputpaths += [Path(__file__),REPO/'tests/pivot_language_experiment_test.py',SERVER,REPO/'.git/index',REPO/'requirements-hybrid.lock',RESEARCH/'model-receipt.json']
 inputpaths += list((RESEARCH/'model').iterdir())
 inputpaths += [REPO/'tools'/name for name in ('retrieval_ablation.py','retrieval_budget_benchmark.py','technical_quality.py','qdrant_quality.py','multilingual_embedding_experiment.py','server_benchmark.py','accuracy_stepping_stone.py')]
 inputpaths += [oldmodel/'receipt.json']+[oldmodel/n for n in json.loads((oldmodel/'receipt.json').read_bytes())['files']]
 inputpaths += [REPO/'artifacts/models/minilm'/n for n in ('manifest.json','model.onnx','tokenizer.json')]
 hashes={p.relative_to(REPO).as_posix():sha(p) for p in inputpaths if p.is_file()}
 (run/'code').mkdir()
 for p in inputpaths:
  if p.suffix=='.py':shutil.copyfile(p,run/'code'/p.name)
 freeze=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=hashes,artifacts={p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file()},variants=VARIANTS,expected_requests=180,
  acquisition='Original MiniLM128 dense60; total lexical20 slots: baseline original20, pivot translated20, fusion original10+pivot10 weighted .5/.5. Dense weight1 RRF60. Duplicate slots no refill. Final pool20; same original-query incumbent mMARCO20 raw logits, top5 gates.',
  immutable='Generic backticks, dotted/underscored identifiers, numeric versions, uppercase abbreviations, symbolic operators. Placeholders roundtrip exact; only natural fragments enter translator. Original dense AND reranker query unchanged; source bytes/citations unchanged.',
  translation='Pinned OPUS fr-en CPU2 threads, greedy beam1 max_new_tokens96, input256 cap failclosed no truncation; fragment translation loses cross-span context. No operator dictionary or label inputs.',
  thresholds={'first_top1':.8,'stretch_top1':.9,'answerable_coverage_floor':.8},abstention='NONE; retrieval false accepts measured; cannot certify safe answer generation',
  selection='Highest P1 then MRR on reused Git DEVELOPMENT answerable only; exact ties baseline then pivot then fusion. Freeze before fresh Go inference. No reranker/weight/budget tuning.',
  labels='Implementing-agent selected incomplete evidence; Go public source-family disjoint from Git development and frozen before inference, NOT independent human. Rust and old sets reused diagnostics only.',measurement='Each variant own translation if applicable, original query encoding, actual isolated Qdrant HTTP query, lexical acquisition, original rerank20, full original citations/JSON. No translation cache. 1200s measured bound.')
 save(run/'freeze.json',freeze)
 report=dict(status='OPEN_PENDING_PARENT_VERIFICATION',requests=0,blockers=[],summaries=[],environment={'python':sys.version,'platform':platform.platform(),'logical_cpus':psutil.cpu_count(),'physical_cpus':psutil.cpu_count(logical=False),'ram_bytes':psutil.virtual_memory().total,'cpu':platform.processor()})
 server=None; worker=None; log=None; dbs={}; rows=[]
 try:
  started=time.perf_counter()
  env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}; env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(RESEARCH/'hf-offline'),PYTHONIOENCODING='utf-8')
  log=(run/'translator-stderr.log').open('w',encoding='utf8')
  worker=subprocess.Popen([str(RESEARCH/'translation-env/Scripts/python.exe'),'-B',str(Path(__file__)),'--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf8',env=env,cwd=REPO)
  ready=worker.stdout.readline()
  if not ready:raise RuntimeError('translator failed to initialize; inspect translator-stderr.log')
  report['translator_init']=json.loads(ready); report['translator_pid']=worker.pid
  encoder=verified_encoder(REPO/'artifacts/models/minilm',cap=128); ranker=CrossEncoder(oldmodel)
  report['cold_load_validate_ms']=(time.perf_counter()-started)*1000
  server=Server(run); server.start(); report['server']=server.request('GET','/')
  offline=time.perf_counter()
  for label,(corpus,queries,sources,docs) in datasets.items():
   dbs[label]=tq.lexical_index(corpus)
   matrix=encoder.encode([d['text'] for d in corpus],'passage'); np.save(run/(label+'-vectors.npy'),matrix)
   paired.fresh_connection(server)
   server.request('PUT','/collections/'+label,dict(vectors=dict(size=384,distance='Cosine',on_disk=False),shard_number=1,hnsw_config=dict(m=16,ef_construct=100,full_scan_threshold=10),optimizers_config=dict(indexing_threshold=1,default_segment_number=1)))
   server.request('PUT','/collections/'+label+'/points?wait=true',{'points':[dict(id=i+1,vector=v.tolist(),payload=dict(document_id=d['id'])) for i,(d,v) in enumerate(zip(corpus,matrix))]})
   deadline=time.monotonic()+90
   while True:
    info=server.request('GET','/collections/'+label)['result']
    if info['status']=='green' and info['indexed_vectors_count']==len(corpus):break
    if time.monotonic()>deadline:raise TimeoutError('owned collection not indexed '+label)
    time.sleep(.2)
   back=server.request('POST','/collections/'+label+'/points',dict(ids=list(range(1,len(corpus)+1)),with_payload=True,with_vector=True))['result']; back.sort(key=lambda p:p['id'])
   assert len(back)==len(corpus) and np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix))<1e-6
   assert all(p['payload']['document_id']==corpus[i]['id'] for i,p in enumerate(back))
   save(run/(label+'-readback.json'),dict(collection=info,points=back))
  report['offline_encoding_indexing_ms']=(time.perf_counter()-offline)*1000
  report['first_query_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  measured=time.monotonic()
  with ResourceSampler(server) as sampler,(run/'raw-results.jsonl').open('w',encoding='utf8') as output:
   for label,split in [('reused','development'),('fresh_go','holdout'),('reused','holdout'),('old','development'),('old','holdout')]:
    if label=='fresh_go':
     dev=[r for r in rows if r['dataset']=='reused' and r['split']=='development' and r['relevant']]
     choice=max(VARIANTS,key=lambda v:(statistics.mean(r['metrics']['p1'] for r in dev if r['variant']==v),statistics.mean(r['metrics']['mrr'] for r in dev if r['variant']==v),-VARIANTS.index(v)))
     save(run/'selection-freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected=choice,fit_ids=sorted({r['id'] for r in dev}),rationale='Reused Git development only; baseline wins exact ties',before_first_fresh_go_inference=True))
    corpus,queries,sources,docs=datasets[label]
    for q in [q for q in queries if q['split']==split]:
     for variant in VARIANTS:
      if time.monotonic()-measured>1200:raise TimeoutError('1200s bounded experiment')
      start=time.perf_counter(); cpu=time.process_time()
      translated=dict(pivot=q['query'],ok=True,fragments=[],wall_ms=0,cpu_s=0,reason='baseline original')
      if variant!='baseline':
       worker.stdin.write(json.dumps(dict(query=q['query'],language=q['language']),ensure_ascii=False)+'\n'); worker.stdin.flush()
       reply=worker.stdout.readline()
       if not reply:raise RuntimeError('translator subprocess exited')
       translated=json.loads(reply)
      after_translation=time.perf_counter(); paired.fresh_connection(server)
      vector=encoder.encode([q['query']],'query')[0]
      response=server.request('POST','/collections/'+label+'/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=128)))
      dense=paired.rank_parents(response['result']['points'],corpus)
      original=lexical_or(dbs[label],q['query']); pivot=lexical_or(dbs[label],translated['pivot'])
      order,scores,admitted=rank_candidates(dense,original,pivot,variant); pool=order[:20]
      states=eligibility(q['query'],docs,sources); candidates=select_candidates(pool,states,True,20); acquired=time.perf_counter()
      ranked,logits=ranker.rank(q['query'],[docs[n] for n in candidates]); after_rank=time.perf_counter()
      top=present(ranked,eligibility(q['query'],docs,sources),True)
      evidence=[docs[n]|{'url':sources[docs[n]['source']]['url'],'source_raw_sha256':sources[docs[n]['source']]['sha256'],'judgment':'SELECTED' if n in q['relevant'] else 'INCOMPATIBLE' if n in q['incompatible'] else 'UNKNOWN'} for n in top]
      payload=json.dumps(dict(query=q['query'],evidence=evidence),ensure_ascii=False).encode(); end=time.perf_counter()
      row=dict(q,dataset=label,variant=variant,translation=translated,query_vector=vector.tolist(),server_response=response,dense=dense,lexical_original=original,lexical_pivot=pivot,admitted_lexical=admitted,fusion_scores=scores,pool20=pool,candidates=candidates,ranked=ranked,logits=logits,top5=top,eligibility=states,evidence=evidence,metrics=metrics(top,q,candidates),timing_ms=dict(translation=(after_translation-start)*1000,acquisition=(acquired-after_translation)*1000,rerank=(after_rank-acquired)*1000,citations=(end-after_rank)*1000,e2e=(end-start)*1000),cpu_s=time.process_time()-cpu+translated['cpu_s'],wire_bytes=len(payload),utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
      rows.append(row); output.write(json.dumps(row,ensure_ascii=False)+'\n'); output.flush()
      print(label,q['id'],variant,row['metrics']['p1'],round(row['timing_ms']['e2e']),flush=True)
  report['resources']=sampler.report
  report['translator_end_rss_bytes']=psutil.Process(worker.pid).memory_info().rss
  report['measurement_seconds']=time.monotonic()-measured; report['requests']=len(rows); assert len(rows)==180
  for label in datasets:
   for split in ('development','holdout'):
    for variant in VARIANTS:
     for language in ('all','fr','en','en_or_mixed'):
      chosen=[r for r in rows if r['dataset']==label and r['split']==split and r['variant']==variant and (language=='all' or r['language']==language)]
      yes=[r for r in chosen if r['relevant']]; no=[r for r in chosen if not r['relevant']]
      if not chosen:continue
      item=dict(dataset=label,split=split,variant=variant,language=language,n=len(chosen),answerable=len(yes),correct_top1=sum(r['metrics']['p1'] for r in yes),answerable_coverage=sum(bool(r['top5']) for r in yes)/len(yes) if yes else None,abstentions=sum(not r['top5'] for r in chosen),noanswer_count=len(no),noanswer_false_accept=sum(bool(r['top5']) for r in no),incompatible_top1=sum(r['metrics']['incompatible_top1'] for r in chosen),incompatible_top5=sum(r['metrics']['incompatible_top5'] for r in chosen),unknown_top5=sum(e['judgment']=='UNKNOWN' for r in chosen for e in r['evidence']),e2e_p50_ms=statistics.median(r['timing_ms']['e2e'] for r in chosen),e2e_p95_ms=percentile([r['timing_ms']['e2e'] for r in chosen],.95),translation_p50_ms=statistics.median(r['timing_ms']['translation'] for r in chosen),cpu_s=sum(r['cpu_s'] for r in chosen))
      for key in ('p1','p3','p5','mrr','recall5','candidate_recall'):item[key]=statistics.mean(r['metrics'][key] for r in yes) if yes else None
      report['summaries'].append(item)
  report['frozen_inputs_unchanged']=all(sha(REPO/name)==h for name,h in hashes.items()); assert report['frozen_inputs_unchanged']
 except Exception as exc:
  report['blockers'].append(repr(exc)); raise
 finally:
  if server:report['cleanup']=server.close()
  if worker:
   if worker.stdin:worker.stdin.close()
   try:worker.wait(timeout=20)
   except subprocess.TimeoutExpired:worker.terminate(); worker.wait(timeout=20)
   if worker.stdout:worker.stdout.close()
   report['translator_cleanup']=dict(pid=worker.pid,exited=worker.poll() is not None,returncode=worker.returncode)
  if log:log.close()
  for db in dbs.values():db.close()
  save(run/'raw-results.json',rows); save(run/'report.json',report)
  lines=['# Per-query full original evidence','Selected incomplete implementing-agent labels; UNKNOWN is not proven wrong. Public source-family split is not independent human acceptance.']
  for r in rows:
   lines += [f"## {r['dataset']} / {r['id']} / {r['variant']}",r['query'],'Pivot: '+r['translation']['pivot'],json.dumps(r['metrics']),f"Selected {r['relevant']}; incompatible {r['incompatible']}; candidates {r['candidates']}; eligibility {r['eligibility']}",f"Latency ms {r['timing_ms']}; CPU s {r['cpu_s']}"]
   for i,e in enumerate(r['evidence'],1):lines += [f"### {i} {e['id']} {e['judgment']} logit={r['logits'][e['id']]}",f"{e['url']} offsets[{e['start']},{e['end']}) SHA256 {e['sha256']}",'> '+e['text'].replace('\n','\n> ')]
  (run/'PER-QUERY-REVIEW.md').write_text('\n\n'.join(lines),encoding='utf8')
  save(run/'evidence-sha256.json',{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file() and not any(n in p.parts for n in ('storage','snapshots','temp')) and p.name!='evidence-sha256.json'})
 return report

def sha_bytes(data):
 import hashlib
 return hashlib.sha256(data).hexdigest()

def verify_run(run):
 """Replay file integrity, source boundaries, lexical/fusion/logit/gate metrics."""
 import json
 import numpy as np
 import technical_quality as tq
 from retrieval_ablation import lexical_or
 from retrieval_budget_benchmark import eligibility,select_candidates,present
 from accuracy_stepping_stone import metrics
 from server_benchmark import sha
 from qdrant_quality import rank_parents
 run=Path(run); load=lambda name:json.loads((run/name).read_bytes())
 for name,h in load('evidence-sha256.json').items():assert sha(run/name)==h,name
 freeze=load('freeze.json')
 for name,h in freeze['inputs'].items():assert sha(REPO/name)==h,name
 for name,h in freeze['artifacts'].items():assert sha(run/name)==h,name
 rows=load('raw-results.json'); assert len(rows)==180
 assert len({(r['dataset'],r['id'],r['variant']) for r in rows})==180
 datasets={}; pairs={}; selection=load('selection-freeze.json')
 for label in ('reused','old','fresh_go'):
  corpus=load(label+'/corpus.json'); sources=load(label+'/source-receipts.json'); docs={d['id']:d for d in corpus}
  matrix=np.load(run/(label+'-vectors.npy')); points=load(label+'-readback.json')['points']
  assert len(points)==len(corpus) and np.max(np.abs(np.asarray([p['vector'] for p in points])-matrix))<1e-6
  datasets[label]=(corpus,sources,docs,tq.lexical_index(corpus))
 try:
  for r in rows:
   corpus,sources,docs,db=datasets[r['dataset']]
   assert r['dense']==rank_parents(r['server_response']['result']['points'],corpus)
   assert r['lexical_original']==lexical_or(db,r['query']) and r['lexical_pivot']==lexical_or(db,r['translation']['pivot'])
   if r['variant']!='baseline' and r['language']=='fr' and r['translation']['ok']:
    fragments=iter(r['translation']['fragments'])
    translated=pivot_query(r['query'],'fr',lambda text:next(fragments)['translated'])
    assert translated['pivot']==r['translation']['pivot']
   order,scores,admitted=rank_candidates(r['dense'],r['lexical_original'],r['lexical_pivot'],r['variant'])
   assert r['pool20']==order[:20] and r['fusion_scores']==scores and r['admitted_lexical']==admitted
   states=eligibility(r['query'],docs,sources); assert r['eligibility']==states
   assert r['candidates']==select_candidates(order[:20],states,True,20)
   assert r['ranked']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
   assert r['top5']==present(r['ranked'],states,True) and r['metrics']==metrics(r['top5'],r,r['candidates'])
   key=(r['dataset'],r['id'])
   if key in pairs:assert pairs[key]==r['query_vector']
   pairs[key]=r['query_vector']
   if r['dataset']=='fresh_go':assert selection['utc']<=r['utc']
   for e in r['evidence']:
    text=(run/r['dataset']/'sources'/(e['source']+'.txt')).read_text(encoding='utf8')
    assert text[e['start']:e['end']]==e['text']==docs[e['id']]['text'] and sha_bytes(e['text'].encode())==e['sha256']
    assert e['url']==sources[e['source']]['url']
 finally:
  for *_,db in datasets.values():db.close()
 cleanup=load('cleanup.json'); assert cleanup['process_exited'] and cleanup['port_closed']
 assert load('report.json')['translator_cleanup']['exited']
 return True

if __name__=='__main__':
 import argparse,json
 parser=argparse.ArgumentParser(); parser.add_argument('--worker',action='store_true'); parser.add_argument('--run',type=Path); parser.add_argument('--verify',type=Path); args=parser.parse_args()
 if args.worker:translation_worker()
 elif args.verify:print(verify_run(args.verify))
 elif args.run:print(json.dumps(experiment(args.run),indent=2));print('VERIFIED',verify_run(args.run))
 else:parser.error('explicit --run NEW-UNIQUE-DIR or --verify required')
