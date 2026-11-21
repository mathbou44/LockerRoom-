"""
SLABCOACH - le tableau de bord du CEO (16 nov 2026).

Mathieu : « pour le lancement officiel, comme admin et CEO, je dois avoir une page un peu a la Shopify ou je vois tous les
outils que mon app utilise, mes abonnes, les bugs, propositions, credits, tous mes abonnements, les couts associes, rappel
pour les taxes et autres responsabilites gouvernementales et financieres, securite du site ; ultra complete pour l'ordi,
le cell n'a pas besoin d'etre aussi puissant ; ajoute des choses que j'ai peut-etre manquees (pubs, affiliation, commandites) ».

Tout est calcule a la volee a partir de ce que le serveur sait deja (comptes, demandes, quotas, erreurs, sauvegarde). Ce que
seul Mathieu sait (le cout de chaque abonnement, ses dates de renouvellement, son statut d'entreprise, ce qui est fait dans
ses obligations) est garde dans admin_ceo.json, modifiable depuis la page. AUCUN secret n'est jamais renvoye : pour chaque
service, seulement « configure : oui / non ».

Les rappels fiscaux sont des reperes generaux pour un travailleur autonome au Quebec ; ils ne remplacent pas un comptable.
"""
import json
import os
import re
import threading
from datetime import date, datetime, timedelta

_verrou = threading.Lock()

# [cle, nom, role, categorie, variables d'environnement qui le configurent, lien du tableau de bord, cout connu par defaut]
SERVICES = [
    ("render", "Render", "Héberge le serveur et le site", "infra", ("RENDER_EXTERNAL_URL", "RENDER_GIT_COMMIT"), "https://dashboard.render.com", None),
    ("domaine", "Nom de domaine slabcoach.com", "L’adresse du site", "infra", (), None, None),
    ("github", "GitHub", "Le code et ses versions", "infra", (), "https://github.com", None),
    ("r2", "Cloudflare R2", "Sauvegarde de nuit des données", "infra", ("R2_BUCKET", "R2_ACCESS_KEY_ID"), "https://dash.cloudflare.com", None),
    ("codemagic", "Codemagic", "Compile l’app iPhone", "infra", (), "https://codemagic.io/apps", None),
    ("apple", "Apple Developer", "App Store, connexion Apple, notifications", "magasins", ("APPLE_BUNDLE_ID", "APNS_KEY_ID"), "https://developer.apple.com/account", {"montant": 99, "devise": "USD", "periode": "an"}),
    ("google", "Google (connexion)", "Se connecter avec Google", "magasins", ("GOOGLE_CLIENT_ID",), "https://console.cloud.google.com", None),
    ("stripe", "Stripe", "Paiements de l’abonnement sur le web", "paiements", ("STRIPE_CLE_SECRETE",), "https://dashboard.stripe.com", None),
    ("ebay", "eBay Developers", "Annonces, ventes, Radar (API)", "donnees", ("LOCKERROOM_EBAY_API",), "https://developer.ebay.com/my/keys", None),
    ("epn", "eBay Partner Network", "Commissions sur les achats faits par nos liens", "revenus", ("LOCKERROOM_EPN_CAMPID",), "https://partnernetwork.ebay.com", None),
    ("anthropic", "Anthropic (Claude)", "Lecture des photos, agent des demandes, conseils", "ia", ("ANTHROPIC_API_KEY",), "https://console.anthropic.com", None),
    ("soldcomps", "SoldComps", "Ventes comparables (comps)", "donnees", ("SOLDCOMPS_CLE",), None, None),
    ("compsniper", "CompSniper", "Ventes comparables (crédits)", "donnees", ("COMPSNIPER_CLE",), None, None),
    ("thecardapi", "TheCardAPI", "Moisson de ventes", "donnees", ("THECARDAPI_CLE",), None, None),
    ("highlightly", "Highlightly", "Faits des matchs (stats en direct)", "donnees", ("HIGHLIGHTLY_CLE",), None, None),
    ("cardsight", "CardSight", "Reconnaissance des cartes", "donnees", ("CARDSIGHT_CLE",), None, None),
    ("psa", "PSA", "Population et données de gradation", "donnees", ("PSA_JETON",), None, None),
]
CATEGORIES = {"infra": "Hébergement et code", "magasins": "Magasins d’apps et connexion", "paiements": "Paiements",
              "donnees": "Données et API", "ia": "Intelligence artificielle", "revenus": "Revenus"}

# Les obligations : [cle, titre, detail, categorie, frequence, quand (mois, jour) ou None]
OBLIGATIONS = [
    ("tps_tvq_seuil", "TPS/TVQ : surveiller le seuil de 30 000 $", "Au-delà de 30 000 $ de ventes taxables sur 4 trimestres de suite, l’inscription à la TPS et à la TVQ devient obligatoire. Les ventes via l’App Store : Apple perçoit les taxes. Les ventes web via Stripe : c’est à toi de les percevoir une fois inscrit.", "taxes", "continu", None),
    ("tps_tvq_declarations", "Déclarations TPS/TVQ (une fois inscrit)", "Selon la période choisie à l’inscription : annuelle, trimestrielle ou mensuelle.", "taxes", "selon inscription", None),
    ("impot_solde", "Payer le solde d’impôt de l’année", "Pour un travailleur autonome : le solde est dû le 30 avril, même si la déclaration peut être produite jusqu’au 15 juin.", "impots", "annuel", (4, 30)),
    ("impot_declaration", "Produire les déclarations de revenus (fédéral et Québec)", "Travailleur autonome : 15 juin. Revenus d’entreprise : T2125 (fédéral) et TP-80 (Québec).", "impots", "annuel", (6, 15)),
    ("acomptes", "Acomptes provisionnels", "Obligatoires si l’impôt à payer dépasse 1 800 $ (Québec) cette année et une des deux précédentes. Dates : 15 mars, 15 juin, 15 septembre, 15 décembre.", "impots", "trimestriel", "acomptes"),
    ("registres", "Garder les pièces et registres 6 ans", "Factures des abonnements (Render, Apple, Stripe…), relevés Stripe et Apple, dépenses. Exigé par l’ARC et Revenu Québec.", "comptabilite", "continu", None),
    ("tenue_livres", "Tenue de livres du mois", "Revenus Stripe et Apple, dépenses de chaque service, taux de change pour les dépenses en $ US.", "comptabilite", "mensuel", "mensuel"),
    ("req", "Registraire des entreprises (NEQ)", "Si l’entreprise est immatriculée : déclaration de mise à jour annuelle.", "gouvernement", "annuel", None),
    ("loi25", "Loi 25 : protection des renseignements personnels", "Responsable désigné (fait : dans la politique), registre des incidents de confidentialité, évaluation des facteurs relatifs à la vie privée avant un nouveau fournisseur hors Québec.", "gouvernement", "continu", None),
    ("marque", "Protéger la marque SlabCoach", "Une demande d’enregistrement à l’OPIC protège le nom au Canada (aujourd’hui : ™, non enregistrée).", "gouvernement", "une fois", None),
    ("assurance", "Assurance responsabilité professionnelle", "Couvre une réclamation d’un utilisateur (ex. une valeur estimée contestée).", "finances", "annuel", None),
    ("compte_affaires", "Compte bancaire séparé pour l’entreprise", "Stripe et Apple versent sur ce compte ; toutes les dépenses en sortent : la comptabilité devient simple.", "finances", "une fois", None),
    ("apple_renouv", "Renouveler Apple Developer", "99 $ US par an : si l’adhésion expire, l’app disparaît de l’App Store.", "renouvellements", "annuel", "apple"),
    ("domaine_renouv", "Renouveler le nom de domaine", "Activer le renouvellement automatique chez le registraire.", "renouvellements", "annuel", "domaine"),
    ("ebay_conformite", "eBay : conformité de l’API", "Avis de suppression de compte (actif), respect des limites d’appels, revue annuelle des conditions du programme développeur.", "gouvernement", "annuel", None),
]
OBL_CATEGORIES = {"taxes": "Taxes de vente", "impots": "Impôts", "comptabilite": "Comptabilité", "gouvernement": "Lois et gouvernement",
                  "finances": "Finances", "renouvellements": "Renouvellements"}

# Idees de revenus en plus (le front les affiche ; le serveur dit seulement ce qui est deja branche)
OPPORTUNITES = [
    ("platine", "Version Platine (comps)", "Ta vue admin devient un forfait payant plus cher : valeurs tirées des ventes, prix calculés, deals avec mise max. Déjà prête : il suffit d'une licence commerciale des ventes (ou de l'accord écrit d'eBay), puis LR_PLATINE=1 dans Render.", "revenus"),
    ("epn", "Affiliation eBay (eBay Partner Network)", "Chaque achat fait par un lien du Radar peut rapporter une commission à SlabCoach, sans rien coûter à l’acheteur. Déjà branché dans l’app : il faut seulement l’identifiant de campagne. À dire clairement aux utilisateurs (lien affilié).", "affiliation"),
    ("parrainage", "Parrainage", "Un mois de Pro offert à celui qui invite et à celui qui s’inscrit. Le coût est faible et chaque collectionneur connaît d’autres collectionneurs.", "croissance"),
    ("boutiques", "Forfait Boutique", "Les fonctions boutique (comptoir, rachats, consignation, rapport de taxes) valent plus que 7,99 $ pour un commerce : un forfait à part, plus cher.", "revenus"),
    ("commandites", "Commandites claires", "Une boutique locale, un breaker ou un salon de cartes mis en vedette, toujours identifié « commandité ». Attention : la politique et le site disent « aucune publicité » ; une commandite demanderait de mettre ces textes à jour.", "revenus"),
    ("createurs", "Créateurs de contenu", "YouTubeurs et streamers de breaks : un code promo à eux (ex. 1 mois offert) et une commission sur les abonnements qu’ils amènent.", "croissance"),
    ("salons", "Salons et boutiques du Québec", "Une affiche avec code QR au comptoir des boutiques partenaires et aux salons de cartes ; essai prolongé pour ceux qui scannent.", "croissance"),
    ("annuel", "Abonnement annuel", "Un prix à l’année (ex. 2 mois gratuits) garde les abonnés plus longtemps et donne de l’argent d’avance.", "revenus"),
    ("donnees", "Rapports de marché (sans données personnelles)", "Des tendances agrégées (joueurs en hausse, produits qui baissent) vendues aux boutiques ou publiées comme vitrine. Jamais de données d’utilisateurs.", "revenus"),
]


# 16 nov 2026 (Mathieu : « la liste des choses a faire dans mon tableau d'admin CEO ; ca doit devenir mon outil de travail ») :
# ses taches a lui (titre, note, echeance, priorite 1-4, projet, etat), melees aux alertes dans « Aujourd'hui ». Le projet
# « Licences de donnees » est seme une fois : chaque demande a son courriel pret a copier (modele) et son contact.
PRIOS = (1, 2, 3, 4)                       # 1 urgent, 2 bientot, 3 a faire, 4 quand tu peux
ETATS = ("a_faire", "en_cours", "attente", "fait")
SEMIS = {
    "licences": [
        ("lic_hci", "Demander la licence commerciale à Hobby Card Index", "Commercial Data License : ventes réelles (hockey), affichage public dans une app payante, entraînement de modèles, Canada. Plan Enterprise 49,99 $/mois + licence à négocier.", 2, "hci", "https://www.hobbycardindex.com/developers"),
        ("lic_tca", "Demander la licence commerciale à The Card API", "Déjà branchée chez nous : passer en Enterprise avec droits d'affichage public, d'entraînement et Canada.", 2, "tca", "https://www.thecardapi.com/trading-card-api"),
        ("lic_ch", "Demander la licence commerciale à Card Hedge", "40 M ventes/semaine, toutes gradations, hockey. support@cardhedger.com", 2, "ch", "https://ai.cardhedger.com/api-services"),
        ("lic_hl", "Confirmer l'usage commercial avec Highlightly (stats LNH)", "La licence commerciale n'est pas affichée sur leur site : la confirmer par écrit pour l'app payante.", 3, "hl", "https://highlightly.net"),
        ("lic_ebay", "eBay : accès Marketplace Insights + accord écrit pour l'outil de prix", "Licence API eBay : §8.5.3 (outil de prix sur accord écrit), §9.5 (modéliser des prix), §9.10 (entraînement interdit). Ticket au support développeur.", 3, "ebay", "https://developer.ebay.com/support"),
        ("lic_cl", "Collectors / Card Ladder : demande de partenariat de données", "La donnée qu'eBay utilise dans son propre guide de prix. Long, mais la source la plus solide.", 3, "cl", "https://www.cardladder.com/about"),
        ("lic_avocat", "Faire valider la licence choisie par un avocat avant de signer", "Points à vérifier : affichage public, entraînement de modèles, Canada, résiliation, données gardées après la fin.", 3, None, None),
        ("lic_platine", "Après la signature : brancher le fournisseur et ouvrir Platine", "Claude branche la nouvelle source (1-2 jours), puis : prix du forfait Platine, produit Stripe/Apple, LR_PLATINE=1 dans Render.", 4, None, None),
    ],
}
# 18 nov 2026 (Mathieu : « revoir la liste des choses a faire pour etre sur qu'on est a jour ») : ce qui reste a faire de son
# cote apres les travaux des 17-18 nov
SEMIS["suivi"] = [
    ("sv_pousser", "Pousser les dernières versions (v84 à v95), puis « Valider maintenant »", "GitHub Desktop → Push. Ensuite : Entraîner SlabIQ → Valider maintenant (lettres, audit Pro, questions).", 1, None, None),
    ("sv_stripe_annuel", "Stripe : créer le prix annuel (5,99 $/mois, 12 mois)", "Puis STRIPE_PRIX_PRO_ANNUEL dans Render et le lien des conditions (frais d'annulation).", 2, None, "https://dashboard.stripe.com/products"),
    ("sv_soldcomps", "SoldComps : renouveler ou changer de plan", "Les crédits du blitz finissaient le 18 nov. Sans crédits : moins de comps récentes (règle des 45 jours).", 2, None, None),
    ("sv_aikido", "Aikido : marquer lightgbm « Ignore »", "Aucune version corrigée n'existe ; le reste est réglé.", 3, None, None),
    ("sv_recadrage", "Vérifier le recadrage photo sur une vraie carte (ex. Demidov holo)", "4 mm nets sur chaque côté : la carte ne doit plus être coupée.", 3, None, None),
    ("sv_defi", "Jouer le défi SlabIQ 2-3 fois au cell", "Page /slabiq : fluidité, lisibilité, bouton « Rejouer ».", 3, None, None),
    ("sv_baseball", "Vérifier que le blitz baseball se remplit", "Entraîner SlabIQ → bandeau du blitz : des ventes de baseball doivent apparaître.", 3, None, None),
]
# 19 nov 2026 (Mathieu : « aller chercher les encheres de Fanatics Collect aussi ») : leurs conditions interdisent l'extraction
# de leurs donnees ; on leur demande une entente. Un 2e semis (le 1er des licences est deja fait) range dans « Licences ».
SEMIS["licences_fc"] = [
    ("lic_fc", "Demander à Fanatics Collect une entente pour montrer leurs enchères", "Leurs conditions interdisent d'extraire leurs données : il faut leur accord écrit (API ou flux des lots Weekly et Premier, affichage dans l'app, affiliation). En attendant : un bouton « Fanatics Collect » ouvre leurs enchères de la semaine.", 2, "fc", "https://help.fanaticscollect.com/hc/en-us/articles/18437607549853-Contact-Us"),
]
# 21 nov 2026 (Mathieu : « les priorites et choses a faire devraient toujours etre dans la to-do de la page admin ») : la liste
# du lancement du 1er decembre (docs/PRIORITES_LANCEMENT.md), une tache par point. 7e element (facultatif) : l'echeance.
# REGLE : toute nouvelle priorite ou chose a faire va ICI (un nouveau semis), pas seulement dans un document.
SEMIS["lancement_1dec"] = [
    ("l1_pousser", "Pousser la version du 21 nov et attendre « live » sur Render", "GitHub Desktop → Commit → Push. Inclut : notes App Store sur le site, autos B+ dans SlabIQ, Vendre sur un écran.", 1, None, None, "2026-11-21"),
    ("l1_apple", "Soumettre l'app à Apple", "Build Codemagic (vérifier qu'il passe : il contient la fenêtre de note d'Apple), captures, fiche App Store, note au réviseur avec le code démo. Pas de « Bêta » visible.", 1, None, "https://appstoreconnect.apple.com", "2026-11-22"),
    ("l1_parcours", "Tester le parcours d'un nouveau compte au cell", "Inscription → Pour bien partir → relier eBay → 1re carte → Radar → Breaks → essai Pro. Noter tout ce qui accroche ; Claude corrige en direct.", 1, None, None, "2026-11-22"),
    ("l1_stripe_id", "Stripe : finir la vérification d'identité", "Sans elle, pas de paiements le 1er décembre. Le prix annuel est dans la tâche « Stripe : créer le prix annuel ».", 1, None, "https://dashboard.stripe.com", "2026-11-25"),
    ("l1_paiement", "Faire un vrai paiement test de bout en bout", "Essai 14 jours → Pro → annulation → remboursement. Après la vérification Stripe.", 1, None, None, "2026-11-27"),
    ("l2_cloudflare", "Cloudflare : 2FA, HSTS et DMARC", "2FA sur le compte ; HSTS dans Edge Certificates ; DMARC p=none. Ne pas activer Bot Fight Mode (bloque Stripe, Apple, eBay).", 2, None, "https://dash.cloudflare.com", "2026-11-28"),
    ("l2_aikido_scan", "Aikido : relancer le scan après le push", "Ignorer avec la raison : lightgbm, liste IP GitHub, CSP. Envoyer à Claude ce qui reste.", 2, None, None, "2026-11-24"),
    ("l2_courriels", "Courriels de licence (7, dont Fanatics) : choisir l'adresse d'envoi", "Claude prépare les brouillons dans Gmail ; tu dis « envoie » pour chacun.", 2, None, None, "2026-11-26"),
    ("l2_demo", "Après l'approbation d'Apple : retirer le code démo", "Conseil dans la section Sécurité.", 2, None, None, None),
    ("l2_c_2comptes", "Claude : test 2 comptes sur tous les écrans", "Personne ne doit voir les données d'un autre compte.", 2, None, None, "2026-11-26"),
    ("l2_c_fenetres", "Claude : Bilan vide et page joueur sans données", "Les 2 dernières fenêtres à passer « Apple ».", 3, None, None, "2026-11-27"),
    ("l2_c_nouv", "Claude : Nouveautés à jour la veille du lancement", "Règle : après chaque grosse mise à jour.", 2, None, None, "2026-11-30"),
    ("d_vitrine", "Décider : supprimer ui/vitrine.html ?", "Pas servie, dit encore « 9/10 ».", 3, None, None, None),
    ("d_cadence", "Décider : « réentraîné plusieurs fois par semaine » ?", "Le site dit « chaque semaine » ; c'est aux 3 jours.", 3, None, None, None),
    ("d_noncartes", "Décider : refuser les non-cartes aussi à l'ajout manuel ?", "Aujourd'hui, seul l'import automatique les écarte.", 3, None, None, None),
    ("d_baseball", "Décider : baseball le 1er décembre ou après ?", "Budget SoldComps / TheCardAPI.", 3, None, None, None),
    ("d_ygr", "Décider : YG Renewed à D ou à B ?", "Le marché la place à B. B : accord 80,5 % au lieu de 80,3 %, le reste ne bouge pas.", 3, None, None, None),
    ("d_asc", "Décider : clé App Store Connect pour les téléchargements ?", "Apple ne publie pas ce chiffre. Clé API (rôle « Sales ») dans Render ; en attendant, le site montre « X+ collectionneurs ».", 4, None, None, None),
    ("ap_baseball", "Après le lancement : la version baseball", "La même app que le hockey, page par page, avec nos données de baseball.", 4, None, None, None),
]
# 21 nov 2026 (Mathieu : « un pare-feu pour empecher un hacker de ne pas payer ou d'aller chercher mon data ») : le pare-feu
# Cloudflare devant le site, et Render qui refuse tout ce qui ne passe pas par lui (server.py, LR_ORIGINE_*)
SEMIS["securite_21nov"] = [
    ("s_cf_proxy", "Cloudflare : www.slabcoach.com et slabcoach.com en orange (proxied)", "DNS → les 2 lignes doivent avoir le nuage orange. Gris = le pare-feu ne voit rien passer.", 1, None, "https://dash.cloudflare.com", "2026-11-24"),
    ("s_cf_waf", "Cloudflare : pare-feu (règles gérées) + limite de débit", "Security → WAF → Managed rules : activer le Free Managed Ruleset. Rate limiting rules (1 règle gratuite) : chemin commence par /auth/ ou /connexion, 20 requêtes / 10 s par IP → Block. Ne pas activer Bot Fight Mode (bloque Stripe, Apple, eBay).", 1, None, "https://dash.cloudflare.com", "2026-11-24"),
    ("s_origine", "Verrouiller Render derrière Cloudflare (3 étapes, dans l'ordre)", "1) Cloudflare → Rules → Transform Rules → Modify Request Header : ajouter X-SC-Origine = un long secret (gestionnaire de mots de passe, 32+ caractères), pour tout le trafic. 2) Render → LR_ORIGINE_JETON = le même secret ; ouvrir https://www.slabcoach.com/sante/cloudflare → doit dire « oui ». 3) Render → LR_ORIGINE_BLOQUER = 1. Si le site tombe : enlever LR_ORIGINE_BLOQUER. Ne jamais écrire le secret dans le chat.", 1, None, None, "2026-11-25"),
]
SEMIS["matin_21nov"] = [
    ("m_bfm", "Cloudflare : archiver l'alerte « Bot Fight Mode » (ne pas l'activer)", "Il peut bloquer les avis automatiques de Stripe, d'Apple et d'eBay. Bouton « Archive insight ».", 2, None, "https://dash.cloudflare.com", "2026-11-24"),
    ("m_mot", "Valider ton mot de fondateur sur l'accueil du site", "« Comme un conseiller financier. Mais pour tes cartes. » + la petite note « pas des conseils financiers ». Dis à Claude si tu veux changer un mot.", 3, None, "https://www.slabcoach.com/#mot", None),
    ("m_poe", "Vérifier une Program of Excellence dans le Radar après le push", "Ex. la Celebrini « Young Guns Canvas POE » : elle doit se comparer aux POE (60 à 100 $), plus aux Young Guns Canvas.", 2, None, None, "2026-11-22"),
]
# 21 nov 2026 (Mathieu : « il me reste quoi a faire pour rendre mon site, les donnees des utilisateurs et mes donnees
# inviolables ? ») : ce qui reste, par ordre de risque reel. Le plus grand risque n'est pas le code : c'est un de TES comptes vole.
SEMIS["securite_reste"] = [
    ("sr_2fa", "Activer la 2FA sur TOUS les comptes qui tiennent les clés", "Le risque no 1 : un compte volé donne tout. Avec une app d'authentification (pas le SMS) : GitHub, Render, Cloudflare, Stripe, Apple (développeur), eBay (développeur et vendeur), Google (ton Gmail), le registraire du domaine, Codemagic, Anthropic. Garde les codes de secours dans ton gestionnaire de mots de passe.", 1, None, None, "2026-11-23"),
    ("sr_github", "GitHub : dépôt privé, analyse des secrets, branche main protégée", "Settings → General : le dépôt LockerRoom- doit être Private. Settings → Code security : activer Secret scanning et Push protection. Vérifier qui a accès (Collaborators).", 1, None, "https://github.com/mathbou44/LockerRoom-/settings", "2026-11-23"),
    ("sr_restaure", "Sauvegarde : vérifier qu'elle part chaque nuit, et tester UNE restauration", "Admin → Sécurité : la sauvegarde R2 doit être « active » avec une date d'hier. Puis télécharger un .zip et vérifier qu'il s'ouvre (une sauvegarde jamais testée n'en est pas une).", 2, None, None, "2026-11-27"),
    ("sr_admin", "Admin : confirmer la 2e vérification (iPhone relié + code de secours)", "La console admin demande un code envoyé sur ton iPhone. Vérifie que ton iPhone est relié et que le code de secours (LOCKERROOM_ADMIN_CODE) est dans Render et dans ton gestionnaire de mots de passe.", 2, None, None, "2026-11-25"),
    ("sr_loi25", "Loi 25 : ouvrir un registre des incidents de confidentialité (même vide)", "Tu es déjà nommé responsable dans la Politique de confidentialité. Il reste le registre (un simple document daté). En cas d'incident sérieux : aviser la CAI et les personnes touchées. À valider avec un avocat.", 3, None, "https://www.cai.gouv.qc.ca", "2026-11-28"),
    ("sr_plan", "Plan d'incident d'une page : quoi faire si un compte ou une clé est volé", "Claude l'écrit : dans l'ordre, changer les clés dans Render, révoquer les sessions, vérifier Stripe, restaurer la sauvegarde, aviser. Tu le relis et tu le gardes hors de l'app.", 3, None, None, "2026-11-28"),
    ("sr_alertes", "Alertes : Render (déploiement raté, service tombé) et Stripe (Radar) vers ton courriel", "Render → Settings → Notifications. Stripe → Radar : règles par défaut activées. Un moniteur gratuit (ex. UptimeRobot) sur /sante.", 3, None, None, "2026-11-28"),
    ("sr_c_deps", "Claude : audit des dépendances et test 2 comptes avant le 1er décembre", "pip-audit sur requirements.txt + le test « personne ne voit les données d'un autre » sur tous les écrans, sur la version finale.", 2, None, None, "2026-11-28"),
]
# 21 nov 2026 (Mathieu : « repasse tous les codes pour maximiser la reponse et la rapidite du serveur ») : la suite de la revue
SEMIS["vitesse_21nov"] = [
    ("v_piles", "Après le push : demander à Claude « regarde les piles lentes »", "Le serveur note maintenant OÙ il perd son temps (lignes « Pile lente » du journal Render). 30 minutes après le push, Claude les lit et corrige les vrais points lents, avec tes vraies données.", 1, None, None, "2026-11-22"),
    ("v_push", "À partir du 1er décembre : pousser tôt le matin ou tard le soir", "Chaque mise à jour redémarre le serveur : 3 à 5 minutes plus lentes pour tout le monde. Jamais en pleine soirée.", 2, None, None, "2026-12-01"),
    ("v_c_radar", "Claude : accélérer l'ouverture du Radar (3,5 s à chaque fois)", "La seule lenteur en régime normal dans le journal : deals_liste 3,4 à 3,9 s, annonce_detail 2,3 à 3 s.", 2, None, None, "2026-11-25"),
]
SEMIS["consig_21nov"] = [
    ("cg_test", "Tester la consignation dans l'app iPhone : Excel, PDF et retrait d'eBay", "Inventaire → Consigner → choisir 1 ou 2 cartes en vente sur eBay. 1) La question « Retirer d'eBay ? » apparaît ; 2) Export (Excel) ouvre le fichier dans Safari (Partager pour l'enregistrer) ; 3) Imprimer / PDF ouvre la liste (Partager → Imprimer). Claude n'a pas pu l'essayer dans la vraie app : dis-lui ce qui accroche.", 1, None, None, "2026-11-22"),
]
SEMIS["soir_21nov"] = [
    ("d_series", "Décision : la chance de séries (trophée + %) est maintenant visible par tous dans le Radar", "Avant : admin et Platine seulement. Maintenant : tous les forfaits voient le % (il vient du classement public de la LNH). Le « +x % à la revente », tiré de nos ventes, reste admin et Platine (licence eBay). Si tu préfères garder le % pour le Pro seulement, dis-le à Claude.", 2, None, None, "2026-11-24"),
    ("c_piles", "Claude : relire les « Pile » du journal après ton prochain usage, puis corriger les vrais points lents", "Trouvé le 21 nov : sur Render, gunicorn précharge l'app dans le processus maître ; le worker qui répond aux clients repartait à froid après chaque mise à jour (inventaire 98 s) et le gardien des piles regardait le mauvais processus. Corrigé : le worker se réchauffe lui-même et le gardien y roule. Reste à lire où vont les 3,3 s de Deals (demandé aux 45 s), les 13 s de « Achetées » et les 12 s du statut baseball.", 2, None, None, "2026-11-23"),
    ("c_hagens", "Claude : comprendre pourquoi une seule note d'expert (Hagens B+) fait bouger tout le test SlabIQ", "Testé le 21 nov : Hagens en B+ dans la liste d'experts donnait Radar Pro 71 % → 67,6 % et A/E 10,4× → 9,3× : pas gardé (règle : jamais pire). En attendant, un joueur inconnu du modèle n'a plus de lettre dans Breaks (au lieu d'un « C » trompeur). À creuser avant de noter les espoirs à la main.", 3, None, None, None),
]
SEMIS_PROJET = {"licences_fc": "licences", "lancement_1dec": "lancement", "securite_21nov": "lancement", "matin_21nov": "lancement", "securite_reste": "lancement", "vitesse_21nov": "lancement", "consig_21nov": "lancement", "soir_21nov": "lancement"}
PROJETS = {"licences": "Licences de données", "lancement": "Lancement", "general": "Général", "suivi": "Suivi"}


def taches(cfg=None):
    """Les taches, la plus importante d'abord (priorite, puis echeance, puis la plus vieille)."""
    cfg = cfg if cfg is not None else lire()
    l = [t for t in (cfg.get("taches") or []) if isinstance(t, dict)]
    return sorted(l, key=lambda t: (t.get("etat") == "fait", int(t.get("prio") or 3), t.get("echeance") or "9999", t.get("cree_le") or ""))


def _semer(cur):
    """Une seule fois par projet : ses taches de depart."""
    vus = set(cur.get("semis") or [])
    l = cur.setdefault("taches", [])
    maint = datetime.now().isoformat(timespec="minutes")
    for projet, items in SEMIS.items():
        if projet in vus:
            continue
        for tid, titre, note, prio, modele, lien, *ech in items:
            if not any(t.get("id") == tid for t in l):
                l.append({"id": tid, "titre": titre, "note": note, "prio": prio, "projet": SEMIS_PROJET.get(projet, projet), "etat": "a_faire",
                          "modele": modele, "lien": lien, "cree_le": maint, "echeance": (ech or [None])[0], "fait_le": None})
        vus.add(projet)
        if projet == "lancement_1dec":     # 21 nov : « Pousser v84 a v95 » est remplacee par « Pousser la version du 21 nov »
            for t in l:
                if t.get("id") == "sv_pousser" and t.get("etat") != "fait":
                    t.update(etat="fait", fait_le=maint, note=(t.get("note") or "") + " (remplacée par « Pousser la version du 21 nov »)")
    cur["semis"] = sorted(vus)
    return cur


def _tache_propre(v, ancienne=None):
    t = dict(ancienne or {})
    if "titre" in v:
        t["titre"] = str(v.get("titre") or "").strip()[:160]
    if "note" in v:
        t["note"] = str(v.get("note") or "")[:2000]
    if "echeance" in v:
        t["echeance"] = _date_ok(v.get("echeance")) if v.get("echeance") else None
    if "prio" in v:
        try:
            t["prio"] = int(v["prio"]) if int(v["prio"]) in PRIOS else 3
        except (TypeError, ValueError):
            t["prio"] = 3
    if "projet" in v:
        p = str(v.get("projet") or "general").strip()[:40] or "general"
        t["projet"] = p
    if "etat" in v and v.get("etat") in ETATS:
        t["etat"] = v["etat"]
        t["fait_le"] = datetime.now().isoformat(timespec="minutes") if v["etat"] == "fait" else None
    return t


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "admin_ceo.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _nombre(v):
    try:
        x = round(float(str(v).replace(",", ".").replace(" ", "")), 2)
        return x if 0 <= x < 1e7 else None
    except (TypeError, ValueError):
        return None


def _date_ok(v):
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def sauver(d):
    """Ce que Mathieu remplit : {services: {cle: {montant, devise, periode, plan, renouvellement, note}}, obligations: {cle:
    {fait_le, prochaine, note}}, entreprise: {...}, notes}. Tout est verifie (liste blanche) ; rien d'autre n'est garde."""
    d = d if isinstance(d, dict) else {}
    with _verrou:
        cur = lire()
        cles_s = {s[0] for s in SERVICES}
        for k, v in ((d.get("services") or {}) if isinstance(d.get("services"), dict) else {}).items():
            if k not in cles_s or not isinstance(v, dict):
                continue
            e = cur.setdefault("services", {}).setdefault(k, {})
            if "montant" in v:
                e["montant"] = _nombre(v["montant"]) if v["montant"] not in (None, "") else None
            if v.get("devise") in ("CAD", "USD"):
                e["devise"] = v["devise"]
            if v.get("periode") in ("mois", "an", "usage"):
                e["periode"] = v["periode"]
            for t in ("plan", "note"):
                if t in v:
                    e[t] = str(v[t] or "")[:120]
            if "renouvellement" in v:
                e["renouvellement"] = _date_ok(v["renouvellement"])
        cles_o = {o[0] for o in OBLIGATIONS}
        for k, v in ((d.get("obligations") or {}) if isinstance(d.get("obligations"), dict) else {}).items():
            if k not in cles_o or not isinstance(v, dict):
                continue
            e = cur.setdefault("obligations", {}).setdefault(k, {})
            if "fait_le" in v:
                e["fait_le"] = _date_ok(v["fait_le"])
            if "prochaine" in v:
                e["prochaine"] = _date_ok(v["prochaine"])
            if "note" in v:
                e["note"] = str(v["note"] or "")[:200]
        # 18 nov 2026 (Mathieu : « rentrer toutes les places ou on a des mensualites, et les nouvelles, le plus simple
        # possible ») : ses abonnements a lui, en plus de la liste connue
        P = [x for x in (cur.get("services_perso") or []) if isinstance(x, dict)]
        def _perso(v, x=None):
            x = dict(x or {})
            if "nom" in v:
                x["nom"] = str(v.get("nom") or "").strip()[:60]
            if "montant" in v:
                x["montant"] = _nombre(v["montant"]) if v["montant"] not in (None, "") else None
            if v.get("devise") in ("CAD", "USD"):
                x["devise"] = v["devise"]
            if v.get("periode") in ("mois", "an", "usage"):
                x["periode"] = v["periode"]
            if "renouvellement" in v:
                x["renouvellement"] = _date_ok(v["renouvellement"]) if v.get("renouvellement") else None
            return x
        a_ = d.get("perso_ajout")
        if isinstance(a_, dict) and str(a_.get("nom") or "").strip() and len(P) < 60:
            # meme nom deja la (connu ou perso) : on met a jour au lieu de doubler
            n_ = re.sub(r"\W+", "", str(a_["nom"]).lower())
            connu = next((s[0] for s in SERVICES if re.sub(r"\W+", "", str(s[1]).lower()) == n_), None)
            deja = next((x for x in P if re.sub(r"\W+", "", str(x.get("nom") or "").lower()) == n_), None)
            if connu:
                e = cur.setdefault("services", {}).setdefault(connu, {})
                e.update({k: v for k, v in _perso(a_).items() if k != "nom"})
            elif deja:
                P = [_perso(a_, x) if x is deja else x for x in P]
            else:
                import secrets
                P.append({"id": "p" + secrets.token_hex(4), "devise": "CAD", "periode": "mois", **_perso(a_)})
        if isinstance(d.get("perso"), dict):
            for pid, v in d["perso"].items():
                if isinstance(v, dict):
                    P = [_perso(v, x) if x.get("id") == pid else x for x in P]
        if isinstance(d.get("perso_suppr"), list):
            ids = {str(x) for x in d["perso_suppr"]}
            P = [x for x in P if x.get("id") not in ids]
        cur["services_perso"] = P
        if isinstance(d.get("entreprise"), dict):
            e = cur.setdefault("entreprise", {})
            for t in ("statut", "neq", "comptable", "fin_exercice", "tps_tvq"):
                if t in d["entreprise"]:
                    e[t] = str(d["entreprise"][t] or "")[:120]
        if "notes" in d:
            cur["notes"] = str(d.get("notes") or "")[:4000]
        # les taches : ajout, modification, suppression (identifiant genere ici)
        l = [t for t in (cur.get("taches") or []) if isinstance(t, dict)]
        if isinstance(d.get("tache_ajout"), dict) and str(d["tache_ajout"].get("titre") or "").strip() and len(l) < 500:
            import secrets
            t = _tache_propre({"prio": 3, "projet": "general", "etat": "a_faire", **d["tache_ajout"]})
            t.update(id="t" + secrets.token_hex(5), cree_le=datetime.now().isoformat(timespec="minutes"))
            t.setdefault("fait_le", None)
            l.append(t)
        if isinstance(d.get("taches"), dict):
            for tid, v in d["taches"].items():
                if not isinstance(v, dict):
                    continue
                for i, t in enumerate(l):
                    if t.get("id") == tid:
                        l[i] = _tache_propre(v, t)
        if isinstance(d.get("taches_suppr"), list):
            ids = {str(x) for x in d["taches_suppr"]}
            l = [t for t in l if t.get("id") not in ids]
        cur["taches"] = l
        cur["maj"] = datetime.now().isoformat(timespec="minutes")
        ch = _chemin()
        tmp = ch + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ch)
    return {"ok": True, "config": cur}


def _par_mois_cad(montant, devise, periode, usd_cad):
    if montant is None or periode == "usage":
        return None
    m = float(montant) * (usd_cad if devise == "USD" else 1.0)
    return round(m / 12 if periode == "an" else m, 2)


def _prochaine(quand, aujourd, cfg_o, cfg_s):
    """La prochaine echeance d'une obligation (date ISO) ou None."""
    if cfg_o.get("prochaine"):
        return cfg_o["prochaine"]
    if quand == "acomptes":
        for a in (aujourd.year, aujourd.year + 1):
            for m in (3, 6, 9, 12):
                d = date(a, m, 15)
                if d >= aujourd:
                    return d.isoformat()
    if quand == "mensuel":
        m = aujourd.replace(day=1) + timedelta(days=32)
        return m.replace(day=10).isoformat()
    if quand in ("apple", "domaine"):
        return (cfg_s.get(quand) or {}).get("renouvellement")
    if isinstance(quand, tuple):
        d = date(aujourd.year, *quand)
        return (d if d >= aujourd else date(aujourd.year + 1, *quand)).isoformat()
    return None


def tableau(api):
    import admin
    import comptes
    import demandes
    aujourd = date.today()
    cfg = lire()
    if set(SEMIS) - set(cfg.get("semis") or []):          # 16 nov 2026 : les taches de depart, une seule fois
        with _verrou:
            cfg = _semer(lire())
            ch = _chemin()
            with open(ch + ".tmp", "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=1)
            os.replace(ch + ".tmp", ch)
    a = admin.abonnes()
    cpts = a.get("comptes") or []
    # -- abonnes : la courbe des inscriptions (12 semaines) et les chiffres du lancement
    sem = []
    debut = aujourd - timedelta(days=aujourd.weekday())
    for k in range(11, -1, -1):
        d0 = debut - timedelta(weeks=k)
        d1 = d0 + timedelta(days=7)
        n = sum(1 for c in cpts if c.get("cree_le") and d0.isoformat() <= str(c["cree_le"])[:10] < d1.isoformat())
        sem.append({"semaine": d0.isoformat(), "n": n})
    essais_finis = sum(1 for c in cpts if c["statut"] in ("pro", "gratuit"))
    conv = round(100 * a["pro"] / essais_finis, 1) if essais_finis else None
    annules = sum(1 for c in cpts if c.get("annule"))
    apple = sum(1 for c in cpts if c["statut"] == "pro" and not c.get("stripe"))
    stripe_n = a["pro"] - apple
    # -- revenus et couts
    try:
        usd = (api.taux_change() or {}).get("usd") or 0.70
    except Exception:
        usd = 0.70
    usd_cad = round(1 / usd, 4) if usd else 1.4
    prix = a.get("prix") or {}
    prix_m = (prix.get("montant") or 7.99) / (12 if prix.get("intervalle") == "year" else 1)
    mrr = round(a["pro"] * prix_m, 2)
    frais_stripe = round(stripe_n * (prix_m * (0.029 + 0.007) + 0.30), 2)          # 2,9 % + 0,30 $ + Billing 0,7 %
    frais_apple = round(apple * prix_m * 0.15, 2)                                 # programme petites entreprises : 15 %
    cs = cfg.get("services") or {}
    services, fixe = [], 0.0
    for cle, nom, role, cat, env, lien, defaut in SERVICES:
        c = {**(defaut or {}), **{k: v for k, v in (cs.get(cle) or {}).items() if v not in (None, "")}}
        configure = bool(env) and all(bool(os.environ.get(e)) for e in env[:1])
        pm = _par_mois_cad(c.get("montant"), c.get("devise") or "CAD", c.get("periode") or "mois", usd_cad)
        if pm:
            fixe += pm
        services.append({"cle": cle, "nom": nom, "categorie": cat, "lien": lien, "configure": configure if env else None,
                         "montant": c.get("montant"), "devise": c.get("devise") or "CAD", "periode": c.get("periode") or "mois",
                         "plan": c.get("plan") or "", "renouvellement": c.get("renouvellement"), "note": c.get("note") or "",
                         "par_mois_cad": pm, "a_remplir": c.get("montant") is None})
    for x in (cfg.get("services_perso") or []):
        if not isinstance(x, dict) or not x.get("id"):
            continue
        pm = _par_mois_cad(x.get("montant"), x.get("devise") or "CAD", x.get("periode") or "mois", usd_cad)
        if pm:
            fixe += pm
        services.append({"cle": x["id"], "nom": x.get("nom") or "?", "categorie": "perso", "lien": None, "configure": None, "perso": True,
                         "montant": x.get("montant"), "devise": x.get("devise") or "CAD", "periode": x.get("periode") or "mois",
                         "plan": "", "renouvellement": x.get("renouvellement"), "note": "", "par_mois_cad": pm, "a_remplir": x.get("montant") is None})
    s = admin.sante()
    ia_usd = ((s.get("photos") or {}).get("usd") or 0.0)
    ia_cad = round(ia_usd * usd_cad, 2)
    variable = round(frais_stripe + frais_apple + ia_cad, 2)
    couts = {"fixe_mois": round(fixe, 2), "variable_mois": variable, "frais_stripe": frais_stripe, "frais_apple": frais_apple,
             "ia_cad": ia_cad, "ia_usd": round(ia_usd, 2), "ia_plafond_usd": (s.get("photos") or {}).get("plafond_usd"),
             "total_mois": round(fixe + variable, 2), "usd_cad": usd_cad, "a_remplir": sum(1 for x in services if x["a_remplir"])}
    revenus = {"mrr": mrr, "arr": round(mrr * 12, 2), "net_mois": round(mrr - couts["total_mois"], 2), "prix_mois": round(prix_m, 2),
               "devise": a.get("devise") or "CAD", "stripe_mode": a.get("stripe_mode"), "apple": apple, "stripe": stripe_n,
               "seuil_tps": 30000, "annualise": round(mrr * 12, 2)}
    # -- quotas et credits
    quotas = []
    for k, v in ((s.get("ebay") or {}).get("appels") or {}).items():
        if v.get("limite"):
            quotas.append({"nom": "eBay · " + k, "utilises": v.get("utilises") or 0, "limite": v["limite"], "periode": "jour"})
    try:
        import vendues
        vs = vendues.statut()
        quotas.append({"nom": "SoldComps", "utilises": vs.get("aujourdhui") or 0, "limite": vs.get("plafond") or 0, "periode": "jour", "actif": vs.get("actif")})
        t = vs.get("thecardapi") or {}
        quotas.append({"nom": "TheCardAPI", "utilises": t.get("aujourdhui") or 0, "limite": t.get("plafond") or 0, "periode": "jour", "actif": t.get("actif")})
        c_ = vs.get("compsniper") or {}
        if c_.get("plafond"):
            quotas.append({"nom": "CompSniper", "utilises": c_.get("utilises") or 0, "limite": c_["plafond"], "periode": "mois", "actif": c_.get("actif")})
    except Exception:
        pass
    try:
        import highlightly
        h = highlightly.statut()
        quotas.append({"nom": "Highlightly", "utilises": h.get("aujourdhui") or 0, "limite": h.get("plafond") or 0, "periode": "jour", "actif": h.get("actif")})
    except Exception:
        pass
    if s.get("photos"):
        p = s["photos"]
        quotas.append({"nom": "ia_photos", "usd": True, "utilises": round(p.get("usd") or 0, 2), "limite": p.get("plafond_usd") or 0, "periode": "mois", "actif": p.get("disponible")})
    # -- bugs et propositions
    items = demandes.lire().get("items") or []
    ouv = [x for x in items if x.get("statut") in ("nouveau", "en_cours")]
    par_type = {}
    for x in ouv:
        c = ((x.get("ia") or {}).get("categorie")) or ("bug" if x.get("type") == "probleme" else x.get("type") or "autre")
        par_type[c] = par_type.get(c, 0) + 1
    recents = sorted(ouv, key=lambda x: str(x.get("le") or ""), reverse=True)[:12]
    dem = {"ouvertes": len(ouv), "nouvelles": sum(1 for x in ouv if x.get("statut") == "nouveau"), "par_categorie": par_type,
           "liste": [{"id": x.get("id"), "type": x.get("type"), "categorie": (x.get("ia") or {}).get("categorie"), "priorite": (x.get("ia") or {}).get("priorite"),
                      "resume": (x.get("ia") or {}).get("resume") or str(x.get("texte") or "")[:140], "le": x.get("le"), "statut": x.get("statut")} for x in recents],
           "fermees_30j": sum(1 for x in items if x.get("statut") not in ("nouveau", "en_cours") and str(x.get("le") or "") > (aujourd - timedelta(days=30)).isoformat())}
    errs = s.get("erreurs") or []
    erreurs = {"h24": sum(1 for e in errs if str(e.get("le")) > (datetime.now() - timedelta(days=1)).isoformat()),
               "j7": sum(1 for e in errs if str(e.get("le")) > (datetime.now() - timedelta(days=7)).isoformat()),
               "dernieres": [{"le": e.get("le"), "ou": e.get("ou"), "msg": str(e.get("msg") or e.get("erreur") or "")[:160]} for e in errs[:8]]}
    # -- securite : des verifications, jamais une valeur secrete
    sv = {}
    try:
        import sauvegarde
        sv = sauvegarde.statut()
    except Exception:
        pass
    age_sv = None
    if sv.get("dernier_ok"):
        try:
            age_sv = (datetime.now() - datetime.fromisoformat(str(sv["dernier_ok"])[:19])).total_seconds() / 3600
        except ValueError:
            pass
    heberge = os.environ.get("LOCKERROOM_HEBERGE") == "1"
    sec = [
        ("https", "HTTPS forcé (HSTS)", heberge, "Le site refuse les connexions non chiffrées.", "Actif seulement sur le serveur Render."),
        ("secret", "Clé de session forte", len(os.environ.get("LOCKERROOM_SECRET") or "") >= 32, "Les sessions ne peuvent pas être falsifiées.", "Mets LOCKERROOM_SECRET (32 caractères ou plus) dans Render."),
        ("admin2", "Admin protégé par un 2e facteur", bool(os.environ.get("APNS_KEY_ID") or os.environ.get("LOCKERROOM_ADMIN_CODE")), "Un code sur ton iPhone avant d’ouvrir l’admin.", "Configure les notifications Apple (APNs) ou un code admin de secours."),
        ("admins", "Liste des administrateurs", bool(os.environ.get("LOCKERROOM_ADMINS")), f"{len([c for c in cpts if c.get('admin')])} compte(s) admin.", "Garde cette liste la plus courte possible."),
        ("stripe_wh", "Webhook Stripe signé", bool(os.environ.get("STRIPE_WEBHOOK_SECRET")) or not os.environ.get("STRIPE_CLE_SECRETE"), "Seul Stripe peut confirmer un paiement.", "Ajoute STRIPE_WEBHOOK_SECRET dans Render."),
        ("ebay_avis", "Avis de suppression eBay", bool(os.environ.get("LOCKERROOM_EBAY_AVIS_JETON")), "Exigé par eBay pour garder l’accès à l’API.", "Configure le jeton dans Render et sur developer.ebay.com."),
        ("csp", "Politique de contenu (CSP)", os.environ.get("LR_CSP", "1") != "0", "Bloque les scripts injectés.", "Ne mets pas LR_CSP=0 en production."),
        ("sauvegarde", "Sauvegarde de nuit", bool(sv.get("actif")) and age_sv is not None and age_sv < 30, ("Dernière il y a " + str(int(age_sv)) + " h.") if age_sv is not None else "Aucune sauvegarde réussie.", "Configure Cloudflare R2 (R2_BUCKET et ses clés)."),
        ("erreurs", "Erreurs des dernières 24 h", erreurs["h24"] == 0, f"{erreurs['h24']} erreur(s).", "Regarde la liste des erreurs dans l’admin."),
        ("demo", "Pas de code démo ouvert", not os.environ.get("LOCKERROOM_DEMO_CODE"), "Aucun accès démo public.", "Garde-le pendant l’examen d’Apple, puis retire LOCKERROOM_DEMO_CODE de Render une fois l’app acceptée."),
    ]
    mem = s.get("memoire") or {}
    disque = s.get("disque") or {}
    vals = {"admins": len([c for c in cpts if c.get("admin")]), "sauvegarde": int(age_sv) if age_sv is not None else None, "erreurs": erreurs["h24"]}
    securite = {"verifs": [{"cle": k, "ok": bool(ok), "v": vals.get(k)} for k, t, ok, d, c in sec],
                "memoire": {"utilise_mo": mem.get("conteneur_mo") or mem.get("processus_mo"), "limite_mo": mem.get("limite_mo")},
                "disque": disque, "version": s.get("version"), "version_app": s.get("version_app"), "en_ligne_h": s.get("en_ligne_h")}
    securite["score"] = round(100 * sum(1 for v in securite["verifs"] if v["ok"]) / len(securite["verifs"]))
    # -- obligations
    co = cfg.get("obligations") or {}
    obl = []
    for cle, titre, detail, cat, freq, quand in OBLIGATIONS:
        c = co.get(cle) or {}
        pr = _prochaine(quand, aujourd, c, cs)
        jours = (date.fromisoformat(pr) - aujourd).days if pr else None
        obl.append({"cle": cle, "categorie": cat, "frequence": freq, "prochaine": pr, "jours": jours,
                    "fait_le": c.get("fait_le"), "note": c.get("note") or ""})
    obl.sort(key=lambda o: (o["jours"] is None, o["jours"] if o["jours"] is not None else 0))
    # -- opportunites
    opp = [{"cle": k, "type": ty, "branche": (k == "epn" and bool(os.environ.get("LOCKERROOM_EPN_CAMPID"))) or (k == "platine" and os.environ.get("LR_PLATINE") == "1")} for k, t, d, ty in OPPORTUNITES]
    # -- les alertes du jour (ce qui demande une action), en premier sur la page
    alertes = []
    for o in obl:
        if o["jours"] is not None and o["jours"] <= 30 and not (o["fait_le"] and o["prochaine"] and o["fait_le"] >= o["prochaine"]):
            alertes.append({"k": "obl", "cle": o["cle"], "jours": o["jours"], "ton": "rouge" if o["jours"] <= 7 else "or", "section": "obligations"})
    for v in securite["verifs"]:
        if not v["ok"] and v["cle"] != "https":
            alertes.append({"k": "sec", "cle": v["cle"], "ton": "or", "section": "securite"})
    for q in quotas:
        if q.get("limite") and q["utilises"] / q["limite"] > 0.8:
            alertes.append({"k": "quota", "nom": q["nom"], "pct": round(100 * q["utilises"] / q["limite"]), "ton": "rouge", "section": "quotas"})
    if dem["nouvelles"]:
        alertes.append({"k": "demandes", "n": dem["nouvelles"], "ton": "acc", "section": "demandes"})
    if couts["a_remplir"]:
        alertes.append({"k": "couts", "n": couts["a_remplir"], "ton": "acc", "section": "services"})
    if revenus["annualise"] >= 0.8 * revenus["seuil_tps"]:
        alertes.append({"k": "tps", "ton": "rouge", "section": "obligations"})
    # -- la preuve en direct (preuve.py) : jours figes, horodatage, chaine intacte, premiers resultats
    try:
        import preuve
        pv = {**preuve.statut(), "verification": preuve.verifier(), "resultats": (preuve.resultats_garde() or {}).get("par_horizon")}
    except Exception as e:
        pv = {"erreur": repr(e)[:120]}
    if pv.get("verification") and not pv["verification"].get("ok"):
        alertes.insert(0, {"k": "preuve_brisee", "ton": "rouge", "section": "preuve"})
    elif pv.get("jours") is not None and (not pv.get("dernier") or pv["dernier"]["jour"] < (aujourd - timedelta(days=1)).isoformat()):
        alertes.append({"k": "preuve_retard", "ton": "or", "section": "preuve"})
    return {"ok": True, "le": datetime.now().isoformat(timespec="minutes"), "preuve": pv,
            "abonnes": {**{k: v for k, v in a.items() if k not in ("comptes", "prix")}, "semaines": sem, "conversion_pct": conv, "annules": annules,
                        "derniers": [{"username": c["username"], "statut": c["statut"], "cree_le": c.get("cree_le"), "vu_le": c.get("vu_le"), "connexion": c.get("connexion")}
                                     for c in sorted(cpts, key=lambda x: str(x.get("cree_le") or ""), reverse=True)[:10]]},
            "revenus": revenus, "couts": couts, "services": services, "categories": CATEGORIES, "quotas": quotas, "demandes": dem,
            "erreurs": erreurs, "securite": securite, "obligations": obl, "obl_categories": OBL_CATEGORIES, "opportunites": opp, "taches": taches(cfg), "projets": PROJETS,
            "entreprise": cfg.get("entreprise") or {}, "notes": cfg.get("notes") or "", "alertes": alertes, "multi": comptes.MULTI}
