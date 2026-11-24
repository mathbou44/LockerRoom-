"""24 nov 2026 (vitesse du Radar ; journal de production : deux « Radar (temps) : 20 s » finis a la meme seconde). L'accueil et
le Radar demandaient le meme calcul au meme moment : deux fois les memes recherches eBay sur un seul serveur. Un seul
calcul a la fois par compte ; le deuxieme attend et recoit une copie ; un echec ou un retard ne bloque personne."""
import os, sys, tempfile, threading, time
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lockerroom
from lockerroom import Api
a = Api(os.path.join(tempfile.mkdtemp(), "a.db"))
b = Api(os.path.join(tempfile.mkdtemp(), "b.db"))
n = {"appels": 0}
def lent(self, frais=False):
    n["appels"] += 1
    time.sleep(0.6)
    return {"ok": True, "deals": [{"item_id": "1", "titre": "Carte"}], "qui": self.chemin_db, "no": n["appels"]}
Api._mes_deals1 = lent
# 1. deux demandes du MEME compte en meme temps : un seul calcul, le meme Radar pour les deux, chacun sa copie
res = {}
def demander(nom, api, apres=0.0):
    time.sleep(apres); t0 = time.time(); res[nom] = (api.mes_deals(), time.time() - t0)
T = [threading.Thread(target=demander, args=("accueil", a)), threading.Thread(target=demander, args=("radar", a, 0.15))]
[t.start() for t in T]; [t.join() for t in T]
assert n["appels"] == 1, n
r1, r2 = res["accueil"][0], res["radar"][0]
assert r1 == r2 and r1 is not r2 and r1["deals"] is not r2["deals"]             # une copie : personne ne modifie le Radar de l'autre
assert res["radar"][1] < 0.6                                                    # le deuxieme n'a pas refait le calcul
assert not Api._RADAR_UN                                                  # rien ne reste en attente
# 2. deux comptes differents : chacun son calcul, en parallele
n["appels"] = 0
T = [threading.Thread(target=demander, args=("a", a)), threading.Thread(target=demander, args=("b", b, 0.05))]
t0 = time.time(); [t.start() for t in T]; [t.join() for t in T]
assert n["appels"] == 2 and res["a"][0]["qui"] != res["b"][0]["qui"] and time.time() - t0 < 1.1
# 3. une demande apres la fin : un nouveau calcul (rien n'est garde ici ; la copie de 10 min est ailleurs)
a.mes_deals()
assert n["appels"] == 3
# 4. le premier echoue : le deuxieme calcule lui-meme, et l'erreur du premier reste la sienne
def casse(self, frais=False):
    n["appels"] += 1
    time.sleep(0.3)
    if n["appels"] == 4:
        raise RuntimeError("eBay injoignable")
    return {"ok": True, "deals": [], "no": n["appels"]}
Api._mes_deals1 = casse
def essayer(nom, apres=0.0):
    time.sleep(apres)
    try:
        res[nom] = a.mes_deals()
    except RuntimeError as e:
        res[nom] = "erreur : " + str(e)
T = [threading.Thread(target=essayer, args=("un",)), threading.Thread(target=essayer, args=("deux", 0.1))]
[t.start() for t in T]; [t.join() for t in T]
assert res["un"] == "erreur : eBay injoignable" and res["deux"]["ok"] and res["deux"]["no"] == 5, res
assert not Api._RADAR_UN
# 5. le premier tarde trop : le deuxieme n'attend pas plus que la limite
Api.RADAR_ATTENTE_S = 0.2
def tres_lent(self, frais=False):
    n["appels"] += 1; time.sleep(0.7); return {"ok": True, "deals": [], "no": n["appels"]}
Api._mes_deals1 = tres_lent
n["appels"] = 0
T = [threading.Thread(target=demander, args=("p", a)), threading.Thread(target=demander, args=("q", a, 0.05))]
[t.start() for t in T]; [t.join() for t in T]
assert n["appels"] == 2 and not Api._RADAR_UN
print("OK test_radar_un_calcul")
