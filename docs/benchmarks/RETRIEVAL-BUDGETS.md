# Retrieval personnel : budgets de reranking et filtre de version

## Résultat exécuté

**Usage visé : connaissances personnelles et workflows d’agents.** Ce travail ne traite ni de qualification bancaire ni d’ingestion privée. Aucun réglage de production n’est activé.

Run final : [`artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/measured-v2/`](../../artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/measured-v2/).

- **1 024 requêtes réellement exécutées** : 32 questions × 8 variantes × 4 blocs. Modèles ONNX MiniLM et mMARCO résidents, serveur Qdrant natif 1.19.2, aucune installation ni nouveau téléchargement.
- Baseline appariée **OR-RRF reproduite sur 32/32 questions**, pools20 historiques identiques pour chaque requête et chaque variante ; empreintes de tous les vecteurs-query identiques au run `c43fdc89538747999b78e90236bd3c2e/measured-v3`.
- Le filtre Python appliqué avant reranking **et revérifié à la présentation** élimine toutes les versions Python connues différentes et tous les UNKNOWN interdits par une demande explicite de version. **Zéro violation** dans les candidats rerankés ou présentés des variantes filtrées.
- Sur les 12 répondables du holdout historique réutilisé, le reranking filtré à 5 améliore P@1 sélectionné de **0,5000 à 0,6667**, mais pas recall5 (**0,6667**). Budget10 : recall5 **0,7917** ; budget20 : **0,9167**. Le P@1 reste **0,6667**, pas 90 % de précision.
- Coût E2E résident médian sur les 64 requêtes chronométrées de cette partition : **4,884 ms sans reranking**, **190,136 ms à 5**, **425,931 ms à 10**, **817,282 ms à 20**.
- Limites décisives : le budget20 filtré conserve **deux incompatibilités explicites**, toutes deux sur la question Qdrant de négation ; **4/4 questions sans réponse** reçoivent encore des candidats dans chaque partition. Le filtre de version ne résout ni l’absence de preuve ni la négation.

**Pas d’acceptation ≥90 %.** Ces questions ont déjà été observées ; les labels de pertinence sont incomplets et les autres passages restent UNKNOWN. Les répétitions chronométriques ne créent pas de nouveaux exemples de qualité. Aucun score cosine, RRF ou logit n’est présenté comme une probabilité calibrée.

## Livrable principal : précision et preuves par question

La revue exhaustive contient les **32 questions exactes**, les huit classements top5 ordonnés, extraits, sources épinglées, offsets, hashes, P@1/P@3/P@5 sélectionnés, rappel, rang réciproque, incompatibilités et UNKNOWN. Chaque variante montre aussi ses quatre coûts E2E réels.

| Preuve | Contenu |
|---|---|
| [`measured-v2/PER-QUERY-REVIEW.md`](../../artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/measured-v2/PER-QUERY-REVIEW.md) | Revue principale ; extraits de 500 caractères, source et rang de chaque résultat |
| `measured-v2/raw-results.json` | 1 024 lignes : passages complets originaux, citations brutes, labels, états de version, candidats, logits, réponses Qdrant et timings |
| `measured-v2/per-query-differences.json` | Changements de rangs/résultats, positifs perdus/retrouvés, différences de précision et quatre latences par question/variante |
| `paired-cost-differences.json` | 1 024 deltas E2E réellement appariés à OR-RRF dans le même bloc, pas différence de deux médianes |
| `incumbent-and-compatibility.json` | Comparaison par question avec la baseline AND historique, positifs gagnés/perdus et nouvelles incompatibilités ; aucune comparaison de ses anciens timings attribués avec l’E2E actuel |
| `measured-v2/report.json` | 16 agrégats, étapes, quatre médianes par bloc, ressources, parité et nettoyage |
| `measured-v2/freeze.json` | Matrice, politique UNKNOWN, budgets et 48 empreintes d’entrées enregistrées avant toute inférence |
| `measured-v2/collection-readback.json`, `server-readback.json` | Collection verte, 136 vecteurs indexés, vecteurs et payloads réellement relus après écriture |
| `measured-v2/evidence-sha256.json` | 58 fichiers du run hashés et revérifiés |
| `verify.py`, `verification.json` | Vérification indépendante de 1 024 lignes et 5 120 citations ; recompte métriques, provenance, filtre, hashes et nettoyage |

Les fichiers sans préfixe `measured-v2/` ci-dessus se trouvent dans la racine unique `artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/`.

## Protocole gelé, sans sélection rétrospective

1. **Corpus et unités inchangés** : 136 passages des dix sources publiques du snapshot `artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/`. Texte, frontières, offsets et hashes vérifiés ; aucun nouveau découpage, enrichissement de titre ou contenu personnel.
2. **Questions inchangées** : 12 répondables et quatre sans réponse dans chacune des partitions historiques `development` et `holdout`. Les deux sont **REUSED DIAGNOSTIC**, pas des partitions indépendantes de validation. Aucun nouveau label après observation.
3. **Baseline choisie explicitement : OR-RRF**, pas le AND historique. Dense MiniLM original top60, FTS5 BM25 OR des mêmes tokens techniques top20, fusion RRF constante60 à poids égaux. Même pool20 **avant toute intervention**, vérifié contre le précédent run. La comparaison au AND reste une lecture de compatibilité séparée et ne change pas la baseline causale.
4. **Matrice finie** : `ungated_none`, `gated_none`, puis paires `ungated_5/gated_5`, `ungated_10/gated_10`, `ungated_20/gated_20`. Les contrôles non filtrés sont volontairement observationnels, pas une chaîne recommandée.
5. **Budgets** : filtrer le pool20 d’origine, prendre les premiers 5/10/20 admissibles, reranker uniquement ceux-ci puis présenter top5. Aucun refill extérieur au pool20, aucune réintroduction de sa queue. `none` garde l’ordre des membres admissibles du pool20 sans reranking. Budget5 ne peut donc améliorer le rappel d’un top5 non filtré, seulement son ordre.
6. **Modèles existants strictement conservés** : MiniLM quantifié384 dimensions, max128 et recette historique ; mMARCO `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, révision `1427fd652930e4ba29e8149678df786c240d8825`, ONNX AVX2 SHA-256 `6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b`. CPU, intra/inter2/1, batches reranker4, longest-first512, logits bruts. Un seul chargement de chaque session dans le run.
7. **Qdrant serveur réel** : binaire1.19.2 identique au freeze historique, collection dédiée cosine384, shard1, M16, ef_construct100, full_scan_threshold10 KB, indexing_threshold1 KB, ANN ef128. Collection verte et 136 vecteurs indexés avant mesure ; sur ce petit corpus le moteur peut choisir un scan, pas de prétention à un passage HNSW systématique.
8. **Quatre blocs complets** : ordre des questions et des variantes inversé dans les blocs impairs, sessions inchangées. Tout est réexécuté à chaque requête, y compris encodage, lexical, appel HTTP, métadonnées, filtres, reranking et citations. Ni timings de composants partagés ni cache de résultats.
9. **Abstention : aucune**, choix gelé avant inférence. L’expérience optionnelle de règle calibrée sur développement n’a pas été réalisée. Un retour non vide sur une question sans réponse compte comme fausse acceptation de candidats, pas comme mesure d’une réponse générée.

### Versions et UNKNOWN

Seules les URLs CPython épinglées `.../python/cpython/v3.11.9/Doc/...` et `v3.12.3` fournissent une version explicite. Aucune pertinence, phrase du passage, question, date de capture ou révision documentaire Qdrant ne devient une déclaration de compatibilité.

- Demande contenant explicitement `Python 3.11`, `Python 3.12` ou un patch : même famille demandée → `MATCH_EXPLICIT_FAMILY` ; version connue différente → `REJECT_VERSION` ; version/produit non établi → `REJECT_UNKNOWN`.
- Autres questions : `NOT_ASSESSED`, **pas « compatible »**. Les métadonnées inconnues peuvent alors être affichées, explicitement inconnues ; aucune certification générique d’applicabilité.
- Filtre avant sélection du budget et reranking ; deuxième calcul depuis les sources brutes à la présentation. Le test injecte directement versions différentes et UNKNOWN dans cette seconde frontière pour vérifier leur rejet.
- Compatibilité inter-versions et disponibilité de chaque API : **UNKNOWN**. Le filtre ne remplace pas une vérification de ces propriétés.
- Citations inchangées : URL publique originale, hash des octets source, texte original intégral, offsets et hash du passage. Aucun préfixe/version réécrit dans la preuve.

## Qualité observée

P@k = positifs sélectionnés aux k premières places / k ; cases manquantes = zéro. Moyennes sur **12 répondables uniques** par partition. UNKNOWN n’est pas déclaré faux ; ces valeurs ne mesurent pas une précision sémantique exhaustive. MRR est un rang réciproque moyen, pas un taux de vérité. R5 est le rappel macro des preuves sélectionnées, pas la précision.

### Holdout historique réutilisé

| Variante | P1 / P3 / P5 | MRR / R5 | Incompatibles explicites top5 | Versions connues différentes top5 | Preuves admissibles manquées |
|---|---|---|---:|---:|---:|
| ungated_none | 0,5000 / 0,2222 / 0,1500 | 0,5444 / 0,6667 | 2 | 3 | 5 |
| gated_none | 0,5000 / 0,2222 / 0,1500 | 0,5444 / 0,6667 | 1 | 0 | 5 |
| ungated_5 | 0,6667 / 0,2222 / 0,1500 | 0,6667 / 0,6667 | 2 | 3 | 5 |
| gated_5 | 0,6667 / 0,2500 / 0,1500 | 0,6667 / 0,6667 | 1 | 0 | 5 |
| ungated_10 | 0,6667 / 0,2778 / 0,1833 | 0,7361 / 0,7917 | 5 | 4 | 3 |
| gated_10 | 0,6667 / 0,2778 / 0,1833 | 0,7361 / 0,7917 | 2 | 0 | 3 |
| ungated_20 | 0,6667 / 0,3056 / 0,2167 | 0,7500 / 0,9167 | 5 | 4 | 1 |
| gated_20 | 0,6667 / 0,3056 / 0,2167 | 0,7500 / 0,9167 | 2 | 0 | 1 |

### Développement historique réutilisé

| Variante | P1 / P3 / P5 | MRR / R5 | Incompatibles explicites top5 | Versions connues différentes top5 |
|---|---|---|---:|---:|
| ungated_none | 0,5833 / 0,2778 / 0,1667 | 0,6528 / 0,7500 | 2 | 1 |
| gated_none | 0,5833 / 0,2778 / 0,1667 | 0,6528 / 0,7500 | 1 | 0 |
| ungated_5 | 0,6667 / 0,2500 / 0,1667 | 0,6875 / 0,7500 | 2 | 1 |
| gated_5 | 0,6667 / 0,2500 / 0,1667 | 0,6875 / 0,7500 | 1 | 0 |
| ungated_10 | 0,6667 / 0,2778 / 0,1667 | 0,7083 / 0,7500 | 2 | 1 |
| gated_10 | 0,6667 / 0,2778 / 0,1667 | 0,7083 / 0,7500 | 1 | 0 |
| ungated_20 | 0,6667 / 0,2778 / 0,1667 | 0,7083 / 0,7500 | 2 | 1 |
| gated_20 | 0,6667 / 0,2778 / 0,1667 | 0,7083 / 0,7500 | 1 | 0 |

Dans toutes les variantes : **12/12 répondables non vides** et **4/4 sans-réponse non vides** par partition. Non-vide n’est pas une réponse soutenue. Les variantes filtrées conservent69 UNKNOWN top5 en développement ; sur holdout70 sans reranking/à5,67 à10 et65 à20, sur80 passages présentés par variante. Pas de correction de ces labels après observation.

### Où les preuves sont perdues

« Admissible » ci-dessous signifie **non rejeté par ce filtre étroit**, donc inclut NOT_ASSESSED ; ce n’est pas une compatibilité certifiée. Les comptes portent uniquement sur les preuves positivement sélectionnées, pas sur toutes les preuves possibles.

| Variante filtrée | Dev : absentes pool / perdues budget / hors top5 | Holdout : absentes pool / perdues budget / hors top5 |
|---|---|---|
| none | 2 / 0 / 1 | 1 / 0 / 4 |
| 5 | 2 / 1 / 0 | 1 / 4 / 0 |
| 10 | 2 / 0 / 1 | 1 / 2 / 0 |
| 20 | 2 / 0 / 1 | 1 / 0 / 0 |

Dénominateurs :13 preuves sélectionnées non rejetées en développement,14 en holdout. Les preuves rejetées, absentes du pool20, perdues au budget et perdues à la présentation sont listées **par ID pour chaque question** dans `proof_audit`. Aucun positif sélectionné n’est perdu au filtre dans ce run ; le gain de budget ne peut récupérer la preuve absente du pool.

### Exemples discriminants, sans relabelisation

- **holdout-00**, « Pourquoi deux rédacteurs SQLite WAL ne peuvent-ils pas écrire simultanément ? » : `wal-writer` n’entre au top5 qu’à20, au rang3 ; les deux premières preuves sont encore UNKNOWN. Le petit budget ne suffit pas à ce cas.
- **holdout-02**, sauvegarde cohérente : OR sans reranking et budget5 ne retrouvent aucun positif sélectionné ; budget10 retrouve `backup-snapshot` au rang2 ; budget20 retrouve `backup-snapshot` au rang3 et `py311-backup` au rang5. La première preuve présentée reste UNKNOWN.
- **holdout-05**, sauvegarde pendant accès concurrents : `py311-backup` passe du rang3 au rang1 dès budget5 ; payer20 n’ajoute ici aucun positif.
- **holdout-07**, protection asyncio contre annulation : `async-shield` passe du rang5 au rang1 dès budget5.
- **holdout-04 / holdout-11**, Python3.11/3.12 : zéro source de mauvaise famille après filtre ; positifs conservés. À20, filtré conserve les deux preuves3.12 de holdout-11 alors que le contrôle non filtré a encore des preuves3.11 inapplicables.
- **holdout-08**, `should` : budget10 suffit pour `qfilter-should` au rang3 ; budget20 ne le promeut pas au rang1.
- **holdout-09**, négation : `qfilter-must_not` est absent du pool20 ; le reranker à10/20 place `qfilter-must` au rang1 et `qfilter-should` au rang3, tous deux explicitement incompatibles. Le gate Python ne s’applique pas. **Le coût supplémentaire ne rend pas ce résultat acceptable.**
- Les quatre sans-réponse demandent une mesure locale, un propriétaire de fichier, Raft natif SQLite ou un mot de passe perdu. Aucun classement de documentation publique ne justifie de leur fabriquer une réponse.

## Coût E2E réel et compromis

Ces latences sont **des requêtes entières indépendamment exécutées**, contrairement aux sommes attribuées du précédent rapport. Les valeurs de qualité utilisent les questions uniques ; les percentiles de temps portent sur **64 requêtes par variante/partition**, les mêmes16 questions répétées quatre fois.

| Variante, holdout | E2E p50 / p95, ms | Rerank p50, ms |
|---|---:|---:|
| ungated_none | 4,947 / 10,313 | 0,000 |
| gated_none | 4,884 / 10,861 | 0,000 |
| ungated_5 | 192,746 / 396,611 | 186,374 |
| gated_5 | 190,136 / 401,935 | 183,837 |
| ungated_10 | 432,899 / 749,035 | 427,330 |
| gated_10 | 425,931 / 828,001 | 420,261 |
| ungated_20 | 849,958 / 1 523,550 | 844,790 |
| gated_20 | 817,282 / 1 444,006 | 812,221 |

Médianes des **deltas appariés** au contrôle OR sans filtre, même question/même bloc : gated_none−0,251 ms ; gated5+182,921 ms ; gated10+418,547 ms ; gated20+810,110 ms. Ne pas interpréter la petite différence sans reranking comme un gain significatif du filtre.

Pour gated20 holdout, étapes médianes : encodage3,058 ms ; lexical0,148 ms ; HTTP Qdrant0,861 ms ; résolution/fusion/métadonnées/filtre0,381 ms ; rerank812,221 ms ; contrôle final0,368 ms ; citation/sérialisation0,174 ms. **La somme des médianes n’est pas la médiane E2E.** La chronométrie E2E commence avant encodage et finit après sérialisation des citations ; export disque et hashing d’évidence sont exclus, contrairement au calcul des preuves et des métadonnées qui est inclus.

Chargement et validation des hashes séparés : MiniLM568,108 ms ; reranker648,158 ms. Warm-up complet744,407 ms, hors mesures. Les vecteurs documentaires originaux sont réutilisés du run épinglé ; on ne revendique pas de nouvel encodage offline. La troncature MiniLM historique reste une limite du corpus. Le reranker atteint512 tokens sur313 paires, warm-up inclus ; pas de lecture exhaustive garantie des passages longs.

Le filtre réduit réellement les paires sur certaines questions Python : gated20 traite9 ou20 paires en développement,10/11/20 en holdout ; budget10 peut n’en traiter que9 en développement. Aucun remplissage ne masque cette réduction.

**Variabilité visible** : médianes gated20 holdout par bloc1 161,379 / 767,849 / 742,595 / 749,266 ms ; gated5 306,978 / 186,155 / 184,053 / 185,158 ms. L’alternance réduit un biais d’ordre évident mais n’annule pas contention, fréquence CPU, longueur des candidats et échauffement. Ni SLA, ni test de significativité, ni comparaison moteur isolée.

Environnement mesuré : Python3.11.16 de la `.venv` existante, NumPy2.4.6, ONNX Runtime1.31.0,24 cœurs physiques/logiques déclarés,51 132 588 032 octets RAM. Mesure résidente409,931 s ; CPU harness1 110,3125 s, serveur0,890625 s ; pics RSS échantillonnés1 263 976 448 et38 785 024 octets. Ces ressources comprennent le logging en mémoire et l’échantillonnage, pas seulement un modèle.

**Lecture pratique pour l’agent personnel** : garder le filtre explicite ; budget5 peut améliorer le premier résultat à coût inférieur, mais manque quatre preuves présentes dans le pool holdout. Budget10 réduit cette perte à deux. Budget20 retrouve ces deux preuves supplémentaires au prix du coût observé, sans améliorer P@1 au-delà de2/3 et sans résoudre le faux opérateur. Aucun budget n’est activé automatiquement.

## TDD, exécution et vérification

Trois tranches RED→GREEN observées : frontière de version/source et présentation ; partition explicite des preuves manquées ; expérience résidente réelle. Les logs `red-gate.txt`, `green-gate.txt`, `red-proof.txt`, `green-proof.txt`, `red-experiment.txt` et `green-integration-v2.txt` sont conservés.

- **3/3 tests nouveaux PASS,417,763 s**, intégration réelle complète incluse, `ResourceWarning` en erreur.
- Régression ciblée retrieval/extraction : **31 tests,26 PASS et5 SKIP,12,726 s**. Le skip du nouveau run réel dans ce second passage ne remplace pas son acceptation exécutée ci-dessus. Inclut aussi un serveur réel existant avec stockage unique `artifacts/server-benchmark/decf7e35a3c6470383aef11beac31332/`, nettoyage vérifié. Suite doc-intelligence hors sujet non exécutée ; aucune revendication de suite globale verte.
- Vérificateur indépendant :58 hashes du run,48 entrées d’exécution,1 024 lignes,5 120 citations. Parité de classement entre les quatre blocs pour toutes les variantes.
- Serveur principal PID5688, port52209 : seul Popen possédé arrêté, PID absent et port fermé vérifiés après relecture de `cleanup.json`. Retour1 = `terminate` forcé Windows, pas preuve d’arrêt gracieux ou de durabilité.
- Première tentative `measured/` interrompue par la limite dure420 s de l’outil foreground : trois blocs incomplets conservés **et exclus** des résultats. Aucun Qdrant encore actif, ancien port49604 fermé vérifié dans `measured/interruption-cleanup.json`. Nouveau run complet `measured-v2/` lancé en processus background suivi puis attendu jusqu’à exit0 ; aucun mélange des deux essais.
- Premier shell : `rtk --version` →0.48.0. Beads : seule tâche possédée `bk-hah` suivie, sans init/install/configuration globale.
- Aucun symbole ni fichier incumbent édité ici ; seuls `tools/retrieval_budget_benchmark.py`, `tests/retrieval_budget_benchmark_test.py`, ce document et artefacts uniques sont créés. Index Git inchangé, pas de staging/commit/push. Inventaire :59 412 fichiers incumbents inchangés ; `docs/benchmarks/PERSONAL-AGENT-READINESS.md` a changé hors de cette tâche pendant le run et n’a pas été touché ici. Toutes les48 entrées d’exécution restent strictement identiques.
- `.venv` utilisée en lecture/exécution seulement avec `-B` / `PYTHONDONTWRITEBYTECODE=1` ; aucun package installé, aucun vault ni contenu personnel ingéré.

Hashes finaux :

- `measured-v2/report.json` : `4d954b68eaa0dfad1b92e8882581fb9dfd17b1d273c124bc72de7edf90fd376b`.
- `measured-v2/freeze.json` : `74c3129a3d91d9c41f9db42ad76a17985c705da6a531cbc96e2975c086e53008`.

### Reproduire

Depuis `D:/Projets/BorgKnowledge`, sans modifier l’environnement :

```bash
# Tests légers ; le run réel est opt-in et ne télécharge rien.
PYTHONDONTWRITEBYTECODE=1 rtk proxy .venv/Scripts/python.exe -B \
  -m unittest discover -s tests -p retrieval_budget_benchmark_test.py -v

# Nouveau run UUID automatique, à lancer comme job suivi si l’outil a une limite foreground.
PYTHONDONTWRITEBYTECODE=1 rtk proxy .venv/Scripts/python.exe -B tools/retrieval_budget_benchmark.py

# Intégration réelle : choisir obligatoirement un NOUVEAU chemin.
PYTHONDONTWRITEBYTECODE=1 BUDGET_REAL_RUN='D:/Projets/BorgKnowledge/artifacts/retrieval-budgets/NEW-UNIQUE-RUN' \
  rtk proxy .venv/Scripts/python.exe -B -W error::ResourceWarning \
  -m unittest discover -s tests -p retrieval_budget_benchmark_test.py -v

# Relecture indépendante du run livré, sans inférence ni téléchargement.
rtk proxy .venv/Scripts/python.exe -B \
  artifacts/retrieval-budgets/90afd10bbff64c1dae95729d5a745133/verify.py
```

Les deux modèles, le binaire serveur, le snapshot et le précédent run épinglé doivent déjà exister. La réutilisation de ces questions reste diagnostique même après un replay. Pour conclure sur la précision d’un agent personnel réel, il manque encore des jugements neufs/exhaustifs, une évaluation d’abstention et le branchement opérationnel aux actions search/get, mises à jour et suppressions ; ce benchmark ne les prétend pas réalisés.
