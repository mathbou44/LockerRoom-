"""31 oct 2026 : la mise envoyee a Gixen (API simulee : aucun reseau)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gixen  # noqa: E402

os.environ.pop("GIXEN_UTILISATEUR", None)
assert not gixen.ajouter("206646459992", 54)["ok"]                         # sans identifiants dans Render : rien
os.environ.update(GIXEN_UTILISATEUR="moi", GIXEN_MOT_DE_PASSE="x")
vu = []
r = gixen.ajouter("206646459992", 54, lire=lambda q: vu.append(q) or "OK 206646459992 ADDED")
assert r["ok"] and r["mise"] == 54.0 and vu[0]["maxbid"] == "54.00" and vu[0]["itemid"] == "206646459992" and vu[0]["bidoffset"] == "6", (r, vu)
r = gixen.ajouter("206646459992", 54, lire=lambda q: "ERROR (E07): Item has already ended")
assert not r["ok"] and "already ended" in r["erreur"] and r["code"] == "E07", r
assert not gixen.ajouter("abc", 54)["ok"] and not gixen.ajouter("206646459992", 0)["ok"]
assert gixen.ajouter("206646459992", 54, decalage=99, lire=lambda q: vu.append(q) or "OK 206646459992 ADDED")["decalage"] == 6
print("ok : Gixen")
r = gixen.ajouter("206646459992", 54, lire=lambda q: "ERROR (501): API DISABLED")
assert not r["ok"] and r["api_coupee"] and not gixen.actif(), r                # retour au copier-coller pour 6 h
gixen._ETAT["coupee_le"] = 0
assert gixen.actif()
print("ok : Gixen API coupee")
