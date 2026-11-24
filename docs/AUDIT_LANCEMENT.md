# Audit avant le lancement (commencé le 24 novembre 2026)

Demandé par Mathieu : « Repasse chaque fonction et calcul. Il faut un audit intense de l'app et du site avant le release
officiel. » Ce fichier garde chaque trouvaille : **corrigé**, **à décider** (par Mathieu) ou **sans risque** (vu, laissé).
Les outils d'audit restent dans le dépôt et tournent avec la suite de tests.

## État des cinq passes

| Passe | État | Outil |
|---|---|---|
| 1. Les calculs d'argent | en cours (frais, taxes, mise max : faits ; bilan, breaks, gradation, change : à faire) | `tests/test_taxe_province.py` |
| 2. SlabIQ, Radar, chiffres du site | à faire | |
| 3. Chaque fonction du serveur | **fait** | `outils/audit_api.py`, `tests/test_audit_api.py` |
| 4. L'app écran par écran | à faire (le chemin de la personne d'Apple est fait : `vue/chemin.py`) | |
| 5. Le site | à faire (l'écran de connexion est fait) | |

## Passe 3 : chaque fonction du serveur (fait le 24 nov)

`outils/audit_api.py` appelle les **321 fonctions** de l'API comme l'app le fait (POST /api/…), sans réseau, par un compte
gratuit (le compte démo) et par personne (aucune session) : sans argument, avec des arguments plausibles, puis tordus (vide,
texte géant, négatif, dictionnaire, liste, HTML, SQL, chemin de fichier). 4 083 appels, 10 secondes.

| Vérifié | Résultat |
|---|---|
| Une fonction d'admin répond à un compte ordinaire | **0** |
| Une fonction répond sans session | **0** |
| Un champ réservé (valeur tirée des ventes eBay : médiane, comps, mise max…) sort pour un compte ordinaire | **0** (les 6 champs trouvés sont vides, faux ou nuls) |
| Le serveur tombe, ou renvoie autre chose qu'un message propre | **0** |

Trouvailles :

- **Corrigé.** Un appel avec le mauvais NOMBRE d'arguments (une vieille version de l'app gardée sur un téléphone, un appel
  fabriqué) finissait en « Erreur du serveur » et s'écrivait dans Admin › Erreurs : 461 cas sur 4 083. Le serveur répond
  maintenant « Demande invalide : mets l'app à jour » (code 400), sans rien écrire dans les erreurs.
- **Corrigé.** Trois messages faits pour l'utilisateur partaient en « Erreur du serveur : réessaie dans un instant » :
  « Logo invalide : une image PNG ou JPEG de moins de 300 Ko », « Scan trop lourd (40 Mo au plus) », « Réglage trop long ».
  Ils arrivent maintenant tels quels (`lockerroom.MessageClient`).
- **Corrigé.** `couts_depuis_achats` sans compte eBay relié : « Erreur du serveur » au lieu de « Compte eBay non connecté ».
- **Sans risque.** 557 appels avec le mauvais TYPE d'argument (un dictionnaire à la place d'un numéro, du texte à la place
  d'une liste…) finissent en « Erreur du serveur ». L'app n'envoie jamais ça ; rien ne fuit, rien ne tombe ; la limite de
  demandes par minute protège le journal. Laissé tel quel (100 fonctions à durcir une par une pour un gain nul à l'écran).

## Passe 1 : les calculs d'argent (en cours)

Faits vérifiés à la source le 24 nov 2026 :

- **eBay.ca, cartes de sport** (ebay.ca › Selling fees ; mise à jour des frais de mars 2025) : 13,25 % du total de la vente
  jusqu'à 7 500 $ (2,35 % au-delà), plus 0,30 $ par commande de 10 $ et moins, 0,40 $ au-dessus. Le pourcentage se calcule
  sur le total, port et taxe de l'acheteur compris.
- **Taxes de vente au Canada, 2026** (taxtips.ca, révisé le 28 août 2026) : AB 5 · BC 12 · MB 12 · NB 15 · NL 15 · NS 14 ·
  NT 5 · NU 5 · ON 13 · PE 15 · QC 14,975 · SK 11 · YT 5.

Trouvailles :

- **Corrigé.** La taxe d'un achat au Canada était celle du **Québec (14,975 %) pour tout le monde**. Le « Total » d'une carte du
  Radar était gonflé de près de 10 % pour un acheteur de l'Alberta, de 2 % pour un Ontarien. La taxe suit maintenant la
  province choisie (Profil › Mes préférences › Mes deals › J'achète depuis › Ma province). Sans province : le Québec, comme
  avant. Le chasseur de l'admin ne change pas.
- **Corrigé.** Le frais par commande d'eBay était toujours de 0,40 $ ; c'est 0,30 $ pour une commande de 10 $ et moins
  (`calcul.profit_vente`). Le profit d'une carte à 8 $ était 0,10 $ trop bas.
- **Sans risque.** Le réglage par défaut des frais (13,25 % + 0,40 $) est le bon tarif d'eBay.ca. Il ne compte pas la taxe de
  l'acheteur dans la base ; `frais_calibrer` corrige ça seul après 5 ventes (le pourcentage suit les frais vraiment facturés).
  La part de 2,35 % au-dessus de 7 500 $ n'est pas calculée (aucune carte de l'inventaire n'y est).
- **Sans risque.** Les constantes de la revente d'un deal (admin) : 14,9 % de (prix + port), port moyen 15 $, matériel 1,50 $,
  30 % de profit et 15 $ au moins. Identiques dans le serveur (`deals.py`) et dans l'app. Calibrées sur UNE vraie vente du
  7 nov : à revoir avec plus de ventes.
- **À décider.** Une carte des États-Unis montrée à un Canadien : le « Total » ajoute **49,7 %** tant que l'annonce n'a pas été
  relue chez eBay (frais d'importation). Ce chiffre vient d'UNE commande de Mathieu (8 nov 2026). Deux ou trois autres
  commandes le confirmeraient ou le corrigeraient (`LR_IMPORT_DEFAUT` dans Render, sans déployer).
- **Sans risque.** Tarifs de gradation PSA et TAG : relevés sur psacard.com le 19 nov 2026, datés à l'écran. À relire la
  veille du lancement.

## Vitesse (24 nov)

Voir NOTES_CLAUDE.md, « Vitesse du Radar » : trois correctifs et la ligne « Radar (temps) » du journal.
