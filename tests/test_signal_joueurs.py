"""23 nov 2026 (Mathieu : « go ») : le signal par joueur en direct, admin seulement. Les regles (cas + evenement du soir),
la lecture d'un soir de la LNH, le journal qui ne se retouche pas, les echanges, et la note sur la meme carte."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.DOSSIER_COMPTES = os.path.join(comptes.DONNEES, "comptes")
from datetime import date, datetime, timedelta
import math
import signal_joueurs as sj

# 1. le cas du joueur : la saison recrue (regle du Calder) puis recrue / jeune / veteran
S = lambda *l: {"par_saison": [{"s": y * 10000 + y + 1, "l": lig, "gp": gp} for y, lig, gp in l]}
assert sj.annee_recrue(S((2015, "NHL", 45), (2016, "NHL", 82), (2025, "NHL", 80))) == 2015                  # McDavid
assert sj.annee_recrue(S((2024, "KHL", 60), (2024, "NHL", 2), (2025, "NHL", 82), (2026, "NHL", 20))) == 2025  # Demidov : 2 matchs, puis sa vraie saison
assert sj.annee_recrue(S((2023, "NHL", 10), (2024, "NHL", 12), (2025, "NHL", 60))) == 2024                  # 6 matchs et plus dans deux saisons
assert sj.annee_recrue({}) is None and sj.annee_recrue(S((2025, "AHL", 60))) is None
D = date(2026, 11, 23)
assert sj.saison(D) == 2026 and sj.saison(date(2027, 3, 1)) == 2026 and sj.saison(date(2027, 9, 1)) == 2027
assert [sj.cas_joueur(a, D) for a in (2026, 2025, 2024, 2023, None)] == ["recrue", "jeune", "jeune", "veteran", "veteran"]
print("OK cas")

# 2. les evenements du soir
def G(pts, buts=None):
    buts = buts or [0] * len(pts)
    return [[(date(2026, 1, 1) + timedelta(days=2 * k)).isoformat(), p, b] for k, (p, b) in enumerate(zip(pts, buts))]
base = [1, 0, 1, 1, 0] * 8                                   # 40 matchs a 0,6 point par match
g = G(base + [0, 0, 1, 0, 0, 3]); assert sj.evenements(g, 45, "veteran") == (["gros"], False)
g = G(base + [2, 1, 1, 1, 0, 3]); assert sj.evenements(g, 45, "veteran") == (["gros"], True)                # deja chaud : 5 points en 5 matchs
g = G(base + [0, 0, 0, 0, 0, 3], [0] * 45 + [3]); assert sj.evenements(g, 45, "veteran")[0] == ["chapeau", "gros"]
g = G(base + [0, 0, 0, 0, 0, 1], [0] * 45 + [2]); assert sj.evenements(g, 45, "jeune")[0] == ["gros"]       # 2 buts
g = G(base + [1, 1, 1, 2, 2]); assert sj.evenements(g, 44, "jeune")[0] == ["feu"]                            # 7 points en 5 matchs : la sequence commence
g = G(base + [1, 0, 0, 0, 0]); assert sj.evenements(g, 44, "jeune")[0] == ["panne"]
g = G(base + [1, 0, 0, 0, 0, 0]); assert sj.evenements(g, 45, "jeune")[0] == []                              # le 5e match sans point : deja dit
assert sj.evenements(G(base[:30] + [3]), 30, "veteran")[0] == []                                              # pas 40 matchs d'historique : on ne juge pas
r = G([1, 0, 1, 0, 1, 1, 0, 1, 0, 0, 0, 0]); assert sj.evenements(r, 11, "recrue")[0] == ["panne"]           # une recrue se juge des 8 matchs
assert sj.evenements(G([0, 1, 0, 3]), 3, "recrue")[0] == ["gros"]
print("OK evenements")

# 3. le tableau de decision
d_ = lambda cas, evs, chaud=False: (lambda x: x and (x["signal"], x["ev"], x["fort"]))(sj.decision(cas, evs, chaud))
assert d_("veteran", ["gros"]) == ("FENETRE", "gros", False) and d_("veteran", ["gros"], True) == ("ACHETE", "gros", True)   # isole : fenetre de vente ; deja chaud : achete
assert d_("jeune", ["chapeau", "gros"]) == ("ACHETE", "chapeau", True) and d_("jeune", ["feu"]) == ("ACHETE", "feu", False)
assert d_("jeune", ["panne"]) == ("ATTENDS", "panne", False) and d_("recrue", ["panne"]) == ("VENDS", "panne", False)
assert d_("veteran", ["panne"])[0] == "OBSERVE" and d_("veteran", ["feu"])[0] == "OBSERVE" and d_("recrue", ["gros"])[0] == "OBSERVE"
assert d_("veteran", []) is None
assert sj.decision_echange("hausse")["signal"] == "ACHETE" and sj.decision_echange("hausse")["fort"]
assert sj.decision_echange("baisse")["signal"] == "VENDS" and sj.decision_echange("neutre")["signal"] == "OBSERVE"
print("OK decision")

# 4. un soir de la LNH (les vraies formes de l'API : /v1/score/AAAA-MM-JJ et /v1/gamecenter/ID/boxscore)
def faux_get(soirs):
    appels = []
    def get(u):
        appels.append(u)
        if "/score/" in u:
            j = u.rsplit("/", 1)[1]
            return {"games": [{"id": gid, "gameType": ty, "gameState": et, "gameDate": j} for gid, ty, et, _l in soirs.get(j, [])]}
        if "/boxscore" in u:
            gid = int(u.split("/gamecenter/")[1].split("/")[0])
            l = next(l for js in soirs.values() for g, _t, _e, l in js if g == gid)
            mk = lambda pid, p, b: {"playerId": pid, "name": {"default": "X. Y"}, "goals": b, "assists": p - b, "points": p, "toi": "15:00"}
            rempl = [mk(900000 + gid * 100 + k, 0, 0) for k in range(24)]
            return {"gameType": 2, "gameState": "OFF", "playerByGameStats": {"awayTeam": {"forwards": [mk(*x) for x in l] + rempl[:12], "defense": rempl[12:18], "goalies": []},
                                                                              "homeTeam": {"forwards": rempl[18:], "defense": [], "goalies": []}}}
        if "/game-log/" in u:
            pid = u.split("/player/")[1].split("/")[0]
            return {"gameLog": [{"gameDate": (date(2026, 1, 1) + timedelta(days=2 * k)).isoformat(), "points": p, "goals": 0}
                                for k, p in enumerate(base + [2, 1, 1, 1, 0])]} if pid == "77" and u.endswith("20252026/2") else {"gameLog": []}
        return None
    get.appels = appels
    return get
get = faux_get({"2026-11-22": [(11, 2, "OFF", [(1, 3, 1), (2, 0, 0)]), (12, 2, "LIVE", []), (13, 1, "OFF", [])]})
r = sj.lire_soir("2026-11-22", get=get)
assert r["total"] == 2 and r["lus"] == ["11"] and not r["fini"] and r["lignes"]["1"] == [3, 1] and r["lignes"]["2"] == [0, 0], r
assert r["appels"] == 2 and len(r["lignes"]) == 26                           # le match hors concours (type 1) n'est pas lu
r = sj.lire_soir("2026-11-22", deja={"11"}, get=get); assert r["lus"] == [] and not r["fini"] and r["appels"] == 1
print("OK soir")

# 5. la passe : l'historique vient du test SlabIQ (ici : vide), les soirs manquants sont lus du plus vieux au plus recent
h_vet = S((2015, "NHL", 70), (2025, "NHL", 80)); h_jeune = S((2025, "NHL", 82)); h_rec = S((2026, "NHL", 12))
suivis = {"1": ("Vet Eran", h_vet), "2": ("Jeune Homme", h_jeune), "3": ("Re Crue", h_rec), "77": ("Sans Histoire", h_vet)}
M = {"joueurs": {"1": {"nom": "Vet Eran", "m": G(base + [2, 1, 1, 1, 0])}, "2": {"nom": "Jeune Homme", "m": G(base + [1, 0, 0, 0])},
                 "3": {"nom": "Re Crue", "m": G([1, 0, 1, 0, 1, 1, 0, 1, 0, 0, 0])}}, "jours": {}, "amorce": True}
for k in range(1, sj.JOURS_RELUS + 1):                                         # tout est deja lu, sauf hier soir
    M["jours"][(date(2026, 11, 23) - timedelta(days=k)).isoformat()] = {"total": 0, "lus": [], "fini": True}
del M["jours"]["2026-11-22"]
sj._ecrire("signal_matchs.json", M)
soirs = {"2026-11-22": [(21, 2, "OFF", [(1, 3, 1), (2, 0, 0), (3, 0, 0), (77, 4, 2)])]}
get = faux_get(soirs)
ech = {"Dylan Larkin": {"de": "DET", "vers": "MTL", "le": "2026-11-23", "source": "nouvelles", "sens": "hausse", "de_nom": "Detroit", "vers_nom": "Montréal"},
       "Kirby Dach": {"de": "MTL", "vers": "DET", "le": "2026-11-23", "source": "vu", "sens": "baisse", "de_nom": "Montréal", "vers_nom": "Detroit"},
       "Vieux Cas": {"de": "TOR", "vers": "CBJ", "le": "2026-10-01", "source": "alignements", "sens": "baisse"}}
maint = datetime(2026, 11, 23, 8, 30)
r = sj.passe(maint, get, suivis, ech)
J = sj.lire_journal()
par = {e["nom"]: e for e in J["journal"]}
assert r["signaux"] == 6 and r["soirs"] == 1, (r, J["journal"])
assert (par["Vet Eran"]["signal"], par["Vet Eran"]["fort"], par["Vet Eran"]["ev"], par["Vet Eran"]["direct"]) == ("ACHETE", True, "gros", True)
assert (par["Jeune Homme"]["signal"], par["Jeune Homme"]["ev"]) == ("ATTENDS", "panne") and (par["Re Crue"]["signal"], par["Re Crue"]["cas"]) == ("VENDS", "recrue")
assert par["Sans Histoire"]["signal"] == "ACHETE" and par["Sans Histoire"]["fort"]             # son historique a ete relu (2 appels), puis juge
assert sum("/game-log/" in u for u in get.appels) == 2
assert (par["Dylan Larkin"]["signal"], par["Dylan Larkin"]["fort"], par["Dylan Larkin"]["ev"]) == ("ACHETE", True, "echange")
assert par["Dylan Larkin"]["raison"] == "Échangé vers un gros marché : Detroit → Montréal" and par["Kirby Dach"]["signal"] == "VENDS"
assert "Vieux Cas" not in par and J["depuis"] == "2026-11-21"
# le journal ne se retouche pas : une 2e passe n'ajoute rien, ne change rien
avant = [dict(e) for e in J["journal"]]
r2 = sj.passe(datetime(2026, 11, 23, 9, 30), faux_get(soirs), suivis, ech)
assert r2["signaux"] == 0 and sj.lire_journal()["journal"] == avant, r2
# un soir lu 3 jours plus tard : « rattrapage », pas « direct »
M = sj.lire_matchs(); del M["jours"]["2026-11-22"]; M["joueurs"]["2"]["m"] = [g for g in M["joueurs"]["2"]["m"] if g[0] != "2026-11-22"]
M["joueurs"]["2"]["m"][-1][1] = 1; sj._ecrire("signal_matchs.json", M)
sj.passe(datetime(2026, 11, 26, 9, 0), faux_get({"2026-11-22": [(21, 2, "OFF", [(2, 3, 0)])]}), suivis, {})
e = [x for x in sj.lire_journal()["journal"] if x["nom"] == "Jeune Homme" and x["ev"] == "gros"][0]
assert e["signal"] == "FENETRE" and e["direct"] is False, e
print("OK passe et journal")

# 6. la note : LA MEME carte, 7 jours avant contre jours 8 a 60 apres ; les cartes fortes selon SlabIQ a part
V = [("2026-11-18", 100.0, "2015-16 Upper Deck Young Guns Vet Eran #201"), ("2026-11-20", 100.0, "2015-16 UD Young Guns #201 Vet Eran RC"),
     ("2026-12-05", 120.0, "2015-16 Upper Deck Young Guns Vet Eran #201 Rookie"), ("2026-11-30", 300.0, "2015-16 Upper Deck Young Guns Vet Eran #201"),   # jour 8 : compte
     ("2026-11-25", 999.0, "2015-16 Upper Deck Young Guns Vet Eran #201"),                                 # jours 1 a 7 : ne compte pas
     ("2026-11-19", 10.0, "2023-24 Upper Deck Series 1 Vet Eran #55"), ("2026-12-10", 9.0, "2023-24 Upper Deck Series 1 Vet Eran #55"),
     ("2026-11-19", 50.0, "2015-16 Upper Deck Young Guns Vet Eran #201 PSA 10"),                           # une autre carte (gradee) : pas d'apres
     ("2026-12-10", 70.0, "2019-20 SP Authentic Vet Eran #12")]                                            # pas d'avant
m = sj.mesurer(V, "Vet Eran", "2026-11-22", date(2026, 12, 20))
assert m["n"] == 2 and m["nf"] == 1 and abs(m["yf"] - 0.7419) < 1e-3, m                                    # YG : 100 -> mediane(120, 300) = 210
assert m["n14"] == 1 and abs(m["y14"] - math.log(3)) < 1e-3, m                                             # jours 2 a 14 : mediane(999, 300, 120) = 300 contre 100
assert abs(m["y"] - (math.log(2.1) + math.log(0.9)) / 2) < 1e-3, m
m0 = sj.mesurer(V, "Vet Eran", "2026-11-22", date(2026, 11, 28))
assert m0["y"] is None and m0["n"] == 0 and m0["n14"] == 1, m0                                             # trop tot pour les jours 8 a 60 ; la fenetre de 2 semaines a deja une vente
n = sj.noter(datetime(2026, 12, 20, 5, 0), {"vet eran": V})
J = sj.lire_journal(); idv = next(e["id"] for e in J["journal"] if e["nom"] == "Vet Eran")
assert n >= 1 and J["notes"][idv]["n"] == 2 and J["notes"][idv]["final"] is False, (n, J["notes"])
assert len(J["journal"]) == len(avant) + 1                                                                   # la note n'efface rien du journal
sj.noter(datetime(2027, 1, 25, 5, 0), {"vet eran": V}); J = sj.lire_journal()
assert J["notes"][idv]["final"] is True and all(J["notes"][e["id"]]["final"] for e in J["journal"])       # apres 60 jours : finale, meme sans vente
B = sj.bilan(J)
assert B["direct"]["achete"]["n"] == 3 and B["direct"]["achete"]["notes"] == 1 and B["direct"]["achete"]["bon"] == 10.0, B
assert B["direct"]["achete_cartes_fortes"]["med"] == 110.0 and B["direct"]["vends"]["n"] == 2 and B["rattrapage"]["achete"]["n"] == 0 and B["rattrapage"]["fenetre"]["n"] == 1, B
a = sj.admin()
assert a["ok"] and a["signaux"] == 7 and a["derniers"][0]["jour"] >= a["derniers"][-1]["jour"] and all(x["signal"] in sj.GRANDS for x in a["derniers"])
assert next(x for x in a["derniers"] if x["nom"] == "Vet Eran")["note"] is not None
os.environ["LR_SIGNAL_JOUEURS"] = "0"; assert not sj.actif() and sj.passe_si_besoin() is False; os.environ.pop("LR_SIGNAL_JOUEURS")
print("SIGNAL JOUEURS OK")
