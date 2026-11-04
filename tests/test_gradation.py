"""3 nov 2026 (Mathieu : « assister l'utilisateur pour grader avec PSA ») : chances par note, service selon la valeur
declaree (apres gradation), gain attendu, seuil, verdict. Aucun reseau."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gradation

p = gradation.probas(9, 9)
assert abs(sum(p.values()) - 1) < 0.01 and max(p, key=p.get) == 9, p
p = gradation.probas(9.5, 10)
assert set(p) == {10, 9, 8} and p[10] > p[8], p
assert gradation.service(400)["nom"] == "Value" and gradation.service(1200)["nom"] == "Regular" and gradation.service(4000)["nom"] == "Super Express"
r = gradation.calculer(150, {10: {"valeur": 600, "n": 12}, 9: {"valeur": 260, "n": 20}, 8: {"valeur": 180, "n": 9}}, 9, 10, 1.38)
assert r["verdict"] == "oui" and r["gain"] > 0 and r["service"]["nom"] == "Value" and r["retour_prevu"], r
r = gradation.calculer(150, {10: {"valeur": 300, "n": 12}, 9: {"valeur": 170, "n": 20}, 8: {"valeur": 120, "n": 9}}, 8, 9, 1.38)
assert r["verdict"] == "non" and r["gain"] < 0, r
r = gradation.calculer(150, {9: {"valeur": 170, "n": 2}}, 9.5, 10, 1.38)
assert r["verdict"] == "pas_assez", r                         # pas de ventes en PSA 10 : on ne devine pas
r = gradation.calculer(100, {10: {"valeur": 400, "n": 8}, 9: {"valeur": 120, "n": 15}, 8: {"valeur": 80, "n": 6}}, 9, 9, 1.38)
assert r["seuil"] == 10 and r["verdict"] in ("pari_10", "non", "juste"), r
# 3 nov 2026 : TAG (la couverture n'est pas un plafond ; Value 10 cartes min, Base 5) ; taxes sur les frais PSA seulement
V = {10: {"valeur": 600, "n": 12}, 9: {"valeur": 260, "n": 20}, 8: {"valeur": 180, "n": 9}}
t = gradation.calculer(150, V, 9, 10, 1.38, compagnie="TAG")
assert t["compagnie"] == "TAG" and t["service"]["nom"] == "Standard" and not t["plafond"], t["service"]
nv = {n["nom"]: n for n in t["niveaux"]}
assert nv["Value"]["raison"] == "minimum" and nv["Base"]["raison"] == "minimum" and nv["Express"]["permis"]
assert gradation.service(3000, "TAG", 1)["nom"] == "Premier" and gradation.service(200, "TAG", 10)["nom"] == "Value"
t2 = gradation.calculer(150, {10: {"valeur": 9000, "n": 3}, 9: {"valeur": 7000, "n": 3}}, 9, 10, 1.38, compagnie="TAG")
assert all(n["permis"] for n in t2["niveaux"] if n["minimum"] == 1) and any(n["assure_moins"] for n in t2["niveaux"])
p1 = gradation.calculer(150, V, 9, 10, 1.38, compagnie="PSA", taxes_pct=14.975)
p0 = gradation.calculer(150, V, 9, 10, 1.38, compagnie="PSA")
assert p1["cout"] > p0["cout"] and p1["taxes_incluses"] and not gradation.calculer(150, V, 9, 10, 1.38, compagnie="TAG", taxes_pct=14.975)["taxes_incluses"]
os.environ["LR_PSA_TARIFS"] = '[["Test", 10, 5000, 5, 10]]'
assert gradation.service(100)["nom"] == "Test"
print("ok gradation")
