# Notes de passation pour Claude (SlabCoach)

À lire au début d'une nouvelle conversation avec Claude (nouveau compte, nouveau courriel, nouvelle session).
Aucun secret ici : les clés restent dans Render (Environment), jamais dans ce fichier ni dans le chat.

## Le projet
- **SlabCoach** : app de cartes de hockey. Flask hébergé sur Render (www.slabcoach.com, gunicorn `-w 1 --threads 32`,
  disque persistant /data 10 Go) + app iOS Capacitor.
- Dépôt : ce dossier (`LockerRoom-`), copie miroir dans `PycharmProjects/LockerRoom`.
- L'écran : `ui/app.html` (construit à partir de la source `src_app.html` avec `outils/construire_cloud.py lr --ecrire`).
- Tests : `for t in tests/test_*.py; do python3 $t; done` (tous doivent passer avant de pousser).
- Pousser = GitHub Desktop (Commit puis Push origin) ; Render déploie seul.

## La mission (Mathieu)
Aider monsieur, madame tout le monde (un papa, un grand-père, quelqu'un qui travaille) à suivre sa collection, savoir
quand acheter et quand vendre, sans le bruit des influenceurs ni les pumps. Un enfant de 12 ans doit s'en sortir.
On vise le monde ordinaire du hobby ; les connaisseurs en profitent aussi.

## Façon de travailler
- Réponses en français, concises, sections avec ▓ ; barre de progression et petites nouvelles pendant les longs travaux.
- Design : pastilles rondes, icônes en traits, pas d'emoji, de vraies données ; fenêtres au centre, fond flou, un X.
- Avant d'écraser un fichier du PC : comparer pour être sûr que seuls nos changements diffèrent.
- Après un changement d'algorithme SlabIQ : refaire le test avant/après et garder seulement si c'est meilleur.

## Règles permanentes
- Jamais de mot de passe, de NIP ni de clé dans le chat ; Mathieu met les clés lui-même dans Render.
- Ne jamais toucher LOCKERROOM_CLE ; ne pas régler PSA_LICENCE ni LOCKERROOM_MISES_APPROUVEES ; ne pas toucher le
  disque ni les variables de Render ; ne pas monter les plafonds LR_SOLDCOMPS_JOUR / LR_DEALS_VERIF_JOUR / LR_DEALS_VERIF_PRIO.
- SlabCoach ne mise jamais tout seul.
- Licence eBay : comps, médianes, deals et prix suggérés = admin seulement (LR_PRIX_ANNONCES=1 seulement avec l'accord
  écrit d'eBay). Le score public n'utilise jamais le prix des annonces ; les ventes servent seulement à entraîner (labo).
- Nouvelles : titre + lien seulement ; pas Google News, ESPN, Yahoo ; pas de scraping de Google Trends.
- Pas de logos LNH, d'équipes ou de fabricants ; pas de population ni d'images PSA ; pas d'étiquettes PSA/TAG.
- Alertes de deals, promos et SlabIQ : fermées par défaut ; photos d'entraînement seulement avec consentement.
- SlabCoach reste séparé de Hall of Cardz / Onetwelve (Shopify, Klaviyo, OpenArt = Onetwelve).
- Pas de dépendance à 130point.

## Où on en est (12 nov 2026, v236 en ligne)
- **SlabIQ** : test de mouvement des cartes (top 2 % : 15/15, top 3 % : 22/23) + journal en direct chaque semaine.
  Le marché de l'équipe aide l'Indice joueur mais PAS le modèle de mouvement (testé : moins bon) ; il n'y est pas.
- **Types de cartes** (`types_cartes.py`) : chaque sorte comparée aux autres cartes du même joueur ; test avant/après
  chaque semaine sur 4 mois jamais vus ; se retire seul du score si ce n'est pas mieux (tuile Admin « Types de cartes »).
- **« Ce que tu as manqué »** (`quoi_de_neuf.py`) et **Nouveau dans l'app** (liste `MAJ_APP` dans src_app.html :
  ajouter une entrée à chaque grosse mise à jour, en mots simples, sans fonction réservée à l'admin).
- Sauvegarde de nuit vers Cloudflare R2 (`sauvegarde.py`) : active dès que les clés R2 sont dans Render.

## En attente
- Réponse d'eBay (prix vendus montrés au public) et accès à l'API Google Trends (alpha).
- Vérifier la tuile Admin « Types de cartes » (vert = le test avant/après est meilleur).
