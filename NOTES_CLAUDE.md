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
- **La liquidité compte mal les ventes (24 nov, 10 h 17 ; Mathieu, devant une Rantanen UD Canvas Young Guns PSA 10 de
  slabsharksinc partie à 63 $ C en encan : « j'espère qu'on l'avait captée »)**. Impossible de vérifier d'ici ce que son Radar
  montrait à ce moment-là. Ce que la règle aurait fait : PAS « À la une » : sous son titre exact la carte avait 2 ventes en 60
  jours chez nous (il en faut 8), et ces 2 lignes sont la MÊME vente (92,97 et 92,99 $ le 22 oct). Deux défauts trouvés
  (`outils/recherche/garde/cle_carte.py`) : (1) LA MÊME VENTE EST GARDÉE PLUSIEURS FOIS : la clé de `base_ventes.ventes` est
  (q, url) : une vente trouvée par 3 recherches = 3 lignes, au prix converti à quelques cents près ; l'index
  (`liquidite`, clé (cle, le, prix, h)) ne les confond pas. Estimé sur les ventes de 30 $ et plus des 90 derniers jours (même
  titre, à 1 jour près, prix à 1 % près) : 53 272 lignes sur 149 257 (36 %). L'export (titre, prix, le, q) n'a pas l'URL : pas
  de dédoublonnage exact possible dans le test. (2) LA MÊME CARTE A PLUSIEURS CLÉS : `liquidite.cle` = tous les mots du titre
  (« 2015 » et « 2015-16 », « Series 1 », l'ordre des mots) : la Rantanen = 59 lignes sous 21 clés. Effet sur les cartes
  « liquides » (8 ventes en 60 jours ET vendue il y a 2 mois) : en place 386 ; sans doublons 165 ; clé canonique (le décodeur,
  comme `outils/recherche/modele/cle2.py`) sans doublons 489. Donc aujourd'hui « 8 ventes » veut souvent dire 3 ou 4 vraies
  ventes, et de vraies cartes liquides sont refusées. À FAIRE (pas commencé, un vrai chantier : il touche la règle testée) :
  ajouter un identifiant de vente à l'export (`/admin/ventes_export.tsv.gz` : l'URL hachée), dédoublonner par cet identifiant
  dans l'index et dans le test, passer `liquidite.cle` à la clé canonique (nouvel index, relecture des archives), puis banc
  CHOIX / JUGE, test du site et bulletin. Les chiffres publiés (84,6 %) sont mesurés AVEC ces doublons : à refaire ensuite.
  Vraies ventes récentes de la Rantanen (PSA 10) : 80 $ (9 oct), 93 $ (22 oct), 70 $ (30 oct), 114 $ (16 nov).
- **Les vraies ventes : le chantier (24 nov, 10 h 23 ; Mathieu : « Oui on doit être parfait avant Apple »)**. FAIT dans le bac
  à sable (PAS livré tant que le test du site n'est pas refait avec des doublons exacts) :
  `liquidite.py` : `VERSION = 2`, nouvel index `liquidite2.sqlite` (clé (cle, idv) : une vente = le numéro de l'annonce
  vendue, `id_vente`), `cle_base` (la clé stricte sans le bruit d'écriture : saison, dièse, « Series 1 », « Upper Deck » /
  « UD », ponctuation), `LIQ_MIN = 5` (5 VRAIES ventes ; choisi au banc : 85,3 % / 89,7 %, 131 cartes différentes à la
  dernière fenêtre, contre 85,6 / 84,8 % et 83 cartes avant). La clé du décodeur (cle2) est REJETÉE (confond des cartes).
  `vitrine.py` : `_sv` (version des signaux) : les annonces en vitrine sont relues dans le nouvel index dès qu'il est prêt.
  `outils/tests_site.py` : une vente = une ligne (colonne « id » de l'export ; sans elle : doublons estimés et REFUS
  d'écrire le site), clé de carte = `liquidite.cle_base` (toutes les mesures : « la même carte » veut dire la même chose
  partout), `doublons` dans les résultats. Tests : `test_ventes_une_fois.py`, `test_vitrine.py`, `test_export_id.py`.
  LIVRÉ sur son PC et à pousser par lui : `server.py` (l'export a la 5e colonne « id », jamais le lien). ENSUITE : il
  télécharge « Toutes les ventes · Hockey » et le joint ; alors : `banc2.py <A> <trav> <export>` + `regles2.py` (revalider
  5 ventes avec les doublons exacts), `tests_site.py <export> --ecrire`, `bulletin_iq.py <export> --ecrire` (4 dates, 50
  min), suite de tests, livraison de TOUT (liquidite, vitrine, tests_site, site, tests, recherche). Après la mise en ligne :
  l'index se rebâtit seul en fond (quelques minutes) ; lire « Vitrine : N annonces montrables » au journal.
- **Les vraies ventes : RÉSULTATS (24 nov, midi ; export de 10 h 52 avec la colonne « id » : 1 778 722 lignes pour 1 264 949
  annonces vendues, soit 29 % de lignes en double)**. « La même vente » = la même annonce, à un jour et 5 % près
  (`liquidite.meme_vente`, la même fonction dans l'index du serveur et dans `tests_site.charger`). Banc (doublons exacts) :
  5 ventes = 87,5 % (choix) / 90,3 % (jugé), 116 cartes différentes à la dernière fenêtre (avant : 85,6 / 84,8 %, 83).
  Test officiel ÉCRIT sur le site (achats du 9 sept au 15 oct 2026, 620 380 ventes) : « À la une » 87,1 % (638 achats, IC
  84,6-89,7), se revend 98,7 %, seul 12,7 %. DEUX CHIFFRES BAISSENT (les doublons les gonflaient) : A et A+ contre E 4,3 fois
  (le site dit 4× ; avant 6×) et l'accord avec le marché 0,685 (68 % ; avant ≈ 75 %). B reste sous C. Le site dit : 87 %
  contre 13 %, 98 % contre 25 %, 4×, 68 %, 620 k+ ventes. `deals._vitrine` : le journal dit maintenant « Vitrine : N a la
  une · M tres recherchees · J jugees ». Vu au journal avant ce chantier (10 h 53) : 14 à la une, 231 annonces jugées depuis
  la remise à zéro de la vitrine : la rangée « Très recherchées » se remplit au rythme du chasseur, pas en une heure.
- **Les vraies ventes : LIVRÉ (24 nov, 13 h)**. Bulletin refait aux 5 dates sur les vraies ventes (29 sept, 13 oct, 27 oct,
  10 nov, 24 nov) : 88, 91, 92, 90, 87 % ; seul 15, 16, 13, 12, 13 % ; le site dit « 87 à 91 % », « 12 à 16 % », « 5 fois sur
  5 ». Suite de tests complète : passe. 17 fichiers sur son PC (md5 vérifiés) : `liquidite.py`, `vitrine.py`, `deals.py`,
  `outils/tests_site.py`, le site (`ui/site_slabiq.html`, `ui/site_accueil.html`, `ui/slabiq_tests.json`,
  `ui/slabiq_bulletin.json`), l'app, les tests, la recherche. APRÈS SON PUSH : (1) l'index `liquidite2.sqlite` se rebâtit
  seul en fond dès la 1re ouverture du Radar (une à trois minutes ; d'ici là les annonces en vitrine gardent leurs anciens
  signaux) ; (2) lire au journal « Vitrine : N a la une · M tres recherchees · J jugees » et le lui dire ; (3) vérifier
  qu'il n'y a pas de « Liquidite (index) : … » ni de Traceback. Liste « Amélioré cette semaine » du site : ligne ajoutée
  « Chaque vente comptée une seule fois » ; la ligne « 214 joueurs ajustés par le marché » n'est toujours pas vérifiée.
  PAS FAIT : la même carte écrite SANS son numéro (« C98 » sans dièse, ou pas de numéro du tout) garde une autre clé ; les
  annonces à plusieurs exemplaires vendus le même jour au même prix comptent pour une vente.
- **État (24 nov, 12 h 25)** : Mathieu a poussé à 12 h 16 (commit dbdd62b, en ligne à 12 h 18, aucun Traceback ni
  « Liquidite (index) » au journal). Le site en ligne dit : 87 % contre 13 %, 98 % contre 25 %, 4×, 68 %, « 87 à 91 % »,
  « 5 fois sur 5 » (vérifié). Journal à 12 h 23 : « Vitrine : 16 a la une · 1211 tres recherchees · 6606 jugees » (peut-être
  avant la fin de la reconstruction de `liquidite2.sqlite` : un rappel est programmé pour relire le compte). Rien n'attend
  sur son PC sauf ces notes. À PENSER (pas un défaut nouveau, mais à dire clairement un jour) : « À la une » montre un encan
  tant que sa mise COURANTE est sous la médiane ; le test, lui, juge les achats au prix FINAL sous la médiane. Un encan qui
  finit au-dessus sort de la rangée avant la fin, mais l'utilisateur Pro ne voit pas jusqu'où il peut miser (la licence
  interdit de montrer un prix tiré d'eBay) : le 87 % vaut pour celui qui achète pendant que la carte est encore affichée.
- **« 214 joueurs ajustés par le marché » RETIRÉE du site (24 nov, 12 h 27 ; Mathieu : « non je ne sais pas, donc si tu sais pas
  aussi, retire »)** : la ligne de la liste « Amélioré cette semaine » (`ui/site_slabiq.html`, écrite à la main) n'avait aucune
  source (ni test, ni notes). Règle rappelée : une ligne du site sans mesure derrière se retire.
- **Le nombre du Radar : UN seul partout (24 nov, 12 h 50 ; Mathieu : « pourquoi 99+ dans la page Radar et 11 dans la page
  d'accueil ? »)**. Deux causes dans `lockerroom.py` : (1) le compte de l'accueil (`_mes_deals_garde`) oubliait les deux rangées
  du haut (`a_la_une` depuis le 19 nov, `recherchees` depuis ce matin : MON oubli) ; (2) il était rangé sous une clé (compte +
  provenance + forfait) et relu par `acheteur_accueil` sous une autre (sans le forfait) : l'accueil retombait toujours sur la
  longueur de son carrousel (24 au plus). Corrigé : `Api._radar_tout(r)` (chaque annonce de chaque rangée une fois, les mêmes
  rangées que l'app : `_TOUT_PLATES`, `_TOUT_GROUPES`), compté dans `mes_deals` à CHAQUE Radar envoyé (`_radar_compter` :
  `tout_n`, `tout_le` = heure du serveur), relu par l'accueil sous la même clé (`_cle_tout`) : `nb_deals`, `nb_deals_le`.
  Dans l'app : `radarNb(n, le)` garde le plus récent des deux et écrit l'onglet du bas ; `nbRadarAccueil(a)` pour les tuiles ;
  le nombre s'écrit en entier (`nbTxt` : 214, plus « 99+ » ; « 999+ » au-delà). Étiquette de la tuile : toujours « N pour toi »
  (« à ton prix » aurait été faux pour tout le Radar). `changerVue` remet `S.nbRadar` à zéro. Test `tests/test_radar_meme_nombre.py`
  (dont : les rangées lues par l'app = celles comptées par le serveur). **Le « 35 » de 12 h 30** n'était pas un bogue de compte :
  c'était le DERNIER Radar gardé (serveur : 6 h ; téléphone : 36 h), montré pendant que le neuf se calculait (journal : « Pile
  lente : /api/mes_deals 8 s » à 12 h 30 min 59 s) ; il se remplace seul 20 s plus tard si on est en haut de la page.
- **Tri « Meilleur deal » avec « Encans » (24 nov ; Mathieu : « quand je clique sur Best deal, ça revient à Ending soon »)** :
  `appliquer` de `feuilleFiltresDeals` remplaçait EN SILENCE `rabais` par `fin` quand le type était `encan`. Maintenant : choisir
  « Encans » propose « Finit bientôt » sous ses yeux (la mise d'un encan monte) ; « Meilleur deal » rechoisi RESTE.
- **Feuille Filtres façon Réglages d'iOS (24 nov ; Mathieu : « que ça fitte sur une page ; fie-toi tout le temps à la méthode
  Apple ; la personne se retrouve sans s'en rendre compte »)**. Règle de design à garder pour TOUTES les feuilles de réglages :
  groupes arrondis (`.io-g`), une rangée de 44 px par choix (`.io-r`) : le nom à gauche, le choix en gris à droite + double
  chevron, et le menu NATIF du téléphone (un `<select>` invisible couvre la rangée : `.io-m`, aide `menu(id, nom, L, v)` +
  `lier`/`poser`) ; interrupteur 51 × 31 (`.io-sw`) ; « Réinitialiser » en haut à gauche, titre centré, le X ; « Appliquer »
  apparaît en bas au premier changement. « Expédiées de » : un menu à 3 choix ; « Cartes » : 3 pastilles sur la rangée (choix
  multiple) ; mes joueurs : une rangée qui défile de côté. Mesuré : 997 px → 591 px (665 avec « Appliquer ») pour une feuille de
  767 px (iPhone de 852 px) ; iPhone SE (667 px) : rangées de 40 px, 619 px, sans défiler. Scripts `vue/filtres.py`,
  `vue/filtres2.py`. Test `tests/test_filtres_ios.py`. Les règles `.fx-*` (pastilles) sont retirées. À FAIRE dans le même
  style : la feuille « Ton radar » de la vue Pro et les autres feuilles de réglages (pas encore converties).
- **Revue avant l'envoi à Apple (24 nov, 13 h 05 ; Mathieu : « qu'est-ce qui vaudrait la peine d'être repassé avant l'envoi à
  Apple ? je te laisse me dire où aller et on le fait »)**. Constat de départ (vérifié : `mobile/capacitor.config.json`,
  `server.url` = le site) : l'app iPhone est une coquille qui charge le site. Donc : ce qui compte AVANT de soumettre, c'est
  (1) ce qui est dans la coquille (textes des permissions, écran hors ligne, icône : déjà passés le 27-28 oct, relus, corrects)
  et (2) le chemin de la personne d'Apple pendant ses 10 minutes (connexion → Démo → accueil → Radar → fiche → Profil → GO PRO →
  supprimer le compte). Tout le reste (mise à jour automatique des données, nouvelles, SlabIQ, standardiser TOUTES les pages)
  est du côté du serveur : ça se livre n'importe quel jour APRÈS, sans nouvel examen. Ordre retenu : 1. l'écran de connexion
  (FAIT, ci-dessous) ; 2. les feuilles du chemin d'Apple au style iOS des Filtres (Profil, Pro, Mon compte, « Ton radar ») :
  À FAIRE ; 3. pendant l'examen, un seul push par jour, tard le soir (ajouté au calendrier de `mobile/APP_STORE.md`) ;
  4. après l'envoi : `g_c_auto` (26 nov), puis le reste des pages. Sécurité : le scan Aikido est corrigé (20 nov) ; il reste SES
  réglages Cloudflare et la 2FA (`g_cloudflare`, `g_comptes`). Aucune tâche ajoutée à la liste (elle est à sa limite : 25).
  **Écran de connexion** (`ui/connexion.html`, `server.py`) : lu les règles en vigueur le 24 nov (developer.apple.com :
  App Review Guidelines 3.1.1(a), 4.8 ; guide « Sign in with Apple »). Trois corrections : (a) DANS l'app iPhone, la ligne
  « Paiement par Stripe ou Apple » nommait Stripe : remplacée par « Aucun mot de passe gardé · données jamais vendues » (3.1.1(a) :
  hors des États-Unis, aucun bouton, lien ni appel à l'action vers un autre moyen de paiement ; une simple mention n'est pas
  traitée par la règle, mais elle n'apportait rien dans l'app) ; le site garde sa ligne ; (b) le bouton Apple suit le guide
  d'Apple pour un bouton sur mesure : pas plus petit que les autres, visible sans défiler (iPhone SE compris : tout tient en
  667 px), blanc sur fond sombre, logo et titre noirs, titre à 43 % de la hauteur (50 px → 21,5 px), police du système d'abord ;
  sur un appareil Apple, le logo est le glyphe du système (U+F8FF), vérifié par un dessin d'essai, sinon le tracé reste ;
  (c) la note « Sur l'iPhone, chez eBay… » restait en français dans la page anglaise (vieilles versions de l'app seulement) :
  traduite. Les trois boutons sont dans UNE pile (`.conn`), même hauteur, même police ; le « ou » est retiré. NON vérifié sur un
  vrai iPhone : le glyphe du logo Apple (mon navigateur d'essai n'a pas la police d'Apple) : Mathieu doit le regarder une fois
  (Safari → slabcoach.com/connexion). Le guide d'Apple dit de n'utiliser que le logo téléchargé d'Apple Design Resources : si
  Apple accroche là-dessus, y prendre le fichier SVG officiel. Test `tests/test_connexion_apple.py`. Script `vue/connexion.py`
  (aperçu local : `LOCKERROOM_MULTI=1` + des valeurs bidon pour GOOGLE_* et APPLE_* afin d'afficher les trois boutons).
- **La vérification par photo du chasseur ne tournait plus depuis le 20 nov au soir (trouvé le 24 nov, 13 h 30, en lisant le
  journal pour le suivi des rangées du Radar)**. Journal Render : « Compte manquant (dossier, fil deals) : refuse » puis
  « Deals (photo) : SansCompte('Aucun compte pour dossier') », 100 fois en 8 minutes (12 h 25 à 12 h 33), la première le
  21 nov à 00:06:57Z, soit la mise en ligne du garde-fou du 20 nov (`comptes.garde` : en ligne, sans compte = refusé). Cause :
  `vision.verifier_deal` lisait le compteur du SERVEUR par `_chemins()`, qui demande d'abord le dossier d'un COMPTE ; le
  chasseur tourne sans compte. `deals.photo_refusee` attrapait l'erreur et gardait le deal : depuis 4 jours, aucun deal très
  sous la médiane (`PHOTO_RATIO` 0,50) n'était vérifié par photo, et l'onglet Erreurs de l'admin se remplissait.
  Corrigé : `vision._chemin_serveur()` (le fichier du serveur ne passe plus par le dossier d'un compte ; les 5 lectures du
  compteur du serveur l'utilisent). Le garde-fou du 20 nov reste entier (`_chemins()` sans compte est toujours refusé).
  Dépense : inchangée dans ses plafonds existants (40 photos par jour `DEALS_PHOTO_JOUR`, 50 $ par mois
  `LR_VISION_PLAFOND_USD`) ; aucun plafond touché. Aucun autre « Compte manquant » dans le journal depuis le 21 nov.
  Test `tests/test_photo_chasseur.py`. LEÇON : chercher « Traceback » ne suffit pas pour lire le journal : `comptes.garde`
  écrit une pile SANS ce mot. Chercher aussi « Compte manquant » et les lignes « X : Erreur(...) ».
  **Suivi des deux rangées** (tâche planifiée de 13 h 05) : aucune nouvelle ligne « Vitrine : … » depuis 12 h 23
  (16 à la une · 1 211 très recherchées · 6 606 jugées) ; le serveur a redémarré à 13 h 04 (push).
- **Le chemin de la personne d'Apple, passé écran par écran (24 nov, 13 h 50 ; point 2 de la revue avant l'envoi)**. Script
  `vue/chemin.py` (iPhone simulé 393 × 852, agent de l'app, faux plugin d'achat ; serveur local `LOCKERROOM_MULTI=1` +
  `LOCKERROOM_DEMO_CODE`) : Démo → questions d'accueil (« Passer ») → accueil → Profil (`#reglages`) → Mon compte → Aide,
  déconnexion, suppression → Supprimer → GO PRO → Radar. Constat : ces écrans étaient déjà en listes ; pas de refonte.
  Quatre corrections : (1) **« Noter SlabCoach sur l'App Store » menait à une page qui n'existe pas** (l'app n'est pas publiée :
  `apps.apple.com/ca/app/id6827726629` répond par une erreur) : un lien mort pendant l'examen. La rangée ne s'affiche que si
  Apple renvoie la fiche de l'app : `avis_app.en_ligne()` (le lookup iTunes, relu aux 6 h ; `lire_lookup` rend aussi `existe`),
  passé à l'app par `forfait().app_store`. Elle apparaîtra seule après la publication. (2) **La feuille d'achat de l'iPhone
  tient sur un écran** (832 px → 710 px pour 767) : nom, durée, prix, « S'abonner », « Restaurer », renouvellement, Conditions et
  Confidentialité sans défiler (styles `#feuille:has(#fp-apple) …`). (3) **« Aide, déconnexion, suppression »** en liste groupée
  d'iOS : trois groupes (l'aide ; se déconnecter ; supprimer en rouge), bloc marqué `.r-aide`, séparateurs `.r-sep` (invisibles
  hors de la feuille). (4) « Supprimer mon compte » : le lien des abonnements Apple en couleur d'accent, le champ respire.
  Vu et laissé tel quel : le Profil (déjà des rangées avec chevrons), la fenêtre « Ton radar » (rangées, deux boutons), les
  questions d'accueil. Test : `tests/test_avis_app.py` (publiée ou non, Apple muet). Les captures : `vue/chemin_apres_*.png`.
- **Vitesse du Radar : mesuré dans le journal, trois correctifs, des temps par étape (24 nov, 15 h ; tâche `g_c_vitesse`
  devancée parce que la personne d'Apple ouvrira le Radar)**. Faits (journal Render, « Lent : POST /api/mes_deals ») : 20,4 s,
  21,2 s, 30,4 s, 29,0 s (juste après le push de 14 h 48), 12,5 s, 8 à 9 s ; ce n'est PAS seulement après un redémarrage. Dix
  piles de Radars lents (« Pile lente : /api/mes_deals ») : 3 dans `_radar_admin_vendu → vendues.memes_cache →
  vendues.archives` (ADMIN seulement, plafonné à 6 s ; la requête `titre LIKE '%nom%'` balaie 1,78 million de ventes : à
  refaire avec un index, pas fait) ; 3 dans `reglages_lire` ; 2 dans le score (`indice_joueurs.lire → getmtime`,
  `demande_legale.lire → exists` : un appel au disque PAR CARTE) ; 2 en attente des recherches eBay (limite 15 s,
  `LR_RADAR_DELAI_S`) ; 1 dans `_radar_garder`. Mesuré dans le bac : le score lui-même est rapide (0,5 à 0,9 ms par annonce).
  Corrigé : (1) `reglages_lire` gardé 2 s par base (`Api._REGL`, `REGL_S`), vidé par `reglages_sauver` et `logo_sauver`
  (`_reglages_oublier`) ; rend une copie ; (2) `indice_joueurs.lire` : la date du fichier au plus aux 2 s (`_ecrire` se voit
  tout de suite) ; (3) `demande_legale.lire` : la vérification d'existence passe APRÈS le raccourci de 2 s. Ajouté : la ligne
  « Radar (temps) : 19.3 s = préparation 0.4 · recherches 9.1 · scores 2.3 · … | 12 recherches, 0 trop longues ; les plus
  lentes : … | N annonces gardées » écrite quand un Radar prend 4 s et plus (`LR_RADAR_TEMPS_S`). Test
  `tests/test_vitesse_radar.py`. À FAIRE après le push : lire ces lignes, puis décider avec des chiffres : (a) un premier Radar
  « rapide » pour un compte sans Radar gardé (les deux rangées de la vitrine tout de suite, le reste 20 s après : le compte
  démo d'Apple est dans ce cas, et un Radar gardé de plus de 6 h aussi) ; (b) l'index pour `vendues.archives`.
  À savoir : Mathieu en vue Pro simulée n'a JAMAIS le Radar gardé (calcul complet à chaque ouverture) : ses temps sont le pire cas.
- **AUDIT AVANT LE LANCEMENT (24 nov, 15 h ; Mathieu : « repasse chaque fonction et calcul ; un audit intense de l'app et du site
  avant le release officiel »)**. Le rapport vivant : `docs/AUDIT_LANCEMENT.md` (chaque trouvaille : corrigé / à décider /
  sans risque). Cinq passes : 1 calculs d'argent (EN COURS), 2 SlabIQ-Radar-chiffres, 3 chaque fonction du serveur (FAIT),
  4 l'app écran par écran, 5 le site. Fait ce jour : `outils/audit_api.py` (321 fonctions, 4 083 appels, compte gratuit et
  sans session, arguments tordus ; `--test` = les règles qui ne doivent jamais casser ; `tests/test_audit_api.py` le lance à
  chaque suite) : 0 fonction d'admin ouverte, 0 sans session, 0 champ réservé. Corrigé : mauvais nombre d'arguments → 400 et
  plus rien dans Admin › Erreurs (`server.dispatcher`, `inspect.signature(m).bind`) ; `lockerroom.MessageClient` (les
  messages faits pour l'utilisateur arrivent tels quels) ; `couts_depuis_achats` sans eBay. Calculs : la taxe d'achat suit la
  PROVINCE (`deals.TAXES_PROVINCE`, `taxe_province`, `_prov` dans `taxe_de` ; réglage `province` ; menu dans « J'achète
  depuis » avec `ioMenu`/`ioLier`, les aides de menu iOS maintenant partagées) ; 0,30 $ par commande de 10 $ et moins
  (`calcul.profit_vente`). Tests `tests/test_taxe_province.py`. RESTE À FAIRE : passe 1 (bilan, breaks, gradation, taux de
  change, valeur d'inventaire : recalcul indépendant sur un compte semé), passes 2, 4 et 5.

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
- **Surtaxe du Canada sur les cartes des Etats-Unis (24 nov, Mathieu : « ce sont les tarifs, on doit en tenir compte. Renseigne-toi »)** : verifie aux sources (Tarif des douanes 2026 ch. 49 : 4911.91.00.30 = cartes a collectionner ; Finances Canada, liste du 8 sept. 2026 : 4911.91.00 = 50 % ; ASFC Avis des douanes 26-23 : achats personnels, sans minimum, sur le PRIX pas le port, TPS sur prix + port + surtaxe). Sa commande du 8 nov colle au cent (53,09 = 50 % de 106,17 ; 8,89 = 5 % du tout). C'est une surtaxe CANADIENNE (reponse aux tarifs americains). `deals.taxe_de(x, pays, total, valeur)` : la fraction depend du prix -> calculee pour `total` s'il est donne (le « Total », `_paye`), sinon au plus haut prix payable de `valeur` (mise max d'un encan : `_total_max`), sinon au total de l'annonce. `SURTAXE_US` (LR_SURTAXE_US, 50), `TPS_IMPORT` (5), `taxe_import(prov)` (TVH en ON/NS/NB/NL/PE), `_taux_import(x)` (taux lu d'une annonce relue, garde dans `import_taux` par `achat()`), `_budget()`. Tous les `prix_max(V, taxe=taxe_de(X))` passent `valeur=V`. `veille_ebay.calibrer_surtaxe` : la mediane de (frais d'importation / prix) sur 15 annonces americaines relues en 14 jours remplace le 50 % (si Ottawa change le taux). `IMPORT_DEFAUT` (49,7 %) ne sert plus que sans prix ni valeur, ou hors Etats-Unis pas relue. Non mesure : TVQ non percue par eBay (une commande) ; seuil de 40 $ ; vendeur qui expedie lui-meme. Appel au TCCE AP-2025-018 (cartes a echanger hors surtaxe ?) : pas de decision le 24 nov. Test : `tests/test_surtaxe_us.py`.
- **Watchlist : « Miser » et « Miser en lot » pour tous (24 nov, capture de Mathieu en vue Pro : « No auction to bid on right now »)** : depuis le 16 nov un compte sans l'outil de prix n'a plus de mise max, et `watchlist.preparer` sautait tout encan sans mise max : les deux boutons etaient morts pour Gratuit et Pro (chemin d'Apple). Maintenant `preparer` garde l'encan (`mise_max` None, `trop_bas` False), `watchlist.liste` garde la mise ECRITE par l'utilisateur (`mise_perso`) meme sans l'outil de prix (jamais la valeur ni la mise conseillee), l'ecran propose le minimum d'eBay, la case en lot attend le montant, Gixen ignore les encans sans mise. `argentDev` : « $28 » / « US $62 » en anglais. Test : `tests/test_miser_sans_prix.py` ; apercu : `vue/miser.py` (routes `watch_liste` / `watch_preparer` simulees). Lecon : quand un champ devient reserve (16 nov), chercher tout ce qui en DEPEND (ici un `continue` sur `mise_max is None`).
- **Vitesse du Radar, premieres lignes « Radar (temps) » en production (24 nov, 16 h 13, 2 min apres un push)** : admin 20,1 s = recherches 7,5 · ventes (admin) 7,0 · pour moi et verification 3,5 · scores 1,5 ; Pro 6,8 s. DEUX calculs identiques en meme temps (accueil + Radar). A faire : (1) un seul calcul a la fois par cle (le 2e attend), (2) « ventes (admin) » hors du calcul (en fond, garde), (3) voir pourquoi « petits tous » prend 5 a 6 s. Relire des lignes prises loin d'un push avant de trancher.
- **Le Profil tient dans l'ecran (24 nov, Mathieu : « je ne devrais pas pouvoir bouger l'ecran »)** : `tenirProfil()` (appele par `pastillerReglages`, a 0, 700 et 2500 ms, et au `resize`) pose `--pk` (0 a 1) sur `<html>` : le plus petit serrage qui fait tenir la page (recherche par moities sur `scrollHeight - innerHeight`) ; rien si tout tient, rien si ca ne tient pas meme serre (iPhone SE). Les regles CSS `calc(... * var(--pk, 0))` ne visent que `.ecran.reglages`. **L'iPhone de Mathieu fait 430 x 932 points** (captures de 1188 px de large pour 66 points par rangee), pas 393 x 852. Pour mesurer comme sur l'iPhone : Playwright + CDP `Emulation.setSafeAreaInsetsOverride` (haut 59, bas 34) : `vue/profil.py plus,i16,i14,mini,se pro en apres`. Sans ces marges, une page qui deborde sur le telephone semble tenir.
- **Breaks : cotes deduites des tirages (24 nov, Splendor : crochet vert puis « chances pas encore connues »)** : `catalogue._estimer_boite_numerotee` (fin de `taux_par_boite`) : si AUCUNE cote n'est publiee, que le format de boite est connu et que 90 % des sous-ensembles ont un tirage, cote = cartes de la boite x exemplaires du sous-ensemble / tous les exemplaires (`_exemplaires`). Sans tirage : aucune cote, mais compte dans le total au tirage median. Ne touche que Splendor sur 26 produits. `catalogue.liste()` renvoie `sans_cotes` : la tuile montre « Cotes a venir » au lieu du crochet. Test : `tests/test_boite_numerotee.py`.
- **« Ton radar » comme Reglages d'iOS + bouton SlabIQ (24 nov, Mathieu : « c'est laid, ca brise l'experience Apple » ; « le bouton SlabIQ ne fonctionne pas »)** : `configurerRadar` garde son fond (`.tuto-fond`) mais la liste (RECAP) et chaque sous-fenetre portent `rq-ios` et les pieces du kit iOS (`.io-tete`, `.io-g`, `.io-r`, `IO_FL` chevron simple, `IO_OK` crochet, `.io-x`, `.io-t` titre de groupe, `.io-fin` bouton de droite). Liste : Afficher | Joueurs et equipes, Cartes, Budget (menu natif `ioMenu('rq-bud')`, garde par `sauverProfil`) | Alertes : Prix cibles, 2 interrupteurs (`rq-a1`, `rq-a2`) | Mes vendeurs eBay. « OK » en haut a droite (`#rq-ok`) ; toucher le fond ferme ; on va au Radar seulement si un reglage a change ailleurs. Sous-fenetres : `T_[i]` donne le titre court, l'ancien `<h3>` question est retire, « Annuler » = `#rq-ann`. Plus de `tuto-bas`, plus de crochets verts (16 nov) : le choix ecrit a droite dit l'etat. Les boutons de l'en-tete du Radar (`#d-iqp`, `#d-x-iq`, `#d-aide`) sont branches juste avant `await chargerDeals()` : avant, seulement a la fin de `chargerDeals`, apres le `return` du Radar public. Lecon : un `return` anticipe pour les comptes sans comps saute tout ce qui est branche plus bas ; chercher les autres. Tests : `tests/test_radar_ios.py` ; apercus : `vue/monradar.py`, `vue/monradar2.py`.
- **Inventaire : « A liquider » sous 20 $, « A ajuster » a 20 $ et plus (24 nov, Mathieu)** : `lockerroom.popularite` rend `liquider` / `liquider_ids` (froides de moins de `LIQUIDER_PRIX` = 20 $) et `ajuster` / `ajuster_ids` (froides de 20 $ et plus) ; une populaire n'est jamais froide. « Froide » = sa regle du 23 nov (60 j+ sans suivi et peu vue, ou 90 j+). Ecran : `S.invAjuster` + `majTuileAjuster` (union avec les cartes au-dessus du marche SEULEMENT si `prixOutil()`). **`prixOutil()` = comps() et (admin ou forfait.comps)** : garde-fou dans `repere()` et `estimerManquantes()` ; un compte Pro ne voit plus aucun jugement de prix tire des ventes (avant : par `c.valeur`).
- **Balayage automatique des ecrans (24 nov)** : `outils/audit_ecrans.py <vue> <langue> [largeur hauteur] [routes]` (Playwright + Chrome + serveur local 8431). La vue (pro, gratuit) est celle du SERVEUR (`API.admin_vue`, comme Mathieu) : attendre que `S.forfait.vue` soit arrivee avant de mesurer (sinon tout tourne en Admin sans le dire) ; ne jamais lancer deux scripts qui changent la vue en meme temps (une seule cle « local »). Il mesure : erreurs JS, appels refuses, page qui glisse (marges iPhone par CDP), largeur, francais reste en anglais, et les boutons MORTS (un bouton sans `onclick`, sans `href`, hors formulaire, est touche ; aucune mutation, navigation ni appel = mort). Limite : serveur local presque vide (pas d'eBay) ; les bogues du 24 nov venaient d'ecrans pleins. A faire : un compte de test rempli.
- **Breaks : la carte d'equipe nationale suit le joueur (24 nov, Mathieu : « "other division" lol ? »)** : `calcul.equipes_ligue(cartes, sport)` ({joueur: code de la ligue}, d'apres ses cartes a un joueur et une equipe), `equipes_carte` (remplace « Team X » / « All Star » par l'equipe du joueur ; les anciennes equipes restent), `divisions_carte`. Utilises par `prix_places` et `prix_catalogue` (modes divisions ET equipes) et par `Api.frappe_ajouter` (`_place_de_equipe(..., ligue)`). `_RE_NATIONALE` couvre aussi « All Star ». Noms de divisions en anglais : `i18n/en_09.json` (toujours inclus dans le dictionnaire).
- **Fiche d'une annonce sans l'outil de prix : « Vendues sur eBay » (24 nov, idee de Mathieu)** : `#fe-vendus` dans `feuilleEbay` (a la place de la tuile « Ton prix ») ouvre `feuilleVendusEbay(titre, mettre)` : eBay montre ses vendues, la personne tape le dernier vendu, +15 % (NEGO), un toucher met le prix. Rien n'est recopie d'eBay.
- **Idee de slogan refusee telle quelle (24 nov)** : Mathieu propose « NHL most advanced cards system analyser » pour le site. Reponse : pas de superlatif impossible a mesurer (sa regle : le site n'annonce jamais plus que ce qui est mesure), et « hockey » plutot que « NHL » (marque de la ligue). Propose : une phrase appuyee sur les 213 174 ventes testees (deja sur la page SlabIQ). En attente de son choix.
- **Radar : un seul calcul a la fois par compte (24 nov)** : l'accueil et le Radar demandaient chacun `mes_deals` a la meme seconde (20 s deux fois). `Api.mes_deals` = verrou par (base, cle du Radar) dans `_RADAR_UN` : le 2e appel attend le 1er (`RADAR_ATTENTE_S` = 45 s) et recoit une copie ; si le 1er echoue ou traine, il calcule lui-meme (`_mes_deals1` = l'ancien corps). `tests/test_radar_un_calcul.py`. Reste a faire pour la vitesse : sortir « ventes (admin) » du calcul (7 s sur 20, admin seulement) et regarder la recherche « petits tous » (5 a 6 s).
- **Menu de gauche a l'ordi plus aere (24 nov, Mathieu : « ca fait trop colle »)** : `body .onglets{gap:12px}` (6 avant) a 900 px et plus ; 8 px (2 avant) sur un ecran de moins de 780 px de haut.
- **Audit avant le lancement : les cinq passes sont faites (24 nov)** : rapport et decisions en attente dans `docs/AUDIT_LANCEMENT.md` (« Bilan de l'audit »). Outils qui restent : `outils/audit_api.py`, `outils/audit_calculs.py` (139 verifications refaites a la main : ventes, bilan, deals, taxes, breaks, comptoir, gradation), `outils/audit_site.py` (994 verifications sur 10 pages), `outils/audit_ecrans.py` (Chrome + serveur local, pas dans la suite). Tests : `test_audit_api`, `test_audit_calculs`, `test_audit_coherence` (lettres SlabIQ, constantes des deals, limites du gratuit, prix, chiffres du site = tests consignes), `test_fiche_ferme_au_retour`.
- **La fiche d'une annonce se ferme au changement d'ecran (24 nov)** : `hashchange` → `fermerAnnonce()` (a cote de la touche Echap). Avant, « Retour » du navigateur changeait l'ecran derriere la fiche. Rien n'ouvre la fiche en changeant le hash du meme geste (le toucher fait `preventDefault`) : a garder ainsi, sinon elle se refermerait aussitot.
- **Compte de test local rempli pour voir des ecrans PLEINS** : `/tmp/srv_m/lockerroom.db` (8 annonces, 5 en stock, 4 vendues, 4 encans dans `watchlist`). A refaire si `/tmp` est vide : inserer dans `cartes` (statut « Listée », « En stock », « Vendue ») et `watchlist` (encan = 1, `fin` en ISO UTC).
- **Prix : 8,99 $ / mois, annuel −20 % = 7,19 $ / mois (24 nov au soir, Mathieu)** : UNE source pour ce qui est ANNONCE : `forfaits.PRIX_PRO`, `RABAIS_ANNUEL`, `PRIX_PRO_ANNUEL`, `ECONOMIE_ANNUEL` ; le site, `ui/conditions.html`, la description dans `server.py` et `ceo.py` suivent (texte en dur, verrouille par `tests/test_audit_coherence.py`). Le prix FACTURE vit dans Stripe (`STRIPE_PRIX_PRO`, `STRIPE_PRIX_PRO_ANNUEL` dans Render : je n'y touche pas) et chez Apple (App Store Connect). Au 24 nov, Stripe (vrai mode) n'a qu'un prix : price_1UUwYW… = 7,99 $ CA / mois, produit prod_VVyVMUZHtt83lA, aucun abonne. L'annuel se montre (site `.si-annuel`, app `f.prix_annuel`) des que `STRIPE_PRIX_PRO_ANNUEL` existe. iPhone : un seul produit Apple (mensuel) ; l'annuel Apple reste a decider. Connecteur Stripe : lecture OK ; ecrire seulement avec son accord explicite.
- **Petits iPhone (375 x 667) : tout tient (24 nov)** : `tenirProfil` plie `PLIER_PROFIL` (Nouveautes, Donnees, Aide, Boutique, dans cet ordre) derriere `#gg-plus` (« Plus », icone `trois`) seulement si, serre au maximum (`--pk` = 1), le Profil depasse encore et que l'ecran fait moins de 900 px de large ; la feuille « Plus » clone les lignes et un toucher clique la vraie. CSS `@media (max-width:699px) and (max-height:700px)` pour le dessin de Vendre et l'etat vide des Notifications. Mesure : `/home/claude/vue/tailles.py`.
- **Fiche d'une carte au telephone (24 nov)** : `#feuille` est une colonne flexible a hauteur limitee et `.fcx` est en `display:contents` : tout enfant a hauteur fixe sans `min-height` peut s'ECRASER quand le contenu depasse (« mini barre Save » du 19 nov, « List on eBay » du 24 nov). Tout nouveau bouton pose la : `flex:none; min-height`.
- **Cartes couchees debout dans les slabs (24 nov)** : `photoCadree(..., {debout:true})` tourne l'image entiere (`toutTourner`) quand la photo est deja cadree serre sur un contour couche, ou sans contour si W/H est entre 1,36 et 1,46. Essais : `/home/claude/vue/tourner.py`.
- **Stripe, vrai mode : deux prix crees le 24 nov a 19 h 27, avec le « oui » de Mathieu** (connecteur Stripe, sur le produit prod_VVyVMUZHtt83lA) : mensuel 8,99 $ CA = `price_1UfU3mCHwdi9E0tAtmQKpaJ5` ; annuel 7,19 $ CA par mois (engagement 12 mois) = `price_1UfU3qCHwdi9E0tAOhybz3uD`. L'ancien 7,99 $ (price_1UUwYW…) reste actif tant que Render pointe dessus. A Mathieu : coller ces deux identifiants dans Render (`STRIPE_PRIX_PRO`, `STRIPE_PRIX_PRO_ANNUEL`), mettre 8,99 $ dans App Store Connect, et faire la photo en direct de sa piece d'identite dans Stripe (exigence en retard). `tax_behavior` laisse « unspecified », comme l'ancien prix (le paiement n'utilise pas les taxes automatiques).
- **Phrase du site, choisie par Mathieu le 24 nov (« OUI GO »)** : sous le titre de l'accueil, `<p class="punch">` = « Ne mise plus à l'aveugle. » / "Never bid blind again." puis « SlabIQ a testé 213 174 ventes de hockey pour noter chaque carte de A+ à E. » avec le lien `/slabiq#tests`. Leviers retenus : la peur de perdre, puis le chiffre exact. Il avait refuse trois phrases descriptives (« ca manque de punch ») et son idee de depart (« NHL most advanced… ») : pas de superlatif sans mesure, « hockey » plutot que « NHL ». Style `.punch` dans `ui/site_base.html`. Le nombre suit le test : `outils/site_iq.py` le reecrit, `tests/test_audit_coherence.py` (4 d) le verifie. Voir le site en local : `LOCKERROOM_MULTI=1 LOCKERROOM_DONNEES=/tmp/srv_multi LOCKERROOM_PORT=8432 python3 server.py`, puis `/` (script `/home/claude/vue/heros.py`).
- **Stripe : `STRIPE_WEBHOOK_SECRET` de Render etait (tres probablement) celui du mode TEST (trouve le 24 nov au soir)** : capture de Mathieu (Stripe › erreurs : « No such subscription sub_1UU5qB… a similar object exists in test mode, but a live mode key was used », 9 h 22). Le seul appel `GET subscriptions/…` est dans `paiements.traiter`, APRES la verification de la signature ; le journal de Render montre `POST /stripe/webhook 200` (14 octets = « compte inconnu ») a 14:22:43 UTC : un avis du mode test (son abonnement d'essai a 1 $ qui se renouvelle) a donc passe la signature. Consequence : les avis du VRAI mode (endpoint we_1UUwqW…, actif, bons evenements) seraient refuses (400) : un client paierait sans devenir Pro. A Mathieu : Stripe vrai mode › Developers › Webhooks › Signing secret → Render. Jamais dans le chat. Preuve attendue : son vrai paiement de bout en bout. Garde ajoutee : `paiements.recevoir` ignore un avis dont `livemode` n'est pas le mode de la cle (« autre mode : ignoré », et une ligne au journal) ; `tests/test_paiements.py`. Stripe lui a aussi montre l'assistant « How do you want to accept subscriptions? » : reponse = Prebuilt checkout (notre code cree des sessions Checkout hebergees).
- **Vrai paiement de Mathieu, 24 nov 20 h 30 : il marche (8,99 $, compte passe Pro, deux avis `{"recu": "ok"}`), mais le retour de Stripe allait sur lockerroom-6efg.onrender.com** (ou le client n'est pas connecte : il voyait le site). Cause : `paiements.adresse_publique` prenait `RENDER_EXTERNAL_URL` (pas de `LOCKERROOM_URL` dans Render). Corrige : l'adresse ou le client EST (`(www.)?slabcoach.com`, comme `server._base_publique`), Render en dernier recours ; `tests/test_paiements.py`. Stripe, fait par Claude a sa demande (« prends le controle et gere Stripe ») : prix par defaut 8,99 $, image du produit = `https://www.slabcoach.com/icone-512.png`, description sans « real sold comps » ; essai du webhook par un abonnement d'essai sans carte, annule aussitot (client « Essai du webhook (Claude) - a supprimer », cus_VgsRO43P7LyjPi, a effacer par lui : le connecteur n'a pas d'operation de suppression). Piece d'identite : verifiee. Reste : archiver price_1UUwYW… (7,99 $) quand il le dit ; rembourser et annuler son abonnement d'essai (sub_1UfV2A…) seulement s'il le demande avec le montant ; numero d'entreprise (samedi) ; virements en mode manuel ; nom sur le releve « : SLABCOACH.COM ». Lecon : `{"recu": "ok"}` = 14 octets, « compte inconnu » = 26 : l'avis du mode test du matin avait donc ete APPLIQUE a un compte (un compte d'essai garde peut-etre un Pro venu du mode test).
- **Notifications iPhone jamais recues (24 nov au soir, Mathieu)** : en production son iPhone s'enregistre bien (`POST /api/push_enregistrer` 200, app LockerRoomiOS/1.1, 4 fois le 24 nov) et le journal n'a AUCUNE ligne « APNs » en 3 jours (un refus d'Apple en ecrirait une ; un succes non) : soit `APNS_KEY_ID` / `APNS_TEAM_ID` / `APNS_KEY` manquent dans Render (`apns.actif()` faux : `_push` rend 0 sans rien dire), soit aucune alerte ne s'est declenchee (3 par jour au plus, rien de 22 h a 8 h). Ajoute : `Api.push_essai()` + lien « Envoyer une notification d'essai » (Notifications › Reglages, app iPhone seulement) qui dit la cause (serveur / appareil / Apple ; le detail pour le vrai admin) ; `apns.DERNIER` garde la derniere reponse d'Apple ; `tests/test_push_essai.py`. `APNS_SANDBOX` doit rester vide pour TestFlight et l'App Store. Gixen = un fichier CSV partage depuis la Watchlist (pas une API).
- **Soiree du 24 nov, trois ecrans refaits sur ses captures (292 tests)** : (1) **Accueil** : `remplirAccTel` calcule la place de la barre du bas d'apres sa mise en page (`innerHeight - bottom - offsetHeight`), plus d'apres sa position lue a l'ecran + le defilement (trou en bas pendant le rebond d'iOS ou une animation) ; remesure a 400, 1200 et 2600 ms ; `tests/test_accueil_sans_trou.py`. (2) **Bilan refait** (« elle semble vieille ; elle doit tenir sur une page ») : classe `bil2`, titre et mois sur une rangee (mois court au telephone), `.b2-heros` = le profit net en grand + tendance + 3 reperes (`.b2-3` : ventes, cartes, marge), « ou va ton argent » en lignes serrees (libelles courts « Frais eBay », « Autres »), UNE action pleine (`.b2-go`) et deux liens (`.b2-liens` : depense, CSV) ; paliers de hauteur 880 et 700 px ; 0 depassement a 430 x 932, 393 x 852, 375 x 667. (3) **Grille de centrage** (`.vd.cg`) : la grille prend la hauteur qui reste (`--cgh` = 100dvh - marges - 352 px), plus de defilement ni de glissement de cote, « Enregistrer » en bas, les explications (`.cg-expl`) seulement avec « Comment ? » (`cg-aide-on`) ; `tests/test_bilan_grille_un_ecran.py`. Apercus : `/home/claude/vue/bilan.py`, `grille.py`, `acc_trou.py`. Le « Server error » de sa capture de 20 h 57 = le redemarrage du deploiement (aucune erreur au journal).
- **Envoi automatique des petites ventes eBay (nuit du 24 au 25 nov, pendant que Mathieu dort ; il avait dit : « sous 30 $ c'est toujours 3 $ de ship ; ca devrait etre automatique »)** : eBay ne donne jamais ce que l'envoi a coute au vendeur ; la synchro laisse `port_paye` a NULL et le port paye par l'acheteur comptait comme du profit (son Bilan de novembre : 245 $ de port percus dans les 609 $ de profit). Reglage PAR COMPTE, ETEINT PAR DEFAUT : `reglages.port_auto` = {"seuil", "montant"} ; `Api.port_auto_regler(seuil, montant)` l'enregistre et remplit les ventes passees ; `_port_auto_appliquer` (appele aussi a la fin de la synchro des ventes) ne touche que `statut='Vendue' AND canal='eBay' AND port_paye IS NULL AND prix_vendu < seuil AND consignataire_id IS NULL` et baisse le profit du meme montant. Un montant entre a la main, meme 0, n'est jamais ecrase. Ecran : dans la fiche d'une vente, sous l'avis « ce montant compte comme du profit », le lien « Toujours le meme envoi ? » ouvre `feuillePortAuto` (30 $ et 3 $ proposes). `tests/test_port_auto.py`. RIEN ne change pour lui tant qu'il n'a pas touche « Appliquer ». A decider par lui : les ventes de 30 $ et plus (compter le port de l'acheteur comme cout, ou lire le cout de l'etiquette dans eBay : a verifier, demande une permission eBay de plus).
- **Balayage apres la soiree (25 nov, 22 h)** : Pro en anglais a 430 x 932 et Gratuit en francais a 375 x 667 : 0 erreur JavaScript, 0 appel refuse, 0 bouton mort, aucune fenetre restee ouverte. Restent a defiler : les listes (Watchlist, Inventaire, Breaks, Ventes, Calendrier, Guide) et, sur le petit iPhone seulement, Idees (184) et le Comptoir (255).
- **PAS ENCORE POUSSE au 24 nov 22 h 30 (son PC etait verrouille)** : le Bilan refait, la grille de centrage sur un ecran, l'envoi automatique. Tout est dans son dossier GitHub ; 293 tests passent.

- **Baseball, test du 25 nov (export du 23 nov, rien d'écrit sur le site ; `outils/tests_site_bb.py`, 34 s)** : 138 510 lignes,
  68 916 ventes utiles (43 318 doublons, 21 268 sous 3 $), 168 joueurs (hockey : 990). 93 % des ventes datent d'oct.-nov. 2026
  (nov. seul : 78 %) : pas de profondeur. rho 0,20 (hockey 0,929), accord 0,752, inversions A+/A, B+/B, B-/C+ ; Radar Pro 21 achats
  seulement (90,5 %) ; fenêtre de revente de 6 jours (reventes 1 à 3 % par lettre = non mesurable) ; simulation 12 semaines
  négative avec et sans (-3,5 % contre -6,3 %). 16 corrections, toutes des espoirs montés à A+ (effet de mode sur 6 semaines).
  Verdict dit à Mathieu : PAS publiable ; il manque de l'historique (2023-2026) et des joueurs (~500 + vintage), pas du volume
  récent. Parts de marché : aucune donnée trouvée pour le Canada (son 50 % hockey / 25 % baseball n'est pas vérifié) ; aux É.-U.
  le baseball est 1er en cartes gradées 2025 (3,6 M sur 10,0 M), le basketball pèse plus en dollars sur eBay.
- **Baseball, décision du 25 nov (Mathieu)** : le hockey d'abord (lancement lundi 30 nov), le baseball en « release officiel » à
  l'ouverture de la saison MLB 2027 (calendrier : 24-25 mars 2027 ; lock-out attendu le 1er déc., en 2022 l'ouverture avait
  glissé au 7 avril). Il veut payer 3 ans d'historique, « féroce », viser le marché américain, des heures d'itération comme au
  hockey ; tout ce que le hockey offre (sortes de cartes par décennie, parallèles, gros joueurs par décennie, junk wax, gradable).
  Demandé à Mathieu : (1) son budget de données par mois, (2) le « go » pour bâtir la moisson d'historique baseball (comme le
  méga test 3 ans) APRÈS le lancement, (3) un export Ventes Baseball par semaine, (4) 5 à 10 testeurs américains en février.
  Dit franchement : source = eBay via SoldComps seulement (pas Goldin / Fanatics / PSA sans accord écrit) donc pas « les mêmes
  données que Card Ladder » ; le vintage haut de gamme se vend surtout en maisons d'encan. Rien de baseball dans l'app avant lundi.
- **Sources de checklists baseball, tour du 25 nov (Mathieu : « regarde partout, la base va être énorme »)** :
  - **TheCardAPI Catalog** (notre 2e source de ventes) : 16,7 M cartes, 346 000 ensembles, 16 sports ; checklists, drapeaux
    recrue/auto/relique, tirages, parallèles liés au produit parent (`/api/v1/catalog`, `/catalog/sets`, `/catalog/releases/{id}/checklists`).
    Forfaits : Free 0 $ (5 000 ventes/j, 30 j), Starter 9 $, Builder 49 $ (+29 $ catalogue, 500 fiches/j, plafond 250 000),
    Pro 199 $ (catalogue inclus, 2 000 fiches/j, plafond 1 M ; ventes 200 000/j, 180 j d'historique). Pas d'export en bloc.
  - **ALERTE conditions TheCardAPI (mises à jour le 15 nov 2026)** : forfait GRATUIT = « No persistent local storage », « Non-commercial
    use only ». Or `thecardapi.py` archive la moisson dans base_ventes sur le forfait gratuit. Payant : stockage permis
    (Starter 500 000 ventes, Builder 5 M, Pro 25 M), effacement sous 30 j si l'abonnement s'arrête ; entraîner un modèle avec
    leurs données = entente écrite à part ; œuvres dérivées (analyses, indices) à nous. Dit à Mathieu ; il décide (forfait payant
    ou arrêt de la moisson). Ne pas toucher Render.
  - **CardSight AI** : identification par photo (joueur, produit, numéro, confiance) + parallèles candidats classés (17 000 motifs),
    baseball depuis 1933, catalogue 17 M ; gratuit 750 appels/mois, 14,95 $ pour 5 000, 199,95 $ pour 100 000. Conditions non lues.
    Candidat pour le « dernier recours visuel » à la place de l'API eBay. À tester contre notre vision.py sur de vraies photos.
  - **Fichiers par produit** : Beckett (tableur par page, import existant), Topps (topps.com/pages/checklists, « Download checklist » ;
    conditions réputées interdire la collecte automatique : téléchargement à la main seulement), GTS (gts.py lit déjà le hockey ;
    catégorie baseball à ajouter, page non ouverte d'ici). **Écartés** : TCDB (pas d'API officielle, seulement des aspirateurs tiers),
    Checklist Insider (refuse notre serveur), Baseballcardpedia (licence inconnue), SportsCardsPro (CSV payant, à effacer à la fin).
  - Les 3 ans de ventes ne viendront PAS de TheCardAPI (180 j max) : SoldComps, comme le méga test hockey.
- **25 nov, matin (captures de Mathieu sur iPhone) : quatre changements, livrés ensemble (p86)** :
  - **SlabIQ, Renewed numérotée** (« Renewed Exclusives est une carte B » ; Makar Renewed Exclusives /100 notée C) : `bareme_iq.renewed()` :
    une YG Renewed NUMÉROTÉE suit la règle des numérotées (/100 → B, High Gloss /10 → A-), raison `yg_renewed_num` ; la Renewed de base
    reste D. Nos ventes (sans les gradées) : base 2,86 $ en médiane (6 820), Exclusives /100 51,57 $ (299), High Gloss /10 212 $ (52).
    `score_slab` (YG 2024-25 d'un vétéran sans le mot « Renewed ») passe par la même fonction (base : E, inchangé). L'empreinte a
    changé → `tests_site.py export_2411 --ecrire` + `bulletin_iq.py --ecrire` refaits (chaine4.sh) : accord 0,685 → 0,684, Radar Pro
    inchangé (87 %, 638 achats), le site dit « 25 nov. ». Décision « YG Renewed à D ou à B ? » (ceo `d_ygr`) : toujours ouverte pour la BASE.
  - **Joueur blessé / absent** (« Bedard est blessé, il devrait avoir le badge » puis « pourquoi on l'a pas capté ? On doit TOUS les
    capter ») : `indice_joueurs.suivre_blessures` (état `d["blessures"]`, durée lue dans la manchette, retour, nom de famille seul +
    équipe) et `absents()` (les sommaires de matchs de `signal_joueurs`, 45 jours : un patineur régulier encore dans l'alignement qui
    rate ses 2 derniers matchs). Pastilles `blesse` / `absent`, en PREMIER dans la liste ; `mauvaise` ne s'ajoute plus par-dessus.
    Gardiens : manchettes seulement. `pourquoi()` renvoie `blessure` et `absent`. Test : `tests/test_blessures.py`.
    Dit à Mathieu : sans manchette on ne distingue pas blessure / suspension / laissé de côté ; 2 à 4 jours de délai ; un flux officiel
    payant (Sportradar, SportsDataIO) donnerait tout le jour même (prix non vérifié) ; ESPN exclu par sa règle.
  - **Pastilles = « Bad news » + notification à la iOS** (09 h 49 : « Bad news c'est mieux, et quand tu cliques sur la pastille t'as
    l'explication ; inspire-toi d'Apple iOS pour le pop-up de la notif ») : sur la tuile, `blesse` et `absent` s'affichent « Mauvaise
    nouvelle / Bad news ». TOUTES les pastilles d'une annonce se touchent (`data-np`, plus `data-cu` / `data-se` déjà là) →
    `notifPastille()` : verre dépoli, icône à gauche, titre gras, joueur en gris à droite, texte, lien « Lire la nouvelle » ; descend du
    haut, ne bloque rien (toucher ailleurs, glisser vers le haut, 8 s). Textes : `NP_TXT()` ; faits du joueur : `npDetail()` via
    `API.tendance_joueur` (gardé 10 min). L'ancienne feuille `.cs-f` (Clé, Culte, chance de séries) est remplacée. Aperçu : `vue/badge.py`.
  - **Photos du Radar** (« les photos loadent pas assez vite », tuiles McDavid et Frondell vides en 5G faible) : `photosVite()` (les photos
    de l'écran en `eager` + priorité haute, les autres ~1600 px avant d'arriver, par IntersectionObserver ; un MutationObserver les
    trouve), une photo en échec est redemandée UNE fois (`?r=1`, cachée pendant l'attente) avant d'être enlevée, `preconnect` vers
    i.ebayimg.com. Mêmes adresses et tailles. Non mesuré sur son réseau.
  - Leçon : dans cette VM, un travail lancé en fond et les serveurs locaux tombent entre deux tours ; ne pas dormir en avant-plan
    (Mathieu interrompt) : travailler, puis relire `/tmp/chaine4_etat.log`.
- **Miser en lot : essai du lien avec le montant (25 nov, 16 h ; Mathieu : « si tu ouvres le lien, le prix est déjà rentré, tu as
  juste à faire bid »)** : état avant = 4 gestes par encan (ouvrir, Enchérir, coller, confirmer). Trois voies dites à Mathieu : l'API
  Offer d'eBay (`ebay_ecriture.miser`, diffusion limitée, demande par l'eBay Partner Network : pas déposée), le lien pré-rempli,
  Gixen pour tous (non recommandé : mot de passe d'un tiers). Vérifié dans le navigateur de son PC, NON connecté à eBay :
  `/itm/ID?bolp=1&maxbid=N` renvoie à la connexion avec `ru=…/itm/ID?cta=placebid` (+ `maxbid=N`) ; `/bfl/placebid/ID?maxbid=N&currencyId=CAD`
  renvoie à la connexion en gardant `maxbid` dans l'adresse de retour ; l'ancien `offer.ebay.com … MakeBid` est mort depuis 2021.
  PAS vérifié : que le montant arrive inscrit une fois connecté (il faut son compte ; jamais de mot de passe). Rappel du 31 oct :
  `/bfl/placebid` dans le navigateur de l'app avait planté après la connexion. LIVRÉ (p87) : pour l'ADMIN seulement, sous le bouton
  de mise, trois essais (A app eBay, B annonce dans le navigateur de l'app, C page de mise) : `lienMisePre`, `ouvrirMisePre`,
  `.mi-essai` ; le montant reste copié ; rien ne change pour les clients. Test : `tests/test_mise_preremplie.py`.
  À faire après sa réponse (A, B, C ou aucun) : brancher le gagnant pour tous, ou retirer l'essai.
- **Vendeurs : les aubaines (25 nov, 16 h 46 ; Mathieu, Sergachev SP Authentic Limited Auto Material /100 vendue 32 $ + 12,75 $ le
  24 oct : « on aurait dû la capter » ; « les vendeurs pour lesquels les ventes bien en dessous des last sold sortent le plus
  souvent » ; « Minting, est-ce qu'on les regarde ? »)** : dit à Mathieu : (1) notre fichier de ventes (SoldComps / TheCardAPI) n'a PAS
  le vendeur ; seuls les encans finis suivis par le chasseur l'ont (`encans_archive.json`, 45 jours, sur le serveur : pas lisible
  d'ici) ; (2) le rapport existe depuis le 12 nov : Admin → Outils du Radar → « Vendeurs : les aubaines » (`feuilleVendeursPerf`,
  `Api.vendeurs_rapport`, `chances.perf_vendeurs`) ; AJOUTÉ : par vendeur, le nombre et la part d'encans finis à 70 % ou moins de la
  valeur, port compris (`aubaines`, `sous_70`) et à moitié prix (`moitie`, `sous_50`) ; le rapport est maintenant CLASSÉ par cette
  part (l'ordre du chasseur ne change pas). Test : `tests/test_vendeurs_perf.py`. (3) La Sergachev : dans nos ventes (item
  198720521671), 6 ventes de la même carte : 127, 53, 86, 30,51, 32, 107 $ → médiane 69,45 $ ; `deals.prix_max` = 35,11 $ port
  compris : 32 + 12,75 = 44,75 $ n'était PAS un deal selon sa règle des 30 % ; à 32 $ sans port (ramassage) oui, de justesse. Et le
  24 oct le chasseur ne cherchait que les recrues des joueurs les plus demandés (vendeurs suivis : 29 oct). (4) « Minting » : aucun
  vendeur de ce nom dans `VENDEURS_DEFAUT` ; demandé son pseudo eBay exact. À FAIRE après le push : lire le rapport avec lui.
- **Mintink suivi + le rapport des vendeurs dit vrai (25 nov, 16 h 54 ; Mathieu, photo « Mintink Trading Cards (13997) » ; « les plus
  gros vendeurs au Canada par volume ? » ; « être sûr de scanner tout eBay » ; « propose-moi une manière d'améliorer la méthode avec
  les crédits qu'on a »)** : (1) `mintink` (pseudo lu sur ebay.ca/str/mintink : lien `_ssn=mintink` ; 58 000 ventes, encans) ajouté à
  `deals.VENDEURS_DEFAUT` (groupe hockey, pas prioritaire), `VENDEURS_V = 4` (ajouté aux listes déjà réglées). (2) ERREUR DE MA PART
  corrigée : j'avais écrit que le rapport « Vendeurs : les aubaines » couvre « tous les vendeurs vus, suivis ou non ». FAUX :
  `chances.archiver` ne garde que les encans des vendeurs SUIVIS (`_noter_suivi`) et, pour les autres vendeurs, seulement leurs encans
  retenus comme DEALS : leur part d'aubaines est gonflée. Le rapport les montre maintenant à part (« Pas suivis : … Part gonflée, pas
  comparable »). Le balayage de la catégorie (`balayer`) n'archive rien. (3) Dit à Mathieu, franchement : on ne scanne PAS tout eBay.
  Couvert : les vendeurs suivis (tous leurs encans) ; la catégorie hockey : encans de 15 $ et plus des 24 prochaines heures (2 000),
  les 1 000 qui finissent le plus tôt à tout prix, les raretés jusqu'à 72 h, les nouvelles annonces à prix fixe. Trous : fiche sans
  « Ice Hockey », carte sous 15 $ loin de la fin, carte sans ventes de la même carte (pas de valeur = pas de deal), plafonds (eBay
  5 000 appels / jour pour toute l'app ; ventes ciblées : 40 / jour + 250 pour les prioritaires). Aucun classement public des vendeurs
  eBay par volume. (4) PROPOSÉ (rien de bâti, attend son choix) : A. chaque nuit, « aubaines manquées » : depuis nos ventes du jour,
  chaque encan fini à 70 % ou moins de la médiane de la même carte : montré avant la fin ou non, et pourquoi (jamais vu / vu sans
  valeur / vu trop tard / trop cher avec le port) : 0 crédit ; B. UNE seule file de crédits, classée par dollars attendus par crédit
  (écart valeur approx. − prix, taux d'aubaines mesuré du vendeur, heures restantes) : plus de crédits = plus bas dans la même file ;
  C. archiver chaque encan du balayage qui a une valeur (tous les vendeurs) → vrai taux par vendeur et volume par vendeur → les N
  meilleurs suivis automatiquement (N suit les crédits) ; à valider avec la règle « contenu eBay 24 h » ; D. balayage aux heures où
  les encans finissent (soir, dimanche). Recommandé : A d'abord (admin seulement, sans risque pour le lancement), le reste après lundi.
- **Les aubaines manquées : bâti (25 nov, 17 h 02 ; Mathieu : « la meilleure chose pour capter le plus de cartes possible à l'avenir,
  et que ça aide SlabIQ à améliorer son modèle ; si c'est A, on fait A »)** : nouveau module `manquees.py`. (1) LE REGISTRE
  (`chasse_vus.sqlite`, 21 jours) : `deals._juger` y note chaque annonce jugée : heure de la 1re vue, heures avant la fin, verdict le
  plus fort (deal > photo > trop_cher > sans_ventes / comps_vieilles > ecartee / joueur / sport > fenetre), 1er moment « deal », notre
  valeur. AUCUN contenu d'eBay gardé : la clé est une empreinte SHA-256 du numéro d'annonce (règle « rien d'eBay plus de 24 h »
  respectée). `_juger0` dit pourquoi il sort tôt (`st["_sortie"]`). Écrit par paquets (`manquees.vider()` dans `_sauver`). (2) LE
  RAPPORT (`aubaines_manquees.json`, aux 12 h, à la fin d'un tour, 7 minutes au plus, 0 crédit, 0 appel) : dans `base_ventes`, les
  ventes des 10 derniers jours ; une AUBAINE = carte de 30 $ et plus vendue à `deals.prix_max(valeur)` ou moins (≈ 51 % de la valeur :
  SA règle des 30 % ; port de la vente inconnu), valeur = `valeur_sure` des ventes de la même carte des jours d'AVANT ; le registre
  dit : montrée (dont « à moins d'une heure de la fin »), jamais vue, vue sans valeur, trop chère sur le coup, vue trop tôt, écartée.
  Rien avant le 1er jour entier du registre. (3) ÉCRAN : Admin → Outils du Radar → « Aubaines manquées » (`feuilleManquees`,
  `Api.aubaines_manquees`, admin seulement) : le % montrées, les raisons, les plus grosses. Test : `tests/test_aubaines_manquees.py`.
  (4) MESURÉ sur l'export du 24 nov (pas de registre : seulement « combien d'aubaines ») : 15 nov : 14 sur 6 172 ventes ; 16 nov : 8
  sur 4 361 ; 17 nov : 2 sur 4 311 (les ventes arrivent avec des jours de retard). Peu d'aubaines par jour, et plusieurs sont des
  ERREURS DE VALEUR : c'est là que la mesure aide le modèle. Deux corrigées tout de suite dans `cartes_match.py` : « Oversized » (le
  grand format de boîte passait pour la Young Guns : Schaefer 47 $ contre 210 $) = variante exigée dans les deux sens (+ synonyme
  « oversize ») ; « READ / SEE DESCRIPTION », « flaw » = carte abîmée. Vues, PAS corrigées : « Rookie Redemptions RED-207 » (carte
  d'équipe prise pour un joueur « redemptions »), une PSA 10 à 28 $ contre 86 $ (Byram YG), « Draft SP-1 » McKenna, les lots à emoji
  (Sennecke Stature /999 à 8 $ contre 43 $). Suite complète : 296 fichiers, 0 échec. À FAIRE : lire le rapport avec lui 2 jours après
  le push ; puis B (une file de crédits), C (vendeurs par la mesure), D (heures du balayage) selon ce que les raisons montrent.
- **Soirée Apple (25 nov, 17 h 52 à 20 h ; Mathieu a poussé à 17 h 48, en ligne 17 h 49)** : la liste est un doc (« Apple : la liste
  de ce soir », 8 étapes + fiche + note). FAIT par lui dans App Store Connect : accord « Applications payantes » accepté, banque
  envoyée (traitement 24 h), formulaires de taxes Canada (TPS / TVQ) et États-Unis, entente de développeur mise à jour acceptée,
  DSA Europe = « pas commerçant / pas de distribution en UE » (À FAIRE à l'étape 8 : décocher les pays de l'UE dans Pricing and
  Availability), abonnement `com.slabcoach.app.pro.mensuel` créé (8,99 $ CA, FR + EN, achats groupés « multiseat » refusés, image
  1024 et capture d'examen fournies : `Téléchargements\SlabCoach-Pro-1024.png`, `SlabCoach-Passe-au-Pro-en.png`), App Information
  (nom SlabCoach, sous-titre, Sports / Lifestyle, droits de contenu, cote 4+, avis du serveur v2 sur les deux adresses). Codemagic
  ne bâtit JAMAIS seul (pas de `triggering` dans `codemagic.yaml`) : « Start new build » › ios-app-store. RESTE : build, TestFlight
  (achat, restaurer), 6 captures FR + EN en vue Pro, fiche, note, soumettre.
- **Clé APNs : panne et correctif (25 nov, 20 h 05)** : il n'existait AUCUNE clé de notifications (la seule clé Apple était celle de
  « Sign in with Apple », variables `APPLE_*` : ne pas y toucher). Il en a créé une (« SlabCoach APNs », Key ID V839W78U58, fichier
  dans Téléchargements) et a mis `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_KEY` dans Render (redémarrage 19 h 48). Deux pannes : (1) la
  clé collée SANS ses lignes BEGIN / END : `apns.jeton_auth` la décodait en base64 puis `.decode()` plantait (« Server error » à la
  notification d'essai) et `print("Push : " + repr(e))` (alarmes.py, marche.py) a écrit les OCTETS DE LA CLÉ au journal Render,
  deux fois. Dit à Mathieu : révoquer cette clé, en créer une autre, coller le fichier au complet. (2) dès que les 3 variables
  existent, `_admin_verif_possible()` devenait vrai : sa session n'était plus admin tant que le code (envoyé par notification…
  qui ne pouvait pas partir) n'était pas confirmé : plus de pastille de vue sur son iPhone. CORRIGÉ dans le bac (à pousser) :
  `apns.cle_pem` lit la clé sous 8 formes (fichier, une ligne, « \n » écrits, corps seul, base64, guillemets, CRLF) ;
  `apns.CleIllisible` (message fixe, jamais la clé, `from None`) ; `apns.envoyer` ne plante plus et n'écrit jamais `repr(e)` ;
  `apns.pret()` (les variables sont là ET la clé se lit) remplace `actif()` dans `_admin_verif_possible` : une clé illisible ne
  bloque plus l'admin ; `push_essai` dit « Render : APNS_KEY illisible… » au compte admin. Tests : `tests/test_apns_cle.py`,
  `tests/test_admin_verif.py` ; 40 fichiers de tests liés passent (pas la suite complète). Idée à lui proposer :
  `LOCKERROOM_ADMIN_CODE` (code de secours, 8 caractères et plus) dans Render, pour ne jamais dépendre d'une notification.
- **Admin introuvable au cell, flèche de retour plantée, accueil trop haut (25 nov, 20 h 25 ; Mathieu, captures)** : (1) LA VRAIE
  CAUSE de « je ne peux plus naviguer au travers des versions en format cell » : depuis le 20 nov l'accueil n'a plus de pastilles,
  et la tuile Admin du Profil ne s'affichait que pour un admin CONFIRMÉ : une session en attente de son code (dès que les
  notifications marchent) n'avait AUCUN endroit où le demander sur l'iPhone. Maintenant : la tuile Admin reste au Profil, avec un
  cadenas (`data-admin2`) : elle ouvre `feuilleVerifAdmin`, puis recharge l'app. (2) La flèche du geste « retour » restait
  affichée quand iOS annule le toucher (`touchcancel`, jamais de `touchend`) : elle s'efface à l'annulation, à chaque nouveau
  toucher et quand l'app passe en arrière-plan ; sur l'accueil sans fenêtre ouverte il n'y a nulle part où revenir : pas de geste.
  Vérifié par un script (`vue/geste.py`). (3) Accueil au cell (mesuré sur 430 × 932 et 375 × 667, `vue/accueil.py`) : les
  ampoules descendent à 133, le « Bonsoir » commençait à 130 (sa marge des fêtes était écrasée par `margin:0 2px !important`) :
  +12 sous les lumières ; en bas, 42 de vide entre les nouvelles et la barre (24 de marge interne + 18 de réserve) : la marge
  interne s'en va en mode `acc-plein`, il reste 18. 16 fichiers de tests liés passent (pas la suite complète).
- **Deux retouches de 20 h 33 (Mathieu à l'ordi)** : (1) « pourquoi un par-dessus l'autre ? » (le sapin et le cadeau du pied du
  menu, empilés dans un carré gris) : MA faute du matin : les règles de la notification des pastilles s'appelaient `.np-ic` et
  `.np-t` tout court, comme celles du pied du menu (`.np-fete .np-ic`, `.np-t`). Elles sont maintenant sous `.np > …`. LEÇON :
  chercher un nom de classe dans tout le fichier avant de le créer. Vérifié (`vue/pied.py`) : côte à côte, et la notification
  garde son allure. (2) « personne sauf moi doit voir la tuile admin » : la tuile au cadenas ne s'affiche que si
  `admin_a_verifier && !admin_reel` : un compte de `LOCKERROOM_ADMINS` dont la session n'est pas confirmée ; jamais un compte
  ordinaire (test), ni l'admin confirmé qui regarde en vue Pro (ses captures pour l'App Store).
- **État à 20 h 45 (25 nov)** : poussé à 20 h 38 (commit 9578fb4, en ligne 20 h 39) : tuile Admin au cadenas, flèche de retour,
  accueil, sapin et cadeau, clé APNs tolérante. Mathieu a confirmé son code admin (« ça marche ») et la notification d'essai est
  arrivée sur son iPhone (nouvelle clé APNs, l'ancienne révoquée). Dans le bac, PAS poussé : le champ du code admin
  (`.av-z`) était écrasé à 30 px par le bouton Confirmer : corrigé (champ 211 à 476 px selon l'écran, bouton 120 px), mesuré sur
  ordi, 430 et 375 (`vue/code.py`). PSA : il a collé le contrat de l'API de Collectors : usage limité à ses propres ventes, « a
  software subscription product or service offering » exclu : rien de PSA dans SlabCoach sans entente commerciale écrite
  (possible pour Hall of Cardz, ses propres annonces). APPLE, RESTE : étape 5 (build Codemagic : lui demander s'il est lancé),
  6 (TestFlight : S'abonner, Restaurer), 7 (6 captures FR + EN en vue Pro), 8 (fiche, note, décocher l'UE, publication
  manuelle, soumettre). Après l'envoi : un push par jour, tard le soir.
- **Méga test bloqué, en-tête du Radar à l'ordi (25 nov, 21 h)** : (1) Mathieu relance le méga test (écran : 1 860 / 3 000 cartes,
  932 972 ventes ajoutées, plafond 20 000 atteint depuis 3 jours ; CompSniper 28 320 / 50 000 selon NOTRE compteur, 33 000 restants
  selon le sien) avec un plafond de 30 000 : « Stopped (error) · chris chelios rookie auto · page 2 · CompSniper HTTP 400 ». Un 400
  arrêtait TOUTE la collecte, qui reprenait sur la même page une heure plus tard : bloquée pour toujours. Corrigé (`mega_test.py`) :
  400 / 404 / 422 ferme CETTE carte (`raison = refusee (HTTP 400)`), aucun crédit compté, on passe à la suivante ; 8 refus de suite
  (`REFUS_SUITE_MAX`) arrêtent la collecte ; 401 / 403 arrêtent toujours. Test ajouté dans `tests/test_mega_test.py`. Ventes uniques
  de l'export du 24 nov par année : 2023 : 15 796 ; 2024 : 157 846 ; 2025 : 271 305 ; 2026 : 820 388. (2) En-tête du Radar à l'ordi
  sans fond « en sortant d'une tuile » : mesuré : `body.fen-ouverte{overflow:hidden}` faisait du body une zone de défilement,
  l'en-tête collant perdait son appui (−1 500 px) puis le reprenait à la fermeture, redessiné sans fond dans son Chrome. Deux
  corrections : `overflow:clip` (l'en-tête ne bouge plus : vérifié, `vue/entete2.py`) et un fond PLEIN (`.tete-fixe` + `::before`
  jusqu'en haut + ombres pleines à gauche et à droite), sans flou d'arrière-plan ni clip-path ni ombre de 100vmax. PAS reproduit
  dans mon navigateur d'essai (le fond restait là) : à confirmer par lui après le push.
- **p95 poussé par Mathieu vers 21 h 10 (25 nov)** : le méga test est reparti (« shane wright psa 10 · page 1 », 1 861 / 3 000,
  plafond 30 000) ; il tourne seul la nuit. L'en-tête du Radar à l'ordi (fond plein + `overflow:clip`) est dans ce push : PAS
  encore confirmé par lui.
- **TENDANCE DES CARTES (25 nov, 20 h 46 → 22 h 40) : état FINAL, après la triple vérification demandée par Mathieu** (« double et
  triple vérifie tous les graphiques et infos ; on doit être parfait, on n'a pas le droit à l'erreur »). Demandes, dans l'ordre :
  « idem au trend des joueurs mais pour les cartes, biggest risers et losers » ; « petit et clean sur la tuile du Radar, plus visible
  quand on clique » ; « dans SlabIQ » ; « aux 3 jours » ; « j'espère que le trend est associé aux joueurs ? » ; « une OPC Platinum
  Emerald Surge Auto ne doit pas être compilée avec une Violet Pixel Auto, ni avec une Emerald Surge pas auto » ; « type en hausse +
  joueur en hausse = méga valeur » ; « on se fout des parallèles à 20 $ et moins, à part les Young Guns ».
  * LA MESURE (`tendance_sortes.py`) = LA CARTE D'UN JOUEUR : un joueur + une sorte + UNE saison, comparée à elle-même, 30 derniers
    jours contre les 60 d'avant (médianes, borné ×4, rétréci N / (N + 8) : le chiffre affiché est PRUDENT ; `brut` = l'écart des
    médianes tel quel). Annoncée seulement si : 12 ventes et 4 par période ; test de Mann-Whitney p < 0,01 (`P_CARTE` : sur 200
    cartes testées, 2 fausses alertes au plus) ; la courbe des 30 derniers jours va dans le même sens (`coherent`) ; |%| ≥ 5.
    Listes En hausse / En baisse : 20 ventes et plus, 25 par liste. La sorte « tous joueurs » (5 cartes, 40 ventes, p < 0,10) reste
    à côté, étiquetée ; elle ne va JAMAIS sur une tuile (dans les Young Guns, autant de joueurs montent que baissent).
  * MON ERREUR DE LA SOIRÉE : mon échantillon hors ligne (`/tmp/cartes_130.pkl`) ne triait PAS les ventes par cartes_match comme le
    serveur. Tous les chiffres donnés à Mathieu avant 22 h 10 (34 sortes, « O-Pee-Chee Platinum +39 % », 497 cartes) étaient faux
    ou gonflés. Refait par le VRAI chemin : une vraie base sqlite montée avec son export du 24 nov (862 000 ventes depuis le
    10 juillet), le vrai `base_ventes.cartes_toutes` (126 s, 420 Mo), puis `listes`. Scripts gardés dans `/tmp/verif/` (la VM ne
    les garde pas) : `pipeline.py`, `mesure.py`, `entonnoir.py`, `audit_titres.py`.
  * CE QUE LA VÉRIFICATION A TROUVÉ, et corrigé :
    1. la même vente est rangée sous plusieurs recherches (152 000 ventes sur 582 000 ; « jacob fowler young guns », « jacob fowler
       hockey ») : les recherches d'une même carte sont FONDUES et chaque vente (son numéro eBay, `_RE_NUMERO`) compte UNE fois
       (141 000 → 61 000 ventes) ;
    2. une recherche sans année ramène plusieurs saisons : la saison se lit dans le titre de CHAQUE vente (`saison_du_titre`, qui lit
       aussi « 25/26 », ce que `cartes_match._annee` ne fait pas : l'Elias Pettersson défenseur de 2025-26 passait pour celui de
       2018-19). Une saison à 90 % : une carte ; sinon une carte PAR saison ; aucune tolérance « 2026 pour 2025-26 » ;
    3. des paniers ne sont pas UNE carte : « rookie auto », « auto », « psa 10 », un nom de SET seul (« o-pee-chee », « sp authentic
       auto », « portfolio », « clear cut auto », « the cup rookie auto patch ») : écartés (`_precise`, `SETS`, `ATTRIBUTS`) ;
    4. « case hit serie select », « metal universe hobby box » donnaient un « joueur » Case Hit : il faut un joueur CONNU
       (`cartes_match._joueurs_connus`, 1 464 noms ; « Alexander Ovechkin » = « alex ovechkin ») ;
    5. des ventes trop vieilles : la dernière LECTURE (`lu_le` = MAX(vu_le) de la recherche) ou la dernière vente doit avoir 10 jours
       ou moins (`FRAIS_J`), sinon « 30 derniers jours » serait faux. C'EST LE PLUS GROS FILTRE : 1 363 cartes sur 1 935 ;
    6. des prix très étalés DANS UNE MÊME SEMAINE (`_etalement`, q75 / q25 > 2,5) : la recherche mélange des cartes ; une carte qui
       monte vite garde des prix serrés chaque semaine et reste (la 1re version, sur les 60 jours, punissait les cartes qui bougent) ;
    7. hors Young Guns, sous 20 $ de médiane : écartée (`PRIX_MIN_HORS_YG`) ;
    8. le graphique : 100 = le niveau des 60 jours d'avant, axe du temps VRAI (`jours`), bande « 30 derniers jours » (`j_rec`) ;
    9. rien n'est publié tant que plus de 2 % des ventes de la fenêtre ne sont pas triées (`base_ventes.A_TRIER`, `PARTIEL_MAX`) :
       un essai aux 10 minutes, journal « N ventes encore à trier ».
  * `base_ventes.cartes_toutes(detail=True)` : ajoute `q`, `lu_le` et `ventes` = [date, prix, numéro, saison] ; sans `detail`, rien
    ne change pour les autres appelants (vérifié par le test).
  * RÉSULTAT VÉRIFIÉ sur l'export du 24 nov : 169 cartes mesurées (161 Young Guns et variantes, 8 inserts nommés), 145 joueurs,
    17 818 ventes ; 16 hausses et 39 baisses confirmées ; 2 sortes (Young Guns −9 % sur 152 cartes ; Young Guns PSA 10 −1 %).
    Vérifié À LA MAIN sur 12 cartes, directement dans les titres vendus : même sens partout ; les grosses cartes à 1 à 5 points
    (Fowler +81 / +86, Martone −44 / −44, Hutson −28 / −26, Gauthier +56 / +57, Frondell −43 / −41, Protas −38 / −37). Le seul
    gros écart (Misa −2 à la main, −19 au module) venait de MA vérification : elle comptait la carte double Schaefer / Misa #500
    à 5 $, que cartes_match refuse à raison ; sur les ventes communes : −17 %. Audit de `de_titre` sur 7 381 vrais titres :
    1 024 reçoivent la tendance d'une carte, 0 erreur (autre saison, variante, gradée 9+, lot).
  * DEUX DÉFAUTS de `cartes_match` trouvés, PAS corrigés (ils touchent les valeurs : sa règle, pas à la sauvette) : sans année dans
    la recherche, la « Young Guns Renewed » 2024-25 (3 $) passe pour la Young Guns d'origine (58 des 200 ventes de « kirill kaprizov
    young guns ») ; un lot « Young Guns + Dazzlers » passe pour la carte. `tendance_sortes.autre_carte` les écarte ICI seulement.
    À LUI DIRE et à corriger avec un test sur les comps. (Les gradées 8 et moins comptent comme des brutes : voulu, 22 nov.)
  * Écrans : Tendances → « Joueurs | Cartes » ; Cartes en hausse / en baisse (le joueur en gros, « Young Guns 2025-26 · 634 ventes »),
    « Par sorte, tous joueurs » ; Gratuit : les premières verrouillées. Radar : un badge de plus sur la photo, seulement LA carte
    du joueur, confirmée (son icône est la courbe). Fiche et fenêtre SlabIQ : la bande « Tendance de cette carte » (ou « Sa sorte,
    tous joueurs »). Un toucher : `feuilleSorte` (graphique, 3 chiffres, « s'est vendue ENVIRON X % plus cher »). « Double hausse /
    baisse » : la carte bouge ET le joueur est dans « Au plus haut / bas » : deux faits côte à côte, PAS prouvé pour la suite.
  * LIMITES à lui dire : presque tout est Young Guns (les recherches d'autos sont des paniers : « x rookie auto ») ; les cartes dont
    la recherche n'a pas été relue depuis 10 jours ne sont pas mesurées (1 363) : pour en couvrir plus, il faut relire les cartes
    exactes plus souvent (des crédits : SA décision) ; les recherches larges « upper deck kaboom hockey » (sans joueur) ne servent
    pas encore. La LETTRE SlabIQ n'a pas changé.
- **Fenêtre SlabIQ refaite (25 nov, 21 h 05, capture à l'ordi : « devrait tout fitter sur une page sans scroll ; couleur fade,
  manque de vie »)** : la couleur dit la note (A vert, B lilas, C or, D orange, E rouge, « — » gris), la lettre dans une pastille
  pleine, une barre de niveau au bas de chaque tuile, libellés en minuscules ; à l'ordi (900 px+) la fenêtre fait 880 px en DEUX
  colonnes (les 8 notes | la tendance, les faits, l'histoire) ; `ajusterPS()` resserre tant que la fenêtre déborde (s1 : 2 faits,
  histoire sur 3 lignes ; s2 : 1 fait, 2 lignes ; s3 : sans le mot sous le libellé) ; un toucher sur l'histoire la déplie.
  Mesuré : tient à 1830 × 883, 1280 × 680, 390 × 844 et 375 × 667. Classes `ps2`, `psg`, `pst` (les anciennes `psb-g` / `psb`
  ne servent plus à cette fenêtre). Tendances au petit iPhone : `tiq-serre` (sans la phrase) puis `tiq-court` (sans le
  sous-titre) pour tenir avec le nouveau choix du haut.
- **Leçons du soir** : `tendDe` et `.tiq-lt` existaient déjà (collision : erreur JS, puis style) : TOUJOURS chercher un nom dans
  tout le fichier avant de le créer. `tests/test_blessures.py` exige le texte exact « [data-np], .w-go ».
- **Suite complète le 25 nov, 22 h 40 : 298 fichiers, 0 échec** (168 s et 285 s), après la triple vérification.
- **26 nov, 7 h 30 – 8 h 30 : push de p98, export du 26, et le TEST SUR L'HISTORIQUE (demande de Mathieu : « je m'attends à la perfection ;
  qu'après ton analyse il nous soit impossible d'améliorer davantage notre modèle »)**.
  * Push de Mathieu à 7 h 29 (commit 63ed9a5, en ligne 7 h 30). À 8 h 18, le serveur n'avait PAS encore écrit sa ligne « Tendance
    des sortes : … » (le calcul se fait à la FIN d'un tour du chasseur, au plus un tour par heure, et rien n'est publié tant que
    les ventes ne sont pas triées) : à relire dans le journal Render.
  * Export du 26 nov (`ventes_hockey (6).tsv.gz`, pris dans ses Téléchargements, copie dans `/home/claude/export_2611/`) :
    1 993 717 lignes, 1 392 350 ventes uniques (+127 000 depuis le 24 : 2023 : 18 520 ; 2024 : 187 824 ; 2025 : 310 588 ;
    2026 : 875 381). Travail dans `/tmp/v26/` (base sqlite complète, `pipeline.py`, `mesure.py`, `histo.py`, `analyse*.py`,
    `double*.py`, `radar_joueur.py` ; la VM ne les garde pas).
  * Tendances sur l'export du 26 (vrai chemin) : 148 cartes mesurées (143 Young Guns et variantes), 127 joueurs, 14 hausses et
    37 baisses confirmées ; 2 sortes (Young Guns −9 % sur 129 cartes ; Young Guns PSA 10 −1 %).
  * TEST SUR L'HISTORIQUE (`histo.py`) : à chaque quinzaine depuis janvier 2024, chaque carte exacte mesurée COMME le module (avec
    les seules ventes d'avant), puis les 30 et 60 jours suivants : 4 918 mesures, 387 cartes, 205 joueurs. Résultats (médiane du
    mois suivant, intervalle à 90 % ré-échantillonné par carte ou par joueur) :
    - une HAUSSE confirmée : +1,0 % [0,0 ; +2,0] le mois suivant, 0,0 % de 30 à 60 jours : elle ne continue pas ;
    - une BAISSE confirmée : −2,5 % puis −5,0 %, mais c'est l'effet « nouveau produit » : carte de la saison en cours −7,2 %,
      carte d'une saison passée −0,1 % ;
    - carte de la saison en cours, peu importe le signal : −3 à −7 % par mois (déjà dans le modèle : la vague) ;
    - « DOUBLE HAUSSE » (son idée : la carte monte ET les autres cartes du joueur montent) : +5,8 % le mois suivant, 84 % se
      revendent à 90 % du prix et plus… mais 85 des 225 cas sont Macklin Celebrini (+10,3 %) ; sans lui +2,2 % [0,0 ; +7,3] ;
      sans les 5 joueurs les plus présents 0,0 % [−3,3 ; +2,4] ; un joueur = une voix (23 joueurs) : +1,9 %, 10 montent, 8
      baissent. PAS un signal. L'étiquette verte « Double hausse / Double baisse » est RETIRÉE des listes ; il reste une note
      neutre dans la fenêtre (« À noter : le marché de ce joueur… est aussi à son plus haut »).
    - le marché du joueur EN BAISSE (ses autres cartes) : ses cartes perdent encore 3,6 % [−5,9 ; −1,7] le mois suivant (29
      joueurs ; tient en 2024 et 2026, sans les 5 plus présents). MAIS testé dans le VRAI test du Radar Pro (`radar_joueur.py`,
      les 735 achats publiés, même définition du succès) : joueur en baisse 87,6 %, stable 88,5 %, en hausse 87,7 % ; « sauter les
      joueurs en baisse » : 87,8 % (rien de gagné) et 250 achats de moins. Les règles du Radar (liquidité, pas plus de 10 %
      au-dessus de ce qu'elle se vend) couvrent déjà ça. AUCUNE règle ajoutée, la lettre SlabIQ ne change pas.
  * TESTS DU SITE refaits sur l'export du 26, SANS écrire (`LR_TESTS_TRAV=/tmp/v26/ts`, 11 min) ; publié (24 nov) → refait :
    Radar Pro 638 achats, 87,1 % [84,6 ; 89,7] → 735 achats, 87,8 % [85,3 ; 90,2] ; accord 0,684 → 0,692 ; rho 0,929 → 0,952 ;
    corrections 112 → 118 ; hasard 12,7 % → 12,5 % ; profit après frais 28,5 % → 28,2 % ; SIMULATION d'un an : rendement
    +10,5 % → +7,9 %, bat le hasard 92 % → 87 %, écart 635 $ → 497 $, p10 +97 $ → −94 $, p90 1 268 $ → 1 081 $ ; inversions
    [B, C] → [A-, B+] et [B, C]. PAS publié : il doit dire « publie » (la simulation baisse).
  * Trois constats sur la MESURE elle-même (à lui dire, rien changé) : (1) les 735 achats du Radar Pro viennent de 33 joueurs,
    62 % de 5 joueurs (Schaefer 135, Fowler 93, Sennecke 89, Celebrini 71, Demidov 70) : l'intervalle publié [85,3 ; 90,2] traite
    chaque achat comme indépendant ; ré-échantillonné par joueur : [81 ; 94]. Sans ces 5 joueurs : 88,1 % (277 achats, 28 joueurs).
    (2) par sorte : Young Guns 91 % (524), YG PSA 10 85 % (111), variantes 81 % (54), Future Watch Auto 61 % (41 achats, 8
    joueurs : trop peu pour une règle ; Misa 1 réussi sur 14). (3) les « inversions » A- / B+ et B / C viennent de la mesure
    « combien de fois la carte est revendue » : une numérotée ou une auto (rare) revient 0,4 à 1,5 % du temps, une Young Guns
    7 à 17 %, quelle que soit la lettre : c'est la rareté, pas une erreur de lettre.
  * Suite complète le 26 nov, 8 h 30 : 298 fichiers, 0 échec. Livré (p99) : `source/src_app.html`, `ui/app.html`,
    `tests/test_tendance_sortes.py`, `NOTES_CLAUDE.md`. PAS poussé.
  * (Répondu à 8 h 52 : « Oui à tout » : voir plus bas. Restent : le NOMBRE de crédits et l'état du méga test.)
- **26 nov, 8 h 30 – 8 h 45 : le calcul des tendances ne partait pas sur le serveur**. Push de p99 par Mathieu à 8 h 29 (commit
  c4f3fef). Constat dans le journal Render : entre le déploiement de 7 h 30 et celui de 8 h 30, AUCUNE ligne « Tendance des
  sortes » : le calcul était accroché seulement à la FIN d'un tour du chasseur (un tour par heure au plus, long, et chaque
  déploiement le coupe). Corrigé : `tendance_sortes.passe_si_besoin()` dans la boucle horaire de `server.py` (après le test
  SlabIQ), dans son propre fil, quelques minutes après chaque déploiement ; `_ETAT` : jamais deux calculs à la fois ; le chasseur
  l'appelle encore à la fin de son tour (sans effet si c'est frais ou en cours). Journal attendu : « Tendance des cartes : calcul
  lance » puis « Tendance des sortes : N cartes mesurees… » (ou « N ventes encore a trier »). Suite complète : 298 fichiers,
  0 échec. Livré (p100) : `tendance_sortes.py`, `server.py`, `tests/test_tendance_sortes.py`, `NOTES_CLAUDE.md`. À POUSSER, puis
  lire le journal et comparer aux 148 cartes de mon calcul sur l'export du 26.
- **26 nov, 8 h 52 – 10 h 30 : « Oui à tout » (publie, corrige, intervalle par joueur) et « pourquoi la simulation baisse ? »**
  * POURQUOI LA SIMULATION BAISSE (+10,5 % → +7,9 %) : le code n'a pas changé (même empreinte `2fdb41790cb59bca`). Simulation
    rejouée hors serveur en changeant UNE chose à la fois (`/tmp/sim/decomp.py`, `cf.py`, `cf2.py` ; moyenne de 4 tirages) :
    publié 10,5 % → prix de revente mis à jour (2 jours de plus, ventes arrivées en retard ; Jagr 1990 Score Canadian PSA 10 :
    médiane 164 → 144 $) 10,0 % → 7 cartes de plus qui ont maintenant une revente, presque toutes perdantes (Bedard YG
    Achievement payée 81 $, revendue 37 $) 9,1 % → coupe au 14 oct 8,7-9,0 % → 4 joueurs que l'apprentissage monte à la note A
    avec plus de ventes (Yzerman 76 → 86, Richter 66 → 88, Binnington, Kucherov ; Yzerman : −18 %) 8,2 % → les 11 241 ventes
    ajoutées dans l'année simulée : +0,0. Bruit d'un tirage à l'autre : ±0,3 point (publié 10,1 à 10,6 ; refait 7,9 à 8,6 sur 8
    graines : le tirage publié, 7,9, est le plus bas). Le panier « avec SlabIQ » = environ 3 400 achats possibles de ~290 cartes,
    20 joueurs par mois (Hutson, Demidov, Caufield, Sennecke, Kaprizov en tête) : une dizaine de cartes déplacent le résultat de
    2 points. RAPPEL : la simulation n'est PLUS sur le site depuis le 23 nov (gardée dans `ui/slabiq_tests.json`, recherche).
  * « CORRIGE » : `cartes_match.py`, deux règles dans `raisons_refus` (elles n'ajoutent que des refus) :
    (1) LOT ÉCRIT AVEC « + » : `_plus_lot(titre)` (champ `plus` de `decoder`, le champ `exclu` ne change PAS : le Radar, la lettre
    SlabIQ et le test du site s'en servent) : « Young Guns + Dazzlers », « + Base YG », « + 3 Rookie Cards », « +more », « + Bonus ».
    Pas un lot : le « + » après un mot d'état (« NM-MINT + Oilers », « EX+ »), envoi / étui / certificat / compliment, les deux
    morceaux d'une même carte (« Jersey + Stick »), une ligue (« Murakami + MLB »), le mot suivant est dans la recherche ou un
    joueur connu (« Celebrini + Will Smith »). Vaut pour les recherches ET les comparables d'une annonce.
    (2) SUITE D'UN SET : « Renewed » (aussi « renewd », le code #YGR-nn) et « Achievement » (aussi #YGA-nn) absents de la
    recherche = une autre carte, SEULEMENT quand la recherche nomme un set ou une variante (`cible()["carte_nommee"]` : un
    `SETS_CLES` hors marques / séries, ou une parallèle). « anze kopitar », « mcdavid upper deck », « mcdavid edmonton oilers
    psa 9 » gardent tout, comme avant. Les comparables d'une annonce (`ident`) avaient déjà leur règle : inchangés.
    PAS dans la règle : « Flashback », « Throwback », « Rewind » (les légendes n'ont de « Young Guns » que la Flashback 2001-02 :
    « jaromir jagr young guns » = 100 % de Flashback ; les refuser viderait la recherche).
    AVANT / APRÈS sur les 1,97 M de ventes (`/tmp/tri/avant_apres.py`) : 6 628 ventes écartées (6 086 Renewed, 277 Achievement,
    265 lots), 371 recherches touchées ; médiane des 90 jours : bouge de plus de 5 % pour 113 recherches, plus de 25 % pour 60,
    plus que doublée pour 34 (toutes en hausse). « sidney crosby young guns » 78 → 20 ventes, 20 $ → 1 831 $ ; « connor mcdavid
    young guns » 97 → 42, 20 $ → 1 312 $ ; Ovechkin 15 $ → 1 568 $ ; Kucherov 2,79 $ → 311 $ ; MacKinnon 7 $ → 370 $ ; Makar 9 $ →
    324 $. Lots : 194 recherches, 9 dont la médiane bouge de plus de 5 %. 2 recherches sans vente en 90 jours après (« nick suzuki
    young guns psa 10 » : ses 2 ventes étaient des Renewed). Les cartes du PLAN (cible avec l'année) étaient déjà protégées par
    l'année : la faille touchait les recherches sans année (chasseur, fiches, recherche d'un utilisateur).
    `base_ventes.retrier_si_regle_change()` (appelée au début de `cartes_toutes`) : efface UNE fois par base (`PRAGMA
    user_version`, `TRI_VERSION = 1`) le verdict gardé (table `accepte`, ok = 1) des ventes dont le titre porte renew /
    achievement / YGR / YGA / « + » : 8 306 verdicts sur 463 964 dans la base du 26 ; la passe suivante les refait. À CHAQUE
    changement de règle du tri : monter `TRI_VERSION` et ajuster le motif.
    RESTE (pas fait, à lui dire) : (a) une Renewed dont le titre ne dit ni « Renewed » ni #YGR (« Upper Deck 2024-25 Series 2
    Young Guns Connor McDavid #201 ») passe encore dans une recherche sans année : 2 des 20 ventes de Crosby en 90 jours, 4-5
    des 42 de McDavid ; la médiane tient, mais il faudrait une règle « saison dominante » au niveau de la liste (l'année des
    titres est bruitée : pas « la plus ancienne ») ; (b) « Mint + SP Rookie » passe (le « + » après un mot d'état) ; (c)
    `liquidite.cle_base` lit « 2025/26 » comme une numérotation « /26 » (clé « /26 205 demidov guns ivan young » vue dans le test).
  * INTERVALLE PAR JOUEUR : `outils/tests_site.pro_reel` : `joueurs` et `reussi_ic95_joueurs` (on retire des JOUEURS avec tous
    leurs achats, 1 000 tirages, son propre tirage : `reussi_ic95` ne change pas). Radar Pro : 33 joueurs, [0,798 ; 0,954]
    (stable : [0,795 ; 0,951] à 10 000 et 50 000 tirages). J'avais dit « 81 à 94 » à Mathieu (calcul à la main du matin) : le
    calcul officiel donne 79 à 95, corrigé dans mon message. `outils/site_iq.bloc_vs` : une phrase de plus dans la note de la
    page SlabIQ seulement (« Ces 735 achats viennent de 33 joueurs : avec d'autres joueurs, le résultat du Radar Pro irait de
    79 % à 95 % »), bornes vers le bas ; `tests/test_site_a_jour.py` la vérifie (FR et EN, absente de l'accueil).
  * « PUBLIE » : `tests_site.py export_2611 --ecrire` (`LR_TESTS_TRAV=/tmp/v26/ts`) : publié 25 nov → 26 nov : ventes testées
    213 174 → 236 349 ; joueurs 990 → 1 001 ; accord 0,684 → 0,692 (« ≈ 70 % ») ; rho 0,929 → 0,952 ; Radar Pro 638 achats
    87,1 % → 735 achats 87,8 % [85,3 ; 90,2] ; seul 12,7 % → 12,5 % ; A et A+ contre E 4,3× → 4,9× (le site écrit 4×) ; défi :
    100 %. Fichiers : `ui/slabiq_tests.json`, `ui/site_slabiq.html`, `ui/site_accueil.html`.
    BULLETIN refait aux 4 dates d'avant (`/tmp/v26/bul/lancer.py` = `bulletin_iq.calculer`, deux dates à la fois sur 2 cœurs,
    ~15 min par paire) : 1er oct 86,2 % (1 466 achats), 15 oct 89,4 % (1 193), 29 oct 90,3 % (853), 12 nov 89,5 % (704), 26 nov
    87,8 % (735) ; seul 14,0 / 14,7 / 14,1 / 12,2 / 12,5 % ; la page : « Refait 5 fois. Le Radar Pro l'emporte 5 fois sur 5 »,
    « 86 à 90 % » contre « 12 à 15 % » (avant : 87 à 91 %). `bulletin_iq.pc` : la moitié vers le haut, comme `iq_publie.pro`
    (12,5 % seul s'écrivait « 12 % » au bulletin et « 13 % » au comparatif de la même page : round() de Python). À noter : avec les vieilles ventes du méga test,
    les coupes (65 % et 80 % des ventes par date) reculent : le test du 1er oct fixe ses lettres avant le 3 avril et mesure les
    reventes après le 7 août (avant le méga test : coupes bien plus tardives).
  * CRÉDITS pour relire les cartes exactes (pas fait, il doit donner un chiffre) : avec la fraîcheur de 10 jours, 173 cartes
    passent tous les garde-fous (148 publiées) ; sans la fraîcheur : 401 (249 publiables) : 228 cartes perdues faute de relecture,
    dont 101 publiables tout de suite. Une lecture = 1 page = 1 crédit ; aux 10 jours = 3 lectures par mois : environ 700
    crédits par mois pour ces 228 cartes. Mon « 1 360 cartes » du matin comptait AVANT le plancher de 20 $ et le minimum de
    ventes : corrigé dans mon message. Proposé : plafond de 1 000 crédits par mois. Les autos / numérotées par recherches de
    carte exacte : un autre budget, pas chiffré.
  * Push de p100 par Mathieu à 9 h 53 (commit 83796c9) : le calcul des tendances a maintenant sa place dans la boucle du serveur.
  * Suite complète le 26 nov, vers 10 h 15 : 299 fichiers, 0 échec (153 + 146 ; `test_tendance_sortes.py` attendait encore que
    cartes_match laisse passer la Renewed et le lot : mis à jour). Livré (p101) : `cartes_match.py`, `base_ventes.py`,
    `outils/tests_site.py`, `outils/site_iq.py`, `outils/bulletin_iq.py`, `ui/slabiq_tests.json`, `ui/slabiq_bulletin.json`,
    `ui/site_slabiq.html`, `ui/site_accueil.html`, `tests/test_tri_lots_suites.py` (nouveau), `tests/test_site_a_jour.py`,
    `tests/test_bulletin_iq.py`, `tests/test_tendance_sortes.py`, `NOTES_CLAUDE.md`. À POUSSER.
    APRÈS LE PUSH : au premier `cartes_toutes`, 8 000 verdicts environ sont refaits (une passe) ; tant qu'il en reste à trier, le
    calcul des tendances attend (« N ventes encore a trier ») et réessaie aux 10 minutes.
  * JOURNAL DU SERVEUR après son push (déploiement en ligne à 9 h 55) : « Tendance des cartes : calcul lance » à 9 h 57, puis
    « Tendance des sortes : 54554 ventes encore a trier (184498 lues) » à 10 h 00 : le méga test a ajouté des dizaines de milliers
    de ventes, une passe en trie 15 000 et la boucle ne repasse qu'aux heures (4 heures d'attente). Corrigé :
    `tendance_sortes.passe_si_besoin` enchaîne les passes dans son fil (`PASSES_MAX = 12`, `PAUSE_PASSE_S = 45`, `_PARTIEL`),
    s'arrête si une passe n'avance pas ; une passe = 2 min 20 s sur le serveur. Tant que rien n'est publié, la page Trending ne
    montre PAS le choix « Joueurs | Cartes » (il n'apparaît qu'avec des données) : d'où sa capture de 10 h 05 avec la vieille
    puce « CARDS » (« The most sought-after cards »). Ajouté au paquet p101 : `tendance_sortes.py`, `tests/test_tendance_sortes.py`
    (54 fichiers de tests qui touchent au tri, à la base des ventes et aux tendances relancés : 0 échec).
  * DEMANDE DE 10 h 06 (Mathieu, capture de Trending) : remplacer l'onglet « Cards » actuel par les tendances des cartes ; trois
    vues : les joueurs seuls, les cartes seules, et un mélange joueur + carte (« si un joueur est en baisse mais qu'une carte monte,
    c'est peut-être le temps de vendre la carte, et vice-versa ») ; « aucune erreur, sinon on perd toute notre crédibilité » ;
    « si tu as des questions, je vais valider ». PAS ENCORE BÂTI : je lui ai d'abord donné ce que disent les 3 ans de ventes
    (`/tmp/v26/croise.py` sur `histo_14_double.json`, 2 981 mesures, 98 joueurs ; « joueur » = ses AUTRES cartes, par les ventes) :
    - les deux cas qu'il décrit n'arrivent presque jamais : carte en hausse / joueur en baisse : 10 mesures (5 joueurs) ; carte en
      baisse / joueur en hausse : 7 mesures (5 joueurs). Une carte et le reste du joueur bougent ensemble : rien à conseiller là ;
    - une carte qui monte SEULE (joueur neutre) redescend : −0,9 % à 30 jours, −5,3 % à 60 jours [−9,3 ; −3,0] (111 mesures, 32
      joueurs ; sans les 5 plus gros −4,6 ; un joueur = une voix : 25 en baisse, 7 en hausse) ; le témoin (carte stable, joueur
      neutre) : 0,0 % ;
    - le joueur baisse (carte stable) : −2,9 % à 30 jours [−5,1 ; −1,5], −5,0 % à 60 jours (30 joueurs, 24 en baisse) ; carte et
      joueur en baisse : −4,2 % puis −5,5 % ;
    - carte et joueur en hausse : +3,4 % [−0,1 ; +9,5], sans les 5 plus gros 0,0 (Celebrini = 85 des 234 cas) : pas un signal.
    PLAN PROPOSÉ (à valider par lui) : trois onglets en haut de Trending : « Joueurs », « Cartes », « Joueur + carte » ; la puce
    « Cards » actuelle disparaît dès que les tendances des cartes sont là (sa liste des sortes recherchées : un lien dans
    « Cartes ») ; « Joueur + carte » montre les deux tendances côte à côte (la carte, et le reste des cartes du joueur) et ne
    dit en mots que ce qui est mesuré (« monte seule : en moyenne, redescend dans les 2 mois » ; « le reste du joueur baisse »),
    jamais « vends » ni un profit. À TESTER AVANT : la même croix avec l'indice public du joueur (celui de l'onglet Joueurs).
  * MÉGA TEST : je ne peux pas voir son état : le journal Render n'a qu'une ligne (« Mega test : tour (en_cours) », 25 nov
    21 h 12) et rien après les déploiements de 7 h 30 et 8 h 30 ; le navigateur intégré de son PC n'est pas connecté à SlabCoach
    (je ne me connecte jamais pour lui). À lui de le dire (écran admin).
- **26 nov, 10 h 17 – 11 h 30 : « Oui go pour 1 et 2 et voici mega test »** (Trending en trois vues ; 1 000 crédits par mois pour
  relire les cartes ; capture du méga test : TERMINÉ, 2 999 / 3 000 cartes, 1 209 131 ventes ajoutées, 23 533 pages, 26 967 crédits ;
  CompSniper : 35 931 utilisés ce mois-ci sur 50 000). Et à 10 h 10 : « pour Sold et Profit on devrait pouvoir ajuster le time
  frame jusqu'à 1 an ».
  * ERREUR DE MA PART, CORRIGÉE AVANT DE BÂTIR : je lui avais écrit à 10 h 15 « une carte qui monte seule redescend : −5 % dans
    les 2 mois (32 joueurs) ». FAUX SIGNAL : dans ce 1er test, « le reste du joueur » comptait la MÊME carte dans une autre note
    (Young Guns PSA 10 contre Young Guns). En version stricte (une autre base de carte, `tendance_sortes.base_carte`, 20 ventes au
    moins) : −0,3 % [−6,3 ; +11,1], 13 joueurs : rien. Le seul fait qui tient : le reste du joueur baisse et la carte ne monte
    pas → le mois suivant −5,0 % [−6,7 ; −2,1], 348 mesures, 19 joueurs : 14 en baisse, 4 en hausse (sans les 5 plus gros : −2,2 % ;
    Bedard = 104 des 348). L'app l'écrit EN JOUEURS (« chez 14 joueurs sur 19 »), sans grandeur. Détail et scripts :
    `outils/recherche/tendances_croisees/LISEZMOI.txt` ; constantes : `tendance_sortes.CROISE_MESURE` (à refaire à chaque gros export).
  * `tendance_sortes.py` : `croiser()` (chaque carte publiée reçoit `reste` = ses autres cartes, et `croix = "joueur_baisse"` quand
    le fait s'applique) ; `public()` envoie `reste` (un % seulement s'il est net), `croix`, `fait` {baissent, joueurs, depuis} ;
    `page()` : `par_joueur` (les joueurs avec 2 cartes mesurées ou plus, notes comprises, 40 au plus) et `croise_mesure`.
    Le 26 nov : 15 joueurs, 36 cartes (Martone, Schaefer, C. Hutson, Sennecke, Celebrini, Demidov, Bedard…). `lockerroom.
    _tendances_gratuit` : `par_joueur` vidé (Pro).
  * ÉCRAN (`source/src_app.html`, `ui/app.html`) : Trending = trois vues en haut, « Joueurs | Cartes | Joueur + cartes » (la 3e
    seulement s'il y a des joueurs à 2 cartes). « Joueur + cartes » : une ligne par joueur (▲ n · ▼ n · ● n), un toucher ouvre ses
    cartes (courbe + %), chacune ouvre sa fenêtre ; 3 colonnes à l'ordi. La puce « Cartes » de la vue Joueurs (« les cartes les
    plus recherchées ») s'efface au cell dès que les sortes « toutes » sont là (Pro) ; sa liste s'ouvre de Cartes → Par sorte →
    « Les sortes les plus recherchées › » ; à l'ordi, la colonne reste (rien ne bouge). Fenêtre d'une carte : une ligne « Les
    autres cartes du joueur baissent (−18 %) : 5 cartes, 148 ventes. Depuis 2024, dans ce cas… » (`resteTD`, chiffres du
    serveur). Aperçus (`/home/claude/vue/tend4.py`, `vend.py`) : cell 390 et 375, ordi 1830 et 1280 : tout tient, aucune erreur JS.
  * VENTES : le choix de période existait (menu sous les tuiles : ce mois-ci, 90 jours, 12 mois, depuis le début) mais au cell
    les tuiles ne disaient pas leur période (`.s` caché) : « VENDU · NOV », « PROFIT · 12 MO » dans le titre de la tuile, et
    toucher Vendu ou Profit ouvre une feuille « Période » (les 4 choix).
  * RELIRE LES CARTES EXACTES (son « oui » à 1 000 crédits par mois) : `tendance_sortes.a_relire()` (calculé avec les tendances,
    gardé dans `tendance_sortes.json`, jamais envoyé à l'écran) : les cartes qui passent les garde-fous et dont la dernière vente
    ou lecture a plus de 6 jours (`RELIRE_AGE_J` = 10 − 3 − 1 : avant que la fraîcheur tombe au calcul suivant) : 319 le 26 nov.
    `relire_si_besoin()` dans la boucle horaire de `server.py` (son fil) → `relire()` : `historique.rechercher(q, chasseur=True,
    principal=True, cache_s=6 jours)` (1 page = 1 crédit, compté dans le budget du mois de CompSniper), 60 par heure au plus,
    `LR_RELIRE_MOIS` (1 000 par défaut, RIEN à régler dans Render) ; état dans `tendance_relire.json` ; quand tout est relu (10
    lectures ou plus), le fichier des tendances est vieilli pour que le calcul reparte à l'heure suivante. Journal : « Tendance
    des cartes : N cartes relues (n / 1000 credits ce mois-ci, r a venir) ». Attendu : ~320 crédits au premier passage (5 à 6
    heures), puis ~1 000 par mois ; les listes devraient passer de ~148 à ~250 cartes.
  * MESURE DU MÉGA TEST (son « refais nos tests avec les nouvelles data ») sur l'export du 26 : `LR_MEGA_TRAV=/tmp/v26/mega
    python3 outils/mega_test.py export_2611 --dates 8` (une date aux 91 jours du 27 févr. 2025 au 26 nov. 2026 ; ~55 min sur un
    cœur). VERDICT : PAS PROUVÉ à 3, 6 et 12 mois (comme le 22 nov). Radar Pro, frais eBay compris (13,25 % + 0,40 $) :
    à 3 mois, gain net médian −12, −12, −10, −11, −9, −6, −9, −9 % (8 dates) ; gagnants 20 à 38 % contre 5 à 7 % au hasard ;
    jamais revendus : 0 à 1 % ; à 6 mois : −5 à −14 %, gagnants 18 à 41 % contre 6 à 10 % ; à 12 mois : −28 à +10 % (la dernière
    date seulement est positive : +10 %, panier +40 %, 580 achats). Ce que ça dit : les cartes du Radar Pro se revendent (99 %+)
    et gagnent 4 à 6 fois plus souvent que des achats au hasard, mais après les frais l'acheteur médian perd encore ~9 % à 3
    mois. Le site n'annonce toujours AUCUN profit de revente (règle permanente). `outils/mega_test_resultats.json` mis à jour
    (jamais sur le site). `tests/test_mega_test.py` : OK.
  * Suite complète le 26 nov vers 11 h : 299 fichiers ; 3 échecs pendant que la machine calculait le méga test, tous réglés :
    `test_sans_pickle` (mes scripts de recherche utilisaient pickle : passés à `cache_recherche`), `test_score_appris` et
    `test_slabiq_test` (délai de 600 s dépassé sous la charge : OK relancés seuls). Livré (p102) : `tendance_sortes.py`,
    `server.py`, `lockerroom.py`, `source/src_app.html`, `ui/app.html`, `tests/test_tendance_sortes.py`,
    `outils/mega_test_resultats.json`, `outils/recherche/tendances_croisees/` (7 fichiers), `NOTES_CLAUDE.md`. Avec p101 (pas
    encore poussé) : 30 fichiers à pousser en une fois.
- **26 nov, 11 h 20 – 12 h : « On est combien de fois meilleur avec SlabCoach ? On doit être vraiment simple »** puis « Oui » à
  ma proposition : UN chiffre, une phrase, deux barres, à la place du comparatif à trois colonnes (garde sa valeur, se revend,
  A contre E).
  * `iq_publie.fois_seul(R, bulletin=None)` → (N, bas, haut, nombre de tests) : N = le PIRE rapport « Radar Pro garde sa valeur /
    seul » parmi le test du site et chaque date du bulletin (`ui/slabiq_bulletin.json`), vers le bas : « N fois » est vrai à
    CHAQUE test, jamais écrit à la main. Le 26 nov : 6,16 / 6,08 / 6,40 / 7,34 / 7,02 → « 6× » (le test du jour seul dirait 7).
    `publics()["fois_seul"]` pour l'app.
  * Ce qu'il y a DANS le 6× (dit à Mathieu) : surtout la revente (99 % des cartes du Radar Pro se revendent contre 25 % seul :
    4 fois), un peu la valeur (parmi les revendues, 89 % gardent leur valeur contre 51 % : 1,8 fois) ; « seul » = tous les achats
    de 30 $ et plus de la même période (acheter sans trier). JAMAIS « 6 fois plus de profit » (méga test : pas prouvé).
  * `outils/site_iq.bloc_vs` : `<div class="cmp cmp-un">` : « 6× » en gros, « plus de chances que ta carte garde sa valeur. »,
    « Avec le Radar Pro 87 % » et « Seul 13 % » (deux barres) ; la note de la page SlabIQ perd la définition de « Se revend » et
    gagne « « 6× » : à chacun de nos 5 tests, le Radar Pro a fait au moins 6 fois mieux que seul (de 6,0 à 7,3 fois) ».
    Styles : `ui/site_base.html` (`.cmp-un`). Pages réécrites avec `site_iq.ecrire(R, defi)` depuis `/tmp/v26/ts/resultats.json`
    et `defi_pool.json` (le test n'a pas été refait : mêmes chiffres).
  * App, fenêtre SlabIQ (`expliquerSlabIQ`) : le gros chiffre devient « 6× » avec la même phrase que le site (« … Avec le Radar
    Pro : 87 %. Seul : 13 %. ») ; « 4× : une carte A ou A+ se revend plus souvent qu'une E » passe dans la rangée du dessous ;
    « au hasard » → « seul ». La fenêtre défilait déjà au cell avant (950 px pour 707) ; à l'ordi elle tient.
  * `tests/test_site_a_jour.py` (le N× = le pire des tests, un seul gros chiffre, même phrase dans l'app) et
    `tests/test_chiffres_partout.py` mis à jour ; aperçus : `/home/claude/vue/site6.py` (page SlabIQ et accueil, cell et ordi),
    `iqx.py`. Suite complète vers midi : 299 fichiers, 0 échec. Livré (p103) : `iq_publie.py`, `outils/site_iq.py`,
    `ui/site_base.html`, `ui/site_slabiq.html`, `ui/site_accueil.html`, `source/src_app.html`, `ui/app.html`,
    `tests/test_site_a_jour.py`, `tests/test_chiffres_partout.py`, `NOTES_CLAUDE.md`.
- **26 nov, 12 h – 13 h 30 : après son push (94f6c8d = p101 + p102 + p103), 4 demandes d'affilée** :
  * Vérifié en direct : le site dit « 6× », 87 % / 13 %, « Refait 5 fois » ; le serveur a calculé les tendances (225 cartes
    mesurées, 3 sortes, 20 346 ventes). « Pourquoi juste des Young Guns / 3 parallèles ? » : nos archives viennent des
    recherches de l'app (1 947 cartes exactes, 982 Young Guns ; les 1 131 autres sont éparpillées sur 370 sortes ; une ligne
    « Par sorte » veut 5 cartes mesurées). À faire : fusionner les doublons de sortes (« Dazzlers Blue » / « Blue Dazzlers »,
    « Upper Deck Young Guns Canvas » / « Young Guns Canvas ») et le libellé tronqué.
  * « Bug après avoir refresh » (Trending, l'en-tête par-dessus les onglets) : l'en-tête collant mesurait sa place pendant que
    `#vue` était encore décalé par le tirer-pour-rafraîchir. `ptrY()` (le décalage en cours), soustrait dans l'en-tête de
    Trending et la bande des Breaks ; `APRES_PTR.f` : la mesure est refaite à la fin du geste. Aperçu : `/home/claude/vue/ptr.py`.
  * « Le X en haut à droite est caché » (fiche d'une annonce, cell) : la fiche défile quand elle dépasse (dans l'app, sur un
    iPhone de 393 x 852, il reste 739 px : la fiche admin avec la bande de tendance et une alerte en fait 766) et le X, posé en
    absolu en haut du CONTENU, partait avec. Au cell (≤ 999 px) le X est maintenant `position:sticky` dans les deux fiches
    (`.fa-pub` : top 10 ; `.fb-adm` : top 18, sur le coin de la photo, marge du bas négative). IMPORTANT : la marge du haut de
    la fenêtre passe à 0 et c'est le X qui porte l'espace, parce qu'avec une marge interne Chrome et Safari comptent « top » à
    partir du contenu (un `top:10px` donnait 62 px). À l'ordi (X en absolu) un écouteur `scroll` le fait suivre
    (`fen-x-suit`). La bande de tendance de la fiche admin perd sa marge du haut au cell (16 px dessus, 8 dessous → 8 partout).
    Aperçus : `/home/claude/vue/fen.py` (fiche Pro) et `fen_adm.py` (fiche admin : il faut `S.forfait.comps = true` et simuler
    `/api/annonce_detail`), tailles 393x852, 393x759 (= iPhone dans l'app), 375x667, 440x863, ordi 1280x560.
    Test : `tests/test_fen_x_colle.py`.
  * **Les données PSA (« quelles cartes valent la peine d'être gradées »)**. Sa méthode (12 h 31) : toutes les parallèles
    vendues en PSA 10 sur ~3 mois, la moyenne raw contre la moyenne PSA 10 sur la même période, classées par rapport ; le Radar
    les détecte ; Admin d'abord, Pro ensuite. 12 h 46 : « on y va pour le mega test pour données PSA, juste me dire quand le
    partir ». Constats : (1) nos archives ont déjà ~46 600 lignes « PSA 10 » et ~31 100 « PSA 9 » sur 120 jours, mais rangées
    sous la recherche qui les a trouvées : une PSA 9 trouvée par une recherche raw est refusée (« gradée ») au lieu d'être
    comptée comme PSA 9 ; il faut ranger PAR TITRE. (2) `grader.py` (17 nov) est trop optimiste (PSA 9 = 45 % de la PSA 10 :
    le vrai est ~25 % ; 62 « oui » sur 93). (3) Sans population PSA (interdit), on ne peut PAS écrire une chance de 10 : on
    montre « si 10 », « si 9 » et le seuil de rentabilité, jamais un profit espéré.
    Construit : `banque_psa.py` (base À PART `banque_psa.sqlite` : JAMAIS dans `base_ventes`, une recherche « joueur + note »
    mélangerait des cartes dans les tendances et les tests publiés). Phase 1 : « <joueur> psa 10 » et « <joueur> psa 9 » pour
    les 200 premiers joueurs de l'indice (actifs d'abord), 120 jours, 30 pages au plus. Phase 2 : chaque carte exacte vue 4 fois
    ou plus en PSA 10 (`carte_du_titre` : `cible_titre` + `raisons_refus` + `tendance_sortes.autre_carte`, donc les règles des
    comps ET des tendances) : sa recherche raw (`requete_ebay` sans la note), 8 pages au plus, sautée si elle est déjà dans nos
    archives et fraîche (20 ventes, la dernière de 10 jours ou moins). Plafond 8 000 crédits par défaut (choisi dans la
    fenêtre), budget du mois moins `LR_MEGA_RESERVE`. NE PART JAMAIS SEULE (`continuer_si_besoin` ne reprend qu'une collecte
    déjà lancée). Admin > Mesures > « Données PSA » (`feuilleBanquePSA`, routes `admin_banque_psa`, `admin_banque_psa_lancer`).
    Essai du rangement par titre sur nos archives (`/tmp/v26/proto_psa.py`) : Bedard 363 ventes PSA 10 dans 85 cartes (Young
    Guns 128, O-Pee-Chee Glossy 22, Glossy Gold 11…). Test : `tests/test_banque_psa.py`.
    SUITE (paquet suivant) : la liste « À grader » dans Admin (raw / PSA 10 / PSA 9 par carte exacte ET par saison : la
    recherche raw n'a pas l'année ; même période pour les trois ; ce qui reste après frais PSA et eBay), puis le badge du Radar.
  * **Onglet « Player + cards » : « c'est juste plus compliqué pour rien »** (12 h 50, capture « ▼1 ●2 »). Proposé A (un seul
    chiffre par joueur : toutes ses cartes ensemble sur 30 jours, En hausse / En baisse, même look que Cards ; on touche = ses
    cartes une par une) ou B (deux signaux côte à côte) → « Oui A, ça doit être compréhensible en 1 sec ».
    FAIT (p105) : `tendance_sortes.joueurs_ensemble(pc, mes, auj)` : `_agreger` sur les cartes PUBLIÉES du joueur (exactement
    celles qu'on voit en le touchant ; les notes d'une même carte comptent), 2 cartes et 40 ventes au moins, le même test que
    LA carte d'un joueur (p < 0,01 et la courbe dans le même sens) ; sans mouvement net, le joueur n'est dans aucune liste.
    Gardé dans le fichier (`joueurs`, `joueurs_hausses`, `joueurs_baisses`, `format: 2`) ; `calculer_si_besoin` refait un fichier
    d'avant (sans `format`) sans attendre 3 jours : après un déploiement, l'onglet revient au premier calcul (~10 min) ;
    d'ici là `page()["joueurs"]` vaut None et l'onglet est caché. `page()["joueurs"] = {hausses, baisses, n}` (chaque joueur :
    pct, serie, n, n_cartes, `cartes` = ses cartes pour la fenêtre) ; `par_joueur` (l'ancienne forme) est encore envoyé pour une
    app pas rechargée. Gratuit : `so["joueurs"] = None`. Écran : puces En hausse / En baisse, rangées « rang, nom, N cartes ·
    N ventes, courbe, % », « Voir les N » ; la fenêtre du joueur : « Ses N cartes ensemble », puis chaque carte. Plus de ▲▼●.
    Sur ma copie des ventes (148 cartes publiées) : 15 joueurs, 3 en hausse (Levi +60, Cooley +31, Kaprizov +13), 7 en baisse
    (Martone −42, C. Hutson −25, Celebrini −16, Demidov −12, Schaefer −9, Bedard −9, Sennecke −7), 5 sans mouvement net.
    Aperçu : `/home/claude/vue/tend5.py` (données : `/tmp/v26/joueurs_auj.py` → `page_sortes2.json`).
    À polir : la carte « Smith Young Guns » de Celebrini est la vraie #499 « Young Guns Teammates Celebrini/Smith » (libellé
    à clarifier) ; au cell `ajusterTiq` ne montre que 3 rangées alors qu'une 4e tiendrait.
  * **13 h 31 – 13 h 32, AVANT que p105 soit poussé : il change d'idée, Trending passe à DEUX onglets.** « On pourrait mettre la
    note du joueur à côté du trend ? Comme ça on aurait seulement 2 onglets ? Pour carte c'est rising et falling et joueur c'est
    highest et lowest : garder rising et falling pour les 2 » puis, devant « See all 16 » : « Juste 16 risers ? On devrait en
    avoir le top 100 pour les 2 ». Demandé et répondu (deux questions à choix) : 2 onglets EN HAUT (Players | Cards), la note
    du joueur seulement sur les lignes des joueurs (sur une carte, un « A+ » se lirait comme la note de la carte).
    FAIT (dans p105, qui remplace la vue A à l'écran) : l'onglet « Joueur + cartes » et tout son code d'écran sont enlevés
    (`joueurs_ensemble` reste calculé et envoyé par le serveur, sans écran : à réutiliser dans la fiche du joueur au besoin) ;
    joueurs : puces « En hausse » (`haut`) puis « En baisse » (`bas`), comme les cartes ; titres « Joueurs en hausse / en
    baisse » (`CATS_IQ`, panneaux) ; la ligne garde son fait (« Au plus bas en 12 mois ») ; `noteM(x)` : la lettre SlabIQ du
    joueur à droite du %, classe `.tiq-nj` (ATTENTION : `.tiq-lt` existait déjà, c'est le titre d'une liste en `display:flex`) ;
    au cell les colonnes sont resserrées (`:has(.tiq-nj)` : rang 18, courbe 50, pastille 64, espace 8) pour garder 137 px au
    nom. La puce « Joueurs » (les plus recherchés) n'existe plus quand les tendances des cartes sont là : la liste est dans
    « Plus de listes » (`top` n'est plus exclu de `autres`) et dans la 3e colonne à l'ordi. Aperçu : `/home/claude/vue/tend6.py`.
    TOP 100 : `Api.TEND_TOP` 25 → 100 (et `cats[bas|haut]` n'est plus coupé à 40), `N_LISTE_CARTES` 25 → 100. Le plafond
    monte, PAS les règles : « 16 » n'était pas un plafond, c'est le nombre de cartes dont la hausse est confirmée (p < 0,01,
    20 ventes, courbe dans le même sens) sur 225 cartes mesurées ; sur ma copie : 14 hausses et 36 baisses confirmées sur 148
    (25 baisses seulement étaient montrées). Pour avoir vraiment 100 hausses il faut mesurer ~6 fois plus de cartes : (1) la
    relecture finit de rafraîchir les ~400 cartes qui passent les autres garde-fous ; (2) importer dans les archives les
    recherches raw de la phase 2 de la collecte PSA (des cartes exactes, 120 jours, toutes notes) APRÈS avoir vérifié leurs
    libellés sur un export, puis monter `LR_RELIRE_MOIS` (1 000 → ~5 000 par mois pour ~1 500 cartes) : son accord d'abord.
  * 13 h 27 : il lance la collecte PSA (plafond 10 000, 36 080 crédits utilisés ce mois, dispo 12 420 avant la réserve).
    `banque_psa.py` (p105) : l'étape 2 saute les titres sans « psa » ni « 10 » et respire tous les 500 titres ; une ligne de
    journal aux 100 crédits (« Donnees PSA : N credits (phase P : recherche, page X) ») et à la fin de chaque tour.
    À FAIRE pour la liste « À grader » : une route d'export admin de `banque_psa.sqlite` (pour valider l'analyse sur ma copie).
  * **ANOMALIE NON EXPLIQUÉE, 13 h 28** : journal « Donnees PSA : reprise (en_cours) » 45 s après son lancement (13 h 27 min 46).
    La boucle de l'heure (première passe, 180 s après le démarrage) a donc vu `ETAT["en_cours"]` à faux ET le statut
    « en_cours » dans la base. Un seul worker gunicorn (vérifié : `-w 1`, un seul « Booting worker »), aucune trace d'erreur
    dans le journal, impossible à reproduire en local (`/tmp/simu_psa.py` : `continuer_si_besoin` rend bien None pendant
    qu'elle tourne). Soit le premier fil est mort sans trace, soit deux collectes ont tourné en même temps (chaque page payée
    deux fois) jusqu'au redémarrage suivant. Demandé à Mathieu : une capture de la fenêtre (crédits ≈ pages : une seule ;
    crédits ≈ 2 x pages : deux). CORRIGÉ dans p105, dans la BASE (vrai même entre deux processus) : (1) `vivante()` : statut
    « en_cours » et battement de moins de 180 s = elle tourne : ni la boucle, ni le bouton, ni `collecter` ne la doublent ;
    (2) le JETON : chaque collecte écrit le sien en partant et le relit avant chaque page ; s'il a changé, elle s'arrête sans
    toucher au statut (« une autre collecte a pris le relais »). `cartes_psa10(battre=…)` bat pendant le décodage de l'étape 2.
    La fin de chaque tour est écrite dans le journal (statut, crédits, erreur). Test : « JAMAIS DEUX OK ».
  * 13 h 24 : « c'est poussé » (commit 0e7c136 = p104, en ligne à 13 h 25, aucune erreur au démarrage). Journal 13 h 09 :
    « Tendance des cartes : 54 cartes relues (54 / 1000 credits ce mois-ci, 1 a venir) » : la relecture des cartes exactes tourne.
- **26 nov, 14 h – 14 h 45 : la liste « À grader » (Admin), paquet p106.** `a_grader.py` + `tests/test_a_grader.py`.
  * `classer(titre, joueur)` → ((joueur, recherche raw, année, /N, numéro de carte), « raw » | « 10 » | « 9 ») ou None. Le décodeur
    de `cartes_match` a des pièges, tous couverts par le test : (1) « PSA 10 ? », « Possible PSA 10 », « PSA 10 ready »,
    « contender » sont lus comme une PSA 10 → écartés (`_RE_ESPOIR`) [ce piège existe AUSSI dans les comps de l'app : une raw
    « PSA 10 ? » est acceptée comme comparable d'une PSA 10 : À CORRIGER dans `cartes_match`] ; (2) une PSA 8 et moins a
    `grade = None` et `grade_bas` rempli, « graded 9 » / « slab » n'ont aucune note → jamais comptées comme raw
    (`_RE_GRADEE`) ; (3) une numérotée /100 est refusée par `raisons_refus(cible(q))` si la recherche ne dit pas « /100 » → on
    teste avec `q + " /N"` ; (4) une couleur seule (« Gold ») a `carte_nommee` vrai mais `ident` vide → il faut un SET ;
    (5) abîmée (`_RE_ABIMEE`) : pas une raw à grader.
  * `analyser(ventes)` : dédoublonne par numéro d'annonce, range par titre, rattache une vente sans année / sans numéro à la
    carte seulement s'il n'y en a qu'une (90 %), LA MÊME PÉRIODE pour raw et PSA 10 (depuis le jour où les deux sont
    couvertes), médianes, 5 raw et 5 PSA 10 au moins (4 → 5 dès l'essai), PSA 9 dès 3 ventes sinon vide, prix trop étalés
    (q75 / q25 > 3) → pas listée. Par carte : `reste10`, `reste9` (frais eBay 13,25 % + 0,40 $, PSA + envoi 41 $), `seuil`
    (part de 10 pour ne pas perdre ; 0 = rentable même en 9 ; None = PSA 9 inconnue ou perd même en 10), `rendement` (net de
    la PSA 10 / (raw + 41 $)) : la liste est classée par rendement (classer par PSA 10 / raw mettait en tête des cartes à
    2 $). JAMAIS de chance de 10 ni de profit espéré.
  * Essai sur ma copie des archives, 60 joueurs (`/tmp/v26/proto_grader.py`, 181 013 ventes, 116 s) : 103 cartes. Tête de
    liste : Sennecke YG 2025-26 (raw 78 $, PSA 10 675 $, PSA 9 213 $ : +466 / +65), Slafkovsky YG, Boldy YG (31 → 377),
    Celebrini YG (542 → 3 030), Gauthier YG (38 → 406 : +273 / −1), Misa YG (41 → 417), Hutson YG (112 → 748), Demidov YG.
    La PSA 9 vaut en général 20 à 30 % de la PSA 10.
  * Serveur : `_ventes_serveur()` = toute la collecte PSA (`banque_psa.sqlite`) + nos archives pour les mêmes joueurs
    (`q >= "<joueur> " AND q < "<joueur>!"`) ; `calculer()` en fond (`lancer`, `refaire_si_besoin` dans la boucle de l'heure :
    une fois par 20 h, seulement si la collecte a des ventes), gardé dans `a_grader.json`. Routes `admin_a_grader`,
    `admin_a_grader_calculer` ; export `/admin/psa_export.tsv.gz` (titre, prix, date, recherche, joueur, id).
    Écran : Admin > Mesures > Données PSA > « La liste À grader » (`feuilleAGrader`), prix = ADMIN seulement.
  * À FAIRE : le badge « À grader » du Radar (Admin d'abord), le test sur l'historique avant Pro, les libellés (« Skates
    Silver » = Silver Skates), les Renewed numérotées de deux façons (#201 et #YGR-10 font deux cartes).
- **26 nov, 14 h 26 : « Si ce sont de fausses valeurs, oui, il faut les enlever »** (une raw « PSA 10 ? » comptée comme PSA 10
  dans les comps). Paquet p107. `cartes_match.espere_note(titre)` (`_RE_ESPERE`) ; `raisons_refus` : quand la carte cherchée est
  gradée (ou « graded »), une vente qui espère sa note est refusée (« pas gradée (espère la note) ») ; cherchée raw : inchangé
  (elle reste refusée « gradée ») ; la règle n'ajoute que des refus. `a_grader` utilise la même fonction.
  LA RÈGLE EST ÉTROITE EXPRÈS, mesurée sur 52 544 ventes « PSA 10 / PSA 9 » de 120 jours (`/tmp/v26/espoir.py`) : la note
  suivie de « ? », « contender », « candidate », « worthy », « ready » (pas « ready to ship »), « potential / possible » (pas
  « possible black label ») ; « possible / potential PSA|gem » ; « ungraded », « not graded ». PAS : un « ? » ailleurs dans
  le titre (40 titres : « HOF? », « next MLB? » : de vraies PSA 10), « should be a 10 » (de vraies PSA 9), « raw »,
  « future » (« Team of the Future »). Effet réel (`espoir_effet.py`) : 3 ventes acceptées deviennent refusées ; une valeur
  change vraiment : « beckett sennecke young guns psa 10 » 606 $ → 667 $ (la « PSA 10 Contender » à 100 $ sur 7 ventes).
  `base_ventes.TRI_VERSION` 1 → 2 : les verdicts gardés des ventes qui portent ces mots sont refaits une fois (une base déjà
  en version 1 ne refait que ceux-là). Tests : `tests/test_espere_note.py`. Suite complète : 303 fichiers, 0 échec.
  Vu en passant, NON corrigé : « PSA 10 possible black label » est refusée comme « variante black » (une vraie PSA 10 perdue).
- **26 nov, 14 h 55 : « Pushed » (commit e34dd4f = p105 + p106 + p107, en ligne à 14 h 55). L'ANOMALIE DE 13 h 28 EST EXPLIQUÉE.**
  Journal : 14 h 57 min 59 « Donnees PSA : reprise (en_cours) » puis, 22 s plus tard, « Donnees PSA (fin) : OperationalError
  ('database is locked') » et « Exception in thread donnees-psa … sqlite3.OperationalError: database is locked ». La collecte
  MEURT quand une base est occupée : (1) cette fois, `a_grader._ventes_serveur` tenait un curseur ouvert sur
  `banque_psa.sqlite` pendant tout son calcul (`fetchmany` dans un générateur : un verrou de lecture pendant des minutes, les
  écritures de la collecte expirent après 10 s) ; (2) `historique._cx()` n'attend que 5 s et `historique._compter` n'était pas
  protégé (le même défaut existe dans `mega_test.py`). Le `_run_maj` du `finally` échouait aussi → statut resté « en_cours » :
  d'où la « reprise » de 13 h 28. Donc PAS deux collectes en même temps : une collecte morte puis relancée. Rien payé deux fois.
  CORRIGÉ (p108) : `banque_psa._tenace` (chaque lecture / écriture de la collecte réessaie 2 minutes : 1, 2, 4, 8, 15, 30, 30,
  30 s), `_cx` attend 30 s, une erreur imprévue donne le statut « erreur » (plus jamais « en_cours » pour toujours) ;
  `a_grader._ventes_serveur` lit par blocs de 5 000 avec une connexion courte par bloc (test : une écriture passe pendant le
  calcul). `tendance_sortes.passe_si_besoin` : la condition « format » manquait (elle n'était que dans `calculer_si_besoin`) :
  après le push de 14 h 55 le fichier n'a PAS été refait (journal : aucun « calcul lance ») ; corrigé et testé.
  À FAIRE : la même ténacité dans `mega_test.py` (`historique._compter` nu).
- **26 nov, 15 h 06 : « Dans trend on devrait voir la liste du top 100 à grader qui se refresh chaque semaine »** → demandé qui le
  voit : « Admin seulement » pour commencer (le Pro après le test sur le passé ; en Pro, jamais un prix : rendement et seuil
  seulement). FAIT (p108) : `a_grader.top_tendances()` (100 premières), `REFAIRE_J = 7` (refaite chaque semaine, une fois de
  plus quand la collecte PSA finit, et à la demande) ; `tendances_iq` ajoute `a_grader` SEULEMENT si `_est_admin()` (ni Pro,
  ni Gratuit, ni l'admin en vue client : testé) ; écran : 3e onglet « À grader » (`modeT === 'grader'`, classe `tiq-mixv`
  réutilisée), une ligne = rang, joueur, carte, « Rentable même en 9 » / « Il faut N % de 10 », ×rendement, AUCUN prix ; un
  toucher : `agCarte(x)` (raw, PSA 10, PSA 9, si 10, si 9), partagé avec la fenêtre admin. Aperçu : `/home/claude/vue/tend7.py`.
  Sur le serveur à 15 h 02 : « A grader : 156 cartes (179 825 ventes lues, 101 060 rangées, 262 s) ».
  15 h 18 : il a relancé la collecte PSA lui-même (le serveur avait encore la version sans ténacité).
  À DÉCIDER avec lui quand la collecte aura fini (on connaîtra son vrai coût) : rafraîchir les DONNÉES chaque semaine coûte
  des crédits (une semaine de ventes par recherche : de l'ordre de 2 000 à 2 500 crédits par semaine) ; sans ça, la liste
  refaite chaque semaine vieillit avec ses données.
- **Demandé pour demain (21 h 02)** : « améliore SlabIQ et refais nos tests avec les nouvelles data une fois obtenues ; tu devrais
  aller chercher tout automatiquement » → refaire les tests sur les ventes de la collecte de 3 ans ; SlabIQ ne change que si le test
  le prouve ; le test publié sur le site doit tourner seul sur le serveur (tâche `g_c_auto`), sans export à la main.
