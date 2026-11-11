"""Experimental wrapper only. Frozen 96/24 400/100 10 RRF60 pool20."""
import time
from .compiler import eligible,lexical_filtered


def scoped_search(session,query,catalog,request,vector):
    from tools.acquisition_repair.core import acquire
    from qdrant_quality import fresh_connection
    allowed={d['id'] for d in eligible(list(session.docs.values()),catalog,request)}
    pointids=[i+1 for i,r in enumerate(session.records) if eligible([r],catalog,request)]
    if not allowed or not pointids:
        return dict(pool=[],ranked=[],scores={},top5=[],dense=[],lexical=[],allowed_parent_count=len(allowed),allowed_point_count=len(pointids),contributions={},stage_seconds={})
    started=time.perf_counter();fresh_connection(session.server)
    payload=dict(query=vector.tolist(),limit=400,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=512),filter={'must':[{'has_id':pointids}]})
    response=session.server.request('POST','/collections/selected/points/query',payload)
    assert {p['id'] for p in response['result']['points']}<=set(pointids)
    dense=acquire(response['result']['points'],session.records,[],100)['dense']
    dense_seconds=time.perf_counter()-started
    assert set(dense)<=allowed
    started=time.perf_counter();lexical=lexical_filtered(session.db,query,allowed,10);lexical_seconds=time.perf_counter()-started
    contributions={}
    for branch,names in [('dense',dense),('lexical',lexical)]:
        for rank,n in enumerate(names,1):contributions.setdefault(n,{})[branch]=dict(rank=rank,contribution=1/(60+rank))
    pool=sorted(contributions,key=lambda n:(-sum(x['contribution'] for x in contributions[n].values()),n))[:20]
    started=time.perf_counter();ranking,scores=session.ranker.rank(query,[session.docs[n] for n in pool]);rerank_seconds=time.perf_counter()-started
    return dict(pool=pool,ranked=ranking,scores=scores,top5=ranking[:5],dense=dense,lexical=lexical,allowed_parent_count=len(allowed),allowed_point_count=len(pointids),contributions=contributions,server_request=payload,server_response=response,stage_seconds=dict(dense=dense_seconds,lexical=lexical_seconds,rerank=rerank_seconds))
