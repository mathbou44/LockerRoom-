"""25 nov 2026 (Mathieu, Bedard opere a l'epaule, absent 4 mois : « il devrait avoir le badge injured, non ? ») : une blessure dure
plus longtemps que sa manchette. L'etat « blesse » du joueur tient jusqu'a la date dite par la manchette (ou un defaut), tombe
quand une manchette annonce son retour ou qu'il rejoue ; la pastille passe en premier (la tuile du Radar en montre une seule)."""
import os, sys, tempfile
from datetime import date, timedelta
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import indice_joueurs as ij

J = date(2026, 11, 25)
D = lambda t, le=J: ij.duree_blessure(t, le)
# la duree que dit la manchette (la borne haute), en anglais et en francais
assert D("Bedard out four months for Blackhawks following shoulder surgery") == (120, True)
assert D("Connor Bedard opéré à l'épaule, absent quatre mois") == (120, True)
assert D("Matthews expected to miss 4-6 weeks with upper-body injury") == (42, True)
assert D("Hutson absent de six à huit semaines") == (56, True)
assert D("Barkov to miss 10 days") == (10, True)
assert D("Landeskog suffers season-ending knee injury") == ((date(2027, 6, 30) - J).days, True)
assert D("Makar is week-to-week with a lower-body injury") == (14, False)
assert D("Pettersson day-to-day") == (3, False)
assert D("Crosby out indefinitely after surgery") == (30, False)
assert D("McDavid leaves game with injury") == (ij.BLESSURE_DEFAUT_J, False)

INFO = {"Connor Bedard": {"actif": True, "equipe": "CHI"}, "Quinn Hughes": {"actif": True, "equipe": "VAN"},
        "Jack Hughes": {"actif": True, "equipe": "NJD"}, "Auston Matthews": {"actif": True, "equipe": "TOR"},
        "Cale Makar": {"actif": True, "equipe": "COL"}}
N = lambda t, le: {"titre": t, "date": le, "lien": "https://exemple.test/a"}
# le nom de famille seul : unique chez les actifs ET son equipe dans la manchette ; jamais un homonyme
d = {}
b = ij.suivre_blessures(d, [N("Bedard out four months for Blackhawks following shoulder surgery", "2026-11-24"),
                            N("Hughes leaves game with upper-body injury for Devils", "2026-11-24"),
                            N("Makar injured? Not so fast", "2026-11-24")], INFO, aujourdhui=J)
assert set(b) == {"Connor Bedard"}, b                                  # Hughes : deux joueurs ; Makar : pas d'equipe dans le titre
assert b["Connor Bedard"]["jusqu"] == "2027-03-24" and b["Connor Bedard"]["explicite"] and b["Connor Bedard"]["depuis"] == "2026-11-24"
# la premiere manchette sans duree, puis celle qui la dit : la date suit ; relire le fil ne change rien
d = {}
fil = [N("Connor Bedard will have surgery on his right shoulder", "2026-11-21"), N("Connor Bedard out four months after shoulder surgery", "2026-11-24")]
for _ in range(3):
    b = ij.suivre_blessures(d, fil, INFO, aujourdhui=J)
assert b["Connor Bedard"]["depuis"] == "2026-11-21" and b["Connor Bedard"]["jusqu"] == "2027-03-24", b
# 40 jours plus tard, les manchettes sont sorties du fil : il est toujours blesse ; apres la date : plus
assert "Connor Bedard" in ij.suivre_blessures(d, [], INFO, aujourdhui=J + timedelta(days=40))
assert "Connor Bedard" not in ij.suivre_blessures(d, [], INFO, aujourdhui=date(2027, 3, 26))
# une manchette de retour ferme l'etat (« returns ... after surgery » est un retour, pas une blessure) ; « expected to return » non
d = {}
fil = [N("Auston Matthews out 4-6 weeks with upper-body injury", "2026-11-10")]
assert "Auston Matthews" in ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 12))
fil.append(N("Auston Matthews expected to return in two weeks", "2026-11-14"))
assert "Auston Matthews" in ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 14))
fil.append(N("Auston Matthews returns to Maple Leafs lineup after injury", "2026-11-16"))
assert "Auston Matthews" not in ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 16))
assert "Auston Matthews" not in ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 17))     # la vieille manchette relue ne le reblesse pas
# il rejoue (ses matchs joues montent apres la blessure) : l'etat tombe sans manchette
d = {}
fil = [N("Cale Makar leaves game with lower-body injury", "2026-11-10")]
st = {"Cale Makar": {"jours": {"2026-11-10": {"an": 2026, "mj": 18, "pts": 20}, "2026-11-12": {"an": 2026, "mj": 18, "pts": 20}}}}
assert "Cale Makar" in ij.suivre_blessures(d, fil, INFO, st, aujourdhui=date(2026, 11, 13))
st["Cale Makar"]["jours"]["2026-11-15"] = {"an": 2026, "mj": 19, "pts": 21}
assert "Cale Makar" not in ij.suivre_blessures(d, fil, INFO, st, aujourdhui=date(2026, 11, 15))
# la pastille : « blesse » en premier, et l'etat est garde d'une passe a l'autre (passe() recopie ses cles)
src = open(os.path.join(ICI, "indice_joueurs.py"), encoding="utf-8").read()
assert 'past.insert(0, "blesse")' in src and '"blessures": dict(d.get("blessures") or {})' in src
app = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
# 25 nov 2026, 09 h 49 (Mathieu : « Bad news c'est mieux, et quand tu cliques sur la pastille t'as l'explication ; inspire-toi
# d'Apple iOS pour le pop-up de la notif ») : sur la tuile, blesse et absent disent « Mauvaise nouvelle » ; la pastille se touche
# et la notification dit pourquoi (blesse, absent, la manchette, le retour prevu)
assert app.count("blesse: [tt('Mauvaise nouvelle', 'Bad news'), 'rouge'], absent: [tt('Mauvaise nouvelle', 'Bad news'), 'rouge']") >= 4
assert "blesse: 'alerte', absent: 'alerte'" in app and "croix: '" in app
assert "function notifPastille(" in app and "tt('Mauvaise nouvelle · Blessé', 'Bad news · Injured')" in app and "tt('Mauvaise nouvelle · Absent', 'Bad news · Out')" in app
assert 'data-np="${esc(t1k)}"' in app and ("[data-np], .w-go" in app or "[data-np], [data-agp], .w-go" in app) and "backdrop-filter:blur(34px)" in app
assert "ouvrirFeuille(`<div class=\"cs-f\">" not in app, "Cle, Culte et chance de series passent par la meme notification"
# Meme jour (Mathieu : « pourquoi on n'a pas capte Bedard ? On doit TOUS les capter ») : les matchs. Un patineur de l'alignement
# qui jouait regulierement et qui a rate ses 2 derniers matchs est « absent », sans aucune manchette
def club(code, n, dates, sauf=None):
    """n joueurs du club qui jouent tous ces soirs ; sauf = {nom: dates qu'il a jouees}."""
    info = {f"{code} Joueur{k}": {"actif": True, "equipe": code} for k in range(n)}
    m = {nom: list(dates) for nom in info}
    for nom, ds in (sauf or {}).items():
        info[nom] = {"actif": True, "equipe": code}; m[nom] = list(ds)
    return info, m
T = [(date(2026, 11, 5) + timedelta(days=2 * k)).isoformat() for k in range(10)]            # 10 matchs, du 5 au 23 nov
info, m = club("CHI", 18, T, {"Connor Bedard": T[:7], "Frank Nazar": T[:9], "Recrue Rappelee": T[9:], "Jamais Vu": []})
A = ij.absents(info, m, aujourdhui=J)
assert set(A) == {"Connor Bedard"} and A["Connor Bedard"] == {"rates": 3, "depuis": T[7], "dernier": T[6]}, A    # 1 match rate : pas encore
assert "Connor Bedard" not in ij.absents(info, m, alignement={"frank nazar"}, aujourdhui=J)        # plus dans l'alignement : pas « absent »
assert ij.absents(info, m, aujourdhui=J + timedelta(days=30)) == {}                              # la saison arretee : personne
info2, m2 = club("MTL", 18, T, {"Laisse De Cote": [T[0], T[3]] })                                # jouait peu : pas un regulier
assert ij.absents(info2, m2, aujourdhui=J) == {}
# un blesse qui rate encore ses matchs reste blesse passe la date prevue ; des qu'il rejoue (sommaire), l'etat tombe
d = {}
fil = [N("Connor Bedard leaves game with injury", "2026-11-17")]
assert "Connor Bedard" in ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 18))
assert "Connor Bedard" not in ij.suivre_blessures(d, [], INFO, aujourdhui=date(2026, 12, 20))
d = {}
ij.suivre_blessures(d, fil, INFO, aujourdhui=date(2026, 11, 18))
assert "Connor Bedard" in ij.suivre_blessures(d, [], INFO, aujourdhui=date(2026, 12, 20), absents_={"Connor Bedard": {"rates": 14}})
assert "Connor Bedard" not in ij.suivre_blessures(d, [], INFO, aujourdhui=date(2026, 12, 21), absents_={}, matchs={"Connor Bedard": ["2026-11-17", "2026-12-20"]})
assert 'past.insert(0, "absent")' in src and "nom not in blesses and nom not in absents_" in src
print("OK test_blessures")
