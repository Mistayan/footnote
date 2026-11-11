import pathlib,subprocess,json
B=pathlib.Path(__file__).parent
S='C:/Users/johan/AppData/Local/hermes/skills/research/grounded-citations/scripts/sources.py'
# Exact retained line ranges chosen after reading the source text.
ranges={1:[(36,46),(379,398)],2:[(44,46),(108,116)],3:[(65,80)],6:[(81,98),(150,156)],7:[(11,19)],8:[(11,19)],9:[(1,3)],10:[(2,4)],11:[(92,94),(270,272)],12:[(140,149)],13:[(262,290)],15:[(15,22)],17:[(1,16)],18:[(1,3)],19:[(8,41),(120,150)],20:[(406,430)],21:[(1,25)],22:[(10,20)],23:[(72,95)],24:[(1,12)],26:[(40,54)],27:[(99,117),(615,625)],28:[(1,3)],29:[(230,269),(342,360)],30:[(118,125),(138,181)]}
mapping=json.loads((B/'citation-map.json').read_text(encoding='utf-8'))
for row in mapping:
 cid=row['citation']; p=B/f"source-{row['source']:02}.txt"; lines=p.read_text(encoding='utf-8').splitlines()
 for lo,hi in ranges.get(cid,[]):
  q='\n'.join(lines[lo-1:hi]);r=subprocess.run(['python',S,'--ledger',str(B/'ledger.json'),'quote',str(cid),'--text',q,'--from',str(p)],capture_output=True,text=True,encoding='utf-8')
  if r.returncode: print(cid,lo,hi,r.stderr,r.stdout)
print('Evidence enrichment finished')
