"""15 nov 2026 (« itere jusqu'a ce que le gain soit reel » ; « on ne doit jamais arreter d'iterer et d'ameliorer SlabIQ ») :
le moment d'achat lu sur la Young Guns, le verdict d'un deal, l'iteration de la semaine, la mise a jour des ventes, le journal."""
import math, os, sys, tempfile, time
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import numpy as np
import banque_yg, moment_yg as M, historique, vendues

# 1. le tri des ventes : la YG de BASE du joueur seulement
assert M.classer("2023-24 Upper Deck Young Guns #201 Connor Bedard RC", "Connor Bedard") == "raw"
assert M.classer("2023-24 UD Young Guns Connor Bedard PSA 10 Gem Mint", "Connor Bedard") == "psa10"
assert M.classer("Connor Bedard Young Guns Exclusives /100", "Connor Bedard") is None
assert M.classer("Connor Bedard Young Guns PSA 9", "Connor Bedard") is None
assert M.classer("Connor Bedard Young Guns BGS 9.5", "Connor Bedard") is None
assert M.classer("Connor Bedard Young Guns Chicago Blackhawks RC", "Connor Bedard") == "raw"      # « black » de l'equipe
assert M.classer("Macklin Celebrini Young Guns", "Connor Bedard") is None
print("CLASSER OK")

# 2. un joueur qui chute puis qui flambe
rng = np.random.default_rng(1)
J0 = date.today().toordinal() - 400
def serie(prix_jour):
    l = []
    for k, p in enumerate(prix_jour):
        for _ in range(2):
            l.append((J0 + k, float(p * math.exp(rng.normal(0, 0.05)))))
    return l
chute = [100] * 300 + [100 - 2 * k for k in range(20)] + [60] * 10        # -40 % en 3 semaines a la fin
flambe = [100] * 300 + [100 + 3 * k for k in range(20)] + [160] * 10
for prix, attendu in ((chute, ("creux", "creux_fort")), (flambe, ("flambee",))):
    ix = M.indice({"raw": serie(prix)})
    e, rs = M.etat_de(M.facteurs(ix, J0 + len(prix) - 1))
    assert e in attendu and rs and all(isinstance(r, dict) and r.get("k") for r in rs), (e, rs)     # des codes, jamais du texte
assert M.etat_de(M.facteurs(M.indice({"raw": serie([100] * 330)}), J0 + 329))[0] == "neutre"
print("ETAT OK")

# 3. le verdict d'un deal : etat x rabais
assert M.verdict("creux_fort", 36)["niveau"] == 3 and M.verdict("creux_fort", 36)["cle"] == "fort_bas"
assert M.verdict("creux", 36)["niveau"] == 3 and M.verdict("creux", 30)["cle"] == "bon" and M.verdict("creux", 18)["cle"] == "bon"     # banc beton : Feu vert a -35 %
assert M.verdict("creux", 5) is None and M.verdict("neutre", 40) is None
assert M.verdict("flambee", 40)["cle"] == "flambee"
v = M.verdict("creux", 40, stats={"fort": {"vaut_plus": 91, "profit": 81, "n": 500}})
assert v["taux_vaut_plus"] == 91 and v["taux_profit"] == 81
# la vague de sortie (banc beton : 0-60 j apres la sortie, un achat vaut -28 % deux mois plus tard) : jamais de Feu vert
assert M.etat_de(None, M.REGLES_V2, age=20) == ("sortie", [{"k": "sortie", "v": 20}])
assert M.etat_de(None, M.REGLES_V2, age=90)[0] == "inconnu" and M.verdict("sortie", 50)["cle"] == "sortie"
assert M.sortie_yg(["2025-26 Upper Deck Young Guns #451 Ivan Demidov"]) == date(2026, 2, 18).toordinal()
assert M.sortie_yg(["2025-26 Upper Deck Extended Young Guns #712 X"]) == date(2026, 6, 18).toordinal()
assert M.sortie_yg(["2023-24 Upper Deck Young Guns #201 Connor Bedard"]) == date(2023, 11, 12).toordinal()
a_ = date.today().year if date.today().month >= 11 else date.today().year - 1
vg = M.vague_de(f"{a_}-{(a_ + 1) % 100:02d} Upper Deck Young Guns #201 Joueur Neuf", aujourd=date(a_, 11, 30))
assert vg and vg["jours"] == 18 and vg["baisse_pct"] < 0 and vg["points"] < 0, vg
assert M.vague_de("2023-24 Upper Deck Young Guns #201 Connor Bedard") is None
print("VERDICT OK")

# 4. la banque : des ventes, les etats du jour, l'annotation d'un deal, l'iteration (garde l'historique)
lignes = []
def ajouter(nom, prix, bruit=0.25):
    for k, p in enumerate(prix):
        for i in range(2):
            d = date.fromordinal(J0 + k).isoformat()
            lignes.append((f"{nom}{k}{i}|{d}|t", f"{nom} young guns", nom, f"2023-24 Upper Deck Young Guns {nom} RC",
                           float(p * math.exp(rng.normal(0, bruit))), "USD", None, d, f"{nom}{k}{i}"))
for i in range(12):                     # des joueurs qui montent et descendent (du bruit : des aubaines qui reviennent)
    base = 50 + 10 * i
    ajouter(f"Joueur{i} Test", [base * (1 + 0.3 * math.sin((k + 30 * i) / 25)) for k in range(400)])
ajouter("Connor Bedard", [100] * 380 + [100 - 2 * k for k in range(20)])
c = banque_yg._cx()
c.executemany("INSERT OR IGNORE INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", lignes)
c.execute("INSERT OR REPLACE INTO faits VALUES (?,?,?,?,?,?)", ("Connor Bedard young guns", "Connor Bedard", 3, 100, 1, time.time()))
c.commit(); c.close()
assert M.calculer_jour() == 13
e = M.etat("connor bedard")                          # sans accents ni majuscules
assert e and e["etat"] in ("creux", "creux_fort"), e
x = M.annoter({"joueur": "Connor Bedard", "rabais": 40, "item_id": "1", "total": 70.0, "valeur": 100.0, "titre": "Bedard YG"})
assert x["moment"]["verdict"]["niveau"] == 3, x
assert "moment" not in M.annoter({"joueur": "Inconnu Total", "rabais": 30})
out = M.iterer_maintenant()
assert out["ventes_test"] > 1000 and "tout" in out["stats"], out
b = M.bilan()
assert b["ok"] and len(b["iterations"]) == 1 and b["regles"] and b["etats"], b
print("ITERER OK")

# 5. l'iteration ne remplace les regles que si le challenger gagne AUSSI sur les mois recents (jamais vus pour choisir)
appels = []
vraie = M.mesurer
def fausse(T, IX, R, depuis=None, jusqua=None):
    appels.append((R["rabais_fort"], depuis is not None))
    bon = R["rabais_fort"] == 0.30
    recent = depuis is not None
    p = 90 if bon and not recent else 80          # meilleur sur le passe, PAS sur les mois recents -> garde
    return {"feu_vert": {"n": 200, "profit": p}, "bon": {"profit": 50}}
M.mesurer = fausse
o = M.iterer({}, R=dict(M.REGLES_V1))
assert not o["change"] and o["regles"]["rabais_fort"] == 0.25, o["regles"]
def fausse2(T, IX, R, depuis=None, jusqua=None):
    return {"feu_vert": {"n": 200, "profit": 90 if R["rabais_fort"] == 0.30 else 80}, "bon": {"profit": 50}}
M.mesurer = fausse2
o = M.iterer({}, R=dict(M.REGLES_V1))
assert o["change"] and o["regles"]["rabais_fort"] == 0.30, o["regles"]
M.mesurer = vraie
print("CHAMPION / CHALLENGER OK")

# 6. le journal en direct : note une fois, verifie 60 jours plus tard
assert M.journal_noter([x, x]) == 2
assert M.journal_noter([{"item_id": "2", "total": 5, "moment": {"etat": "neutre", "verdict": None}}]) == 0
assert M.journal_bilan()["signales"] == 1
assert M.journal_verifier(lambda t: 95.0) == 0                     # trop tot
assert M.journal_verifier(lambda t: 95.0, aujourd=date.today() + timedelta(days=61)) == 1
jb = M.journal_bilan()
k = x["moment"]["verdict"]["cle"]
assert jb[k]["verifies"] == 1 and jb[k]["vaut_plus"] == 100 and jb[k]["profit"] == 100, jb
print("JOURNAL OK")

# 7. la mise a jour de la semaine : ventes recentes seulement, dans un plafond de credits ; une fois par semaine
os.environ["COMPSNIPER_CLE"] = "cs_test"; os.environ["LR_HISTORIQUE_MOIS"] = "5000"
vendues._taux_usd_cad = lambda: 1.40
banque_yg.PAUSE_S = 0
APP = []
def page(q, p, par, debut=None):
    APP.append((q, p, debut))
    n = 50 if p == 1 else 3
    return {"results": [{"itemId": f"r{p}{i}", "title": f"{q} rc {i}", "soldPrice": {"amount": "10", "currency": "USD"},
                         "soldDate": date.today().isoformat()} for i in range(n)]}
banque_yg._page = page
r = banque_yg.rafraichir(plafond=10)
assert r["ok"] and r["fini"] and r["credits"] == 2 and r["requetes"] == 1, r
assert APP[0][2] >= (date.today() - timedelta(days=60)).isoformat(), APP           # depuis la derniere vente connue (- 3 j)
assert banque_yg.rafraichir_si_besoin() is None                                       # deja fait cette semaine
APP.clear(); banque_yg._meta("rafraichi_le", 0); banque_yg._meta("rafraichi_essai", 0)
r = banque_yg.rafraichir_si_besoin()
assert r and r["credits"] == 2 and banque_yg.rafraichir_si_besoin() is None
r = banque_yg.rafraichir(plafond=1)
assert not r["fini"] and r["credits"] == 1, r
print("MISE A JOUR OK")

# 8. admin seulement ; le SlabIQ d'un deal porte le moment (un seul SlabIQ)
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin = lambda reel=False: False
assert api.admin_moment_yg()["ok"] is False and api.admin_moment_yg_iterer()["ok"] is False
api._est_admin = lambda reel=False: True
assert api.admin_moment_yg()["ok"]
import indice_joueurs
iq = lockerroom.Api._iq_un("Connor Bedard", {"Connor Bedard": {"indice": 70, "pastilles": []}})
assert iq["sens"] == "creux" and iq["pq"] == "yg_creux" and iq["yg"]["raisons"], iq
print("ADMIN + SLABIQ OK")

# 9. la passe du serveur (chaque heure) : mise a jour, iteration de la semaine, etats du jour, journal
import server
banque_yg._meta("rafraichi_le", 0); banque_yg._meta("rafraichi_essai", 0); banque_yg._meta("itere_le", 0)
r = server.moment_yg_tour()
assert "mise_a_jour" in r and "iteration" in r and "journal_verifies" in r, r
r = server.moment_yg_tour()
assert "iteration" not in r and "mise_a_jour" not in r, r                 # deja fait : rien a refaire avant demain / la semaine
print("PASSE SERVEUR OK")

# 10. les points du moment dans le Score SlabIQ (mesures : ou va la YG dans 2 mois dans cet etat)
st = {"derive": {"creux_fort": {"derive_pct": 16.9}, "creux": {"derive_pct": 4.3}, "flambee": {"derive_pct": -8.7}, "neutre": {"derive_pct": -0.7}, "tout": {"derive_pct": 0.0}}}
assert M.points("creux_fort", st) == 10 and M.points("creux", st) == 3 and M.points("flambee", st) == -5 and M.points("neutre", st) == 0
assert M.points("creux_fort", {"derive": {"creux_fort": {"derive_pct": 80}, "tout": {"derive_pct": 0}}}) == 12      # plafond
assert M.points("creux", None) == 0
d_ = M.mesurer_derives({j: ix for j, ix in ((j, M.indice(v)) for j, v in M.ventes_par_joueur(M._lignes_banque()).items()) if ix}, M.REGLES_V1)
assert "tout" in d_ and all("derive_pct" in v for v in d_.values()), d_
print("POINTS OK")

# 11. une baisse juste apres une flambee (encore au-dessus de sa moyenne de 6 mois) n'est pas un creux : « retombee », attendre
f_ = {"mom14": math.log(0.69), "mom28": math.log(0.85), "dd56": math.log(0.68), "z182": 0.82, "volrel": 0.75}
e_, rs_ = M.etat_de(f_, M.REGLES_V2, age=2000)
assert e_ == "retombee" and rs_[-1] == {"k": "haut6m"}, (e_, rs_)
assert M.verdict("retombee", 55)["cle"] == "retombee" and M.verdict("retombee", 55)["niveau"] == 0
assert M.etat_de(dict(f_, z182=-0.2), M.REGLES_V2, age=2000)[0] == "creux"
assert M.verdict("creux", 40)["rabais_min"] == 35
print("RETOMBEE OK")
