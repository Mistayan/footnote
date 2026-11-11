# BorgKnowledge — Revue académique thématique du retrieval

**17 octobre 2026 — recherche documentaire, pas implémentation.** Qdrant reste le backend expérimental. Aucune installation, exécution de modèle, ingestion, lecture de vault ou modification du code/runtime. Les coûts et effets locaux des méthodes ci-dessous restent inconnus.

## Synthèse de décision

**Priorité : preuves applicables et candidats utiles, puis classement et abstention ; pas migration de stockage.** La littérature justifie des expériences, pas une promesse de précision ≥ 90 %. Il faut distinguer retrieval de passages, exactitude d’une réponse et fidélité des citations.

Les deux études existantes ont été lues : [QDRANT-RELEVANCE-RESEARCH.md](QDRANT-RELEVANCE-RESEARCH.md) et [DOCUMENT-INTELLIGENCE-RESEARCH.md](DOCUMENT-INTELLIGENCE-RESEARCH.md). Elles couvrent déjà APIs Qdrant, cartes E5/BGE, OCR/layout, parent–enfant et contextualisation industrielle. Le présent complément apporte **13 études regroupées en quatre thèmes**, des comparaisons académiques et leurs limites ; il ne reproduit pas un catalogue d’outils.

**Point de départ local, pas nouvelle mesure :** le briefing de cette mission donne top1 **0,500**, MRR **0,611**, recall5 **0,708** sur un holdout déjà réutilisé. Le rapport antérieur confirme top1 0,5000 et macro recall5 0,7083 sur les 12 répondables du holdout. MRR 0,611 vient du briefing, non d’un recalcul ici. **La valeur 0,64 évoquée auparavant n’est pas une métrique courante établie et n’est pas retenue.** Ces données sont diagnostiques, non une validation indépendante. Les labels incomplets et les mauvaises versions empêchent de convertir ces scores en précision exhaustive.

### Matrice de décision compacte — propositions BorgKnowledge

| Piste | Problème visé | Évidence utile | Coût et limite dominante | Décision |
|---|---|---|---|---|
| Structure + contexte déterministe | Preuve coupée, titre/version perdu | RAPTOR distingue granularités ; late chunking préserve le contexte.[16][2] | Réindexation ; contexte inapplicable peut contaminer un enfant | Premier témoin, sans génération |
| Late chunking | Références inter-chunks | Comparaison même modèle/mêmes frontières, gains mais exceptions.[2] | Encodage long et accès aux états token-level | Pilote après témoin structurel |
| HyDE / multiquery contraint | Formulation FR→EN, preuve absente des candidats | HyDE contrôlé ; RAG-Fusion surtout qualitatif.[4][6] | Génération online, dérive de version/identifiant | Conditionnel aux échecs de rappel |
| Décomposition | Question réellement composée | UniRAG, ablations de pipeline.[5] | Plusieurs recherches et générations ; gain non attribuable à la seule décomposition | Strate multi-preuves uniquement |
| Dense + lexical exact, puis cross-encoder multilingue | API rare, négation, ordre erroné | SPLADE pour mismatch ; mMARCO pour reranking multilingue.[7][9] | Sparse appris ≠ piste littérale ; paires coûteuses | Prioritaire avant gros graphe |
| Late interaction | Alignements fins terme/contexte | ColBERTv2, retrieval et compression documentés.[8] | Vecteurs par token ; compression native non automatiquement transférée | Challenger, pas défaut |
| Filtres d’applicabilité + conflit explicite | Version erronée, preuves concurrentes | FreshQA / WhoQA motivent des tests distincts.[10][11] | Date ≠ compatibilité ; détection de contradiction non prouvée | Barrière obligatoire du protocole |
| Abstention calibrée | Accepter une proximité sans preuve | Selective QA : risque–couverture sous changement de domaine.[12] | Labels nouveaux ; calibration fragile hors distribution | Après fixation du retriever/reranker |
| RAPTOR complet / CDE / GraLC-RAG | Synthèse ou adaptation de domaine résiduelle | Mécanismes distincts, pas interchangeables.[16][3][17] | Résumés, modèles spécifiques, maintenance ou protocole fragile | Recherche différée |

## Méthode de lecture et statut des preuves

Revue **thématique ciblée, non systématique exhaustive**. Découverte sur ACL Anthology, SIGIR/ACM et papier auteur ouvert, OpenReview, arXiv et Semantic Scholar. Recherche de titres et de travaux voisins ; sélection selon mécanisme testable et proximité avec les erreurs locales. Les snippets ne servent pas de preuve de tableaux. Les versions effectivement capturées sont indiquées ; « récent » ne signifie ni meilleur ni état de l’art établi.

**VERIFIED** signifie ici lieu/année de publication constatés dans les actes ou le PDF officiel, **pas réplication indépendante des résultats**. « Prépublication / lieu non vérifié » n’affirme pas qu’aucune publication ultérieure n’existe. « Texte intégral disponible, sections lues » signifie que méthodes/résultats indiqués ont été examinés, pas lecture exhaustive de chaque annexe. Aucun résultat numérique ci-dessous n’est tiré d’un abstract seul.

Le PDF OpenReview RAPTOR a renvoyé 403, puis sa page un challenge ; le texte a été récupéré dans les actes ICLR. Semantic Scholar a servi à la découverte de ColBERTv2, mais son téléchargement direct a renvoyé 202 et zéro octet : les métadonnées et résultats retenus viennent d’ACL, pas de cette réponse vide. Les notices ICLR CDE sont lues au niveau **abstract/métadonnées** uniquement ; les résultats viennent du texte arXiv v4.[13][3]

## 1. Hiérarchie, structure et embeddings contextualisés — quatre études

### 1.1 RAPTOR — hiérarchie sémantique et résumés

**Parth Sarthi, Salman Abdullah, Aditi Tuli, Shubh Khanna, Anna Goldie, Christopher D. Manning — 2024, ICLR, VERIFIED.** Source : PDF intégral des actes ; sections 3–4 et tables 1–3 lues.[16]

- **Mécanisme :** embedding, clustering souple et résumé récursif ; feuilles originales plus nœuds synthétiques. La hiérarchie est sémantique, pas une restitution de la table des matières. La recherche « collapsed tree » compare les niveaux ensemble.[16]
- **Mesure retenue :** table 2, UnifiedQA-3B, même retriever SBERT : QuALITY accuracy **54,9→56,6 %**, soit **+1,7 point** ; QASPER Answer F1 **36,23→36,70**, soit **+0,47 point**. La table 3, autre comparaison, donne GPT-4 QASPER **53,0 DPR contre 55,7 RAPTOR**. Ne pas présenter le slogan du résumé « +20 % » comme l’ablation isolée de l’arbre : il compare des systèmes complets différents.[16]
- **Coût publié / transfert :** génération de résumés avec GPT-3.5-turbo, embeddings et clustering offline, nouveaux nœuds à conserver ; recherche plus large. Un résumé peut omettre une exception ou confondre des versions. Le coût d’un changement documentaire n’est pas celui d’un simple upsert de feuille. NarrativeQA et QuALITY ne sont pas des spécifications d’API.[16]
- **Essai proposé :** comparer d’abord feuilles seules à feuilles + parents déterministes, puis ajouter les résumés comme **routeurs vers les feuilles**, jamais comme preuve originale. Séparer produits/versions avant construction des agrégats. Stocker relations et niveaux dans les dérivés/payloads sans changer de moteur. Applicabilité au top1 technique : **incertaine**.

### 1.2 Late Chunking — contextualisation intra-document sans résumé

**Michael Günther, Isabelle Mohr, Daniel James Williams, Bo Wang, Han Xiao — 2024, révision arXiv v3 du 7 juillet 2025 ; lieu évalué par les pairs non vérifié.** Texte HTML intégral disponible ; sections 3, 4.1–4.5 et tables 2–4 lues.[2]

- **Mécanisme :** encoder le document long, puis moyenner les vecteurs token-level à l’intérieur des frontières des chunks. Ce n’est ni encoder des chunks séparés avec un titre, ni conserver tous les tokens pour MaxSim.[2]
- **Mesure :** table 2, quatre sous-ensembles BEIR (SciFact, NFCorpus, FiQA, TREC-COVID), trois modèles ; moyenne nDCG@10 **52,2→54,0** à frontières fixes de 256 tokens, soit **+1,8 point**. La section 4.1 rapporte +3,46 % relatif. La section 4.2 montre des cas où le contexte ajouté n’aide pas, notamment des informations brèves insérées dans du texte sans rapport. La section 4.5 n’est qu’un petit exemple synthétique de comparaison à la contextualisation LLM, pas un benchmark général de supériorité.[2]
- **Coût / transfert :** encodeur long-contexte et états par token pendant l’indexation ; un seul vecteur final par chunk, recherche dense inchangée. Fenêtrage « long late chunking » si document trop long. Le coût dépend de l’attention, des fenêtres et du matériel ; aucune latence Windows n’est établie ici. Impossible de l’obtenir en moyennant des embeddings de chunks MiniLM déjà calculés.[2]
- **Essai proposé :** mêmes frontières, même encodeur compatible, naïf contre late ; contrôler offsets et versions. Encoder une seule version cohérente à la fois : un filtre postérieur ne retire pas une information incompatible déjà injectée dans l’embedding. Priorité **moyenne**, derrière le témoin déterministe.

### 1.3 Contextual Document Embeddings (CDE) — contexte du corpus, pas voisinage de paragraphe

**John X. Morris, Alexander M. Rush — prépublication 2024 ; ICLR 2025 VERIFIED par les actes.** Texte étudié : arXiv **2410.02525v4**, daté du 8 novembre 2024, sections 4–7 et tables 1–2 ; ne pas le confondre avec une version finale ICLR comparée ligne à ligne.[3][13]

- **Mécanisme :** deux contributions : lots contrastifs de voisins difficiles à l’entraînement ; encodeur en deux étapes conditionné par un échantillon documentaire du corpus. Le contexte est inter-documents, contrairement au late chunking intra-document et au préfixe généré.[3]
- **Mesure :** table 1, petit modèle et BEIR raccourci : baseline **59,9**, deux modifications combinées **63,1 nDCG@10**, soit **+3,2 points**. Mais les batch sizes diffèrent : **16 384 contre 512** ; ce n’est pas une ablation à budget identique de la seule architecture. Table 2, la composante retrieval du MTEB final vaut **53,3** pour CDE contextualisé comme pour bge-base-en-v1.5 ; le meilleur agrégat multi-tâches ne prouve pas une victoire de retrieval sur chaque baseline.[3]
- **Coût / transfert :** première étape de contexte pré-calculable et cachable, entrées contextuelles supplémentaires au second encodeur, ré-embedding et recette de modèle spécifique ; pas davantage de dimensions finales imposées à l’index. Réentraîner cette méthode n’est pas le premier essai local raisonnable.[3]
- **Essai proposé :** challenger pré-entraîné seulement si erreurs de domaine persistantes ; fixer échantillon de contexte et sa révision. Vérifier langues et séparation d’ACL avant contextualisation. Supériorité FR→EN technique : **non démontrée**.

### 1.4 GraLC-RAG — travail récent à traiter comme contre-épreuve, pas recommandation

**Pouria Mortezaagha, Arya Rahgozar — 2026, arXiv 2603.22633v1, prépublication, lieu non vérifié.** HTML intégral disponible ; sections 3.2–3.5, 4.1–4.6 et tables 1–6 lues. L’en-tête arXiv indique **23 mars 2026**, la page de titre **24 août 2026** : cette divergence interne est conservée, non résolue en inventant une chronologie.[17]

- **Mécanisme :** frontières de structure JATS, late chunking, infusion de concepts UMLS/SapBERT, puis score guidé par graphe ; plusieurs facteurs changent. Le système décrit utilise MiniLM et FAISS exact ; l’intérêt n’est pas une preuve en faveur d’un autre stockage.[17]
- **Résultat négatif utile :** table 2, PubMedQA*, 1 000 questions / 1 000 abstracts : MRR late **0,9768**, +frontières **0,9765**, +KG **0,9687**, +graph retrieval **0,9502**. Le papier rapporte des dégradations, pas un gain universel. Table 3, 200 articles full-text CPU : indexation naïve **44,6 s**, late **313,7 s**, GraLC **2 566,1 s** ; tailles/nombres de chunks diffèrent, donc pas un surcoût causal pur à unités constantes.[17]
- **Réserves méthodologiques fortes :** pertinence par ID de document, questions cross-section à templates ; section 3.5 définit son F1 par overlap de la réponse avec la **question**, pas avec une référence d’exactitude. SecCov est décrit normalisé en 3.4.2 puis comme nombre brut en table 5 ; CS Recall reste nul pour toutes les variantes. Le « 15,6× » de diversité ne devient donc pas un gain de preuves correctes. La prose annonce environ « 6× » pour des temps que la table ne soutient pas dans la comparaison au naïf ; ne pas reprendre ce ratio.[17]
- **Décision proposée :** retenir l’obligation de mesurer structure et exactitude séparément, **pas déployer KG infusion**. Coûts terminologie/GAT et transfert biomédical→documentation logicielle non justifiés ; priorité faible, certitude faible.

## 2. Décomposition, expansion, multiquery et exactitude technique — trois études

### 2.1 HyDE — document hypothétique pour récupérer un document réel

**Luyu Gao, Xueguang Ma, Jimmy Lin, Jamie Callan — ACL 2023, VERIFIED.** PDF intégral officiel ; sections 3–5, particulièrement table 5, lues.[4]

- **Mécanisme :** générer un passage hypothétique, l’encoder avec Contriever, chercher les passages réels voisins. Le texte généré est explicitement fictif ; le « bottleneck » du dense n’est pas une garantie que chaque hallucination soit neutralisée.[4]
- **Mesure :** table 5, SciFact BEIR, nDCG@10 **64,9 Contriever contre 69,1 HyDE/InstructGPT**, soit **+4,2 points**. FiQA **24,5→27,3** ; DBPedia **29,2→36,8**. Ce tableau compare des versions du générateur et une baseline non supervisée, pas notre embedding multilingue réglé. Mr.TyDi est étudié séparément ; cela ne mesure pas notre FR→EN de code.[4]
- **Coût / transfert :** génération à chaque question, encodage du texte plus long ; aucune réindexation nécessaire si l’encodeur documentaire demeure inchangé. La variante publiée repose notamment sur text-davinci-003, non une preuve de parité d’un petit générateur local.[4]
- **Essai proposé :** branche additionnelle, non remplacement de l’original ; verrouiller `must_not`, `should`, noms exacts, numéros de version et négations. Le passage HyDE n’est jamais une citation. Mesurer candidats nouveaux pertinents et erreurs induites, surtout questions sans réponse.

### 2.2 RAG-Fusion — multiquery + RRF, preuve expérimentale limitée

**Zackary Rackauckas — 2024, arXiv 2402.03367v2, prépublication / lieu non vérifié.** HTML intégral ; sections « RAG vs RAG-Fusion », cas d’ingénierie et « Challenges », table 1 lues.[6]

- **Mécanisme :** générer plusieurs reformulations, lancer plusieurs recherches, fusionner les rangs par RRF. **Multiquery** décrit la génération de variantes ; RAG-Fusion ajoute une fusion. Ce n’est pas la décomposition d’une conjonction en obligations de preuve.[6]
- **Qualité :** cas Infineon et évaluation manuelle par l’auteur ; pas de score P@k/MRR contrôlé avec benchmark indépendant permettant d’annoncer un gain chiffré. Questions corrigées/reformulées, exemples d’identifiants et de perte de détail rendent le récit pertinent, pas une validation statistique.[6]
- **Coût mesuré :** table 1, dix runs répétés d’une même question : RAG **19,52 s**, RAG-Fusion **34,62 s** en moyenne, ratio **1,77×** rapporté. Ni benchmark local CPU ni estimation de latence Qdrant. Le papier constate des réponses hors sujet lorsque les nouvelles requêtes dérivent.[6]
- **Essai proposé :** original + variantes bornées, budget total constant, déduplication par preuve/parent ; rejeter une variante qui modifie un identifiant/version. Comparer « davantage de candidats de l’original » à « variantes à budget égal » pour ne pas attribuer au multiquery un simple effet de profondeur.

### 2.3 UniRAG — décomposer et vérifier avant de réécrire

**Gun Il Kim, Jong Wook Kim, Beakcheol Jang — Findings EMNLP 2025, VERIFIED.** PDF officiel ; sections 3–5, ablations tables 5–6 lues. Il s’agit du papier de **décomposition de requêtes**, pas de l’homonyme vision-language UniRAG.[5]

- **Mécanisme :** entités FLERT, sous-questions, union de candidats, filtrage/reranking mGTE, raisonnement par sous-faits et réécriture itérative avec décision RAGAs. Pas d’entraînement additionnel de la méthode, mais plusieurs modèles et appels.[5]
- **Mesure :** section 5.3 / table 6, LLaMA-3.1-8B sur HotpotQA : EM **0,346** avec raisonnement seul contre **0,766** avec tous les modules. Ce contraste n’isole **ni décomposition ni reranking**. Les premières 500 questions sont utilisées par dataset selon section 4.4, avec splits différents selon la tâche ; ce n’est pas un test général aveugle de documentation technique.[5]
- **Coût / transfert :** sous-requêtes, union, reranking et boucles de génération ; coût online variable. Une confiance LLM ou un seuil mGTE 0,8–0,9/RAGAs du papier ne constitue pas une politique calibrée transportable dans BorgKnowledge.[5]
- **Essai proposé :** comparaison « question entière » / « sous-questions bornées sans boucle » / « même union + vérification de chaque obligation ». Réécriture seulement ensuite. Tous les sous-faits doivent conserver produit, version, portée et négation. Un NER de personnes/lieux n’assure pas la conservation des noms d’API. Priorité conditionnelle aux questions multi-preuves.

## 3. Lexical, late interaction et reranking multilingue — trois études

### 3.1 SPLADE — poids et expansion sparse appris

**Thibault Formal, Benjamin Piwowarski, Stéphane Clinchant — SIGIR 2021, VERIFIED.** PDF auteur ouvert portant référence ACM et DOI ; sections 3–4, table 1 lues. Réextraction de la table en ordre brut pour éviter les colonnes mélangées du PDF.[7]

- **Mesure :** table 1, MS MARCO dev full ranking, MRR@10 **0,184 BM25→0,322 SPLADE-ℓFLOPS**, delta **+0,138** ; Recall@1000 **0,853→0,955**. Proxy FLOPS de scoring **0,13 BM25 contre 0,73 SPLADE** : ce n’est pas un temps CPU de bout en bout et n’inclut pas simplement tout coût d’encodage.[7]
- **Mécanisme/coût :** projection vocabulaire MLM, log-saturation et régularisation de parcimonie ; encodage neuronal offline et query, nombre de non-zéros à surveiller. L’étude montre aussi que des termes originaux peuvent être supprimés et d’autres ajoutés.[7]
- **Transfert / essai proposé :** sparse appris pour le mismatch, **branche littérale distincte** pour opérateurs, codes d’erreur et versions. Ne pas appliquer IDF BM25 une seconde fois aux poids appris sans recette justifiée. L’article anglais ne démontre pas la qualité FR→EN ; priorité derrière BM25 utile, pas derrière le lexical AND défaillant pris pour un BM25 fort. Licence de chaque checkpoint à recontrôler avant expérimentation, sans recopier celle du papier.

### 3.2 ColBERTv2 — alignements fins avec compression spécifique

**Keshav Santhanam, Omar Khattab, Jon Saad-Falcon, Christopher Potts, Matei Zaharia — NAACL 2022, VERIFIED.** PDF intégral ACL ; sections 3, 5.1 et table 4 lues.[8]

- **Mesure :** table 4, MS MARCO dev : MRR@10 **38,8 RocketQAv2 contre 39,7 ColBERTv2** ; « Local Eval » disjoint : **39,8 contre 40,8**. Baselines dev reprises des papiers respectifs : comparaison de systèmes, pas isolation du seul opérateur MaxSim. Le papier inclut BEIR et LoTTE ; ces résultats ne sont pas un benchmark FR→EN.[8]
- **Coût :** somme des maxima token-query/token-document ; pré-encodage documentaire, multiples vecteurs et lectures supplémentaires au scoring. Section 3.3 : centroïde + résidu quantifié **20 ou 36 octets/vecteur** contre **256** dans la représentation ColBERT décrite. Ce format/codebook est spécifique ; un multivecteur Qdrant générique ne reproduit pas automatiquement cette compression.[8]
- **Essai proposé :** late interaction sur **union de candidats identique** à celle du cross-encoder, pour isoler le classement ; évaluer ensuite génération de candidats propre si son rappel le justifie. Préférer un checkpoint dont multilinguisme/licence sont qualifiés. La similarité de sous-tokens ne garantit pas l’égalité exacte de deux noms d’API ; conserver la branche littérale.

### 3.3 mMARCO — témoin académique de reranking multilingue

**Luiz Henrique Bonifacio, Vitor Jeronymo, Hugo Queiroz Abonizio, Israel Campiotti, Marzieh Fadaee, Roberto Lotufo, Rodrigo Nogueira — 2021, version lue v4 du 10 janvier 2022 ; lieu de publication non vérifié ici.** HTML intégral, sections 3–4 et table 2 lues ; cité comme prépublication, pas comme une conférence supposée.[9]

- **Mesure :** table 2, français traduit par Google, MRR@10 **0,155 BM25**, **0,296 mMiniLM**, **0,302 mT5**, **0,289 mColBERT**. Gain mMiniLM/BM25 **+0,141** ; mMiniLM et mT5 sont des rerankers, mColBERT un retriever. Ce ne sont donc pas quatre parcours de même coût.[9]
- **Coût / protocole :** le reranking calcule des paires ; corpus d’environ 8,8 M passages, 6 980 requêtes dans le petit dev décrit. Distillation pour réduire les paramètres ; l’étude examine aussi qualité de traduction et efficacité. Les triples multilingues gardent question et passages dans **la même langue**.[9]
- **Transfert / essai proposé :** résultat justifiant un cross-encoder multilingue en challenger, pas preuve directe d’un bon FR→EN natif. Évaluer séparément FR→EN, EN→FR, même langue, code inchangé et traductions de termes ambigus. Prendre des candidats admissibles fixes ; si la preuve manque, le reranker ne peut la créer. Ne pas confondre ce mMiniLM cross-encoder avec le MiniLM bi-encodeur de la baseline.

## 4. Applicabilité temporelle, contradictions et abstention — trois études

### 4.1 FreshLLMs / FreshQA — fraîcheur, prémisses et exactitude stricte

**Tu Vu, Mohit Iyyer, Xuezhi Wang, Noah Constant, Jerry Wei, Jason Wei, Chris Tar, Yun-Hsuan Sung, Denny Zhou, Quoc Le, Thang Luong — Findings ACL 2024, VERIFIED.** PDF officiel ; sections 2, 4.1–4.3 et table 1 lues.[10]

- **Mesure :** FreshQA, évaluation STRICT sans hallucination : GPT-4 **28,6 %**, GPT-4 + FreshPrompt **75,6 %**, soit **+47,0 points** ; table 1. Une comparaison avec accès web contre sans accès ne prouve pas que trier les mêmes candidats par date apporte 47 points. L’ablation « snippets only » compare search order **74,0** et time order **74,8**.[10]
- **Mécanisme/coût :** preuves datées, sources/titres/snippets, ordre chronologique et démonstrations ; recherche externe et contexte du générateur. Les modèles et données évalués sont historiques, pas un classement courant des services cités.[10]
- **Transfert proposé :** tester date de validité et fausse prémisse, mais **version Python 3.11 ≠ information simplement vieille**. Une documentation récente pour une autre version reste inadmissible. Associer version demandée, version source et validité connue ; ne pas utiliser `retrieved_at` comme date d’effet. Aucun papier ici ne démontre à lui seul un filtre semver correct.

### 4.2 Who’s Who / WhoQA — plusieurs preuves vraies peuvent produire une réponse fausse

**Quang Hieu Pham, Hoang Ngo, Anh Tuan Luu, Dat Quoc Nguyen — Findings EMNLP 2024, VERIFIED.** PDF officiel ; sections 2–3, table 1 lues.[11]

- **Mesure :** WhoQA, 5 152 questions vérifiées, ambiguïtés d’entités homonymes ; macro accuracy Mistral 7B **96,5** contexte simple, **44,5** conflits non signalés, **54,7** conflits signalés par prompt/few-shot : **+10,2 points** contre conflit non signalé, mais toujours loin du témoin sans ambiguïté. La métrique exige toutes les réponses soutenues, pas seulement un top1 plausible.[11]
- **Coût / limite :** davantage de contextes et prompt explicite ; les documents probants sont fournis pour étudier le lecteur, pas retrouvés par un retriever évalué end-to-end. Les conflits sont des homonymes, non des incompatibilités temporelles ; un signalement dans un prompt ne prouve pas une détection autonome des contradictions.[11]
- **Essai proposé :** sources de versions concurrentes, homonymes de fonctions, changements de valeur par version, ordre des preuves permuté. Autoriser réponse comparative explicitement datée, clarification ou abstention ; ne pas écraser une version valide historique au profit du dernier snapshot. Juger pertinence et applicabilité par affirmation.

### 4.3 Selective QA under Domain Shift — calibrer le refus, sans vendre une probabilité brute

**Amita Kamath, Robin Jia, Percy Liang — ACL 2020, VERIFIED.** PDF officiel ; sections 3–5 et table 1 lues.[12]

- **Mesure :** mélange SQuAD et domaines QA inconnus, moyenne de 20 choix de domaines : à accuracy **80 %**, couverture **48,23 % MaxProb→56,06 % calibrateur source+OOD connu**, soit **+7,83 points**. Table 1 sans test-time dropout. Ce n’est ni 56 % de précision, ni une démonstration de ≥ 90 % dans BorgKnowledge.[12]
- **Mécanisme/coût :** random forest sur longueurs et probabilités du modèle QA ; labels de calibration séparés incluant un domaine OOD connu. Coût léger du calibrateur, collecte des labels non gratuite. Le test-time dropout demande plusieurs forward passes ; il n’est pas requis pour le témoin proposé.[12]
- **Transfert :** méthode initialement extractive ; nous n’avons pas les mêmes probabilités de spans qu’un QA SQuAD. **Proposition**, non capacité établie : comparer seuil simple de reranker et calibrateur sur signaux de preuve/applicabilité, score, marge, désaccord lexical/dense. Réentraîner/recalibrer après changement du pipeline. Ne jamais appeler cosinus, RRF, sigmoid du reranker ou score RAGAs une probabilité empirique d’exactitude par défaut.

## 5. Ablations ordonnées et contrat de mesure — aucun essai lancé

L’ordre suivant maximise l’attribution des effets ; il ne suppose pas que toutes les étapes seront utiles. Une métrique qui monte sur le jeu déjà vu ne valide pas l’activation.

| Ordre | Variante isolée | Contrôle et mesure discriminante |
|---|---|---|
| A0 | Refaire les jugements et partitions | Jeu diagnostic réutilisé conservé ; nouveau développement/calibration et test final séparés par familles documentaires. Annoter preuves complètes, UNKNOWN, mauvaises versions et sans-réponse. |
| A1 | Admissibilité stricte | Même candidats/encodeur, avec/sans filtre validé de produit/version/portée ; filtres sur toutes branches, parent et contexte. Métadonnée inconnue ≠ wildcard silencieux. Mesurer rejets injustifiés et incompatibilités. |
| A2 | Segmentation structurelle + parent/contexte déterministe | Séparer effet frontière, effet préfixe et effet expansion parentale ; texte réellement encodé et tokens comptés. Même budget de preuves distinctes et mêmes unités jugées. |
| A3 | Lexical exact + BM25 utile + dense multilingue | Original lexical AND comme historique, pas comme unique BM25 témoin. Branches seules puis fusion explicite ; mesurer taux vide, rappel de candidats et préservation des opérateurs. Modèle d’embedding changé dans une ablation séparée. |
| A4 | Cross-encoder multilingue | Union admissible et profondeur fixes ; sans/avec reranker. Top1, MRR, nDCG, erreurs de version et recall du pool avant reranking. Si candidat absent, revenir à A2–A3. |
| A5 | Late chunking | Même modèle compatible et mêmes frontières naïf/late ; parent et préfixes constants. Aucune comparaison MiniLM court vs nouvel encodeur long attribuée au seul late chunking. |
| A6 | Expansion contrôlée | Original / original+HyDE / original+multiquery RRF ; budget global constant. Pistes techniques exactes et version verrouillées ; compter fausses expansions et requêtes supplémentaires. |
| A7 | Décomposition ciblée | Seulement requêtes multi-obligations : sous-requêtes sans boucle d’abord ; vérifier rappel de **toutes** les preuves nécessaires, pas seulement première preuve. Ajouter boucle UniRAG séparément si justifiée. |
| A8 | Challenger late interaction / sparse appris | Même pool et même encodeur documentaire lorsque possible ; évaluer coûts et langues. Ne pas changer simultanément compression, index, checkpoint et candidats. |
| A9 | Abstention et conflits | Calibration après fixation des étapes retenues ; comparer seuil simple/calibrateur. Risque–couverture, fausses acceptations sans-réponse, clarifications et contradictions non signalées. |
| A10 | Branches de recherche lourdes | RAPTOR seulement si synthèse dispersée ; CDE si domaine ; graphe seulement avec meilleur signal que GraLC étudié. Gate indépendant avant toute intégration. |

**Mesures communes proposées :** P@1 et précision des preuves réellement présentées au cutoff produit préfixé ; MRR et recall5 comparables à la baseline ; recall des candidats à profondeur fixée ; taux de réponse complète pour multi-preuves ; incompatibilités produit/version et contradictions non signalées. Dédupliquer par preuve et parent, pas seulement point vectoriel. Les passages non jugés restent UNKNOWN jusqu’à adjudication ; les nouvelles branches nécessitent un pool de jugements enrichi.

**Coûts à mesurer séparément :** extraction/chunking, ré-embedding, résumés/KG offline ; encode-query, génération de variantes, recherches, fusion, reranking et reconstitution des citations online ; chargement froid/résidence, p50/p95, RAM, disque, taille des vecteurs/non-zéros, tokens et appels. Les runtimes publiés de RAG-Fusion et GraLC ne sont pas des prévisions pour ce poste. À corpus minuscule, inclure recherche exacte comme contrôle pour ne pas attribuer à ANN une erreur d’encodeur.

### ≥ 90 % : cible future, jamais résultat de cette revue

Définir avant test l’unité « preuve présentée applicable et répondant effectivement à la question », le cutoff, les cas sans-réponse et une couverture minimale. Publier dénominateurs et intervalle d’incertitude tenant compte des regroupements question/document. Une précision apparente au-dessus de 90 % obtenue en refusant presque tout ou en recyclant le holdout n’est pas une qualification.

Calibration, test indépendant et monitoring de dérive sont des conditions de mesure, pas une garantie universelle. Une source plus récente ou plusieurs retrievers d’accord peuvent tous être inapplicables. En cas d’échec : conserver Qdrant, diagnostiquer corpus absent / extraction / frontière / représentation / candidats / ordre / portée / refus, sans conclure à un besoin de nouveau stockage.

## 6. Dossier d’évidence, vérifications et limites

Dossier unique, relatif à la racine du dépôt : **`artifacts/research/academic-retrieval-20261017T115009Z-46468ecd/`** ; lien depuis ce rapport : [évidence académique](../../artifacts/research/academic-retrieval-20261017T115009Z-46468ecd/).

- `ledger.json` : registre de citations **task-local**, jamais registre global.
- `fetch-receipts.json` : URLs demandées/finales, statuts, dates UTC, tailles, SHA-256 des réponses et des textes dérivés ; conserve aussi échecs/challenge/réponse vide.
- `source-*.raw`, PDF, textes et versions compactes : octets reçus et extractions effectivement utilisées ; SHA-256 des dérivés complémentaires dans `verification.json`.
- `evidence-quotes.json` : extraits verbatim vérifiés ; tables difficiles réextraites séparément, sans reconstruire leurs valeurs de mémoire.
- `local-inputs.json` et copies `local-*.md` : les deux rapports antérieurs et leurs empreintes ; pas de lecture du vault.
- `discovery-log.json`, scripts de capture/attachement, `citation-verification.txt`, `verification.json` : recherches et contrôles reproductibles, **pas modifications du runtime BorgKnowledge**.

Limites : sélection non exhaustive, résultats des auteurs non répliqués, absence d’essais locaux et d’audit de licences des checkpoints ; compatibilité CPU/Windows non établie par ces papiers. Extraction PDF SPLADE : quelques glyphes invalides remplacés dans le dérivé UTF-8, PDF brut intact ; chiffres de table contrôlés avec une seconde extraction. La fraîcheur de GraLC n’efface ni ses incohérences internes ni son résultat négatif. Les publications ne garantissent pas un passage de top1 50 % à une précision acceptée de 90 %.

## Sources

[2] https://arxiv.org/html/2409.04701v3 — Late Chunking v3
[3] https://arxiv.org/html/2410.02525v4 — Contextual Document Embeddings v4
[4] https://aclanthology.org/2023.acl-long.99.pdf — HyDE ACL2023
[5] https://aclanthology.org/2025.findings-emnlp.1022.pdf — UniRAG Findings EMNLP2025
[6] https://arxiv.org/html/2402.03367v2 — RAG Fusion v2
[7] https://www.piwowarski.fr/publication/formal_splade_2021-lwjxesk9/formal_splade_2021-LWJXESK9.pdf — SPLADE author open paper
[8] https://aclanthology.org/2022.naacl-main.272.pdf — ColBERTv2 NAACL2022
[9] https://arxiv.org/html/2108.13897v4 — mMARCO v4
[10] https://aclanthology.org/2024.findings-acl.813.pdf — FreshLLMs Findings ACL2024
[11] https://aclanthology.org/2024.findings-emnlp.593.pdf — Whos Who conflicts Findings EMNLP2024
[12] https://aclanthology.org/2020.acl-main.503.pdf — Selective QA ACL2020
[13] https://proceedings.iclr.cc/paper_files/paper/2025/hash/f79df6cbc6e5f708440004fad7ef64cc-Abstract-Conference.html — CDE ICLR2025 venue
[16] https://proceedings.iclr.cc/paper_files/paper/2024/file/8a2acd174940dbca361a6398a4f9df91-Paper-Conference.pdf — RAPTOR ICLR2024 full paper fallback
[17] https://arxiv.org/html/2603.22633v1 — Graph-Aware Late Chunking 2026 v1
