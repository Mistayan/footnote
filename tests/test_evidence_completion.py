import unittest
from tools.evidence_completion.core import complete

class CompletionTests(unittest.TestCase):
    def test_sentence_exact_offsets(self):
        text='Avant. This sentence is complete. After.'
        result=complete(text,12,25)
        self.assertEqual(result['text'],'This sentence is complete.')
        self.assertEqual(text[result['start']:result['end']],result['text'])
        self.assertEqual(result['version'],2)

    def test_code_blocks_and_doctest_not_split(self):
        for text in ['Intro.\n```py\na = 1.\nb = 2\n```\nAfter.', "Intro.\n>>> f('x.py')\nFalse\n>>> f('a/*.py')\nTrue\nAfter."]:
            start=text.index('b =') if 'b =' in text else text.index('True')
            result=complete(text,start,start+2)
            self.assertIn('```py' if '```' in text else ">>> f('x.py')",result['text'])
            self.assertIn('```\n' if '```' in text else 'True',result['text'])

    def test_budget_unicode_and_invalid(self):
        text='é. '+('a'*2600)+'. Next.'
        result=complete(text,20,30)
        self.assertFalse(result['boundary_complete'])
        self.assertEqual(result['text'],text[20:30])
        self.assertLessEqual(len(result['text']),2500)
        for a,b in [(-1,2),(5,4),(0,9999),(0,2600)]:
            with self.assertRaises(ValueError):complete(text,a,b)

    def test_metadata_filter_before_budget_and_get(self):
        from tools.evidence_completion.core import eligible, get_evidence
        docs=[dict(id='a',source='english',start=0,end=4,text='Test'),dict(id='b',source='french',start=0,end=4,text='Test')]
        sources={'english':{'language':'en'},'french':{'language':'fr'}}
        self.assertEqual([d['id'] for d in eligible(docs,sources,{'source_language':'fr'})[:1]],['b'])
        self.assertEqual(len(eligible(docs,sources,{})),2)
        self.assertEqual(eligible(docs,{}, {'source_language':'fr'}),[])
        with self.assertRaises(ValueError):get_evidence(docs[0],{'english':'Test.'},sources,{'source_language':'fr'},True)
        item=get_evidence(docs[1],{'french':'Test.'},sources,{'source_language':'fr'},True)
        self.assertEqual(item['original'],docs[1])
        self.assertEqual(item['presentation']['text'],'Test.')
        self.assertEqual(item['presentation']['version'],2)
        self.assertEqual(get_evidence(docs[1],{'french':'Test.'},sources,{},False)['presentation']['version'],1)

    def test_explicit_request_parser_not_query_language(self):
        from tools.evidence_completion.core import request_metadata
        self.assertEqual(request_metadata('Selon vous, expliquer contextmanager en français.'),{})
        self.assertEqual(request_metadata('According to the French contextlib documentation, explain yield.'),{'source_language':'fr'})
        self.assertEqual(request_metadata('According to the English pathlib documentation, explain paths.'),{'source_language':'en'})
        self.assertEqual(request_metadata('Selon la documentation française de pathlib, expliquer les chemins.'),{'source_language':'fr'})

if __name__=='__main__':unittest.main()
