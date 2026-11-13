"""13 nov 2026 (Mathieu : « supprimer un de mes comptes » ; « mon frere est connecte, pourquoi je ne le vois pas ») :
l'admin supprime un compte avec garde-fous ; « vu » = la derniere activite (pas seulement la connexion)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LOCKERROOM_ADMINS"] = "hallofcardz"
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
comptes.CHEMIN_INDEX = os.path.join(comptes.DOSSIER_COMPTES, "index.json") if hasattr(comptes, "CHEMIN_INDEX") else None
comptes.MULTI = True
import admin, lockerroom
cell, _ = comptes.trouver_ou_creer("apple-sub-1", "Mathieu Bourassa", "apple")
moi, _ = comptes.trouver_ou_creer("ebay-user-1", "hallofcardz", "production")
autre, _ = comptes.trouver_ou_creer("ebay-user-2", "max_189380", "production")
comptes.renvoyer(cell, moi)                                     # l'ancien compte du cell, relie au compte eBay
A = {c["username"]: c for c in admin.abonnes()["comptes"]}
assert A["Mathieu Bourassa"]["relie_a"] == "hallofcardz" and A["hallofcardz"]["admin"] and not A["max_189380"]["admin"]
# garde-fous
assert not admin.supprimer_compte(moi, moi, "hallofcardz")["ok"]               # le compte connecte / admin : jamais
assert not admin.supprimer_compte(cell, moi, "mauvais nom")["ok"]               # le nom doit etre retape
r = admin.supprimer_compte(cell, moi, "mathieu bourassa")                      # l'ancien compte relie : son dossier seulement
assert r["ok"] and r.get("relie") and cell not in comptes.lister() and moi in comptes.lister(), r
assert comptes.resoudre(moi) == moi
# « vu » : la derniere activite, au plus une ecriture aux 10 min
comptes.maj(autre, vu_le="2026-11-10T08:00:00")
assert comptes.vu(autre, 2_000_000_000) and comptes.info(autre)["vu_le"].startswith("2033")
assert not comptes.vu(autre, 2_000_000_100)                                   # 100 s plus tard : pas de 2e ecriture
print("OK admin supprimer")
