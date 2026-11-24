# SlabCoach sur l'App Store : le plan de la semaine

L'app iPhone est la même app que le site (elle charge l'app en ligne sur Render), avec en plus ce que l'iPhone
fait mieux :

- les annonces eBay s'ouvrent dans une fenêtre Safari intégrée ;
- le partage passe par le menu de l'iPhone ;
- une vibration légère confirme les actions ;
- un écran « Pas de connexion » apparaît avec un bouton Réessayer ;
- les alertes de prix arrivent en notification.

Le contenu (deals, valeurs, textes) se met à jour par le serveur. Toute NOUVELLE fonction importante se soumet à
Apple avec une nouvelle version (règle 2.5.2 : ne jamais écrire ailleurs que l'app change sans revue).

**Achats dans l'app iPhone : par Apple seulement.** Au Canada, Apple interdit les boutons, prix et liens qui mènent à
Stripe (l'app n'en montre aucun). Le Pro s'achète DANS l'app avec l'identifiant Apple (achat intégré, règle 3.1.3(b)) :
c'est construit, voir « Achat intégré » plus bas.

---

## Calendrier de la semaine du 23 novembre 2026

Rien n'est encore soumis à Apple (Mathieu, 23 nov au soir). Le lancement est le 1er décembre : voici le chemin le plus court.
L'app existe déjà dans App Store Connect (Apple ID 6827726629) et Codemagic est branché.

| Quand | Toi | Résultat |
|---|---|---|
| Mardi 24 | App Store Connect : accepter l'accord « Applications payantes » et remplir banque et taxes ; créer l'abonnement `com.slabcoach.app.pro.mensuel` (7,99 $ CA) ; régler l'adresse des avis du serveur | L'achat intégré peut être testé |
| Mardi 24 | Codemagic : « Start new build » › ios-app-store | La version arrive dans TestFlight (≈ 30 min) |
| Mercredi 25 | TestFlight sur ton iPhone : tester « S'abonner » puis « Restaurer mes achats » ; prendre les captures (voir plus bas) | Tout est vérifié sur un vrai iPhone |
| Mercredi 25 | Coller la fiche ci-dessous, joindre les captures, la note au réviseur avec ton code démo, choisir le build, **publication manuelle**, puis « Soumettre pour examen » | En examen |
| Du jeudi 26 au dimanche 29 | Répondre vite si Apple demande quelque chose | Long congé américain (Action de grâce le 26) : l'examen peut être plus lent |
| Lundi 30 | Si c'est approuvé : ne rien publier encore | Prêt |
| Mardi 1er décembre | « Publier cette version » | Dans l'App Store |

**Plan B, si Apple n'a pas approuvé le 1er décembre :** on lance quand même sur le web (www.slabcoach.com marche sur iPhone dans
Safari). L'app iPhone suit dès l'approbation. Un premier envoi avec abonnement est souvent refusé une fois : c'est normal, on corrige et on renvoie.

**À savoir :** dans l'app iPhone, le Pro est mensuel seulement (un seul produit chez Apple). L'annuel se vend sur le web ; un 2e
produit Apple (annuel) peut s'ajouter après le lancement.

L’inscription Apple est faite. Le Bundle ID est `com.slabcoach.app` : il ne pourra plus changer, le nom affiché (SlabCoach) oui. Si tu avais déjà créé `com.cardcoach.app`, laisse-le de côté : il ne sert à rien.

- **À ton nom (individuel) :** c'est le plus rapide, et l'App Store affichera ton nom comme vendeur.
- **Au nom d'une entreprise :** il faut un numéro D-U-N-S, ce qui peut prendre 1 à 2 semaines.

---

## Étape 1 · Apple Developer (aujourd'hui)
1. Va sur https://developer.apple.com/programs/enroll/ et connecte-toi avec ton identifiant Apple (active l'authentification à deux facteurs).
2. Choisis **Individual**, puis paie les 99 $ US.
3. Une fois accepté, va dans **Certificates, Identifiers & Profiles > Identifiers > +** :
   - type **App IDs > App**, description `SlabCoach`, Bundle ID **explicite** `com.slabcoach.app` ;
   - coche **Push Notifications** dans les capacités ;
   - clique sur Register.
4. Va dans **Keys > +** et crée la clé des notifications :
   - nom `SlabCoach APNs`, coche **Apple Push Notifications service (APNs)** ;
   - télécharge le fichier `.p8` (une seule fois possible) et note le **Key ID** et ton **Team ID** (en haut à droite).

## Étape 2 · App Store Connect
1. Sur https://appstoreconnect.apple.com, va dans **Apps > + > Nouvelle app** :
   - plateforme iOS, nom **SlabCoach** (si le nom est pris : « SlabCoach: Sports Card Comps ») ;
   - langue principale Français (Canada), Bundle ID `com.slabcoach.app`, SKU `slabcoach-ios`.
2. Dans **Infos de l'app**, note l'**Apple ID** (un numéro de 10 chiffres) : c'est `APP_STORE_APPLE_ID`.
3. Va dans **Utilisateurs et accès > Intégrations > Clés d'API App Store Connect > +** :
   - nom `Codemagic`, accès **Admin** ;
   - télécharge le fichier `.p8` et note l'**Issuer ID** et le **Key ID**.

## Étape 3 · Codemagic (compile l'app sur un Mac dans le nuage, sans Mac chez toi)
1. Crée un compte sur https://codemagic.io avec ton compte GitHub et ajoute ton dépôt GitHub (celui de l’app).
2. Va dans **Team settings > Integrations > Developer Portal > Manage keys > Add key** :
   - nom **`SlabCoach ASC`** (exactement ce nom) ;
   - colle l'Issuer ID et le Key ID, puis dépose le `.p8` de l'étape 2.
3. Va dans **Team settings > Code signing identities > iOS certificates > Generate certificate** et choisis Apple Distribution.
4. Dans l'app Codemagic, ouvre **Environment variables** et crée le groupe **`slabcoach`** :
   - `LR_URL` = l'adresse de ton app sur Render (ex. `https://lockerroom.onrender.com` (ou ton nouveau domaine), sans / à la fin) ;
   - `APP_STORE_APPLE_ID` = le numéro de l'étape 2.
5. Clique sur **Start new build** et choisis le workflow **ios-app-store**. Après environ 20 minutes, la version est dans TestFlight.

## Étape 4 · Render (notifications et compte de démo pour Apple)
Dans Render, ouvre **Environment** et ajoute :

| Variable | Valeur |
|---|---|
| `APNS_KEY_ID` | le Key ID de la clé APNs (étape 1) |
| `APNS_TEAM_ID` | ton Team ID |
| `APNS_KEY` | tout le contenu du fichier `.p8` APNs (de `-----BEGIN PRIVATE KEY-----` à `-----END PRIVATE KEY-----`) |
| `LOCKERROOM_DEMO_CODE` | un code que tu inventes, ex. `APPLE-LR-2026` (il sert à l'équipe d'Apple) |

Les clés restent dans Render, jamais dans GitHub.

## Étape 5 · Tester, captures, soumettre
1. Installe **TestFlight** sur ton iPhone. Tu y reçois SlabCoach, que tu testes avec ton vrai compte.
2. Fais 5 captures d'écran **sur ton iPhone**, avec tes vraies données : Accueil, Valeur / tendances, Breaks, Deals, Vendre. Les captures de `captures_brouillon/` sont de VIEUX brouillons (ancien logo) : ne pas les utiliser ; faits avec des données de test, en 1320 × 2868.
3. Remplis la fiche ci-dessous, choisis la version dans **Build**, puis clique sur **Soumettre pour examen**.

---

## Fiche App Store (à copier) · revue « comme Apple » du 27 oct 2026

> **Achat intégré (In-App Purchase) : construit le 27 oct 2026.** Le code est prêt (app + serveur). Il reste à créer
> l'abonnement chez Apple, une seule fois :
>
> 1. **App Store Connect › Accords, taxes et transactions bancaires** : accepte l'accord **Applications payantes**,
>    puis remplis les coordonnées bancaires et fiscales. Sans ça, l'achat ne marche pas, même en test.
> 2. **App Store Connect › ton app › Abonnements › +** : groupe **SlabCoach Pro**, puis un abonnement :
>    - Nom de référence : `SlabCoach Pro mensuel`
>    - **Identifiant du produit : `com.slabcoach.app.pro.mensuel`** (exactement : c'est ce que l'app demande)
>    - Durée : **1 mois** · Prix : **7,99 $ CA** (Apple calcule les autres pays)
>    - Localisation FR et EN : nom « SlabCoach Pro », description FR « Tout le Radar, annonces illimitées », EN « The full Radar and unlimited listings »
>      (23 nov 2026 : c'est ce que la feuille « Passe au Pro » de l'app montre aujourd'hui ; l'ancienne parlait de « valeurs » et de « deals »)
>    - Capture pour l'examen : la feuille « Passe au Pro » de l'app (fais-la dans TestFlight)
> 3. **App Store Connect › ton app › Infos de l'app › Avis du serveur App Store** (App Store Server Notifications),
>    **version 2**, pour la production ET le bac à sable :
>    `https://slabcoach.com/apple/notifications` (ou ton adresse Render + `/apple/notifications`).
> 4. **Codemagic** : relance un build (le plugin d'achat est ajouté dans `mobile/package.json`). Dans TestFlight,
>    l'achat est gratuit (bac à sable) : teste « S'abonner », puis « Restaurer mes achats ».
> 5. **Programme pour petites entreprises** (App Store Small Business Program) : la commission d'Apple passe de 30 % à 15 %.
>
> Rien à mettre dans Render : la vérification des achats utilise la racine publique d'Apple. Optionnel :
> `APPLE_IAP_PRODUIT` (autre identifiant de produit), `APPLE_IAP_SANDBOX=0` (refuser les achats de test, à éviter :
> l'équipe d'Apple teste avec des achats de test).
>
> **Dans la description App Store**, termine par la ligne (Apple l'exige pour un abonnement) :
> `Conditions d'utilisation : https://slabcoach.com/conditions · Confidentialité : https://slabcoach.com/confidentialite`

**Nom :** SlabCoach
**Sous-titre (30 car.) :** Cartes de hockey notées A+ à E
**Sous-titre EN (30 car.) :** Hockey cards rated A+ to E
**Catégorie :** Sports (secondaire : Style de vie)
**Âge :** réponds au questionnaire honnêtement. Jeux d'argent réels : *aucun* (aucune mise, aucun paiement, aucun prix
dans l'app). Mais l'app sert aussi aux breakers : ils y notent les places vendues ailleurs et font le TIRAGE des équipes.
Si le questionnaire demande « jeux de hasard simulés » ou « concours », lis bien la définition : ce n'est pas un jeu dans
l'app, mais ne cache pas les breaks. Accès Web sans restriction : *non* (seulement des annonces précises, dans une fenêtre
Safari intégrée). Contenu généré par les utilisateurs : *non*. Le résultat sera probablement 4+ ou 9+ : ne le force pas.

> **23 nov 2026 : fiche refaite pour l'app d'aujourd'hui.** L'ancienne (27 oct) promettait « le vrai prix de tes cartes, tiré
> des ventes réelles » et des « ventes comparables ». Le public ne voit plus aucun prix tiré d'eBay (règle de licence), et la
> promesse est « acheter et vendre au bon moment », avec le ton du hobby. Une fiche qui promet ce que l'app ne montre pas est
> un motif de refus chez Apple (règle 2.3.1). Les sept points suivent le guide « Que veux-tu faire ? » de l'app.

**Texte promotionnel (170 car.) :**
Collectionne plus. Cherche moins. Une lettre sur chaque carte, un Radar qui cherche pour toi, ta collection suivie toute seule.

**Texte promotionnel EN :**
Collect more. Search less. One letter on every card, a Radar that searches for you, your collection tracked on its own.

**Description (FR) :**
SlabCoach aide les collectionneurs de cartes de hockey à acheter et vendre au bon moment, sans passer leurs soirées à fouiller.

- SlabIQ : une lettre, de A+ à E, sur chaque carte. Est-ce qu'elle va se revendre, et garder sa valeur ? Touche la lettre pour voir pourquoi.
- Radar : dis-lui ce que tu collectionnes (joueurs, équipes, budget). Il cherche pour toi et te montre les meilleures cartes d'abord.
- Collection : tes cartes au même endroit, suivies toutes seules, avec ce qu'elles t'ont coûté et ton profit réel.
- Vendre en une photo : l'app lit la carte (avec ta permission) et prépare ton annonce.
- Tendances : les joueurs en hausse, en baisse, au plus bas et au plus haut. Des faits, pas des promesses.
- Breaks : ce que vaut ta place avant de payer, et tes chances d'avoir un hit selon la checklist et les cotes publiées par le fabricant.
- Alertes : une notification quand la carte que tu veux passe sous ton prix cible.

SlabIQ t'aide à choisir ; il ne garantit pas de gain.

Connexion avec Apple ou avec ton compte de vente en ligne (page officielle, aucun mot de passe dans l'app). Rien n'est acheté ni vendu sans ton geste.

Forfait Pro optionnel : abonnement mensuel renouvelé automatiquement, payé avec ton identifiant Apple, annulable en tout temps dans les Réglages de l'iPhone.
Conditions d'utilisation : https://slabcoach.com/conditions · Confidentialité : https://slabcoach.com/confidentialite

**Description (EN) :**
SlabCoach helps hockey card collectors buy and sell at the right time, without spending their evenings digging.

- SlabIQ: one letter, A+ to E, on every card. Will it resell, and hold its value? Tap the letter to see why.
- Radar: tell it what you collect (players, teams, budget). It searches for you and shows the best cards first.
- Collection: your cards in one place, tracked on their own, with what they cost you and your real profit.
- Sell in one photo: the app reads the card (with your permission) and drafts your listing.
- Trending: players rising, falling, at their lowest and at their highest. Facts, not promises.
- Breaks: what your spot is worth before you pay, and your odds of a hit from the manufacturer's checklist and published odds.
- Alerts: a notification when the card you want drops under your target price.

SlabIQ helps you choose; it does not guarantee a gain.

Sign in with Apple or with your marketplace account (official page, no password in the app). Nothing is bought or sold without your tap.

Optional Pro plan: monthly auto-renewing subscription, paid with your Apple ID, cancel anytime in iPhone Settings.
Terms of use: https://slabcoach.com/conditions · Privacy: https://slabcoach.com/confidentialite

> Pas de marque d'autrui dans le nom, le sous-titre ni les mots-clés (règles 2.3.7 et 5.2.1) : « eBay », « LNH »,
> « Young Guns », « Upper Deck » sont retirés des mots-clés. Dans la description, une mention descriptive reste
> possible, mais j'ai gardé « compte de vente en ligne » pour ne rien laisser croire à un partenariat.

**Mots-clés (100 car.) :** cartes,hockey,collection,recrue,radar,alerte,break,inventaire,vendre,sportives,gradation,rookie
**Mots-clés EN (100 car.) :** cards,hockey,collection,rookie,radar,alerts,break,inventory,sell,sports,grading,collector

**URL d'assistance :** https://slabcoach.com/support
**URL de confidentialité :** https://slabcoach.com/confidentialite
**URL marketing (facultatif) :** https://slabcoach.com

**Captures (23 nov 2026) :** à prendre sur TON iPhone, dans TestFlight, c'est le plus rapide (5 minutes). Les captures d'un
iPhone Pro Max ont la bonne taille (6,9 po). Avant : Profil › passe la vue à **Pro** (jamais « Admin » : Apple ne doit voir ni
les outils admin ni un prix tiré d'eBay). Six écrans, en français puis en anglais (Profil › langue) :
1. Accueil ; 2. Radar (tes cartes, avec la lettre SlabIQ) ; 3. la fenêtre SlabIQ d'une carte (touche la lettre) ;
4. Inventaire ; 5. Tendances ; 6. Breaks.
Ne plus utiliser `captures_v2/` (27 oct : ancien accueil, ancien Radar) ni `captures_brouillon/`.

## Notes pour l'examen d'Apple (Review Notes, en anglais)
23 nov 2026 : 1er paragraphe refait pour l'app d'aujourd'hui (plus de « real-sales card values ») ; le chemin du compte démo et celui de
l'achat intégré sont ceux de l'app d'aujourd'hui, refaits pas à pas sur un iPhone simulé (tests/test_demo_apple.py). 28 oct 2026 (audit) : compte démo GRATUIT (l'équipe d'Apple doit voir l'achat intégré), natif mis en avant, breaks
décrits honnêtement. Remplace <TON CODE> par la valeur de LOCKERROOM_DEMO_CODE (Render).
```
SlabCoach is a companion app for hockey card collectors. Every card gets a SlabIQ letter (A+ to E) that estimates how
well it resells and holds its value; a Radar surfaces listings that match the user's own targets (players, teams,
budget); the app also tracks the user's collection, drafts a listing from one photo, shows player trends and break
odds. SlabIQ helps users choose; the app promises no financial gain.

DEMO ACCOUNT: at the bottom of the sign-in screen, tap "Démo / Demo" and enter: <TON CODE>.
It is a FREE account (trial ended) with sample inventory, breaks and sales, so you can see the In-App Purchase.
No eBay account is needed.

IN-APP PURCHASE: SlabCoach Pro (auto-renewable subscription, monthly, product com.slabcoach.app.pro.mensuel).
Where to find it: Profile tab (bottom right) > tap the "GO PRO" badge under the name > "See Pro" ("Voir le Pro" in
French). Also: Profile > My account > My plan, and the "Pro" badges in the app. The sheet shows the
price, period, auto-renewal terms, Terms of Use, Privacy Policy and "Restore purchases". The app shows no other way
to pay and no external prices.

NATIVE FEATURES (beyond the web content):
- Live card scanner: the camera opens inside the app, guides the user (light, glare, angle), captures automatically
  when the card is sharp and straight, then crops and straightens the card into a clean "studio" photo.
- Push notifications for price alerts (opt-in, max 3 per day, none at night).
- In-App Purchase (StoreKit) with restore and subscription management.
- Sign in with Apple; Google and eBay sign-in run in SFSafariViewController (no password in the app).
- Native share sheet, haptics, in-app Safari view for listings, offline screen with retry.

PRIVACY: card photos are sent to a third-party AI (Anthropic) only after an explicit in-app permission ("Read the
card with AI?"), withdrawable in Settings. Support messages may be sorted by the same AI (stated in the form and in
the privacy policy). Promotional alerts (deals) are off until the user turns them on.

ACCOUNT DELETION: Profile > My account > "Help, sign out, delete account" > Delete my SlabCoach account (immediate;
Sign in with Apple tokens are revoked).

BREAKS: breakers use the app to price spots, record spots they sold on their own channels and run the random team
assignment. No payment, wager, bet or prize happens in the app.
```

## Confidentialité de l'app (App Store Connect › Confidentialité de l'app)
Suivi (tracking) : **Non**. Pour chaque type ci-dessous : *lié à l'utilisateur : oui*, *utilisé pour le suivi : non*,
*but : fonctionnalité de l'app*.

| Type de données (Apple) | Ce que c'est chez nous |
|---|---|
| Coordonnées › Nom, Adresse courriel | connexion Apple (ou Google sur le web) |
| Identifiants › Identifiant de l'utilisateur | identifiant Apple / eBay, compte SlabCoach |
| Achats › Historique d'achats | ventes et achats eBay importés, abonnement |
| Contenu utilisateur › Photos | photos de cartes (lecture par l'IA avec permission) |
| Contenu utilisateur › Autre contenu | inventaire, breaks, clients, dépenses |
| Diagnostic › Autres données de diagnostic | erreurs du serveur (pour corriger les bogues) |

Le jeton de notification n'est pas un « identifiant de l'appareil » au sens d'Apple. Aucune publicité, aucune analyse tierce.
