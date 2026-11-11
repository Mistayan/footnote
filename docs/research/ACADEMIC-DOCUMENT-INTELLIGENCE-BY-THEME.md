# Intelligence documentaire — revue académique par thème

**BorgKnowledge · 17 octobre 2026 · Recherche documentaire uniquement.**

Complément de [DOCUMENT-INTELLIGENCE-RESEARCH.md](DOCUMENT-INTELLIGENCE-RESEARCH.md), pas une nouvelle sélection d'outils. Le rapport précédent fixe le modèle canonique, les familles de formats et Qdrant. Ici, l'objet est de sélectionner **des mécanismes scientifiques à éprouver** : association structure↔contenu natif, canonicalisation des tableaux, représentations visuelles compressées, recherche de cellules contextualisées et évaluation à plusieurs granularités.

**Périmètre respecté :** sources publiques primaires et ce rapport existant uniquement ; aucun coffre ni document privé lu, aucune installation, ingestion, exécution de modèle, modification de code applicatif, de service ou de configuration globale. Qdrant reste la base sélectionnée. Les documents et preuves de recherche ci-dessous sont les seules créations. Aucun score local, résultat commercial garanti ni précision à 90 % n'est revendiqué.

## 1. Synthèse : les idées à retenir

1. **Ne pas réécrire les chiffres quand leur texte natif est exploitable.** TableFormer sépare prédiction de structure et localisation des cellules afin de rattacher leur contenu PDF ; PubTables-1M montre que définir la structure de référence et corriger la sursegmentation sont déjà des décisions déterminantes pour l'évaluation.[1][2]
2. **Indexer le sens de la cellule, pas seulement sa valeur ou sa ligne.** MT2Net sérialise les cellules avec les chemins d'en-têtes de lignes et de colonnes ; HiTab raisonne sur des régions sélectionnées par ces deux hiérarchies. Ce sont des mécanismes plus précis qu'un simple chunking « parent-enfant ».[6][7]
3. **Comparer trois représentations visuelles, pas uniquement des noms de checkpoints.** ColPali : multivecteurs et MaxSim ; VisRAG-Ret : vecteur unique par page après pooling pondéré ; Light-ColQwen2 : fusion de patchs tardive avec adaptation à cette fusion. Ces trois compromis sont différents et ont des protocoles publiés différents.[3][4][5]
4. **La preuve complète n'est pas une page thématiquement proche.** OmniDocBench mesure l'extraction, MMDocIR distingue recherche de pages et de régions. HiTab ajoute un avertissement essentiel : une réponse numérique correcte peut venir d'un programme incorrect ou de la mauvaise cellule.[8][9][7]

**Choix proposé pour les futurs essais :** priorité à la fidélité cellule–en-têtes–unités–ancre, puis à la couverture des ensembles de preuves ; ajout visuel et compression ensuite. Ce classement est une recommandation de conception, pas un résultat mesuré.

## 2. Corpus retenu, statut et niveau de lecture réel

**Dix articles**, répartis en **3 / 3 / 2 / 2** par thème. Les sources complémentaires de licences et de statut ne sont pas comptées comme articles. « Lu » signifie ici **texte intégral récupéré et sections ciblées effectivement lues**, non lecture exhaustive ligne par ligne de toutes les annexes. Aucun article n'est évalué à partir de son seul résumé.

| Thème | Article et statut vérifié | Texte et sections effectivement examinés |
|---|---|---|
| Parsing | Nassar et al., **TableFormer**, CVPR 2022, version CVF des actes.[1] | PDF primaire ; §3–5.4, architecture, limites de taille et Tables 2–4. |
| Parsing | Smock et al., **PubTables-1M**, CVPR 2022, version CVF des actes.[2] | PDF primaire ; §3–5, Algorithm 1, Tables 2–5, limites et conclusion. |
| Layout | Zhao et al., **DocLayout-YOLO**, arXiv **2410.12628v1**, 2024 ; traité comme **prépublication**, aucun lieu évalué par les pairs établi par cette collecte.[10][11] | PDF v1 ; §3–5.4, Tables 1–3. La fiche arXiv ne vaut pas acceptation en conférence. |
| Visuel | Faysse et al., **ColPali**, **ICLR 2025** confirmé par les actes officiels ; texte lu : arXiv **2407.01449v6**.[3][12] | §3.2, §4–5.2, Table 2 ; annexes B.2–B.4 sur entraînement, stockage et latence. |
| Visuel | Yu et al., **VisRAG**, **ICLR 2025**, PDF des actes.[4] | §3.2–3.3, §4–5.1, Tables 1–3 ; séparation retrieval/génération et in-domain/out-of-domain. |
| Visuel | Ma et al., **Towards Storage-Efficient Visual Document Retrieval: An Empirical Study on Reducing Patch-Level Embeddings**, **Findings of ACL 2025**, pas ACL main.[5] | §4–6, Tables 1–3 et limitations ; Light-ColPali/ColQwen2. |
| Hiérarchie | Zhao et al., **MultiHiertt**, **ACL 2022, Long Papers**.[6] | §3–5.4, Tables 3–4, sérialisation et modules de MT2Net. |
| Hiérarchie | Cheng et al., **HiTab**, **ACL 2022, Long Papers**.[7] | §2.1, §2.6–2.7, §3.1–3.3, §4.2.3 ; Tables 3–4, alignements et erreurs de programmes. |
| Évaluation | Ouyang et al., **OmniDocBench**, **CVPR 2025**, version CVF des actes.[8] | §3.2–3.3, §4.1–4.3 et §5 ; Tables 2–9, exclusions du scoring. |
| Évaluation | Dong et al., **MMDocIR**, **EMNLP 2025**, PDF ACL Anthology.[9] | §2–3.5, §5.1–5.7, Tables 2–9, annexe G sur les licences ; incohérences de dénombrement conservées. |

**Critère de sélection :** apport méthodologique réutilisable et source primaire accessible, pas classement exhaustif des publications jusqu'à octobre 2026. Aucun résultat ICCV/ECCV/SIGIR n'est ajouté artificiellement pour remplir une case. Les articles CVPR, ACL/Findings, EMNLP et ICLR constituent le noyau vérifié ; arXiv reste explicitement identifié. OpenReview a été repéré à la découverte pour VisRAG ; le PDF des actes ICLR, plus directement exploitable, fonde la lecture.

## 3. Thème A — layout, parsing et fidélité structurelle

### A1. TableFormer : structure et boîtes couplées, contenu natif séparé

**Méthode originale.** Un encodeur d'image alimente un décodeur de structure HTML ; l'état caché associé à chaque cellule alimente un décodeur de boîte. La synchronisation fournit une correspondance explicite cellule↔région, permettant ensuite de reprendre le texte dans le PDF plutôt que d'entraîner un décodeur OCR de contenu. Les spans sont représentés dans la séquence structurelle ; les boîtes sont prédites en correspondance avec les cellules, pas appariées a posteriori à une liste arbitraire d'objets. Voir §4.1, Figure 3–4.[1]

**Ce qu'on peut transposer.** Pour une région tabulaire native, effectuer l'assignation des fragments de texte aux cellules ; garder le texte original et la boîte d'assignation. Une région image nécessite toujours un OCR distinct : l'absence de décodeur OCR dans TableFormer ne transforme pas un scan en PDF natif. L'idée à tester est la séparation **structure visuelle / transcription de contenu**, et non le remplacement obligatoire du parseur déjà présélectionné.

**Données et évaluation.** Le papier utilise PubTabNet, FinTabNet, TableBank et SynthTabNet, et sépare structure seule, détection de cellules et structure avec contenu, §5.3–5.4, Tables 2–4. Le TEDS de structure seule ne doit pas être cité comme exactitude des chiffres extraits. Le texte signale aussi des écarts entre texte PDF et vérité HTML liés aux espaces et représentations Unicode, §5.4.[1]

**Limites concrètes.** Le prétraitement d'entraînement limite les dimensions tabulaires ; §5.1 impose un budget de séquence structurelle et redimensionne les images. §5.4 observe des difficultés sur les grandes tables dont les détails deviennent indistinguables après réduction de résolution. Les tables multipages, l'ordre de lecture global et les en-têtes métier implicites ne sont pas résolus par ce seul mécanisme.[1]

**Calcul/licence.** §5.1 décrit ResNet-18, PyTorch, les phases d'apprentissage et le cache de décodage ; pas de configuration matérielle complète ni de débit CPU Windows établi dans les sections lues. Aucune licence du checkpoint TableFormer exact n'a été vérifiée ici : ne pas reprendre la licence d'un toolkit qui l'intègre comme autorisation générale de ses poids.[1]

### A2. PubTables-1M : canonicaliser la topologie avant d'apprendre et de noter

**Méthode originale.** Le pipeline aligne les caractères PDF et le HTML/XML avec Needleman–Wunsch, complète les boîtes de lignes/colonnes/cellules vides, puis fusionne les cellules d'en-tête sursegmentées selon des règles explicites. L'Algorithm 1 ne fait pas une simple suppression d'espaces : il modifie l'interprétation logique de la grille. Un même rendu peut cacher plusieurs annotations incompatibles, §3.[2]

**Transposition proposée.** Conserver deux couches : observation brute et topologie interprétée, avec journal des fusions. En revue humaine, vérifier si un en-tête s'applique réellement à toutes les colonnes fusionnées ; ne jamais « réparer » silencieusement les chiffres pour satisfaire une grille attendue. Comparer deux sérialisations sans égaliser leurs conventions de cellules vides peut produire un faux classement.

**Évaluation utile.** §5 distingue **AccCon**, proportion de tables dont toutes les cellules ont un contenu exactement correct, et **GriTS** pour topologie, contenu et localisation partiellement corrects. Table 5 : sur les tables complexes, AccCon passe de **0,5360** pour DETR-NC entraîné/évalué en non-canonique à **0,6944** pour DETR en canonique. Cela change à la fois les annotations d'apprentissage et d'évaluation : ce n'est pas le gain isolé d'un composant à modèle et vérité terrain constants.[2]

**Limites.** §3 précise que la canonicalisation est conçue pour PMCOA, ne garantit pas l'absence d'erreurs et n'infère pas l'intégralité des en-têtes de lignes. Les tableaux multipages sont hors périmètre. Ne pas appliquer les règles mécaniquement aux budgets, tableaux de bord et tableurs français.[2]

**Calcul/licence.** Modèles DETR et Faster R-CNN à backbone ResNet-18, §4 ; matériel d'entraînement et enveloppe de déploiement non établis par les passages lus. Le dépôt table-transformer a une licence **MIT** ; cette licence de logiciel n'efface pas les droits des publications PMCOA et ne constitue pas à elle seule un audit de chaque artefact de données/poids.[2][13]

### A3. DocLayout-YOLO : diversité synthétique et perception multi-échelle

**Méthode originale.** **Mesh-candidate BestFit** compose des pages par placement d'éléments et recherche de grilles libres, inspirée du bin packing bidimensionnel. Le module **GL-CRM** combine réceptions globales, intermédiaires et locales afin de reconnaître des éléments de tailles très différentes, §3–4. L'originalité exploitable est l'ablation **diversité de pré-entraînement / architecture**, plutôt que l'ajout d'un VLM généraliste à chaque page.[10]

**Données/métriques.** Évaluation sur D4LA, DocLayNet et DocStructBench ; mAP de détection et FPS, §5.1–5.4, Tables 1–3. Le papier utilise la **validation DocLayNet** pour évaluer, §5.1. Une bonne boîte « table » n'atteste ni grille de cellules, ni OCR exact, ni ordre de lecture : ne pas transformer la mAP en taux de conversion fidèle.[10]

**Calcul et limites.** §5.3 décrit un entraînement sur **8 A100** ; Table 3 mesure les FPS sur **une A100**, avec frameworks différents selon les méthodes. Ce n'est pas un budget CPU ni le débit du pipeline entier. Le pool synthétique vient notamment de M6Doc test, §3.1 : documenter les provenances et recouvrements avant toute réutilisation de données, et ne pas mélanger des familles dérivées entre développement et test.[10]

**Licence/statut.** Snapshot de code **AGPL-3.0** ; obligations de copyleft et cas de mise à disposition réseau à examiner avant intégration. Poids, données synthétiques et éléments sources nécessitent leur propre vérification. Le texte utilisé est une prépublication v1, pas une acceptation CVPR supposée parce que le modèle figure dans un benchmark CVPR.[14][10][11]

## 4. Thème B — recherche visuelle : interaction, pooling et compression

### B1. ColPali : une page comme ensemble de vecteurs, pas comme transcription

**Méthode.** Adaptation de PaliGemma : les sorties de tokens sont projetées vers un espace commun ; le score additionne, pour chaque token de requête, sa meilleure similarité avec les vecteurs de la page (**MaxSim**, équation 1, §4.1). L'entraînement contrastif et les ablations BiSigLIP/BiPali/ColPali sont essentiels : appliquer MaxSim à des patchs non entraînés pour cet objectif n'est pas une reproduction de la méthode.[3]

**Apport au rapport précédent.** Le nouvel angle n'est pas « ajouter ColPali », déjà proposé, mais garder deux témoins : un modèle réellement appris en vecteur unique et une interaction tardive apprise. Cela évite d'assimiler un moyennage improvisé à un baseline scientifique valide.

**Données/évaluation.** ViDoRe : classement à la page, nDCG@5, Table 2 ; apprentissage en anglais et examen du transfert vers le français, §4.2 et §5.1. Le transfert montré sur ces tâches n'est pas une validation de scans métier français, de toutes leurs unités ou de leur provenance. Des variantes de questions proviennent de VLM et sont filtrées : conserver ce mode de construction dans l'interprétation.[3]

**Coût.** §4.2 et B.2 : LoRA et entraînement multigpu ; §5.2/B.4 : mesures d'inférence sur NVIDIA L4. B.4 et une note de §5.2 ne décrivent pas le même dénombrement de pages pour les mesures ; aucun chiffre unique de latence n'est repris ici. Dans tous les cas, stocker plusieurs vecteurs accroît la taille de représentation ; la latence de scoring n'inclut pas automatiquement rendu, accès aux preuves et lecture finale.[3]

**Licence.** La carte **ColPali v1.3**, différente du checkpoint expérimental du papier, distingue adaptateurs **MIT** et backbone **Gemma**. C'est une alerte de qualification, pas la preuve que tous les checkpoints ColPali ont exactement les mêmes conditions.[18]

### B2. VisRAG : vecteur visuel unique et séparation retrieval/génération

**Méthode.** VisRAG-Ret applique un **pooling moyen pondéré par position** aux derniers états du VLM, puis compare les pages et requêtes par cosinus ; apprentissage InfoNCE, §3.2.1. La génération explore juxtaposition de pages, sélection pondérée de réponses ou VLM multi-image, §3.2.2. Le vecteur unique est une alternative structurante au coût multivecteur, non une prétendue compression sans perte.[4]

**Ce que l'expérience distingue.** Les Tables 2 et 3 séparent classement et qualité des réponses ; Table 2 distingue off-the-shelf, hors domaine et dans le domaine, et le ColPali comparé y est réentraîné sur leurs données. Les performances de ce ColPali ne doivent pas remplacer celles du checkpoint publié sur ViDoRe. Pour la génération, les résultats « Oracle » fournissent les pages positives : utile pour séparer panne de recherche et panne de lecture.[4]

**Données/limites.** Corpus issus notamment de DocVQA, ArxivQA, ChartQA, InfoVQA, PlotQA et SlideVQA ; suppression de questions dépendantes du contexte, §3.3/Table 1. La métrique de réponse accepte une marge numérique relative dans le protocole publié, §3.3 : ne pas l'utiliser comme mesure de conservation exacte des valeurs. La phrase des auteurs sur la préservation de toute l'information visuelle n'est pas une garantie de restitution : rendu, résolution et compression représentationnelle demeurent des transformations.[4]

**Coût/licence.** §4 : fine-tuning d'une époque sur **8 NVIDIA A100 80 GB**, batch 128 ; pas de fine-tuning du générateur dans cette comparaison. Le code VisRAG récupéré est **Apache-2.0**, mais les conditions du backbone MiniCPM-V et des checkpoints exacts n'ont pas été auditées ; aucune autorisation commerciale globale n'est déduite.[4][15]

### B3. Light-ColPali/ColQwen2 : fusion tardive plutôt que suppression aveugle

**Méthode originale.** L'étude compare pruning aléatoire, par score et par attention, puis fusion par voisinage spatial ou clustering sémantique. La pertinence d'un patch dépendant de la requête future, supprimer hors ligne les patchs supposés inutiles peut éliminer un indice rare. La méthode retenue fusionne les embeddings par similarité **après projection**, et le modèle est adapté avec ces embeddings fusionnés lors de l'entraînement et de l'inférence, §4–6.[5]

**Résultat exploitable sans surpromesse.** Table 2, backbone Qwen2-VL-2B, moyenne des tâches publiées : **ColQwen2 81,4 nDCG@5** contre **Light-ColQwen2 79,9** au facteur de fusion 9 ; coûts de représentation relatifs à DSE **64,4** et **7,6**. Le papier rapporte **98,2 % du score** et **11,8 % de l'empreinte** originale pour cette configuration. Ce sont des rapports sur les embeddings, pas « 98,2 % des preuves correctes », ni la taille totale d'un index Qdrant avec HNSW, payloads et rendus.[5]

**Coût et piège d'ingénierie.** Table 3 : apprentissage sur **8 A100**, génération de représentations de pages sur **une A100** ; la fusion peut ajouter du temps hors ligne. Faire du merging tardif ne réduit pas nécessairement les FLOPs de l'encodeur. Le gain de stockage ne doit donc pas être transformé en gain de débit d'ingestion.[5]

**Applicabilité.** L'étude retrouve des régressions différentes selon les types de documents ; les pages à forte densité d'information exigent une analyse séparée. La compression doit conserver une liaison page→preuve indépendante des vecteurs : les centroïdes ne sont pas des ancres documentaires. Licence du code/poids Light exact non vérifiée : ne pas hériter automatiquement de l'étiquette du backbone ou des adaptateurs d'un autre dépôt.[5]

## 5. Thème C — cellules, hiérarchies et preuves numériques

### C1. MultiHiertt / MT2Net : la cellule accompagnée de tous ses en-têtes

**Méthode.** MT2Net transforme chaque cellule en phrase avec ses **en-têtes de lignes et de colonnes hiérarchiques** ; un classifieur question–fait sélectionne des faits, remis dans l'ordre du document, puis un module produit un span ou un programme arithmétique exécutable, §4. Cela vise directement le cas où plusieurs branches partagent les mêmes libellés « Product », « Service » et la même année.[6]

**Données et métriques.** Table 3 : **10 440 QA**, **2 513 documents**, provenant de rapports financiers ; §3.1 décrit la sélection de documents courts et le rejet de tables non traitables par leur prétraitement. Table 4 : F1 de réponse test **33,60** pour FinQANet RoBERTa-large et **38,43** pour MT2Net RoBERTa-large. Ce n'est ni Recall@k d'un index corpus entier, ni un gain attribuable uniquement aux en-têtes : les frameworks diffèrent.[6]

**Apport pratique proposé.** Représenter chaque fait candidat par valeur brute, chemin de ligne, chemin de colonne, unité/échelle, période, note applicable et identifiants de cellule/table/document/version. Garder séparément la valeur normalisée et la règle de transformation. L'extension **unités, notes et provenance de version** est une exigence BorgKnowledge, pas une capacité démontrée par le modèle MT2Net.

**Limites/calcul/licence.** Le papier suppose des tables HTML déjà structurées ; il ne mesure pas les fautes OCR amont. Les opérations autorisées bornent ce que le programme peut exprimer. §5.2 : BERT-base pour la sélection de faits, variantes BERT/RoBERTa pour le raisonnement, entraînement sur **RTX 3090s** ; nombre exact de cartes et coût complet non établis. Dépôt sous **MIT** ; vérifier séparément droits FinTabNet/FinQA et rapports sous-jacents avant redistribution ou usage commercial.[6][17]

### C2. HiTab : sélectionner une région à deux hiérarchies, puis opérer

**Méthode.** HiTab définit une région indexée par les arbres d'en-têtes gauche et supérieur. `filter_tree` sélectionne un sous-arbre et `filter_level` un niveau ; la sélection précède l'opération. Cela évite notamment d'additionner sans distinction des niveaux « détail » et « total ». Les alignements entités/quantités servent à réduire les programmes parasites, §3.1–3.2.3.[7]

**Résultat contrôlé et borné.** Table 4, supervision faible : MAPO passe de **29,2** à **40,7** en execution accuracy test avec la forme logique hiérarchique plutôt que la forme originale. Sous supervision partielle, d'autres annotations sont ajoutées : les lignes correspondantes ne sont donc pas un progrès gratuit à labels constants. La même table présente un taux de programmes parasites audité manuellement sur un échantillon de développement, pas sur tout le test.[7]

**Mécanisme de contexte récupérable.** §4.2.3 propose de partir des cellules sélectionnées, d'ajouter leurs en-têtes correspondants et leurs parents, puis de sérialiser le sous-tableau. Pour BorgKnowledge, cela suggère une **fermeture contextuelle bornée** : récupérer les cellules candidates, ajouter chemins d'en-têtes et notes nécessaires, pas tout le tableau systématiquement. C'est une adaptation de la sélection de sous-tableaux pour génération, non un retriever open-domain déjà démontré dans HiTab.[7]

**Limites/calcul/licence.** Le dataset est anglais, issu de rapports statistiques HTML et de tables Wikipedia, avec hiérarchies extraites par heuristiques ; il ne valide pas un parsing PDF/OCR français. §3.2.5 : serveur à **quatre V100**. Le fichier LICENSE récupéré est **Computational Use of Data Agreement v1.0**, pas MIT : utilisation computationnelle, attribution et transmission des conditions lors de redistribution, et distinction Data/Results. Le fournisseur n'y garantit pas détenir tous les droits. Ne pas traiter l'ensemble données+code+sources comme une licence commerciale uniforme.[7][16]

## 6. Thème D — évaluer extraction, pertinence et suffisance des preuves

### D1. OmniDocBench : tester le parseur sans lui attribuer le succès du retrieval

**Méthode d'évaluation.** La contribution utile est le matching adaptable aux différences de segmentation, puis les métriques spécifiques : distance d'édition pour texte, TEDS pour tables, CDM pour formules et distance d'édition pour ordre, §4.1–4.3. Le protocole permet d'isoler layout, reconnaissance et résultats finaux, au lieu de réduire l'extraction à une similarité de Markdown.[8]

**Version : attention à la dérive.** Le PDF **CVPR 2025** lu décrit **981 pages**, §3.1–3.3. Ce n'est pas le même état que les versions et nombres de pages des publications arXiv/dépôts actuels évoqués dans l'étude précédente. Ne pas fusionner les scores de ces états dans un tableau unique.[8]

**Angle mort important.** §4.2 décrit l'ignore handling : mobilier, notes et légendes peuvent participer au matching tout en étant exclus du calcul ; §4.3 exclut tables/images et composants ignorés du scoring final d'ordre. Ainsi, conserver un score standard et ajouter un **score métier non masqué** sur notes, unités, renvois et légendes indispensables. L'absence de pénalité standard n'est pas une extraction correcte.[8]

**Calcul/licence.** Les coûts des différents moteurs ne sont pas normalisés en budget local exploitable dans les passages examinés ; aucun besoin RAM/VRAM global ni débit Windows déduit. Les documents et modèles composites exigent un audit de droits distinct ; aucune licence de dataset OmniDocBench n'a été validée dans cette collecte. Les résultats de la publication ne sont pas réinterprétés comme ceux des versions courantes des parseurs.[8]

### D2. MMDocIR : distinguer preuve à la page et preuve à la région

**Méthode.** Les annotations identifient pages de preuve et boîtes des éléments nécessaires. Pour les régions, §5.1 utilise le recouvrement des boîtes afin de ne pas exiger des segmentations identiques entre détecteur et référence. Le protocole évalue aussi recherche directe de régions et cascade pages→régions, §5.7/Table 9 : une cascade n'est pas supposée meilleure par construction.[9]

**Vérification utile des sources.** Le PDF contient une contradiction interne : résumé/figure annoncent **1 685** questions et le résumé **173 843** labels bootstrappés ; §3.2/Table 3 décrivent **1 658** questions d'évaluation et Table 4 **73 843** questions d'entraînement. Retenir les tables et sections pour décrire le protocole, tout en conservant la contradiction dans le dossier de preuves ; vérifier le manifeste réel avant tout futur téléchargement de dataset. Aucun total « réconcilié » n'est inventé.[9]

**Leçon pour la pertinence.** §3.2–3.3 : revue des labels, correction des indices de pages et des omissions de pages multiples ; Table 2 mesure la cohérence d'annotation à deux granularités. Le recall de page ne suffit pas à certifier la présence du nombre, de l'unité et de la note. Un recouvrement géométrique peut lui aussi manquer la relation sémantique en-tête↔valeur : compléter par jugement humain de l'affirmation effectivement supportée.[9]

**Limite d'extrapolation.** Le protocole décrit le classement de pages/régions à l'intérieur du document pour une question ; ne pas traiter ses résultats comme un benchmark automatique d'un entrepôt global de millions de sources, ni comme un taux de citation fidèle. Le texte d'un VLM utilisé comme description doit rester marqué généré ; ses gains de rappel ne le rendent pas identique à la transcription source.[9]

**Droits/calcul.** L'annexe G limite les nouvelles annotations à la recherche académique et non commerciale ; une exploitation commerciale nécessite permission écrite des auteurs. Elle liste aussi les régimes distincts des corpus d'origine. L'accès public n'est donc pas une autorisation d'ingestion métier sans examen. Matériel et temps complet des expériences non établis par les passages consultés ; pas d'estimation locale inventée.[9]

## 7. Ce que ces articles ne couvrent pas

- **Formats natifs hétérogènes :** ce noyau porte surtout sur pages rendues, PDF ou tables HTML. Il ne démontre pas la conservation des formules XLSX, révisions DOCX, notes PPTX, ancres DOM ou sémantique Markdown. Reprendre le contrat de formats du rapport précédent, et ajouter des tests dédiés ; ne pas convertir toute l'identité source en numéro de page pour faire entrer le corpus dans les benchmarks.
- **Unités et nombres français :** tester virgule décimale, espace de milliers, signe moins, pourcentages, monnaies, milliers/millions, valeurs manquantes et notes. Ces exigences sont proposées ici ; aucun article retenu ne prouve leur couverture universelle.
- **ACL, versions et révocation :** ces publications ne constituent pas une preuve de sûreté de filtrage. Les filtres de droits/version doivent s'appliquer avant la recherche et lors de toute expansion contextuelle.
- **Déploiement local :** les matériels publiés sont des contextes d'expérience, pas des minima garantis. Aucun inventaire de ce poste ni test CPU/GPU Windows n'a été réalisé.
- **Licences :** « article accessible », « code libre », « poids utilisables » et « données redistribuables » sont quatre questions différentes. Les snapshots de branches courantes ne sont pas des commits épinglés. Tout composant aux droits non vérifiés reste **non qualifié**, pas implicitement autorisé.

## 8. Expériences contrôlées proposées — sans exécution à ce stade

Les variantes, critères et niveaux de budget ci-dessous sont des **propositions à approuver**. Conserver Qdrant, les mêmes partitions par famille de documents et les mêmes filtres. Commencer sur des documents publics autorisés ; pas sur le coffre. Aucun entraînement complet de publication n'est requis pour tester les principes.

| Expérience | Facteur isolé et témoins | Mesures et diagnostic attendus |
|---|---|---|
| **E1 — Structure sans retranscription** | Sur PDF natifs, structure identique avec contenu natif assigné aux cellules vs contenu OCR ; strate scan séparée, jamais utilisée comme faux témoin natif. | Exactitude valeur/signe/unité, erreurs d'assignation de cellule, omissions et boîtes valides ; coût OCR séparé. Vérifier si la transcription ou l'assignation casse le chiffre. |
| **E2 — Topologie canonique auditée** | Référence brute et référence canonique versionnées ; revue des fusions et cellules vides. Évaluer la même sortie sous chaque convention sans appeler cela un gain de modèle. | GriTS contenu/topologie/localisation, exactitude de table entière et exactitude en-têtes↔cellules. Publier désaccords de conventions avant scores. |
| **E3 — Cellule riche vs ligne plate** | À extraction et encodeur constants : ligne aplatie ; cellule+en-têtes immédiats ; cellule+chemins hiérarchiques+unité/notes. Même budget encodé et troncatures enregistrées. | Rappel des faits support, confusion entre branches homonymes, exactitude unité/période/version, taille des représentations. Le coût des tokens d'en-tête fait partie du résultat. |
| **E4 — Fermeture contextuelle bornée** | Mêmes candidats : cellule seule, cellule avec ancêtres/notes nécessaires, tableau entier. Prévoir questions multi-cellules et deux tableaux. | Couverture de l'ensemble minimal de preuves, précision des preuves affichées, budget contexte et double comptage des totaux. Comparer suffisant, insuffisant, contradictoire et hors périmètre. |
| **E5 — Représentation visuelle et fusion** | Texte seul, vecteur visuel unique appris, multivecteurs complets ; puis fusion tardive à checkpoint et corpus constants. Séparer fusion sans adaptation et modèle adapté. Pas de comparaison brute de scores ViDoRe/VisRAG. | nDCG/Recall au même cutoff, précision des preuves, rappel avant reranking, régressions sur pages denses et français ; coût encodeur, mémoire embeddings, index réel et lecture finale. |
| **E6 — Page trouvée ≠ preuve trouvée** | Comparer recherche directe de régions et cascade page→région, puis évaluation avec pages/régions oracle. Inclure absences de réponse et nombres identiques sous mauvais en-têtes. | Rappel page, rappel région, relation valeur–unité–en-têtes correcte, suffisance de tous les faits, exactitude réponse/calcul et support des citations séparément. Isoler le plafond du lecteur du défaut de candidats. |

### Contrôles transversaux à préenregistrer

- **Vérité terrain :** valeurs brutes, normalisations admises, cellules/en-têtes/notes nécessaires, réponse ou impossibilité, ancre et version. Une réponse numériquement juste issue d'une mauvaise cellule est une erreur de preuve.
- **Fuites :** garder source et variantes dégradées dans la même partition ; réserver un holdout qui n'alimente ni choix de chunk ni réglage de compression. Ne pas utiliser des étiquettes synthétiques seules pour prononcer l'acceptation.
- **Budgets équitables :** publier soit un même budget de candidats/coût, soit des courbes qualité–coût ; pas un seul cutoff choisi après coup. Un même k de pages et de cellules n'est pas un même budget informationnel.
- **Exact/ANN :** sur petit sous-corpus, recherche exacte témoin puis parcours Qdrant retenu ; ne pas imputer à l'encodeur une perte ANN ni à Qdrant un défaut OCR. Pas de changement de base recommandé.
- **Ressources :** chargement froid/chaud, rendu, OCR, encodage, présélection, MaxSim/reranking, reconstruction et lecture ; RAM/VRAM de pic, taille images/payloads/vecteurs/index, timeouts et échecs. Les ratios de mémoire des papiers ne remplacent pas cette mesure.
- **Statistique :** publier résultats par question/famille/langue, différences appariées et intervalles tenant compte des regroupements par document. L'abstention doit être rapportée avec la couverture et les faux positifs sans réponse ; aucun seuil universel de succès n'est déduit des papiers.

**Ordre proposé : E1–E3 → E4/E6 → E5.** Si les chiffres ou unités sont déjà faux dans les dérivés, le visuel doit servir de voie de contrôle et de preuve complémentaire, pas masquer le défaut du canonique.

## 9. Traçabilité de la recherche et réserves

Dossier de preuves unique relatif au dépôt : **`artifacts/research/academic-docintel-20261017T114959Z/`**.

- **`ledger.json`** : registre local grounded-citations ; aucun reset du registre global.
- **`retrieval-manifest.json`** : URL demandée/finale, date UTC, statut HTTP, taille et SHA-256 des sources ; PDF primaires conservés.
- **`reading-evidence.json`** : niveau de lecture par source, fichier lu, extrait littéral attaché au registre et résultat de validation de citation.
- **`quantitative-evidence.json`** : extraits littéraux supplémentaires des Tables 5 (PubTables), 2 (compression), 4 (MultiHiertt) et 4 (HiTab), avec protocole et repère exact ; aucun gain calculé mentalement.
- **`*.pdf` / `*.txt`** : textes intégraux récupérés et extractions de lecture ; les noms de base correspondent aux articles du tableau. Le texte extrait n'est pas une nouvelle vérité terrain.
- **`*-license.raw`, `*-status.raw`, `colpali-venue.raw`** : réponses primaires de licences et de statut ; snapshots non épinglés à un commit.
- **`citation-verification.txt`**, **`artifact-validation.json`** : reçus de vérification finaux.

Les premières extractions ont échoué sur un chemin supposé de `pdftotext` ; le chemin réellement présent a été utilisé, sans installation. Des encodages et caractères de contrôle ont nécessité une normalisation du **texte de lecture seulement** ; les PDF et réponses brutes sont conservés. Certaines tables en colonnes s'alignent mal dans ce texte : les scores ambigus ne sont pas retranscrits. Les quelques valeurs retenues ci-dessus proviennent de lignes identifiables et de commentaires explicites des tables, avec leur section et leur protocole. Les recherches ont utilisé des replis du moteur configuré ; aucune configuration n'a été modifiée.

**Bilan :** cette revue ajoute des hypothèses testables et une chaîne de citations, pas une preuve de performance de BorgKnowledge. Les points bloquants pour une qualification restent la vérité terrain française/hétérogène, les droits des artefacts exacts et la mesure locale des erreurs et ressources.

## Sources

[1] https://openaccess.thecvf.com/content/CVPR2022/papers/Nassar_TableFormer_Table_Structure_Understanding_With_Transformers_CVPR_2022_paper.pdf — tableformer
[2] https://openaccess.thecvf.com/content/CVPR2022/papers/Smock_PubTables-1M_Towards_Comprehensive_Table_Extraction_From_Unstructured_Documents_CVPR_2022_paper.pdf — pubtables
[3] https://arxiv.org/pdf/2407.01449v6 — colpali
[4] https://proceedings.iclr.cc/paper_files/paper/2025/file/3640a1997a4c9571cea9db2c82e1fc35-Paper-Conference.pdf — visrag
[5] https://aclanthology.org/2025.findings-acl.1003.pdf — patch-reduction
[6] https://aclanthology.org/2022.acl-long.454.pdf — multihiertt
[7] https://aclanthology.org/2022.acl-long.78.pdf — hitab
[8] https://openaccess.thecvf.com/content/CVPR2025/papers/Ouyang_OmniDocBench_Benchmarking_Diverse_PDF_Document_Parsing_with_Comprehensive_Annotations_CVPR_2025_paper.pdf — omnidocbench
[9] https://aclanthology.org/2025.emnlp-main.1576.pdf — mmdocir
[10] https://arxiv.org/pdf/2410.12628v1 — doclayout
[11] https://arxiv.org/abs/2410.12628v1 — doclayout-status
[12] https://proceedings.iclr.cc/paper_files/paper/2025/hash/99e9e141aafc314f76b0ca3dd66898b3-Abstract-Conference.html — colpali-venue
[13] https://raw.githubusercontent.com/microsoft/table-transformer/main/LICENSE — table-transformer-license
[14] https://raw.githubusercontent.com/opendatalab/DocLayout-YOLO/main/LICENSE — doclayout-license
[15] https://raw.githubusercontent.com/OpenBMB/VisRAG/master/LICENSE — visrag-license
[16] https://raw.githubusercontent.com/microsoft/HiTab/main/LICENSE — hitab-license
[17] https://raw.githubusercontent.com/psunlpgroup/MultiHiertt/main/LICENSE — multihiertt-license
[18] https://huggingface.co/vidore/colpali-v1.3/raw/main/README.md — colpali-license
