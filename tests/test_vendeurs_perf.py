"""12 nov 2026 (Mathieu : « quels vendeurs finissent le plus sous la mediane des last sold ? on passe leurs annonces
d'abord ; Savage, Remi et CF31 : pas de port ») : le rapport des vendeurs et l'ordre du chasseur."""
import os, sys, tempfile, json
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import chances, deals
E = {}
def ajout(v, n, ratio, port=10.0):
    for i in range(n):
        E[f"{v}{i}"] = {"fin": "2026-11-01T00:00:00Z", "mise_max": 60, "valeur": 100.0, "final": 100.0 * ratio, "port": port, "vendeur": v,
                        "vendeur_score": 50000, "recrue": False}
ajout("savage.cards", 20, 0.80, port=12)        # 80 % de la valeur, ramassage : pas de port
ajout("slabsharksinc", 20, 0.78, port=20)       # 78 % + 20 $ de port : plus cher pour nous que Savage
ajout("remi-card-trader", 3, 0.40)              # 3 encans seulement : pas assez pour bouger l'ordre
ajout("petit_bon", 12, 0.70, port=5)
ajout("probstein123", 30, 0.60)                 # une maison a volume reste en dernier
chances._ecrire({"encans": E, "stats": {}})
p = chances.perf_vendeurs(deals.RAMASSAGE_DEFAUT)["vendeurs"]
assert p["savage.cards"]["cout"] == 0.8 and p["savage.cards"]["ramassage"] and p["slabsharksinc"]["cout"] == 0.98, p
assert p["savage.cards"]["score"] < p["slabsharksinc"]["score"]
assert p["remi-card-trader"]["n"] == 3 and deals._perf("remi-card-trader") is None
o = deals.ordre_priorite()
assert o[0] == "savage.cards" and o[-1] == "slabsharksinc", o
assert deals.rang_ordre("probstein123") == 7.0 and deals.rang_ordre("petit_bon") < deals.rang_ordre("inconnu_total")
g = deals.groupes_vendeurs(["slabsharksinc", "savage.cards", "remi-card-trader", "cf31_sports_cards", "wests01"])
assert g[0] == ["savage.cards"], g
print("VENDEURS OK", o, {v: (x["n"], x["cout"], x["score"]) for v, x in p.items()})
