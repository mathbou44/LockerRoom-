"""27 nov 2026 (Mathieu : « double puis triple verifier les graphiques de prise de valeur ; des pommes avec des pommes et des poires
avec des poires » ; « Go » au correctif). La verification (archives du 26 nov) : par SORTE de carte, des cartes differentes se
melangeaient (Bobrovsky -59 % affiche, -28 % carte par carte). Le marche d'un joueur se mesure maintenant CARTE EXACTE par carte
exacte (ventes_cartes : chaque titre range une fois, garde sur le disque).   python tests/test_ventes_cartes.py"""
import os, sys, tempfile, sqlite3
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import ventes_cartes as vc, a_grader, marche_joueurs as mj
from datetime import date

YG = "2010-11 Upper Deck Young Guns Sergei Bobrovsky #240 RC"
REN = "2024-25 Upper Deck Young Guns Renewed Sergei Bobrovsky #YGR-37 PSA 10 Auto"
# ---- 1. la carte exacte : la Young Guns 2010 et la Renewed 2024 ne sont JAMAIS la meme carte
a, b = vc.ranger(YG), vc.ranger(YG + " PSA 10 GEM MINT")
assert a[:5] == b[:5] and a[5] == "raw" and b[5] == "10", (a, b)
r = vc.ranger(REN)
assert r is None or r[:5] != a[:5], r
assert vc.ranger("2010-11 Upper Deck Young Guns Sergei Bobrovsky #240 PSA 8") is None, "une autre note : a part (rien)"
assert vc.ranger("Bobrovsky + Hart lot of 2 Young Guns") is None and vc.ranger("") is None

# ---- 2. range UNE fois, garde sur le disque ; les jours suivants : le disque
appels = []
vrai = a_grader.classer
a_grader.classer = lambda t, j=None, pq=None: appels.append(t) or vrai(t, j)
P = [(YG, "Sergei Bobrovsky"), (YG + " PSA 10", "Sergei Bobrovsky"), ("titre illisible zz", None), (YG, "Sergei Bobrovsky")]
K = vc.cartes(P)
assert len(appels) == 3 and K[(YG, "Sergei Bobrovsky")][5] == "raw" and K[("titre illisible zz", "")] is None, (appels, K)
appels.clear()
K2 = vc.cartes(P)
assert appels == [] and K2 == K, "deja ranges : rien n'est relu"
assert tuple(vc.compte()) == (3, 2)
# une regle de rangement qui change : tout est relu une fois
vc.REGLE += 1
vc.cartes(P[:1]); assert len(appels) == 1
a_grader.classer = vrai

# ---- 3. le marche d'un joueur : une carte contre elle-meme ; la carte d'un AUTRE joueur ne compte pas ; une vente vue deux fois, une fois
V = [("Sergei Bobrovsky", YG, 40.0, "2026-11-20"), ("Sergei Bobrovsky", YG, 40.0, "2026-11-20"),
     ("Sergei Bobrovsky", YG + " PSA 10", 430.0, "2026-11-01"), ("Sergei Bobrovsky", "2010-11 Upper Deck Young Guns Claude Giroux #2 RC", 30.0, "2026-11-02"),
     ("Sergei Bobrovsky", YG, 3.0, "2026-11-03"), ("Connor Bedard", YG, 99.0, "2026-11-04")]
S = mj.series_cartes(V, {"Sergei Bobrovsky"})
assert set(S) == {"Sergei Bobrovsky"} and len(S["Sergei Bobrovsky"]) == 2, S
ks = sorted(S["Sergei Bobrovsky"], key=lambda k: k[-1])
assert [len(S["Sergei Bobrovsky"][k]) for k in ks] == [1, 1] and ks[0][-1] == "10" and ks[1][-1] == "raw", S   # 40 $ une fois ; 3 $ : sous le minimum
assert S["Sergei Bobrovsky"][ks[1]] == [(date(2026, 11, 20).toordinal(), 40.0)]
assert mj.VERSION == 8 and mj.N_SORTES == 2 and mj.N_T_MIN == 6, "2 cartes exactes et 6 ventes dans le mois (banc du 27 nov)"
src = open(os.path.join(RACINE, "marche_joueurs.py"), encoding="utf-8").read()
assert "S = series_cartes(ventes, noms, respirer=lambda i: time.sleep(0.01))" in src and "marche_cles.series(" not in src.split("def calculer(")[1]
print("VENTES CARTES OK")
