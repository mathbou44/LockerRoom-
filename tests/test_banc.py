"""10 nov 2026 : le banc de validation (backtest honnete, notes A+ a F, recette adoptee si meilleure)."""
import os
import random
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from datetime import datetime, timedelta
import base_ventes
import banc
import deals

rnd = random.Random(3)
c = base_ventes._cx()
joueurs = ["Connor Bedard", "Macklin Celebrini", "Ivan Demidov", "Matvei Michkov", "Lane Hutson", "Logan Cooley"] * 30
for i, j in enumerate(joueurs):
    cible = f"2023-24 upper deck young guns {j.lower()} #{i}"
    q = f"{j.lower()} young guns {i}"
    c.execute("INSERT OR REPLACE INTO plan (cible, q, joueur) VALUES (?,?,?)", (cible, q, j))
    base = rnd.uniform(20, 200)
    for k in range(10):
        le = (datetime.now() - timedelta(days=80 - k * 8)).strftime("%Y-%m-%d")
        p = round(base * rnd.uniform(0.9, 1.1), 2)
        c.execute("INSERT OR REPLACE INTO ventes VALUES (?,?,?,?,?,?,?,?,?)",
                  (q, f"u{i}-{k}", f"2023-24 Upper Deck Young Guns {j} #{i}", p, le, None, f"https://www.ebay.com/itm/{10**11 + i * 100 + k}", 0, le))
c.commit(); c.close()
import cartes_match
_orig = cartes_match.cible
def _cible(t):                       # base de test vide : le joueur est donne (en ligne, le catalogue le reconnait)
    d = _orig(t)
    for j in set(joueurs):
        if j.lower() in str(t).lower():
            d = dict(d, joueur=j.lower())
    return d
cartes_match.cible = _cible
cartes = banc._cartes()
assert len(cartes) >= 100, len(cartes)
v = banc.valider_valeur(cartes)
assert v["cartes"] >= 100 and v["recettes"]["en_place"]["dans25"] >= 0.9, v["recettes"]["en_place"]
assert banc.note(98) == "A+" and banc.note(85) == "B" and banc.note(10) == "F"
r = banc.passe()
assert r["notes"]["valeur"] in ("A+", "A", "A-"), r["scores"]
assert banc.resume()["note"]
# la regle de deals lit la recette adoptee (ici : aucune, ou une variante valide)
assert deals.valeur_sure([{"titre": "x", "prix": 10, "le": datetime.now().strftime("%Y-%m-%d")}] * 1)[0] is None
print("OK banc", r["note_globale"], r["scores"])
