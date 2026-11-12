"""12 nov 2026 (Mathieu : « y aller par ordre pour limiter le gaspillage de credit ») : l'ordre des credits."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import credits, cartes_match as cm
C = cm.cible_titre
# les categories
assert credits.etiquettes(C("2023-24 Upper Deck Ice Emerald Surge Cole Caufield RC 1/10 PSA 8")) == ["serie /25-", "gradee <9"]
assert "auto-patch" in credits.etiquettes(C("2021 SP Game Used Dominik Hasek Gold Patch Auto /15"))
assert credits.etiquettes(C("2024-25 Upper Deck Young Guns Joe Nobody RC")) == ["recrue base"]
# les bons joueurs d'abord, la recrue de base d'un joueur gris jamais (sous 30 $)
n_has = credits.note(C("2021 SP Game Used Dominik Hasek Gold Patch Auto /15"), 92, "savage.cards")
n_cau = credits.note(C("2023-24 Upper Deck Ice Emerald Surge Cole Caufield RC 1/10 PSA 8"), 186, "x")
n_yg = credits.note(C("2024-25 Upper Deck Young Guns Joe Nobody RC"), 3, "savage.cards")
n_auto_g = credits.note(C("2022 SP Authentic Future Watch Auto Joe Nobody /999"), 5, "x")
assert n_has[0] > n_cau[0] > 0 and n_has[2] == "bon", (n_has, n_cau)
assert n_yg[0] == 0 and n_auto_g[0] == 0
# la meme carte a 40 $ (la mise montre qu'elle vaut plus) : verifiee
assert credits.note(C("2022 SP Authentic Future Watch Auto Joe Nobody /999"), 40, "x")[0] > 0
# le vendeur prioritaire passe devant le meme carte ailleurs
assert credits.note(C("2021 SP Game Used Dominik Hasek Gold Patch Auto /15"), 92, "x")[0] < n_has[0]
# le registre : une categorie qui ne rapporte rien glisse vers le bas ; le cache ne compte pas
cib = C("2022 SP Authentic Future Watch Auto Joe Nobody /999")
cat = credits.note(cib, 40, "x")[1]
avant = credits.note(cib, 40, "x")[0]
for _ in range(60):
    credits.noter(cib, "x", 40, "trop_cher", 1.4, n_ventes=5)
credits.noter(cib, "x", 40, "deal", 0.5, cache=True)
apres = credits.note(cib, 40, "x")[0]
assert apres < avant * 0.6, (avant, apres)
r = credits.rapport()
assert r["total"]["credits"] == 60 and r["total"]["deals"] == 0
assert sum(x["credits"] for x in r["lignes"] if x["calibre"] == "gris") == 60
# un deal : le gain = la valeur - le prix
credits.noter(C("2021 SP Game Used Dominik Hasek Gold Patch Auto /15"), "savage.cards", 100, "deal", 0.25, n_ventes=2)
r = credits.rapport()
assert r["total"]["deals"] == 1 and r["total"]["gain"] == 300.0, r["total"]
assert next(g for g in r["groupes"] if g["groupe"] == "prio")["credits"] == 1
print("CREDITS OK")
# l'ordre : le groupe du vendeur d'abord (Probstein en dernier), le Canada avant les Etats-Unis
bon = C("2021 SP Game Used Dominik Hasek Gold Patch Auto /15")
k_sav = credits.cle_ordre(bon, 92, "savage.cards", annonce={"lieu": "CA"})
k_pro = credits.cle_ordre(bon, 92, "probstein123", annonce={"lieu": "US"})
k_aut_ca = credits.cle_ordre(bon, 92, "quelquun", annonce={"lieu": "CA"})
k_aut_us = credits.cle_ordre(bon, 92, "quelquun", annonce={"lieu": "US"})
assert k_sav < k_aut_ca < k_aut_us < k_pro, (k_sav, k_aut_ca, k_aut_us, k_pro)
assert round(credits.note(bon, 92, "x", annonce={"lieu": "US"})[0] / credits.note(bon, 92, "x", annonce={"lieu": "CA"})[0], 2) == credits.FACTEUR_ETRANGER
print("ORDRE OK")
