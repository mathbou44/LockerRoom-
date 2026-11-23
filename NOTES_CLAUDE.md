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
- **Apple (samedi)** : note au réviseur fournie à Mathieu ; il doit y mettre le code démo. Pas de « Bêta » visible.
  Après l'approbation : retirer le code démo (conseil dans `ceo.py`).
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
  .csv.gz, relus identiques) ; `tests/test_sans_pickle.py` l'interdit partout. RESTE UN pickle : `demande_legale.py` (le modèle
  sklearn de la demande, écrit et relu par notre serveur). À retirer en 2 temps, car un trou sans modèle changerait la valeur
  des joueurs sans ventes. Mathieu a dit « oui » (23 nov, 14 h 50).
  **1er temps : FAIT le 23 nov** (`demande_legale._exporter_arbres`, `ArbresJson`, `_sauver_arbres_json` ; `tests/test_arbres_json.py`) :
  chaque passe horaire écrit `demande_legale_arbres.json` (5 Mo) et compare notre prédicteur à sklearn sur tous les joueurs ;
  l'état est dans `labo.arbres_json` et dans le journal (« Demande legale : … ; arbres JSON {'ok': True, …, 'ecart': …} »).
  Mesuré en local sur le vrai modèle (forêt de 500 arbres, 757 joueurs) : écart 4e-16, 0 demande différente, 1 ms par joueur
  (sklearn : 88 ms). On lit ENCORE pickle.
  **2e temps : À FAIRE**, au moins 1 h 30 après la mise en ligne du 1er temps : vérifier dans les journaux Render la ligne
  « arbres JSON {'ok': True » (demander à Mathieu l'espace Render : un seul existe, « LockerRoom », mais il doit le confirmer) ;
  puis `_arbres()` lit le JSON (`ArbresJson(json.load(...))`), retirer `_sauver_arbres`, les 2 `import pickle`, `_chemin_arbres`
  (.pkl), l'exception `EXCEPTIONS` et le bloc « l'exception reste » de `tests/test_sans_pickle.py`. L'ancien fichier .pkl reste
  sur le disque (pas de suppression sans permission).
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
