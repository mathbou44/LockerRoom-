# SlabCoach · Guide : accrocher, faire acheter, faire rester

*Écrit le 20 nov 2026 à la demande de Mathieu (« l'utilisateur doit être rapidement hooké ; lis la doc sur le comportement
humain : app, achat, passion, impulsivité, et surtout le faire rester ; enregistre le tout pour le design, le hook et le
texte »). À relire avant tout nouvel écran, toute page du site, toute notification et tout texte.*

---

## 1. Ce que dit la recherche (le minimum à retenir)

### Les gens ne lisent pas, ils balaient
- 79 % des gens balaient une page, 16 % lisent mot à mot (Nielsen, 1997).
- Sur une page moyenne, on lit environ **20 %** des mots, au plus 28 % (Nielsen Norman Group, 2008).
- On lit la moitié du texte seulement quand la page a **111 mots ou moins**.
- Beaucoup lisent seulement la première phrase de chaque paragraphe : **une idée par bloc, l'idée en premier**.

### Un comportement = motivation + capacité + déclencheur, au même moment (Fogg, B=MAP)
- Si une action n'arrive pas, il en manque un des trois. Pas de déclencheur, pas d'action.
- Quand la motivation est faible, il faut que ce soit **très facile**.
- Une notification n'aide que si la motivation et la capacité sont déjà là. Sinon, c'est du bruit.

### La boucle de l'habitude (Eyal, *Hooked*) : déclencheur → action → récompense variable → investissement
- **Déclencheur** : externe (notification) au début, puis interne (l'envie : « je me demande ce que le Radar a trouvé »).
- **Action** : la plus simple possible.
- **Récompense variable** : on ne sait pas d'avance ce qu'on va trouver. C'est ce qui donne envie de revenir.
- **Investissement** : ce que la personne met dans l'app (sa collection, ses joueurs, ses réglages). Plus elle en met, plus
  elle revient, et meilleure l'app devient pour elle.

### La rétention se joue dans les premiers jours
- Médiane toutes catégories : ~25 % reviennent le jour 1, ~8 % au jour 7, ~4 % au jour 30 (UXCam / AppsFlyer, 2026).
- Il est courant de perdre 75 % des utilisateurs dès le jour 1 (Similarweb).
- **Jour 1 = la première session a-t-elle livré la valeur ? Jour 7 = l'habitude prend-elle ? Jour 30 = la valeur dure-t-elle ?**
- Ceux qui passent la première semaine ont beaucoup plus de chances d'être encore là au jour 30 (Braze).

### Les collectionneurs : compléter, contrôler, partager
- Compléter un set est une motivation en soi, pas seulement l'argent (Carey, *Journal of Economic Psychology*, 2008).
- On collectionne aussi pour **mettre de l'ordre et garder le contrôle**. L'envie augmente quand la structure de la
  collection est claire et qu'elle est **proche d'être complète** (Cao, Reimann, Brucks, *Journal of Consumer Research*, 2025).
- **Progrès offert (endowed progress)** : sur une carte de lave-auto, 34 % finissent si 2 tampons sur 10 sont déjà là, contre 19 %
  avec une carte de 8 cases vide, pour le même nombre d'achats (Nunes & Drèze, 2006).
- **Effet d'approche du but (goal gradient)** : plus on est près de la récompense, plus on accélère (Kivetz, Urminsky, Zheng, 2006).

### L'achat impulsif
- L'urgence, la rareté, l'émotion et la facilité poussent à acheter sans y penser. Ce sont les leviers de l'impulsivité.
- Après coup, un achat impulsif laisse souvent un conflit émotionnel (Frontiers in Psychology, 2021).
- Dans les forums, la douleur qui revient : **« mes dépenses m'ont échappé »**. L'impulsivité est déjà le problème de nos
  utilisateurs, pas un levier à pousser.

### Les séries (streaks) et la peur de perdre
- On craint plus de perdre que de gagner (Kahneman & Tversky). Une série de 30 jours est un trophée à défendre.
- Les bonnes séries pardonnent : le « gel » de Duolingo garde la série quand on manque une journée. La « marge de manœuvre »
  motive plus que des règles rigides (Duolingo, recherche UPenn/UCLA).
- Une série ne doit jamais culpabiliser.

### L'abonnement et l'essai
- Les essais longs convertissent mieux : 42,5 % (17 jours et plus) contre 25,5 % (4 jours ou moins) (RevenueCat, 2026).
  Notre essai de 14 jours est dans la bonne zone.

### Les notifications
- Une notification personnalisée peut quadrupler le taux d'ouverture. Une notification générique sur une app d'achat :
  ~2,5 % d'ouverture (Batch).
- Trop de notifications génériques mènent à la désactivation et à la désinstallation.
- Demander la permission après avoir montré la valeur, pas au premier écran.

### Les pièges interdits (dark patterns)
- La FTC les définit comme des designs qui poussent à des choix qu'on n'aurait pas faits et qui peuvent nuire.
  Exemples : annulation difficile, frais cachés, faux décomptes, renouvellement automatique caché.
- **SlabCoach n'en utilise aucun.** C'est aussi notre promesse (« Honnêtes ») et une exigence d'Apple.

---

## 2. Nos règles : ce qu'on fait chez SlabCoach

### A. L'accroche : la valeur en moins d'une minute
1. **Le premier écran promet UNE chose** : « Collectionne plus. Cherche moins. » Un titre, une phrase, un bouton.
2. **La valeur arrive avant toute question.** Connexion eBay → l'inventaire se remplit tout seul (annonces, ventes, achats).
   C'est notre moment « wow ». Le dire pendant le chargement : « On importe tout ton eBay… ».
3. **Sans eBay** : une photo de carte → SlabIQ dit laquelle c'est et sa lettre. La valeur en un geste.
4. **Moins de choix** : un seul bouton principal par écran. Plus il y a d'options, moins les gens agissent.
5. **Progrès offert** : la liste « Pour bien partir » commence déjà cochée à 1 ou 2 sur 5 (compte créé ✓, eBay relié ✓).

### B. Le texte : moins de mots, plus de reconnaissance
1. **Le test des 5 secondes** : qu'est-ce que c'est, pour qui, et quoi faire ? Si ce n'est pas clair en 5 secondes, couper.
2. **Une idée par bloc, l'idée en premier.** Titres de 3 à 6 mots. Tuiles : 2 à 6 mots.
3. **Une section du site = 110 mots au maximum.** Une fenêtre de l'app = 40 mots au maximum, hors données.
4. **Nommer la douleur dans les mots du collectionneur** (« Trop de parallèles »), puis la réponse en 5 mots
   (« Une photo : on te dit laquelle c'est »).
5. **Le ton est hobby, pas finance** : la passion, le temps, le plaisir, le set complété. On évite le profit, les comps et
   « l'argent durement gagné » en vitrine. Les chiffres de vente restent dans les outils, pour ceux qui les cherchent.
6. **Tutoiement, français d'ici**, phrases courtes, pas de jargon sans explication (débutant d'abord).
7. **Jamais un chiffre plus beau que la mesure** : les chiffres publics viennent de `iq_publie` (une seule source).

### C. Le design : léger à l'œil
1. **Beaucoup d'air**, des lignes fines plutôt que des boîtes partout, un seul accent de couleur par bloc.
2. **Le chiffre en gros, le contexte en petit** (comme un widget d'iPhone) : titre en haut, gros chiffre en bas.
3. **Une page tient dans l'écran** à l'ordi (fenêtre ~1465×694) : pas de défilement pour l'essentiel.
4. **Les graphiques racontent une seule chose** (ex. départ → 12 mois : une ligne monte, l'autre descend). Le détail est à un
   toucher (« Voir mois par mois »).
5. **Pastilles rondes, icônes en traits, pas d'emoji**, fenêtres au centre, fond flou, un X.

### D. La boucle qui fait revenir (Hook)
| Étape | Chez SlabCoach |
|---|---|
| Déclencheur externe | Une alerte **personnelle** : « La carte que tu guettes est sur eBay », « Ton joueur est en feu » |
| Déclencheur interne (le but) | « Je me demande ce que le Radar a trouvé ce matin » |
| Action simple | Ouvrir l'app : l'accueil montre tout de suite le nouveau, sans menu à fouiller |
| Récompense variable | Les trouvailles du Radar, le joueur en feu, l'astuce du jour, le trivia, une lettre qui monte |
| Investissement | Ajouter une carte, suivre un joueur, choisir un set à compléter, relier eBay : l'app devient **la sienne** |

### E. Faire rester (jour 1, jour 7, jour 30)
1. **Jour 1** : la première session doit livrer la valeur (l'inventaire rempli ou la première carte reconnue). Finir sur une
   promesse : « Demain matin, le Radar t'aura trouvé de nouvelles cartes ».
2. **Jour 2 à 7** : une seule notification utile par jour au maximum, personnelle (ses joueurs, ses sets). Jamais un « Tu nous
   manques » générique.
3. **La collection est un projet** : « Il te manque 3 cartes de ce set », avec une barre de progrès. On est près du but, on
   accélère.
4. **Les séries pardonnent** : trivia et visites. Un jour manqué n'efface pas tout (un gel par semaine). On ne culpabilise jamais.
5. **Montrer ce qu'on a manqué** : « Depuis ta dernière visite : 4 nouvelles cartes pour toi ».
6. **Le jour 30** : un bilan qui fait plaisir (ta collection, tes sets avancés, tes joueurs), pas un bilan financier en premier.

### F. Faire acheter (le Pro), honnêtement
1. **Montrer avant de vendre** : la personne voit ce que le Pro trouve (« SlabIQ a trouvé 12 cartes pour toi, tu en vois 3 »)
   avant le prix.
2. **Le prix ramené au quotidien** : « moins de 2 $ par semaine ». Comparé à une carte : « moins qu'une carte de base ».
3. **Un essai long et clair** : 14 jours, sans carte de crédit, et on dit quand il finit.
4. **Annuler en 2 touches.** Le renouvellement est toujours affiché.

### G. Ce qu'on ne fait jamais (éthique)
- Pas de faux décompte, de fausse rareté ni de « plus que 2 places » inventé.
- Pas de culpabilisation (« Tu vas manquer… », un hibou triste).
- **On ne pousse jamais à acheter des cartes sur un coup de tête.** Notre rôle est l'inverse : le budget du mois, la lettre
  SlabIQ, « attends » quand c'est la hype. Un collectionneur qui ne regrette pas ses achats reste.
- Pas de notification la nuit, ni plus d'une par jour sauf si la personne l'a demandé (alerte d'encan).
- Pas de jeu de hasard ni de « pack virtuel » payant.

---

## 3. Liste de vérification (avant de livrer un écran, une page ou un texte)
- [ ] On comprend en 5 secondes : quoi, pour qui, quoi faire.
- [ ] Un seul bouton principal.
- [ ] Moins de 110 mots (site) ou 40 mots (fenêtre de l'app).
- [ ] La première phrase de chaque bloc dit l'essentiel.
- [ ] Le ton est hobby (passion, temps, set), pas finance.
- [ ] Les chiffres viennent de la mesure (`iq_publie`), arrondis vers le bas.
- [ ] Ça tient dans l'écran (ordi 1465×694, cell 390×844).
- [ ] Il y a une raison de revenir (récompense variable ou progrès).
- [ ] Aucun piège : rien de faux, rien de caché, rien qui culpabilise.
- [ ] Pareil partout : site, app au cell, app à l'ordi, en français et en anglais.

---

## Sources
- Nielsen, *How Users Read on the Web* (1997) ; Nielsen Norman Group, *How Little Do Users Read?* (2008) — nngroup.com
- BJ Fogg, *Fogg Behavior Model* (B=MAP) — behaviormodel.org ; Stanford Behavior Design Lab
- Nir Eyal, *Hooked: How to Build Habit-Forming Products* (2014)
- UXCam, *Mobile App Retention Benchmarks* (2026, données AppsFlyer) ; Adjust ; Braze ; Similarweb
- C. Carey, *Modeling collecting behavior: the role of set completion*, Journal of Economic Psychology (2008)
- C. C. Cao, M. Reimann, M. Brucks, *Seeking Structure in Collections*, Journal of Consumer Research (2025)
- J. Nunes & X. Drèze, *The Endowed Progress Effect*, Journal of Consumer Research (2006)
- R. Kivetz, O. Urminsky, Y. Zheng, *The Goal-Gradient Hypothesis Resurrected*, Journal of Marketing Research (2006)
- *Past, Present, and Future of Impulse Buying Research Methods*, Frontiers in Psychology (2021)
- Duolingo, *How the streak builds habit* (blog) ; Yu-kai Chou, *Streak design*
- RevenueCat, *State of Subscription Apps 2026* et *How long should your free trial be?*
- Mastercard / Dynamic Yield, *Push notifications strategy* (données Batch, 2025)
- FTC, *Bringing Dark Patterns to Light* (2022)
- Forums de collectionneurs (Blowout Cards, Collectors Universe) et infolettres du hobby : les douleurs qui reviennent
