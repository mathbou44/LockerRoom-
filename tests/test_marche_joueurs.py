"""21 nov 2026 (Mathieu : « toujours sortir la liste des joueurs a acheter (creux) et a vendre (sommet temporaire) » ; « le voir
sur des plus grands time frames » ; « comme Amazon : le plus bas depuis X jours » ; « montre-moi l'indice de confiance ») :
marche_joueurs : un joueur ETABLI dont le marche est sous sa normale de 12 mois -> a acheter ; une recrue dans le meme creux ->
jamais ; un marche bien au-dessus de sa normale et a son plus haut -> a vendre ; chaque signal porte son taux MESURE sur le
passe (jamais utilise s'il ne bat pas le hasard) ; « au plus bas depuis N jours » ; la banque de raisons garde chaque signal."""
import json, os, sys, tempfile
from datetime import date
d = tempfile.mkdtemp(); os.environ["LOCKERROOM_DONNEES"] = d
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import marche_joueurs as mj, marche_cles

FIN = date(2026, 11, 19).toordinal()


def serie(prix_du_jour):
    """Trois cartes (27 nov 2026 : il en faut au moins 3 dans la tranche), une vente aux 3 jours pendant 15 mois ; prix_du_jour(age
    en jours) -> le niveau (1.0 = normal)."""
    return {s: [(FIN - a, base * prix_du_jour(a) * (1 + 0.01 * ((a // 3) % 3 - 1))) for a in range(450, -1, -3)] for s, base in (("yg", 100.0), ("auto", 400.0), ("canvas", 25.0))}


plat = lambda a: 1.0
creux_passe = lambda a: 0.72 if 130 <= a <= 200 else 1.0            # un creux il y a 4-6 mois, revenu a la normale
sommet_passe = lambda a: 1.55 if 130 <= a <= 200 else 1.0           # un sommet temporaire, retombe
creux_now = lambda a: 0.70 if a <= 40 else creux_passe(a)
sommet_now = lambda a: 1.60 if a <= 40 else 1.0

# -- le point d'un joueur --------------------------------------------------------------------------------------------------
x = mj.point(serie(creux_now), FIN)
assert x and 0.66 < x["niveau"] / x["mediane"] < 0.76, x
assert mj.signal_achat(x, ("mediane", 0.20)) and mj.signal_achat(x, ("sommet", 0.20)) and not mj.signal_vente(x, 0.10)
h = mj.point(serie(sommet_now), FIN)
assert h and h["niveau"] / h["mediane"] > 1.5 and mj.signal_vente(h, 0.30) and not mj.signal_achat(h, ("mediane", 0.10)), h
p = mj.point(serie(plat), FIN)
assert not mj.signal_vente(p, 0.10) and not mj.signal_achat(p, ("mediane", 0.10)) and not mj.signal_achat(p, ("sommet", 0.15)), p
assert mj.point({"yg": [(FIN - 3, 100.0)]}, FIN) is None, "pas assez de ventes : rien"
# « au plus bas depuis N jours » : jamais aussi bas de tout l'historique ; un joueur stable : aussi bas il y a 7 jours
dp = mj._depuis(serie(creux_now), FIN, x["niveau"])
assert dp["bas_depuis_j"] == dp["hist_j"] >= 300 and dp["haut_depuis_j"] <= 35, dp
dh = mj._depuis(serie(sommet_now), FIN, h["niveau"])
assert dh["haut_depuis_j"] == dh["hist_j"] >= 300, dh
# la suite (46 a 74 jours plus tard) : un creux passe a remonte
s0 = mj.point(serie(creux_passe), FIN - 150, suite=True)
assert s0["apres"] > s0["niveau"] * 1.2, s0

# -- la passe complete : etats + verification sur le passe ---------------------------------------------------------------
S, base = {}, {}
def joueur(nom, f, matchs):
    S[nom] = serie(f); base[nom] = {"nhl": {"carriere": {"gamesPlayed": matchs}}}
for i in range(45):
    joueur("Vet Creux %02d" % i, creux_passe, 500)                  # les veterans : leur creux a remonte
    joueur("Kid Sommet %02d" % i, sommet_passe, 20)                 # les sommets temporaires sont retombes
    joueur("Vet Plat %02d" % i, plat, 400)
joueur("Vet Dip", creux_now, 600); joueur("Kid Dip", creux_now, 30); joueur("Vet High", sommet_now, 600); joueur("Vet Flat", plat, 600)
vrai = mj.series_cartes
mj.series_cartes = lambda ventes, noms, respirer=None: {k: v for k, v in S.items() if marche_cles._titre(k) in noms or k in noms}
try:
    D = mj.calculer([], base, date.fromordinal(FIN))
finally:
    mj.series_cartes = vrai
V, E = D["verif"], D["etats"]
a, v = V["achat"], V["vente"]
assert a["actif"] and a["taux"] > a["base"] + 0.2 and a["n"] >= mj.N_PARIS_MIN and a["borne"] > a["base"], a
assert v["actif"] and v["taux"] > v["base"] + 0.2 and v["n"] >= mj.N_TEST_MIN, v
assert a["du"] and a["au"] and a["du"] < a["au"] and len(a["essais"]) == len(mj.ACHATS) * len(mj.HORIZONS) and a["essayes"] == len(a["essais"]) and len(v["essais"]) == len(mj.VENTES)
assert E["Vet Dip"]["signal"] == "acheter" and 0 < E["Vet Dip"]["taux"] <= 1 and E["Vet Dip"]["vs_mediane_pct"] <= -20, E["Vet Dip"]
assert E["Vet Dip"]["bas_depuis_j"] == E["Vet Dip"]["hist_j"] and E["Vet Dip"]["etabli"]
assert "signal" not in E["Kid Dip"] and not E["Kid Dip"]["etabli"], "une recrue en creux : jamais a acheter (mesure : ca ne remonte pas mieux que le hasard)"
assert E["Vet High"]["signal"] == "vendre" and E["Vet High"]["vs_mediane_pct"] >= 30, E["Vet High"]
assert "signal" not in E["Vet Flat"], E["Vet Flat"]
# jamais plus que ce qui est mesure : le taux d'un joueur est celui d'un bareme essaye, qui bat le hasard avec assez de cas
ok = {t["taux"] for t in a["essais"] if t["ok"]}
# 21 nov 2026 (« pas mieux que 70 % ? ») : chaque bareme d'achat est verifie a 2, 3 et 4 mois ; le joueur porte le delai du sien
assert {t["mois"] for t in a["essais"]} == {2, 3, 4} and all(t.get("base") is not None for t in a["essais"] if t["n"])
# « une vraie plus-value » : le bareme retenu laisse une marge apres les frais (remontee mediane mesuree de 20 % et plus)
# « une vraie plus-value » : un achat est juge comme un pari (un par joueur et par creux), gagnant APRES les frais
assert E["Vet Dip"]["gain"] > 0 and a["frais"] == mj.FRAIS and a["n_min"] == mj.N_PARIS_MIN, (E["Vet Dip"], a.get("frais"))
assert all(t["n"] <= 45 * 2 + 4 for t in a["essais"]), "un pari par joueur et par creux, pas un par semaine"
_pp = [{"j": "A", "jour": 100}, {"j": "A", "jour": 107}, {"j": "A", "jour": 163}, {"j": "A", "jour": 171}, {"j": "B", "jour": 107}]
assert [(x["j"], x["jour"]) for x in mj.paris(_pp)] == [("A", 100), ("B", 107), ("A", 171)], mj.paris(_pp)
_v0 = mj.FRAIS; mj.FRAIS = 0.9                                   # des frais absurdes : plus aucun pari gagnant, donc personne a acheter
mj.series_cartes = lambda ventes, noms, respirer=None: {k: v for k, v in S.items() if marche_cles._titre(k) in noms or k in noms}
try:
    _d = mj.calculer([], base, date.fromordinal(FIN))
    assert "signal" not in _d["etats"]["Vet Dip"] and not _d["verif"]["achat"]["actif"], "rien ne couvre les frais : personne a acheter"
finally:
    mj.series_cartes = vrai; mj.FRAIS = _v0
assert E["Vet Dip"]["mois"] in (2, 3, 4) and mj.point(serie(creux_passe), FIN - 150, suite=(106, 134))["apres"] is not None
assert E["Vet Dip"]["taux"] in ok, (E["Vet Dip"]["taux"], ok)

# un bareme qui ne bat pas le hasard : aucun signal
P = [{"j": "A%d" % (i % 40), "niveau": 0.7, "sommet": 1.0, "mediane": 1.0, "prec": 0.8, "apres": 0.7 if i % 3 else 0.9, "jour": FIN - 100} for i in range(120)]
P += [{"j": "B%d" % (i % 40), "niveau": 1.0, "sommet": 1.0, "mediane": 1.0, "prec": 1.0, "apres": 1.2 if i % 2 else 1.0, "jour": FIN - 100} for i in range(120)]
W = mj.verifier(P, {"A%d" % i for i in range(40)} | {"B%d" % i for i in range(40)})
assert not W["achat"]["actif"], W["achat"]

# -- le fichier, les listes, la preuve, la banque de raisons -------------------------------------------------------------
mj.ecrire(D); mj._ETAT.update(lu=0.0) if "lu" in mj._ETAT else None
assert [x["nom"] for x in mj.liste("acheter")] == ["Vet Dip"] and [x["nom"] for x in mj.liste("vendre")] == ["Vet High"], (mj.liste("acheter"), mj.liste("vendre"))
assert mj.etat("vet dip")["signal"] == "acheter" and mj.etat("Inconnu Total") is None
pr = mj.preuve()
assert pr["achat"]["taux"] == a["taux"] and pr["achat"]["base"] == a["base"] and pr["achat"]["essais"] and pr["achat"]["du"], pr["achat"]
st = mj.statut(); assert st["acheter"] == 1 and st["vendre"] == 1, st
sg = mj.signaux()
assert sg["Vet Dip"][-1]["signal"] == "acheter" and sg["Vet High"][-1]["signal"] == "vendre" and "Vet Flat" not in sg, list(sg)[:5]
assert sg["Vet Dip"][-1]["le"] == date.fromordinal(FIN).isoformat() and "raisons" in sg["Vet Dip"][-1]
print("OK test_marche_joueurs (creux d'un etabli -> acheter %s %% vs hasard %s %% ; sommet -> vendre %s %% vs %s %%)" % (
    round(a["taux"] * 100), round(a["base"] * 100), round(v["taux"] * 100), round(v["base"] * 100)))

# 21 nov 2026 (recherche : le meilleur de 30 baremes a toujours l'air trop beau) : le taux montre est le taux PRUDENT
_t = next(t for t in a["essais"] if t["ok"])
assert _t["taux"] < _t["taux_brut"] and abs(_t["taux"] - (_t["gagnes"] + _t["base"] * mj.POIDS_PRUDENT) / (_t["n"] + mj.POIDS_PRUDENT)) < 0.002, _t
print("OK test_marche_joueurs (taux prudent : %s %% brut -> %s %% montre, sur %s paris)" % (round(_t["taux_brut"] * 100), round(_t["taux"] * 100), _t["n"]))

# 21 nov 2026 (soir ; « au moins la plus basse mediane en X jours ») : la liste des faits, sans signal
_b = [x["nom"] for x in mj.liste_bas()]
assert "Vet Dip" in _b and "Kid Dip" not in _b and "Vet Flat" not in _b and "Vet High" not in _b, _b
assert mj.liste_bas()[0]["bas_depuis_j"] >= 30 and mj.liste_bas(jours=9999) == []
print("OK test_marche_joueurs (au plus bas : %s)" % _b[:3])
# 23 nov 2026 (Mathieu : « on a enleve "at their highest" ?! ») : le pendant, un fait aussi : au plus haut, au-dessus de sa normale
_h = [x["nom"] for x in mj.liste_haut()]
assert "Vet High" in _h and "Vet Dip" not in _h and "Vet Flat" not in _h, _h
assert mj.liste_haut()[0]["haut_depuis_j"] >= 30 and mj.liste_haut()[0]["vs_mediane_pct"] >= 10 and mj.liste_haut(jours=9999) == [] and "taux" not in mj.liste_haut()[0]
print("OK test_marche_joueurs (au plus haut : %s)" % _h[:3])

# la petite courbe de 12 mois (comme dans Bourse) : le plus vieux d'abord, aujourd'hui a la fin ; des niveaux relatifs
_c = E["Vet Dip"]["courbe"]
assert _c and len(_c) >= 8 and _c[-1] < _c[0] * 0.75 and all(0 < v < 3 for v in _c) and mj.liste_bas()[0].get("courbe"), _c
print("OK test_marche_joueurs (courbe : %s points, de %s a %s)" % (len(_c), _c[0], _c[-1]))
