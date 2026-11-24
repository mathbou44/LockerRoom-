"""24 nov 2026 (audit avant le lancement, Mathieu : « on doit etre parfait avant Apple ») : la fiche d'une annonce se ferme
quand l'ecran change. Avant, le bouton Retour du navigateur changeait l'ecran derriere la fiche, qui restait ouverte par-dessus
(trouve par outils/audit_ecrans.py : une croix « morte » a l'Inventaire, c'etait la fiche ouverte a la Watchlist)."""
import os, re
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for nom in ("source/src_app.html", "ui/app.html"):
    s = open(os.path.join(RACINE, nom), encoding="utf-8").read()
    m = re.search(r"""addEventListener\(['"]hashchange['"],\s*\(\)\s*=>\s*\{?\s*if\s*\(document\.body\.classList\.contains\(['"]fen-ouverte['"]\)\)\s*fermerAnnonce\(\)""", s)
    assert m, nom
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
# une feuille se fermait deja au changement d'ecran : la fiche suit la meme regle
assert "if (!$('#fond-feuille').hidden) fermerFeuille();" in src
# rien n'ouvre la fiche en changeant d'ecran du meme geste (sinon elle se refermerait aussitot) : le toucher annule le lien
i = src.index("const a = e.target.closest('[data-annonce]')")
assert "e.preventDefault(); e.stopPropagation();" in src[i:i + 900] and "ouvrirAnnonce(" in src[i:i + 1100]
# ceux qui quittent la fiche vers un autre ecran la ferment eux-memes
assert "fermerFeuille(); fermerAnnonce(); location.hash = '#joueur/'" in src
# le balayage signale desormais une fenetre restee ouverte d'un ecran a l'autre
b = open(os.path.join(RACINE, "outils", "audit_ecrans.py"), encoding="utf-8").read()
assert "encore ouvert en arrivant" in b and "parti" in b
print("OK test_fiche_ferme_au_retour")
