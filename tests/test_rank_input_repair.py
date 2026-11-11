import unittest
import importlib

class InputTests(unittest.TestCase):
    def test_01_preserve_without_enforcement(self):
        from tools.rank_input_repair import core
        q='According to the English Python 3.13 documentation, do not change x.y --flag=3.'
        self.assertEqual(core.query_view(q,{},False)['text'],q)

    def test_02_remove_only_compiled_en_clause(self):
        from tools.rank_input_repair.core import query_view
        from tools.request_scope_repair.compiler import compile_scope
        q='According to the English Python 3.13 documentation, do not change x.y --flag=3.'
        r=query_view(q,compile_scope(q,{}),True)
        self.assertEqual(r['text'],'do not change x.y --flag=3.')
        self.assertEqual(q[r['removed'][0]['start']:r['removed'][0]['end']],r['removed'][0]['text'])

    def test_03_french_preserves_negation_and_unicode(self):
        from tools.rank_input_repair.core import query_view
        from tools.request_scope_repair.compiler import compile_scope
        q='Selon la documentation française Python 3.13, ne pas modifier x.y --flag=3 ni 42.'
        self.assertEqual(query_view(q,compile_scope(q,{}),True)['text'],'ne pas modifier x.y --flag=3 ni 42.')

    def test_04_mismatched_compilation_never_removes(self):
        from tools.rank_input_repair.core import query_view
        from tools.request_scope_repair.compiler import compile_scope
        q='According to the English Python 3.13 documentation, keep 3.13 and not None.'
        for scope in [compile_scope('English Python 3.13 documentation',{}),dict(request=q,constraints={'source_language':'en','documented_version':'3.13'},spans=[])]:
            self.assertEqual(query_view(q,scope,True)['text'],q)

    def test_05_windows_exact_source_and_token_cap(self):
        from tools.rank_input_repair.core import passage_views
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        tok=Tokenizer(WordLevel({'[UNK]':0},unk_token='[UNK]'));tok.pre_tokenizer=Whitespace()
        text='alpha beta.\n\n'+' '.join(['long']*40)+'\n\nneedle behavior not 42.'
        views=passage_views('needle behavior',text,tok,8,3)
        self.assertTrue(any('needle' in v['text'] for v in views))
        self.assertLessEqual(len(views),3)
        for v in views:
            self.assertEqual(text[v['start']:v['end']],v['text'])
            self.assertLessEqual(len(tok.encode(v['text'],add_special_tokens=False).ids),8)

    def test_06_limit_is_not_proof_truncation(self):
        from tools.rank_input_repair.core import visibility
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from tokenizers.processors import TemplateProcessing
        tok=Tokenizer(WordLevel({'[UNK]':0,'[CLS]':1,'[SEP]':2},unk_token='[UNK]'));tok.pre_tokenizer=Whitespace()
        tok.post_processor=TemplateProcessing(single='[CLS] $A [SEP]',pair='[CLS] $A [SEP] $B:1 [SEP]:1',special_tokens=[('[CLS]',1),('[SEP]',2)])
        tok.enable_truncation(max_length=8,strategy='longest_first')
        v=visibility(tok,'q','one two three four five',[(0,3),(19,23)])
        self.assertTrue(v['at_limit']);self.assertTrue(v['actually_truncated'])
        self.assertEqual([a['fully_visible'] for a in v['anchors']],[True,False])
        w=visibility(tok,'q','one two three four',[(0,3)])
        self.assertTrue(w['at_limit']);self.assertFalse(w['actually_truncated'])

    def test_07_matched_pairs_and_max_parent_aggregation(self):
        from tools.rank_input_repair.core import make_pairs,aggregate
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        tok=Tokenizer(WordLevel({'[UNK]':0},unk_token='[UNK]'));tok.pre_tokenizer=Whitespace()
        docs=[dict(id='a',text='short.'),dict(id='b',text='long body.')]
        for cap in [None,256,384]:
            pairs=make_pairs('short',docs,tok,cap,3)
            self.assertEqual(len(pairs),6)
            self.assertEqual([p['parent'] for p in pairs],['a']*3+['b']*3)
            ranked,scores=aggregate(pairs,{p['id']:float(i) for i,p in enumerate(pairs)})
            self.assertEqual(ranked,['b','a']);self.assertEqual(scores,{'a':2.,'b':5.})

    def test_08_segment_rounds_preserve_original_batch_context(self):
        from tools.rank_input_repair.core import pair_rounds
        pairs=[dict(id=f'{p}:{slot}',parent=p,slot=slot,text=p) for p in ['a','b','c','d','e'] for slot in range(2)]
        rounds=pair_rounds(pairs)
        self.assertEqual(len(rounds),2)
        self.assertEqual([[p['parent'] for p in r] for r in rounds],[['a','b','c','d','e']]*2)
        self.assertEqual([[p['slot'] for p in r] for r in rounds],[[0]*5,[1]*5])

    def test_09_reusable_full_tokenizer_keeps_exact_visibility(self):
        from tools.rank_input_repair.core import visibility
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        tok=Tokenizer(WordLevel({'[UNK]':0},unk_token='[UNK]'));tok.pre_tokenizer=Whitespace();tok.enable_truncation(max_length=5)
        full=Tokenizer.from_str(tok.to_str());full.no_truncation();full.no_padding()
        self.assertEqual(visibility(tok,'q','a b c d e',[(0,1)]),visibility(tok,'q','a b c d e',[(0,1)],full_tokenizer=full))

if __name__=='__main__':unittest.main()
