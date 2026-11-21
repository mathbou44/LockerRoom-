"""21 nov 2026 (vitesse) : la meme lecture lancee 3 fois au meme instant par la meme session = UN seul calcul ; une autre
session, un autre argument ou une ecriture = son propre calcul. Et l'indice d'un joueur ecrit autrement se trouve sans balayage."""
import os, sys, tempfile, threading, time
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI); os.chdir(ICI)
os.environ.update(LOCKERROOM_DONNEES=tempfile.mkdtemp(), LOCKERROOM_TACHES="0", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999")
import server
N = {"n": 0}
def lent(*a):
    N["n"] += 1; time.sleep(0.4); return {"ok": True, "n": N["n"], "a": list(a)}
server.api.inventaire_scores = lent
server.api.carte_sauver = lent                     # une ecriture : jamais partagee
R = []
def appel(nom, corps, cookie="s=1"):
    c = server.app.test_client()
    r = c.post("/api/" + nom, json=corps, headers={"Origin": "http://localhost", "User-Agent": "test " + cookie})
    R.append((nom, cookie, r.get_json()))
def lot(*jobs):
    R.clear(); N["n"] = 0
    T = [threading.Thread(target=appel, args=j) for j in jobs]
    [t.start() for t in T]; [t.join() for t in T]
lot(("inventaire_scores", []), ("inventaire_scores", []), ("inventaire_scores", []))
assert N["n"] == 1 and all(r[2]["n"] == 1 for r in R), (N, R)                      # 3 appels identiques : 1 calcul
lot(("inventaire_scores", [1]), ("inventaire_scores", [2]))
assert N["n"] == 2                                                                 # arguments differents
lot(("inventaire_scores", [], "s=1"), ("inventaire_scores", [], "s=2"))
assert N["n"] == 2                                                                 # sessions differentes
lot(("carte_sauver", [{}]), ("carte_sauver", [{}]))
assert N["n"] == 2                                                                 # ecritures : chacune la sienne
assert not server._VOLS and server.en_vol() == 0
def boum(*a):
    raise RuntimeError("x")
server.api.inventaire_scores = boum
c = server.app.test_client()
assert c.post("/api/inventaire_scores", json=[], headers={"Origin": "http://localhost"}).status_code == 500 and not server._VOLS
import indice_joueurs as ij
ij.lire = lambda: {"indice": {"Tim Stützle": {"indice": 77}, "Connor McDavid": {"indice": 99}}}
assert ij.indice("Connor McDavid")["indice"] == 99 and ij.indice("tim stutzle")["indice"] == 77 and ij.indice("Personne") is None
print("OK test_vitesse_partage")
