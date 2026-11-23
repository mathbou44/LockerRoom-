"""23 nov 2026 (Mathieu : « echange entre Montreal et Detroit : on devrait absolument l'avoir capte, les cartes de ce joueur
vont exploser ») : Dylan Larkin passe a Montreal un dimanche soir ; les alignements n'etaient relus qu'aux 20 h. Une nouvelle
d'echange FERME (pas une rumeur) qui nomme un de nos joueurs fait relire les alignements de la saison tout de suite."""
import io
import json
import os
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
from datetime import date
import indice_joueurs as ij

AUJ = date(2026, 11, 23)
T = lambda t, j="2026-11-23": {"titre": t, "lien": "https://exemple.test/x", "date": j}

# 1. ferme ou rumeur
ferme = lambda t: bool(ij.ECHANGE_FERME.search(t)) and not ij.ECHANGE_RUMEUR.search(t)
for t in ("Dylan Larkin traded to Montreal Canadiens from Detroit Red Wings", "Canadiens acquire Dylan Larkin in blockbuster",
          "Dylan Larkin dealt to Montreal",
          "Dylan Larkin échangé au Canadien", "Le Canadien acquiert Dylan Larkin", "Red Wings trade ex-captain Dylan Larkin to Canadiens",
          "Larkin traded to Canadiens by Red Wings for package involving Dach, Hage"):
    assert ferme(t), t
for t in ("Dylan Larkin trade rumors heat up", "Could Dylan Larkin be traded to Montreal?", "Red Wings must convince Dylan Larkin to join Canadiens",
          "Canadiens have new trade target to consider", "Dylan Larkin wants to be traded", "Larkin pourrait être échangé à Montréal",
          "Trade deadline: 5 players to watch", "Trade talks intensify around Dylan Larkin",
          "Dylan Larkin scores twice in win"):
    assert not ferme(t), t
print("OK ferme / rumeur")

# 2. qui est annonce, et on arrete une fois le changement note
base = {"Dylan Larkin": {"nhl": {"actif": True, "equipe": "DET"}}, "Kirby Dach": {"nhl": {"actif": True, "equipe": "MTL"}},
        "Cole Caufield": {"nhl": {"actif": True, "equipe": "MTL"}}}
items = [T("Dylan Larkin traded to Montreal Canadiens for package involving Kirby Dach"), T("Cole Caufield scores twice"),
         T("Could Cole Caufield be traded?"), T("Old news: Kirby Dach traded", "2026-11-10")]
d = {"indice": {}, "echanges": {}, "equipes_vues": {"Dylan Larkin": {"eq": "DET", "le": "2026-11-22"}, "Kirby Dach": {"eq": "MTL", "le": "2026-11-22"},
                                                   "Cole Caufield": {"eq": "MTL", "le": "2026-11-22"}},
     "rosters": {"le": time.time() - 3 * 3600, "le_prec": time.time() - 3 * 3600, "saison": "20262027",
                 "cour": {"dylan larkin": "DET", "kirby dach": "MTL", "cole caufield": "MTL"},
                 "prec": {"dylan larkin": ["DET"], "kirby dach": ["MTL"], "cole caufield": ["MTL"]}}}
assert ij.echange_annonce(d, base, AUJ, items[:1] + items[1:3]) == ["Dylan Larkin", "Kirby Dach"], ij.echange_annonce(d, base, AUJ, items)
assert ij.echange_annonce(d, base, AUJ, items[1:3]) == []                                     # un but, une rumeur : rien
# le nom de famille seul (la manchette de la LNH) : assez pour declencher la relecture
assert ij.echange_annonce(d, base, AUJ, [T("Larkin traded to Canadiens by Red Wings for package involving Dach, Hage")]) == ["Dylan Larkin"]
print("OK annonce")

# 3. la relecture : tout de suite (3 h apres la derniere), puis pas avant 75 minutes, et au plus 10 par jour
lus = []
def lecteur(vieux, force=False):
    lus.append(force)
    return {"le": time.time(), "le_prec": vieux["le_prec"], "saison": "20262027",
            "cour": {"dylan larkin": "MTL", "kirby dach": "DET", "cole caufield": "MTL"}, "prec": vieux["prec"]}
assert ij.rosters_vite(d, base, AUJ, items, lecteur) == ["Dylan Larkin", "Kirby Dach"] and lus == [True]
assert d["rosters"]["cour"]["dylan larkin"] == "MTL" and d["rosters_vite"] == {"jour": "2026-11-23", "n": 1}
assert ij.rosters_vite(d, base, AUJ, items, lecteur) == [] and lus == [True]                  # relu il y a un instant
d["rosters"]["le"] -= 2 * 3600; d["rosters_vite"]["n"] = ij.ROSTERS_VITE_MAX
assert ij.rosters_vite(d, base, AUJ, items, lecteur) == [] and lus == [True]                  # le plafond du jour
d["rosters_vite"]["n"] = 1
print("OK relecture")

# 4. le changement est note AUJOURD'HUI, avec son sens : Larkin arrive a Montreal (hausse), Dach en part (baisse)
E = ij.suivre_echanges(d, base, AUJ)
assert E["Dylan Larkin"] == {"de": "DET", "vers": "MTL", "le": "2026-11-23", "source": "vu"}, E
assert E["Kirby Dach"]["de"] == "MTL" and E["Kirby Dach"]["vers"] == "DET" and "Cole Caufield" not in E, E
assert ij.echange_de("Dylan Larkin", d)["sens"] == "hausse" and ij.echange_de("Kirby Dach", d)["sens"] == "baisse"
assert ij.echange_annonce(d, base, AUJ, items) == []                                          # note : on arrete de relire
assert ij.rosters_vite(d, base, AUJ, items, lecteur) == [] and lus == [True]
print("OK sens")

# 5. la saison d'avant ne se relit pas a chaque fois : 32 appels au lieu de 64 ; et une relecture forcee passe avant les 20 h
appels = []
class _R:
    def __init__(self, u): self.u = u
    def __enter__(self): return io.BytesIO(json.dumps({"forwards": [{"firstName": {"default": "Dylan"}, "lastName": {"default": "Larkin"}}]
                                                                    if "/MTL/" in self.u else []}).encode())
    def __exit__(self, *a): return False
ij.reseau.ouvrir = lambda req, timeout=15: (appels.append(req.full_url), _R(req.full_url))[1]
v = {"le": time.time() - 3600, "le_prec": time.time() - 3600, "saison": "20262027", "cour": {"dylan larkin": "DET"}, "prec": {"dylan larkin": ["DET"]}}
assert ij.rosters_lnh(v, AUJ) is v and not appels                                              # 1 h : pas relu...
r = ij.rosters_lnh(v, AUJ, force=True)                                                         # ... sauf si on force
assert len(appels) == 32 and all("/20262027" in u for u in appels), len(appels)
assert r["cour"] == {"dylan larkin": "MTL"} and r["prec"] == {"dylan larkin": ["DET"]} and r["le_prec"] == v["le_prec"]
appels.clear(); v["le"] = v["le_prec"] = time.time() - 8 * 86400                              # 8 jours : la saison d'avant aussi
r = ij.rosters_lnh(v, AUJ)
assert len(appels) == 64 and r["le_prec"] > v["le_prec"], len(appels)
print("ECHANGE VITE OK")

# 6. LE CAS REEL du 23 nov au matin : Larkin n'est sur AUCUN alignement (retire de Detroit, pas encore a Montreal) : ce sont les
# manchettes qui le disent. Deux manchettes d'accord, ou une manchette et le joueur absent de l'alignement de son club.
def neuf():
    return {"indice": {}, "echanges": {}, "equipes_vues": {"Dylan Larkin": {"eq": "DET", "le": "2026-11-22"}, "Kirby Dach": {"eq": "MTL", "le": "2026-11-22"},
                                                             "Cole Caufield": {"eq": "MTL", "le": "2026-11-22"}},
            "rosters": {"le": time.time(), "le_prec": time.time(), "saison": "20262027", "cour": {"cole caufield": "MTL", "kirby dach": "MTL"},
                        "prec": {"dylan larkin": ["DET"], "kirby dach": ["MTL"], "cole caufield": ["MTL"]}}}
assert ij.equipes_du_titre("Larkin traded to Canadiens by Red Wings for package involving Dach, Hage") == {"MTL", "DET"}
assert ij.equipes_du_titre("Le Canadien acquiert Dylan Larkin des Red Wings de Détroit") == {"MTL", "DET"}
U = lambda t, l: {"titre": t, "lien": l, "date": "2026-11-23"}
m1 = U("Larkin traded to Canadiens by Red Wings for package involving Dach, Hage", "https://www.nhl.com/news/a")
m2 = U("Red Wings trade ex-captain Dylan Larkin to Canadiens in multiplayer deal", "https://www.nbcsports.com/nhl/b")
d = neuf()
assert ij.echange_par_nouvelles(d, base, AUJ, [m1]) == ["Dylan Larkin"], d["echanges"]      # une manchette + absent de l'alignement
assert d["echanges"]["Dylan Larkin"] == {"de": "DET", "vers": "MTL", "le": "2026-11-23", "source": "nouvelles"}, d["echanges"]
assert ij.echange_de("Dylan Larkin", d)["sens"] == "hausse"
assert ij.echange_par_nouvelles(d, base, AUJ, [m1, m2]) == []                                 # deja note : une seule fois
d = neuf(); d["rosters"]["cour"]["dylan larkin"] = "DET"                                      # encore dans l'alignement de Detroit
assert ij.echange_par_nouvelles(d, base, AUJ, [m1]) == [] and not d["echanges"]              # une seule manchette : pas assez
assert ij.echange_par_nouvelles(d, base, AUJ, [m1, m2]) == ["Dylan Larkin"]                  # deux sources d'accord : oui
# on ne devine pas : rumeur, deux equipes d'arrivee possibles, aucune equipe, ou la sienne seulement
for mauvais in ([U("Could Dylan Larkin be traded to the Canadiens?", "https://a.test/1"), U("Dylan Larkin trade rumors: Canadiens interested", "https://b.test/2")],
                [U("Dylan Larkin traded: Canadiens or Maple Leafs?", "https://a.test/1"), U("Dylan Larkin traded, Bruins and Leafs react", "https://b.test/2")],
                [U("Dylan Larkin traded in blockbuster", "https://a.test/1"), U("Dylan Larkin has been traded", "https://b.test/2")],
                [U("Red Wings acquire picks as Dylan Larkin saga ends", "https://a.test/1"), U("Red Wings: Dylan Larkin dealt", "https://b.test/2")]):
    d = neuf(); d["rosters"]["cour"]["dylan larkin"] = "DET"
    assert ij.echange_par_nouvelles(d, base, AUJ, mauvais) == [] and not d["echanges"], mauvais
# celui qui part : « Red Wings acquire Kirby Dach » (Dach est encore dans l'alignement de Montreal : il faut deux manchettes)
d = neuf()
k1, k2 = U("Red Wings acquire Kirby Dach in Larkin trade", "https://a.test/1"), U("Kirby Dach traded to Detroit", "https://b.test/2")
assert ij.echange_par_nouvelles(d, base, AUJ, [k1, k2]) == ["Kirby Dach"] and ij.echange_de("Kirby Dach", d)["sens"] == "baisse"
print("OK manchettes")

# 7. la suite : l'alignement confirme (la date de la manchette reste), ou la manchette sans suite s'efface
d = neuf(); ij.echange_par_nouvelles(d, base, AUJ, [m1])
E1 = ij.suivre_echanges(d, base, AUJ)                                                         # pas encore dans un alignement : on garde
assert E1["Dylan Larkin"]["source"] == "nouvelles" and E1["Dylan Larkin"]["vers"] == "MTL", E1
d["rosters"]["cour"]["dylan larkin"] = "MTL"                                                  # 2 jours apres : Montreal l'ajoute
E2 = ij.suivre_echanges(d, base, date(2026, 11, 25))
assert E2["Dylan Larkin"] == {"de": "DET", "vers": "MTL", "le": "2026-11-23", "source": "nouvelles+vu"}, E2
d = neuf(); d["rosters"]["cour"]["dylan larkin"] = "DET"; ij.echange_par_nouvelles(d, base, AUJ, [m1, m2])
assert "Dylan Larkin" in ij.suivre_echanges(d, base, date(2026, 11, 24))
assert "Dylan Larkin" not in ij.suivre_echanges(d, base, date(2026, 11, 26))                  # 3 jours apres, toujours a Detroit : fausse alerte
d = neuf(); ij.echange_par_nouvelles(d, base, AUJ, [m1])
assert "Dylan Larkin" in ij.suivre_echanges(d, base, date(2026, 11, 30)) and "Dylan Larkin" not in ij.suivre_echanges(d, base, date(2026, 12, 4))
print("ECHANGE PAR MANCHETTES OK")
