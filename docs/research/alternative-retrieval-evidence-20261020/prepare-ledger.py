import pathlib,runpy,json,subprocess
B=pathlib.Path(__file__).parent
m=runpy.run_path(str(B/'fetch.py'))
r=m['fetch']((37,'https://github.com/paradedb/paradedb/issues/2686'))
(B/'fetch-final-manifest.json').write_text(json.dumps([r],indent=2),encoding='utf-8')
S='C:/Users/johan/AppData/Local/hermes/skills/research/grounded-citations/scripts/sources.py'
def cmd(*a):
 r=subprocess.run(['python',S,'--ledger',str(B/'ledger.json'),*a],capture_output=True,text=True,encoding='utf-8');
 if r.returncode: raise RuntimeError(r.stdout+r.stderr)
 return r.stdout
print(cmd('reset'))
rows=[]
for n in ['fetch-manifest.json','fetch-more-manifest.json','fetch-final-manifest.json']:rows+=json.loads((B/n).read_text(encoding='utf-8'))
rows.append({'id':36,'url':'https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations/'})
selected=[1,2,3,7,8,9,11,12,13,14,15,16,17,19,20,21,22,23,24,25,26,28,29,30,31,32,33,35,36,37]
terms={1:['perfect recall','Windows','filtering is applied','iterative','Full-Text'],7:['normalization processor','score ranker','rerank','Hybrid search combines'],8:['RRF','rerank','semantic'],21:['Docker','Linux','PostgreSQL'],24:['content nodes','ONNX','total-rerank-count'],25:['intended to be used','ColBERT','paged'],26:['memory','Docker'],29:['JOIN','Enterprise','Community'],30:['Santhanam','2022','NAACL'],33:['3.1','4.1','Limitations','English','MS MARCO'],36:['MaxSim','m=0','prefetch'],37:['Windows','support','2025','2026']}
mapping=[]
for i in selected:
 row=next(r for r in rows if r['id']==i); p=B/f'source-{i:02}.txt'
 if not p.exists():continue
 text=p.read_text(encoding='utf-8'); out=cmd('add',row['url'],'--title',f'Source {i}: '+text.splitlines()[0][:120]); cid=int(__import__('re').search(r'\[(\d+)\]',out).group(1))
 quotes=[]
 for term in terms.get(i, ['Apache License','license','License','MaxSim','Tokenizers','French']):
  lines=text.splitlines(); matches=[j for j,l in enumerate(lines) if term.lower() in l.lower()]
  if not matches: continue
  j=next((j for j in matches if 65<len(lines[j])<900),matches[0]);q=lines[j]
  if len(q)>1800 or len(q.split())<3: continue
  if q in quotes:continue
  cmd('quote',str(cid),'--text',q,'--from',str(p));quotes.append(q)
 mapping.append({'citation':cid,'source':i,'url':row['url'],'quotes':quotes})
 print(f'[{cid}] source-{i:02}: '+ ' | '.join(q.replace('\n',' ')[:360] for q in quotes))
(B/'citation-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
