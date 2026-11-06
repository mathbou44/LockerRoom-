"""3 nov 2026 (Mathieu, Jordan Beam Team en encan : « pourquoi ca sort rien ? », SoldComps TimeoutError) : une panne de
SoldComps ne vide plus la fiche : eBay.ca lu quand eBay.com tombe, les ventes deja lues (45 jours) en secours, et le deal
n'est plus retire pour tout le monde a cause d'une panne. Aucun reseau."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues

vendues._cle = lambda: "test"
vendues._taux_usd_cad = lambda: 1.38
vendues._compter = lambda usage=None: None
vendues.INTERVALLE_MIN_S = 0
IT = lambda i, p: {"title": "1993-94 Topps Stadium Club Beam Team Michael Jordan #4", "soldPrice": p, "soldCurrency": "USD",
                   "endedAt": "2026-10-2%d" % i, "url": "https://www.ebay.com/itm/12345678%d" % i}
appels = []


def faux(q, site, attendre=True, usage=None, **k):
    appels.append(site)
    if site == "ebay.com" and MODE["com"] == "panne":
        return None, "SoldComps injoignable (TimeoutError)"
    if site == "ebay.ca" and MODE["ca"] == "panne":
        return None, "SoldComps injoignable (TimeoutError)"
    return {"items": [IT(1, 200), IT(2, 220), IT(3, 210)]}, None


vendues._appel = faux
MODE = {"com": "panne", "ca": "ok"}
r = vendues.rechercher("jordan beam team 4 stadium club", fond=False)
assert not r["erreur"] and len(r["ventes"]) == 3 and all(v["site"] == "ebay.ca" for v in r["ventes"]), r      # eBay.ca garde

# les deux sites en panne : les ventes deja lues (cache de plus de 3 jours, moins de 45) en secours
c = vendues._cx(); c.execute("UPDATE cache SET le=?", (time.time() - 10 * 86400,)); c.commit(); c.close()
MODE.update(com="panne", ca="panne")
r = vendues.rechercher("jordan beam team 4 stadium club", fond=False)
assert not r["erreur"] and r.get("vieux_cache") and len(r["ventes"]) == 3, r

# rien en cache : l'erreur ; un « Reessayer » 15 s plus tard reessaie vraiment (une panne n'est pas bloquee 10 min)
r = vendues.rechercher("autre carte jamais lue", fond=False)
assert r["erreur"] and "injoignable" in r["erreur"]
n0 = len(appels)
vendues._ERREURS["autre carte jamais lue"] = (time.time() - 540 - 20, r["erreur"])
MODE.update(com="ok", ca="ok")
r = vendues.rechercher("autre carte jamais lue", fond=False)
assert len(appels) > n0 and not r["erreur"] and r["ventes"], r

# la fiche : ventes pas lues -> la valeur du chasseur, et le deal n'est PAS retire
import deals, lockerroom, ebay_compte
deals._ecrire({"deals": [{"item_id": "999", "titre": "1993-94 Topps Stadium Club Beam Team Michael Jordan #4", "total": 211, "valeur": 420,
                          "ratio": 0.5, "encan": True, "port": 26, "mise_max": 268, "vu_le": "2026-11-03T10:00:00+00:00", "v": deals.VERSION}]})
ebay_compte.article = lambda iid, fond=False, frais=False: {"item_id": iid, "titre": "1993-94 Topps Stadium Club Beam Team Michael Jordan #4 Bulls",
                                               "prix_cad": 185, "port_cad": 26, "encan": True, "mises": 3, "fin": None, "photos": []}
ebay_compte.rechercher = lambda *a, **k: []
vendues.memes_annonce = lambda *a, **k: {"ventes": [], "nb": 0, "erreur": "SoldComps injoignable (TimeoutError)"}
vendues.autres_joueurs = lambda *a, **k: None
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
d = api.annonce_detail("999")
assert d["ventes_panne"] and d["valeur_chasseur"]["valeur"] == 420 and d["suggere"]["achat_max"] > 0 and d["valeur_source"] == "chasseur", d
assert any(str(x["item_id"]) == "999" for x in deals.lire()["deals"]), "le deal a ete retire a cause d'une panne"
print("ok ventes en panne")
