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

# 21 nov 2026 (2e suivi) : le gardien s'annonce, se relance dans le processus courant et echantillonne les requetes courtes
import inspect as _i
_s = _i.getsource(server._gardien_piles)
assert "Gardien des piles : actif" in _s and "Pile : " in _s and "Pile lente : " in _s, "le gardien doit s'annoncer et echantillonner"
assert "pass" not in _s.split("except Exception")[1][:40], "une erreur du gardien ne doit plus etre avalee"
assert "_gardien_assurer()" in _i.getsource(server._chrono_debut)
assert server._pile_lisible(_i.currentframe()).startswith("test_vitesse_partage.py:")
print("OK gardien des piles")

# 21 nov 2026 (2e suivi) : sur Render, gunicorn precharge l'app dans le maitre ; le worker (copie sans les fils) se rechauffe
# lui-meme a sa premiere requete, une seule fois par processus ; le processus qui a lance les taches ne le refait pas
import os as _os
assert "_worker_assurer()" in _i.getsource(server._chrono_debut)
assert '_CHAUD["pid"] = os.getpid()' in _i.getsource(server.demarrer_taches)
# 21 nov 2026 (3e suivi) : le worker rechauffe aussi ses breaks (le calcul est garde en memoire, par processus), sans jamais
# passer devant un client
_srw = _i.getsource(server._rechauffer_worker)
assert "analyse_break" in _srw and "_attendre_calme" in _srw and "[:12]" in _srw
_lances = []
_vrai, server._rechauffer_worker = server._rechauffer_worker, (lambda: _lances.append(1))
try:
    server._CHAUD["pid"] = _os.getpid()
    server._worker_assurer(); assert not _lances, "deja rechauffe dans ce processus : rien a relancer"
    server._CHAUD["pid"] = -1                    # comme dans un worker copie du maitre (autre pid)
    server._worker_assurer(); server._worker_assurer()
    import time as _t
    _t.sleep(0.2)
    assert _lances == [1] and server._CHAUD["pid"] == _os.getpid(), _lances
finally:
    server._rechauffer_worker = _vrai
print("OK rechauffage du worker")
