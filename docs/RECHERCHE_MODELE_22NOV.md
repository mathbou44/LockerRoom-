# Recherche du 22 nov 2026 : faire parler 1,15 million de ventes

But (Mathieu) : trouver un modèle qui donne un vrai avantage, en s'inspirant de la finance. Tout est mesuré sur la même
carte exacte, frais de revente compris (13,25 % + 0,40 $), sur plusieurs périodes. Les scripts sont dans `outils/recherche/`.

Données : export du 22 nov au soir (1 151 045 ventes, 523 765 de hockey après tri), les matchs LNH et les visites
Wikipedia de 604 joueurs (`slabiq_donnees.json.gz` du 12 nov).

## Ce qui est mesuré

| # | Idée de la finance | Ce qu'on a testé | Résultat | Solidité |
|---|---|---|---|---|
| 1 | Coûts de transaction | Acheter à la médiane, revendre 3 ou 6 mois plus tard | Perte nette médiane de 6 à 37 % selon l'âge de la carte | Forte : toutes les périodes |
| 2 | Nouvelles émissions (IPO) | Prix d'une carte selon son âge | Saison 2025-26 : −37 % en 6 mois, moins chère 95 % du temps | Une seule saison propre |
| 3 | Fournir la liquidité | Acheter sous la médiane des 90 jours | Carte de 12 mois et plus : positif seulement à −30 % et moins (2 à 4 % des ventes), +1 % gradée, +13 % brute | Moyenne |
| 4 | Momentum et retour | Indice par joueur, 1 à 3 mois | Pas de momentum ; une flambée de +37 % rend −5,6 % | Faible (50 joueurs) |
| 5 | Dérive après résultats | Forme du joueur ce mois, cartes 1 à 3 mois après | En feu : +2 à +5 %, en hausse 56-59 % ; en creux : −1 à −8 %, en hausse 36-43 % | Significatif (p de 0,001 à 0,012), petit échantillon |
| 6 | Étude d'événements | Pic de visites Wikipedia, prix avant et après | +15 % la semaine du pic, encore +8 à +9 % de 3 à 12 semaines après | Moyenne (150 événements lisibles) |
| 7 | Signal de vente | Carte à +20 % de sa normale, 2 mois après | A baissé 59 à 73 % du temps, hasard 40 à 45 % | Forte : 6 demi-années |

## Ce que ça veut dire

1. **Revendre vite ne paie pas.** Avec 13 % de frais, il faudrait un signal qui prédit +13 % en quelques mois. Aucun ne le
   fait. Le méga test le confirme : perte nette médiane de 11 à 28 % à chacune des 6 dates, à 3, 6 et 12 mois.
2. **« Acheter le creux » va dans le mauvais sens.** Les cartes d'un joueur en creux continuent de baisser pendant 1 à 3
   mois. Sur la glace, le creux se résorbe à moitié le mois suivant, mais les cartes ne suivent pas.
3. **Le marché réagit lentement aux bonnes nouvelles.** Un joueur en feu, ou une grosse nouvelle, fait monter ses cartes,
   et la hausse tient. Le meilleur cas mesuré : joueur en feu dont le prix n'a pas encore monté (+5,7 % en 2 mois, 33 cas).
4. **L'âge de la carte compte plus que tout.** Une recrue de l'année perd beaucoup sa première année. Après 12 mois, la
   carte tient son prix.
5. **Vendre se prédit, acheter non.** Une flambée de prix retombe ; un creux ne remonte pas.

## Le modèle proposé : SlabIQ Timing

Changer la promesse : pas « achète pour revendre », mais « achète au bon moment, vends au bon moment ». Celui qui achète
une carte qu'il veut garder ne paie pas les frais de revente : le timing seul lui fait économiser.

| Signal | Règle | Preuve aujourd'hui |
|---|---|---|
| Attends | Recrue de l'année, moins de 12 mois | Une saison (2025-26), à confirmer sur 2026-27 |
| Attends | Joueur en creux sur la glace | Dérive mesurée, p de 0,001 à 0,012 |
| Achète maintenant | Joueur en feu, prix pas encore monté | 33 cas : à confirmer |
| Vends | Carte à +20 % de sa normale | 6 demi-années |
| Vends tôt | Young Guns de moins de 60 jours | Banque YG (2 périodes) |

## Limites à dire clairement

- **Biais de survie.** Le méga test a cherché l'historique des cartes qui comptent aujourd'hui. Les vieilles ventes
  viennent donc surtout de cartes qui ont bien tenu. Les chiffres d'avant 2025 sont trop beaux.
- **Une seule saison propre** pour la courbe de vie (2025-26). La saison 2024-25 (Hutson, Celebrini) a monté, mais on n'y
  voit que 21 cartes, des survivantes.
- **Petits échantillons** pour la dérive (61 à 129 cas par groupe) et le momentum (50 joueurs).
- **Clé de carte très stricte** : 266 000 cartes, seulement 1 111 avec 20 ventes et plus. Une clé un peu plus souple
  donnerait plus de cas.
- Rien de ceci n'est encore dans l'app ni sur le site.

## Prochaines étapes

1. Refaire les tests 5 et 6 avec un export frais de `slabiq_donnees` (matchs jusqu'à aujourd'hui).
2. Assouplir la clé de carte pour tripler les cas, puis refaire les 7 tests.
3. Construire le score « Timing » (forme, âge de la carte, écart à la normale, nouvelle récente) et le tester avant / après
   comme SlabIQ : on garde seulement si c'est mieux, sur une période jamais vue.
4. Suivre la cohorte 2026-27 en direct pour confirmer la courbe de vie sans biais de survie.

## Recherche consultée

- Jegadeesh et Titman (1993), momentum sur 3 à 12 mois.
- Ritter (1991), sous-performance des nouvelles émissions sur 3 ans.
- Bernard et Thomas (1989), dérive après l'annonce des résultats.
- Dimson et Spaenjers (2014), objets de collection : rendements et coûts de transaction.
- Engelberg, Le et Williams (2018), anomalies boursières dans les cartes de baseball.

---

## Suite du 22 nov (soir) : le modele d'apprentissage « Timing »

Scripts : `outils/recherche/modele/` (jeu.py batit les donnees, entraine.py apprend en marchant, joueur.py regroupe par joueur, regles.py teste les declencheurs).

**Methode.** Une ligne = une carte exacte (meme grade) une semaine donnee, de mars 2025 a nov. 2026 : 131 237 lignes, 34 criteres
(mediane 30/90/365 j, EMA 7/30/90, moyenne 200 j, distance du haut et du bas, volume en part de marche, age de la carte, les AUTRES
cartes du joueur, forme 5 et 15 matchs contre sa base, jours sans match, pics Wikipedia, marche entier). Modele : arbres boostes
(LightGBM), entraine sur le passe, teste sur le mois suivant jamais vu, 12 mois de suite.

**Correction importante : le prix d'entree.** Avant, on comparait le prix futur au prix qui declenche le signal. Ce prix est bruite
(une vente chanceuse). Ici le prix d'achat ou de vente est la mediane des 14 jours APRES le signal. Consequence :
- « Carte a +20 % de sa normale = vends » : contre le prix du signal, plus bas 61 a 64 % du temps a 60 j (comme avant).
  Contre le prix reel des 14 jours suivants : 52 %. **Le signal de vente n'existe presque plus** : 14 jours apres, la carte a
  deja reperdu 10 %. La hausse etait surtout une vente chanceuse, pas un prix qu'on peut obtenir.
- Meme chose au niveau joueur (ses autres cartes a +20 % vs 91-365 j) : 51 %. Rien.
- A refaire sur la liste « A vendre » de l'app avant le lancement (pastille Sell, feuille de preuve, notification).

**Ce que le modele trouve (cas jamais vus, prix reel).**
- Il classe : correlation positive 11 mois sur 12 (30 j), 8 sur 10 au niveau joueur (60 j).
- Il trouve surtout ce qu'il faut EVITER : les 20 % du bas baissent de 5 % a 30 j et de 7 % a 60 j (en hausse 39 %).
  Au niveau joueur : -8,5 % a 60 j, en baisse 64 % du temps (184 joueur-semaines, 54 joueurs).
- Il ne trouve PAS d'achat qui monte : les 10 % du haut font 0 % (en hausse 50 %). Net de frais : -13 %.

**Declencheurs simples tires du modele (toutes les donnees, prix reel).**
| Regle | 30 j | 60 j | 90 j | Tient |
|---|---|---|---|---|
| ATTENDS : carte de moins de 10 mois + les autres cartes du joueur en baisse de 10 % | -6,3 % | -8,9 % | -9,8 % (hausse 29 %) | sous les autres 12 a 14 mois sur 14 a 16 ; 19 a 32 joueurs |
| ATTENDS : joueur en creux (5 matchs) + ses cartes en baisse sur 90 j | -3,9 % | -8,4 % | -11,7 % (hausse 25 %) | 10 a 13 mois sur 11 a 14 |
| ACHETE : joueur en feu (+0,3 pt/match), carte pas montee, carte de plus de 10 mois | +1,8 % | +3,4 % | +10,6 % (hausse 64 %) | au-dessus 13 mois sur 16, MAIS gains surtout d'aout 2025 a janv. 2026 ; faible depuis fevrier |
| ACHETE (paires) : les autres cartes du joueur ont monte de 10 %, celle-ci non | +0,9 % | +3,5 % | +5,8 % | 5 a 7 mois sur 7 a 10 |
| Pic Wikipedia, carte pas encore montee | -5,0 % | -2,4 % | -4,2 % | rien |
| Tendance haussiere du joueur (90 j + EMA) | 0 % | -0,2 % | -1,0 % | rien |
| Retour a la moyenne (carte a -20 %, joueur stable) | 0 % | +0,2 % | +2,4 % | rien de fiable |
| Saison morte (pas de match depuis 126 j) | -2,8 % | -5,9 % | +1,3 % | deux etes seulement, contradictoires |

Aucune regle ne bat les frais de 13 % en revente. La meilleure (en feu) finit a -4 % net a 90 j.

**Lecture.** La baisse a de l'elan (une carte jeune qui baisse continue de baisser), la hausse n'en a pas. Comme en bourse :
le momentum existe surtout du cote perdant, et le retour a la moyenne mesure sur des prix bruites est en bonne partie une illusion.

**Limites.** 80 % des lignes viennent d'aout a nov. 2026. Les regles « ATTENDS » reposent sur 19 a 39 joueurs. Semaines qui se
chevauchent : les cas ne sont pas independants. Forme et Wikipedia arretes au 12 nov. Pas d'historique d'abonnes Instagram.

### Grande recherche de regles (726 756 combinaisons)

`jeu2.py` : 70 criteres, chaque famille avec plusieurs fenetres (medianes 60/90/180/365 j, EMA 3/7/14/30/60/120, moyennes simples
60/120/200/365, hauts et bas 90/200/365, bandes de Bollinger, RSI sur 10 ventes, volume 14 et 30 j, forme 3/5/10/20 matchs, buts,
serie de points, Wikipedia 3/7/14/30 j, ecart carte contre joueur). `cherche.py` : toutes les paires de conditions x 6 seuils
x 3 ages de carte x 3 horizons. **On choisit sur le passe, on juge une seule fois sur la periode suivante.**

| Horizon | Regles essayees | 25 meilleurs ACHATS : passe -> jamais vu | 25 meilleurs ATTENDS : passe -> jamais vu |
|---|---|---|---|
| 30 j | 261 459 | +10,2 % -> -2,6 % (2 sur 25 tiennent) | -10,3 % -> -12,4 % (25 sur 25 tiennent) |
| 60 j | 262 713 | +15,9 % -> +0,9 % (mediane -5,7 %) | -13,0 % -> -5,7 % (19 sur 25) |
| 90 j | 202 584 | +26,3 % -> +2,2 % (mediane -3,8 %) | -18,6 % -> -2,3 % (18 sur 25) |

- **Aucune regle d'achat ne survit.** Les « meilleures » du passe (+10 a +26 %, en hausse 70 a 80 %) retombent a zero sur la
  periode suivante. C'est l'effet d'avoir cherche parmi des centaines de milliers : on trouve toujours du hasard qui a l'air d'une regle.
- **Une regle ATTENDS tient aux trois horizons, avec presque le meme chiffre avant et apres :**
  **carte de moins de 10 mois + ses ventes qui explosent (sa part du marche a triple et plus).**
  30 j : -8,8 % -> -11,8 % (558 cas, 60 joueurs, en hausse 28 %). 60 j : -15,5 % -> -16,7 % (252 cas, 22 joueurs, en hausse 24 %).
  90 j : -18,0 % -> -9,1 % (442 cas, 23 joueurs, en hausse 31 %). Avec les ventes du JOUEUR qui explosent aussi : -14,9 % a 30 j
  (122 cas, 18 joueurs, en hausse 25 %).
  Lecture : quand une carte neuve inonde le marche, le prix continue de tomber. C'est aussi un vrai signal de VENTE pour celui qui
  vient de l'ouvrir : vendre tout de suite plutot que dans 2 mois vaut 11 a 17 %. Mesure au prix reel, pas au prix du signal.
- Le modele d'apprentissage avec 70 criteres ne fait pas mieux qu'avec 34 (bas 20 % : -5,2 % a 30 j, -5,6 % a 60 j, -7,7 % a 90 j ;
  haut 20 % : 0 %). Plus de criteres n'ajoute rien : c'est la profondeur de l'historique qui manque, pas les variables.

---

## Le signal par joueur (v1) : un detecteur de cas branche sur les matchs

Decide avec Mathieu le 22 nov au soir : la promesse est « acheter et vendre au bon moment », pas « revendre avec profit apres frais ».

### 1. Deux fois plus de cas : la cle de carte canonique (`cle2.py`)
La cle stricte coupait la meme carte en dizaines de morceaux (la Young Guns de Demidov : 40 ecritures du titre). Avec le decodeur
de l'app (joueur, annee, numero, tirage, paralleles, auto, patch) : 270 596 « cartes » deviennent 178 838 ; les ventes utilisables
(cartes de 4 ventes et plus) passent de 174 674 a 294 477 ; les cas notes a 30 j de 21 100 a 43 773. Verifie : les morceaux
recolles ont la meme mediane de prix.

### 2. Les techniques de bourse sur l'indice du joueur (`jeu3.py`, `techniques.py`) : rien a l'achat
Indice causal pour 456 joueurs (chaque vente d'une carte deja vue donne le niveau du joueur). L'indice suit les vraies cartes
(correlation 0,55 a 30 j, 0,70 a 60 j). Regles testees au prix reel :
- Croix doree (EMA7 > EMA30 > EMA120) : -0,8 % a 30 j contre -1,8 % pour les autres. Pas de hausse.
- Prix au-dessus ou au-dessous de sa moyenne 200 j, elan 60 et 180 j, acceleration, MACD : rien de fiable.
- Seul le cote baisse parle : croix de la mort -3 a -4 % ; elan 180 j a -15 % : -5 % ; volume du joueur qui explose pendant que
  le prix baisse : -11 a -13 % a 60 et 90 j (-13 a -15 % sur ses vraies cartes).
- Apprentissage en marchant, 100 criteres : correlation hors echantillon +0,04 a +0,10. Un modele PAR CAS fait moins bien qu'un
  seul modele qui connait le cas (pas assez de donnees par cas).

### 3. La courbe de vie d'une carte (meme carte, prix reel)
| Age de la carte | 30 j | 60 j | 90 j |
|---|---|---|---|
| 0 a 5 mois | -3 a -6 % | -10 a -12 % | -15 % |
| 6 a 11 mois | -3 a -6 % | -6 a -10 % | -5 a -9 % |
| 12 a 14 mois | -1,7 % | -1,4 % | 0 % |
| 15 mois et plus | -2 a +2 % | -2 a +4 % | -2 a +3 % |
Une carte de l'annee (brute) a baisse a 60 j pendant 15 mois sur 15. Le plancher est vers 12 mois.

### 4. Ce qui fait bouger un joueur : les matchs, au jour pres (`evenements3.py` : LA MEME CARTE, 7 j avant contre apres)
| Evenement | Jour meme | Lendemain | Jours 8 a 30 | Jours 31 a 60 | Cas |
|---|---|---|---|---|---|
| Match de 0 point (temoin) | +1,4 % | -0,5 % | -0,1 % | -1,9 % | 731 |
| 2 points | 0 % | 0 % | +1,8 % | +1,5 % | 625 |
| Gros match (3 points+ ou 2 buts+) | -1,0 % | +4,5 % | +4,6 % | +5,9 % | 435, 165 joueurs |
| 2 buts et plus | +0,1 % | +5,9 % | +6,5 % | +10,2 % | 304 |
| Tour du chapeau | -1,0 % | +20,3 % | +14,1 % | +16,9 % | 35 a 56, 45 joueurs |
| Debut de sequence en feu | +1,9 % | +6,7 % | +5,9 % | +2,6 % | 227 |
| Panne de 4 matchs (0,5 pt/match+) | -3,1 % | -2,3 % | -3,2 % | -4,9 % | 170 |
| Nouvelle sans gros match (Wikipedia x3) | +0,9 % | +3,8 % | 0 % | 0 % | 320 |
- Le gros match tient sur les deux periodes : +5,6 % avant aout 2026, +6,8 % depuis (jours 31 a 60).
- Dose et effet : 0 point, 2 points, 3 points, 2 buts, tour du chapeau : la hausse grandit avec la performance.
- Le jour du match le prix n'a pas bouge ; le lendemain c'est fait. L'avantage est la vitesse.
- Recrue de l'annee (rejoue avec la vraie annee recrue, `rejoue.py`) : meme apres un gros match ses cartes baissent
  (-5,6 % sur les jours 8 a 60, 21 cas). Recrue en panne : -21 %, 21 cas, 17 joueurs.

### 5. Jumele a la cote SlabIQ (`evenements4.py`)
Apres un gros match ou une sequence en feu : les types de carte forts selon SlabIQ (Young Guns, auto, RPA ; note du type 88+) font
+6,8 % (jours 8 a 30) et +8,7 % (jours 31 a 60, en hausse 62 %) ; les cartes ordinaires -0,5 % et +3,6 %. Le signal dit QUAND,
SlabIQ dit QUELLE carte. (La lettre finale melange une photo de novembre : on se fie ici a la note du type de carte.)

### 6. Le signal v1 rejoue soir par soir (`signal_joueur.py`, `rejoue.py`)
3 207 signaux. Note : meme carte, 7 j avant contre jours 8 a 60. « Bon conseil » = le prix est alle du bon cote.
| Signal | Mediane | Bon conseil | Avant aout 2026 | Depuis | Cas |
|---|---|---|---|---|---|
| ACHETE (tous) | +6,2 % | 6,1 sur 10 | +7,3 %, 6,1 | +4,2 %, 6,2 | 657, 172 joueurs |
| ACHETE, cartes fortes SlabIQ | +8,4 % | 6,3 sur 10 | +9,5 %, 6,4 | +5,9 %, 6,0 | 576 |
| ACHETE, cartes ordinaires | +1,5 % | 5,2 sur 10 | +1,3 %, 5,0 | +1,7 %, 5,5 | 386 |
| ACHETE veteran, gros match | +5,8 % | 6,1 | +6,4 %, 6,0 | +4,6 %, 6,2 | 358 |
| ACHETE veteran, tour du chapeau | +11,8 % | 6,7 | +10,7 %, 6,1 | +14,7 %, 7,6 | 45 |
| ACHETE jeune, sequence en feu | +15,0 % | 7,6 | +22,4 %, 7,6 | trop peu | 42 |
| ATTENDS jeune en panne | -6,9 % | 7,0 | -5,4 %, 6,8 | -17,6 %, 7,5 | 53 |
| VENDS recrue en panne | -21,0 % | 8,6 | -16,0 %, 8,6 | trop peu | 21 |
| ACHETE veteran, sequence en feu | +1,2 % | 5,4 | | | 112 : a retirer |
| ATTENDS veteran en panne | -0,6 % | 5,0 | | | 128 : a retirer |
| VENDS nouvelle sans match | 0 % | 4,8 | | | 327 : a retirer |
Temoin (soir d'un match de 0 point) : le prix est plus haut ensuite 4,5 a 4,9 fois sur 10, mediane de -0,1 a -1,9 %.

### 7. La force du signal, apprise par un modele (`force.py`)
Appris sur les 441 ACHETE d'avant aout 2026, juge sur les 216 d'apres (jamais vus), criteres publics le soir meme :
| Tiers predit | Mediane (jours 8 a 60) | Bon conseil |
|---|---|---|
| Bas | +2,7 % | 5,6 sur 10 |
| Milieu | -0,7 % | 5,0 sur 10 |
| Haut (« signal fort ») | +15,8 % | 7,6 sur 10 |
(72 cas par tiers ; modele lineaire : +11,9 %, 7,1 sur 10.) Le critere qui pese le plus : le joueur etait DEJA chaud (5 points et plus
sur ses 5 matchs d'avant) : +10,1 % et 6,6 sur 10 avant, +6,9 % et 6,5 depuis. Un gros match isole apres une passe froide :
+3,2 % et 5,1 sur 10 avant, -3,9 % et 4,6 depuis.

### Limites
- Un an et demi d'historique, mince avant aout 2026 ; une seule saison complete. Les lignes de 20 a 60 cas sont a confirmer.
- Depuis aout 2026 : debut de saison seulement (les fenetres de 60 j sont coupees au 22 nov).
- Dates au jour pres : on ne sait pas a quelle heure la vente s'est faite. « Acheter le soir meme au prix d'avant » n'est pas prouve,
  seulement que le prix du jour du match n'a pas encore bouge.
- Meme le signal fort (+12 a +16 % brut) est a la limite des frais de 13 % : on ne promet pas de profit de revente.
- Retirer des regles apres avoir vu leur note embellit un peu le total : la vraie preuve sera le suivi en direct cette saison.


---

## 23 nov : le signal en direct (admin seulement)

Mathieu : « go ». `signal_joueurs.py`, Admin → Mesures → « Signal par joueur ».
- Chaque heure, le serveur lit les soirs de match manquants sur l'API publique de la LNH, reconnait le cas de chaque joueur suivi
  et ecrit le signal dans un journal qui ne se retouche pas. Aucun prix dans le declencheur.
- Regles gardees (v1.1) : gros match, tour du chapeau, jeune en feu = Achete (« fort » si le joueur etait deja chaud ou tour du
  chapeau) ; jeune en panne = Attends ; recrue en panne = Vends. Les regles retirees par la recherche sont notees en silence.
- Un cas de plus, vu le matin meme : **l'echange**. Dylan Larkin passe de Detroit a Montreal le 22 nov au soir. Arriver a Toronto ou
  Montreal = Achete (fort), en partir = Vends (etude du 14 nov : Kreider +143 %, Marchenko +161 %, Knies -50 %, Robertson -47 % ;
  4 cas). Le matin du 23, Larkin n'etait sur AUCUN alignement de la LNH : la detection lit maintenant les manchettes
  (`indice_joueurs.echange_par_nouvelles`), et l'alignement confirme ensuite. Larkin, Dach et Montembeault sont les premiers cas
  notes en direct.
- La note : une fois par jour, la meme carte, 7 jours avant contre jours 8 a 60 apres. « Direct » et « rattrapage » sont comptes a part.
- On le montre aux clients seulement quand il tient en direct.
- Le meme jour, « A vendre » est retire de l'app (pastille, notification, liste) : la preuve ne tenait que contre le prix du signal.
