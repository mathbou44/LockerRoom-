"""21 nov 2026 (Mathieu : « sur le cell, incapable de creer le fichier Excel ou PDF ; les cartes affichees sur eBay doivent etre
retirees d'eBay si on les envoie en consignation ») : le fichier fabrique par le serveur (lien de 20 min) et le retrait d'eBay."""
import io, os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI); os.chdir(ICI)
os.environ.update(LOCKERROOM_DONNEES=tempfile.mkdtemp(), LOCKERROOM_TACHES="0", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999")
import server, exports_temp
from openpyxl import load_workbook
a = server.api
L = [{"joueur": "Connor McDavid", "titre": "2025-26 OPC Glossy <b>Gold</b>", "grade": "Raw", "photo": "https://i.ebayimg.com/a.jpg", "numero": "=1+1"},
     {"titre": "Sans photo", "photo": "javascript:alert(1)"}]
r = a.consig_fichier(L, "Slab Sharks", "xlsx", True, "en")
assert r["ok"] and r["url"].startswith("/x/") and r["nom"].endswith(".xlsx")
c = server.app.test_client()
x = c.get(r["url"])
assert x.status_code == 200 and "inline" in x.headers["Content-Disposition"] and "attachment" in c.get(r["url"] + "?d=1").headers["Content-Disposition"]
ws = load_workbook(io.BytesIO(x.data)).active
assert ws["B3"].value == "Connor McDavid" and ws["F3"].value == "'=1+1" and "Slab Sharks" in ws["A1"].value      # jamais une formule
h = c.get(a.consig_fichier(L, "Maison <x>", "html", True, "fr")["url"])
t = h.get_data(as_text=True)
assert h.status_code == 200 and "<b>Gold" not in t and "javascript:" not in t and "&lt;x&gt;" in t and "ebayimg.com/a.jpg" in t and "Content-Disposition" not in h.headers
assert c.get("/x/" + "0" * 32 + "/a.xlsx").status_code == 404 and c.get("/x/abc/a.xlsx").status_code == 404
assert a.consig_fichier([], "x")["ok"] is False
# le retrait d'eBay : l'annonce est terminee, la carte RESTE (« En stock ») ; si eBay refuse, rien ne change
ida = a.carte_sauver({"titre": "Carte A", "joueur": "A"})["id"]
idb = a.carte_sauver({"titre": "Carte B", "joueur": "B"})["id"]
idc = a.carte_sauver({"titre": "Carte C", "joueur": "C"})["id"]
import lockerroom, sqlite3
cx = sqlite3.connect(a.chemin_db)
cx.execute("UPDATE cartes SET statut='Listée', item_number='111111111111' WHERE id=?", (ida,))
cx.execute("UPDATE cartes SET statut='Listée', item_number='222222222222' WHERE id=?", (idb,)); cx.commit(); cx.close()
vus = []
def faux(fn, item, *k, **kw):
    vus.append((fn, item)); return {"ok": item != "222222222222", "erreur": "eBay a refusé"}
a._ecrire_ebay = faux
r = a.consig_retirer_ebay([ida, idb, idc, "x"])
assert r["terminees"] == 1 and len(r["erreurs"]) == 1 and r["erreurs"][0]["id"] == idb and vus == [("terminer", "111111111111"), ("terminer", "222222222222")], (r, vus)
assert a.carte_lire(ida)["statut"] == "En stock" and a.carte_lire(idb)["statut"] == "Listée" and a.carte_lire(idc)
print("OK test_consig_fichier")
