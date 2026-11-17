"""17 nov 2026 : la cote marche des joueurs (cote_marche) : moyenne 90 j, liquidite, tendance de la MEME carte, lettres."""
import os, sys, tempfile, json
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from datetime import datetime, timedelta
import cote_marche as cm
import bareme_iq as b

m = datetime(2026, 11, 17)
j = lambda d: (m - timedelta(days=d)).strftime("%Y-%m-%d")
rows = []
# Fort : cher et souvent vendu, en hausse (la meme YG : 100 $ il y a 60 jours, 130 $ cette semaine)
for t in ("2024-25 Upper Deck Young Guns Lane Hutson #201", "2024-25 Upper Deck Young Guns Canvas Lane Hutson #C201",
          "2024-25 SP Authentic Future Watch Lane Hutson /999"):
    for d in range(1, 80, 6):
        rows.append((t, 130.0 if d < 30 else 100.0, j(d)))
# Moyen : peu cher, peu vendu
for d in range(1, 80, 8):
    rows.append((f"2024-25 Upper Deck Young Guns Brendan Smith #222", 4.0, j(d)))
for d in range(1, 80, 4):
    rows.append((f"2024-25 Upper Deck Young Guns Cole Caufield #210", 40.0, j(d)))
r = cm.calculer(rows, maintenant=m)
J = r["joueurs"]
assert set(J) >= {"Lane Hutson", "Cole Caufield"}, J.keys()
h = J["Lane Hutson"]
assert h["n"] == 42 and h["tendance_pct"] == 30 and h["cartes_suivies"] == 3 and h["par_semaine"] == round(42 / (90 / 7), 1), h
assert cm.ORDRE.index(h["lettre"]) <= cm.ORDRE.index(J["Cole Caufield"]["lettre"])       # le plus fort : la meilleure lettre
assert cm.ORDRE.index(h["lettre_liquidite"]) <= cm.ORDRE.index(J["Cole Caufield"]["lettre_liquidite"])
# la cote marche decide la note du joueur (sauf une cote d'expert) quand il a assez de ventes
json.dump(r, open(os.path.join(comptes.DONNEES, "cote_marche.json"), "w"))
cm._MEMO["d"] = None
assert b.note_joueur("Lane Hutson")[2] == "expert"                 # l'expert passe toujours avant
x = {"joueurs": {"Joueur Test": {"n": 30, "lettre": "A-"}}}
json.dump(x, open(os.path.join(comptes.DONNEES, "cote_marche.json"), "w")); cm._MEMO["d"] = None
assert b.note_joueur("Joueur Test")[1:] == ("A-", "marche")
x["joueurs"]["Joueur Test"]["n"] = 5
json.dump(x, open(os.path.join(comptes.DONNEES, "cote_marche.json"), "w")); cm._MEMO["d"] = None
assert b.note_joueur("Joueur Test")[2] != "marche"               # trop peu de ventes : la cote marche ne decide pas
# le balayage SoldComps : seulement SES cartes de hockey ; le rythme vient des jours couverts quand on est au plafond (240)
items = [{"title": "2024-25 Upper Deck Young Guns Lane Hutson #201 Canadiens", "soldPrice": 100, "soldCurrency": "CAD",
          "endedAt": f"2026-11-{10 + i % 5:02d}T10:00:00", "seller": {"username": f"v{i % 7}"}} for i in range(240)]
items[0]["title"] = "2025 Panini Score Cam Ward Rookie Titans"              # un autre sport : ecarte
items[1]["title"] = "2024-25 Upper Deck Young Guns Cole Hutson #202"        # un autre joueur : ecarte
g, m_ = cm.mesurer_joueur("Lane Hutson", items, 1.0)
assert m_["n"] == 238 and m_["plafond"] and m_["jours_couverts"] == 5 and m_["vendeurs"] == 7, m_
assert m_["par_semaine"] == round(238 / 5 * 7, 1)
print("COTE MARCHE OK")
