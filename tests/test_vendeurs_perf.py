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
# 25 nov 2026 (Mathieu : « les vendeurs pour lesquels les ventes bien en dessous des last sold sortent le plus souvent ») : la part
# des VRAIES aubaines, port compris : fini a 70 % ou moins de la valeur, et a la moitie ou moins ; pour tous les vendeurs vus
E2 = dict(E)
for i in range(4):
    E2[f"mix{i}"] = {"fin": "2026-11-01T00:00:00Z", "mise_max": 60, "valeur": 100.0, "final": (40.0, 60.0, 62.0, 95.0)[i], "port": 5.0, "vendeur": "mix",
                     "vendeur_score": 900, "recrue": False}
chances._ecrire({"encans": E2, "stats": {}}); chances._MEM.update(v=None, mtime=None); chances._PERF.update(cle=None, v=None)
p2 = chances.perf_vendeurs(deals.RAMASSAGE_DEFAUT)["vendeurs"]
assert (p2["mix"]["aubaines"], p2["mix"]["moitie"], p2["mix"]["sous_70"], p2["mix"]["sous_50"]) == (3, 1, 0.75, 0.25), p2["mix"]      # 45, 65, 67, 100 avec le port
assert p2["savage.cards"]["aubaines"] == 0 and p2["probstein123"]["aubaines"] == 30 and p2["probstein123"]["moitie"] == 0, p2["probstein123"]   # 60 + 10 de port = 70 %
assert p2["petit_bon"]["sous_70"] == 0.0                                                    # 70 + 5 de port : 75 %, pas une aubaine
app = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "src_app.html"), encoding="utf-8").read()
assert "(b.sous_70 || 0) - (a.sous_70 || 0)" in app and "tt('d’aubaines', 'bargains')" in app and "tt('à moitié prix', 'at half price')" in app
# 25 nov 2026 : un vendeur pas suivi n'a que ses deals dans l'archive : montre a part, jamais classe avec les suivis
assert "x.n >= r.n_min && x.suivi" in app and "Part gonflée, pas comparable." in app and "suivis ou non" not in app
# 25 nov 2026 (Mathieu : « Minting, est-ce qu'on les regarde ? ») : Mintink suivi, et ajoute aux listes deja reglees
assert "mintink" in deals.VENDEURS_DEFAUT and "mintink" not in deals.VENDEURS_PRIORITE and deals.rang_vendeur("mintink") == 4
assert any("mintink" in g for g in deals.groupes_vendeurs())
print("VENDEURS OK", o, {v: (x["n"], x["cout"], x["score"]) for v, x in p.items()})
