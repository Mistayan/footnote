# BorgKnowledge — Intelligence documentaire LAD/RAD et recherche de preuves

**Étude documentaire, 17 octobre 2026. Statut : recommandations, aucune implémentation ni mesure locale.**

**Périmètre autorisé :** sources publiques primaires, rédaction dans ce dépôt uniquement. Aucun coffre Obsidian ni document personnel consulté ou ingéré ; aucune installation, modification de configuration, exécution de modèle ou écriture dans Qdrant. Qdrant reste la base sélectionnée : la question est la qualité de la chaîne documentaire en amont et de la recherche, pas un nouveau comparatif de bases vectorielles.

## 1. Décision proposée

Retenir **Docling comme premier candidat de conversion structurée**, **PaddleOCR/PP-StructureV3 comme challenger OCR/layout**, et **MinerU comme challenger complet à versionner strictement**. Ces trois solutions disposent d'éléments techniques officiels pour la structure documentaire ; ce choix de présélection n'est pas un classement de qualité sur BorgKnowledge.[2][4][6]

Ajouter ensuite une **branche visuelle page/image ColPali ou ColQwen**, sans supprimer la branche texte, lorsque les questions exigent graphiques, schémas ou disposition spatiale. ColPali est une méthode de recherche de pages par représentations visuelles multivecteurs, pas un convertisseur sémantiquement fidèle ni un moteur de réponse autonome.[10]

**Architecture recommandée :** originaux immuables → routage par format et région → extraction native/OCR/layout → modèle documentaire canonique + dérivés visuels → blocs/chunks traçables → candidats texte et éventuellement visuels → fusion/classement → preuves contextualisées ou abstention. Les originaux et la provenance doivent être indépendants de l'index Qdrant, afin de pouvoir reconstruire tous les dérivés.

**Barrière d'acceptation :** viser au moins **90 % de précision des preuves effectivement présentées**, avec couverture et incertitude publiées. Ce seuil n'est atteint ni par « 90 % d'OCR », ni par un score OmniDocBench, ni par le rappel ANN. Cette étude ne démontre aucun taux de précision pour BorgKnowledge.

## 2. LAD/RAD : séparer les fonctions et les erreurs

Dans ce rapport, RAD désigne le routage/reconnaissance du type et de la structure documentaire ; LAD couvre lecture, transcription et extraction. Ce sont des conventions de travail explicites, pas une prétention à uniformiser tous les usages de ces sigles.

| Couche | Résultat attendu | Erreur à identifier séparément |
|---|---|---|
| Reconnaissance/routage | Format réel, langue, natif/scan/mixte, structure présumée | Faux scan, mauvaise langue, mauvaise famille documentaire |
| OCR | Texte ancré dans une image/région | Caractères faux, lignes omises, duplication |
| Layout et parsing | Blocs typés, ordre, cellules, légendes | Colonnes entremêlées, mauvais parent, en-tête perdu |
| Recherche | Preuve applicable à la question et à la version | Résultat thématique mais non probant, version erronée |
| Réponse | Affirmations soutenues et citations exactes | Inférence non justifiée, nombre inventé, citation inadéquate |

OmniDocBench évalue notamment texte, tableaux, formules et ordre de lecture par des métriques distinctes ; ViDoRe évalue la recherche de pages, avec notamment nDCG@5, Recall@K et MRR. Leur objet n'est donc pas interchangeable.[9][10]

**Limite fondamentale de conception :** une conversion sémantique universellement sans perte n'est pas un engagement tenable : rendu, position, formules, images, révisions, liens et relations implicites ne se réduisent pas à du texte. La documentation Docling appelle « lossless » la **sérialisation du DoclingDocument en JSON** ; cela ne prouve pas une conversion sans perte de l'original.[1][2] La garantie à rechercher est : **octets originaux préservés, dérivés auditables, pertes et inconnues déclarées**.

## 3. Traitement par famille documentaire

Les règles de cette section sont des **exigences proposées pour BorgKnowledge**, non des capacités garanties de chaque outil.

### PDF natif

- Exploiter la couche texte et ses positions, puis analyser l'ordre de lecture et les tableaux ; un PDF contenant du texte n'est pas nécessairement correctement extractible.
- Contrôler colonnes, ligatures, césures, caractères spéciaux, code, notes et texte invisible. Ne pas remplacer systématiquement un texte natif correct par une retranscription OCR.
- Rendre les pages pour la vérification et la recherche visuelle ; conserver numéro physique de page et étiquette imprimée séparément.

Docling décrit une chaîne PDF associant backend, analyse de mise en page, OCR et reconnaissance de structure de tableaux ; TableFormer associe les cellules PDF à la structure prédite, évitant une retranscription inutile du texte natif des tableaux.[13]

### PDF scanné, photographié ou mixte

- Détecter par **région**, pas seulement par fichier : page native avec capture embarquée, tampon ou annotation image ; scan avec couche OCR existante de mauvaise qualité.
- Conserver image d'origine, transformation de rotation/redressement, résolution et correspondance des coordonnées. L'OCR ne doit ni doubler le texte natif ni laisser une région image silencieusement vide.
- Choisir explicitement les langues, tester le français accentué, chiffres, unités et identifiants techniques. Une confiance OCR ne constitue pas une probabilité calibrée de pertinence.
- Sortir `partial`, `unsupported` ou `needs_review` plutôt que rendre un succès global trompeur.

Real5-OmniDocBench reconstruit physiquement les pages d'OmniDocBench sous cinq conditions — numérisation, déformation, photographie d'écran, illumination et inclinaison — pour isoler les dégradations ; les scans propres ne suffisent donc pas comme unique strate de test.[22]

### Office : DOCX, PPTX, XLSX et anciens formats

Docling documente les formats OOXML DOCX/XLSX/PPTX ; la liste courante mentionne également les anciens DOC/XLS/PPT via LibreOffice. MinerU courant documente un parsing natif local Flash pour Office et d'autres formats, distinct de ses parcours PDF/images.[1][4]

Exigences proposées :

- **DOCX :** titres/listes/tableaux, notes et liens ; politique explicite pour commentaires, suivi de modifications et texte masqué. Ancre native = partie OOXML + paragraphe/run/table/cellule, pas un numéro de page inventé.
- **PPTX :** diapositive, forme, groupe, notes et légende ; préserver le rendu pour flèches, regroupements et hiérarchie spatiale. Un texte extrait hors de sa forme peut changer de sens.
- **XLSX :** feuille, plage/cellule, valeur, formule, résultat mis en cache, unité et en-têtes ; distinguer cellules masquées et visibles. Ne pas exécuter macros, liens externes ou recalculs implicitement.
- **Formats anciens :** conversion éventuelle dans une étape isolée, consentie et versionnée ; conserver le fichier source et le fichier converti. Aucune installation de LibreOffice n'a été effectuée ici.
- Pour un rendu Office paginé, enregistrer moteur/version/polices et relier les pages rendues aux ancres natives ; le rendu n'est pas l'identité canonique du document.

### HTML et Markdown

Docling annonce HTML et Markdown parmi les entrées ; MinerU distingue parsing HTML/MHTML et lecture directe des formats texte tels que Markdown.[1][4]

Exigences proposées : conserver URL finale, date, octets, encodage, base des liens, ancres DOM/chemin de nœud et plages d'octets ou caractères dans le snapshot. Pour Markdown : fichier, révision, offsets et lignes, titres, blocs de code et liens. Ne pas lancer JavaScript, charger des ressources externes ou suivre récursivement les liens sans politique explicite. Un snapshot HTML n'implique pas la capture de tout le rendu dynamique.

### Tableaux, formules, schémas et images

- **Tableau :** conserver grille de cellules, `rowspan`/`colspan`, en-têtes hiérarchiques, unités, légende, notes et boîtes ; CSV ou Markdown seul ne suffit pas pour les cellules fusionnées.
- **Recherche tabulaire :** chunks de lignes/plages avec en-têtes et unités répétés ; joindre le tableau parent. Tester séparément des questions exigeant plusieurs lignes/pages. Ne pas créer une association valeur/en-tête seulement parce que les tokens sont proches.
- **Formule/code :** garder transcription candidate, image et texte exact ; contrôler symboles, indices, espaces significatifs et ponctuation. Une similarité textuelle globale masque des erreurs critiques.
- **Schéma :** préserver image entière, crop et légende ; l'OCR des étiquettes ne reconstitue pas automatiquement les flèches et relations. Une description VLM doit être marquée **générée**, liée à l'image et non élevée au rang de fait source.
- **Graphique :** ne pas présenter une valeur inférée visuellement comme une cellule exacte ; préserver axes, échelle, légende et incertitude.

PP-StructureV3 documente reconnaissance de tableaux/formules, analyse de layout, restauration de l'ordre et compréhension de graphiques ; cela justifie son inclusion dans le test, pas une garantie d'extraction de tous les schémas métier.[6]

## 4. Modèle canonique : adopter une base, ajouter la traçabilité BorgKnowledge

DoclingDocument représente textes, tableaux et images, hiérarchie, séparation du corps et du mobilier, boîtes **si disponibles**, et provenance. C'est une base réaliste, mais pas une raison de supposer des coordonnées présentes pour chaque format.[2]

**Contrat proposé**, indépendant du choix final de parseur :

| Objet | Champs/relations nécessaires |
|---|---|
| Source immuable | `source_id`, URI d'origine autorisée, révision, date de capture, MIME détecté, taille, SHA-256, emplacement des octets, droits/ACL |
| Exécution | `run_id`, outil/version/commit, backend, modèles et hashes, langues, paramètres, dispositif, date, avertissements, statut |
| Document | Identifiant de version, titre/langue avec origine explicite/inférée, relations document→section→bloc ; version métier et périmètre validés |
| Bloc | ID stable dans une version, type, parent, ordre de lecture, contenu brut/extrait/normalisé séparé, lien de transformation |
| Ancre source | PDF : page + boîte/polygone + repère/origine/unité/rotation ; Office : partie/objet/cellule ; HTML : snapshot + DOM ; texte : offsets/lignes |
| Média | Image/page/crop, hash, dimensions/résolution, relation figure↔légende, source et transformation géométrique |
| Tableau | Cellules, spans, en-têtes et relations, boîtes, texte brut ; fragments multipages liés explicitement |
| Incertitude | Scores fournis par moteur, portée de chaque score, omissions, langue douteuse, état de revue ; `null` si inconnu |
| Chunk | Blocs sources et segments, parent, texte réellement encodé, tokenizer, budget/troncature, en-têtes ajoutés, modèle et version d'embedding |

**Règles impératives proposées :**

1. Distinguer offsets du fichier brut, du texte extrait et du texte normalisé ; conserver une table de correspondance, y compris les suppressions/ajouts. Une césure supprimée change les offsets.
2. Ne pas inventer un offset caractère dans les octets PDF pour une transcription OCR : sa preuve est l'image/région ; un offset local dans le texte OCR reste possible.
3. Conserver un journal de transformations et des relations `derived_from` ; les corrections humaines créent une nouvelle version, pas une réécriture de l'original.
4. Séparer champs observés, inférés et générés ; filtrage dur seulement sur métadonnées validées. Conserver les versions concurrentes au lieu d'un écrasement « dernier document ».
5. Quarantainer erreurs et contenus non pris en charge ; ne pas les compter comme correctement indexés. Originaux accessibles selon ACL, jamais via un chemin arbitraire fourni par un document.
6. Le Markdown est un dérivé lisible ; JSON canonique et images assurent une description plus riche, mais seule la préservation des octets garantit l'original.

## 5. Outils : comparaison réaliste, matériel et licences

| Candidat | Éléments établis dans les sources officielles | Place proposée et réserves |
|---|---|---|
| **Docling standard** | Formats multiples et modèle unifié ; code MIT, licences des modèles à vérifier séparément ; Windows/Linux/macOS ; publication décrivant exécution CPU et accélérateurs.[1][2][3][13] | Premier candidat CPU/Windows et canonique. Mesurer OCR et tableaux coûteux ; ne pas extrapoler les timings de la publication aux versions actuelles ou à cette machine. |
| **MinerU courant** | Dépôt actuel : tiers Flash/Basic/Standard/Advanced, formats natifs Office/HTML, ONNX CPU et llama.cpp/Vulkan ; parcours PyTorch accélérés.[4] | Challenger complet. Ne pas appliquer sans vérification les anciens guides `magic-pdf` ou le tableau des backends 2.x à la documentation courante. Format de sortie et ancres à tester. |
| **PaddleOCR / PP-StructureV3** | Pipeline modulaire layout/OCR/tableaux/formules/ordre/graphiques ; CPU possible, GPU recommandé pour performances ; dépôt sous Apache-2.0.[6][7] | Challenger pour régions scannées et structure ; ne remplace pas à lui seul une politique d'ancres natives Office. Vérifier runtime, modèles, dépendances et capacités linguistiques exactes. |
| **Tesseract** | OCR avec sorties texte, hOCR, TSV, ALTO et PAGE ; code Apache-2.0.[20] | Témoin OCR simple et auditable ; ces sorties ne constituent pas une compréhension automatique des tableaux ou schémas. La distribution Windows et les données linguistiques restent à qualifier. |
| **ColPali / ColQwen** | Recherche visuelle multivecteurs, distincte du parsing ; cartes modèles avec contraintes de backbone et adaptateur.[10][11][18] | Branche expérimentale complémentaire, pas candidat unique CPU par défaut ni substitut au modèle canonique. |

### Attention particulière : MinerU a évolué

Le README officiel récupéré présente pour Basic ONNX environ **0,8 GB de modèles et 2 GB de RAM minimum** ; Standard/Advanced ONNX + llama.cpp environ **2 GB de modèles et 8 GB de RAM**, CPU possible avec Vulkan recommandé. Les parcours PyTorch + llama.cpp ou vLLM/lmdeploy/mlx indiquent **16 GB de RAM et 8 GB+ de VRAM**. Ce sont des indications du projet pour ces parcours, **pas des mesures sur ce poste ni une garantie de débit**.[4]

Sa licence courante est **MinerU Open Source License**, basée sur Apache-2.0 avec conditions supplémentaires : licence commerciale distincte au-delà de **100 millions d'utilisateurs actifs mensuels** ou de **20 millions USD de revenus mensuels** consolidés avec affiliés ; attribution pour les services en ligne fournis à des tiers. Ne pas résumer cette licence à « Apache-2.0 » sans ces conditions ; revue juridique avant diffusion.[5]

### Windows, CPU et GPU : conclusion opérationnelle

- **Commencer CPU**, sur lots contrôlés, en désactivant seulement les traitements prouvés inutiles et en consignant cette décision. La publication Docling montre que l'OCR peut dominer le coût CPU ; il s'agit d'une observation sur sa configuration publiée, non d'une prédiction de temps local.[13]
- **PaddleOCR :** support CPU documenté, mais la compatibilité de chaque module/runtime Windows doit être vérifiée. Le minimum Python annoncé par le paquet ne prouve pas l'existence de toutes les roues et accélérations pour une version Python donnée.[6][8]
- **MinerU :** son chemin ONNX/llama.cpp/Vulkan actuel interdit de conclure « GPU obligatoire » pour tous les parcours ; le README précise aussi un traitement spécifique des builds torch GPU sur Windows.[4]
- **Visuel :** les exemples ColQwen utilisent CUDA/MPS et bfloat16 ; la carte ne donne pas un débit CPU Windows garanti. Le nombre de patchs et la résolution augmentent le coût mémoire. GPU à envisager après mesure, pas comme prérequis acquis sur cette machine.[11]
- **Ne pas confondre GPU du modèle et base vectorielle** : encoder les pages visuelles et stocker/reclasser leurs vecteurs sont des étapes distinctes. Aucun GPU, driver, service ou mémoire locale n'a été inventorié pendant cette étude.
- Fixer avant essais OS, Python/runtime, threads, backend, versions, poids, résidence des modèles, taille de batch et budgets RAM/VRAM/disque. Mesurer chargement à froid et régime chaud séparément.

### Licences visuelles : point bloquant potentiel

La carte **ColPali v1.3** distingue adaptateurs MIT et backbone PaliGemma sous licence Gemma. La carte **ColQwen2.5 v0.2**, malgré son en-tête MIT, distingue adaptateurs MIT et backbone Qwen sous **Qwen RESEARCH LICENSE AGREEMENT**.[18][11] Le fichier LICENSE officiel du **Qwen2.5-VL-3B-Instruct** concerné limite l'usage accordé aux fins non commerciales et demande une licence pour l'usage commercial : ce checkpoint ne doit pas être déclaré automatiquement compatible avec une exploitation commerciale.[19] Vérifier chaque checkpoint exact, pas la famille « Qwen » dans son ensemble.

## 6. Recherche structurée et visuelle avec Qdrant conservé

### Branche texte et hiérarchie — recommandation

Indexer des **enfants cohérents** pour retrouver la preuve précise, puis charger le **parent pertinent** : section, tableau ou page. Le parent apporte le contexte ; il ne doit pas transformer tous ses enfants en résultats artificiellement pertinents. Dédupliquer frères/versions et limiter le nombre de preuves par source.

Docling fournit un chunker hiérarchique et un HybridChunker qui ajoute ajustements selon tokenizer et fusion conditionnelle ; sa documentation décrit également répétition d'en-têtes de tableaux et gestion des débordements.[16] Pour BorgKnowledge, aligner le tokenizer sur le modèle réellement utilisé et vérifier le texte encodé **après** ajout du titre, du chemin de section et des unités. Compter toute troncature ; les offsets du chunk doivent pointer vers les blocs, pas uniquement vers sa sérialisation.

Comparer sous protocole figé : dense seul ; sparse/lexical + dense ; fusion puis reranking. Préserver les termes exacts pour commandes, versions et références. Ni cosinus, ni RRF, ni score de reranking ne sont à considérer comme probabilités calibrées. Un filtre ACL/version/périmètre doit être appliqué à toutes les branches et à l'expansion parentale.

### Branche visuelle — mécanisme établi et limites

ColPali encode des pages en plusieurs vecteurs de patchs et compare séparément les tokens de requête aux patchs par interaction tardive de type MaxSim. Il exploite ainsi des indices visuels que la seule transcription peut perdre ; ViDoRe porte sur le classement de pages, pas sur la restitution exacte d'une cellule ou d'une relation de diagramme.[10]

ColQwen2.5 v0.2 accepte des résolutions dynamiques, avec au plus **768 patchs image** dans la configuration décrite ; davantage de patchs améliore certains résultats au prix de mémoire. La carte signale aussi une différence de préfixe de requête entre versions de `colpali-engine` et configuration Sentence Transformers : **figer le processeur et le format de requête**, pas seulement le nom du modèle.[11]

La réplication indépendante de Qiao et al. reproduit les gains de late interaction, mais souligne ses inefficacités d'inférence et analyse les dépendances au contenu textuel/visuel. Cela renforce l'intérêt d'un essai ciblé plutôt qu'une adoption universelle.[14]

Qdrant documente multivecteurs `MAX_SIM` et un schéma de reranking avec HNSW désactivé sur le champ multivecteur (`m=0`) pour éviter d'indexer chaque token ; le champ dense conserve son index et fournit les candidats.[12] **Proposition BorgKnowledge :** points de chunks texte et points de pages visuelles reliés par `source_version_id`, `page_id`, `block_ids`, avec reconstruction de la preuve hors Qdrant.

**Piège critique :** reclasser uniquement les candidats texte ne retrouvera jamais une page purement graphique absente de ces candidats. Comparer une branche visuelle de génération de candidats indépendante : MaxSim exact sur petit sous-corpus autorisé pour établir un témoin, puis une méthode de présélection visuelle à qualifier. Mesurer son rappel avant reranking. Ne pas prétendre qu'un simple moyennage des patchs reproduit le modèle entraîné.

Une bonne page récupérée n'est pas encore une réponse : ouvrir le crop/parent et vérifier l'affirmation par extraction ou lecture multimodale contrôlée. Une carte de similarité patch/token n'est pas une annotation de provenance certaine. Stockage et latence doivent inclure les vecteurs multiples, les images et l'étape de lecture, non la seule recherche ANN.

## 7. Publications et évaluations : ce qu'elles prouvent réellement

| Source primaire lue | Apport | Limite pour décider ici |
|---|---|---|
| **Docling, toolkit (2025, v1)** | Architecture locale, modèle structuré, TableFormer et décomposition des coûts CPU/GPU.[13] | Publication historique : résultats non transférables directement à la version courante, à Windows ou au français. |
| **OmniDocBench, Ouyang et al.** | Évaluation par composants et attributs, texte/tables/formules/ordre ; matching des sorties.[9] | Il faut figer version du dataset, évaluateur et modèles ; certains éléments sont ignorés dans l'évaluation. |
| **Dépôt OmniDocBench courant** | Historique v1.0/v1.5/v1.6 et définitions de métriques ; Overall agrège texte, TEDS et CDM.[17] | Pas une précision de recherche ; ne pas comparer une ligne ancienne Docling à une ligne MinerU récente comme un duel contrôlé. |
| **Real5-OmniDocBench (2026)** | Correspondance des mêmes pages sous cinq conditions physiques ; **6 775** variantes issues de **1 355** pages.[22] | Hérite des annotations de base ; tester déformation ne résout pas leur éventuel défaut. |
| **PureDocBench (2026, v1)** | Sources HTML/CSS et annotations liées, versions propres et dégradées ; critique documentée de la qualité des annotations existantes.[15] | Prépublication ; génération source ne couvre pas toute la variété des documents authentiques, prédominance chinois/anglais. |
| **ColPali / ViDoRe** | Mesure du classement de pages visuellement riches ; méthode multivecteur et ablations.[10] | nDCG élevé ne certifie ni P@k à 90 %, ni exactitude de réponse, ni qualité d'extraction. |
| **Qiao et al. (2025, v1)** | Réplication et analyse de la recherche visuelle à interaction tardive.[14] | Coûts et résultats dépendent des modèles, des corpus et de la couverture visuelle. |

**Pourquoi ne pas publier un tableau de « champions » ?** Les sources officielles ne constituent pas un essai commun figé sur le corpus français BorgKnowledge. Les versions de MinerU et d'OmniDocBench ont changé ; même les chiffres de snippets de moteurs de recherche peuvent être périmés. Cette étude privilégie les pages effectivement récupérées et archivées. Aucun chiffre de débit ou de pertinence n'a été fabriqué.

**Angle mort à traiter :** OmniDocBench exclut certains éléments de son scoring, dont mobilier et éléments aux placements ambigus ; l'ordre de lecture évalué ne couvre pas tous les objets.[9] Pour BorgKnowledge, notes, légendes, unité ou renvoi de version peuvent pourtant être la preuve décisive : ajouter des tests d'omission et de traçabilité au-delà du score publié.

## 8. Expérience contrôlée proposée — pas de construction maintenant

Les tailles et seuils ci-dessous sont des **choix de protocole à approuver**, pas des résultats mesurés.

### Étape A — corpus public et contrat d'acceptation

Constituer un petit pilote public autorisé, puis un corpus de qualification plus large, stratifié : français/anglais ; PDF natif multicolonne ; scans propres/dégradés/mixtes ; DOCX/PPTX/XLSX ; HTML/Markdown ; tableaux complexes ; code/formules ; schémas et graphiques. Inclure versions contradictoires, sources non applicables et questions sans réponse. Ne pas ingérer le coffre pour « accélérer le test ».

Geler droits, octets/hashes, ancres, partitions par document/famille, questions et jugements. Garder toutes les variantes dégradées d'une même page dans la même partition. Prévoir annotation indépendante et arbitrage ; éviter un jeu de labels construit uniquement autour des extraits déjà retrouvés.

### Étape B — extraction seule

Comparer Docling standard, MinerU avec moteur/tier figé et PP-StructureV3 sur les **mêmes documents** ; Tesseract témoin sur la strate OCR. Vérifier séparément les ancres Office et HTML/Markdown, au lieu de rendre artificiellement tout le corpus en PDF.

Mesurer : CER/WER avec règles de normalisation explicites ; blocs omis/dupliqués ; ordre de lecture ; cellules/en-têtes/spans et nombres/unités ; code exact ; erreurs de version ; couverture des régions ; taux d'ancres valides ; temps/page à froid/chaud, RAM/VRAM maximale, taille des dérivés, erreurs et timeouts. Les métriques TEDS/CDM d'OmniDocBench peuvent compléter les contrôles ciblés, pas les remplacer.[9]

Faire relire les cas critiques : signe négatif, décimale, unité, flèche et exception en note. Une excellente moyenne OCR avec une unité fausse reste un défaut bloquant pour cette preuve. Rejeter les passages non retraçables ou signaler leur statut incomplet.

### Étape C — retrieval texte figé

Après choix des extractions admissibles : comparer découpage plat et hiérarchique, puis dense et hybride, puis reranking. Changer **un facteur à la fois** ; garder Qdrant et les mêmes filtres. Comparer à une recherche exacte des vecteurs pour isoler une erreur ANN d'une erreur de pertinence.

Pour chaque question : texte, réponse attendue ou absence, top résultats ordonnés avec extraits/pages/boîtes, version/périmètre, labels pertinents/non pertinents/non jugés, scores bruts, P@1/P@3/P@5, rappel des preuves si jugements suffisamment complets, et catégorie de panne. Un résultat qui parle du sujet sans répondre à la question est non pertinent pour l'acceptation.

### Étape D — ajout visuel ciblé

Sur les mêmes partitions, comparer texte seul, visuel seul et union des deux ; contrôler résolution, patchs, taille des candidats, budget mémoire et coût de lecture finale. Inclure pages riches en schémas **et témoins purement textuels**. Rapporter les gains et régressions par famille, notamment français et scans dégradés. Toute quantification/compression/pruning devient une variante distincte, non une optimisation supposée neutre.

### Étape E — décision au seuil de 90 %

Définir avant l'essai l'unité : **preuve affichée dans un résultat retenu** ; publier précision micro et macro par question/famille et aux cutoffs réellement affichés. Ne pas sélectionner après coup le cutoff qui réussit. Si le produit génère une réponse, mesurer aussi précision des affirmations et support des citations : c'est une autre métrique.

Le gate proposé est : précision des preuves présentées au moins 90 %, incertitude documentée, couverture minimale explicitement approuvée, taux de fausse acceptation sur questions sans réponse rapporté, aucune violation ACL/version connue. Pour une qualification exigeante, demander que la borne inférieure d'un intervalle de confiance convenu dépasse le seuil ; tenir compte du regroupement par question/document, plutôt que supposer tous les passages indépendants.

Une politique qui s'abstient presque toujours ne réussit pas. Publier taux d'abstention, couverture des questions répondables, faux positifs sans réponse et rejets injustifiés ; calibrer seuils sur développement seulement. Un score RRF ou MaxSim ne suffit pas comme confiance. Si le gate échoue, ne pas activer le parcours et diagnostiquer extraction, structure, candidats, classement, version ou preuve absente avant toute optimisation de vitesse.

Toute consultation du holdout en fait un jeu de diagnostic pour la variante suivante : nouveau test indépendant nécessaire pour une revendication de généralisation. Conserver les runs, paramètres et erreurs ; ne pas remplacer l'historique par un seul « latest ».

## 9. Livrables d'une future qualification et limites de cette étude

**À produire plus tard, après accord :** manifeste de corpus public et droits ; références d'extraction ; modèle canonique validé ; rapport de licences par code/poids/runtime ; matrices de qualité et de ressources ; résultats par question avec preuves ; décision d'activation signée ou refus motivé. Ce rapport ne construit ni pipeline ni service et n'ingère aucune documentation privée.

**Limites explicites :** pas d'exécution des outils candidats ; matériel local non inventorié ; compatibilité et performances Windows non vérifiées expérimentalement ; pas de résultat de recherche à 90 % revendiqué ; pas d'avis juridique. La page HTML de l'étude arXiv `2604.04948v1` a renvoyé 404 et n'est pas utilisée pour étayer les conclusions. Les pages amont non versionnées sont des snapshots datés, pas des engagements de stabilité.

## 10. Dossier de preuves et reproductibilité de la recherche

Les captures HTML identifient les versions **OmniDocBench `2412.07626v2`** et **ColPali `2407.01449v6`** derrière leurs URL non suffixées ; ces versions observées et les hashes du manifeste fixent l'évidence lue.[9][10] Les autres publications citées par URL suffixée gardent leur suffixe. Les snapshots des dépôts et cartes modèles sur branche `main`/`master` doivent être repinnés à un commit avant une expérimentation, sans remplacer ces captures historiques.

Dossier relatif au dépôt : **`artifacts/research/docintel-20261017T113748Z/`**.

- `ledger.json` : numérotation locale des sources, sans toucher au registre global.
- `retrieval-manifest.json` : URL demandée/finale, statut, date UTC, SHA-256 des octets et taille du texte extrait pour chaque source récupérée.
- `page-NN.raw` et `page-NN.txt` : réponse primaire et texte dérivé conservés ; seuls les extraits effectivement lus fondent les affirmations.
- `retrieve.py` : capture publique reproductible via bibliothèque standard, sans ingestion ni installation. Les snapshots, pas une relance ultérieure, sont l'évidence de ce rapport.
- `source-01.json` à `source-05.json` : erreurs initiales de `web_extract`, conservées pour transparence. Le backend configuré ne pouvait pas extraire ; repli sur récupération HTTP directe sans changement de configuration. Les deux pages PaddleOCR ont redirigé vers HTTP : provenance visible dans le manifeste, à renforcer par récupération TLS avant de figer des dépendances.
- Un vérificateur de citations et ses reçus accompagnent ce dossier ; les numéros sont générés par le registre. Les scripts de recherche n'ont aucune instruction d'installation ou de lancement des produits candidats.

**Conclusion :** commencer par fidélité et provenance, puis mesurer la pertinence ; ajouter le visuel pour les vrais besoins visuels. Qdrant peut accueillir le classement multivecteur, mais ne répare ni OCR abîmé ni preuve omise. Aucun choix de parseur ne justifie de supprimer les originaux.

## Sources

[1] https://docling-project.github.io/docling/usage/supported_formats
[2] https://docling-project.github.io/docling/concepts/docling_document
[3] https://github.com/docling-project/docling
[4] https://github.com/opendatalab/MinerU
[5] https://raw.githubusercontent.com/opendatalab/MinerU/master/LICENSE.md
[6] https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html
[7] https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/main/LICENSE
[8] https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/installation.html
[9] https://arxiv.org/html/2412.07626
[10] https://arxiv.org/html/2407.01449
[11] https://huggingface.co/vidore/colqwen2.5-v0.2/raw/main/README.md
[12] https://qdrant.tech/documentation/tutorials-search-engineering/using-multivector-representations
[13] https://arxiv.org/html/2501.17887v1
[14] https://arxiv.org/html/2505.07730v1
[15] https://arxiv.org/html/2605.07492v1
[16] https://docling-project.github.io/docling/concepts/chunking
[17] https://github.com/opendatalab/OmniDocBench
[18] https://huggingface.co/vidore/colpali-v1.3/raw/main/README.md
[19] https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/raw/main/LICENSE
[20] https://github.com/tesseract-ocr/tesseract
[22] https://arxiv.org/html/2603.04205v1
