"""Pinned offline resident ONNX reranker callable for independent evaluators."""
from pathlib import Path
import hashlib,json,time

class ResidentRanker:
    def __init__(self,directory,cap=512):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.directory=Path(directory); self.cap=cap
        receipt=json.loads((self.directory/'receipt.json').read_bytes())
        for name,item in receipt['files'].items():
            if hashlib.sha256((self.directory/name).read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('model artifact hash mismatch: '+name)
        self.tokenizer=Tokenizer.from_file(str(self.directory/'tokenizer.json'))
        self.tokenizer.no_padding(); self.tokenizer.no_truncation()
        self.counter=Tokenizer.from_str(self.tokenizer.to_str())
        self.tokenizer.enable_truncation(max_length=cap,strategy='longest_first')
        self.tokenizer.enable_padding(pad_id=1,pad_token='<pad>')
        opts=ort.SessionOptions(); opts.intra_op_num_threads=2; opts.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(self.directory/'model.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
        self.session_loads=1
    def evaluate(self,query,documents):
        import numpy as np
        if len({d['id'] for d in documents})!=len(documents): raise ValueError('duplicate candidate IDs')
        start=time.perf_counter(); scores={}; lengths={}; visible={}
        for offset in range(0,len(documents),4):
            batch=documents[offset:offset+4]
            tokens=self.tokenizer.encode_batch([(query,d['text']) for d in batch])
            ids=np.asarray([t.ids for t in tokens],dtype=np.int64)
            mask=np.asarray([t.attention_mask for t in tokens],dtype=np.int64)
            inputs={'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)}
            logits=self.session.run(None,{i.name:inputs[i.name] for i in self.session.get_inputs()})[0].reshape(-1)
            if len(logits)!=len(batch) or not np.isfinite(logits).all(): raise ValueError('nonfinite or invalid logits')
            for d,t,s in zip(batch,tokens,logits):
                scores[d['id']]=float(s)
                lengths[d['id']]=len(self.counter.encode(query,d['text']).ids)
                visible[d['id']]={'text':self.tokenizer.decode([i for i,m in zip(t.ids,t.attention_mask) if m]),'offsets':t.offsets,'sequence_ids':t.sequence_ids}
        return dict(ranked=sorted(scores,key=lambda n:(-scores[n],n)),scores=scores,pair_tokens=lengths,visible=visible,wall_ms=(time.perf_counter()-start)*1000,session_loads=self.session_loads)
    def rank(self,query,documents):
        out=self.evaluate(query,documents)
        return out['ranked'],out['scores']
