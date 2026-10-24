# LockerRoom en ligne (Render, https)

Guide pas a pas du lancement : doc « LockerRoom — Guide de lancement » (24 oct 2026).

## Ce que Mathieu cree (comptes : personne d'autre ne peut le faire)
1. Un depot GitHub **prive** avec le contenu de ce dossier.
2. Un compte https://render.com : New > Blueprint > ce depot (render.yaml), puis les secrets.
3. Optionnel : un nom de domaine dans Settings > Custom Domains.

## Puis sur developer.ebay.com (application LockerRoom, cles Production)
- **Alerts & Notifications** > Marketplace Account Deletion : endpoint
  `https://<adresse>/ebay/suppression-compte` + le jeton `LOCKERROOM_EBAY_AVIS_JETON`
  (le meme dans Render et chez eBay ; 32 a 80 lettres, chiffres, _ ou -).
- **RuName** : Auth accepted URL = `https://<adresse>/api/ebay_retour`,
  Privacy Policy URL = `https://<adresse>/confidentialite`.

## Puis sur dashboard.stripe.com (mode test d'abord)
- Produit « LockerRoom Pro », prix recurrent mensuel -> son `price_...` dans `STRIPE_PRIX_PRO`.
- Webhook (payload **Snapshot**) : `https://<adresse>/stripe/webhook`, evenements
  `checkout.session.completed`, `customer.subscription.created`, `.updated`, `.deleted`
  -> son `whsec_...` dans `STRIPE_WEBHOOK_SECRET`.
- Portail client active (Settings > Billing > Customer portal).
- Cle secrete `sk_test_...` dans `STRIPE_CLE_SECRETE` (plus tard `sk_live_...`).

## Comment un client commence (zero configuration)
1. Il ouvre `https://<adresse>` -> **Se connecter avec eBay** (+ le code d'acces si la version est privee).
2. Page officielle d'eBay -> il accepte. Son compte LockerRoom est cree tout seul.
3. Ses annonces, ventes, frais reels et la sante de ses prix s'importent seuls.
4. Reglages > Mon forfait > **Passer a Pro** : page de paiement de Stripe ; le forfait
   change seulement quand Stripe le confirme (avis signe).

## Variables
| Variable | Role |
| --- | --- |
| LOCKERROOM_HEBERGE=1 | serveur de production, pas d'auto-redemarrage, erreurs masquees |
| LOCKERROOM_DONNEES=/data | base, cles et jetons sur le disque persistant |
| LOCKERROOM_CODE | code d'acces demande a l'ouverture (version privee) |
| LOCKERROOM_SECRET | signature du temoin de session (genere par Render) |
| LOCKERROOM_MULTI=1 | un dossier + une base par client, isoles |
| LOCKERROOM_CLE | chiffre les jetons eBay des clients (genere par Render, ne jamais la perdre) |
| LOCKERROOM_EBAY_ENV | `production` (vrais comptes) ou `sandbox` |
| LOCKERROOM_EBAY_APP_ID / CERT_ID / RUNAME | NOS cles eBay, jamais montrees aux clients |
| LOCKERROOM_EBAY_AVIS_JETON | jeton de l'avis de suppression de compte (adresse : celle de Render) |
| LOCKERROOM_EPN_CAMPID | n° de campagne eBay Partner Network de LockerRoom : tous les liens d'achat le portent |
| ANTHROPIC_API_KEY | reconnaissance photo : NOTRE cle, collee a la main dans Render |
| LR_VISION_PLAFOND_USD / LR_VISION_GRATUIT | plafond photo du serveur par mois / photos par mois d'un compte gratuit |
| STRIPE_CLE_SECRETE / STRIPE_PRIX_PRO / STRIPE_WEBHOOK_SECRET | abonnement Pro (paiements.py) |
