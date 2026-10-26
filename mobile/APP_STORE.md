# SlabCoach sur l'App Store : le plan de la semaine

L'app iPhone est la même app que le site (elle charge l'app en ligne sur Render), avec en plus ce que l'iPhone
fait mieux :

- les annonces eBay s'ouvrent dans une fenêtre Safari intégrée ;
- le partage passe par le menu de l'iPhone ;
- une vibration légère confirme les actions ;
- un écran « Pas de connexion » apparaît avec un bouton Réessayer ;
- les alertes de prix arrivent en notification.

Chaque mise à jour du site met l'app à jour sans repasser par Apple. Il faut repasser par Apple seulement si on
change une partie native (icône, plugins, permissions).

**Rien ne s'achète dans l'app iPhone.** Au Canada, Apple interdit les boutons qui mènent à Stripe : le forfait Pro
se prend et se gère sur le site, et l'app reconnaît le compte Pro.

---

## Calendrier réaliste

| Jour | Toi | Résultat |
|---|---|---|
| ✅ Fait | Inscription Apple Developer (99 $ US) | Accepté |
| Aujourd'hui | Étapes 1 à 4 ci-dessous + compte Codemagic | Tout est prêt pour le 1er build |
| Mar–mer | Créer l'app dans App Store Connect + la clé API, lancer le 1er build | La version arrive dans TestFlight (≈ 30 min) |
| Mer | Tester sur ton iPhone avec TestFlight, prendre les vraies captures | Fiche complète |
| Jeu | Soumettre à Apple | Examen : souvent 24–48 h |
| Ven–sam | Corriger si Apple demande quelque chose, sinon publier | Dans l'App Store |

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
2. Fais 5 captures d'écran **sur ton iPhone**, avec tes vraies données : Accueil, Valeur / tendances, Breaks, Deals, Vendre. Les captures de `captures/` sont des brouillons faits avec des données de test, en 1320 × 2868.
3. Remplis la fiche ci-dessous, choisis la version dans **Build**, puis clique sur **Soumettre pour examen**.

---

## Fiche App Store (à copier)

**Nom :** SlabCoach
**Sous-titre (30 car.) :** Cartes de sport : prix et ventes
**Catégorie :** Sports (secondaire : Affaires)
**Âge :** 4+ (pas de jeu d'argent : les breaks sont analysés, rien ne s'achète dans l'app)

**Texte promotionnel :**
Le vrai prix de tes cartes, tiré des ventes eBay réelles, pas des prix demandés.

**Description (FR) :**
SlabCoach aide les collectionneurs, vendeurs et breakers de cartes de sport à acheter et vendre au bon prix.

- Valeur d'une carte : les ventes eBay réelles de la MÊME carte (même parallèle, même numérotation, gradée ou non), pas les prix demandés.
- Deals : les annonces bien sous ce que la carte se vend vraiment, avec les ventes comparables.
- Breaks : pour chaque joueur et chaque équipe, la chance de te faire rembourser et la valeur attendue, calculées sur la checklist et les cotes du fabricant. Tout est expliqué.
- Vendre : une photo, l'app lit la carte, trouve le bon prix et prépare ton annonce eBay.
- Inventaire et bilan : ton stock, tes coûts, ton profit réel.
- Alertes de prix : une notification quand LA carte que tu veux passe sous ton prix.
- Tendances et astuces : ce qui monte, ce qui baisse, et des astuces vérifiées pour tous les niveaux.

Connexion avec ton compte eBay (page officielle d'eBay, aucun mot de passe dans l'app). Rien n'est acheté ni vendu sans ton geste.

**Description (EN) :**
SlabCoach helps sports card collectors, sellers and breakers buy and sell at the right price.

- Card value: real eBay sales of the SAME card (same parallel, numbering, graded or raw), not asking prices.
- Deals: listings well below what the card actually sells for, with comparable sales.
- Breaks: for every player and team, your chance to get paid back and the expected value, from the manufacturer's checklist and odds. Everything is explained.
- Sell: one photo, the app reads the card, finds the right price and drafts your eBay listing.
- Inventory and report: your stock, costs and real profit.
- Price alerts: a notification when THE card you want drops under your price.
- Trends and tips: what's rising, what's falling, and verified tips for every level.

Sign in with your eBay account (eBay's official page, no password in the app). Nothing is bought or sold without your tap.

**Mots-clés (100 car.) :** cartes,hockey,eBay,prix,valeur,break,young guns,collection,vendre,comps,sports,LNH

**URL d'assistance :** l'adresse Render + `/conditions`
**URL de confidentialité :** l'adresse Render + `/confidentialite`

## Notes pour l'examen d'Apple (Review Notes, en anglais)
```
SlabCoach is a companion tool for eBay sports card sellers and collectors. Users sign in with their own eBay
account (eBay's official OAuth page) because the app reads and manages THEIR eBay listings and sales
(guideline 4.8: client for a specific third-party service).

Demo access (no eBay account needed): on the sign-in screen tap "Code de démonstration" and enter the code: <TON CODE>.
The demo account is a full Pro account with sample inventory.

No digital goods are sold in the app. The optional Pro plan is purchased and managed only on our website; the
iOS app contains no purchase buttons, prices or links to external payment (3.1.1 / 3.1.3).

Native features: price-alert push notifications, native share sheet, in-app Safari view for eBay listings,
camera / photo library to identify cards for a listing, haptics, offline screen.
Account deletion: Settings > Delete my SlabCoach account (5.1.1(v)).
Breaks: the app only analyzes odds of products the user buys elsewhere; no gambling or paid chance in the app.
```

## Confidentialité de l'app (App Store Connect > Confidentialité)
- **Données liées à l'utilisateur :** identifiant eBay (nom d'utilisateur), contenu de l'utilisateur (inventaire, photos de cartes envoyées pour la lecture), données d'achat (historique eBay importé).
- **Utilisation :** fonctionnement de l'app seulement. **Suivi publicitaire : non.**
- **Notifications :** jeton de l'appareil, gardé dans le compte, effacé avec le compte.

## À savoir
- **Connexion eBay avec Google :** Google bloque les connexions dans les apps intégrées. Ces utilisateurs entrent leur mot de passe eBay, ou utilisent « Mot de passe oublié » d'eBay.
- **Changer l'adresse de l'app :** il suffit de changer `LR_URL` dans Codemagic et de relancer un build.
- **Nouvelle version native :** relance un build dans Codemagic ; le numéro de build monte tout seul.
