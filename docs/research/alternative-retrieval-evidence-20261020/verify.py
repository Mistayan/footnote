import pathlib,json,re,hashlib,subprocess,datetime
B=pathlib.Path(__file__).parent
D=B.parent/'ALTERNATIVE-RETRIEVAL-ARCHITECTURES.md'
S='C:/Users/johan/AppData/Local/hermes/skills/research/grounded-citations/scripts/sources.py'
commands=[]
for args in [('render','--replace-in',str(D)),('verify',str(D),'--evidence','--strict')]:
 r=subprocess.run(['python',S,'--ledger',str(B/'ledger.json'),*args],capture_output=True,text=True,encoding='utf-8');commands.append({'arguments':args,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 assert r.returncode==0,r.stdout+r.stderr
text=D.read_text(encoding='utf-8'); broken=[];checked=[]
for target in re.findall(r'\]\(([^)]+)\)',text):
 if '://' in target:continue
 p=(D.parent/target.split('#')[0]).resolve();checked.append(str(p))
 if not p.exists():broken.append(str(p))
assert not broken,broken
pair=pathlib.Path('D:/Projets/BorgKnowledge/artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/primary-pair-per-query.json')
pair_data=json.loads(pair.read_text(encoding='utf-8'))
assert len(pair_data)==32 and all(r['sqlite_top5']==r['qdrant_top5'] for r in pair_data)
paired_review={'queries':len(pair_data),'ordered_top5_equal':sum(r['sqlite_top5']==r['qdrant_top5'] for r in pair_data),'splits':{}}
for split in sorted({r['split'] for r in pair_data}):
 rows=[r for r in pair_data if r['split']==split]; answerable=[r for r in rows if r['relevant']]; noanswer=[r for r in rows if not r['relevant']]
 paired_review['splits'][split]={'answerable':len(answerable),'noanswer':len(noanswer),'noanswer_candidate_returns':sum(bool(r['qdrant_top5']) for r in noanswer),'p1':sum(r['qdrant_precision']['p1'] for r in answerable)/len(answerable),'mrr5':sum(r['qdrant_metrics']['mrr'] for r in answerable)/len(answerable),'recall5':sum(r['qdrant_metrics']['recall_at_5'] for r in answerable)/len(answerable)}
receipt={'primary_pair_independent_static_review':paired_review,'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'citation_commands':commands,'checked_local_link_targets':checked,'broken_links':broken,'primary_pair_shape':{'type':type(pair_data).__name__,'keys_or_length':list(pair_data)[:10] if isinstance(pair_data,dict) else len(pair_data)},'report_sha256':hashlib.sha256(D.read_bytes()).hexdigest(),'scope':'Research and static checks only; no alternative engine or fresh relevance experiment executed.'}
(B/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in B.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'}
(B/'evidence-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2,ensure_ascii=False));print('Evidence files hashed:',len(manifest))
