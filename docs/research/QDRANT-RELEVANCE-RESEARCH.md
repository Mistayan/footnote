# Améliorer la pertinence de BorgKnowledge avec Qdrant

**Rapport de recherche — 17 octobre 2026.** Recherche documentaire, sans installation, modification de code/configuration, exécution de modèle ou accès à un vault. Qdrant demeure la baseline de développement choisie ; pertinence en premier, performance en second. Le seuil futur d’acceptation ≥ 90 % n’est ni atteint ni garanti par ce rapport.

## 1. Décision proposée

Conserver Qdrant et améliorer ce qui détermine les candidats, leur applicabilité et leur classement. L’expérience harmonisée ne montre pas de défaut de pertinence propre au stockage : SQLite et Qdrant retournent le même top5 ordonné sur 32/32 questions. Changer de moteur ne répare ni une preuve tronquée, ni un filtre de version absent, ni une question sans réponse dans le corpus.

**Ordre recommandé :**

1. Définir des jugements indépendants et le contrat du ≥ 90 %, puis préserver les preuves et l’applicabilité par version.
2. Tester le découpage/contextualisation déterministe et une véritable branche lexicale, sans tout changer simultanément.
3. Comparer un embedding multilingue explicite à la baseline, sur les mêmes passages.
4. Ajouter un cross-encoder multilingue sur une union de candidats suffisamment rappelante.
5. Valider une politique d’abstention, sans confondre score et probabilité.
6. Réserver SPLADE, ColBERT et la contextualisation générée aux échecs résiduels qui les justifient.

Ces étapes sont des **expériences proposées, non implémentées**. L’annotation et la provenance sont prioritaires ; les hypothèses de gain restent à mesurer sur notre corpus.

## 2. Ce que les résultats locaux permettent réellement de conclure

### Provenance locale

Documents lus dans le dépôt, sans lire de vault : [QDRANT-QUALITY.md](../QDRANT-QUALITY.md), [TECHNICAL-QUALITY.md](../TECHNICAL-QUALITY.md), [HYBRID.md](../HYBRID.md). Des copies datées et hachées de ces trois documents sont conservées dans le dossier d’évidence de cette recherche. Les chiffres ci-dessous sont **rapportés par ces documents**, pas recalculés par une nouvelle exécution du benchmark.

Expérience principale référencée : `artifacts/qdrant-quality/613659fee2a84ff28f6d2bf5da91d00d/`, notamment `PRIMARY-PAIRED-REVIEW.md` et `primary-pair-per-query.json`.

| Observation locale | Interprétation / intervention prioritaire |
|---|---|
| Même top5 sur 32/32 questions SQLite/Qdrant | Aucune supériorité de pertinence observée d’un backend ; garder Qdrant. |
| MiniLM : 135/136 passages atteignent/dépassent le plafond de 128 tokens | Perte d’entrée majeure ; vérifier où se trouve la preuve et compter les tokens réels, préfixes inclus. Ce plafond appartient à la recette testée, pas à tous les usages de MiniLM. |
| Holdout déjà observé : top1 0,5000 ; macro recall5 0,7083 sur 12 questions répondables | Il existe des problèmes de génération de candidats et/ou de classement ; ces valeurs concernent les positifs sélectionnés. |
| Labels incomplets, souvent un seul positif ; P@5 idéale alors égale à 0,2 | Ne pas traiter les passages UNKNOWN comme faux ; impossible de certifier une précision sémantique exhaustive. |
| Quatre questions sans réponse par split retournent toutes des candidats ; abstention absente de l’expérience harmonisée | Le moteur trouve une proximité, pas une preuve d’answerability ; ce n’est pas quatre réponses générées fausses. |
| Passage Python 3.11 au rang2 d’une question Python 3.12 | Un top1 correct ne sécurise pas la liste ; filtrer l’applicabilité avant classement, pas seulement favoriser la fraîcheur. |
| `should` / `must_not` Qdrant manqués ; shielding classé après cancellation | Tester précision lexicale/opérateurs et reranking de preuves réellement présentes. |
| Branche lexicale FTS5 : termes de la question reliés par AND ; français et longues questions souvent sans match | Le précédent « hybride » n’est pas une validation d’un BM25 bien configuré ; mesurer d’abord le taux de branche vide. |

**Contre-exemple utile à une recette automatique :** le découpage enfant sans overflow a déjà dégradé top1 pour MiniLM ; E5-small enfant améliore certains résultats du holdout réutilisé mais augmente les incompatibilités. Il ne faut donc promettre ni « chunking = gain », ni « E5 = gagnant ». Les enfants suivent en outre la contrainte MiniLM ; ce n’est pas une optimisation autonome de leur longueur pour E5. Le nom et le manifeste du modèle E5 déjà testé doivent être vérifiés avant de le confondre avec **multilingual-e5**.

L’ancien test de seuil cosinus, distinct de l’expérience harmonisée, réduit les candidats sans réponse à 1/4 mais rejette 4/12 questions répondables du holdout. C’est une piste diagnostique, pas une calibration acceptée. Le holdout ayant été observé, toute nouvelle variante doit l’appeler **jeu diagnostic réutilisé**, et non validation indépendante.

**ANN recall ≠ pertinence.** Une éventuelle ANN recall de 94 % mesure la récupération de voisins d’une recherche exacte, pas la présence d’une preuve correcte. Dans cette petite expérience Qdrant, la recall ANN contre exact est même rapportée à 1,0 sans atteindre le seuil de pertinence. Augmenter `ef` ne peut pas réparer un classement exact déjà mauvais.

## 3. Hybride dense + BM25 : premier changement de retrieval à isoler

Qdrant propose Query API, les pré-requêtes `prefetch`, les vecteurs nommés et la fusion RRF ou DBSF ; la requête principale travaille sur les candidats des pré-requêtes.[1] Cela permet de rester dans le backend choisi plutôt que d’en changer pour obtenir de l’hybride.

### Mécanisme et protocole proposé

Le dense doit retrouver les paraphrases et le passage français→anglais ; BM25 doit offrir une voie robuste pour noms d’API, identifiants, erreurs et opérateurs exacts. Qdrant permet le BM25 sous forme sparse, avec génération côté client ou par son mécanisme d’inférence ; cela ne signifie pas que tout texte envoyé à un serveur local bénéficie automatiquement d’un modèle local configuré.[4][6]

**Hypothèse BorgKnowledge :** les zéros de la branche AND et les confusions `should`/`must_not` justifient un test BM25 lexical indépendant avant un sparse neuronal. Conserver une piste exacte non agressivement stemmée pour les tokens de code ; ne pas enlever une négation décisive comme mot vide. Comparer, sur développement seulement :

- lexical actuel AND ;
- BM25 avec correspondance non conjonctive de tous les mots, analyseur documenté et tokens techniques préservés ;
- dense inchangé ;
- fusion dense + lexical, puis adjudication des nouveaux candidats UNKNOWN.

La documentation courante précise que le BM25 utilise par défaut stemming et stopwords anglais, que les traitements doivent être cohérents à l’ingestion et à la requête, et que les statistiques IDF sont par défaut calculées sur les données du shard interrogé.[4] Sur un corpus anglais interrogé en français, changer seulement l’analyseur en français ne traduit pas les termes : la branche dense multilingue reste nécessaire.

La fiche `Qdrant/bm25` demande le modificateur IDF.[6] Ne pas l’appliquer aveuglément à des poids SPLADE ou BGE-M3 appris : ce sont d’autres recettes sparse. Figer `avg_len`, `k1`, `b`, champs indexés et portée IDF ; un changement de corpus ou de segmentation change ces statistiques. Qdrant ne propose pas actuellement BM25F natif selon sa documentation ; les champs séparés fusionnés sont un contournement, pas BM25F équivalent.[4]

### Fusion : ne pas modifier discrètement la baseline

La recette locale historique est RRF avec `k=60`, rangs à partir de 1 ; la documentation Qdrant consultée indique un défaut `k=2` et des rangs à partir de 0.[1] Reproduire explicitement la recette si l’objectif est la parité, ou nommer le changement comme nouvelle variante. Tester les fonctionnalités effectivement disponibles dans le serveur installé : la page courante n’est pas la spécification garantie de toutes les versions.

Ne pas additionner naïvement cosinus et BM25 bruts : leurs distributions sont différentes ; RRF utilise les rangs et DBSF normalise des distributions.[1] **Aucune de ces fusions n’est une confiance d’answerability.** Garder budgets et déduplication explicites ; un budget d’enfants n’est pas un budget de parents distincts. Vérifier aussi que les filtres s’appliquent à chaque branche avant la consommation du budget de candidats.

## 4. SPLADE : expansion lexicale apprise, pas BM25 amélioré gratuitement

SPLADE apprend des représentations lexicales sparse avec régularisation de parcimonie ; l’article original du 12 juillet 2021 décrit le compromis efficacité/coût, mais seul son résumé a été consulté ici.[14] Les expansions peuvent récupérer des termes non littéralement présents, au prix d’un encodeur neuronal supplémentaire ; la documentation Qdrant signale un coût de calcul supérieur au BM25.[4]

La fiche officielle du checkpoint `naver/splade-cocondenser-ensembledistil` indique anglais, espace sparse de 30 522 dimensions, longueur maximale de 512 tokens et 256 pour la reproduction de son évaluation ; elle annonce MRR@10 38,3 et R@1000 98,3 sur MS MARCO dev.[21] Ce sont des **résultats de fiche de modèle**, pas une mesure sur notre corpus ni une précision de 98,3 %. La licence déclarée est **CC BY-NC-SA 4.0**, ce qui empêche d’en faire un défaut commercial sans examen des droits.[21]

**Applicabilité :** pertinent si les échecs résiduels sont des décalages lexicaux dans une même langue et si les candidats BM25 manquent encore la preuve. Faible priorité pour le français→anglais avec ce checkpoint anglais. Préserver une branche exacte pour les noms rares ; ne pas attribuer à tout checkpoint SPLADE une couverture multilingue, une licence permissive ou les résultats d’un autre. Mesurer temps d’encodage offline/query, nombre de non-zéros, mémoire/index et recall des candidats. Le vocabulaire subword n’assure pas une correspondance exacte des identifiants hors domaine.

## 5. Embeddings multilingues : comparer la bonne famille, sur les mêmes unités

### Multilingual E5

La fiche de `intfloat/multilingual-e5-base` indique 768 dimensions, 12 couches, préfixes `query: ` / `passage: ` même hors anglais, 100 langues annoncées et troncature à 512 tokens ; licence MIT.[7] La famille n’est pas interchangeable avec un modèle E5 anglophone ni avec un checkpoint instruct. Pooling, normalisation, tokenizer et préfixes doivent être épinglés.

Le rapport E5 du 8 février 2024, table4, donne sur le **développement MIRACL, moyenne de 16 langues**, nDCG@10/R@100 : BM25 39,3/78,7 ; mE5-small 60,8/92,4 ; base 62,3/93,1 ; large 66,5/94,3.[16] Ces résultats expliquent pourquoi tester une famille multilingue est raisonnable ; ils ne prédisent pas top1 ni précision de BorgKnowledge. MIRACL est ici du retrieval dans chaque langue : ce tableau n’est pas une mesure directe du français→anglais de notre usage.

**Expérience proposée :** sélectionner d’abord un checkpoint multilingual-e5 small/base selon le budget CPU, sans supposer que l’E5 déjà local est multilingue ; comparer à MiniLM avec les mêmes passages admissibles et une recette correcte pour chacun. Séparer l’effet modèle de l’effet longueur de chunk. Échantillonner FR→EN, EN→FR, même langue, tokens techniques et négations ; conserver les résultats par strate plutôt qu’une moyenne flatteuse.

### BGE-M3

BGE-M3 réunit dense, sparse lexical appris et multi-vector, annonce plus de 100 langues, 1 024 dimensions denses et un contexte jusqu’à 8 192 tokens ; licence MIT.[8] Son sparse n’est ni le BM25 fréquentiste ni nécessairement une expansion SPLADE. Une fenêtre plus longue ne justifie pas l’encodage aveugle de documents entiers.

**Point de vigilance documentaire concret :** la fiche signale une correction des résultats MIRACL le 1er juillet 2024 après retrait erroné de passages ayant le même ID que la requête.[8] La v1 du papier du 5 février 2024 a été conservée pour l’historique, mais les résultats retenus viennent de la **v5 du 12 décembre 2025**.[17][20]

Dans cette v5, table1 MIRACL dev, les moyennes nDCG@10 sont **69,2 dense ; 53,9 sparse ; 70,5 multi-vector ; 70,4 dense+sparse ; 71,5 combinaison des trois**.[20] Cette ablation montre un apport dans le protocole des auteurs ; elle ne compare pas notre MiniLM à un BGE-M3 local quantifié sous Windows. Le papier souligne aussi que la partie multi-vector peut être exclue de la génération initiale de candidats en raison de son coût.[20]

**Hypothèse :** BGE-M3 est un challenger utile si multilingual-e5 et BM25 ne couvrent pas suffisamment la longue preuve multilingue ; le tester dense seul avant d’activer toutes ses têtes évite une expérience impossible à attribuer. Pas de latence/RAM garantie ici.

## 6. Cross-encoder : priorité élevée pour les erreurs d’ordre, pas remède au manque de candidats

Un cross-encoder traite conjointement question et passage. L’étude de Rosa et al., v1 du 12 décembre 2022, rapporte que son plus grand cross-encoder dépasse un bi-encodeur de référence de plus de quatre points moyens sur BEIR, dans ses conditions de modèles et de candidats ; ce résultat ne donne pas un gain attendu de quatre points pour BorgKnowledge.[19] Le résumé BEIR (v4, 21 octobre 2021) conclut que reranking et late interaction sont forts en moyenne en zero-shot mais coûteux ; ce n’est pas une victoire sur chaque domaine.[18]

`BAAI/bge-reranker-v2-m3` est un candidat multilingue sous Apache-2.0 ; sa fiche montre une inférence locale Transformers sur des paires et un exemple tronqué à 512 tokens.[9] Il fonctionne **après** la recherche Qdrant ; Qdrant n’exécute pas magiquement ce cross-encoder en stockant ses embeddings. La fiche propose une transformation sigmoïde vers [0,1], mais celle-ci ne prouve aucune calibration de précision sur nos questions.[9]

**Plan proposé :** après filtrage, union dense/BM25 puis déduplication en parents, comparer sans reranker / reranker avec budgets de 20, 50, 100 candidats sur développement. Mesurer séparément recall des candidats, top1, MRR et preuves incompatibles. Le meilleur classement possible est borné par les preuves disponibles dans cette union : inspecter les manques avant d’augmenter la taille du modèle.

Pour `shield` contre `cancel`, ou `should` contre `must_not`, présenter au modèle un passage contenant la définition complète, ses conditions et son titre. Contrôler la troncature des **paires** question+preuve ; déplacer la preuve au-delà du plafond reproduirait le défaut actuel. Conserver le texte source cité, pas seulement le texte enrichi qui sert au score.

**Coûts :** calcul à chaque requête sur chaque paire, RAM des poids et activations, latence croissante avec budget et longueur. Commencer par un modèle résident, mesurer CPU FP32 puis éventuellement quantification vérifiée ; ne pas reprendre le conseil FP16 orienté accélération sans vérifier son comportement CPU/Windows. Aucun export ONNX, quantification ou temps de réponse de ce checkpoint n’a été testé ici.

## 7. ColBERT / late interaction : option ciblée, pas étape obligatoire

ColBERT conserve des vecteurs par token et fait interagir les représentations après encodage. Le résumé de ColBERTv2, version du 10 juillet 2022, annonce une réduction de volume de **6–10× par rapport aux représentations late-interaction comparées**, via compression résiduelle et supervision débruitée.[15] Ce n’est ni 6–10× moins de RAM qu’un vecteur dense unique, ni une propriété automatique du stockage multivector de Qdrant.

Qdrant expose des multivecteurs avec `max_sim`, somme des maxima de similarité par vecteur de la requête.[3] Son tutoriel propose dense+sparse puis reranking late interaction ; pour une représentation réservée au reranking, il désactive HNSW avec `m=0`.[11] C’est une possibilité d’architecture, pas une recommandation d’implémenter cette configuration aujourd’hui.

**BorgKnowledge :** tester seulement si les interactions terme/contexte restent mal classées après un cross-encoder correctement évalué, ou si le coût online du cross-encoder motive un autre compromis. Encodage documentaire pré-calculable mais stockage token-level, lecture et coût MaxSim supplémentaires ; comparer à même recall de candidats et même top final. Le ColBERTv2 du tutoriel n’est pas une preuve de qualité FR→EN.

Une option explicitement multilingue, `jina-colbert-v2`, annonce un contexte de 8 192 tokens mais sa fiche indique **CC BY-NC 4.0**.[12] Elle sert ici à illustrer le filtre linguistique et juridique nécessaire, pas à recommander une activation. BGE-M3 propose aussi des multivecteurs sous sa propre licence, avec des coûts et une qualité qui doivent être mesurés séparément.[8]

## 8. Métadonnées, versions et contextual retrieval

### L’applicabilité doit être une contrainte, non une préférence de score

Qdrant filtre sur payload/ID et combine des conditions ; sa documentation recommande des index payload pour les champs filtrés.[2] Les embeddings n’expriment pas toutes les contraintes métier : une date récente n’est pas une version compatible.[2]

**Schéma proposé, non créé :** `source_id`, URL officielle, hash des octets, `retrieved_at`, `published_at` si attesté, produit/technologie, version documentée, plage de compatibilité validée séparément, langue, statut (`current`, `superseded`, `withdrawn`, `unknown`), parent/section, offsets et hash du texte. Les droits/ACL doivent aussi être des contraintes s’ils existent ; aucun vault n’a été examiné ici.

- Version demandée explicite : contraindre les branches de candidats et revérifier l’applicabilité avant présentation.
- Version inconnue : ne pas inventer une plage compatible depuis la seule similarité ; demander la version ou signaler la portée limitée.
- Recherche historique ou comparative : autoriser les versions demandées, les distinguer et citer chaque portée, sans transformer la source historique en conseil courant.
- Champs absents : politique explicite d’exclusion/quarantaine pour les réponses dépendantes d’une version ; pas de fallback silencieux vers une autre version.

Le CLI dispose déjà de filtres structurés de records, d’après `HYBRID.md`, mais le harness public ne filtre pas automatiquement la version et cela ne prouve pas que les chunks libres aient des métadonnées d’applicabilité fiables. Le test doit donc couvrir les deux branches et les passages, pas seulement les records.

### Contextualisation : commencer sans génération

**Hypothèse à faible risque :** préfixer le texte d’indexation par titre officiel, chemin de section, technologie et version vérifiés peut restaurer le contexte perdu par les petits chunks. Garder l’extrait source immuable, les offsets et le contexte ajoutés distincts. Évaluer la densité de preuve et les frontières de sections, pas uniquement l’absence d’overflow. Les en-têtes consomment eux-mêmes des tokens.

Anthropic décrit, le 19 septembre 2024, une contextualisation générée de 50–100 tokens ajoutée avant embedding et BM25.[10] Ses mesures annoncent une baisse **relative du taux d’échec de retrieval top20** : 5,7 %→2,9 % avec contextual embeddings+BM25 (49 %), puis 5,7 %→1,9 % avec reranking (67 %).[10] Ce ne sont pas 49/67 points de précision, ni des résultats académiques indépendants, ni une garantie de 90 % sur notre top5.

Le coût publié de 1,02 dollar par million de tokens documentaires suppose notamment chunks 800 tokens, documents 8k, contexte 100 tokens et cache Claude ; c’est une estimation historique de cette recette, non un devis actuel ni un coût d’inférence locale.[10] Pour notre usage local, génération et contrôle du contexte, licences du générateur, temps CPU/GPU et réindexation restent non mesurés. Une hallucination dans le contexte peut polluer dense et lexical ; commencer par les métadonnées déterministes, et n’évaluer la génération qu’avec provenance, revue et ablation distincte.

## 9. Abstention et contrat d’acceptation ≥ 90 %

**Contrat proposé à faire valider avant toute nouvelle mesure :** une unité présentée est une preuve qui répond effectivement à la question, avec la bonne version et le bon champ d’application. Distinguer précision des passages, exactitude d’une réponse générée et entailment de ses citations. Une réponse plausible sur le bon sujet n’est pas une preuve.

Mesurer ensemble :

- précision des unités présentées et P@1/P@3/P@5 des listes, selon le produit réellement exposé ;
- recall/nDCG/MRR avec labels exhaustifs ou couverture des jugements explicitée ;
- couverture des questions répondables, rejets erronés et courbe risque–couverture ;
- abstention sur questions non répondables et fausse acceptation, avec dénominateurs ;
- mauvais produit/version, contradiction non signalée, source obsolète et citation non étayante.

RRF, cosinus et score de reranker ne sont pas des probabilités d’exactitude. **Proposition :** après le contrôle d’admissibilité, apprendre sur développement/calibration une règle de refus avec score du reranker, présence d’une preuve, éventuellement marge et désaccord des retrievers. Comparer à un seuil simple et expliciter l’échec possible de chaque signal ; le consensus peut lui aussi être faux. L’abstention doit autoriser « corpus insuffisant » ou « version inconnue », et non fabriquer un détail de déploiement absent des documents publics.

La publication *Conformal Language Modeling*, v2 du 1er juin 2024, étudie des ensembles de réponses générées et des règles calibrées, sous des hypothèses explicites sur des exemples de calibration i.i.d.[13] Ce n’est pas un seuil prêt à appliquer à Qdrant ; ses garanties ne se transfèrent pas aux scores RRF ni à notre distribution technique. Elle motive surtout une calibration séparée et l’énoncé des hypothèses, pas une promesse de confiance universelle.

Le seuil ≥ 90 % doit porter sur un jeu neuf, indépendant, suffisamment jugé, accompagné d’une incertitude statistique et d’un plancher de couverture convenu **avant** le test. Présenter aussi les effectifs bruts. Une précision élevée obtenue en refusant presque tout n’est pas acceptable ; les 12 répondables et 4 non-répondables par split actuels ne certifient pas la généralisation. Les questions déjà consultées servent au diagnostic, jamais à justifier une sélection indépendante après tuning.

## 10. Plan expérimental ordonné, sans implémentation

| Ordre | Expérience et échec visé | Contrôle / décision |
|---|---|---|
| E0 | Taxonomie d’échecs, jugements indépendants ; reconstruction de la preuve visible au modèle | Annoter absent du corpus / extraction / frontières / troncature / version / candidats / ordre / sans-réponse. Geler corpus, sources, questions, labels et manifeste avant inférence. |
| E1 | Applicabilité et refus des mauvaises versions | Baseline identique avec/sans contraintes explicites. Cas métadonnée absente, historique, version ambiguë. Exiger aucune incompatibilité connue présentée dans le jeu testé, sans en déduire une garantie universelle. |
| E2 | Entrée du modèle : segmentation par structure et contexte déterministe | Même MiniLM ; parent tronqué contre segments contrôlés. Conserver preuves complètes, offsets, déduplication ; mesurer bias des parents longs et recall par parent. Ne pas utiliser le découpage déjà perdant comme amélioration présumée. |
| E3 | Branche lexicale utile | Dense fixe, lexical AND contre BM25 paramétré ; fusion explicite. Mesurer branche vide, gains/pertes de candidats, tokens exacts et négations. Pas de comparaison confondue avec changement de moteur. |
| E4 | Multilinguisme | MiniLM contre multilingual-e5 puis BGE-M3 dense si nécessaire ; mêmes passages, recettes propres documentées. Scores FR→EN séparés de même langue. |
| E5 | Reranking | Union admissible fixe, sans/avec cross-encoder multilingue ; budgets 20/50/100 sur développement. Si la preuve manque à l’union, retour à E2–E4 plutôt que gros reranker. |
| E6 | Abstention | Calibration séparée après ranking ; risque–couverture et non-répondables difficiles. Figer règle avant nouveau test ; refuser l’activation si contrat non satisfait. |
| E7 | Options conditionnelles | SPLADE si manque lexical persistant ; ColBERT si compromis qualité/coût justifié ; contexte généré si ambiguïté documentaire persistante. Une seule nouveauté par ablation. |
| E8 | Performance, seulement après pertinence | E2E encode/recherche/fusion/rerank/citations, modèle résident et démarrage, p50/p95, RAM, disque, ingestion ; blocs répétés randomisés. Vérifier que quantification/ANN conservent la qualité acceptée. |

Pour chaque requête : conserver question, statut répondable, version, liste ordonnée top5 avec extraits et offsets, labels positifs/incompatibles/UNKNOWN, scores de chaque branche et du reranker, motifs de refus et métriques. Constituer un pool profond depuis plusieurs variantes puis l’adjudiquer à l’aveugle ; ne pas déclarer les nouveaux passages non pertinents faute de labels. Prévoir un jeu final neuf et des familles documentaires/questions séparées pour limiter la fuite entre splits.

## 11. Coûts, Windows, local et licences : ce qui est établi / ce qui reste ouvert

| Composant | Évidence et droits | Coût/risque restant à mesurer ici |
|---|---|---|
| Qdrant | Source officielle sous Apache-2.0 ; serveur 1.19.2 déjà documenté localement.[22] | Pas de migration de stockage justifiée par la pertinence. Vérifier la disponibilité de chaque option de documentation courante dans la version installée. |
| BM25 Qdrant | Fiche modèle Apache-2.0 ; nécessité IDF documentée.[6] | Normalisation FR/EN, tokens techniques, statistiques, index et maintenance ; pas de coût transformer requis pour BM25 classique. |
| FastEmbed | README : ONNX Runtime, pas de GPU requis ; licence Apache-2.0 du dépôt.[5][23] | Chaque modèle a ses propres droits et export. Ne pas supposer que tous les checkpoints cités sont immédiatement supportés. |
| multilingual-e5-base | MIT, 768 dimensions, limite documentée 512 tokens.[7] | Re-embedding, taille des vecteurs, CPU/RAM, parité pooling/préfixes, export et quantification à valider. |
| BGE-M3 | MIT, dense 1 024 dimensions, fenêtre annoncée 8 192.[8] | Longueur et têtes sparse/multi-vector augmentent les coûts ; pas de mesure Windows locale fournie dans cette recherche. |
| bge-reranker-v2-m3 | Apache-2.0 ; exemples locaux PyTorch/Transformers.[9] | Inférence paire par paire, limite effective de la recette, latence CPU, RAM, export ONNX et quantification non vérifiés. |
| SPLADE checkpoint retenu pour étude | CC BY-NC-SA 4.0, anglais.[21] | Examen juridique avant usage commercial, coût neuronal, non-zéros sparse et couverture linguistique. |
| Jina ColBERT v2 | CC BY-NC 4.0 dans sa fiche.[12] | Droit commercial non acquis, stockage token-level, qualité FR→EN et inférence locale à vérifier. |
| Runtime Windows | ONNX Runtime documente le CPU et demande Visual C++ 2019 runtime pour ses builds Windows.[24] | Cela ne certifie pas un modèle particulier, ses opérateurs, son export ou sa vitesse. Aucune dépendance installée ici. |
| Contextualisation générée | Recette et coût historiques Claude, pas une licence de modèle local.[10] | Générateur local, licence, contrôle des hallucinations et coût offline restent à sélectionner/évaluer. |

**Lacunes délibérément non comblées par des chiffres inventés :** pas de benchmark CPU de ces nouveaux modèles sur cette machine ; pas d’enveloppe mémoire/chiffre de latence garanti ; pas d’audit juridique exhaustif des poids dérivés et datasets ; pas d’export ONNX effectué ; pas d’évaluation de réponse générée, de vault, d’OCR ou de fidélité des tableaux. La licence du moteur ne couvre pas automatiquement celle des modèles.

Aucune alternative de stockage n’a montré ici de preuve convaincante qu’elle corrigerait les échecs identifiés. Une réouverture du choix exigerait un obstacle fonctionnel ou des mesures comparables à pertinence constante, pas un slogan de benchmark ANN. **Conclusion : poursuivre Qdrant, mais ne pas activer une politique de réponse acceptée à 90 % sur les preuves actuelles.**

## 12. Dossier d’évidence et limites de la recherche

Dossier task-local : [`artifacts/research/relevance-20261017T113846Z-f7167ef2/`](../../artifacts/research/relevance-20261017T113846Z-f7167ef2/).

- `ledger.json` : identifiants de citation attribués mécaniquement, URLs et extraits de preuve attachés.
- `fetch-receipts.json` : URL demandée/finale, HTTP, date UTC, nombre d’octets et SHA-256 ; `sources/` conserve octets reçus et texte extrait.
- `evidence-quotes.json` : citations verbatim vérifiées contre les textes conservés ; `local-evidence.json` et `local/` lient les constats locaux à leurs documents.
- `citation-verification.txt` et `verification.json` : résultats de contrôle des citations, des téléchargements et des empreintes ; pas de certification scientifique de toutes les interprétations.

Les 24 sources enregistrées ont été effectivement téléchargées le **17 octobre 2026 UTC**, pas seulement vues dans des snippets. Les pages officielles sans date de publication sont datées par consultation ; leurs URLs flottantes sont liées aux octets hachés, non présentées comme des commits immuables. Les versions arXiv utilisées sont explicites. SPLADE original, ColBERTv2 et BEIR ont été lus au niveau résumé/métadonnées, pas intégralement ; aucune valeur de tableau non consulté ne leur est attribuée. E5, BGE-M3, cross-encoders et conformal ont été consultés en HTML intégral. Les résultats de fiches de modèle et le billet industriel Anthropic sont identifiés comme tels, distincts des publications académiques.

Ce travail privilégie des sources primaires pertinentes et réellement lues ; ce n’est pas une revue systématique exhaustive de toutes les publications jusqu’en octobre 2026, ni une preuve qu’aucun modèle plus récent ne serait meilleur. Aucun gain de ces méthodes sur BorgKnowledge n’a été mesuré pendant cette mission.

## Sources

[1] https://qdrant.tech/documentation/hybrid-search — Hybrid Queries
[2] https://qdrant.tech/documentation/concepts/filtering — Filtering
[3] https://qdrant.tech/documentation/concepts/vectors — Vectors
[4] https://qdrant.tech/documentation/search/text-search/full-text-search — Full Text Search
[5] https://raw.githubusercontent.com/qdrant/fastembed/main/README.md — FastEmbed
[6] https://huggingface.co/Qdrant/bm25/raw/main/README.md — Qdrant BM25
[7] https://huggingface.co/intfloat/multilingual-e5-base/raw/main/README.md — Multilingual E5 base
[8] https://huggingface.co/BAAI/bge-m3/raw/main/README.md — BGE M3
[9] https://huggingface.co/BAAI/bge-reranker-v2-m3/raw/main/README.md — BGE reranker v2 M3
[10] https://www.anthropic.com/engineering/contextual-retrieval — Contextual Retrieval
[11] https://qdrant.tech/documentation/search-precision/reranking-hybrid-search — ColBERT hybrid Qdrant
[12] https://huggingface.co/jinaai/jina-colbert-v2/raw/main/README.md — Jina ColBERT v2 model
[13] https://arxiv.org/html/2306.10193v2 — Conformal Language Modeling
[14] https://arxiv.org/abs/2107.05720 — SPLADE
[15] https://arxiv.org/abs/2112.01488v3 — ColBERTv2
[16] https://arxiv.org/html/2402.05672v1 — Multilingual E5 report
[17] https://arxiv.org/html/2402.03216v1 — BGE M3 paper
[18] https://arxiv.org/abs/2104.08663v4 — BEIR
[19] https://arxiv.org/html/2212.06121v1 — Cross Encoders
[20] https://arxiv.org/html/2402.03216v5 — BGE M3 paper latest v5
[21] https://huggingface.co/naver/splade-cocondenser-ensembledistil/raw/main/README.md — SPLADE model card
[22] https://raw.githubusercontent.com/qdrant/qdrant/master/LICENSE — Qdrant license
[23] https://raw.githubusercontent.com/qdrant/fastembed/main/LICENSE — FastEmbed license
[24] https://onnxruntime.ai/docs/install — ONNX Runtime installation
