"""11 nov 2026 (Mathieu : « d'abord TOUTES les annonces de Savage, Remi et CF31 ; ensuite le reste, les petits vendeurs ;
a la fin Slab Sharks, Probstein, puis DC Sports ») : l'ordre du tour de chasse. Aucun reseau."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals

d_, m_, f_ = deals.phases_chasse()
assert d_ == [["savage.cards"], ["remi-card-trader"], ["cf31_sports_cards"]], d_
assert f_ == [["slabsharksinc"], ["probstein123"], ["dcsports87"]], f_
assert all(v not in ("slabsharksinc", "probstein123", "dcsports87", "savage.cards") for g in m_ for v in g), m_

ordre = []
def rech(q, **k):
    if k.get("vendeurs"):
        ordre.append(("v:" + ",".join(k["vendeurs"]), "encan" if k.get("encheres") else "fixe"))
    elif k.get("aspects"):
        ordre.append(("petits", None))
    else:
        ordre.append(("flux:" + str(q), None))
    return []
deals.flux_hits = lambda c: ([("hit1", "hockey")], 0)
deals.flux_liste = lambda: []
deals._verificateur = lambda *a, **k: None
deals._verifier_tard = lambda *a, **k: None
deals.flux(rechercher=rech, bassin=deals.Bassin(charger=False))
noms = [o[0] for o in ordre]
def premier(n):
    return next(i for i, x in enumerate(noms) if x == n)
i_s, i_r, i_c = premier("v:savage.cards"), premier("v:remi-card-trader"), premier("v:cf31_sports_cards")
i_p, i_h = premier("petits"), premier("flux:hit1")
i_ss, i_pb, i_dc = premier("v:slabsharksinc"), premier("v:probstein123"), premier("v:dcsports87")
i_m = premier("v:" + ",".join(m_[0]))
assert i_s < i_r < i_c < i_p < i_m < i_h < i_ss < i_pb < i_dc, noms
assert ("v:savage.cards", "fixe") in ordre                       # TOUTES leurs annonces : prix fixes aussi
assert ("v:slabsharksinc", "fixe") not in ordre and ("v:dcsports87", "fixe") not in ordre
print("ORDRE CHASSE OK")
