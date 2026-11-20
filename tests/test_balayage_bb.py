"""20 nov 2026 : la recolte quotidienne du baseball : chaque recherche relue juste avant que ses ~240 ventes ne debordent
(Ohtani aux 12 h, un joueur tranquille chaque semaine), les joueurs avant leurs variantes, dans le budget du jour. Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("LR_BALAYAGE_BB_JOUR", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cote_marche as cm  # noqa: E402

m = datetime(2026, 11, 20, 12, 0)
il_y_a = lambda h: (m - timedelta(hours=h)).isoformat(timespec="seconds")

# 1) le rythme : pleine sur 1 jour -> 12 h ; pleine sur 10 jours -> 8 jours ; pas pleine -> 7 jours ; ancien format -> maintenant
assert cm._bb_intervalle_h({"plein": True, "couvert": 1}) == 12
assert cm._bb_intervalle_h({"plein": True, "couvert": 10}) == 8 * 24
assert cm._bb_intervalle_h({"plein": True, "couvert": 2}) == 24
assert cm._bb_intervalle_h({"plein": False, "couvert": 200}) == 7 * 24
assert cm._bb_echeance({"n": 50, "le": il_y_a(1)}) == datetime.min            # lu avant le 20 nov : a reevaluer
assert cm._couverture_jours(["2026-11-19"] * 95 + ["2026-01-01"] * 5) == 1       # une vieille vente isolee ne compte pas
assert cm._couverture_jours(["2026-11-%02d" % d for d in range(10, 20)] * 10) == 9   # 90 % des ventes : du 11 au 19

# 2) les taches dues : les joueurs d'abord (le plus en retard d'abord), puis les variantes des joueurs pleins
B = {"Shohei Ohtani": {"n": 200, "le": il_y_a(13), "plein": True, "couvert": 1},       # du (12 h)
     "Bryan Woo": {"n": 230, "le": il_y_a(30), "plein": True, "couvert": 4},           # pas du (3 jours)
     "Joe Calme": {"n": 40, "le": il_y_a(24 * 8), "plein": False, "couvert": 90},      # du (7 jours)
     "Jean Lu": {"n": 40, "le": il_y_a(2), "plein": False, "couvert": 90}}             # pas du
V = {"Shohei Ohtani|psa 10": {"n": 100, "le": il_y_a(1), "plein": True, "couvert": 1}}  # lue il y a 1 h : pas due
noms = ["Shohei Ohtani", "Bryan Woo", "Joe Calme", "Jean Lu", "Nouveau Joueur"]
t = cm.taches_baseball(B, V, noms, maint=m)
types = [x[0] for x in t]
assert types == sorted(types, key=lambda x: x == "v"), types                     # les joueurs avant les variantes
joueurs = [x[1] for x in t if x[0] == "j"]
assert joueurs == ["Nouveau Joueur", "Joe Calme", "Shohei Ohtani"], joueurs       # jamais lu, puis le plus en retard
var = {x[1] for x in t if x[0] == "v"}
assert "Shohei Ohtani|psa 10" not in var and "Shohei Ohtani|bowman chrome" in var
assert all(k.split("|")[0] in ("Shohei Ohtani", "Bryan Woo") for k in var), var   # variantes : seulement les joueurs pleins

# 3) le budget du jour : LR_BALAYAGE_BB_JOUR s'il est la, sinon la part de la semaine (inchange : 150 / 7 -> 22)
assert cm.budget_baseball_jour() == 22
os.environ["LR_BALAYAGE_BB_JOUR"] = "140"
assert cm.budget_baseball_jour() == 140
os.environ.pop("LR_BALAYAGE_BB_JOUR")

# 4) une passe complete, SoldComps simule : la couverture et « pleine » sont gardees ; le budget du jour est respecte
import base_ventes, mlb, sports, vendues  # noqa: E401,E402
appels = []


def faux_appel(q, site, attendre=True, usage=None, compte=None, delai=25):
    appels.append(q)
    nom = q.rsplit(" baseball", 1)[0] if q.endswith(" baseball") else q
    n = 240 if "Ohtani" in q else 30
    return {"items": [{"t": f"2025 Topps Chrome {nom} RC", "le": "2026-11-19" if "Ohtani" in q else "2026-%02d-15" % (1 + i % 10)} for i in range(n)]}, None


vendues._cle = lambda: "cle"
vendues._appel = faux_appel
vendues._vers_vente = lambda it, taux: {"titre": it["t"], "prix": 25.0, "le": it["le"]}
vendues._taux_usd_cad = lambda: 1.37
vendues.sites = lambda: ["EBAY-US"]
mlb.joueur_du_titre = lambda t: {"nom": "Shohei Ohtani"} if "Ohtani" in t else {"nom": "Joe Calme"} if "Calme" in t else None
sports.sport_de = lambda t: "baseball"
notes = []
base_ventes.noter = lambda q, v, sport=None: notes.append((q, len(v), sport)) or len(v)
cm._noms_baseball = lambda max_=400: ["Shohei Ohtani", "Joe Calme"]
os.environ["LR_BALAYAGE_BB_JOUR"] = "3"
r = cm.balayer_baseball(20)
assert r["ok"] and r["fait"] == 2 and appels == ["Shohei Ohtani baseball", "Joe Calme baseball"], (r, appels)   # les joueurs d'abord
d = cm.lire_balayage()
assert d["baseball"]["Shohei Ohtani"]["plein"] and d["baseball"]["Shohei Ohtani"]["couvert"] == 1, d["baseball"]
assert not d["baseball"]["Joe Calme"]["plein"] and d["baseball"]["Joe Calme"]["n"] == 30
r = cm.balayer_baseball(20)                       # la passe suivante : une variante d'Ohtani (sa recherche deborde), budget 3
assert r["fait"] == 1 and appels[2].startswith("Shohei Ohtani ") and appels[2] != "Shohei Ohtani baseball", appels
assert "Joe Calme" not in " ".join(appels[2:])    # Joe Calme : pas plein, pas de variantes, pas du avant une semaine
assert all(s == "baseball" for _, _, s in notes)
r = cm.balayer_baseball(20)
assert r.get("raison") == "budget du jour", r
os.environ.pop("LR_BALAYAGE_BB_JOUR")
print("ok : recolte quotidienne du baseball")
