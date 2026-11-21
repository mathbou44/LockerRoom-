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
- Écrire les fichiers changés directement dans le dossier `LockerRoom-` de son PC, vérifier le md5, puis lui dire
  de pousser avec GitHub Desktop. Jamais de git (commit/push) depuis la VM.
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

## En attente
- **Apple (samedi)** : note au réviseur fournie à Mathieu ; il doit y mettre le code démo. Pas de « Bêta » visible.
  Après l'approbation : retirer le code démo (conseil dans `ceo.py`).
- **Baseball** : test SlabIQ à refaire dès que Mathieu exporte des ventes fraîches (Entraîner SlabIQ → ↓ Ventes Baseball).
- **Courriels de licence (7, dont Fanatics)** : attendent le connecteur Gmail et le choix de l'adresse d'envoi.
- **Cloudflare** : activer la 2FA (créer un mot de passe via « mot de passe oublié » car il se connecte avec Google),
  activer HSTS (Edge Certificates), ajouter DMARC p=none. Ne PAS activer Bot Fight Mode (bloque Stripe, Apple, eBay).
- **Aikido** : relancer le scan ; ignorer avec raison lightgbm, liste IP GitHub, SSRF (faux positif), CSP.
- Prix annuel Stripe à confirmer. Réponse d'eBay (prix vendus montrés au public) toujours attendue.

- Inventaire = des CARTES seulement (20 nov 2026, Mathieu : « un cadre signe, c'est pas une carte ; pas de tables de cuisine ni de chaudrons ») : rien n'entre tout seul s'il n'est pas une carte a l'unite (cartes_match.est_carte_seule). Objets signes, cadres, photos, chandails, rondelles, fournitures, boites scellees, places de break : jamais importes automatiquement.

- Nouveautés (MAJ_APP dans source/src_app.html) : a chaque grosse mise a jour, ajouter une entree (n plus haut, date, 3-4 points en mots simples, ce qui change pour la personne). Demande de Mathieu, 20 nov 2026.

- Ergonomie (Mathieu, 20 nov 2026) : l humain est paresseux ; s il ne trouve pas l info en quelques secondes, il part. Chaque page, fenetre et option : l essentiel visible tout de suite, pas de grosses tuiles vides, pas de barre de defilement, entete compacte (une ligne a l ordi). Modele : Apple.

- To-do (Mathieu, 21 nov 2026 : « les priorites et choses a faire devraient toujours etre dans la to-do de la page admin ») : toute nouvelle priorite, decision a prendre ou chose a faire (pour Mathieu OU pour Claude, prefixe « Claude : ») va dans la to-do de l admin : un nouveau semis dans ceo.py (SEMIS["<nom>"], projet « lancement » ou autre, 7e element = echeance). Un document (docs/...) peut la resumer, jamais la remplacer.

- Pousser (Mathieu, 21 nov 2026 : « pousse toujours ») : apres chaque livraison (tests passes, md5 verifies sur le PC), Claude fait lui-meme Commit + Push dans GitHub Desktop sur le PC de Mathieu (commande de l ordinateur, acces a GitHub Desktop), sans redemander. Toujours par GitHub Desktop : jamais de git depuis la VM. Si GitHub Desktop n est pas joignable : le dire et laisser Mathieu pousser.
