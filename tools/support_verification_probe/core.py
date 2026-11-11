"""Isolated question-conditioned QA development probe. Margins are not confidence."""

def decode_span(text, start, end, sequence_ids, offsets, cls=0, max_tokens=48):
    valid=[i for i,s in enumerate(sequence_ids) if s==1 and offsets[i][1]>offsets[i][0]]
    candidates=[(float(start[i])+float(end[j]),i,j) for i in valid for j in valid if i<=j<i+max_tokens]
    if not candidates:
        raise ValueError('no visible context tokens')
    score,i,j=max(candidates,key=lambda x:(x[0],-x[1],-x[2]))
    a,b=offsets[i][0],offsets[j][1]
    null=float(start[cls])+float(end[cls])
    return dict(text=text[a:b],start=a,end=b,span_score=score,null_score=null,null_minus_span=null-score)

class QA:
    def __init__(self, directory):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer=Tokenizer.from_file(str(directory/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=384,strategy='only_second')
        self.tokenizer.no_padding()
        options=ort.SessionOptions(); options.intra_op_num_threads=4; options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(directory/'model.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.pairs=0

    def answer(self, question, text):
        import numpy as np
        t=self.tokenizer.encode(question,text)
        inputs={'input_ids':np.asarray([t.ids],dtype=np.int64),'attention_mask':np.asarray([t.attention_mask],dtype=np.int64)}
        start,end=self.session.run(None,inputs); self.pairs+=1
        result=decode_span(text,start[0],end[0],t.sequence_ids,t.offsets,t.ids.index(0))
        return result|dict(tokens=len(t.ids),overflow_windows_omitted=len(t.overflowing),session_id=id(self.session))

def counts(rows):
    a=[r for r in rows if r['answerable']]; n=[r for r in rows if not r['answerable']]
    c=sum(r['accepted'] and r['correct'] for r in a); ac=sum(r['accepted'] for r in a); total=sum(r['accepted'] for r in rows)
    return dict(correct_accepted=c,answerable=len(a),answerable_accepted=ac,answerable_rejected=len(a)-ac,noanswer=len(n),noanswer_false_accept=sum(r['accepted'] for r in n),accepted=total,p1_all_answerable=c/len(a) if a else None,coverage=ac/len(a) if a else None,selected_label_precision=c/total if total else None)
