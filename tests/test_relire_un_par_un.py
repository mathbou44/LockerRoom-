"""20 nov 2026 (revue de lancement) : eBay refuse getItems (lots de 20, « Limited Release ») avec un 403 ; les encans qui
finissent et les prix fixes des deals n'etaient jamais relus. Repli : une annonce par appel (get_item_by_legacy_id), au plus
quelques-unes par passe, les plus proches de la fin d'abord. Aucun reseau : eBay est simule."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals  # noqa: E402
import ebay_compte  # noqa: E402

m = datetime.now(timezone.utc)
iso = lambda h: (m + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
vu = m.isoformat(timespec="seconds")

# eBay simule : getItems toujours refuse (403) ; getItem repond selon le tableau (None = 404, finie ou retiree)
appels = {"lot": 0, "un": []}
REPONSES = {}


def faux_lot(ids, fond=True):
    appels["lot"] += 1
    raise RuntimeError('eBay HTTP 403 : {"errors":[{"errorId":1100,"message":"Access denied"}]}')


def faux_article(iid, fond=False, frais=False, pays="CA"):
    appels["un"].append(iid)
    r = REPONSES.get(iid, "absent")
    if r is None:
        raise RuntimeError('eBay HTTP 404 : {"errors":[{"errorId":11001}]}')
    if r == "limite":
        raise RuntimeError("Limite quotidienne d'appels eBay presque atteinte : reprise automatique demain")
    return r


ebay_compte.articles_lot, ebay_compte.article = faux_lot, faux_article

# 1) articles_relire : 403 -> retenu 24 h, puis une par une, au plus maxi ; 404 = demandee mais absente
ebay_compte._LOT_REFUSE.update(jusqu=0.0, dit=False)
REPONSES.update({"100000001": {"prix_cad": 10.0}, "100000002": None, "100000003": {"prix_cad": 30.0}})
lus, dem = ebay_compte.articles_relire(["100000001", "100000002", "100000003", "100000004"], maxi=3)
assert appels["lot"] == 1 and appels["un"] == ["100000001", "100000002", "100000003"], appels
assert set(lus) == {"100000001", "100000003"} and dem == {"100000001", "100000002", "100000003"}, (lus, dem)
lus, dem = ebay_compte.articles_relire(["100000001"], maxi=3)
assert appels["lot"] == 1, "le refus de getItems est retenu : pas de 2e appel perdu"

# 2) une limite (ou une panne) au milieu : on garde ce qui est lu ; le reste n'est pas demande (rien n'est conclu)
appels["un"].clear()
REPONSES.update({"200000001": {"prix_cad": 5.0}, "200000002": "limite"})
lus, dem = ebay_compte.articles_relire(["200000001", "200000002", "200000003"], maxi=5)
assert set(lus) == {"200000001"} and dem == {"200000001"}, (lus, dem)
try:                                            # la limite des la 1re annonce : l'erreur remonte (rien de lu)
    ebay_compte.articles_relire(["200000002"], maxi=5)
    raise AssertionError("la limite devait remonter")
except RuntimeError:
    pass

# 3) fin_proche sans lire_lot : les plus proches de la fin d'abord, au plus FIN_PROCHE_UN_PAR_UN ; la mise a monte -> sortie
appels["un"].clear()
d = deals.lire()
d["suivis"], d["pres"] = [], []
d["deals"] = [{"item_id": f"30000000{k}", "titre": f"e{k}", "total": 20, "valeur": 100, "ratio": .2, "encan": True,
               "fin": iso(0.1 + k * 0.1), "vu_le": vu} for k in range(1, 8)]
d["deals"].append({"item_id": "399999999", "titre": "loin", "total": 20, "valeur": 100, "ratio": .2, "encan": True, "fin": iso(30), "vu_le": vu})
deals._ecrire(d)
REPONSES.update({f"30000000{k}": {"prix_cad": 20.0, "port_cad": 0.0, "fin": iso(0.1 + k * 0.1), "mises": 1} for k in range(1, 8)})
REPONSES["300000001"] = {"prix_cad": 90.0, "port_cad": 0.0, "fin": iso(0.2), "mises": 12}          # la mise a monte
REPONSES["300000002"] = None                                                                         # 404 : encore ouvert -> garde
r = deals.fin_proche()
assert appels["un"] == [f"30000000{k}" for k in range(1, deals.FIN_PROCHE_UN_PAR_UN + 1)], appels["un"]
dd = {x["item_id"]: x for x in deals.lire()["deals"]}
assert r["lus"] == deals.FIN_PROCHE_UN_PAR_UN and r["sortis"] == 1, r
assert "300000001" not in dd and "300000002" in dd and "399999999" in dd, sorted(dd)

# 4) prix_fixes sans lire_lot : vendue (404) -> sortie ; prix monte -> sortie ; pareil -> gardee, au plus PRIX_FIXE_UN_PAR_UN
appels["un"].clear()
d = deals.lire()
d["deals"] = [{"item_id": "400000001", "titre": "a", "total": 30, "valeur": 100, "ratio": .3, "encan": False, "vu_le": vu},
              {"item_id": "400000002", "titre": "b", "total": 30, "valeur": 100, "ratio": .3, "encan": False, "vu_le": vu},
              {"item_id": "400000003", "titre": "c", "total": 30, "valeur": 100, "ratio": .3, "encan": False, "vu_le": vu}]
deals._ecrire(d)
REPONSES.update({"400000001": None, "400000002": {"prix_cad": 95.0, "port_cad": 0.0}, "400000003": {"prix_cad": 29.0, "port_cad": 1.0}})
r = deals.prix_fixes()
dd = {x["item_id"]: x for x in deals.lire()["deals"]}
assert r["sortis"] == 2 and set(dd) == {"400000003"} and dd["400000003"].get("prix_lu_le"), (r, dd)

# 5) prix_fixes : toutes « absentes » d'un coup (eBay renvoie 404 partout) -> on ne conclut rien, personne ne sort
d = deals.lire()
d["deals"] = [{"item_id": f"50000000{k}", "titre": "x", "total": 30, "valeur": 100, "ratio": .3, "encan": False, "vu_le": vu} for k in range(1, 4)]
deals._ecrire(d)
REPONSES.update({f"50000000{k}": None for k in range(1, 4)})
r = deals.prix_fixes()
assert r["sortis"] == 0 and len(deals.lire()["deals"]) == 3, r
print("ok : relecture une par une (getItems refuse)")
