"""Questions authored after the source/memory freeze; never used by the writer."""


def questions(rows):
    output = []
    english = [r for r in rows if r['language'] == 'en']
    for row in english:
        p, who, stack = row['project'], row['person'], row['stack']
        prompts = {
          'f1': (f'How can the {p} {stack} daemon avoid hanging during shutdown?',
                 f'Comment éviter le blocage du daemon {stack} de {p} pendant sa fermeture ?',
                 f'Which {stack} release was used to test the {p} daemon shutdown fix?',
                 f'Quelle version de {stack} a servi à tester le correctif de fermeture du daemon {p} ?',
                 'No language/runtime release is recorded for this daemon fix.'),
          'f2': (f'How does {p} prevent duplicate notifications when a job is retried?',
                 f'Comment {p} empêche-t-il les notifications en double quand une tâche est relancée ?',
                 f'Which hash algorithm generates {p} notification idempotency keys?',
                 f'Quel algorithme de hachage génère les clés d’idempotence des notifications de {p} ?',
                 'No key-generation hash algorithm is recorded.'),
          'f3': (f'How should {p} bound accented prompt input without breaking UTF-8 characters?',
                 f'Comment {p} doit-il borner une requête accentuée sans casser les caractères UTF-8 ?',
                 f'What tokenizer library version does the {p} prompt hook use?',
                 f'Quelle version de bibliothèque de tokenisation utilise le hook de requêtes de {p} ?',
                 'No tokenizer library or tokenizer version is recorded.'),
          'f4': (f'What lock ordering fixes the cache-update deadlock in {p}?',
                 f'Quel ordre de verrouillage corrige le blocage de mise à jour du cache dans {p} ?',
                 f'On which operating system was the {p} cache-lock fix validated?',
                 f'Sur quel système d’exploitation le correctif de verrouillage du cache de {p} a-t-il été validé ?',
                 'Cache-fix platform is explicitly unrecorded; daemon test platform is not cache-fix evidence.'),
          'p1': (f'How does {who} want performance comparisons for {p} presented?',
                 f'Comment {who} souhaite-t-il voir présentées les comparaisons de performances de {p} ?',
                 f'Which color palette does {who} require for {p} performance charts?',
                 f'Quelle palette de couleurs {who} exige-t-il pour les graphiques de performances de {p} ?',
                 'No chart color palette is specified.'),
          'p2': (f'What distinction does {who} want made in {p} security audits?',
                 f'Quelle distinction {who} souhaite-t-il voir dans les audits de sécurité de {p} ?',
                 f'Who must approve the {p} security audit before {who} reads it?',
                 f'Qui doit approuver l’audit de sécurité de {p} avant sa lecture par {who} ?',
                 'No audit approver or approval procedure is recorded.'),
          'p3': (f'How does {who} want commands explained in the {p} incident runbooks?',
                 f'Comment {who} veut-il que les commandes soient expliquées dans les procédures d’incident de {p} ?',
                 f'What font size does {who} require for {p} incident runbooks?',
                 f'Quelle taille de police {who} exige-t-il pour les procédures d’incident de {p} ?',
                 'No font size is recorded.'),
          'd1': (f'Which store is authoritative for {p}, and how are its text indexes treated?',
                 f'Quel stockage fait référence pour {p} et quel est le statut de ses index textuels ?',
                 f'How frequently is the {p} authoritative SQLite store backed up?',
                 f'À quelle fréquence le stockage SQLite de référence de {p} est-il sauvegardé ?',
                 'No backup schedule is specified.'),
          'd2': (f'How many failed-job attempts does {p} allow, and where does the job go afterwards?',
                 f'Combien de tentatives {p} autorise-t-il pour une tâche en échec et où va-t-elle ensuite ?',
                 f'What delay does {p} require between retries of a failed job?',
                 f'Quel délai {p} impose-t-il entre les relances d’une tâche en échec ?',
                 'Retry delay is explicitly unspecified.'),
          'd3': (f'How long does {p} retain failed-experiment receipts, and may originals be overwritten?',
                 f'Combien de temps {p} conserve-t-il les reçus d’expérience en échec et peut-on écraser les originaux ?',
                 f'Which encryption algorithm protects the failed-experiment receipts in {p}?',
                 f'Quel algorithme de chiffrement protège les reçus d’expérience en échec de {p} ?',
                 'Receipt encryption algorithm is explicitly unspecified.')}
        en, fr, neg_en, neg_fr, absence = prompts[row['topic']]
        for language, positive, negative in [('en', en, neg_en), ('fr', fr, neg_fr)]:
            common = dict(family=row['family'], project_group=row['project_group'], split=row['split'],
                          language=language, topic=row['topic'])
            output.append(common | dict(id=f'{row["family"]}-{language}-pos', query=positive,
                gold=[row['family']], expected_answer=row['qualified'], source_evidence=row['full']))
            output.append(common | dict(id=f'{row["family"]}-{language}-neg', query=negative,
                gold=[], absence=absence))
    return output
