import importlib
import unittest

class ScopeTests(unittest.TestCase):
    def test_explicit_language_version_and_verbatim_spans(self):
        spec=importlib.util.find_spec('tools.request_scope_repair.compiler') if importlib.util.find_spec('tools.request_scope_repair') else None
        self.assertIsNotNone(spec, 'request scope compiler is not implemented')
        c=importlib.import_module('tools.request_scope_repair.compiler')
        q='According to the English Python 3.13 documentation, explain json.dump.'
        r=c.compile_scope(q,{})
        self.assertEqual(r['constraints'],{'source_language':'en','documented_version':'3.13'})
        self.assertEqual(r['request'],q)
        for s in r['spans']: self.assertEqual(q[s['start']:s['end']],s['text'])

class CatalogTests(unittest.TestCase):
    def test_catalog_family_comparison_and_editions(self):
        from tools.request_scope_repair import compiler as c
        self.assertTrue(hasattr(c,'build_catalog'),'authoritative catalog missing')
        sources={'j':dict(language='fr',version='Python 3.13 snapshot',url='https://docs.python.org/fr/3.13/library/json.html'),'d':dict(language='en',version='Python 3.13 snapshot',url='https://docs.python.org/3.13/library/dataclasses.html')}
        raw={'j':'<title>json — JSON encoder and decoder — Python 3.13.16 documentation</title>','d':'<title>dataclasses — Data Classes — Python 3.13.16 documentation</title>'}
        catalog=c.build_catalog(sources,raw)
        r=c.compile_scope('Compare json.dumps and dataclasses.asdict.',catalog)
        self.assertEqual(set(r['constraints']['source_families']),{'json','dataclasses'})
        self.assertFalse(r['fail_closed'])
        r=c.compile_scope('Explain dataclass(init=True)',catalog)
        self.assertEqual(r['constraints']['source_families'],['dataclasses'])
        for q in ['Réponds en français : json.dumps', 'Answer in French: json.dumps', 'Que fait json.dumps ?']:
            self.assertNotIn('source_language',c.compile_scope(q,catalog)['constraints'])
        for q in ['Use French documentation for Python 3.13 json.dumps', 'Selon la documentation française Python 3.13, json.dumps', 'Use the documentation in French for Python 3.13 json.dumps']:
            self.assertEqual(c.compile_scope(q,catalog)['constraints']['source_language'],'fr')
        self.assertTrue(c.compile_scope('English documentation and French documentation',catalog)['fail_closed'])
        self.assertEqual(c.compile_scope('English documentation',catalog,{'source_language':'fr'})['constraints']['source_language'],'fr')

class GateTests(unittest.TestCase):
    def test_unknown_empty_scope_get_and_lexical_prelimit(self):
        from tools.request_scope_repair import compiler as c
        self.assertTrue(hasattr(c,'eligible'),'independent scope gate absent')
        catalog={'ok':{'language':'fr','documented_version':'3.13.16','family':'json'},'unknown':{'language':None,'documented_version':None,'family':None}}
        request=c.compile_scope('French Python 3.13 documentation',catalog={})
        docs=[{'id':'yes','source':'ok'},{'id':'no','source':'unknown'}]
        self.assertEqual(c.eligible(docs,catalog,request),[docs[0]])
        self.assertEqual(c.eligible(docs,catalog,c.compile_scope('Python 3.12 documentation',{})),[])
        self.assertEqual(c.eligible(docs,catalog,c.compile_scope('Compare Python 3.12 and Python 3.13 documentation',{})),[])
        with self.assertRaises(ValueError):c.get_evidence(docs[1],{},catalog,request)
        import sqlite3
        db=sqlite3.connect(':memory:');db.execute('CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED,text)')
        db.executemany('INSERT INTO documents VALUES (?,?)',[(f'bad{i}','json json json') for i in range(30)]+[('yes','json')])
        self.assertEqual(c.lexical_filtered(db,'json',{'yes'},10),['yes'])
        self.assertEqual(c.lexical_filtered(db,'json',set(),10),[])
        request=c.compile_scope('English documentation',{}, {'source_language':'fr'})
        self.assertEqual(c.eligible(docs,catalog,request),[docs[0]])

class RetrievalTests(unittest.TestCase):
    def test_empty_and_prelimit_scope(self):
        import importlib
        spec=importlib.util.find_spec('tools.request_scope_repair.retrieval')
        self.assertIsNotNone(spec,'standalone retrieval adapter missing')
        from tools.request_scope_repair.retrieval import scoped_search
        from types import SimpleNamespace
        import sqlite3
        db=sqlite3.connect(':memory:');db.execute('CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED,text)')
        session=SimpleNamespace(docs={'a':{'id':'a','source':'s','text':'x'}},records=[{'id':'slice','source':'s'}],db=db)
        result=scoped_search(session,'Python 3.12 documentation',{'s':{'documented_version':'3.13'}},{'constraints':{'documented_version':'3.12'}} ,None)
        self.assertEqual(result['ranked'],[])
        self.assertEqual(result['allowed_point_count'],0)

class PreferenceTests(unittest.TestCase):
    def test_output_preference_near_documentation_is_not_source_edition(self):
        from tools.request_scope_repair.compiler import compile_scope
        self.assertNotIn('source_language',compile_scope('Answer in French using Python 3.13 documentation',{})['constraints'])
        r=compile_scope('Answer in French using the English Python 3.13 documentation',{})
        self.assertEqual(r['constraints']['source_language'],'en')
        self.assertFalse(r['fail_closed'])
        self.assertNotIn('source_language',compile_scope('Réponds en français selon la documentation Python 3.13',{})['constraints'])

class FormalTests(unittest.TestCase):
    def test_bad_formal_values_fail_closed_not_silent_broadening(self):
        from tools.request_scope_repair.compiler import compile_scope,eligible
        for formal in [{'source_families':'json'},{'source_families':[]},{'source_language':'xx'},{'documented_version':'latest'}]:
            r=compile_scope('hello',{},formal)
            self.assertTrue(r['fail_closed'],formal)
            self.assertEqual(eligible([{'source':'s'}],{'s':{}},r),[])

class TitleTokenTests(unittest.TestCase):
    def test_title_namespace_tokens_casefold_without_crossmodule_narrowing(self):
        from tools.request_scope_repair.compiler import compile_scope
        catalog={'j':{'family':'json','aliases':['json']},'d':{'family':'dataclasses','aliases':['dataclasses']}}
        r=compile_scope('Compare JSON and dataclasses documents',catalog)
        self.assertEqual(r['constraints']['source_families'],['dataclasses','json'])

if __name__=='__main__': unittest.main()
