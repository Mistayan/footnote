"""Fetch official byte snapshots only. No models, gold or ranking are used."""
import sys,json,uuid,hashlib,datetime,urllib.request,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.final_multilingual_confirmation.corpus import extract,blocks

def main():
    run=ROOT/'artifacts/final-multilingual-confirmation'/('fresh-'+uuid.uuid4().hex)
    (run/'sources').mkdir(parents=True)
    def fetch(item):
        name,url,lang=item
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BorgKnowledge-public-source-benchmark/1.0'}),timeout=45) as r:raw=r.read();final=r.url;headers=dict(r.headers)
            (run/'sources'/(name+'.raw')).write_bytes(raw)
            text=extract(raw) if lang else raw.decode('utf8')
            (run/'sources'/(name+'.txt')).write_text(text,encoding='utf8',newline='')
            return name,dict(url=url,final_url=final,language=lang,version='Python 3.13 documentation snapshot; all statements apply only as documented in these frozen bytes',sha256=hashlib.sha256(raw).hexdigest(),text_sha256=hashlib.sha256(text.encode()).hexdigest(),license='PSF License Version 2; documentation examples additionally Zero-Clause BSD per retained official license',license_receipt='python-license',fetched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),headers=headers,chars=len(text))
        except Exception as e:return name,{'error':repr(e),'url':url}
    items=[(topic+'-'+lang,'https://docs.python.org/'+('fr/' if lang=='fr' else '')+'3.13/library/'+topic+'.html',lang) for topic in ['json','dataclasses','asyncio-queue'] for lang in ['en','fr']]
    items.append(('python-license','https://docs.python.org/3.13/license.html','en'))
    rows=dict(concurrent.futures.ThreadPoolExecutor(max_workers=7).map(fetch,items))
    (run/'network-receipts.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    sources={k:v for k,v in rows.items() if k!='python-license' and 'error' not in v}
    assert len(sources)==6 and 'error' not in rows['python-license'],rows
    (run/'source-receipts.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf8')
    corpus=[d for s in sources for d in blocks(s,(run/'sources'/(s+'.txt')).read_text(encoding='utf8'))]
    (run/'corpus.json').write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf8')
    print(run);print(json.dumps({k:v.get('chars',v.get('error')) for k,v in rows.items()}));print('blocks',len(corpus))
if __name__=='__main__':main()
