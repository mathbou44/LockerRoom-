"""27 nov 2026 (Mathieu : « notre modele doit apprendre [...] avec toutes les variables intrants » ; « il faut une maniere de valider
si ces modifications sont bonnes ou mauvaises ; une version qui roule en arriere de la nouvelle ; si elle est bonne, elle la
remplace une fois validee ; on serait un peu en arriere, mais tout le temps bon ; il faudrait juste une maniere de tester ca » ;
« on garde ca dans admin jusqu'a temps qu'on ait prouve son fonctionnement »). Le modele de prix (modele_prix.py) : la table sans
jamais regarder la suite, champion et aspirant, la reserve qui reprend sa place, et le PIEGE.   python tests/test_modele_prix.py"""
import math, os, sys
import numpy as np
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import modele_prix as mp
from datetime import date, timedelta
d = lambda s: date.fromisoformat(s)

# ---- 1. la table ne regarde JAMAIS la suite : une carte qui double apres le 2 mars a le meme prix du moment
K = ("cutter gauthier", "cutter gauthier young guns", 2024, None, "212")
avant = [(K, "raw", (d("2026-03-02") - timedelta(days=k)).isoformat(), 20.0) for k in (2, 6, 11, 17, 25, 40, 70)]
apres = [(K, "raw", (d("2026-03-02") + timedelta(days=k)).isoformat(), 40.0) for k in (0, 1, 20, 25, 30, 50, 55, 60)]
L1 = mp.panneau(mp.cartes(avant), ["2026-03-02"], cibles=False)
L2 = mp.panneau(mp.cartes(avant + apres), ["2026-03-02"])
assert len(L1) == len(L2) == 1
for v in mp.VARIABLES2:
    a, b = L1[0][v], L2[0][v]
    assert (math.isnan(a) and math.isnan(b)) or a == b, (v, a, b)
assert abs(L2[0]["p0"] - math.log(20)) < 1e-9 and abs(L2[0]["y30"] - math.log(2)) < 1e-9 and abs(L2[0]["y60"] - math.log(2)) < 1e-9
assert "y30" not in L1[0]
# trop peu de ventes : pas de ligne ; la cible demande 3 ventes dans sa fenetre
assert mp.panneau(mp.cartes(avant[:2]), ["2026-03-02"]) == []
L3 = mp.panneau(mp.cartes(avant + apres[:3]), ["2026-03-02"])
assert L3 and math.isnan(L3[0]["y30"]) and math.isnan(L3[0]["y60"]), "2 ventes seulement dans la fenetre : pas de cible"
# le joueur : ses AUTRES cartes seulement
K2 = ("cutter gauthier", "cutter gauthier young guns canvas", 2024, None, "c212")
autre = [(K2, "raw", (d("2026-03-02") - timedelta(days=k)).isoformat(), p) for k, p in ((3, 30), (9, 30), (20, 30), (35, 15), (50, 15), (80, 15))]
L4 = {x["cle"][1]: x for x in mp.panneau(mp.cartes(avant + autre), ["2026-03-02"], cibles=False)}
assert abs(L4["cutter gauthier young guns"]["j_pente"] - math.log(2)) < 1e-9, "la pente de l'AUTRE carte du joueur"
assert abs(L4["cutter gauthier young guns canvas"]["j_pente"] - L4["cutter gauthier young guns"]["pente"]) < 1e-9

# ---- 2. un modele apprend un vrai motif et bat « le prix ne bouge pas » ; ecrit en texte (jamais de pickle)
rng = np.random.default_rng(3)
def lignes(n, motif=True):
    L = []
    for _ in range(n):
        x = {v: float(rng.normal()) for v in mp.VARIABLES2}
        y = (0.5 * x["pente"] if motif else 0.0) + float(rng.normal(0, 0.15))
        x.update(y30=y, y60=y, note=0)
        L.append(x)
    return L
app, te = lignes(6000), lignes(3000)
m = mp.apprendre(app, 30, arbres=300)
assert isinstance(m["texte"], str) and m["texte"].startswith("tree") and mp.lire(mp.ecrire(m))["texte"] == m["texte"]
y = np.array([x["y30"] for x in te])
p = mp.predire(mp.lire(mp.ecrire(m)), te)
b = mp.bilan(p, y)
assert b["gain_vs_zero"] > 0.2 and b["bon_sens"] > 0.9, b
assert m["retrecir"] == mp.RETRECIR == 0.75 and m["variables"] == mp.VARIABLES2, "la version retenue par la serie d'essais du 27 nov"
assert np.abs(mp.predire(m, [{**te[0], "pente": 99.0}])).max() <= mp.BORNE, "une prediction est bornee"

# ---- 3. decider : assez de predictions, assez mieux, et PROUVE au tirage ; le PIEGE est refuse
z = mp.erreurs(np.zeros(len(y)), y)
e_m = mp.erreurs(p, y)
assert mp.decider(z, e_m)["promu"], "un vrai modele remplace « ne bouge pas »"
assert not mp.decider(e_m, z)["promu"], "et jamais l'inverse"
piege = mp.predire({"bruit": 0.3, "graine": 1}, te)
r = mp.decider(z, mp.erreurs(piege, y))
assert not r["promu"] and "pas assez mieux" in r["raison"], ("PIEGE : une version mauvaise expres doit etre refusee", r)
r = mp.decider(z[:500], e_m[:500])
assert not r["promu"] and "seulement 500" in r["raison"], r
r = mp.decider(e_m, e_m * 0.99)                                     # 1 % mieux : pas assez (il faut 3 %)
assert not r["promu"] and "pas assez mieux" in r["raison"]
ch_, asp_ = np.array([1.0, 0.0] * 600), np.array([0.0, 0.94] * 600)   # 6 % mieux en moyenne, mais tout se joue sur la moitie des
r = mp.decider(ch_, asp_)                                               # cartes ou il perd beaucoup : pas prouve au tirage
assert not r["promu"] and "pas prouve" in r["raison"] and r["gain"] > 0.03, r
assert mp.N_MIN == 1000 and mp.GAIN_MIN == 0.03, "la regle mesuree au banc du 27 nov (jamais pire que la regle, nulle part)"

# ---- 4. le tour, par segment : au depart partout « ne bouge pas » ; un modele prouve prend SON segment ; la reserve reprend
E = mp.etat_initial()
assert set(E) == {"30-raw", "30-gradee", "60-raw", "60-gradee"} and all(e["champion"] == mp.ZERO and e["reserve"] is None for e in E.values())
assert mp.segment({"note": 0}, 30) == "30-raw" and mp.segment({"note": 2}, 60) == "60-gradee"
E2, dec = mp.tour(E, {"30-raw": {mp.ZERO: z, "m1": e_m}, "60-raw": {mp.ZERO: z, "piege": mp.erreurs(piege, y)}}, le="2026-04")
assert E2["30-raw"]["champion"] == "m1" and E2["30-raw"]["reserve"] == mp.ZERO and E2["30-raw"]["historique"][-1]["a"] == "m1"
assert E2["60-raw"]["champion"] == mp.ZERO, "le piege ne prend rien"
assert E["30-raw"]["champion"] == mp.ZERO, "l'etat d'avant n'est pas modifie"
# le nouveau champion faiblit : la reserve (l'ancien) le bat de facon prouvee -> elle reprend sa place
E3, dec = mp.tour(E2, {"30-raw": {"m1": mp.erreurs(piege, y), mp.ZERO: z}}, le="2026-05")
assert E3["30-raw"]["champion"] == mp.ZERO and E3["30-raw"]["reserve"] == "m1" and any(x.get("reserve") and x["promu"] for x in dec)
# deux aspirants : le meilleur gagne
e_m2 = mp.erreurs(p * 0.5, y)
E4, _ = mp.tour(E, {"30-raw": {mp.ZERO: z, "m2": e_m2, "m1": e_m}})
assert E4["30-raw"]["champion"] == "m1"
print("MODELE DE PRIX OK")
