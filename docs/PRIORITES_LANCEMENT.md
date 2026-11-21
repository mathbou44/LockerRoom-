# Lancement du 1er décembre 2026 : les priorités

Mis à jour le 20 novembre 2026 au soir. Ordre = importance. « Toi » = Mathieu, « Claude » = ce que je fais.

## 1. Bloquant : sans ça, pas de lancement

| # | Quoi | Qui | Quand |
|---|------|-----|-------|
| 1 | **Pousser** tout ce qui est sur le PC (GitHub Desktop → Commit → Push), attendre « live » sur Render | Toi | Demain 8 h |
| 2 | **Soumission Apple** : build Codemagic (il contient maintenant la fenêtre de note d'Apple : vérifier que le build passe), captures, fiche App Store, note au réviseur avec le code démo. Pas de « Bêta » visible | Toi | Samedi 22 nov au plus tard |
| 3 | **Stripe** : finir la vérification d'identité ; créer le prix annuel et mettre son code dans Render (`STRIPE_PRIX_PRO_ANNUEL`) | Toi | Avant le 25 nov |
| 4 | **Un vrai paiement test** de bout en bout : essai 14 jours → Pro → annulation → remboursement | Toi + Claude | Après le point 3 |
| 5 | **Parcours d'un nouveau compte au cell** : inscription → « Pour bien partir » → relier eBay → 1re carte → Radar → Breaks → essai Pro. Noter tout ce qui accroche | Toi (je corrige en direct) | Demain 10 h 30 |
| 6 | **Crédits SoldComps** (blitz épuisé le 18 nov) : renouveler, sinon les ventes récentes s'arrêtent | Toi | Avant le 25 nov |

## 2. Important : à faire avant le 1er décembre

| # | Quoi | Qui |
|---|------|-----|
| 7 | **Cloudflare** : 2FA, HSTS (Edge Certificates), DMARC `p=none`. Ne pas activer Bot Fight Mode (bloque Stripe, Apple, eBay) | Toi |
| 8 | **Aikido** : relancer le scan après le push ; ignorer avec raison lightgbm, liste IP GitHub, CSP. M'envoyer ce qui reste | Toi → Claude |
| 9 | **Test 2 comptes** sur tous les écrans : personne ne voit les données d'un autre | Claude |
| 10 | **Courriels de licence (7, dont Fanatics)** : le connecteur Gmail est maintenant branché ; choisis l'adresse d'envoi, je prépare les brouillons, tu dis « envoie » pour chacun | Toi + Claude |
| 11 | **Les 2 dernières fenêtres** à passer « Apple » (Bilan vide, page joueur sans données). Faits : Vendre à l'ordi sur un écran, Comptoir au cell, Notifications vide | Claude |
| 12 | **Nouveautés** à jour la veille du lancement (règle : après chaque grosse mise à jour) | Claude |
| 13 | **Après l'approbation d'Apple** : retirer le code démo (conseil dans `ceo.py`) | Toi |

## 3. Tes décisions en attente (oui / non)

1. Supprimer `ui/vitrine.html` (pas servi, dit encore « 9/10 ») ?
2. Le site dit SlabIQ « réentraîné chaque semaine » ; c'est aux 3 jours. On écrit « plusieurs fois par semaine » ?
3. Le refus des non-cartes s'applique aussi quand tu touches toi-même « Ajouter à l'inventaire » ?
4. Budget baseball (SoldComps / TheCardAPI) : on lance le baseball le 1er décembre ou après ?
5. SlabIQ « YG Renewed » : le marché la place à B ; tu l'avais mise à D après une mesure. B donne un accord de 80,5 % au lieu de 80,3 %, et le reste ne bouge pas. On garde D, ou on passe à B ?
6. Téléchargements sur le site : Apple ne publie pas ce chiffre. Pour l'avoir automatiquement, il faut une clé API App Store Connect (rôle « Sales »), que tu mets dans Render. On la branche après le lancement ? En attendant, le site montre « X+ collectionneurs » (nos comptes, à partir de 250).

## 4. Après le lancement (pas bloquant)

- **Baseball** : la même app que le hockey, page par page, avec nos données de baseball. Test SlabIQ à refaire dès qu'on exporte des ventes fraîches (Entraîner SlabIQ → ↓ Ventes Baseball).
- Réponse d'eBay sur les prix vendus montrés au public.
- SlabIQ : continuer les essais avant / après (règle : on garde seulement si ce n'est pas pire, sur des ventes jamais vues).

## Notes App Store (preuve sociale, automatique)

- Le site lit les vraies notes Apple aux 6 h. Il affiche la note moyenne sous les boutons du haut et un diaporama des commentaires 4-5★ avant les Forfaits.
- Il n'affiche rien avant 5 notes et 3 bons commentaires.
- Dans l'app, la fenêtre de note d'Apple s'ouvre après la 3e réussite, au moins 3 jours après la première ouverture, une fois par version au maximum. Un lien « Noter SlabCoach » est ajouté dans Réglages.
- ⚠ Ne jamais demander « 5 étoiles » en échange de quoi que ce soit (règle Apple).

## Ce qui est fait (20 nov)

Import eBay automatique (cartes seulement), isolation des comptes, trivia admin, tuiles d'accueil, slogan, site (« Ça te dit quelque chose ? », À propos, SlabIQ), Breaks et Tendances en version Apple, en-têtes fixes, admin sans barre de défilement, consignation en lot (Excel / PDF), palmarès d'un joueur, retour sur la page joueur, sécurité Aikido (pickle, XSS, SSRF, lecture de fichier), notes App Store sur le site, SlabIQ : les autos passent de B à B+ (testé sur des ventes jamais vues : accord 79,7 % → 80,3 %, A+/A contre E 9,6× → 10,7×, Radar Pro inchangé à 71 %).
