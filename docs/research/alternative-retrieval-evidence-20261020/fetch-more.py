import runpy, concurrent.futures,json
m=runpy.run_path(str(__import__('pathlib').Path(__file__).with_name('fetch.py')))
urls=[
'https://raw.githubusercontent.com/vespa-engine/documentation/master/en/ranking/phased-ranking.html',
'https://raw.githubusercontent.com/vespa-engine/documentation/master/en/rag/embedding.html',
'https://raw.githubusercontent.com/vespa-engine/documentation/master/en/operations/self-managed/docker-containers.html',
'https://raw.githubusercontent.com/qdrant/landing_page/master/qdrant-landing/content/documentation/advanced-tutorials/using-multivector-representations.md',
'https://raw.githubusercontent.com/vespa-engine/sample-apps/master/colbert/README.md',
'https://www.paradedb.com/docs/reference/joins/overview',
'https://aclanthology.org/2022.naacl-main.272/',
'https://www.elastic.co/docs/reference/text-analysis/analysis-lang-analyzer',
'https://raw.githubusercontent.com/lancedb/lancedb/main/README.md',
'https://arxiv.org/html/2112.01488v3',
'https://www.paradedb.com/docs/llms.txt',
'https://raw.githubusercontent.com/qdrant/qdrant/master/LICENSE'
]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e: rows=list(e.map(m['fetch'],enumerate(urls,24)))
(m['BASE']/'fetch-more-manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows,indent=2))
