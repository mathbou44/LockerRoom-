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
