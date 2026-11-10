"""10 nov 2026 (Mathieu : « si un joueur a 6 buts cette semaine il tombe tres haut ; les effets legendes ») : l'Indice
joueur de la semaine, fait de stats et de donnees publiques seulement."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
from datetime import date, timedelta
import indice_joueurs as ij


def st(an, mj, b, a):
    return {"saison": an, "partie": "Season", "stats": {"Total Games Played": mj, "Total Goals": b, "Total Assists": a, "Total Points": b + a}}


# 1. la semaine = la difference des totaux de saison notes chaque jour ; une nouvelle saison ne compte pas
d = {"joueurs": {}}
j0, j7 = (date.today() - timedelta(days=7)).isoformat(), date.today().isoformat()
ij.noter_jour(d, "Feu Joueur", {"saisons": [st(2026, 60, 20, 30), st(2027, 10, 3, 4)]}, j0)
ij.noter_jour(d, "Feu Joueur", {"saisons": [st(2026, 60, 20, 30), st(2027, 14, 9, 6)]}, j7)
f = ij.forme_semaine(d["joueurs"]["Feu Joueur"])
assert f == {"mj": 4, "b": 6, "a": 2, "pts": 8, "jours": 7}, f
assert d["joueurs"]["Feu Joueur"]["avant_ppm"] == round(50 / 60, 3)
ij.noter_jour(d, "Calme", {"saisons": [st(2027, 10, 1, 1)]}, j0)
ij.noter_jour(d, "Calme", {"saisons": [st(2027, 14, 1, 2)]}, j7)
assert ij.forme_semaine({"jours": {j0: {"an": 2026, "mj": 80, "pts": 70}, j7: {"an": 2027, "mj": 2, "pts": 1}}}) is None
print("OK indice semaine")

# 2. le classement : 6 buts cette semaine = tout en haut ; une legende garde un plancher ; un retire reste sous le feu
base = {"Feu Joueur": {"nhl": {"actif": True, "equipe": "MTL", "saisons": 5}, "wiki": {"v60": 3000, "v20": 2500}},
        "Calme": {"nhl": {"actif": True, "equipe": "TOR", "saisons": 6}, "wiki": {"v60": 3000, "v20": 1000}},
        "Grand Legende": {"nhl": {"actif": False, "hhof": True, "top100": True, "trophees_c": {"Hart Memorial Trophy": 4, "Stanley Cup": 4},
                                  "carriere": {"points": 2857}}, "wiki": {"v60": 90000, "v20": 30000}},
        "Vieux Capitaine": {"nhl": {"actif": True, "equipe": "PIT", "saisons": 21, "top100": True, "l5": 1,
                                    "trophees_c": {"Stanley Cup": 3, "Art Ross Trophy": 2}, "carriere": {"points": 1700}}, "wiki": {"v60": 60000, "v20": 20000}},
        "Recrue Neuve": {"nhl": {"actif": True, "equipe": "SJS", "saisons": 1, "l5": 3}, "wiki": {"v60": 8000, "v20": 4000}}}
for i in range(20):                                      # des joueurs ordinaires pour que les rangs veuillent dire quelque chose
    base[f"Joueur {chr(65 + i)}"] = {"nhl": {"actif": True, "equipe": "BOS", "saisons": 4, "l5": i % 4}, "wiki": {"v60": 500 + i * 10, "v20": 160}}
I = ij.calculer(d, base, lambda n: {"Grand Legende": 9, "Vieux Capitaine": 6}.get(n, 1))
ordre = sorted(I, key=lambda n: -I[n]["indice"])
assert ordre[0] == "Feu Joueur" and "en_feu" in I["Feu Joueur"]["pastilles"], [(n, I[n]["indice"]) for n in ordre[:5]]
assert I["Feu Joueur"]["semaine"]["b"] == 6
assert "legende" in I["Grand Legende"]["pastilles"] and not I["Grand Legende"]["actif"]
assert I["Vieux Capitaine"]["indice"] >= 55 and "legende" in I["Vieux Capitaine"]["pastilles"]
assert I["Grand Legende"]["indice"] < I["Feu Joueur"]["indice"]
assert "recrue" in I["Recrue Neuve"]["pastilles"]
assert I["Calme"]["indice"] < I["Feu Joueur"]["indice"]
print("OK indice classement")

# 3. la passe du jour : Highlightly lu dans la limite du quota, puis l'indice ecrit ; top() et indice()
import demande_legale
import highlightly
demande_legale.lire = lambda: {"joueurs": base}
demande_legale.demande = lambda n: 1
highlightly.actif = lambda: True
highlightly.plafond_jour = lambda: 10
compte = {"n": 0}
highlightly.utilisees = lambda: compte["n"]


def stats_joueur(nom, sport="hockey"):
    compte["n"] += 2
    return {"saisons": [st(2027, 12, 2, 3)]}


highlightly.stats_joueur = stats_joueur
r = ij.passe()
assert r["lus"] == 3 and compte["n"] == 6, (r, compte)                 # 10 - 4 gardes pour l'essai admin = 6 appels
assert ij.indice("feu joueur") and ij.top(3)[0]["indice"] >= ij.top(3)[-1]["indice"]
assert ij.statut()["lus_aujourdhui"] == 3
print("OK indice passe")

# 4. les nouvelles de la semaine : un joueur nomme dans un evenement (trophee, rappel, record) monte et prend « actu »
import nouvelles
aujourd = date.today().isoformat()
nouvelles.lire_cache = lambda: {"sports": {"hockey": [
    {"titre": "Feu Joueur named NHL player of the week after hat trick", "lien": "https://x/1", "date": aujourd},
    {"titre": "Calme Joueur recalled from AHL", "lien": "https://x/2", "date": aujourd}]}}
base["Calme Joueur"] = {"nhl": {"actif": True, "equipe": "TOR", "saisons": 1, "l5": 0}, "wiki": {"v60": 600, "v20": 200}}
I2 = ij.calculer({"joueurs": {}}, base, lambda n: 1)
assert "actu" in I2["Calme Joueur"]["pastilles"] and I2["Calme Joueur"]["actu"][0]["lien"] == "https://x/2", I2["Calme Joueur"]
print("OK indice actu")
