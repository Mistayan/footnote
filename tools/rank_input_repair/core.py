"""Separate model representations; original requests/evidence stay immutable."""
import re

def query_view(query, scope, enforced=False):
    pattern=r'^According to the (English|French) Python (\d+\.\d+(?:\.\d+)?) (?:documentation|docs),\s*'
    m=re.match(pattern,query)
    french=re.match(r'^Selon la documentation (anglaise|française) Python (\d+\.\d+(?:\.\d+)?),\s*',query)
    if french:m=french
    if enforced and m and not scope.get('fail_closed') and scope.get('request')==query and all(any(s['field']==field and s.get('start') is not None and 0<=s['start']<s['end']<=m.end() and query[s['start']:s['end']]==s['text'] for s in scope.get('spans',[])) for field in ['source_language','documented_version']):
        c=scope.get('constraints',{})
        lang='en' if m[1] in ('English','anglaise') else 'fr'
        if c.get('source_language')==lang and c.get('documented_version')==m[2]:
            return dict(text=query[m.end():],removed=[dict(start=0,end=m.end(),text=m.group())])
    return dict(text=query,removed=[])


def passage_views(query,text,tokenizer,cap=256,count=2):
    """Greedy source sentence/paragraph windows; query overlap selects, no labels."""
    if cap<1 or count<1:raise ValueError('positive budgets required')
    bounds=[0]+[m.end() for m in re.finditer(r'\n\s*\n|(?<=[.!?])\s+(?=[A-ZÀ-Ö])',text)]+[len(text)]
    pieces=[]
    for a,b in zip(bounds,bounds[1:]):
        enc=tokenizer.encode(text[a:b],add_special_tokens=False)
        offsets=[(x,y) for x,y in enc.offsets if y>x]
        for i in range(0,len(offsets),cap):
            chunk=offsets[i:i+cap]
            if chunk:pieces.append((a+chunk[0][0],a+chunk[-1][1]))
    windows=[];start=None;end=None
    for a,b in pieces:
        if start is not None and len(tokenizer.encode(text[start:b],add_special_tokens=False).ids)>cap:
            windows.append((start,end));start=None
        if start is None:start=a
        end=b
    if start is not None:windows.append((start,end))
    terms=set(re.findall(r'\w+(?:\.\w+)*',query.casefold()))
    scored=[]
    for a,b in windows:
        words=set(re.findall(r'\w+(?:\.\w+)*',text[a:b].casefold()))
        scored.append(dict(start=a,end=b,text=text[a:b],selection_score=len(terms&words)))
    return sorted(scored,key=lambda v:(-v['selection_score'],v['start']))[:count]


def make_pairs(query,docs,tokenizer,cap,count):
    pairs=[]
    for doc in docs:
        views=passage_views(query,doc['text'],tokenizer,cap,count) if cap else [dict(start=0,end=len(doc['text']),text=doc['text'])]
        if not views:views=[dict(start=0,end=0,text='')]
        for i in range(count):
            view=views[min(i,len(views)-1)]
            pairs.append(dict(id=f'{doc["id"]}::segment{i}',parent=doc['id'],slot=i,duplicate_slot=i>=len(views),**view))
    return pairs


def pair_rounds(pairs):
    """Keep original candidate-order batch context in each segment pass."""
    return [[p for p in pairs if p['slot']==slot] for slot in sorted({p['slot'] for p in pairs})]


def aggregate(pairs,scores):
    parents={}
    for p in pairs:parents[p['parent']]=max(parents.get(p['parent'],float('-inf')),scores[p['id']])
    return sorted(parents,key=lambda n:(-parents[n],n)),parents


def visibility(tokenizer,query,text,anchors=(),full_tokenizer=None):
    from tokenizers import Tokenizer
    full=full_tokenizer
    if full is None:
        full=Tokenizer.from_str(tokenizer.to_str());full.no_truncation();full.no_padding()
    original=full.encode(query,text);actual=tokenizer.encode(query,text)
    def spans(enc,seq):return [list(o) for o,s in zip(enc.offsets,enc.sequence_ids) if s==seq and o[1]>o[0]]
    qsp=spans(actual,0);psp=spans(actual,1);fps=spans(original,1)
    limit=(tokenizer.truncation or {}).get('max_length')
    proofs=[]
    for a,b in anchors:
        needed=[o for o in fps if o[0]<b and o[1]>a]
        visible=[o for o in needed if o in psp]
        proofs.append(dict(start=a,end=b,text=text[a:b],tokens=len(needed),visible_tokens=len(visible),fully_visible=bool(needed) and len(visible)==len(needed)))
    return dict(tokens=sum(actual.attention_mask),full_pair_tokens=len(original.ids),at_limit=bool(limit and sum(actual.attention_mask)>=limit),actually_truncated=len(original.ids)>sum(actual.attention_mask),query_offsets=qsp,passage_offsets=psp,query_full_tokens=len(spans(original,0)),query_visible_tokens=len(qsp),passage_full_tokens=len(fps),passage_visible_tokens=len(psp),anchors=proofs)
