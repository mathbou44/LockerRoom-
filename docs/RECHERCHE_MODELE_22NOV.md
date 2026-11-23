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
