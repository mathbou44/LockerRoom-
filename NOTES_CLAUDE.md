# Notes de passation pour Claude (SlabCoach)

À lire au début d'une nouvelle conversation avec Claude (nouveau compte, nouvelle session).
Aucun secret ici : les clés restent dans Render (Environment), jamais dans ce fichier ni dans le chat.
Mis à jour le 20 nov 2026 (transfert vers un nouveau compte Claude).

## Démarrage d'une nouvelle session (pour Claude)
1. Mathieu a relié son ordinateur et connecté le dossier `LockerRoom-` (GitHub Desktop).
2. Copier le dépôt dans l'espace de travail cloud pour bâtir et tester (ex. `/home/claude/lrtest`).
   Le dépôt est autonome : tout ce qu'il faut est ici (source de l'écran, outils de construction, données de test).
3. Installer : `pip install -r requirements.txt --break-system-packages` et `npm install terser` (dans `outils/` ou global).
4. Lire ce fichier en entier, puis demander à Mathieu ce qu'il veut faire.

## Le projet
- **SlabCoach** : app de cartes (hockey, et bientôt baseball). Flask sur Render (www.slabcoach.com, gunicorn
  `-w 1 --threads 32`, disque /data 10 Go) + app iOS Capacitor (dossier `mobile/`, build Codemagic).
- DNS sur Cloudflare. Pousser = GitHub Desktop (Commit puis Push origin) ; Render déploie seul.
- Lancement public : **1er décembre 2026**. Soumission Apple : samedi 22 nov au plus tard.

## L'écran (ui/app.html)
- Source : `source/src_app.html` (gros fichier, ~2,5 Mo). Ne JAMAIS éditer `ui/app.html` à la main.
- Construire : `python3 outils/construire_cloud.py lr --ecrire` (depuis la racine du dépôt) → écrit `ui/app.html`
  (traduction EN via `i18n/*.json`, puis minifié par `outils/minifier.js` avec terser).
  Vérifié : depuis le dépôt, le résultat est identique octet par octet à la version en ligne.
- CSS ajouté à la main : avant le repère `/* 20 nov 2026 : le prix final d'un encan fini de la watchlist */`,
  avec préfixe `html body` pour gagner la priorité.
- Vérifier : aucune erreur JS dans la console (lancer le serveur local et ouvrir la page avec Playwright).

## Serveur local et tests
- Serveur : `LOCKERROOM_DONNEES=/tmp/srv_m LOCKERROOM_PORT=8431 LR_CALME_DEMARRAGE_S=99999 LR_RECHAUFFER_S=99999 python3 server.py`
  (en arrière-plan avec setsid nohup ; il faut ~18 s pour démarrer).
- Tests : `bash outils/lancer_tests.sh` (écrit `ECHEC ...` puis `FINI` dans /tmp/tests_resume.log). Tous doivent passer.
  `test_entrainement` échoue si le disque a moins de ~800 Mo libres (environnement seulement).
- Test du site SlabIQ (chiffres publiés) : `python3 outils/tests_site.py <ventes_hockey.tsv.gz>` (~11 min) ;
  données de base dans `outils/donnees_tests_site/` ; résultats dans `$LR_TESTS_TRAV` (défaut /tmp/claude-0/ts).
  L'empreinte du site est vérifiée par `tests/test_site_a_jour.py`.

## Livrer à Mathieu
- Écrire les fichiers changés directement dans le dossier `LockerRoom-` de son PC, vérifier le md5 (la copie arrive parfois
  périmée : revérifier après 25 s et recopier). Claude pousse lui-même avec GitHub Desktop (voir « Pousser » plus bas). Jamais de git (commit/push) depuis la VM.
- Avant d'écraser un fichier du PC : comparer pour être sûr que seuls nos changements diffèrent.

## Façon de travailler (Mathieu, CEO)
- Réponses en français, concises, sections avec ▓. Ultra simple : pas d'écriture en pattes de mouche, maximiser
  l'espace, visuel compris en 1 à 3 secondes.
- **Pas de barre de défilement sur ordinateur** (son navigateur est à 125 % : fenêtre ~1465×694). Tester à cette taille.
- Slab : 8×13,5 cm vertical ; même standard de slab dans Radar et Inventaire.
- Design : pastilles rondes, icônes en traits, pas d'emoji, de vraies données ; fenêtres au centre, fond flou, un X.
- Accroche, texte et rétention : lire docs/GUIDE_ACCROCHE.md avant tout écran, page, notification ou texte (recherche sur le comportement humain, nos règles, liste de vérification). Slogan : « Collectionne plus. Cherche moins. » Ton hobby, pas finance.
- La mission : aider monsieur, madame tout le monde à suivre sa collection, savoir quand acheter et vendre, sans le
  bruit des influenceurs. Un enfant de 12 ans doit s'en sortir.
- **SlabIQ** : tout changement de décision est testé avant/après sur des données jamais vues ; on garde seulement si ce
  n'est pas pire. Le site ne doit jamais annoncer plus que ce qui est mesuré.

## Règles permanentes
- Jamais de mot de passe, de NIP ni de clé dans le chat ; ne jamais demander de clé. Mathieu met les clés dans Render.
- Ne jamais toucher LOCKERROOM_CLE ; ne pas régler PSA_LICENCE ni LOCKERROOM_MISES_APPROUVEES ; ne pas toucher le
  disque ni les variables de Render ; ne pas monter les plafonds LR_* sans son accord.
- SlabCoach ne mise jamais tout seul.
- Licence eBay : comps, médianes, deals, prix suggérés, valeurs dérivées d'eBay = admin et Platine seulement
  (`comps_permis` / `ebay_prix_actif`). Le public ne voit jamais un prix dérivé d'eBay.
- Signaux de marché (22 nov 2026, « safe le plus possible ») : jamais tirés de l'API eBay (licence §9.5, §8.1.3) ; seulement
  des ventes passées obtenues d'un tiers, montrées en écarts % et courbes relatives, jamais un prix ni une annonce. Un seul
  interrupteur les coupe tous : `LR_SIGNAUX_MARCHE=0` (`signaux_marche_actifs`). L'« offre du jour » (API Browse) de la
  banque YG est coupée et hors de l'export (`LR_OFFRE_EBAY=1` seulement avec l'accord écrit d'eBay). Rien de nouveau ne
  garde du contenu de l'API eBay plus de 24 h. Démarches de Mathieu : to-do « legal_22nov » (eBay Growth Check, avocat).
- Goldin et Fanatics Collect (22 nov 2026, Mathieu : « go ») : PAS de scraping (Fanatics l'interdit ; Goldin appartient à eBay
  depuis 2024). Demandes de licence envoyées par Mathieu (courriels rédigés par Claude) ; on ne branche rien avant un accord
  écrit. Card Ladder = l'option d'une seule licence pour eBay, Goldin et Fanatics.
- Pas de population ni d'images PSA ; pas de logos LNH, d'équipes ou de fabricants ; pas d'étiquettes PSA/TAG.
- Nouvelles : titre + lien seulement ; pas Google News, ESPN, Yahoo ; pas de scraping de Google Trends ni de Fanatics.
- Pas de dépendance à 130point. Pas de faux témoignages.
- Courriels et formulaires : brouillon d'abord, envoi seulement après « envoie » de Mathieu pour chacun.
- Pas de suppression de fichiers sans permission. Le courriel de Mathieu ne sort jamais dans une requête externe.
- SlabCoach reste séparé de Hall of Cardz / Onetwelve (Shopify, Klaviyo, OpenArt = Onetwelve).

## Ce qui a été fait récemment (nov 2026)
- Plafond par compagnie de gradation (`score_slab.py` : PSA sans plafond, autres plafonnées à 91 ; TAG/BGS A, SGC/CGC B+).
- Valeur « autre note » (`deals.py` : prix d'une autre compagnie converti par PART_CIE).
- Cartes manquées corrigées : SSP ignoré dans la recherche, « Signature Handles » n'est pas une inscription,
  patch 1 couleur vs 3 couleurs (`patchs.py`).
- Market Low (`marche_cles.py` v2) : par sorte de carte et année, plus seulement des vétérans.
- Watchlist : prix final des encans terminés (`watchlist.finales`, chaque heure).
- Collection : signal « Garde-la » quand le joueur est au plus bas du marché.
- Inventaire Platine : comparaison avec les comps (`comps_inventaire`, 12 cartes/heure) ; repère si mal pricé.
- Entraîner SlabIQ : nouveau design sans défilement. PSA : envoi simplifié (`envoyerPSA`). security.txt en ligne.

- **Tendances « À acheter / À vendre »** (21 nov, `marche_joueurs.py`) : le marché de chaque joueur vs sa normale de 12 mois ;
  à acheter = joueur établi (120 matchs LNH), coté A ou B, pas en creux sur la glace (filtre dans `lockerroom.tendances_iq`) ;
  à vendre = au-dessus de sa normale ET à son plus haut. Chaque barème est rejoué sur le passé à chaque passe (1 fois/jour, dans
  la boucle de `server.py`) ; un barème qui ne bat pas le hasard n'est jamais utilisé ; l'écran n'affiche que le taux mesuré
  (« La preuve »). Depuis le 21 nov au soir, l'ACHAT est jugé comme un vrai pari : un par joueur et par creux,
  gagnant = revendu plus cher après 15 % de frais, à 2-3-4 mois ; gardé seulement si 55 % et + de gagnants et gain net médian
  de 5 % et + (en pratique : creux de −25 % et plus sous sa normale). Écran style Bourse d'Apple : nom, une ligne, un chiffre,
  1 à 3 barres (Mathieu : « tirer ma conclusion en quelques secondes »). « À vendre » : ses joueurs d'abord (« Tu en as N »). Recrues en creux : jamais à acheter (mesuré). Banque de raisons : `marche_signaux.json`. Mathieu veut 90 % et + :
  mesuré seulement pour les gros sommets (vente) ; ne jamais afficher plus que le mesuré. Dans le Radar, les cartes de ces joueurs montent
  (`lockerroom.a_acheter_noms`, même filtre). Tests : `test_marche_joueurs.py`, `test_tendances_marche.py`.
- **Render précharge l'app** (gunicorn `--preload`) : `server.py` est importé dans le processus maître ; le worker est une copie
  SANS les fils de fond. Les tâches de fond tournent dans le maître (le disque est partagé, pas la mémoire) ; le worker se
  réchauffe lui-même (`_rechauffer_worker`) ; le gardien des piles démarre dans le worker (`_gardien_assurer`).
- Scores SlabIQ de l'inventaire gardés sur le disque du compte (`<db>_scores_iq.json`) ; Gratuit : 15 cartes Radar,
  20 recherches/semaine, 10 annonces/mois (`forfaits.py`) ; Breaks : prix plancher et export Excel des prix.

- **Preuve « mesurable et répétable »** (nuit du 21-22 nov, exigence de Mathieu avant le lancement) : `outils/bulletin_iq.py` rejoue
  le test du site à 5 dates (ventes connues ce jour-là seulement) → `ui/slabiq_bulletin.json` + bloc `<!--bulletin-->` de
  `ui/site_slabiq.html`. Radar Pro : 60-71 % gardent leur valeur à chaque date (hasard 6-12 %). `profit_apres_frais` du test est
  une PART d'achats rentables (10-20 %), pas un rendement : ne jamais écrire « +20 % de profit ».
- **« À acheter » n'est pas prouvé** (testé sur la même carte exacte : gain net médian ~0 % après 15 % de frais) : caché du public
  (`lockerroom.ACHAT_PROUVE = False`), l'admin le voit « à l'essai ». Public : « Au plus bas » (un fait, `marche_joueurs.liste_bas`)
  et « À vendre » (58-62 % rebaissent sur la carte exacte, hasard 42 %). Ne pas fouiller d'autres barèmes sans plus d'historique.

- **Couleurs des tuiles** (22 nov) : `--t1..--t4` = la couleur choisie et ses voisines sur le cercle (oklch, ±50°, +160° adoucie),
  plus de contraste ; points des titres de section = anneau net (plus de halo rogné). Revenus et coûts : 3 cartes à gros chiffre
  (Revenus, Coûts, Résultat + abonnés Pro pour couvrir). Test SlabIQ : 2 colonnes à l'ordi, sans défilement.

- **Gradée sous 9 = brute** (22 nov, Mathieu) : `cartes_match.grade_bas` ; la cible d'une carte notée sous 9 (toute compagnie,
  ACA ajoutée) se cherche et se compare comme une brute (comps de brutes et de notes sous 9) ; jamais un 9 ou un 10, ni ramené
  (`deals._facteur_note`). `credits` garde sa catégorie « gradee <9 ». Grader ? : une ligne (« PSA 10 X au lieu de Y · 1 chance sur N »).

- **Chiffres publiés toujours à jour** (22 nov, Mathieu : « à chaque fois qu'on met le test à jour, update partout ») : à chaque
  nouvel export de ventes, refaire `python3 outils/tests_site.py <export> --ecrire` (site SlabIQ + ui/slabiq_tests.json, que l'app
  lit via iq_publie) puis `python3 outils/bulletin_iq.py <export> --ecrire`, et pousser. Plus de « (avant : X %) » sur l'accord.

- **Radar au cell, entête dégagée** (23 nov, `vueDeals` / `vueMesDeals`, `tests/test_radar_entete.py`) : la grosse bande SlabIQ
  est partie ; SlabIQ = petite pastille `#d-iqp` à côté de Mes cibles et Watchlist. La barre = `Mon radar` + 2 ronds : loupe
  `#md-loupe` (ouvre le champ `.md-rech` À LA PLACE de la barre, classe `rech` sur `.md` ; le × `#md-q-x` vide et referme) et
  tri `#md-t2`. « Voir » est la 1re rangée de la fenêtre Mon radar (`configurerRadar({voir})` → `ouvrirVoir`). La nouvelle WOW
  reste sous la barre ; « Voir ses cartes » ouvre le champ (`md._rech`). À l'ordi (1100×640 et plus, pas `tel-large`) : rien
  ne change (les 3 menus, la recherche dans l'entête fixe). Le focus du champ se fait DANS le toucher (iOS).
  Au cell : le titre « Mon radar » est centré dans son bouton (`.md-g-t` : marge de gauche = l'engrenage + l'espace) et la
  nouvelle WOW a 14 px dessus ET dessous (`html body .md-wow{margin:0 0 14px}` ; avant : collée aux tuiles).
  Radar ADMIN au cell (`.d-ligne:has(#d-tour)`, 699 px et moins) : 2 rangées en flex (une coupure `::after` pleine largeur) :
  [Deals | Watchlist] [SlabIQ] … (roue admin) ; puis prochain tour, ↻ encans, annonces vérifiées ; 16 px entre le titre, les
  rangées et la recherche. Sous 410 px la pastille SlabIQ se cache en admin. À l'ordi en vue admin, sous 1800 px : pastilles
  en version courte (`.d-pc`) et onglets à leur largeur : tout tient sur UNE rangée, la recherche fait ~400 px à 1465 px
  (avant : roue dessous, recherche de 30 px). Reste serré entre 1100 et 1250 px. Pour mesurer en local, retirer la carte
  « Tune your Radar » de `.tete-fixe` (elle élargit la colonne du titre ; Mathieu ne l'a pas).
- **Tendances top 25** (23 nov, `lockerroom.tendances_iq`, `TEND_TOP/TEND_GRATUIT/TEND_PCT_MIN`) : Plus bas et Plus haut =
  les 25 plus gros écarts (seuil 1 %, plus 10 %), triés du plus gros au plus petit, avec un rang. Gratuit (ni Pro ni admin) :
  `_tendances_gratuit` vide les 20 premiers (le serveur n'envoie que le % et la courbe : `verrou`), les 5 derniers lisibles ;
  l'écran : `ligneV`, `data-pro-lock="tendances"`. Le local est admin : simuler avec une réponse interceptée (`/home/claude/vue/tend2.py`).
- **Barre du haut au cell** (23 nov) : le « ? » du guide n'a PAS la classe `rond` (36 px dans `.barre-mode`) : `.haut-aide` fait
  44×44, sinon toute la page remonte de 8 px (Mathieu : « tout semble décalé vers le haut »). `tests/test_guide_app.py` le garde.

- **Simulation d'un an du site, revérifiée** (23 nov, `outils/recherche/avenues/sim.py`, `sim2.py`, LISEZMOI) : toujours vraie
  (−4,7 % / +6,6 % / ≈ 600 $) ; elle suit la LETTRE seule, pas le Radar Pro. La règle du Radar Pro y donne +8,1 % mais moins de
  cartes (même gain en dollars) : on ne change pas la page. « A et plus + ≤ médiane » affiche +23 % : un mirage (rabais
  profonds sur cartes brutes ; rien sur les gradées) : NE PAS publier. Le 77 % du Radar Pro tient (76 % à rabais léger, 73 % gradées).

- **Breaks : « Vaut plus scellée »** (23 nov, `marche.verdict_ouvrir(ev, boite, part_mesuree)`, `OUVRIR_PART_MIN = 50`,
  `tests/test_ouvrir_mesure.py`) : Mathieu devant « Keep sealed −93 % » sur Ice : « tu veux dire quoi ? ». Le verdict comparait
  la valeur des cartes d'une boîte à son prix scellée, mais pour Ice et Artifacts cette valeur venait à 0 % de vraies ventes
  (valeurs par défaut : 15 $ par boîte d'Ice). Maintenant : aucun verdict si moins de 50 % de la valeur vient de vraies ventes
  (`calcul.prix_catalogue` → `part_mesuree` ; `catalogue_liste` rend `ev_mesuree_pct`) ; le badge dit « Vaut plus scellée »
  sans chiffre ; l'astuce de l'accueil (`astuces.ouvrir`) dit la part de vraies ventes. Sur les valeurs locales du 22 oct :
  6 produits sur 26 gardent un verdict. À regarder en ligne : combien en gardent un avec les valeurs du jour.

- **Site : la simulation d'un an est RETIRÉE** (23 nov, Mathieu : « oui » ; `ui/site_slabiq.html`, `outils/site_iq.py`,
  `tests/test_site_sans_simulation.py`). Le graphique « un budget de cartes par mois pendant 1 an, avec ou sans SlabIQ » affichait
  un profit AVANT frais eBay (+350 $ / −277 $ ; après frais 13,25 % + 0,40 $ : −412 $ / −1 048 $, écart ≈ 640 $, 96 % des cas)
  avec des lettres fixées après coup (apprises jusqu'à la mi-octobre 2026, achats dès nov. 2025). Le méga test du 22 nov
  (`outils/mega_test_resultats.json` : lettres connues à l'époque, frais compris) ne prouve aucun profit de revente (raté à
  6 dates sur 6 ; le Radar Pro a 2 à 3 fois plus de gagnants que le hasard). À sa place, en haut de la page SlabIQ : le
  comparatif mesuré (`<!--vs-->`, remonté de « Nos tests ») sous « Tes chances, seul ou avec SlabIQ. ». La mesure `sim` reste
  dans `ui/slabiq_tests.json` pour la recherche. NE JAMAIS remettre un profit de revente sur le site.
  Même jour : dans le comparatif (`site_iq.bloc_vs`, les deux pages), chaque chiffre des « faits » est écrit dans les deux langues
  (« 180 519 » / « 180,519 », « 76 % » / « 76% ») ; `tests/test_chiffres_partout.py` refuse un nombre à la française en anglais.
- **Ce qui s'améliore tout seul (vérifié dans les journaux Render le 23 nov, question de Mathieu)** : aucune tâche programmée côté
  Claude ; tout est sur le serveur. Score SlabCoach : réappris aux 3 jours, la nuit (`score_appris`, journal « Score SlabCoach :
  … reapprendre lance » : 18 et 21 nov), gardé seulement s'il tient le garde-fou (précision ≥ 0,90 sur 10 jours jamais vus, pas
  plus de 0,01 sous la dernière mesure). Validation SlabIQ : 1 fois/semaine (`validation_iq`, dernière passe le 18 nov au soir :
  accord 0,639 sur 128 114 ventes ; corrections automatiques + questions à l'expert). Chaque heure : la demande des joueurs.
  PAS automatique : les tests publiés sur le site (export des ventes par Mathieu → `outils/tests_site.py --ecrire` → push) et
  les réponses de Mathieu aux questions de SlabIQ (Admin → Entraîner SlabIQ).
- **Plan des 6 premiers mois et envoi à Apple (23 nov au soir ; Mathieu : « planifier mes premiers 5-6 mois », puis « j'ai rien
  demandé à Apple encore »)** : le plan est sur le Whiteboard « SlabCoach : les 6 premiers mois »
  (https://claude.ai/artifact/4QXyEyEFH3pq9g8Pe4YYGW) : déc. tenir debout, janv. lire les chiffres des premiers essais, avant le
  15 fév. être prêt (Series 2 prévue le 24 fév., date limite des échanges le 1er mars 2027), mars acquisition, avril rétention,
  mai décider (baseball, licences, Platine). Zones : Apple, données, serveur (un seul processus), argent, légal, lui seul, se faire
  connaître, dispersion. Dans la liste admin (`ceo.py`) : `SEMIS["apple_23nov"]` (ap_accord et ap_build le 24, ap_soumettre le 25,
  ap_planb le 29) et `SEMIS["plan_6mois_23nov"]` (projet « Les 6 premiers mois » : p6_charge, p6_support, p6_budget, p6_pc,
  p6_createurs, p6_janvier, p6_fevrier, p6_mai) ; `CLOS["clos_23nov_soir"]` ferme `t_sim` et `l1_apple` (remplacée).
  **Fiche App Store refaite** (`mobile/APP_STORE.md`) : l'ancienne (27 oct) promettait « le vrai prix… tiré des ventes réelles »
  et des « ventes comparables » que le public ne voit plus ; la nouvelle suit le site (« Collectionne plus. Cherche moins. », la
  lettre, le Radar, la collection). Sous-titre « Cartes de hockey notées A+ à E ». Captures : à refaire par Mathieu sur son iPhone
  en vue Pro (celles de `mobile/captures_v2/` datent du 27 oct). **Note au réviseur vérifiée pas à pas** sur un iPhone simulé
  (serveur local `LOCKERROOM_MULTI=1` + `LOCKERROOM_DEMO_CODE`, agent « LockerRoomiOS », faux plugin `NativePurchases`) : le lien
  de l'écran de connexion s'appelle « Démo / Demo » (la note disait « Code de démonstration ») ; l'achat intégré : Profil › pastille
  « GO PRO » › « See Pro » (la feuille montre nom, durée, prix, renouvellement, Conditions, Confidentialité, Restaurer) ; la
  suppression du compte : Profil › My account › « Help, sign out, delete account ». Deux corrections dans l'app : le compte démo ne
  voit plus la fenêtre « Tu utilises déjà SlabCoach ailleurs ? » (`lockerroom.py`, `compte_neuf`) et la ligne du Profil
  « Soutien, conditions, déconnexion » devient « Aide, déconnexion, suppression » (règle 5.1.1(v)). Tests : `tests/test_demo_apple.py`,
  `tests/test_ceo_apple.py`. PAS vérifié : l'état réel chez Apple (accord « Applications payantes », abonnement créé, clés APNs
  dans Render) ni un build Codemagic récent : seul Mathieu peut le voir. Dans l'app iPhone, le Pro est mensuel seulement.
- **Lot de cartes : vitesse, titre, retirer (23 nov au soir ; Mathieu en direct sur son iPhone)**. Mesuré dans le journal Render
  (son lot de 19 h 28, heure de Toronto) : 4 cartes en 1 min 50 s (la 1re en 20 s, les autres 35 à 60 s, l'étape « titre et prix »
  domine), puis `serie_candidates` 10,0 s et `paires_verifier` 6,6 s à l'ouverture de « Programmer ». Fait : (1) `LOT_PARALLELE`
  3 (2 avant) ; (2) chaque carte écrit « Lot : carte lue en X s (lecture · titre et prix · garde) » et `annonce_preparer` écrit
  « Preparer lent : … (ventes · cartes proches · annonces eBay) » au-delà de 8 s : ON NE SAIT PAS ENCORE quelle partie du prix
  est lente (SoldComps/CompSniper 15 s max par appel, TheCardAPI 12 s, eBay) : lire ces lignes après son prochain lot avant de
  toucher au reste ; (3) `serie_candidates` ne lit que les cartes à programmer (`inventaire_liste({"a_programmer": True})`) :
  sur un inventaire simulé de 2 000 cartes (504 Mo), disque froid : 0,92 s → 0,23 s ; le gain réel dépend de son inventaire, à
  relire dans le journal (« Lent : POST /api/serie_candidates ») ; (4) ESSAYÉ PUIS RETIRÉ : noter la paire devant/dos
  confirmée par la lecture du lot dans le cache de `paires_verifier` (gagnait 6,6 s) : c'est la 2e vérification demandée par
  Mathieu le 11 nov après 3 annonces au mauvais dos ; `tests/test_lot_serveur.py` la garde. Ne pas l'enlever sans son accord. Piste non faite : `inventaire_liste`
  lit encore `json_extract(etat_json…)` pour tout l'inventaire (page Inventaire) : mettre note_min/note_max en colonnes.
  **Titre** (« 2x opc et c'est une blue rainbow. Sert-toi du code BA ») : `annonces.titre_optimise` et `ebay_csv.titre_annonce`
  n'écrivent plus la marque quand le set la contient ; `cartes_match.completer_par_code` (appelé aux 2 lectures) donne le
  parallèle d'après le code, table `codes_variantes.json` apprise des ventes par `outils/apprendre_codes_variantes.py <export>
  --ecrire` (20 ventes par saison, 85 % des titres, noms faits de couleurs et de finis seulement) : BA = Blue Rainbow
  (O-Pee-Chee Platinum 2022-23 à 2024-25, 96 % de 395 ventes), RA = Red Rainbow (2025-26 seulement ; avant, RA = Rookie
  Autographs). Une autre couleur lue sur la carte n'est jamais écrasée (le champ passe « à vérifier »). À relancer avec chaque
  nouvel export. **Programmer, étape 2** : bouton « Retirer » par carte (sort du lot, reste dans l'inventaire ; la dernière
  retirée ramène à l'étape 1). Nouveautés n: 244. Tests : `test_codes_variantes.py`, `test_lot_vitesse.py`. Tâche admin `lv_temps`.
  Vu sans y toucher : Kaplan Future Watch Auto /999 à 5 $ et Wood Inscribed à 250 $ dans la même capture (prix à regarder).
- **Soirée du 23 nov, suite (Mathieu en direct, à l'ordi)**. (1) **Nouvelles de l'accueil à l'ordi** (« c'est tout pogné ») :
  7 rangées de hauteur égale dans une hauteur fixe ; la nouvelle WOW (3 lignes) débordait (mesuré à 1456×690 : rangée 75 px,
  texte 79 px). Rangées `flex:1 0 auto` + `nlAjuster()` (cache les dernières rangées tant que la liste déborde, 3 au moins ;
  refait au changement de taille). Test : `test_nouvelles_rangees.py`. (2) **Admin « Sorties à venir »** (« Loading… 94 % ») :
  le serveur répondait en < 1 s par un refus (réponse de 101 octets = « HTTP Error 403: Forbidden » ; la page de Checklist
  Insider se lit d'ailleurs, donc c'est notre serveur qui est refusé) et `blocSorties` sortait sans rien afficher. Maintenant :
  la raison + « Réessayer », ou « rien à venir » ; `sorties.lister` écrit « Sorties : … » au journal et ne redemande pas avant
  15 min. NE JAMAIS contourner ce refus (autre agent, autre adresse) : demander la permission ou entrer les dates à la main ;
  à faire décider par Mathieu. Test : `test_sorties_refus.py`. (3) **Ménage de la liste admin** (« 86 tâches c'est bcp trop ») :
  `SEMIS["menage_23nov"]` + `CLOS["clos_menage_23nov"]` : 87 ouvertes → 25 (18 à lui, 7 à Claude) ; les petites tâches d'un sujet
  = une tâche avec sa liste dans la note. RÈGLE : une nouvelle tâche seulement si elle ne tient dans aucune existante ; jamais
  plus d'une vingtaine à lui. Test : `test_ceo_menage.py`. (4) **Page SlabIQ, « Nos tests »** (« on dirait qu'on s'empire…
  remplacer par autre chose de plus convaincant ») : plus de tableau par date ; `bulletin_iq.rendre` montre les mêmes 5
  résultats, un point par test sur une échelle (Radar Pro 77 à 92 %, seul 7 à 11 %), titre « Refait 5 fois. Le Radar Pro
  l'emporte 5 fois sur 5. » (compté seulement si le bas de l'intervalle bat « seul »), le plus récent écrit en toutes lettres.
  « SlabIQ s'améliore chaque semaine » N'EST PAS écrit : le chiffre du Radar Pro baisse de test en test (92 → 77 %) ; ce qui
  monte dans les mêmes tests : accord 0,65 → 0,77, « A se revend X fois plus que E » 3,8 → 7,8, achats 187 → 475. Cause de la
  baisse PAS vérifiée (hypothèse : plus de cartes couvertes) : tâche `g_c_jeudi`. Règle de livraison rappelée (ex-tâche `v_push`) :
  à partir du 1er décembre, pousser tôt le matin ou tard le soir (chaque push = 3 à 5 minutes lentes : le 23 nov à 20 h 01,
  `achetees_tableau` 10,8 s et `accueil` 5,5 s dans la minute suivante).
- **Admin « Activité » refaite (23 nov, « bcp trop long à scroller pour rien »)** : `adminActivite` : période + 3 chiffres sur une
  ligne, graphique de 54 px (svg `preserveAspectRatio="none"` : il grandissait avec la fenêtre, ≈ 290 px), les 3 classements côte
  à côte (6 lignes, 4 au cell, « Tout voir · N »), « jamais utilisées » dans un `<details>`, commentaires en pastilles par
  catégorie (un toucher montre la liste). Mesuré à 1456×760 : 656 px, aucun défilement. Test : `test_activite_compacte.py`.
  LEÇON pour les autres fenêtres admin : à l'ordi, une fenêtre tient sur un écran ; les listes en colonnes, le détail au toucher.
- **Repère de prix d'une annonce (23 nov au soir ; Mathieu : « va falloir que tu fasses attention », 3e fois sur ce sujet après
  les 8 et 21 nov)**. Sa Michael Misa 2025-26 SP Rookie Authentics OR (jersey) à 55 $ : « Too high +424 % · market $10 · 3 sales »
  avec le bouton « Match the market · $10 », alors que la même carte s'est vendue 61 $ (3 oct.). Dans nos ventes, le #122 existe en
  4 versions : base /1749 et Blue (2 à 6 $), Jersey (10 à 14 $), Jersey Patch (42 à 83 $), Gold « Game Used Patch » (≈ 60 $).
  Le repère de l'annonce (`sante`, passe `_sante` → `c.marche`) a très probablement pris les ventes « Jersey » : PAS vérifié (je
  n'ai ni le titre de sa fiche ni les 3 ventes ; lui demander). Sa règle, redite : « le prix est toujours plus cher que la last
  sold des 3 derniers mois / moyenne pondérée, la plus chère, d'environ 15 % ». Fait : `sante.evaluer_vendues(…, derniere,
  ponderee)` : repère = max(dernière vente 90 j, médiane pondérée `deals.mediane_recente`) ; bon prix = repère + 15 %
  (`MARGE_NEGO`) ; « baisser » seulement au-delà de + 25 % (`HAUT_VENDUES`, avant + 15 %) et la suggestion = repère + 15 % ;
  plus du DOUBLE du repère avec moins de 8 ventes → verdict « verifier », aucune suggestion (donc jamais de baisse automatique
  ni de rabais conseillé) ; `sante_liste("baisser")` écarte aussi les vieux repères douteux ; à l'écran `repere(c)` dit
  « À vérifier · même version ? » sans bouton, et « Mettre au marché » = repère + marge de négo (15 %). Le chemin des comps
  (`comps_valeur`) a la même garde. Test : `test_prix_repere.py`. RESTE (important, pas fait) : `cartes_match` traite « Jersey »
  comme « Patch » (`patch: True` pour les deux) et la couleur OR de cette carte n'est lisible que par le lettrage doré : revoir
  la séparation Jersey / Patch / Or au banc (`outils/banc_valeur.py`) avant d'y toucher, jamais à l'aveugle.
- **« À liquider » (23 nov, tuile à 80 : « 30 jours c'est peu ; si pas de watchers, peu ou pas de views, ou 90 jours affiché »)** :
  `lockerroom.popularite` : 90 jours en ligne et plus, OU 60 jours et plus avec 0 suivi et peu de vues (ou vues inconnues) ;
  avant : 30 jours. Le 60 est MON choix (le même que « traîne ») : il n'a pas donné de chiffre, lui faire confirmer.
  Test : `test_popularite.py`.
- **Consignation, « rien se passe quand je clique » (23 nov, 59 cartes)** : aucun appel `consig_*` au journal Render entre
  20 h 54 et 21 h 07 : rien ne partait du navigateur. Reproduit : Exporter, Exporter (ou Imprimer), puis Annuler → la question
  « Retirer N annonces d'eBay ? » restait affichée avec des boutons morts. `feuilleConsigner` : une seule question à la fois
  (`question`), bandeau d'origine gardé une fois (`bandeau0`). Test : `test_consig_question.py`. PAS confirmé que c'était SA
  suite de gestes : lui faire réessayer après le push. Rappel : « Retirer et continuer » termine vraiment les annonces sur eBay.
- **Misa, la cause trouvée (23 nov, 21 h 30 ; son titre : « 2025-26 SP Hockey Rookie Authentics Patch RC - Michael Misa #122 »)**.
  Rejoué sur l'export : 6 ventes retenues dans les 90 jours, valeur sûre 10,49 $. 5 des 6 étaient des « SP Game Used - Authentic
  Rookies #AR-MM » (autre produit, autre carte ; de 1,43 à 143 $) ; la 6e est « SP ROOKIE AUTHENTICS JERSEY #122 » vendue 10,49 $
  le 20 nov. La vente Gold à 61 $ est refusée parce que son titre ne dit pas « Gold » ; les « Jersey Patch » à 43 $ datent de
  plus de 90 jours. Corrigé dans `cartes_match.raisons_refus` : (1) une vente qui porte un code de carte avec dièse (`_code_diese`,
  #AR-MM) n'est pas la carte #122, ni celle d'un autre code ; (2) « SP Game Used » en toutes lettres d'un seul côté = autre
  produit, sauf si l'autre titre dit aussi « game used ». « SP » seul ne tranche rien (short print). Mesuré sur 19 562 paires
  de vraies ventes : 25 comparaisons retirées sur 1 435 gardées (1,7 %), toutes de vraies erreurs à la lecture. Test :
  `test_misa_comps.py`. PAS RÉGLÉ et à lui de trancher : sa carte (dos « JERSEY », lettrage doré) est-elle la version Gold
  (≈ 61 $) ou la Jersey (10,49 $ le 20 nov) ? Avec son titre actuel il reste UNE vente en 90 jours : plus de verdict.
  Mathieu, 21 h 44 : morceau « uni » = c'est une JERSEY. Le « marché 10 $ » était donc le bon ordre de grandeur (10,49 $ le
  20 nov ; 13 et 14 $ en mars), obtenu avec 5 mauvaises ventes sur 6 ; c'est le mot « Patch » de son titre qui est faux.
  Mathieu, 21 h 41 : « pas gold ». Sur Misa #122 seulement, trois niveaux de prix : Rookie Authentics sans morceau 1 à 6 $
  (15 ventes), « Jersey » 10 à 14 $ (3), « Patch » pas Gold médiane 43 $ (5), Gold 60 $ (1). Une seule carte : trop mince pour
  changer la règle pour toutes ; mesurer Jersey seul contre Patch sur tous les jeux avant d'y toucher.
  Jersey et Patch restent confondus par `_RE_PATCH` (les vendeurs mélangent les deux mots : ne pas séparer à l'aveugle).
- **« Je veux pas cliquer, tout doit se faire auto » (Mathieu, 23 nov, 21 h 55)**. État vérifié : le serveur refait seul le
  test de prédiction chaque semaine (`slabiq_test`, fichier `slabiq_test_donnees.json.gz`) et le signal par joueur se note seul
  chaque jour (`signal_joueurs.noter`). Encore manuel : (1) le test PUBLIÉ sur le site (export des ventes par Mathieu →
  `outils/tests_site.py --ecrire` → push) ; (2) le push par GitHub Desktop (sa règle : jamais de git depuis la VM). Fait :
  sa tâche `r_donnees` fermée, tâche Claude `g_c_auto` (26 nov) : faire tourner le test du site SUR le serveur, la nuit, le site
  lit le résultat ; garde-fou obligatoire (échec ou chiffre qui bouge trop = on garde les anciens chiffres + alerte admin), car
  « le site ne doit jamais annoncer plus que ce qui est mesuré ». À vérifier avant : mémoire et durée sur Render (le test prend
  ~11 min ici, 1,15 M de ventes ; un seul processus). Essayé : le navigateur de l'app Claude sur son PC n'est PAS connecté à
  l'admin (renvoi à /connexion) ; ne pas lui redemander de s'y connecter, il ne veut aucun clic.
- **Nouvel export du 23 nov, 22 h 10 (hockey 1 772 256 lignes, 1 456 171 uniques ; baseball 138 510)** : copies dans
  `/home/claude/export_2311/` (la VM ne les garde pas : les redemander). 444 000 ventes de plus que le matin, surtout 2023-2025.
  Test du site refait SANS écrire (`LR_TESTS_TRAV=/tmp/claude-0/ts2311soir`, 12 min) : 768 209 ventes, coupe 27 sept (avant :
  15 oct), reventes dès le 22 oct. Radar Pro 74,0 % (674 achats, IC 70,9-77,2 ; publié : 77,7 % sur 475) : revendue 92,9 %
  (90,1), garde sa valeur 79,7 % (86,2) = c'est « garde » qui baisse. Seul 9,6 % (11,1). Accord 0,743 (0,765), rho 0,976
  (0,952), UNE inversion B (7,9 %) sous C (9,7 %). A / E : 7,0 fois (7,8). Simulation : +9,4 % contre -1,8 %, bat 94 % (96).
  RIEN PUBLIÉ : demandé à Mathieu s'il publie 74 % (il trouve que la baisse « paraît mal » ; la règle dit que le site ne dit
  jamais plus que la mesure). Les deux tests ne couvrent pas la même période : ne pas dire « baisse » sans le préciser. Cause
  non vérifiée (hypothèse : achats de fin septembre, au sommet du début de saison).
- **Radar Pro : « pas une carte neuve » (nuit du 23 au 24 nov ; Mathieu : « continue à travailler pour rendre SlabIQ
  infaillible et modifie au besoin, tu as mon accord si c'est pour s'améliorer »)**. Recherche : `outils/recherche/garde/`
  (LISEZMOI.txt). Trouvé : (1) avec la MÊME règle, le chiffre du Radar Pro va de 43 à 90 % selon la fenêtre sur un an : la
  « baisse » 92 → 74 % n'était pas SlabIQ qui s'empire ; (2) la cause des mauvaises fenêtres = les cartes NEUVES (moins de 45
  jours depuis leur 1re vente : 27-35 % réussis ; 60 jours et plus : 74-86 %) : les sorties (Series 2 en mars, Extended en
  juin, Series 1 en novembre). Règle ajoutée, sans nouveau réglage : `liquidite.VIEUX_MIN = 1` = au moins une vente entre 60
  et 90 jours avant (`liquidite.signaux` rend maintenant (liq, med, vieux) ; `passe(liq, med, total, vieux)` ; vieux inconnu =
  refusée). Choisie sur oct. 2025 à mars 2026 (70,0 → 85,6 %), jugée sur avril à oct. 2026 (72,2 → 84,8 %). `vitrine.py` :
  `_vieux` gardé avec l'annonce, `_completer()` remplit les annonces déjà en vitrine au balayage suivant (sinon elles
  resteraient cachées). `outils/tests_site.py` mesure la même règle. Interrupteur : `LR_RADAR_ANCIENNETE=0` dans Render.
  Test officiel refait et ÉCRIT sur le site (export du 23 nov au soir) : Radar Pro 84,6 % (454 achats, IC 81,1-87,7 ; avant
  la règle : 74,0 % sur 674), se revend 96,7 %, seul 9,6 %. Bulletin refait aux 5 dates (29 sept, 13 oct, 27 oct, 10 nov,
  24 nov) : 86, 92, 86, 88, 85 % ; seul 11, 10, 9, 10, 10 %. Le site dit : 84 % contre 10 %, 96 % contre 19 %, 6 fois (A et
  A+ contre E : 6,8), ≈ 75 % d'accord (0,743), 765 k+ ventes, 990 joueurs. `iq_publie.pro` : « seul » au plus proche (9,6 →
  10, comme le bulletin ; avant : 9 d'un côté, 10 de l'autre). Nouveautés : un point ajouté à l'entrée 244.
  REJETÉ (sur-apprentissage : bon sur la période de choix, rien sur l'autre) : A et plus seulement, 50 $ et plus. À OFFRIR à
  Mathieu, pas appliqué (tient sur les deux périodes, mais moitié moins de cartes) : + 12 ventes et prix à 7 % sous la médiane
  = 91 % (44 cartes différentes à la dernière fenêtre contre 83). PAS RÉGLÉ : la pire fenêtre de l'année reste à 67 % (mai
  2026 : Demidov 63 %, Bedard 58 %) ; environ une annonce sur trois ne passe plus (vérifier que le Radar Pro a assez de
  cartes après le push : Admin, tâche `g_cell` point 3) ; B se revend moins que C (7,9 contre 9,7 %) = la MESURE (reventes de
  la même carte : B = autos, numérotées, patchs, peu de copies ; C = cartes de base), rien changé, à reprendre jeudi.
  Page SlabIQ, liste « Amélioré cette semaine » (écrite à la main dans `ui/site_slabiq.html`) : ligne ajoutée « Radar Pro : plus
  de cartes tout juste sorties ». La 1re ligne de cette liste, « 214 joueurs ajustés par le marché », n'est PAS tirée du test
  (le test du soir compte 124 corrections) : à vérifier ou à retirer jeudi.
  Vu en passant, pas corrigé : `tests/test_vitrine.py` a échoué une fois sur « database is locked » (PRAGMA journal_mode=WAL
  de `liquidite._cx` pendant que le fil de fond écrit) ; pas reproduit en 8 passes.
- **État du push (24 nov, 0 h 15)** : Mathieu a poussé lui-même à 22 h 05 (commits 49786a7 et 102be57 « oudh », en ligne à
  22 h 06, aucun Traceback au journal ; la minute lente d'après push est toujours là : `achetees_tableau` 24,6 s,
  `admin_resume` 19,4 s). Ce push contient : règle de prix et « À vérifier », Activité, « À liquider », consignation, Misa
  (code de carte, SP Game Used), ménage et tâche `g_c_auto`. PAS POUSSÉ (sur son PC, md5 vérifiés, 18 fichiers) : le Radar Pro
  « pas une carte neuve », le test du site et le bulletin refaits, `iq_publie.pro`, Nouveautés, `outils/recherche/garde/`.
  Le PC affichait « Enter your PIN » : ne jamais le taper. Vu au journal : eBay répond 429 (« Too many requests ») à la
  synchro des vues des annonces (22 h 07 et 23 h 09) : pas regardé.
- **Radar : « beaucoup de cartes », pour chacun (24 nov, 7 h 51 ; Mathieu : « il nous faut beaucoup de cartes à proposer. Chaque
  personne collectionne des équipes et joueurs différents, donc notre radar doit s'adapter aux demandes de chacun et leur
  offrir le meilleur »)**. Sa réponse à l'offre « 91 % avec moitié moins de cartes » : NON, on garde plus de cartes. Mesuré
  (`outils/recherche/garde/couverture.py`, ventes de 30 $ et plus des 90 derniers jours, 522 joueurs qui se vendent) : 427
  joueurs n'ont AUCUNE carte à 82 et plus (règle par défaut), 343 aucune à 76 et plus (règle d'un joueur SUIVI) : celui qui
  suit Evangelista, Dorofeyev ou Doan ne voyait rien de lui, sans le savoir. Fait :
  (1) `lockerroom.Api._radar_rangee_suivie` : la rangée d'un joueur ou d'une équipe SUIVI n'est plus jamais vide ; sous
  `RADAR_RANGEE_MIN` = 24 tuiles, on complète avec les meilleures de ce joueur (note la plus haute d'abord, « elargi »),
  jamais une base ni un lot, jamais sous C (`RADAR_RANGEE_PLANCHER` = 50), jamais sous son prix minimum. Si l'utilisateur a
  choisi lui-même sa note minimum dans les Filtres, son choix tient (rien d'ajouté). Avec le plancher C, il reste 11
  joueurs sur 522 sans aucune carte. « À la une » (la règle prouvée) ne change pas ; l'empreinte du test non plus.
  (2) Filtres du Radar : le choix par défaut s'appelait « B et + », mais le serveur appliquait la règle du 19 nov (A- et
  plus ; B+ pour ses joueurs), et choisir « B et + » renvoyait cette même règle (impossible d'avoir les B). Maintenant :
  « Recommandé » (défaut, `iq_min` nul) et « B et + » envoie 65 pour vrai.
  (3) Journal : « Vitrine : N annonces montrables · … », une fois aux 30 min (`deals._vitrine`) : après le push, lire ce
  chiffre pour juger si « À la une » a assez de cartes avec la règle « pas une carte neuve » (elle en enlève une sur trois
  au banc ; « À la une » montre 60 tuiles au plus).
  Tests : `test_radar_digne.py` (complété), `test_radar_suivi_plein.py` (le Radar complet, de la recherche à la réponse).
  Nouveautés : « Tes joueurs, toujours là » (entrée 244). TROUVÉ, PAS CHANGÉ, à lui de décider : les barres du Radar ne
  suivent pas les lettres (la lettre A- commence à 80, la barre « A- et plus » est à 82 ; B+ : 73 contre 76 ; A : 85 contre
  86) : une carte notée A- à 81 ne passe pas « A- et plus ». Les aligner donnerait plus de cartes, mais `liquidite.NOTE_MIN`
  fait partie de la règle testée (refaire le test du site et le bulletin, environ 1 h 15 de calcul).
- **État du push (24 nov, 8 h 15)** : Mathieu a poussé à 8 h 00 (commit d8bf62f « push », en ligne à 8 h 02) : le Radar Pro
  « pas une carte neuve » et le site refait sont EN LIGNE (vérifié : la page SlabIQ dit 84 % contre 10 %, 5 fois sur 5,
  84 à 92 % ; aucun Traceback au journal). PAS POUSSÉ (sur son PC, md5 vérifiés, 8 fichiers) : la rangée suivie jamais vide,
  les Filtres (« Recommandé », « B et + » pour vrai), le journal « Vitrine : N annonces montrables », `couverture.py`.
  GitHub Desktop affichait encore « 0 changed files » et ne réagissait pas aux clics (3e fois : 23 nov 20 h 54, 21 h 11,
  24 nov 8 h 12) : lui demander de le redémarrer, puis Commit + Push.
- **« Presque pas de cartes dans le Radar Pro, ça fait pas de sens » (Mathieu, 24 nov, 8 h 29, 25 min après le push de la
  règle « pas une carte neuve »)**. MA FAUTE : les annonces déjà en vitrine n'avaient pas leur signal `_vieux` ; `passe()`
  les refuse tant qu'il manque, et `_completer` ne passait qu'au balayage suivant du chasseur, 400 à la fois : « À la une »
  VIDE après la mise en ligne. Corrigé dans `lockerroom.py` (pas dans `vitrine.py`, qui fait partie de l'empreinte du test) :
  `vitrine._completer(vitrine.MAX)` juste avant `vitrine.liste(90, …)`. Test : fin de `test_radar_suivi_plein.py`. Leçon :
  une règle qui a besoin d'une donnée neuve doit remplir cette donnée AVANT d'être appliquée, pas « au prochain passage ».
  Reste vrai après la correction : la règle enlève environ une annonce sur trois de « À la une » ; lire au journal
  « Vitrine : N annonces montrables » après le push et le lui dire ; s'il n'y en a pas assez, c'est à lui de choisir entre
  84,6 % (règle en place) et 74 % avec toutes les cartes (`LR_RADAR_ANCIENNETE=0` dans Render, puis refaire le test du site).
- **« Le 505 est coupé » (24 nov, 8 h 18, fiche d'une annonce du Radar, vue Pro)** : la tuile « Mise actuelle » a 3 lignes
  (titre, chiffre, « 7 mises · + 13 $ port ») dans un tiers de la hauteur de la photo ; le chiffre (`overflow:hidden` dans une
  colonne flex) était le seul à pouvoir rétrécir et se faisait couper le bas. Corrigé pour les DEUX fiches : publique
  (`.fen.fa.fa-pub.fb .fb-t` : rien ne rétrécit, tuile plus serrée, petite ligne 11,5 à 14 px) et admin / Platine au téléphone
  (même défaut, pas signalé : 4 à 15 px coupés ; les 3 chiffres prennent `calc(19.9vw - 51px)` quand une tuile a sa 3e ligne).
  Mesuré avec `/home/claude/vue/fiche505.py` sur 11 tailles (320 à 1440 px) : tout tient, 2 px de marge au moins.
- **État du push (24 nov, 9 h 01)** : Mathieu a poussé à 8 h 55 (commit c4b3b3f, en ligne à 8 h 56, aucun Traceback) : la
  vitrine complétée par le Radar, le « 505 », la rangée suivie jamais vide, les Filtres, le journal « Vitrine : N annonces
  montrables ». Rien n'attend sur son PC. Pas encore de balayage ni de Radar ouvert 4 minutes après : le compte de « À la
  une » n'est pas encore au journal (un rappel est programmé dans cette conversation pour le lire et le lui dire).
- **Radar Pro : deux rangées (24 nov, 9 h 02 ; Mathieu, en vue Pro après la correction : « Only 34 are showing in pro's
  view… » ; à la question posée, il choisit « Deux rangées »)**. « À la une » = la règle prouvée, INCHANGÉE (84,6 %).
  Nouveau, juste dessous : « Très recherchées » = toutes les autres annonces dont la carte est A- ou mieux que le chasseur
  voit (jamais une base, 30 $ et plus), la meilleure note d'abord, sans la preuve de revente (au test, A et A+ sans la
  règle : 24 % gardent leur valeur). `vitrine.py` : la vitrine GARDE maintenant ces annonces avec leurs signaux (avant :
  `None`, oubliées pour de bon) ; `liste()` = prouvées, `recherchees()` = les autres ; nouveau fichier `vitrine2.json` qui
  reprend les annonces de `vitrine_liq.json` (« À la une » ne se vide pas à la mise en ligne) ; les anciens refus sont rejugés
  au balayage suivant (la rangée se remplit en une heure environ) ; quand la vitrine est pleine (4 000), les « Très
  recherchées » partent avant les « À la une ». `lockerroom.py` : clé `recherchees` dans la réponse du Radar (200 tuiles au
  plus ; une carte déjà « À la une » n'y revient pas : ses autres annonces se rangent sous sa tuile), ajoutée aux aides
  (pastilles, forfait gratuit, provenance). App : rangée « Très recherchées » ; dans une même lettre, les « À la une »
  passent avant. Site et app : la preuve dit maintenant « À la une » en toutes lettres (`outils/site_iq.py`, fenêtre SlabIQ).
  Empreinte changée (vitrine.py) : test du site refait et écrit (mêmes chiffres). Tests : `test_vitrine.py`,
  `test_radar_suivi_plein.py`. À VÉRIFIER après le push : le compte au journal (« Vitrine : N annonces montrables · … ») et,
  avec lui, ce qu'il voit en vue Pro ; si la rangée est trop mêlée ou trop longue, `RADAR_RECHERCHEES_MAX` (200).

## En attente
- **Méga test 3 ans (bâti le 22 nov, priorité 1)** : `mega_test.py` (serveur) part seul après le push (boucle de l'heure + reprise
  au démarrage ; `LR_MEGA_AUTO=0` pour l'empêcher). 1) Sonde : 5 crédits, les 5 cartes les plus vendues, fenêtre −1 095 à −730 jours ;
  rien de plus vieux que 2 ans → statut `essai_rate`, on s'arrête. 2) Collecte : le plan = les recherches `q` de base_ventes (carte
  exacte, `cartes_match.requete_ebay`), 30 $+, 3 ventes+ en un an, sans les recherches larges ; pages de 50, jusqu'à 1 095 jours,
  fenêtre qui s'arrête à la plus vieille vente connue (+2 j) si 10 ventes connues ; 30 pages max/carte ; arrêt si page répétée.
  Crédits : plafond 8 000 (admin), jamais plus que `LR_HISTORIQUE_MOIS` − `LR_MEGA_RESERVE` (1 500) ; à sec → `attente_mois`,
  reprend seul. Les ventes vont dans base_ventes (donc dans l'export). Admin → SlabIQ et données → « Méga test 3 ans ».
  3) La mesure : télécharger « Toutes les ventes (hockey) », puis `python3 outils/mega_test.py ventes_hockey.tsv.gz` (le test du site
  rejoué tous les 91 jours, coupes en jours : lettres avant fin−455 j, achats jusqu'à fin−90 j ; `tests_site.mesures` → `gains` :
  Radar Pro vs hasard, revente de la même carte à 90/180/365 j, frais 13,25 % + 0,40 $). Verdict « prouvé » à un horizon : à chaque
  date (3 au moins, 30 achats+), gain net médian > 0 ET rendement du panier > 0 ET plus de gagnants que le hasard. Résultat dans
  `outils/mega_test_resultats.json`, jamais sur le site sans l'accord de Mathieu. Tests : `tests/test_mega_test.py`.
  À vérifier par Mathieu : `LR_HISTORIQUE_MOIS` (95 par défaut = rien ne bouge). Leçon du 21 nov : toujours la même carte exacte,
  un pari par creux, frais compris.
- **Apple (URGENCE no 1 depuis le 23 nov au soir : rien n'est soumis, lancement le 1er décembre)** : calendrier en tête de
  `mobile/APP_STORE.md` (mardi 24 : accord « Applications payantes », abonnement, build Codemagic ; mercredi 25 : TestFlight,
  6 captures, fiche, soumettre en publication manuelle ; Action de grâce américaine le jeudi 26). Plan B à faire décider : lancer
  sur le web le 1er décembre si Apple n'a pas approuvé. Il met lui-même le code démo dans la note. Pas de « Bêta » visible.
  Après l'approbation : retirer le code démo (conseil dans `ceo.py`).
- **Deux réponses attendues de Mathieu (plan des 6 mois)** : son budget de données par mois et son temps par semaine (questions
  ouvertes sur le Whiteboard ; tâche `p6_budget`).
- **Baseball** : test SlabIQ à refaire dès que Mathieu exporte des ventes fraîches (Entraîner SlabIQ → ↓ Ventes Baseball).
- **Courriels de licence (7, dont Fanatics)** : attendent le connecteur Gmail et le choix de l'adresse d'envoi.
- **Cloudflare** : activer la 2FA (créer un mot de passe via « mot de passe oublié » car il se connecte avec Google),
  activer HSTS (Edge Certificates), ajouter DMARC p=none. Ne PAS activer Bot Fight Mode (bloque Stripe, Apple, eBay).
- **Aikido** (23 nov, capture de Mathieu : 1 critique, 2 hauts, 4 moyens, 3 bas) : le tableau datait d'avant le 20 nov au soir.
  DÉJÀ corrigés et en ligne : pickle dans `outils/banc_valeur.py` et `outils/radar_iq.py` ; « document write » de
  `site_slabiq.html` (DOMParser) ; HSTS (vérifié en ligne le 23 nov : `max-age=63072000; includeSubDomains` sur www.slabcoach.com).
  → Mathieu : RELANCER LE SCAN. À ignorer avec raison : liste IP GitHub (réservé à GitHub Enterprise), CSP (scripts par
  empreintes, object-src none, form-action self ; restent style-src unsafe-inline et img-src https:, nécessaires), SSRF (faux
  positif : `reseau_sur`, `tests/test_aikido_ssrf.py`), lightgbm.
  Les 22-23 nov, 34 scripts de `outils/recherche/` avaient RAMENÉ pickle : retiré le 23 nov (`cache_recherche.py` : .json.gz et
  .csv.gz, relus identiques). Le DERNIER pickle (`demande_legale.py`, le modèle sklearn de la demande des joueurs sans ventes) est
  parti le 23 nov en deux temps, pour ne jamais laisser ces joueurs sans modèle : (1) 15 h 13 : chaque passe horaire écrit aussi
  `demande_legale_arbres.json` et compare notre prédicteur (`ArbresJson`) à sklearn ; vu dans les journaux Render à 15 h 19 :
  « arbres JSON {'ok': True, 'type': 'GradientBoostingRegressor', 'arbres': 300, 'ko': 253, 'n': 920, 'ecart': 2.44e-15} » ;
  (2) `_arbres()` lit le JSON ; `labo()` ne garde le modèle d'arbres que si son JSON est écrit et vérifié (sinon la meilleure
  droite). PLUS AUCUN pickle dans le dépôt : `tests/test_sans_pickle.py` (aucune exception) et `tests/test_arbres_json.py`.
  L'ancien `/data/demande_legale_arbres.pkl` reste sur le disque, ignoré (pas de suppression sans permission).
  Render : Mathieu a confirmé l'espace « LockerRoom » pour LIRE les journaux (service `lockerroom`, srv-dbeacqfb9u1s73912rag) ;
  la ligne à chercher : « Demande legale : … ; arbres JSON … » (une passe peu après chaque démarrage, puis chaque heure).
- Prix annuel Stripe à confirmer. Réponse d'eBay (prix vendus montrés au public) toujours attendue.

- Inventaire = des CARTES seulement (20 nov 2026, Mathieu : « un cadre signe, c'est pas une carte ; pas de tables de cuisine ni de chaudrons ») : rien n'entre tout seul s'il n'est pas une carte a l'unite (cartes_match.est_carte_seule). Objets signes, cadres, photos, chandails, rondelles, fournitures, boites scellees, places de break : jamais importes automatiquement.

- Nouveautés (MAJ_APP dans source/src_app.html) : a chaque grosse mise a jour, ajouter une entree (n plus haut, date, 3-4 points en mots simples, ce qui change pour la personne). Demande de Mathieu, 20 nov 2026.

- Ergonomie (Mathieu, 20 nov 2026) : l humain est paresseux ; s il ne trouve pas l info en quelques secondes, il part. Chaque page, fenetre et option : l essentiel visible tout de suite, pas de grosses tuiles vides, pas de barre de defilement, entete compacte (une ligne a l ordi). Modele : Apple.

- To-do (Mathieu, 21 nov 2026 : « les priorites et choses a faire devraient toujours etre dans la to-do de la page admin ») : toute nouvelle priorite, decision a prendre ou chose a faire (pour Mathieu OU pour Claude, prefixe « Claude : ») va dans la to-do de l admin : un nouveau semis dans ceo.py (SEMIS["<nom>"], projet « lancement » ou autre, 7e element = echeance). Un document (docs/...) peut la resumer, jamais la remplacer.

- Pousser (Mathieu, 21 nov 2026 : « pousse toujours ») : apres chaque livraison (tests passes, md5 verifies sur le PC), Claude fait lui-meme Commit + Push dans GitHub Desktop sur le PC de Mathieu (commande de l ordinateur, acces a GitHub Desktop), sans redemander. Toujours par GitHub Desktop : jamais de git depuis la VM. Si GitHub Desktop n est pas joignable : le dire et laisser Mathieu pousser.

- Analyse d'etat (22 nov 2026, tests a l'aveugle Demidov, Hughes, Michkov) : `mesures.eclats` (points blancs sur une arete
  foncee, carton arrache a un coin, arete recalee, filtres holo et motif imprime), `mesures.trouver_carte_serree` (carte qui
  remplit la photo), `examen.clarifier` (FSRCNN x4, `modeles/`, OpenCV 4.10). Les eclats ne sont jamais montres tels quels :
  ce sont des candidats revus par le modele sur leur gros plan (`vision._candidats_verif`). Le compteur est trop sensible sur
  une texture fine : ne jamais afficher son nombre brut.

- **Recherche du 22 nov (soir)** : `docs/RECHERCHE_MODELE_22NOV.md`, scripts dans `outils/recherche/`. Méga test sur 1,15 M
  de ventes : toujours PAS PROUVÉ (perte nette médiane 11 à 28 %). Constats : les frais (13 %) mangent tout ; acheter le
  creux va dans le mauvais sens (dérive après performance, p 0,001 à 0,012) ; un pic de nouvelle tient (+8 %) ; « À vendre »
  tient sur la carte exacte (59-73 % vs 40-45 %) ; recrue de l'année : −37 % en 6 mois (une saison). Biais de survie dans
  l'historique du méga test. Proposition : « SlabIQ Timing » (attends / achète maintenant / vends), à tester avant d'en
  parler. Rien de ça n'est dans l'app ni sur le site.
- **Modele Timing (22 nov, soir)** : `outils/recherche/modele/` + fin de `docs/RECHERCHE_MODELE_22NOV.md`. Regle de mesure : le prix d'entree = mediane des 14 j APRES le signal (jamais le prix du signal, bruite). Avec ca le signal « vends a +20 % » tombe a 52 % (illusion) : a re-tester sur la liste A vendre avant le lancement. Ce qui tient : ATTENDS (carte jeune + cartes du joueur en baisse : -9 % a 60 j). Aucun achat ne bat les frais. Rien dans l'app. Grande recherche (`cherche.py`, 726 k regles, choisies sur le passe, jugees une fois apres) : aucun achat ne survit ; ATTENDS/VENDS TOT qui tient aux 3 horizons = carte de moins de 10 mois + ventes qui explosent (-11 a -17 %). Toujours juger hors echantillon.
- **« Que veux-tu faire ? » : le guide d'une page (23 nov, Mathieu : « le plus simple et efficace pour aider les nouveaux utilisateurs a comprendre tout ce que l'app fait » ; pas de chat IA)** : `guideApp(auto)` / `GUIDE_APP()` dans src_app.html : une fenetre (popOuvrir), 7 lignes = un besoin + le nom de la page (Radar, SlabIQ, Inventaire, Vendre, Tendances, Breaks, Alertes), un toucher y mene ; la 1re ligne suit son but (`reglages.objectif`). Montree UNE fois au nouveau compte, apres ses 3 questions (`guideAppAuto`, reglage `guide_app` + localStorage `sc_guide_app`, jamais par-dessus une autre fenetre). Toujours a un toucher : `[data-guide]` = le « ? » en haut a gauche au cell (`.haut-aide`, l'ancienne case vide) et dans la barre de cote a l'ordi (`.nav-aide`), plus Profil › Le tour de l'app. L'ancien tour en 8 ecrans (`TUTO`, `tutoriel`) est retire. 35 mots (regle : 40 au plus). « Mise a jour » : `MAJ_APP` n 242. Test : tests/test_guide_app.py. Idee gardee pour apres le lancement : un champ « ecris ce que tu veux » (mots-cles, puis IA qui choisit seulement parmi ces 7 pages).
- **« Au plus haut » revient, comme un fait (23 nov, Mathieu : « on a enleve "at their highest" ?! »)** : `marche_joueurs.liste_haut` (le pendant de `liste_bas` : au plus haut depuis 30 jours et plus, +10 % et plus vs sa normale) -> `cats["haut"]` dans `tendances_iq` quand `VENTE_PROUVEE` est False (bon joueur actif, A ou B). A l'ecran : il prend la case de « A vendre » (`pan('haut', ..., 'vendre haut')`), phrase « Un fait, pas une promesse », pastille verte, « Tu en as N » ; aucune barre, aucune preuve, aucune notification, aucune pastille « Vends ». Au cell, 4 choix sur une rangee : « Plus bas | Plus haut | Joueurs | Cartes ». Tests : test_marche_joueurs.py, test_tendances_marche.py.
- **Nouvelle WOW : contour egal (23 nov, Mathieu : « normal, le mauve plus epais a gauche ? »)** : la barre d'accent a gauche (`inset 3px`) suivait les coins ronds ; `.nl-wow` a maintenant un contour fin partout.
- **Voir l'app pour vrai (a faire avant de livrer un ecran)** : serveur local (commande ci-dessus ; il s'arrete seul des qu'un fichier .py change : le relancer), puis Playwright avec `executable_path="/usr/bin/google-chrome"` (cell 390×844, ordi 1465×694). En local on est admin ; `changerVue('gratuit')` montre l'app d'un nouveau. `API` est un Proxy : pour de fausses donnees, intercepter la reponse (`page.route("**/api/tendances_iq", ...)`), pas remplacer la methode.
- **Radar Pro plus strict + comparatif « seul ou avec SlabCoach » sur le site (23 nov, Mathieu : « analyser toutes les avenues », puis « B : 78 % »)** : `liquidite.py` : `LIQ_MIN = 8` (avant 5) et `RABAIS_MAX = 0.0` (avant +10 %) : 8 ventes de la meme carte en 60 jours, jamais au-dessus de sa mediane recente. Test officiel refait : 77,7 % gardent leur valeur (avant 63,0 %), 90,1 % se revendent (avant 81,4 %), 24,8 % rentables apres frais (avant 20,2 %), 475 achats (avant 1 046) ; mieux aux 5 dates du bulletin. Le gain de « 8 ventes » vient de la liquidite ; celui de « <= mediane » du prix paye (le marche de la carte ne tient pas mieux). Moins d'annonces passent : si le Radar Pro est trop vide, `RABAIS_MAX = 0.10` puis refaire tests_site + bulletin. Recherche : `outils/recherche/avenues/` (LISEZMOI.txt). A+ sous A dans les reventes par lettre = la mesure (A+ : 1 130 $ en mediane, peu de copies), pas la lettre ; le graphique des reventes par lettre est retire de la page SlabIQ (Mathieu : « enleve, ca va porter a confusion » ; la mesure reste dans slabiq_tests.json). **Site** : `outils/site_iq.bloc_vs(R, page)` ecrit le comparatif entre `<!--vs-->` et `<!--/vs-->` (accueil : section #slabiq ; page SlabIQ : #tests, a la place des 3 tuiles) : 3 gros chiffres (garde sa valeur, se revend, A contre E), 2 barres chacun (Radar Pro / seul). « Seul » = tous les achats de 30 $ et plus de la meme periode (le « hasard » du test). Styles `.cmp*` dans `ui/site_base.html` (les `.vs*` de la page SlabIQ sont un autre bloc) ; les barres grandissent une fois (script de la base). Arrondis : `iq_publie.pro` et `iq_publie.revendue` (Radar Pro vers le bas, seul au plus proche). `tests/test_site_a_jour.py` exige que le bloc du site soit exactement celui du test. Voir une page sans serveur : rendre `server._page_vitrine` en fichier puis `google-chrome --headless=new --screenshot` (Chrome est dans le bac a sable).
- **Signal v1.2, la boucle complete (23 nov)** : `outils/recherche/modele/boucle.py` et `profil.py`. Gros match + deja chaud (5 pts+ aux 5 matchs d'avant) ou chapeau = ACHETE fort : +13 a +17 % a 30 j, tient 4 mois ; jeune joueur deja chaud : +28 % a 30 j, +36 % a 60 j, 8 sur 10 (12-14 joueurs, une saison : a confirmer ; ★★ dans l'admin). Gros match ISOLE = `FENETRE` (monte 2 semaines, retombe a zero en 30-60 j : fenetre de vente, pas un achat ; note sur `y14`, jours 2 a 14). Sortir quand le joueur refroidit ne sert a rien (14 regles testees) : garder 60-90 j. Depuis aout 2026 le marche reagit en un jour : tout le gain est dans le prix d'avant. En recherche, la saison recrue = la plus vieille annee des cartes recrues (pas le mode).
- **Tendances a l'ordi + WOW (23 nov)** : sans « A vendre », le tiers droit restait vide -> `.tiq-av.tiq-c3` (une liste : 3 colonnes egales Au plus bas | Joueurs | Cartes, `.tiq-col{display:contents}`) ou `.tiq-c2` (aucune liste) ; 10 rangees rendues par bloc, 5 visibles par defaut (cell, 2 listes), 8 a 700 px de haut, 10 a 840 px. **Nouvelles WOW** : `nouvelles.wow_de / marquer_wow` (gros joueur = joueur cle, vedette, Indice 60+/70+ ou 400+/600+ points en carriere ; echange FERME, Temple, honneur, trophee, exploit ; une seule par joueur et type ; epinglee 48 h en tete du fil) ; a l'ecran `nlSur`, `nlWow`, classe `.nl-wow` (or). **Bandeau du Radar** : `Api.wow_actuel()` (echange d'un gros joueur vers/depuis TOR/MTL, 4 jours ; puis autres WOW) -> `wowRadar(z)` insere UN bandeau sous `.md-barre` ; un toucher lance la recherche du Radar sur le joueur ; ✕ = ne revient pas (localStorage sc_wow_vus). Rien n'est reclasse. Test : tests/test_wow.py.
- **« A vendre » retire (23 nov, Mathieu : « oui, enleve si ce n'est plus bon »)** : `lockerroom.VENTE_PROUVEE = False` (comme ACHAT_PROUVE) : plus de pastille « Vends » dans l'inventaire, plus de notification « Temps de vendre » (l'interrupteur des reglages est cache : `alarmes_lire().vente_prouvee`), plus de liste « A vendre » dans Tendances ni de signal « vendre » dans la fiche du joueur. Raison : 59-73 % contre le prix du signal, 51-52 % contre le prix reel des 14 jours suivants. Le mecanisme et ses tests restent (VENTE_PROUVEE = True le rallume). « Garde-la » / « Marche bas » (marche_cles) avait le meme defaut : `verifier` jugeait « remonte » contre l'indice du jour du signal (choisi parce qu'il etait bas : retour a la moyenne garanti). Corrige le 23 nov : choisi sur l'indice du jour, JUGE contre l'indice des 14 jours qui suivent (`points_passes` renvoie aussi `ex`) ; VERSION 3 force le recalcul ; si aucun seuil ne bat le hasard au prix reel, la pastille s'eteint seule (actif = False). Replique sur les donnees de recherche : 35-37 % de remontees contre 37 % pour le hasard. REGLE GENERALE : ne jamais juger un signal contre le prix qui l'a declenche.
- **Signal par joueur EN DIRECT, admin seulement (23 nov, Mathieu : « go »)** : `signal_joueurs.py` + Admin → Mesures → « Signal par joueur » (`feuilleSignalJoueurs`, API `signal_joueurs_admin`). Passe de l'heure dans server.py : lit les soirs manquants (1 appel `/v1/score/JOUR` + 1 `/v1/gamecenter/ID/boxscore` par match termine ; 40 appels au plus par passe ; 45 jours de rattrapage ; historique amorce par le cache du test SlabIQ, sinon `game-log` de 5 joueurs par passe). Cas = `annee_recrue` (Calder) -> recrue / jeune / veteran. Regles v1.1 : gros match, tour du chapeau, jeune en feu = ACHETE (fort si deja chaud : 5 pts+ aux 5 matchs d'avant, ou chapeau) ; jeune en panne = ATTENDS ; recrue en panne = VENDS ; echange vers TOR/MTL = ACHETE fort, en partir = VENDS ; les regles retirees par la recherche restent OBSERVE (notees, jamais conseillees). Journal `signal_journal.json` : une ligne par signal, jamais retouchee ; « direct » = ecrite dans les 36 h du match, sinon « rattrapage ». Note une fois par jour (`noter`) : meme carte (cle canonique du decodeur), 7 j avant contre jours 8 a 60 ; finale au jour 61. Aucun prix dans le declencheur. `LR_SIGNAL_JOUEURS=0` coupe tout. Rien n'est montre aux clients. Test : tests/test_signal_joueurs.py.
- **Echange capte vite (23 nov)** : Larkin echange a Montreal un dimanche soir ; les alignements n'etaient relus qu'aux 20 h. `indice_joueurs.rosters_vite` : une nouvelle d'echange FERME (ECHANGE_FERME sans ECHANGE_RUMEUR) qui nomme un de nos joueurs (nom de famille seul accepte, 6 lettres+) force la relecture des alignements de la saison (32 appels ; au plus aux 75 min et 10 par jour). La saison d'avant se relit aux 7 jours. Le matin du 23, Larkin n'etait sur AUCUN alignement (retire de DET, pas encore a MTL) : `echange_par_nouvelles` note donc l'echange depuis les manchettes (source « nouvelles ») si : mots fermes, UNE seule equipe d'arrivee dans le titre (`equipes_du_titre`), et deux sources d'accord OU une source + joueur absent de l'alignement de son club. L'alignement confirme ensuite (« nouvelles+vu », la date de la manchette reste) ou efface (encore dans son club 3 j apres ; nulle part apres 10 j). Test : tests/test_echange_vite.py.
- **Signal par joueur v1 (22 nov, fin de soiree)** : decide avec Mathieu : la promesse = « acheter et vendre au bon moment », pas le profit de revente. `outils/recherche/modele/` (LISEZMOI.txt dedans). Cle canonique `cle2.py` (decodeur de l'app) = 2 fois plus de cas. Les techniques de bourse (EMA, SMA, RSI, croisements) ne donnent rien a l'achat. Ce qui bouge un joueur = ses matchs, au jour pres (meme carte avant/apres) : gros match +4,5 % le lendemain et +5,9 % a 2 mois, tour du chapeau +20 %, jeune en panne -7 %, recrue en panne -21 %. Signal rejoue : ACHETE +6,2 % et 6,1 sur 10 (cartes fortes SlabIQ +8,4 %) ; signal fort appris hors echantillon : +15,8 % et 7,6 sur 10 (72 cas). Declencheur = donnees publiques LNH + Wikipedia, aucun prix eBay. Pas dans l'app : prochaine etape = suivi en direct en admin.
