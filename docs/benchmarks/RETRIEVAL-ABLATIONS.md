# Retrieval : ablations isolées sur serveur Qdrant

**17 octobre 2026 — pilote public exécuté, pas qualification bancaire.**

## Décision exécutive

La baseline est reproduite : mêmes vecteurs MiniLM et mêmes cinq premiers passages sur **32/32 requêtes** que le précédent benchmark apparié. Les nouveaux essais produisent **704 lignes de résultats** : 32 requêtes × 11 variantes × 2 modes Qdrant. Aucun backend, modèle de production ou réglage global n'est activé.

Trois conclusions distinctes :

1. **Le préfixe déterministe testé dégrade le diagnostic.** Avec le contexte titre/source/version, le MRR du holdout réutilisé passe de 0,6111 à 0,3611 et recall5 de 0,7083 à 0,3750. Le préfixe consomme le budget de 128 tokens ; ce résultat ne condamne ni les métadonnées ni le late chunking.
2. **Un lexical OR BM25 est plus utile que le AND historique, mais la fusion n'est pas une amélioration universelle.** Le AND est vide sur 28/32 requêtes ; le OR sur 0/32. La fusion OR améliore le développement mais dégrade le MRR du holdout réutilisé à 0,5444.
3. **Le cross-encoder multilingue est un challenger mesuré, pas une solution qualifiée.** À pool identique de 20 passages, MRR 0,5444→0,7500 et recall5 0,6667→0,9167 sur les 12 répondables du holdout réutilisé. Cependant P@1 n'est que 0,6667, les incompatibilités explicitement annotées au top5 augmentent de 2 à 5, et le reranking coûte environ 0,897 seconde médiane pour 20 paires sur ce CPU. **0,9167 de rappel n'est pas 91,67 % de précision.**

Toutes les variantes denses/hybrides retournent encore des candidats pour les **4/4 questions sans réponse de chaque partition**. Ce n'est pas un système d'abstention. Aucun résultat ne justifie une revendication de précision ≥ 90 %, une qualification LAD/RAD/GED, ou une mise en service dans un groupe bancaire.

## Dossier livré et preuves primaires

Racine de l'expérience :

`artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/`

Run final faisant foi : [`measured-v3/`](../../artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3/).

| Fichier | Fonction |
|---|---|
| `measured-v3/freeze.json` | Variantes, budgets, politiques, modèle et empreintes des entrées sauvegardés avant l'inférence |
| `measured-v3/report.json` | 44 agrégats variant/mode/partition, environnement, ressources, parité et nettoyage |
| `measured-v3/raw-results.json` | 704 lignes, question exacte, top5, métriques, labels, passages complets, provenance, pool20, logits, admissibilité, timings |
| `measured-v3/raw-server-rankings.json` | Réponses HTTP Qdrant, candidats dense/lexical, empreinte du vecteur-query |
| `measured-v3/per-query.csv` | Export tabulaire des mêmes lignes ; recall5/MRR sont aussi dans la colonne JSON `metrics` |
| `measured-v3/PER-QUERY-REVIEW.md` | Revue exhaustive des top5 avec extraits de 500 caractères ; texte intégral dans le JSON/CSV |
| `QUERY-DELTA-REVIEW.md` | Revue compacte des 32 questions : baseline / OR-RRF / même pool reranké |
| `derived-diagnostics.json` | Rappel du pool20 et erreurs de version connues, distinctes des labels d'incompatibilité |
| `measured-v3/*-readback.json` | Vecteurs et payloads relus sur les collections réellement écrites |
| `measured-v3/*-vectors.npy`, `query-vectors.npy` | Vecteurs réellement utilisés |
| `measured-v3/evidence-sha256.json` | Empreintes de 101 fichiers du run ; vérifiées après relecture |
| `verify.py`, `verification.json` | Vérification indépendante de l'arithmétique/provenance/intégrité ; pas annotation indépendante |
| `reranker-model/receipt.json`, `README.md` | Téléchargements publics épinglés, tailles, SHA-256, déclaration de licence |
| `provision-reranker.py`, `provision-replay/` | Rejeu du téléchargement borné, réellement exercé avec contrôle des hashes attendus |
| `green-integration-v3.txt` | Sept tests exécutés, y compris modèle réel et serveur réel |
| `full-python-tests-final.txt` | Régression élargie et échecs hors périmètre explicités ci-dessous |

Empreintes principales :

- Rapport final : `89bdf240005d6cdd517bd6947f0c9835996a7278ed3328565cde72d508f9c702`.
- Freeze final : `7368b2e768467cf9cce03880cfd71e2d35037bb23b864d8985dcb3919ba6ece0`.
- Harness : `3bc49e33958a7002c579fb50959ec289588d8c0ab5b609e445c9397abca8d5ff`.
- Tests : `3b1c007231858389f2b4de3be641a0b101ae961df92ef1b727116363ce7914d3`.

## Protocole gelé : ce qui change, ce qui ne change pas

Références lues : [revue académique thématique](../research/ACADEMIC-RETRIEVAL-BY-THEME.md), `tools/qdrant_quality.py`, `tools/technical_quality.py`, `tools/server_benchmark.py`, règles du dépôt. Le nouveau harness importe ces helpers **sans les modifier** ; aucune analyse de graphe préalable à une modification de symbole existant n'était donc nécessaire.

- Corpus conservé : 136 passages de 10 sources publiques ; 24 emplacements de preuves sélectionnées et 112 fenêtres de contexte non exhaustivement jugées. Offsets, texte et hashes des passages sont inchangés.
- Snapshot : `artifacts/technical-quality/d6b5dd7fa9a54145a94d7abcf80d6b92/`. Les empreintes du freeze historique sont revérifiées ; aucun téléchargement documentaire nouveau, aucun document bancaire, privé ou de vault n'est ingéré.
- 32 questions anciennes : 12 répondables + 4 sans réponse par partition. Les noms `development` et `holdout` sont historiques. **Les deux partitions sont REUSED DIAGNOSTIC, non indépendantes.** Pas d'annotation nouvelle après observation, pas de sélection de gagnant statistique.
- Même bi-encodeur multilingue MiniLM quantifié ONNX, dimension 384, mean pooling masqué puis L2, max128, préfixes query/passage vides, CPU, threads intra/inter 2/1, batches documentaires de 8.
- Collections distinctes `original` et `context`, mêmes 136 unités jugées. Pas de nouveau découpage, expansion parentale, résumé généré, traduction, HyDE ou changement de modèle d'embedding.
- Budget dense60, lexical20, top5 présenté, pool de reranking20. Les scores cosine sont triés décroissants avec égalité par ID ; RRF de rang1, constante60, poids égaux. Aucun budget supplémentaire obtenu par multiquery ou retry mesuré.
- Qdrant 1.19.2 **serveur natif réel**, cosine, shard1, HNSW M16/ef_construct100, seuil full scan10 KB, indexation1 KB ; requêtes exactes et ANN ef128 séparées. Toutes les collections sont vertes et indexent leurs 136 vecteurs avant interrogation. Le serveur peut choisir un scan exact pour une petite collection : on ne prétend pas que chaque appel ANN traverse HNSW.
- Vecteurs-query calculés une fois et réutilisés entre variantes/modes. Parité exacte NumPy des vecteurs originaux et queries avec le run historique `artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/`.
- Les top5 exact/ANN sont égaux pour les 352 couples question/variante. Ce constat n'est ni une précision de réponse ni un test ANN à grande échelle.

### Matrice d'attribution

| Variante | Comparateur causal | Seule intervention revendiquée |
|---|---|---|
| `dense` | témoin | Dense MiniLM original seul |
| `baseline_and_rrf` | baseline historique | Dense original + FTS5 AND historique |
| `context_dense` | `dense` | Préfixe déterministe documentaire avant embedding |
| `context_and_rrf` | `baseline_and_rrf` | Même préfixe, lexical historique inchangé |
| `lexical_and` | témoin lexical historique | FTS5 AND seul |
| `lexical_or` | `lexical_and` | Termes littéraux OR, classement BM25 utile |
| `or_rrf` | `baseline_and_rrf` | Remplacement de la seule branche lexicale |
| `version_gate_baseline` | `baseline_and_rrf` | Filtre de famille Python explicite sur les deux branches avant fusion |
| `version_gate_or_rrf` | `or_rrf` | Même filtre, autres facteurs constants |
| `rerank_control_pool20` | `or_rrf` | Pool20 tronqué, ordre inchangé ; contrôle apparié |
| `rerank_pool20` | `rerank_control_pool20` | Cross-encoder sur exactement les mêmes 20 preuves |

La dernière variante est **volontairement non filtrée**, pour isoler le classement ; ce n'est pas une chaîne bancaire recommandée. Nous ne fabriquons pas un « meilleur système » en combinant rétroactivement contexte, filtre et reranker.

### Titres, versions, inconnus et compatibilité

Le préfixe final est `Title`, `Source`, `Version`, `Revision`, puis le passage original. Les titres proviennent uniformément des sources : champ YAML Qdrant, titre RST CPython, titre SQLite avant le marqueur de navigation. Leurs offsets et le hash du texte normalisé sont conservés. Aucun titre ne provient d'un label, d'un ID ou d'une génération.

- CPython : `v3.11.9` et `v3.12.3` dans les URLs publiques épinglées donnent **uniquement ces versions explicites**.
- Qdrant : le commit documentaire `3d4e1897a2ca017999ad3d77b1ade6f7530ca1ed` est une **révision documentaire**, pas une version de produit ni une matrice de compatibilité. Version = `UNKNOWN`.
- Pages SQLite : version = `UNKNOWN`, malgré le hash et la date de capture. Une date de capture n'est pas une date d'effet.
- Compatibilité inter-versions = `UNKNOWN` partout. Le pilote ne déduit pas « API compatible » d'un numéro plus récent.
- Le filtre ne traite que les questions contenant explicitement `Python 3.11`, `Python 3.12` ou un numéro patch. Il compare la famille demandée à l'étiquette du snapshot, pas à la disponibilité de chaque API. Source connue différente : `REJECT_VERSION` ; source inconnue : `REJECT_UNKNOWN`, **jamais wildcard silencieux** ; question sans cette demande : `NOT_ASSESSED`, pas « compatible ».
- Le filtrage précède la fusion de chaque branche et ne refait pas le plein de candidats. Il ne constitue pas un filtre générique produit/entité/juridiction/ACL et ne certifie pas les autres passages `UNKNOWN`.

L'essai `measured-v2/` est conservé mais **supplanté**, pas mélangé aux conclusions finales : la revue de protocole y a détecté un ancrage sélectionné utilisé comme titre, absent des fenêtres non jugées. Le test de non-contamination a été écrit et observé RED, puis extraction source uniforme et run v3 neuf. Ce correctif de métadonnées n'a pas été choisi pour maximiser un score. `measured/` correspond au premier échec avant inférence (absence d'ancre sur les fenêtres). Aucune de ces itérations ne rétablit une indépendance du jeu ancien.

## Résultats par partition — ANN ef128

P@k = nombre de positifs sélectionnés parmi les k premières places / k ; slots absents = zéro. Moyenne sur les **12 questions répondables** de chaque partition. Les passages non annotés restent `UNKNOWN`, pas faux. Ces P@k sont des diagnostics de labels sélectionnés, pas une précision sémantique exhaustive. MRR = moyenne du rang réciproque du premier positif au top5 ; recall5 = moyenne du rappel des positifs par question, pas micro-rappel. Sur les questions sans réponse, MRR/recall sont nuls au sens « non applicables » (`null`), et non des succès automatiques.

| Variante | Dev P1 / P3 / P5 | Dev MRR / R5 | Holdout réutilisé P1 / P3 / P5 | Holdout MRR / R5 | Incompatibles explicites top5, dev / holdout |
|---|---|---|---|---|---|
| dense | 0,5000 / 0,2222 / 0,1333 | 0,5278 / 0,5833 | 0,4167 / 0,2778 / 0,1667 | 0,5694 / 0,7083 | 1 / 1 |
| baseline_and_rrf | 0,5833 / 0,2222 / 0,1333 | 0,5833 / 0,5833 | 0,5000 / 0,2778 / 0,1667 | 0,6111 / 0,7083 | 1 / 1 |
| context_dense | 0,2500 / 0,2222 / 0,1333 | 0,4444 / 0,6250 | 0,2500 / 0,1389 / 0,0833 | 0,3056 / 0,3750 | 1 / 1 |
| context_and_rrf | 0,3333 / 0,2222 / 0,1333 | 0,4861 / 0,6250 | 0,3333 / 0,1389 / 0,0833 | 0,3611 / 0,3750 | 1 / 1 |
| lexical_and | 0,1667 / 0,0556 / 0,0333 | 0,1667 / 0,1250 | 0,0833 / 0,0278 / 0,0167 | 0,0833 / 0,0417 | 0 / 0 |
| lexical_or | 0,3333 / 0,2500 / 0,1667 | 0,5167 / 0,7500 | 0,5000 / 0,2222 / 0,1333 | 0,5417 / 0,5833 | 1 / 4 |
| or_rrf | 0,5833 / 0,2778 / 0,1667 | 0,6528 / 0,7500 | 0,5000 / 0,2222 / 0,1500 | 0,5444 / 0,6667 | 2 / 2 |
| version_gate_baseline | 0,5833 / 0,2222 / 0,1333 | 0,5833 / 0,5833 | 0,5000 / 0,2778 / 0,1667 | 0,6111 / 0,7083 | 0 / 0 |
| version_gate_or_rrf | 0,5833 / 0,2778 / 0,1667 | 0,6528 / 0,7500 | 0,5000 / 0,2222 / 0,1500 | 0,5444 / 0,6667 | 1 / 1 |
| rerank_control_pool20 | 0,5833 / 0,2778 / 0,1667 | 0,6528 / 0,7500 | 0,5000 / 0,2222 / 0,1500 | 0,5444 / 0,6667 | 2 / 2 |
| rerank_pool20 | 0,6667 / 0,2778 / 0,1667 | 0,7083 / 0,7500 | 0,6667 / 0,3056 / 0,2167 | 0,7500 / 0,9167 | 2 / 5 |

**Sans réponse :** 4/4 candidats retournés par partition pour toutes les variantes sauf `lexical_and` (0/4). Le AND ne constitue pas une bonne abstention : il ne retourne des candidats que pour 2/12 questions répondables de chaque partition. Pas de génération de réponse évaluée.

**Deux axes d'erreur différents :** les labels explicites d'incompatibilité sont incomplets. Sur le holdout, la baseline retourne aussi 4 passages de version Python connue différente au top5 des questions de version, contre 0 après filtre. OR-RRF en retourne 3, contre 0 filtré. Les fenêtres non sélectionnées conservent leur label de pertinence `UNKNOWN` même si leur version est connue ; on ne les relabelise pas faux après coup. Le filtre ne supprime pas l'erreur logique `must`/`should`/`must_not` : OR-RRF filtré conserve une incompatibilité explicite.

### Revue des erreurs et des gains, sans relabelisation

Les 32 questions exactes et tous leurs extraits se trouvent dans les revues liées plus haut. Exemples discriminants :

| Question historique | Observation vérifiée | Lecture prudente |
|---|---|---|
| holdout-00, deux rédacteurs WAL | Preuve sélectionnée `wal-writer` absente du top5 baseline ; rang3 avec reranker | Gain de rappel, pas top1 certifié ; les premiers passages restent non jugés |
| holdout-01, `SQLITE_BUSY_SNAPSHOT` | Baseline et OR conservent la preuve au rang1 ; préfixe documentaire la perd au top5 | Le préfixe peut diluer un identifiant technique |
| holdout-02, sauvegarde cohérente FR→EN | Baseline retrouve 1/2 preuves ; OR aucune au top5 ; reranker 2/2 | Deux preuves retrouvées ne prouvent pas la complétude d'une réponse générée |
| holdout-04, Python3.11 | Top1 sélectionné correct ; reranker ajoute deux incompatibles3.12 explicitement annotés | Gain global de classement ne remplace pas l'admissibilité |
| holdout-05, backup pendant accès concurrents | `py311-backup` passe du rang3 au rang1 avec reranker | Gain isolé d'ordre à pool identique |
| holdout-07, protection contre annulation | `async-shield` passe du rang2 baseline/rang5 OR au rang1 reranké | Amélioration FR→EN observée sur un exemple, pas preuve générale de multilinguisme |
| holdout-08, `should` | Preuve sélectionnée absente du top5 baseline et OR ; rang3 reranké | Toujours pas preuve sélectionnée au top1 |
| holdout-09, négation Qdrant en français | Aucun positif sélectionné au top5 ; reranker place `qfilter-must` incompatible au rang1 | Échec de portée/négation ; le reranker ne peut inventer une preuve absente de son pool |
| holdout-10, DBSF | Preuve rang1 baseline/OR/reranker, perdue avec préfixe | La pertinence du préfixe doit se juger avec son coût en tokens |
| holdout-11, Python3.12 | Le filtre retire les sources3.11 sans perdre les positifs sélectionnés | Résultat étroit d'un filtre de snapshot, pas preuve de compatibilité logicielle |
| quatre questions sans réponse holdout | Toutes les variantes denses/hybrides renvoient5 passages | L'agent doit refuser d'en déduire un mot de passe, un propriétaire ou une mesure locale |

Le pool20 OR-RRF et son contrôle ont le même recall macro de 0,9167 sur le holdout. Le reranker réordonne ce pool, n'ajoute aucun document ; son recall5 final atteint ici ce plafond diagnostique. Les scores de RRF, cosine et logits ne sont jamais traités comme probabilités d'exactitude.

## Coûts réellement observés et environnement

- CPU inspecté par CIM : **Intel Core Ultra7 270K Plus**, 24 cœurs / 24 processeurs logiques. RAM physique déclarée par psutil : **51 132 588 032 octets**. Plateforme Python : `Windows-10-10.0.28000-SP0` ; cela décrit l'identification API, pas une supposition sur l'édition commerciale Windows.
- `.venv` existante utilisée en lecture/exécution seulement : Python3.11.16, NumPy2.4.6, ONNX Runtime1.31.0, SQLite3.53.1, tokenizers0.22.2, psutil7.2.2. Aucun install/upgrade, aucune mutation de cette venv, aucune installation globale.
- Chargement/validation des deux modèles séparés des stages query ; valeurs exactes dans `report.json`. Les ressources couvrent l'encodage/indexation et les requêtes, pas seulement la recherche.
- Encodage offline : original1 966,38 ms ; contexte2 021,94 ms. **135/136 passages originaux** et **136/136 contextualisés** atteignent/dépassent le cap128 avant troncature. Le texte réellement encodé est sauvegardé ; les citations restent le passage original, pas le préfixe. Cette ablation mesure donc le préfixe **avec son déplacement du texte dans un budget fixe**, pas à quantité de contenu original préservée.
- Cross-encoder : 42 paires au cap512 sur les deux modes du run, warm-up inclus. Pas d'affirmation de lecture exhaustive des passages longs.
- Échantillonnage ressources10 ms, durée77,851 s ; pic RSS harness1 416 822 784 octets, serveur42 717 184 octets. CPU cumulé harness171,90625 s, serveur0,171875 s. Le pic harness comprend les deux modèles et les buffers ; ce n'est pas la RAM marginale du reranker.

| Variante, holdout ANN | Pipeline attribué p50 / p95, ms |
|---|---|
| baseline_and_rrf | 5,624 / 25,095 |
| context_and_rrf | 5,507 / 18,391 |
| lexical_and | 0,114 / 5,839 |
| lexical_or | 0,193 / 0,308 |
| or_rrf | 5,660 / 25,236 |
| version_gate_or_rrf | 5,661 / 25,234 |
| rerank_control_pool20 | 5,654 / 25,226 |
| rerank_pool20 | 904,502 / 1 395,626 |

**Contrat de timing :** somme de composants résidents attribués, pas latence E2E indépendante. Query-encode et lexical partagés sont réutilisés entre variantes ; backend HTTP, filtrage des listes, fusion, reranking, hydratation/sérialisation sont mesurés séparément. La qualification initiale des métadonnées par question et les exports de fichiers sont hors somme. Le query-encode inclut le premier forward résident ; un warm-up explicite précède les boucles serveur/reranking. Un seul passage séquentiel, sans randomisation de l'ordre ; contention de la machine possible. p95 sur16 questions est fragile ; ni SLA, ni verdict de performance du moteur. Les variantes lexicales n'exécutent pas d'encodage dense dans leur somme attribuée.

## Cross-encoder optionnel : checkpoint et licence

Checkpoint public : `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, révision **`1427fd652930e4ba29e8149678df786c240d8825`**. Fichier CPU quantifié : `onnx/model_quint8_avx2.onnx`.

- Carte du modèle conservée : licence déclarée **Apache-2.0**. Cela n'est ni un avis juridique bancaire ni une validation des données d'entraînement.
- ONNX :118 620 016 octets, SHA-256 `6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b`.
- Total modèle + tokenizer + configuration + carte :135 705 845 octets, plafond de téléchargement180 000 000 octets par provisionnement. Le rejeu conserve une deuxième copie dans `provision-replay/`, volontairement traçable ; ne pas additionner ces deux copies pour estimer la taille d'un déploiement.
- Aucune installation `torch`/`transformers` : ONNX Runtime et tokenizer existants. CPU uniquement, sessions résidentes, batches4, troncature longest-first512, logits identity sans sigmoid.
- Le modèle reçoit uniquement les questions et passages du corpus public. Le harness sans `--reranker` complète toutes les autres variantes sans aucun téléchargement ; un échec de chargement optionnel est enregistré dans `blockers`. Un échec d'inférence inattendu reste une erreur explicite, avec résultats partiels et nettoyage en `finally`, pas un résultat inventé.

## Reproduire et contrôler

Depuis `D:/Projets/BorgKnowledge`, sous Git Bash. `rtk --version` a été le premier shell : version0.48.0. `rtk proxy` utilisé pour les commandes non natives du préfixeur.

```bash
# Tests légers : les intégrations serveur/modèle sont opt-in.
rtk proxy .venv/Scripts/python.exe -m unittest discover -s tests -p retrieval_ablation_test.py -v

# Baseline + ablations déterministes/lexicales/filtre, sans nouveau modèle.
# --run doit être un NOUVEAU sous-répertoire d'artifacts/retrieval-ablations.
rtk proxy .venv/Scripts/python.exe tools/retrieval_ablation.py

# Avec le checkpoint déjà reçu et hashé ; run neuf créé automatiquement.
rtk proxy .venv/Scripts/python.exe tools/retrieval_ablation.py \
  --reranker artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model

# Rejouer le provisionnement borné dans une NOUVELLE destination locale.
rtk proxy .venv/Scripts/python.exe \
  artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/provision-reranker.py \
  D:/Projets/BorgKnowledge/artifacts/retrieval-ablations/new-checkpoint-replay

# Relire et recalculer le run final conservé, sans nouvelle inférence.
rtk proxy .venv/Scripts/python.exe \
  artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/verify.py
```

Commande réelle du test d'acceptation final :

```bash
ABLATION_REAL_RUN='D:/Projets/BorgKnowledge/artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/measured-v3' \
ABLATION_RERANKER='D:/Projets/BorgKnowledge/artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model' \
rtk proxy .venv/Scripts/python.exe -W error::ResourceWarning \
  -m unittest discover -s tests -p retrieval_ablation_test.py -v
```

Le chemin final existe maintenant : choisir un nouveau chemin pour une nouvelle exécution, jamais l'écraser. Les modèles MiniLM, le binaire Qdrant et les snapshots historiques doivent déjà être présents aux chemins inscrits dans le freeze. Le harness échoue si leurs hashes ne correspondent pas ; il n'installe rien et ne substitue pas `qdrant-client` local à un serveur.

### TDD, régression, suivi et nettoyage

Tranches RED→GREEN observées séparément : contexte explicite ; lexical OR ; admissibilité UNKNOWN/version ; cross-encoder réel ; expérience serveur complète ; champ d'ancre absent ; titre uniformément dérivé de la source. Les échecs initiaux de fonctions absentes ont précédé l'implémentation correspondante. Le premier run intégré a ensuite révélé le cas d'ancre absent ; le cas est conservé en régression. Le contrôle de contamination des titres a produit `red-title-audit.txt` avant correction.

- **Acceptation finale :7/7 tests PASS,86,351 s**, incluant Qdrant et reranker réels, warnings de ressources traités comme erreurs.
- **Chemin CLI sans reranker réellement exécuté** dans `without-reranker/` :640 lignes (32×10×2), baseline reproduite, nettoyage PID11340/port58450 confirmé. Le modèle optionnel n'est donc pas requis pour compléter la baseline. Rapport SHA-256 `3ae569b292469d88326a6cffaee17b1b4b18915d440b06257646d5660a8a4c5c`.
- **Régression retrieval/extraction hors module docintel :24 tests,22 PASS et2 SKIP,18,743 s**, modèle optionnel activé ; intégration serveur existante également passée (`artifacts/server-benchmark/db36cf89442247bdb635d777534cdc98/`). Ce sous-ensemble vert ne remplace pas la suite globale ci-dessous.
- Vérificateur indépendant :101 empreintes de fichiers et44 entrées gelées vérifiées,704 métriques/provenances recalculées,136 passages contrôlés, mêmes pools de reranking, même index Git.
- Régression élargie finale :**32 tests exécutés,26 PASS,3 SKIP,2 ERROR et1 FAIL** dans la venv commune. Les trois problèmes concernent `document_intelligence_benchmark_test` travaillé séparément : imports `docling` et `bs4` absents, puis pipeline de fixtures non entièrement `ok`. La suite élargie n'est donc **pas verte**. Aucun package ajouté pour masquer ces échecs hors périmètre ; leur propriétaire doit utiliser son environnement séparé. La suite est concurrentement évolutive : le premier passage en comptait30, pas32.
- Les tests existants de serveur génèrent aussi leurs propres répertoires uniques `artifacts/server-benchmark/c79e795f683a47a39fe311e10c69f94b/` et `4ca23ffb92d24863b4a95370026d8f0d/`, processus nettoyés ; aucune réutilisation d'un service existant.
- Beads : recherche avant création, tâche locale `bk-ao9` réclamée. GSD installé découvert à `C:/Users/johan/.claude/gsd-core/bin/gsd-tools.cjs`, `progress --raw` exécuté : aucune phase de projet lisible, aucune initialisation/install/configuration globale.
- Serveur final PID15420, port54997 : arrêt du seul `Popen` possédé, attente, PID absent et port fermé revérifiés séparément. Retour1 après `terminate` Windows = arrêt forcé, **pas acceptation de durabilité ni arrêt gracieux**. Stockage de ce serveur conservé dans son dossier d'évidence, aucun autre service touché.
- Aucun staging/commit/push ; empreinte de `.git/index` inchangée depuis l'entrée. Aucun symbole existant modifié ; fichiers source neufs : `tools/retrieval_ablation.py`, `tests/retrieval_ablation_test.py`, ce document seulement, plus artefacts uniques et suivi Beads autorisé.

## Réutilisation LAD/RAD/GED dans un groupe bancaire — contrat proposé, non implémenté

Ce pilote traite de la **recherche de preuves publiques textuelles**, pas d'une chaîne de reconnaissance documentaire ni de réponses bancaires. Il fournit un format de dossier d'expérience réutilisable ; les capacités suivantes sont des exigences de qualification, pas des fonctions démontrées.

| Couche | Exigence de qualification | Preuve à recueillir avant acceptation |
|---|---|---|
| LAD / acquisition | Original immuable, hash des octets, pages/zones, provenance OCR, détection pertes et contenu non pris en charge | Échantillons autorisés scans natifs/scannés, qualité image, signatures/cachets, tableaux, cases cochées, texte manquant, erreurs de caractères et chiffres |
| RAD / classification-extraction | Type documentaire, champs, unités, en-têtes de lignes/colonnes, confiance OCR séparée de confiance métier, UNKNOWN explicite | Vérité terrain humaine par champ/région, taux d'omission, précision des associations cellule/en-tête, corrections versionnées |
| GED / autorité | Entité juridique, juridiction, propriétaire, statut approuvé, version, validité, périmètre, langue, confidentialité, ACL et conservation | Sources autorisées, rejeu de versions abrogées/coexistantes, séparation groupe/filiale, décision d'autorité explicite |
| Préparation du retrieval | Contextualiser seulement dans un même périmètre autorisé/version valide ; index dense et lexical soumis aux mêmes droits | Tests de non-contamination avant embedding, filtrage des deux branches, caches et parents ; pas de fuite d'un titre ou résumé d'une autre entité |
| Retrieval et reranking | Budgets fixes, candidats admissibles, tokens techniques/négations conservés, preuve absente détectée | Corpus et jugements neufs, questions multi-preuves, version incorrecte, UNKNOWN, traductions FR↔EN et autres langues réellement utilisées |
| Agent lecteur | Les documents sont des données non fiables, pas des instructions de tool-use ; citation à l'original, clarification/refus en cas de portée inconnue | Tests de prompt injection documentaire, fausse prémisse, conflit de versions, absence de preuve ; aucun accès ni action bancaire via une instruction trouvée dans un document |
| Action et supervision | Recherche séparée de décision/exécution ; droits minimaux, approbation humaine selon le risque, journal d'actions corrélé aux preuves | Scénarios d'escalade, journal append-only, révocation, contrôle des accès, séparation des environnements et plans de retour arrière |

### Garde-fous de méthode à conserver

1. **Unités séparées.** Mesurer extraction correcte, preuve retrouvée applicable, réponse soutenue et action autorisée comme quatre critères distincts. Un hash ne prouve pas la justesse OCR ; ANN recall ne prouve pas la pertinence ; un bon classement ne prouve pas l'exactitude d'une recommandation.
2. **Qualification métier préalable.** Définir cutoff d'affichage et unité « information présentée ». Exiger une couverture minimale et mesurer les refus injustifiés, pas seulement la précision des rares réponses acceptées.
3. **Jeux neufs et gouvernés.** Les jeux historiques de ce pilote ne peuvent être réutilisés comme test final. Séparer familles documentaires et entités entre développement, calibration et test ; double annotation/adjudication par spécialistes autorisés ; UNKNOWN conservé jusqu'à jugement. Les labels privés restent dans une infrastructure explicitement autorisée.
4. **Applicabilité avant pertinence.** Versions et dates d'effet doivent être confirmées par le propriétaire documentaire. Un document global n'est pas automatiquement applicable à chaque filiale. Une métadonnée inconnue impose clarification/escalade pour une décision à risque, pas acceptation silencieuse.
5. **Calibrer après avoir fixé la chaîne.** Nouvelle calibration indépendante pour abstention et risque–couverture. Cosine, RRF et logits du reranker ne deviennent pas des probabilités par leur nom. Rapporter faux positifs sans réponse, erreurs de version, contradictions, couverture et incertitude par familles documentaires ; ne pas certifier un seuil sur12 questions.
6. **Pas de mélange de preuves incompatibles.** Un préfixe ou résumé a déjà pu injecter une version inapplicable dans l'embedding. Le retirer seulement après retrieval ne retire pas cette information du vecteur. Filtrer et construire le contexte correctement en amont ; conserver le parent original et les offsets.
7. **Gouvernance des modèles.** Carte, licence, révision, hash, téléchargements bornés, validation sécurité, langues, politique de conservation et dérive. La déclaration Apache-2.0 du checkpoint public n'accorde aucun droit sur un document bancaire et ne vaut pas validation juridique ou réglementaire.
8. **Qualification indépendante et monitoring.** Un pilote local prometteur autorise au mieux une expérimentation supplémentaire ; une mise en service exige les validations métier, sécurité, confidentialité, exploitation et gouvernance du groupe. Aucun de ces contrôles n'est remplacé par les tests de ce dépôt.

### Prochaines expériences justifiées, sans les déclarer réalisées

- Diagnostiquer le coût en tokens du préfixe : source courte ou métadonnées hors vecteur, puis segmentation à frontières constantes dans une expérience distincte ; ne pas rebaptiser ce préfixe « late chunking ».
- Pool candidat inchangé, admissibilité réelle puis reranker ; comparer séparément au reranker non filtré et au contrôle filtré. Le gain et les erreurs ne sont pas extrapolables sans cet essai.
- Vérifier la négation et l'opérateur exact avant toute expansion de requête. L'échec `must_not` est une objection concrète à une activation.
- Collecter des jugements indépendants et une strate sans-réponse représentative avant de choisir un seuil. Aucun nouveau modèle ni corpus privé n'est requis par le code livré.

## Revue éditoriale et limites résiduelles

Deux revues de fond ont été faites, distinctes des tests : (1) attribution et contamination des titres, correction par extraction uniforme et nouveau freeze ; (2) lecture des métriques, séparation des erreurs de version connues / labels explicites / UNKNOWN, des timings attribués / E2E, et des exigences bancaires proposées / capacités implémentées. Les défauts identifiés ont été corrigés ou signalés ci-dessus. Évaluation éditoriale interne :9/10 pour traçabilité, limites et reproductibilité, **pas validation humaine indépendante ni revue visuelle d'une application**.

Limites principales inchangées : petit corpus public, labels sélectionnés incomplets, questions déjà vues, un seul hôte, une passe de timing, troncature massive MiniLM, filtre Python étroit, absence d'abstention et de génération, suite globale non entièrement verte dans l'environnement commun. Le livrable est un benchmark exécuté et auditable, pas un système industriel accepté.
