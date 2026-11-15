"""Source-only bilingual synthetic histories and agent-authored memory templates.

No questions, gold labels or retrieval output are accepted by this module.
"""
PROJECTS = ['Cobalt', 'Rivage', 'Atlas', 'Lierre', 'Cedar', 'Nacre', 'Beacon', 'Sillage', 'Quartz', 'Luciole',
            'Harbor', 'Brume', 'Orion', 'Aster', 'Maple', 'Corail', 'Vega', 'Opale', 'Juniper', 'Serein',
            'Nimbus', 'Ambre', 'Willow', 'Galene', 'Pulsar', 'Mistral', 'Spruce', 'Ecume', 'Solstice', 'Boreal']
PEOPLE = ['Morgan', 'Nora', 'Eli', 'Camille', 'Rowan', 'Salome', 'Avery', 'Lea', 'Sam', 'Malik',
          'Jamie', 'Ines', 'Alex', 'Remy', 'Sasha', 'Lou', 'Robin', 'Noel', 'Charlie', 'Mael',
          'Andrea', 'Dorian', 'Marin', 'Romy', 'Emile', 'Jules', 'Lina', 'Noa', 'Zoe', 'Isa']
STACKS = ['Rust', 'Python', 'TypeScript', 'Go', 'Java', 'C#']
PLATFORMS = ['Windows', 'Linux', 'macOS']


def source_rows():
    rows = []
    for i, (project, person) in enumerate(zip(PROJECTS, PEOPLE, strict=True)):
        stack, platform = STACKS[i % len(STACKS)], PLATFORMS[(i // 2) % len(PLATFORMS)]
        channel, resource = f'pipe-{i + 1:02}', f'cache_{i + 1:02}'
        ttl, byte_limit, attempts, days = 60 + i, 420 + 2 * i, 3 + i % 5, 30 + i
        queue, db = f'dead.{i + 1:02}', f'ledger_{i + 1:02}.db'
        # Each tuple is a source circumstance, original memory, and qualified memory in EN/FR.
        # The qualified sentences are authored here before any evaluation questions exist.
        facts = [
          ('f1', 'fix',
           f'{project} runs a {stack} daemon; its shutdown fix was tested on {platform}. Closing the worker connection during an active session caused hangs.',
           f'{project} utilise un daemon {stack} ; le correctif de fermeture a été testé sous {platform}. Fermer la connexion du worker pendant une session active causait des blocages.',
           f'Keep worker connection {channel} open until the session completes.',
           f'Garder la connexion {channel} du worker ouverte jusqu’à la fin de la session.',
           f'For {project}’s {stack} daemon, keep connection {channel} open until the session ends to prevent shutdown hangs; tested on {platform}.',
           f'Pour le daemon {stack} de {project}, garder {channel} ouverte jusqu’à la fin de la session évite le blocage à la fermeture ; testé sous {platform}.'),
          ('f2', 'fix',
           f'{project}’s {stack} notification dispatcher could send duplicates when a job was retried. The chosen idempotency-key retention was {ttl} minutes.',
           f'Le distributeur de notifications {stack} de {project} pouvait envoyer des doublons lors d’une relance de tâche. La conservation retenue des clés d’idempotence était de {ttl} minutes.',
           f'Keep notification idempotency keys for {ttl} minutes to suppress retry duplicates.',
           f'Conserver les clés d’idempotence des notifications pendant {ttl} minutes évite les doublons de relance.',
           f'{project}’s {stack} notification dispatcher retains idempotency keys for {ttl} minutes to prevent duplicate sends on retried jobs.',
           f'Le distributeur {stack} de notifications de {project} conserve les clés d’idempotence {ttl} minutes pour éviter les envois en double lors des relances.'),
          ('f3', 'fix',
           f'{project}’s {stack} prompt hook broke accented input when truncating it. The agreed input bound is {byte_limit} bytes, with only an incomplete final UTF-8 character discarded.',
           f'Le hook de requêtes {stack} de {project} cassait les accents lors de la troncature. La limite retenue est de {byte_limit} octets et seul un caractère UTF-8 final incomplet est écarté.',
           f'Bound input to {byte_limit} bytes and drop only an incomplete final UTF-8 character.',
           f'Borner l’entrée à {byte_limit} octets et écarter uniquement le caractère UTF-8 final incomplet.',
           f'For {project}’s {stack} prompt hook, cap input at {byte_limit} bytes and discard only the incomplete final UTF-8 character to preserve accented text.',
           f'Pour préserver les accents dans le hook {stack} de {project}, borner l’entrée à {byte_limit} octets et écarter seulement le caractère UTF-8 final incomplet.'),
          ('f4', 'fix',
           f'{project}’s {stack} cache updater deadlocked when it requested a write lock while retaining its read guard on {resource}. No operating system or library version was recorded.',
           f'La mise à jour du cache {stack} de {project} se bloquait en demandant une écriture tout en gardant le verrou de lecture sur {resource}. Aucun système ni version de bibliothèque n’a été consigné.',
           f'Release the read guard on {resource} before acquiring the write lock.',
           f'Libérer le verrou de lecture sur {resource} avant de demander le verrou d’écriture.',
           f'In {project}’s {stack} cache updater, release {resource}’s read guard before requesting its write lock to avoid deadlock.',
           f'Dans la mise à jour du cache {stack} de {project}, libérer la lecture de {resource} avant de demander son écriture évite le blocage.'),
          ('p1', 'preference',
           f'{person} reviews {project} performance comparisons and wants baseline-relative percentage gaps as well as the actual measurements.',
           f'{person} relit les comparaisons de performances de {project} et souhaite les écarts relatifs en pourcentage ainsi que les mesures elles-mêmes.',
           f'{person} prefers relative percentage gaps alongside raw measured values.',
           f'{person} préfère les écarts relatifs en pourcentage accompagnés des valeurs mesurées.',
           f'For {project} performance comparisons, {person} prefers baseline-relative percentage gaps alongside raw measured values.',
           f'Pour les comparaisons de performances de {project}, {person} préfère les écarts relatifs à la référence en pourcentage, avec les valeurs mesurées.'),
          ('p2', 'preference',
           f'{person} wants {project} security audits to distinguish demonstrated failures from leads that still need validation.',
           f'{person} veut que les audits de sécurité de {project} distinguent les défaillances démontrées des pistes encore à vérifier.',
           f'{person} wants confirmed problems separated from unverified hypotheses.',
           f'{person} souhaite séparer les problèmes confirmés des hypothèses non vérifiées.',
           f'In {project} security audits, {person} wants demonstrated failures separated from leads awaiting validation.',
           f'Dans les audits de sécurité de {project}, {person} veut séparer les défaillances démontrées des pistes restant à vérifier.'),
          ('p3', 'preference',
           f'{person} uses {project} runbooks during incidents and wants copyable commands with a short explanation of their purpose.',
           f'{person} utilise les procédures de {project} pendant les incidents et souhaite des commandes copiables avec une brève explication de leur objectif.',
           f'{person} prefers copyable commands with a short rationale.',
           f'{person} préfère des commandes copiables accompagnées d’une courte justification.',
           f'For {project} incident runbooks, {person} prefers copyable commands with a brief explanation of each command’s purpose.',
           f'Pour les procédures d’incident de {project}, {person} préfère des commandes copiables avec une brève explication de leur objectif.'),
          ('d1', 'fact',
           f'{project} needs transactional authoritative data and a text index that can be rebuilt. The chosen source store is SQLite file {db}.',
           f'{project} a besoin de données de référence transactionnelles et d’un index textuel reconstructible. Le stockage retenu est le fichier SQLite {db}.',
           f'Keep authoritative records in SQLite file {db} and rebuild derived text indexes from it.',
           f'Garder les données de référence dans le fichier SQLite {db} et reconstruire les index textuels dérivés depuis celui-ci.',
           f'{project} keeps its authoritative transactional records in SQLite file {db}, with text indexes treated as rebuildable derived data.',
           f'{project} garde ses données transactionnelles de référence dans le fichier SQLite {db}, les index textuels étant des données dérivées reconstructibles.'),
          ('d2', 'fact',
           f'{project}’s job queue retries transient failures, but the policy allows {attempts} attempts and then moves the job to {queue}. No retry delay was specified.',
           f'La file de tâches de {project} relance les erreurs transitoires, mais la politique autorise {attempts} tentatives puis déplace la tâche vers {queue}. Aucun délai de relance n’a été fixé.',
           f'After {attempts} attempts, move a failed job to queue {queue}.',
           f'Après {attempts} tentatives, déplacer une tâche en échec vers la file {queue}.',
           f'{project} allows {attempts} attempts for a failing job before moving it to dead-letter queue {queue}.',
           f'{project} autorise {attempts} tentatives pour une tâche en échec avant de la déplacer vers la file de rejet {queue}.'),
          ('d3', 'fact',
           f'{project} keeps experiment failure receipts for {days} days to retain audit evidence. The original files must not be overwritten. No encryption algorithm was specified.',
           f'{project} conserve les reçus d’échec des expériences pendant {days} jours comme preuves d’audit. Les fichiers d’origine ne doivent pas être écrasés. Aucun algorithme de chiffrement n’a été fixé.',
           f'Retain failure receipts for {days} days and never overwrite their original files.',
           f'Conserver les reçus d’échec {days} jours et ne jamais écraser leurs fichiers d’origine.',
           f'{project} retains experiment failure receipts for {days} days as audit evidence, without overwriting the original files.',
           f'{project} conserve les reçus d’échec des expériences {days} jours comme preuves d’audit, sans écraser les fichiers d’origine.')]
        for j, (topic, kind, src_en, src_fr, base_en, base_fr, qual_en, qual_fr) in enumerate(facts):
            for language, source, baseline, qualified in [('en', src_en, base_en, qual_en), ('fr', src_fr, base_fr, qual_fr)]:
                if (i + j) % 4 == 0:
                    baseline = qualified
                rows.append(dict(id=f'{i:02}-{topic}-{language}', family=f'{i:02}-{topic}', project_group=f'{i:02}',
                    project=project, person=person, stack=stack, platform=platform, topic=topic, kind=kind,
                    language=language, split='dev' if i % 3 == 0 else 'heldout', source=source,
                    original=baseline, qualified=qualified, full=source + '\n' + baseline))
    return rows
