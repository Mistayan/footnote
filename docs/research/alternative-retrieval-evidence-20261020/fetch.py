import urllib.request, concurrent.futures, pathlib, json, html.parser, datetime
BASE=pathlib.Path(__file__).parent
URLS=[
'https://raw.githubusercontent.com/pgvector/pgvector/master/README.md',
'https://raw.githubusercontent.com/paradedb/paradedb/main/README.md',
'https://docs.paradedb.com/documentation/tokenizers/overview',
'https://docs.vespa.ai/en/ranking/phased-ranking.html',
'https://docs.vespa.ai/en/rag/embedding.html',
'https://docs.vespa.ai/en/operations/self-managed/docker-containers.html',
'https://docs.opensearch.org/latest/vector-search/ai-search/hybrid-search/index/',
'https://www.elastic.co/docs/solutions/search/hybrid-search',
'https://docs.lancedb.com/search/multivector-search',
'https://qdrant.tech/documentation/advanced-tutorials/using-multivector-representations/',
'https://arxiv.org/abs/2112.01488',
'https://arxiv.org/abs/2004.12832',
'https://raw.githubusercontent.com/vespa-engine/vespa/master/LICENSE',
'https://raw.githubusercontent.com/lancedb/lancedb/main/LICENSE',
'https://opensearch.org/downloads.html',
'https://www.elastic.co/pricing/faq/licensing',
'https://github.com/pgvector/pgvector/issues/721',
'https://github.com/paradedb/paradedb/issues?q=Windows',
'https://docs.opensearch.org/latest/analyzers/language-analyzers/index/',
'https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-with-zip-on-windows',
'https://docs.paradedb.com/documentation/getting-started/install',
'https://raw.githubusercontent.com/pgvector/pgvector/master/LICENSE',
'https://raw.githubusercontent.com/opensearch-project/OpenSearch/main/LICENSE.txt'
]
class Text(html.parser.HTMLParser):
 def __init__(self): super().__init__(); self.out=[]; self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'): self.skip+=1
  if t in ('p','div','h1','h2','h3','li','tr','pre','br'): self.out.append('\n')
 def handle_endtag(self,t):
  if t in ('script','style'): self.skip=max(0,self.skip-1)
 def handle_data(self,d):
  if not self.skip:self.out.append(d)
def fetch(x):
 i,url=x; rec={'id':i,'url':url,'fetched_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 research'}),timeout=40) as r:
   raw=r.read();rec.update(status=r.status,final_url=r.url)
  text=raw.decode('utf-8','replace'); (BASE/f'source-{i:02}.raw').write_bytes(raw)
  if '<html' in text[:3000].lower() or '<!doctype' in text[:3000].lower():
   p=Text();p.feed(text);text='\n'.join(s.strip() for s in ''.join(p.out).splitlines() if s.strip())
  (BASE/f'source-{i:02}.txt').write_text(text,encoding='utf-8');rec['chars']=len(text)
 except Exception as e:rec['error']=str(e)
 return rec
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex: rows=list(ex.map(fetch,enumerate(URLS,1)))
 (BASE/'fetch-manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print(json.dumps(rows,indent=2))
