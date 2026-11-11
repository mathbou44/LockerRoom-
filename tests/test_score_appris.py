"""11 nov 2026 (Mathieu : « a toutes les semaines le modele reapprend ; toujours a jour, le marche change vite ») : le
pipeline du serveur (score_appris) : apprendre, exporter, noter avec la memoire du marche, la passe du jour, le garde-fou."""
import os
import sys
import tempfile
import random
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import numpy as np
import score_appris as sa
import score_modele as sm

rng = random.Random(4)
JOUEURS = {"Connor Bedard": 3.0, "Macklin Celebrini": 2.6, "Lane Hutson": 1.6, "Brock Nelson": 0.2, "Nick Suzuki": 0.8, "Matvei Michkov": 1.9}
CARTES = [("Upper Deck Young Guns #201", 2.5), ("O-Pee-Chee #45", 0.3), ("SP Authentic Future Watch Auto /999", 4.2),
          ("Upper Deck Series 1 base #12", 0.0), ("The Cup Rookie Patch Auto /249", 6.5), ("Upper Deck Canvas #C12", 1.2)]
d0 = date(2026, 8, 1)
V = []
for k in range(4000):
    j = rng.choice(list(JOUEURS)); c, v = rng.choice(CARTES)
    jour = d0 + timedelta(days=rng.randrange(70))
    hausse = 0.6 if j == "Lane Hutson" and jour > d0 + timedelta(days=55) else 0.0       # le marche bouge a la fin
    V.append((f"2024-25 {c.split('#')[0]}{j} {('#' + c.split('#')[1]) if '#' in c else ''} hockey", round(float(np.exp(0.7 + JOUEURS[j] + v + hausse + rng.gauss(0, 0.3))), 2), jour.isoformat()))
B, y, J = sa.preparer(V, base={}, indice={}, sport=None)
assert len(B) > 3500, len(B)
assert "bedard" not in B[0]["t"].lower() and "celebrini" not in B[0]["t"].lower()       # le texte sans le nom du joueur
coupe = (d0 + timedelta(days=60)).toordinal()
r = sa.entrainer(B, y, J, coupe=coupe, iters=150, log=lambda s: None)
assert r["mesure"]["precision"] > 0.9, r["mesure"]
print("OK apprendre", r["mesure"])
r2 = sa.entrainer(B, y, J, coupe=None, iters=150, log=lambda s: None)
sa.exporter(r2, meta={"mesure_garde_fou": r["mesure"]})
sm.recharger()
m = sm.charger()
assert m and m["source"] == "reappris" and m["v"] == 3
# le score : une RPA de la Cup de Bedard > une base de Nelson ; le prix n'est jamais un parametre
s = sm.scores(["2024-25 The Cup Rookie Patch Auto Connor Bedard /249", "2024-25 Upper Deck Series 1 base Brock Nelson #12"])
assert s[0] > s[1], s
# l'export (numpy) == scikit-learn sur les memes caracteristiques
Xm = sa.caracteristiques(B[-50:], lambda t: sm.vec_car(t, m), aujourdhui=date.fromordinal(int(J.max()) + 1), xv=True)
assert np.isfinite(Xm[:, 0]).mean() > 0.9 and np.isfinite(Xm[:, -1]).mean() > 0.9
# le modele exporte (numpy) == le moteur d'apprentissage, sur les memes lignes
Xa = r2["_X"][-50:]
Xa = Xa.toarray() if hasattr(Xa, "toarray") else Xa
assert float(np.max(np.abs(sm._arbres(m["z"], Xa.astype(float)) - r2["_pred"](r2["_X"][-50:])))) < 1e-6
# au service, les memes caracteristiques que l'apprentissage pour une vente deja connue (sauf sa propre journee)
p_serv = sm.predire(B[-5:])
assert p_serv is not None and np.all(np.isfinite(p_serv))
print("OK exporter et noter", s)

# la passe du jour : les ventes d'hier entrent dans la memoire ; les scores de Hutson montent si le marche monte
t_h = "2024-25 Upper Deck Canvas Lane Hutson #C12"
dern = date.fromordinal(int(J.max()))
avant = sm.score(t_h)
neuves = [(t_h, 400.0, (dern + timedelta(days=1)).isoformat())] * 6
st = sa.passe_jour(ventes=neuves, aujourdhui=dern + timedelta(days=2))
assert st["ok"] and st["ajoutees"] == 6, st
apres = sm.score(t_h)
assert apres >= avant, (avant, apres)
assert sa.passe_jour(ventes=neuves, aujourdhui=dern + timedelta(days=2))["ajoutees"] == 0          # jamais deux fois
print("OK passe du jour", avant, "->", apres)

# le garde-fou : trop peu de ventes -> l'ancien modele reste ; et rien ne se lance de jour
e = sa.reapprendre(ventes=V[:500])
assert e["accepte"] is False and "pas assez" in e["raison"]
from datetime import datetime
out = sa.taches_si_besoin(maintenant=datetime(2026, 11, 11, 14, 0))
assert "reapprendre" not in out
assert sa.statut()["actif"] and sa.historique()["essais"][-1]["accepte"] is False
print("OK garde-fou")

# l'apprentissage et le service calculent la memoire de la MEME facon : apprendre jusqu'a la veille, exporter, puis lire
# les ventes du dernier jour au service ; les poids (combien de ventes, depuis quand) doivent etre identiques
import tempfile as _tf
L_ = int(J.max())
av = J < L_
r3 = sa.entrainer([b for b, a in zip(B, av) if a], y[av], J[av], coupe=None, iters=60, log=lambda s: None)
dest = _tf.mkdtemp() + "/m"
sa.exporter(r3, dest=dest)
vrai_d = sa.dossier
sa.dossier = lambda: dest
sm.recharger()
m3 = sm.charger()
jourL = [b for b, a in zip(B, J == L_) if a]
Xs_ = sa.caracteristiques(jourL, lambda t: sm.vec_car(t, m3), aujourdhui=date.fromordinal(L_), xv=True)
r4 = sa.entrainer(B, y, J, coupe=None, iters=60, log=lambda s: None)
nnum = len(sm.numeriques(B[0], ({}, {}))) + (len(sm.NOMS2) if sa.EXTRA else 0)
deb = 1 + nnum + 64
Xa_ = r4["_X"].toarray() if hasattr(r4["_X"], "toarray") else r4["_X"]
Xa_ = Xa_[J == L_][:, deb:deb + len(sa.NOMS_MEM)]
cols = [k for k, nm in enumerate(sa.NOMS_MEM) if "_w" in nm or nm.endswith("_age")]
ecart = np.nanmax(np.abs(Xa_[:, cols] - Xs_[:, cols]))
assert ecart < 1e-3, ecart
sa.dossier = vrai_d
sm.recharger()
print("OK apprentissage = service (memoire)", float(ecart))

# un nouveau modele ecrit par le processus de la nuit est recharge tout seul par les travailleurs du serveur
import time as _t
sm.recharger()
m_a = sm.charger()
sa.exporter(r2, meta={})
os.utime(os.path.join(sa.dossier(), "modele.npz"), (_t.time() + 5, _t.time() + 5))
sm._M["vu_le"] = 0
m_b = sm.charger()
assert m_b is not m_a and m_b["source"] == "reappris"
print("OK rechargement du modele")

# le processus de la nuit tourne en script (toutes les fonctions definies avant le lancement) et note ses erreurs
import subprocess
pr = subprocess.run([sys.executable, sa.__file__, "reapprendre"], cwd=os.path.dirname(sa.__file__), capture_output=True, text=True,
                    env={**os.environ, "LOCKERROOM_DONNEES": comptes.DONNEES}, timeout=300)
assert pr.returncode == 0, pr.stderr[-500:]
assert sa.historique()["essais"][-1]["accepte"] is False                     # pas de base_ventes ici : refuse proprement
print("OK processus de la nuit", sa.historique()["essais"][-1].get("raison"))
