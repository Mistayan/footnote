"""Pre-inference authored source gold. Never reads candidate outputs."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
# source, question language, question, answer statement, exact start, exact end
FACTS=[
('json-en','en','What happens to unsupported dictionary keys when json.dump uses skipkeys=True?','Unsupported basic-type-excluded keys are skipped rather than TypeError.','skipkeys (bool)', 'Default False.'),
('json-en','en','With json.dump ensure_ascii=False, are quotation marks still escaped?','Yes; mandatory escapes including quotation mark remain.','ensure_ascii (bool)', 'U+001F.'),
('json-en','en','What exception does json.dump raise for NaN with allow_nan=False?','ValueError.','allow_nan (bool)', '(NaN, Infinity, -Infinity) are used.'),
('json-en','en','What risk is documented for a circular container when check_circular=False in json.dump?','RecursionError or worse.','check_circular (bool)', 'Default True.'),
('json-en','en','For json.dump indent=0, are newlines inserted without indentation?','Yes, only newlines.','indent (int', 'no newlines are inserted.'),
('json-en','en','Which separators tuple produces the most compact JSON without whitespace?','Comma and colon, separators=(comma, colon).','separators (tuple', 'eliminate whitespace.'),
('json-en','en','What must the json.dump default callback return or raise?','JSON encodable object or TypeError.','default (callable', 'TypeError is raised.'),
('dataclasses-en','en','Does dataclass(init=True) overwrite an existing __init__ method?','No; parameter ignored if class defines __init__.','init: If true', 'ignored.'),
('dataclasses-en','en','Are fields excluded from repr included in a dataclass generated __repr__ string?','No.','repr: If true', 'are not included.'),
('dataclasses-en','en','What happens if dataclass order=True but eq=False?','ValueError.','order: If true', 'ValueError is raised.'),
('json-en','fr','Quel argument permet de remplacer chaque dictionnaire JSON décodé par la valeur renvoyée par une fonction ?','object_hook.','object_hook (callable', 'Default None.'),
('json-en','fr','Comment décoder les nombres JSON à virgule flottante en decimal.Decimal plutôt qu’en float ?','Supply parse_float=decimal.Decimal.','parse_float (callable', 'for example decimal.Decimal.'),
('json-en','fr','Avec JSONDecoder strict=False, quels codes de caractères de contrôle sont autorisés dans les chaînes ?','Codes 0 through 31.','If strict is false', "'\\n', '\\r' and '\\0'."),
('json-en','fr','Que contient le second élément du tuple renvoyé par JSONDecoder.raw_decode ?','Index in input where document ended.','Decode a JSON document from s', 'where the document ended.'),
('json-en','fr','Quand plusieurs membres JSON portent le même nom, quelle paire est conservée par défaut ?','Last name-value pair.','The RFC specifies that the names within a JSON object', 'for a given name:'),
('json-en','fr','Quelle exception le désérialiseur JSON documente-t-il si un BOM initial est présent ?','ValueError.','The RFC prohibits adding a byte order mark', 'when an initial BOM is present.'),
('dataclasses-en','fr','Quelle exception est levée lors de l’affectation d’un champ d’une dataclass frozen=True ?','FrozenInstanceError.','It is not possible to create truly immutable Python objects.', 'methods will raise a FrozenInstanceError when invoked.'),
('dataclasses-en','fr','Peut-on demander weakref_slot=True sans slots=True dans une dataclass ?','No; it is an error.','weakref_slot: If true', 'without also specifying slots=True.'),
('dataclasses-en','fr','Combien d’arguments doit accepter une default_factory de champ dataclass ?','Zero arguments.','default_factory: If provided', 'both default and default_factory.'),
('dataclasses-en','fr','Comment dataclasses.asdict copie-t-il les objets autres que dataclasses, dictionnaires, listes et tuples ?','copy.deepcopy.','Converts the dataclass obj to a dict', 'copy.deepcopy().'),
('json-fr','en','Do the JSON encoder and decoder preserve input and output order by default?','Yes unless underlying containers unordered.',"Les encodeurs et décodeurs de ce module", 'ne sont pas ordonnés.'),
('json-fr','en','Why do repeated json.dump calls on the same file create invalid JSON?','JSON is not a framed protocol.',"À l'inverse de pickle", 'fichier JSON invalide.'),
('json-fr','en','What Python result type does json.dumps return?','str.','Sérialise obj en une str', 'ceux de dump().'),
('dataclasses-fr','en','What exception results from a dataclass non-default field following a default field, including through inheritance?','TypeError.','Une TypeError est levée si un champ', 'héritage de classes.'),
('dataclasses-fr','en','Does dataclasses.fields include pseudo-fields annotated ClassVar or InitVar?','No.','Renvoie un n-uplet', 'exception TypeError est levée.'),
('asyncio-queue-fr','en','What does an asyncio.Queue maxsize less than or equal to zero mean?','Infinite queue size.','Si maxsize est inférieur', 'supprimé par get().'),
('asyncio-queue-fr','en','Are asyncio queues safe for multithreaded programs?','No.','Les files d\'attente asyncio sont conçues', 'code async/await.'),
('asyncio-queue-fr','en','What function is recommended to impose a timeout on asyncio queue operations?','asyncio.wait_for.','Notez que les méthodes', "avec un délai d'attente."),
('asyncio-queue-fr','en','When does asyncio.Queue.join unblock?','After all items retrieved and processed / unfinished tasks zero.','Bloque jusqu’à', 'traités.'),
('asyncio-queue-fr','en','What exception occurs when task_done is called more times than items put into the asyncio queue?','ValueError.','Lève une exception ValueError', 'dans la file.'),
('asyncio-queue-fr','fr','Dans quel ordre une asyncio.Queue ordinaire récupère-t-elle les éléments ?','FIFO.','File d\'attente premier entré', 'first out).'),
('asyncio-queue-fr','fr','Que renvoie qsize() pour une asyncio.Queue ?','Number of items.','Renvoie le nombre', "dans la file d'attente."),
('asyncio-queue-fr','fr','Avec asyncio.Queue(maxsize=0), full() peut-il renvoyer True ?','Never True.','If the queue was initialized', 'never returns True.'),
('asyncio-queue-fr','fr','Que fait await queue.get() lorsque la file asyncio est vide ?','Wait for an item.','Supprime et renvoie un élément', "un élément soit disponible."),
('asyncio-queue-fr','fr','Quelle exception get_nowait() lève-t-il sur une asyncio.Queue vide ?','QueueEmpty.','Renvoie un élément s\'il y en a un', 'sinon lève QueueEmpty.'),
('asyncio-queue-fr','fr','Que fait await queue.put(item) lorsque la file asyncio est pleine ?','Wait for a free slot before adding.','Met un élément dans la file', "avant d'ajouter l'élément."),
('asyncio-queue-fr','fr','Quelle exception put_nowait() lève-t-il si aucun emplacement libre n’est immédiatement disponible ?','QueueFull.','Si aucun emplacement libre', 'lève QueueFull.'),
('asyncio-queue-fr','fr','Avec asyncio.PriorityQueue, les priorités les plus basses ou les plus hautes sortent-elles en premier ?','Lowest priority first.','Une variante de Queue\xa0; récupère les entrées par ordre', 'basse en premier).'),
('asyncio-queue-fr','fr','Quelle variante de file asyncio récupère les entrées les plus récemment ajoutées en premier ?','LifoQueue.','class asyncio.LifoQueue', 'premier sorti).'),
('asyncio-queue-fr','fr','Dans quelle version le paramètre loop de asyncio.Queue a-t-il été supprimé ?','3.10.','Modifié dans la version 3.10:', 'suppression du paramètre loop.'),
]
NOANSWER=[
('en','According to the English Python 3.13 documentation, what compression ratio does json.dumps(compress=True) guarantee?','Invented json compression parameter.'),
('fr','Selon la documentation française Python 3.13, quel algorithme de chiffrement est activé par json.dumps(encrypt=True) ?','Invented encryption parameter.'),
('en','According to the English Python 3.13 documentation, what exact nanosecond latency is guaranteed for asyncio.Queue.put?','No timing guarantee.'),
('fr','Selon la documentation française Python 3.13, quel est le nombre maximal de consommateurs garanti par asyncio.PriorityQueue ?','No consumer-count guarantee.'),
('en','According to the English Python 3.13 documentation, what is the dataclass cache_ttl default in seconds?','Invented cache_ttl.'),
('fr','Selon la documentation française Python 3.13, quelle base de données est utilisée automatiquement par dataclass(persist=True) ?','Invented persistence.'),
('en','According to the English Python 3.13 documentation, which network port does asyncio.Queue.listen use by default?','Invented listen API.'),
('fr','Selon la documentation française Python 3.13, quelle méthode asyncio.Queue.rollback annule une insertion ?','Invented rollback API.'),
('en','According to the English Python 3.13 documentation, what exact SHA-256 digest is guaranteed by dataclasses.asdict?','No digest guarantee.'),
('fr','Selon la documentation française Python 3.13, quelle option json.loads valide automatiquement un schéma JSON Schema ?','Absent schema validation API.'),
('en','What is the private BorgKnowledge production API token stored in my vault?','Private unavailable; no private source access.'),
('fr','Quel est le mot de passe privé de mon compte et le chemin de mon coffre personnel ?','Private unavailable; no private source access.'),
]

def main(run):
    run=Path(run);sources=json.loads((run/'source-receipts.json').read_bytes());texts={s:(run/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources};corpus=json.loads((run/'corpus.json').read_bytes());rows=[]
    for i,(s,lang,q,answer,a,b) in enumerate(FACTS,1):
        text=texts[s]
        # Uniform typography normalization for author anchors only, never sources.
        if a not in text:
            options=[a.replace('’',"'"),a.replace("'",'’'),a.replace('\xa0',' ')]
            a=next((x for x in options if x in text),a)
        start=text.find(a);end=text.find(b,start)+len(b)
        if start<0 or end<len(b):raise ValueError((i,s,a,b))
        quote=text[start:end];edition=sources[s]['language']
        prefix=('According to the '+('French' if edition=='fr' else 'English')+' Python 3.13 documentation, ') if lang=='en' else ('Selon la documentation '+('française' if edition=='fr' else 'anglaise')+' Python 3.13, ')
        rows.append(dict(id=f'Q{i:02}',query=prefix+q,language=lang,evidence_language=edition,answerable=True,answer_statement=answer,semantic_criteria='Evidence must directly support the complete answer statement in correct Python 3.13 scope; semantically equivalent evidence in any window of an eligible source is acceptable. Exact-ID match is NOT correctness.',applicability=dict(required_source_language=edition,version='3.13',eligible_sources=[n for n,v in sources.items() if v['language']==edition],excluded_sources=[n for n,v in sources.items() if v['language']!=edition],body_language='French edition may contain untranslated English; edition constraint concerns official source URL, not every sentence language.'),acceptable_quotes=[dict(source=s,start=start,end=end,quote=quote)],expected_ids=[d['id'] for d in corpus if d['source']==s and quote in d['text']]))
    for i,(lang,q,reason) in enumerate(NOANSWER,41):rows.append(dict(id=f'Q{i:02}',query=q,language=lang,answerable=False,answer_statement=None,semantic_criteria='No complete answer in any frozen corpus source; reject topical near-miss or invented API. '+reason,applicability=dict(eligible_sources=list(sources),version='3.13'),acceptable_quotes=[],expected_ids=[]))
    assert len(rows)==52 and len({r['query'] for r in rows})==52
    (run/'gold-DO-NOT-SEND.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    (run/'requests.json').write_text(json.dumps([{k:r[k] for k in ('id','query','language')} for r in rows],ensure_ascii=False,indent=2),encoding='utf8')
    print('GOLD',len(rows),'answerable',sum(r['answerable'] for r in rows),'directions',{a+'->'+b:sum(r['answerable'] and r['language']==a and r.get('evidence_language')==b for r in rows) for a in ['en','fr'] for b in ['en','fr']})
if __name__=='__main__':main(sys.argv[1])
