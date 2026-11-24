# Audit avant le lancement (commencé le 24 novembre 2026)

Demandé par Mathieu : « Repasse chaque fonction et calcul. Il faut un audit intense de l'app et du site avant le release
officiel. » Ce fichier garde chaque trouvaille : **corrigé**, **à décider** (par Mathieu) ou **sans risque** (vu, laissé).
Les outils d'audit restent dans le dépôt et tournent avec la suite de tests.

## État des cinq passes

| Passe | État | Outil |
|---|---|---|
| 1. Les calculs d'argent | en cours (frais, taxes, surtaxe des États-Unis, mise max : faits ; bilan, breaks, gradation, change : à faire) | `tests/test_taxe_province.py`, `tests/test_surtaxe_us.py` |
| 2. SlabIQ, Radar, chiffres du site | à faire | |
| 3. Chaque fonction du serveur | **fait** | `outils/audit_api.py`, `tests/test_audit_api.py` |
| 4. L'app écran par écran | commencé (le chemin de la personne d'Apple : `vue/chemin.py` ; la watchlist sans l'outil de prix : `tests/test_miser_sans_prix.py`) | |
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
- **Corrigé (24 nov, Mathieu : « ce sont les tarifs, on doit en tenir compte. Renseigne-toi »).** Une carte des États-Unis
  achetée par un Canadien. Vérifié aux sources officielles :
  - Tarif des douanes du Canada 2026, chapitre 49 : le numéro 4911.91.00.30 nomme les « cartes à collectionner » (baseball,
    hockey, football et similaires) ;
  - Finances Canada, liste en vigueur le 8 septembre 2026 (Décret de surtaxe visant les États-Unis (2026)) : 4911.91.00 = **50 %** ;
  - ASFC, Avis des douanes 26-23 : la surtaxe vise aussi les achats personnels, **sans montant minimum** ; elle se calcule sur la
    valeur de la marchandise (le prix, pas le port) ; la TPS se calcule sur la valeur + la surtaxe.

  La commande de Mathieu du 8 nov le confirme au cent : 53,09 $ = 50 % de 106,17 $ (le prix seul) ; 8,89 $ = 5 % de
  (106,17 + 18,58 + 53,09). C'est donc une surtaxe du **Canada** (sa réponse aux tarifs américains), pas un tarif des États-Unis.
  Avant : +49,7 % de (prix + port) pour toute carte hors Canada. Juste pour CETTE commande (port = 15 % du total), mais
  **8 points trop bas** pour une carte chère au port gratuit (+57,5 %) et **deux fois trop haut** pour une carte de 10 $ au
  port de 20 $ (6,75 $ de frais, pas 14,91 $). Maintenant : 50 % sur le prix seul, la taxe sur le tout (`deals.taxe_de`,
  `tests/test_surtaxe_us.py`). Un encan se juge à sa mise max, un prix fixe à son prix. La veille quotidienne suit le taux
  qu'eBay facture (`veille_ebay.calibrer_surtaxe`, 15 annonces relues) : si Ottawa change le taux, l'app suit seule.
- **Non mesuré (une seule commande, au Québec).** eBay y a perçu la TPS seule (5 %), pas la TVQ. Dans une province à TVH, la
  loi fait percevoir la TVH (13 à 15 %) : c'est ce que l'app compte. Une carte de 40 $ CA et moins par messagerie pourrait
  être exemptée de TPS (seuil de l'ACEUM) : non compté (écart de moins de 3 $). Une carte que le vendeur américain expédie
  lui-même (sans le programme d'eBay) : l'app compte les taxes d'un achat au Canada ; la surtaxe est due en droit, perçue ou
  non à la livraison.
- **Sans risque.** Un appel est en cours au Tribunal canadien du commerce extérieur (AP-2025-018, K. Wong, entendu le
  15 juin 2026) : les cartes à échanger devraient-elles échapper à la surtaxe ? Aucune décision trouvée le 24 nov. Si elle
  tombe : `LR_SURTAXE_US=0` dans Render, ou la veille suit seule.
- **Sans risque.** L'acheteur aux États-Unis d'une carte du Canada : l'app compte 15 % (estimé) tant qu'eBay ne donne pas
  ses frais ; la veille relit 8 annonces par jour avec un acheteur américain et suit ce qu'eBay facture.
- **Sans risque.** Tarifs de gradation PSA et TAG : relevés sur psacard.com le 19 nov 2026, datés à l'écran. À relire la
  veille du lancement.

## Vitesse (24 nov)

Voir NOTES_CLAUDE.md, « Vitesse du Radar » : trois correctifs et la ligne « Radar (temps) » du journal.

## Passe 4 : l'app écran par écran (commencée le 24 nov)

- **Corrigé (capture de Mathieu, vue Pro : « Ça me sort ça quand je veux bid in a batch »).** Watchlist › « Miser » et « Miser
  en lot » répondaient « Aucun encan à miser pour l'instant (fini, ou déjà au-dessus de ta mise max) » avec 5 encans en
  cours. Cause : depuis le 16 nov, un compte Gratuit ou Pro n'a plus de mise max conseillée (outil de prix réservé), et la
  préparation des mises sautait tout encan sans mise max. **Les deux boutons ne menaient nulle part pour tout compte
  Gratuit ou Pro, donc pour la personne d'Apple.** Maintenant : chaque encan en cours est préparé ; sans mise conseillée,
  la case attend le montant de l'utilisateur (en pâle : le minimum d'eBay) ; sa mise écrite est gardée et revient (« Ta
  mise » sur la carte). Aucune valeur ni mise conseillée ne sort pour autant (`tests/test_miser_sans_prix.py`).
- **Corrigé.** Dans la feuille de mise en anglais, les montants étaient écrits à la française (« 28 $ », « 62 $ US ») :
  maintenant « $28 », « US $62 ».
- **Corrigé.** En lot, une case encore vide avait un contour rouge (« sous le minimum d'eBay ») avant qu'on y écrive.
- **Corrigé (captures de Mathieu : « je ne devrais pas pouvoir bouger l'écran »).** Le Profil dépassait l'écran de 16 points
  sur son iPhone (430 × 932) et de 94 points sur un iPhone de 393 × 852 : il glissait pour rien. Quand il dépasse de peu, il
  se serre maintenant juste assez pour tenir (rangées de 58 à 50 points, jamais sous les 44 d'iOS). Mesuré avec les marges
  de l'iPhone (`vue/profil.py`) : 0 point de trop à 430 × 932, 393 × 852, 390 × 844 et 375 × 812 ; l'iPhone SE (375 × 667)
  défile comme avant (`tests/test_profil_tient.py`).
- **Corrigé (capture de Mathieu, Splendor : un crochet vert, puis « chances de tirage pas encore connues » : « ?? »).**
  Splendor n'a aucune cote publiée (« Random Inserts »), donc rien à classer dans « J'achète une place ». Mais c'est 1 carte
  par boîte et chaque carte est numérotée : les tirages imprimés donnent les chances (la part d'un sous-ensemble = ses
  exemplaires / tous les exemplaires). 96 sous-ensembles sur 96 ont maintenant une cote, leur somme fait 1 carte par boîte,
  200 joueurs se classent (Hellebuyck : 1 boîte sur 39). La règle ne joue que si AUCUNE cote n'est publiée et que 90 % des
  sous-ensembles sont numérotés : elle ne touche aucun des 25 autres produits (`catalogue._estimer_boite_numerotee`,
  `tests/test_boite_numerotee.py`). Un produit sans aucune cote ne porte plus le crochet vert (« Cotes à venir »).
- **Corrigé (Mathieu, vue Pro : « le bouton SlabIQ ne fonctionne pas »).** Dans le Radar, la pastille « SlabIQ ? », le
  « × SlabIQ » du titre et le « ? » n'étaient branchés qu'à la fin de la liste des deals (Admin, Platine) : **morts pour tout
  compte Gratuit ou Pro**. Ils sont branchés dès l'en-tête (`tests/test_radar_ios.py`).
- **Refait (Mathieu : « revoir le layout/design de My radar, c'est laid, ça brise l'expérience Apple »).** « Ton radar » est
  bâti comme Réglages d'iOS, avec les pièces de la feuille Filtres : quatre groupes arrondis, une rangée de 44 points par
  réglage (le nom à gauche, le choix en gris à droite), le budget dans le menu natif du téléphone, les deux alertes en
  interrupteurs (deux fenêtres de moins à ouvrir), « OK » en haut à droite. Chaque sous-fenêtre a le même cadre (Annuler |
  son nom | OK) ; Cartes et Budget sont des listes à cocher. Mesuré à 430 × 932 et 375 × 667, FR et EN : tout tient sans
  défiler, rien ne déborde (`vue/monradar.py`, `vue/monradar2.py`).
- **Corrigé (Mathieu, vue Pro : « pour les "to adjust" en Pro, t'utilises les ventes actuelles ? »).** Oui : la tuile « À
  ajuster » et la fiche d'une carte jugeaient encore un prix (« au-dessus du marché ») par la valeur gardée sur la carte, qui
  vient des ventes. **Un jugement de prix réservé (Admin, Platine) sortait en vue Pro.** Le garde-fou est maintenant à la
  source (`repere()` rend rien sans l'outil de prix ; aucune recherche de valeur non plus).
- **Changé (Mathieu : « To clear 186, c'est énorme ; sous 20 $ le clear fait du sens (consignation), au-dessus simplement revoir
  le prix »).** Une annonce sans intérêt (60 jours et plus sans suivi et peu vue, ou 90 jours et plus) : moins de 20 $ = « À
  liquider » ; 20 $ et plus = « À ajuster » (prix à revoir). Ces deux listes reposent sur les jours en ligne, les suivis et
  les vues de SES annonces, rien des ventes : permises à tous les forfaits. Une annonce populaire n'est plus jamais dans
  l'une ou l'autre (avant : 95 jours et 3 suivis = « populaire » ET « à liquider »). En Admin et Platine, « À ajuster »
  compte en plus les cartes au-dessus du marché (`lockerroom.popularite`, `tests/test_popularite.py`).
- **À faire.** Le balayage de chaque écran et feuille, vues Gratuit, Pro et Admin, FR et EN, 430 × 932, 393 × 852 et 375 × 667.
  L'iPhone de Mathieu fait 430 × 932 points (ses captures), pas 393 × 852.

## Vitesse : premières mesures en production (24 nov, 16 h 13, deux minutes après un déploiement)

| Vue | Total | Recherches eBay | Ventes (admin) | Pour moi et vérification | Le reste |
|---|---|---|---|---|---|
| Admin | 20,1 s | 7,5 s | 7,0 s | 3,5 s | 2,1 s |
| Admin (un 2e calcul, en même temps) | 20,2 s | 6,4 s | 7,5 s | 3,9 s | 2,4 s |
| Pro | 6,8 s | 2,1 s | (aucune) | 0,6 s | 4,1 s |

- Le calcul des scores n'est pas le problème (1,5 s pour 145 annonces).
- **Deux calculs identiques ont tourné en même temps** (même seconde de fin) : l'accueil et le Radar le demandent chacun.
  À faire : un seul calcul, le deuxième attend le résultat du premier.
- **« Ventes (admin) » : 7 s sur 20, pour l'admin seulement.** À faire : hors du calcul (en fond, gardé d'un Radar à l'autre).
- La recherche « petits tous » prend 5 à 6 s à elle seule.

