"""25 nov 2026 (Mathieu : « idem au trend qu'on a pour les joueurs mais pour les cartes, avec biggest risers et biggest losers » ;
« j'espere que le trend est associe aux joueurs ? » ; « une OPC Platinum Emerald Surge Auto ne doit pas etre compilee avec une OPC
Platinum Auto Violet Pixel, ni avec une Emerald Surge pas auto » ; « on se fout des paralleles sans valeur qui se vendent 20 $ et
moins, a part les Young Guns » ; « double et triple verifie : on n'a pas le droit a l'erreur ») : tendance_sortes.py.

La mesure : LA carte d'un joueur (un joueur + une sorte + une saison), comparee a elle-meme : 30 jours contre les 60 d'avant.
Chaque vente comptee UNE fois, jamais deux saisons ni deux cartes ensemble, rien d'annonce sans test (p < 0,01), jamais un prix."""
import contextlib, io, json, os, sys, tempfile, time
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
RAC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAC)
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import tendance_sortes as ts_
import cartes_match

AUJ = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
jr = lambda n: (AUJ - timedelta(days=n)).strftime("%Y-%m-%d")
_num = [900000000000]


def ventes(avant, recent, an, n_av=14, n_re=12, pas=2, debut=1):
    """n_av ventes dans les 60 jours d'avant autour de « avant », n_re dans les 30 derniers autour de « recent » ; chacune a son
    numero (comme une vente d'eBay) et la saison lue dans son titre."""
    out = []
    for i in range(n_av):
        _num[0] += 1
        out.append([jr(31 + pas * i), avant * (1 + 0.04 * ((i % 3) - 1)), "https://www.ebay.ca/itm/%d" % _num[0], an])
    for i in range(n_re):
        _num[0] += 1
        out.append([jr(debut + pas * i), recent * (1 + 0.04 * ((i % 3) - 1)), "https://www.ebay.ca/itm/%d" % _num[0], an])
    return out


def entree(joueur, q, v, sport="hockey", lu=None, annee=None):
    return {"joueur": joueur, "carte": q, "q": q, "sport": sport, "annee": annee, "lu_le": lu, "points": [[x[0], x[1]] for x in v], "ventes": v}


# ---------------------------------------------------------------- les mots : une sorte, une carte precise, une saison, un lot
assert ts_.cle_sorte("Connor Bedard", "2023-24 connor bedard young guns #451") == "young guns"
assert ts_.cle_sorte("Connor Bedard", "connor bedard young guns exclusives /100") == "young guns exclusives /100"      # la numerotation reste
assert ts_.cle_sorte("Connor Bedard", "connor bedard rc") is None and ts_.cle_sorte("Connor Bedard", "connor bedard psa 10") is None
assert ts_.libelle("young guns") == "Young Guns"
for k, carte in (("young guns", 1), ("young guns psa 10", 1), ("upper deck young guns canvas", 1), ("dazzlers blue", 1), ("mvp gold script", 1),
                 ("future watch auto", 1), ("o-pee-chee platinum emerald surge auto", 1), ("young guns exclusives /100", 1), ("mvp gold", 1),
                 # des paniers : plusieurs cartes differentes sous une meme recherche
                 ("rookie auto", 0), ("rc auto", 0), ("gold auto", 0), ("o-pee-chee", 0), ("o-pee-chee psa 8", 0), ("sp authentic auto", 0),
                 ("clear cut auto", 0), ("fleer ultra", 0), ("portfolio", 0), ("the cup rookie auto patch", 0), ("red", 0)):
    assert ts_._precise("X Y", k) == bool(carte), k
for t, an in (("2025-26 Upper Deck Jacob Fowler Young Guns", 2025), ("25/26 Upper deck Series 1 Elias Pettersson Young Guns #223", 2025),
              ("2016/17 UD SERIES 1 YOUNG GUNS", 2016), ("2025/2026 Upperdeck Extended", 2025), ("Young Guns 97-98", 1997), ("99-00 Upper Deck", 1999),
              ("Connor Bedard Young Guns #451 PSA 10", None), ("Bedard auto 12/99", None), ("card 10/25 numbered", None)):
    assert ts_.saison_du_titre(t) == an, (t, ts_.saison_du_titre(t))
R = "kirill kaprizov young guns"
assert ts_.vente_detail("2020-21 Upper Deck Kirill Kaprizov Young Guns #451", R) == 2020
assert ts_.vente_detail("2024-25 Upper Deck Series 2 - Young Guns Renewed Kirill Kaprizov #451", R) is False       # une AUTRE carte (3 $)
assert ts_.vente_detail("2024-25 Young Guns Renewed Kaprizov", R + " renewed") == 2024                              # ... sauf si on la cherche
assert ts_.vente_detail("2026/27 Upper Deck Cole Hutson Rookie YOUNG GUNS + Dazzlers", "cole hutson young guns") is False   # un lot
assert ts_.vente_detail("Connor Bedard 1st Overall Pick Young Guns", "connor bedard young guns") is None           # pas un lot ; saison inconnue

# ---------------------------------------------------------------- la carte d'un joueur
F = entree("Jacob Fowler", "jacob fowler young guns", ventes(50, 90, 2025))
r = ts_.listes([F], AUJ)
c = r["cartes"]["jacob fowler|young guns|2025"]
assert c["sens"] == "hausse" and c["joueur"] == "Jacob Fowler" and c["saison"] == 2025 and c["n"] == 26 and c["n_re"] == 12, c
assert 74 <= c["brut"] <= 86 and c["pct"] <= c["brut"] and c["pct"] >= 50, (c["pct"], c["brut"])       # le chiffre affiche est PRUDENT
assert c["p"] is not None and c["p"] < ts_.P_CARTE and c["coherent"], c
# la courbe : 100 = le niveau des 60 jours d'avant ; les points recents vont dans le sens du pourcentage
sv = [v for _d, v in c["serie"]]
assert len(sv) >= 5 and 92 <= sv[0] <= 108 and sv[-1] > 150 and c["n_recents"] >= 2, sv

# la MEME vente rangee sous deux recherches (« jacob fowler young guns », « jacob fowler hockey ») n'est comptee qu'une fois
F2 = entree("Jacob Fowler", "2025-26 jacob fowler young guns", [list(x) for x in F["ventes"][:20]], annee=2025)
c2 = ts_.listes([F, F2], AUJ)["cartes"]["jacob fowler|young guns|2025"]
assert c2["n"] == 26 and c2["brut"] == c["brut"], (c2["n"], c2["brut"])
# ... meme si l'adresse de la vente est ecrite autrement (le numero la reconnait)
F3 = entree("Jacob Fowler", "fowler young guns", [[x[0], x[1], x[2].replace("https://www.ebay.ca/itm/", "https://www.ebay.com/itm/") + "?hash=abc", x[3]] for x in F["ventes"]])
assert ts_.listes([F, F3], AUJ)["cartes"]["jacob fowler|young guns|2025"]["n"] == 26

# deux saisons de la meme sorte = deux cartes (les Dazzlers Blue de Celebrini : 2024-25, 2025-26) : jamais melangees
D = entree("Macklin Celebrini", "macklin celebrini dazzlers blue", ventes(110, 70, 2024) + ventes(30, 30, 2025))
rc = ts_.listes([D], AUJ)["cartes"]
assert set(rc) == {"macklin celebrini|dazzlers blue|2024", "macklin celebrini|dazzlers blue|2025"}, sorted(rc)
assert rc["macklin celebrini|dazzlers blue|2024"]["sens"] == "baisse" and rc["macklin celebrini|dazzlers blue|2025"]["sens"] == "stable", rc
assert rc["macklin celebrini|dazzlers blue|2024"]["n"] == 26
# une saison inconnue (aucun titre date) : on ne peut pas dire que c'est UNE carte
assert not ts_.listes([entree("Jack Quinn", "jack quinn dazzlers blue", ventes(40, 80, None))], AUJ)["cartes"]
# une seule saison (90 % des ventes datees) : une carte, avec ses ventes sans annee ; les rares ventes d'une autre annee restent de cote
M = ventes(40, 40, 2025, n_av=10, n_re=8) + ventes(40, 40, 2026, n_av=1, n_re=1, debut=20) + ventes(40, 40, None, n_av=2, n_re=2, debut=22)
mm = ts_.listes([entree("Michael Misa", "michael misa young guns", M)], AUJ)["cartes"]
assert set(mm) == {"michael misa|young guns|2025"} and mm["michael misa|young guns|2025"]["n"] == 22, {k: x["n"] for k, x in mm.items()}
# la recherche nomme sa saison : seules ses ventes de cette saison (ou sans annee) comptent
N_ = entree("Kirill Kaprizov", "2020-21 kirill kaprizov young guns", ventes(70, 80, 2020) + ventes(3, 3, 2024), annee=2020)
assert ts_.listes([N_], AUJ)["cartes"]["kirill kaprizov|young guns|2020"]["n"] == 26
# ... et ses ventes SANS annee ne comptent que si les ventes datees sont bien d'une seule saison (« Connor McDavid UD Portraits » : de
# quelle annee ?)
N2 = entree("Connor McDavid", "2015-16 connor mcdavid dazzlers blue", ventes(70, 80, 2015) + ventes(70, 80, None, n_av=4, n_re=4, debut=15), annee=2015)
assert ts_.listes([N2], AUJ)["cartes"]["connor mcdavid|dazzlers blue|2015"]["n"] == 34
N3 = entree("Connor McDavid", "2015-16 connor mcdavid dazzlers blue", ventes(70, 80, 2015) + ventes(9, 9, 2019) + ventes(70, 80, None, n_av=4, n_re=4, debut=15), annee=2015)
assert ts_.listes([N3], AUJ)["cartes"]["connor mcdavid|dazzlers blue|2015"]["n"] == 26

# des paniers ne sont jamais mesures : « rookie auto » (toutes ses autos de recrue), un set seul
P_ = [entree("Zayne Parekh", "zayne parekh rookie auto", ventes(60, 120, 2025)), entree("Bobby Orr", "bobby orr o-pee-chee", ventes(200, 400, 1970))]
assert not ts_.listes(P_, AUJ)["cartes"] and not ts_._cartes_exactes(P_)
# « case hit serie select », « metal universe hobby box » : pas un joueur ; « Alexander Ovechkin » = Alex Ovechkin
assert not ts_._cartes_exactes([entree("Case Hit", "case hit serie select", ventes(50, 90, 2025)), entree("Metal Universe Hobby", "metal universe hobby box", ventes(200, 300, 2025))])
assert ts_._cle_joueur("Case Hit") is None and ts_._cle_joueur("Alexander Ovechkin") == "alex ovechkin" and ts_._cle_joueur("Jacob Fowler") == "jacob fowler"
ov = ts_.listes([entree("Alexander Ovechkin", "alexander ovechkin young guns", ventes(900, 1300, 2005))], AUJ)["cartes"]
assert set(ov) == {"alex ovechkin|young guns|2005"} and ov["alex ovechkin|young guns|2005"]["joueur"] == "Alex Ovechkin", ov
# un autre sport n'entre jamais
assert not ts_._cartes_exactes([entree("Shohei Ohtani", "shohei ohtani dazzlers blue", ventes(50, 90, 2025), sport="baseball")])

# « on se fout des paralleles qui se vendent 20 $ et moins, a part les Young Guns »
pe = ts_.listes([entree("Cole Caufield", "cole caufield debut dates", ventes(8, 16, 2025)), entree("Cole Caufield", "cole caufield young guns", ventes(12, 18, 2020)),
                 entree("Cole Caufield", "cole caufield dazzlers pink", ventes(45, 70, 2025))], AUJ)["cartes"]
assert set(pe) == {"cole caufield|young guns|2020", "cole caufield|dazzlers pink|2025"} and ts_.PRIX_MIN_HORS_YG == 20, sorted(pe)

# des ventes trop vieilles : « 30 derniers jours » serait faux. La date de la derniere LECTURE compte, pas seulement la derniere vente
V = ventes(50, 90, 2025, n_av=14, n_re=8, debut=14)                      # sa derniere vente a 14 jours
assert not ts_.listes([entree("Ivan Demidov", "ivan demidov young guns", V)], AUJ)["cartes"]
assert ts_.listes([entree("Ivan Demidov", "ivan demidov young guns", V, lu=jr(1) + "T08:00:00")], AUJ)["cartes"]         # lue hier : elle se vend peu, c'est tout
assert not ts_.listes([entree("Ivan Demidov", "ivan demidov young guns", V, lu=jr(15))], AUJ)["cartes"] and ts_.FRAIS_J == 10

# des prix tres etales dans une meme semaine : la recherche melange deux cartes : rien
X = ventes(20, 20, 2025)
for i, x in enumerate(X):
    x[1] = x[1] * (25 if i % 2 else 1)
assert not ts_.listes([entree("Nick Suzuki", "nick suzuki dazzlers blue", X)], AUJ)["cartes"]
# ... mais une carte qui monte vite garde des prix serres chaque semaine : elle reste
Y = [[jr(88 - 3 * i), 10 * (1.09 ** i), "https://www.ebay.ca/itm/%d" % (910000000000 + i), 2025] for i in range(30)]
assert "lane hutson|young guns|2025" in ts_.listes([entree("Lane Hutson", "lane hutson young guns", Y)], AUJ)["cartes"]

# pas assez de ventes (12, et 4 dans chaque periode) : pas de carte ; un ecart trop faible pour le test : mesuree, rien d'annonce
assert not ts_.listes([entree("Tomas Hertl", "tomas hertl young guns", ventes(30, 60, 2013, n_av=6, n_re=3))], AUJ)["cartes"]
flou = ventes(50, 53, 2025, n_av=6, n_re=6)
cf = ts_.listes([entree("Will Smith", "will smith young guns", flou)], AUJ)["cartes"]["will smith|young guns|2025"]
assert cf["sens"] == "stable" and not cf["confirme"], cf
pf = ts_.public(cf)
assert pf["pct"] is None and pf["brut"] is None and pf["net"] is False, pf                 # AUCUN pourcentage a l'ecran

# ---------------------------------------------------------------- ce qu'un ecran recoit : un indice et un %, jamais un prix
pu = ts_.public(c)
assert set(pu) == {"cle", "nom", "pct", "sens", "net", "n", "n_re", "n_cartes", "n_joueurs", "serie", "jours", "j_rec", "n_recents", "du", "au",
                   "niveau", "joueur", "saison", "brut"}, sorted(pu)
assert pu["niveau"] == "carte" and pu["joueur"] == "Jacob Fowler" and pu["saison"] == "2025-26" and pu["pct"] == c["pct"], pu
assert pu["jours"][0] == 0 and pu["jours"] == sorted(pu["jours"]) and len(pu["jours"]) == len(pu["serie"]) and pu["j_rec"] is not None, pu
assert all(40 <= v <= 400 for v in pu["serie"])
txt = json.dumps(pu).lower()
assert "$" not in txt and not any(m in txt for m in ('"prix', '"mediane', '"valeur', '"norm', '"lr"', '"disp"')), txt

# ---------------------------------------------------------------- la sorte, tous joueurs : la moyenne des cartes exactes
JOUEURS = ["Connor Bedard", "Macklin Celebrini", "Lane Hutson", "Matvei Michkov", "Cole Caufield", "Ivan Demidov", "Nick Suzuki"]
C = [entree(j, j.lower() + " young guns", ventes(40 + 30 * i, (40 + 30 * i) * 0.78, 2020 + i)) for i, j in enumerate(JOUEURS[:6])]
C += [entree(j, j.lower() + " future watch auto", ventes(120 + 50 * i, (120 + 50 * i) * 1.32, 2020 + i)) for i, j in enumerate(JOUEURS[:6])]
C += [entree(j, j.lower() + " sizzle reel", ventes(60 + 10 * i, 60 + 10 * i, 2025)) for i, j in enumerate(JOUEURS[:6])]
C += [entree(j, j.lower() + " ice premieres", ventes(300, 450, 2025)) for j in JOUEURS[:4]]                  # 4 cartes : pas assez pour une sorte
rs = ts_.listes(C, AUJ)
ps = rs["sortes"]
assert set(ps) == {"young guns", "future watch auto", "sizzle reel"}, sorted(ps)
assert ps["young guns"]["sens"] == "baisse" and -25 <= ps["young guns"]["pct"] <= -12 and ps["young guns"]["n_cartes"] == 6 and ps["young guns"]["n"] == 6 * 26, ps["young guns"]
assert ps["future watch auto"]["sens"] == "hausse" and ps["sizzle reel"]["sens"] == "stable", ps
pus = ts_.public(ps["young guns"])
assert pus["niveau"] == "sorte" and "joueur" not in pus and "brut" not in pus, pus
# les listes : des cartes de 20 ventes et plus, classees par leur pourcentage
assert [x["cle"] for x in rs["cartes_baisses"]][:1] and all(x["n"] >= ts_.LISTE_VENTES_MIN and x["sens"] == "baisse" for x in rs["cartes_baisses"]), rs["cartes_baisses"]
assert all(x["sens"] == "hausse" for x in rs["cartes_hausses"]) and len(rs["cartes_hausses"]) == 10, len(rs["cartes_hausses"])     # 6 Future Watch + 4 Ice Premieres

# ---------------------------------------------------------------- calculer : rien n'est publie tant que les ventes ne sont pas triees
import base_ventes
appels = []
base_ventes.cartes_toutes = lambda **k: (appels.append(k) or C)
base_ventes.A_TRIER["n"] = 5000                                             # la derniere passe a laisse 5 000 ventes a trier
ch = os.path.join(comptes.DONNEES, "tendance_sortes.json")
rp = ts_.calculer(AUJ)
assert rp.get("partiel") == 5000 and not os.path.exists(ch) and appels[0].get("detail") is True and appels[0].get("jours") == ts_.JOURS_LUS, (rp, appels)
with contextlib.redirect_stdout(io.StringIO()) as jl:
    assert ts_.calculer_si_besoin() is None and not os.path.exists(ch)
    assert ts_.calculer_si_besoin() is None and len(appels) == 2             # pas deux essais en moins de 10 minutes
assert "encore a trier" in jl.getvalue(), jl.getvalue()
base_ventes.A_TRIER["n"] = 0
ts_._ESSAI["le"] = 0.0
with contextlib.redirect_stdout(io.StringIO()) as jl:
    assert ts_.calculer_si_besoin() and os.path.exists(ch) and len(appels) == 3
assert "cartes mesurees" in jl.getvalue() and "3 sortes mesurees" in jl.getvalue(), jl.getvalue()
assert ts_.AUX_JOURS == 3 and ts_.calculer_si_besoin() is None and len(appels) == 3          # frais : rien a refaire avant 3 jours
os.utime(ch, (time.time() - 4 * 86400,) * 2)
with contextlib.redirect_stdout(io.StringIO()):
    assert ts_.calculer_si_besoin() and len(appels) == 4
pg = ts_.page()
assert pg["hausses"] and all(x["niveau"] == "carte" for x in pg["hausses"] + pg["baisses"]) and {x["cle"] for x in pg["toutes"]} == set(ps), pg["hausses"][:1]
assert pg["n_sortes"] == 3 and pg["n_cartes"] == len(rs["cartes"]) and pg["jours"] == [30, 60]
tp = json.dumps(pg).lower()
assert "$" not in tp and not any(m in tp for m in ('"prix', '"mediane', '"valeur', '"norm', '"lr"', '"disp"')), tp[:300]

# ---------------------------------------------------------------- l'annonce d'un joueur recoit SA carte, de SA saison
t = ts_.de_titre("2020-21 Upper Deck Connor Bedard Young Guns #451", "Connor Bedard")
assert t and t["cle"] == "connor bedard|young guns|2020" and t["niveau"] == "carte" and t["sens"] == "baisse", t
assert ts_.de_titre("20/21 UD Connor Bedard Young Guns #451", "Connor Bedard")["cle"] == "connor bedard|young guns|2020"
assert ts_.de_titre("Connor Bedard Young Guns #451", "Connor Bedard")["cle"] == "connor bedard|young guns|2020"            # une seule carte : pas d'ambiguite
tx = ts_.de_titre("2015-16 Upper Deck Connor McDavid Young Guns #201", "Connor McDavid")                                  # pas de mesure a lui : la sorte
assert tx and tx["niveau"] == "sorte" and tx["cle"] == "young guns" and "joueur" not in tx, tx
for autre in ("2024-25 Upper Deck Connor Bedard Young Guns #451",                      # une autre saison : une autre carte...
              "2020-21 Upper Deck Connor Bedard Young Guns Exclusives /100", "2020-21 Upper Deck Connor Bedard Young Guns Canvas",
              "2020-21 Upper Deck Connor Bedard Young Guns PSA 10", "2020-21 Upper Deck Young Guns Renewed Connor Bedard",
              "2020-21 Upper Deck Connor Bedard Young Guns + Dazzlers", "2020-21 Upper Deck Series 2 Connor Bedard base #201", ""):
    x = ts_.de_titre(autre, "Connor Bedard")
    assert x is None or x["niveau"] == "sorte" and "2024-25" in autre, (autre, x)        # ... (la sorte tous joueurs reste vraie pour 2024-25)
# deux cartes differentes ne sont jamais compilees ensemble (ses exemples)
ref = lambda k, t_: bool(cartes_match.raisons_refus(cartes_match.cible("Connor Bedard " + k), t_))
assert ref("o-pee-chee platinum auto", "2023-24 O-Pee-Chee Platinum Connor Bedard Emerald Surge Auto /10")
assert ref("o-pee-chee platinum auto", "2023-24 O-Pee-Chee Platinum Connor Bedard Violet Pixels Auto /299")
assert ref("o-pee-chee platinum emerald surge auto", "2023-24 O-Pee-Chee Platinum Connor Bedard Violet Pixels Auto /299")
assert ref("o-pee-chee platinum emerald surge auto", "2023-24 O-Pee-Chee Platinum Connor Bedard Emerald Surge /10")
assert ref("o-pee-chee platinum emerald surge", "2023-24 O-Pee-Chee Platinum Connor Bedard Emerald Surge Auto /10")

# ---------------------------------------------------------------- le serveur : Tendances, le Radar, la fenetre SlabIQ ; le Gratuit
import lockerroom
api = lockerroom.Api()
lockerroom.Api._TEND_IQ.update(v=None, le=0)
rt = api.tendances_iq()
assert rt.get("ok") and rt.get("sortes") and {x["cle"] for x in rt["sortes"]["toutes"]} == set(ps), {k: rt.get(k) for k in ("ok", "sortes")}
assert all(x["niveau"] == "carte" for x in rt["sortes"]["hausses"] + rt["sortes"]["baisses"])
grosse = {"ok": True, "cats": {}, "sortes": dict(pg, baisses=[dict(pu, cle=f"s{i}", joueur=f"Joueur {i}") for i in range(8)])}
g = api._tendances_gratuit(grosse)
vb = g["sortes"]["baisses"]
assert len(vb) == 8 and sum(1 for x in vb if x.get("verrou")) == 8 - api.TEND_GRATUIT and all(x.get("verrou") for x in vb[:3]), vb
assert all(set(x) == {"verrou", "pct", "sens", "serie"} for x in vb if x.get("verrou")) and g["sortes"]["toutes"] == [], vb[0]     # ni le joueur ni la carte
T_YG = "2020-21 Upper Deck Connor Bedard Young Guns #451"
rr = api._pastilles_radar({"ok": True, "a_la_une": [{"item_id": "1", "titre": T_YG, "joueur": "Connor Bedard"},
                                                    {"item_id": "2", "titre": "2023 Topps Chrome Shohei Ohtani", "joueur": "Shohei Ohtani", "sport": "baseball"}]})
assert rr["a_la_une"][0]["tend"]["cle"] == "connor bedard|young guns|2020" and "tend" not in rr["a_la_une"][1], rr["a_la_une"]
sc = api.annonce_score(T_YG, "Connor Bedard")
assert (sc.get("tend") or {}).get("cle") == "connor bedard|young guns|2020", sc.get("tend")

# ---------------------------------------------------------------- de bout en bout, par le VRAI chemin du serveur (base_ventes)
import importlib
d2 = tempfile.mkdtemp()
os.environ["LOCKERROOM_DONNEES"] = d2
comptes.DONNEES = d2
importlib.reload(base_ventes)
ts_._MEM.update(mtime=None, v=None, idx=None); ts_._TITRES.clear(); ts_._ESSAI["le"] = 0.0
MAINT = datetime.now()
jr2 = lambda n: (MAINT - timedelta(days=n)).strftime("%Y-%m-%d")
T1 = "2025-26 Upper Deck Series 2 Jacob Fowler Young Guns #461"


def lot(prix_av, prix_re, titre, base_id, n_av=14, n_re=12):
    return ([{"titre": titre, "prix": prix_av * (1 + 0.04 * ((i % 3) - 1)), "le": jr2(31 + 2 * i), "url": "https://www.ebay.ca/itm/%d" % (base_id + i)} for i in range(n_av)]
            + [{"titre": titre, "prix": prix_re * (1 + 0.04 * ((i % 3) - 1)), "le": jr2(1 + 2 * i), "url": "https://www.ebay.ca/itm/%d" % (base_id + 100 + i)} for i in range(n_re)])


vraies = lot(50, 90, T1, 310000000000)
renewed = lot(3, 3, "2025-26 Upper Deck Young Guns Renewed Jacob Fowler #YGR-9", 320000000000, 8, 8)       # une autre carte, a 3 $
unlot = lot(200, 200, "2025-26 Upper Deck Jacob Fowler Young Guns + Dazzlers", 330000000000, 4, 4)         # un lot
canvas = lot(300, 300, "2025-26 Upper Deck Jacob Fowler Young Guns Canvas", 340000000000, 6, 6)            # une variante
assert base_ventes.noter("jacob fowler young guns", vraies + renewed + unlot + canvas, sport="hockey")
assert base_ventes.noter("jacob fowler hockey", vraies[:20] + canvas, sport="hockey")                      # les memes ventes, par une autre recherche
with contextlib.redirect_stdout(io.StringIO()):
    r3 = ts_.calculer()
assert not r3.get("partiel") and base_ventes.A_TRIER["n"] == 0, r3.get("partiel")
c3 = r3["cartes"].get("jacob fowler|young guns|2025")
assert c3, sorted(r3["cartes"])
assert c3["n"] == 26 and c3["n_re"] == 12 and c3["sens"] == "hausse" and 74 <= c3["brut"] <= 86, c3          # ni Renewed, ni lot, ni Canvas, ni doublon
det = base_ventes.cartes_toutes(jours=130, n_min=4, max_q=20000, detail=True)
e0 = [e for e in det if e["q"] == "jacob fowler young guns"][0]
assert e0["lu_le"] and len(e0["ventes"]) == 26 and all(v[3] == 2025 and v[2].startswith("https://www.ebay.ca/itm/31") for v in e0["ventes"]), e0["ventes"][:2]
# 26 nov 2026 (Mathieu : « corrige ») : cartes_match refuse maintenant lui-meme la Renewed et le lot « + » (avant, seul le
# garde-fou des tendances les ecartait : les comps des autres ecrans les gardaient)
assert len(e0["points"]) == 26, len(e0["points"])
assert "points" in base_ventes.cartes_toutes(jours=130)[0] and "ventes" not in base_ventes.cartes_toutes(jours=130)[0]      # sans detail : comme avant
tb = ts_.de_titre(T1, "Jacob Fowler")
assert tb and tb["cle"] == "jacob fowler|young guns|2025" and tb["pct"] == c3["pct"], tb

# ---------------------------------------------------------------- branche : la boucle du chasseur (aux 3 jours) et les ecrans
src = lambda f: open(os.path.join(RAC, f), encoding="utf-8").read()
assert "tendance_sortes.calculer_si_besoin()" in src("deals.py") and "tendance_sortes.passe_si_besoin()" in src("server.py")
# 26 nov 2026 : la boucle du serveur lance le calcul dans son fil (le chasseur seul ne suffisait pas : rien une heure apres le push)
import threading
ch2 = os.path.join(comptes.DONNEES, "tendance_sortes.json")
assert os.path.exists(ch2) and ts_.passe_si_besoin() is None                       # frais : rien a faire
os.utime(ch2, (time.time() - 4 * 86400,) * 2)
ts_._ESSAI["le"] = 0.0
ts_._ETAT["en_cours"] = True
assert ts_.passe_si_besoin() is None and ts_.calculer_si_besoin() is None          # un calcul tourne deja : jamais deux a la fois
ts_._ETAT["en_cours"] = False
with contextlib.redirect_stdout(io.StringIO()) as jl:
    assert ts_.passe_si_besoin() is True
    for th in threading.enumerate():
        if th.name == "tendance-sortes":
            th.join(120)
assert "cartes mesurees" in jl.getvalue() and time.time() - os.path.getmtime(ch2) < 120 and not ts_._ETAT["en_cours"], jl.getvalue()
assert ts_.passe_si_besoin() is None
# 26 nov 2026 (journal du serveur apres le push : « 54 554 ventes encore a trier ») : le fil enchaine les passes de tri jusqu'au
# bout au lieu d'attendre la boucle de l'heure suivante ; il s'arrete si une passe n'avance pas
def fil(reponses):
    appels = []
    vrai = ts_.calculer
    ts_.calculer = lambda maint=None: (appels.append(1), reponses[min(len(appels), len(reponses)) - 1])[1]
    os.utime(ch2, (time.time() - 4 * 86400,) * 2)
    ts_._ESSAI["le"] = 0.0
    try:
        with contextlib.redirect_stdout(io.StringIO()) as j:
            assert ts_.passe_si_besoin() is True
            for th in threading.enumerate():
                if th.name == "tendance-sortes":
                    th.join(60)
    finally:
        ts_.calculer = vrai
    return len(appels), j.getvalue()
ts_.PAUSE_PASSE_S = 0
fini = {"n_cartes": 148, "cartes_hausses": [], "cartes_baisses": [], "n_sortes": 2, "n_cartes_lues": 9, "n_ventes": 99}
n_, jl2 = fil([{"partiel": 54554, "lues": 184498}, {"partiel": 39554, "lues": 199498}, {"partiel": 24554, "lues": 214498}, fini])
assert n_ == 4 and jl2.count("encore a trier") == 3 and "148 cartes mesurees" in jl2, (n_, jl2)
n_, jl2 = fil([{"partiel": 54554, "lues": 1}, {"partiel": 54554, "lues": 1}, fini])
assert n_ == 2 and "cartes mesurees" not in jl2, "le tri n'avance pas : le fil s'arrete (la boucle de l'heure reessaiera)"
n_, jl2 = fil([{"partiel": 900000 - 60000 * i, "lues": 1} for i in range(40)])
assert n_ == ts_.PASSES_MAX, n_                                                    # jamais plus de PASSES_MAX passes de suite
assert not ts_._ETAT["en_cours"]

# ---------------------------------------------------------------- 26 nov 2026 : la carte et le RESTE du joueur, par joueur
# (Mathieu : « separer carte, separer joueur, mais aussi un mix des deux ; aucune erreur, sinon on perd toute notre credibilite »)
assert ts_.base_carte("young guns psa 10") == ts_.base_carte("upper deck young guns 201") == ts_.base_carte("young guns") == "young guns"
assert ts_.base_carte("young guns canvas bgs 9.5") == "young guns canvas" != ts_.base_carte("young guns")
def mesure_de(pct, n=30):                        # une carte mesuree : n ventes avant, n ventes dans les 30 derniers jours
    pts = [(jr2(40 + i), 100 * (1 + 0.02 * ((i % 3) - 1))) for i in range(n)] + [(jr2(2 + (i % 26)), 100 * (1 + pct / 100) * (1 + 0.02 * ((i % 3) - 1))) for i in range(n)]
    m = ts_.mesure_carte(pts, MAINT); m["saison"] = 2025
    return m
def croix(pct_carte, autres, sens_carte=None):
    mes = [("Test Joueur", "test joueur", "young guns", mesure_de(pct_carte))] + [("Test Joueur", "test joueur", k, mesure_de(p_, n_)) for k, p_, n_ in autres]
    pc = ts_.par_carte(None, MAINT, mes)
    return ts_.croiser(pc, mes, MAINT)["test joueur|young guns|2025"]
x = croix(-20, [("young guns canvas", -25, 30), ("dazzlers green", -30, 30)])
assert x["sens"] == "baisse" and x["reste"]["sens"] == "baisse" and x["reste"]["n_cartes"] == 2 and x["croix"] == "joueur_baisse", x.get("reste")
x = croix(-20, [("young guns psa 10", -25, 30), ("upper deck young guns 201", -30, 30)])
assert "reste" not in x and not x.get("croix"), "la meme carte dans une autre note ou sous un autre nom n'est PAS le reste du joueur"
x = croix(-20, [("young guns canvas", -25, 4)])
assert "reste" not in x, "moins de 20 ventes pour le reste : rien n'est dit"
x = croix(+30, [("young guns canvas", -25, 30)])
assert x["sens"] == "hausse" and x["reste"]["sens"] == "baisse" and x["croix"] is None, "la carte monte : le fait mesure ne s'applique pas"
x = croix(+30, [("young guns canvas", 0, 30)])
assert x["reste"]["sens"] == "neutre" and x["croix"] is None, "« monte seule » n'est PAS un signal (faux signal du 1er essai) : aucun mot"
x = croix(+30, [("young guns canvas", +30, 30)])
assert x["reste"]["sens"] == "hausse" and x["croix"] is None, "tout monte : pas un signal non plus"
M = ts_.CROISE_MESURE["joueur_baisse"]
assert set(ts_.CROISE_MESURE) >= {"le", "du", "au", "joueur_baisse"} and "seule" not in ts_.CROISE_MESURE and M["baissent"] + M["montent"] <= M["joueurs"] and M["ic95"][1] < 0
pub = ts_.public(croix(-20, [("young guns canvas", -25, 30)]))
assert pub["croix"] == "joueur_baisse" and pub["fait"] == {"baissent": M["baissent"], "joueurs": M["joueurs"], "depuis": 2024, "le": ts_.CROISE_MESURE["le"]}
assert pub["reste"]["pct"] is not None and "prix" not in json.dumps(pub) and "mediane" not in json.dumps(pub)
assert ts_.public(croix(+30, [("young guns canvas", 0, 30)]))["reste"] == {"sens": "neutre", "pct": None, "n": 60, "n_cartes": 1}, "pas de % quand le reste n'est pas net"
pg = ts_.page()
assert "par_joueur" in pg and pg["croise_mesure"] == ts_.CROISE_MESURE and all(len(g["cartes"]) >= 2 and g["joueur"] for g in pg["par_joueur"])
import inspect, lockerroom as lr_
assert 'so["par_joueur"] = []' in inspect.getsource(lr_.Api._tendances_gratuit), "Gratuit : pas la vue Joueur + cartes"

# ---------------------------------------------------------------- 26 nov 2026 : « Joueur + cartes » = UN chiffre par joueur
# (Mathieu, capture de « ▼1 ●2 » : « c'est juste plus complique pour rien » ; « Oui A, ca doit etre comprehensible en 1 sec »)
def ensemble(cartes_j):                          # {joueur: [(sorte, pct, n)]} -> (pc, joueurs_ensemble)
    mes = [(j, j.lower(), k, mesure_de(p_, n_)) for j, l in cartes_j.items() for k, p_, n_ in l]
    pc = ts_.par_carte(None, MAINT, mes)
    return pc, ts_.joueurs_ensemble(pc, mes, MAINT)
pc_, je = ensemble({"Monte Fort": [("young guns", +30, 30), ("young guns canvas", +25, 30), ("dazzlers green", +35, 30)],
                    "Baisse Net": [("young guns", -20, 30), ("young guns psa 10", -25, 30)],
                    "Une Carte": [("young guns", +30, 30)],
                    "Bouge Pas": [("young guns", +1, 30), ("young guns canvas", -1, 30)],
                    "Tire Deux": [("young guns", +30, 30), ("young guns canvas", -30, 30)],
                    "Peu Vendu": [("young guns", +30, 6), ("young guns canvas", +30, 6)]})
assert set(je) == {"monte fort", "baisse net", "bouge pas", "tire deux"}, set(je)      # 2 cartes mesurees et 40 ventes au moins
m_ = je["monte fort"]
assert m_["sens"] == "hausse" and 20 <= m_["pct"] <= 35 and m_["n_cartes"] == 3 and m_["n"] == 180 and m_["joueur"] == "Monte Fort" and m_["cle"] == "joueur:monte fort"
assert sorted(m_["cartes"]) == sorted(k for k in pc_ if k.startswith("monte fort|")), "exactement les cartes qu'on voit en touchant le joueur"
assert je["baisse net"]["sens"] == "baisse" and je["baisse net"]["n_cartes"] == 2, "les notes d'une meme carte comptent : ce sont toutes SES cartes"
assert je["bouge pas"]["sens"] == "stable" and je["tire deux"]["sens"] == "stable", "sans mouvement net : dans aucune liste"
assert ts_.JOUEUR_CARTES_MIN == 2 and ts_.JOUEUR_VENTES_MIN == 40 and ts_.FORMAT == 2
# le meme test que LA carte d'un joueur (p < 0,01), pas celui d'une sorte (p < 0,10)
src_ts = inspect.getsource(ts_.joueurs_ensemble)
assert 'a["p"] < P_CARTE' in src_ts
# dans le fichier, puis a l'ecran : deux listes, un % par joueur, ses cartes pour la fenetre, jamais un prix
mes_ = [(j, j.lower(), k, mesure_de(p_, n_)) for j, l in {"Monte Fort": [("young guns", +30, 30), ("young guns canvas", +25, 30)], "Baisse Net": [("young guns", -20, 30), ("young guns canvas", -25, 30)],
                                                             "Bouge Pas": [("young guns", +1, 30), ("young guns canvas", -1, 30)]}.items() for k, p_, n_ in l]
vrai_mes = ts_._mesures
ts_._mesures = lambda cartes, auj: mes_
try:
    L_ = ts_.listes([], MAINT)
finally:
    ts_._mesures = vrai_mes
assert L_["format"] == 2 and [x["joueur"] for x in L_["joueurs_hausses"]] == ["Monte Fort"] and [x["joueur"] for x in L_["joueurs_baisses"]] == ["Baisse Net"] and len(L_["joueurs"]) == 3
vrai_lire = ts_.lire
ts_.lire = lambda: json.loads(json.dumps(L_))
try:
    pg2 = ts_.page()
    J2 = pg2["joueurs"]
    assert J2["n"] == 3 and len(J2["hausses"]) == 1 and len(J2["baisses"]) == 1
    h_ = J2["hausses"][0]
    assert h_["joueur"] == "Monte Fort" and h_["niveau"] == "joueur" and h_["net"] is True and h_["pct"] > 0 and h_["n_cartes"] == 2 and len(h_["cartes"]) == 2 and len(h_["serie"]) >= 2
    assert all(c["niveau"] == "carte" and c["joueur"] == "Monte Fort" for c in h_["cartes"]) and "saison" not in h_
    assert "prix" not in json.dumps(J2) and "mediane" not in json.dumps(J2), "jamais un prix"
    # un fichier d'avant (sans « joueurs ») : la vue n'est pas envoyee, et le calcul est refait au prochain tour
    vieux = {k: v for k, v in L_.items() if k not in ("joueurs", "joueurs_hausses", "joueurs_baisses", "format")}
    ts_.lire = lambda: json.loads(json.dumps(vieux))
    assert ts_.page()["joueurs"] is None
finally:
    ts_.lire = vrai_lire
assert '(lire() or {}).get("format") == FORMAT' in inspect.getsource(ts_.calculer_si_besoin), "un fichier d'avant est refait sans attendre 3 jours"
assert 'so["joueurs"] = None' in inspect.getsource(lr_.Api._tendances_gratuit), "Gratuit : pas la vue Joueur + cartes"
# 26 nov 2026, 13 h 31 (Mathieu, captures de Lowest / Highest / Players : « on pourrait mettre la note du joueur a cote du trend ?
# comme ca on aurait seulement 2 onglets ; garder Rising et Falling pour les 2 ») : DEUX onglets (Joueurs | Cartes), la vue
# « Joueur + cartes » disparait de l'ecran (la mesure reste sur le serveur) ; joueurs : En hausse | En baisse, la note SlabIQ du
# joueur a droite de son % ; les memes mots pour les joueurs et les cartes
sx2 = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "src_app.html"), encoding="utf-8").read()
assert "modeT === 'mix'" not in sx2 and "data-jmix" not in sx2 and "Player + cards" not in sx2 and "tiq-mode3\"" not in sx2, "plus d'onglet « Joueur + cartes »"
assert "[['joueurs', tt('Joueurs', 'Players')], ['sortes', tt('Cartes', 'Cards')]].map(" in sx2, "deux onglets en haut"
assert "▲ en hausse · ▼ en baisse" not in sx2, "plus de symboles a decoder"
assert "[['vendre', aH ? tt('En hausse', 'Rising') : tt('À vendre', 'To sell'), aV || aH], ['bas', tt('En baisse', 'Falling'), aB]," in sx2, "joueurs : En hausse d'abord, puis En baisse, comme les cartes"
assert "tt('Plus bas', 'Lowest') : tt('Au plus bas', 'Lowest')" not in sx2 and "'Highest'" not in sx2 and "At their lowest" not in sx2 and "At their highest" not in sx2
assert "['bas', tt('Joueurs en baisse', 'Falling players'), 'vert'], ['haut', tt('Joueurs en hausse', 'Rising players'), 'vert']" in sx2
assert "const OPT = [['bas', tt('En hausse', 'Rising')], ['vendre', tt('En baisse', 'Falling')], ...(T_.length ? [['toutes', tt('Par sorte', 'By type')]] : [])];" in sx2, "cartes : inchange"
# la note du joueur : a droite de son %, sur les lignes des listes de faits seulement ; une ligne verrouillee garde la place, vide
assert "const noteM = (x) =>" in sx2 and "${FAIT(k) ? noteM(x) : ''}</button>`; };" in sx2 and "${sg(v)}</span>${noteM(null)}</button>" in sx2
assert ".tiq-nj{flex:none; width:26px;" in sx2 and 'class="tiq-nj"' in sx2, "« tiq-lt » est deja le titre d'une liste : la note a sa propre classe"
lig_s = sx2[sx2.index("        const ligneS = (x, rg) =>"):sx2.index("        const panS = ")]
assert "noteM" not in lig_s, "pas de note du joueur sur une ligne de carte (elle se lirait comme la note de la carte)"
# « Les joueurs les plus recherches » : plus de puce au cell quand les tendances des cartes sont la ; la liste reste dans « Plus de listes »
assert "['joueurs', tt('Joueurs', 'Players'), top10.length > 0 && !SO]" in sx2
assert "!['bas', 'haut', 'vendre', 'marche_bas', 'en_feu', 'rebond', 'recrue'].includes(k)" in sx2
# le top 100 (« juste 16 risers ? On devrait en avoir le top 100 pour les 2 ») : le plafond monte, pas les regles
assert ts_.N_LISTE_CARTES == 100 and lr_.Api.TEND_TOP == 100 and ts_.P_CARTE == 0.01 and ts_.LISTE_VENTES_MIN == 20

# ---------------------------------------------------------------- 26 nov 2026 : relire les cartes exactes (1 000 credits par mois au plus)
import historique
assert ts_.RELIRE_MOIS == 1000 and ts_.plafond_relire() == 1000 and ts_.RELIRE_AGE_J == ts_.FRAIS_J - ts_.AUX_JOURS - 1
def carte_q(q, age, n=20, pas=3, prix=60.0):      # une recherche : n ventes regulieres, la derniere il y a « age » jours
    return {"joueur": "Jacob Fowler", "carte": q, "q": q, "sport": "hockey", "annee": 2025, "lu_le": jr2(age),
            "points": [[jr2(age + pas * i), prix + (i % 3)] for i in range(n)], "ventes": [[jr2(age + pas * i), prix + (i % 3), "4%011d" % (abs(hash(q)) % 10 ** 8 * 100 + i), 2025] for i in range(n)]}
AR = ts_.a_relire([carte_q("jacob fowler young guns", 12), carte_q("jacob fowler young guns canvas", 3), carte_q("jacob fowler dazzlers pink", 8, 8, 9),
                   carte_q("jacob fowler dazzlers blue", 15, 8, 9, 6.0)], MAINT)
assert [x[0] for x in AR] == ["jacob fowler young guns", "jacob fowler dazzlers pink"] and AR[0][1] == 12, AR      # la Canvas est fraiche (3 jours) ; la Blue vaut 6 $ (sous le plancher)
appels, cache = [], {}
vr, vc, va = historique.rechercher, historique._cache, historique.actif
historique.actif = lambda: True
historique._cache = lambda q, age=None: cache.get(q)
def faux_rechercher(q, **kw):
    assert kw.get("chasseur") and kw.get("principal") and kw.get("cache_s") == ts_.RELIRE_AGE_J * 86400, kw
    appels.append(q); return ([], "budget") if q == "panne" else ([{"titre": "x"}], None)
historique.rechercher = faux_rechercher
vl = ts_.lire
try:
    if os.path.exists(ts_._chemin_relire()): os.remove(ts_._chemin_relire())
    ts_.lire = lambda: {"a_relire": [["q%d" % i, 12, 50 - i] for i in range(8)]}
    cache["q2"] = [1]                                                                  # deja lue par une autre tache : gratuite
    os.environ["LR_RELIRE_MOIS"] = "5"
    with contextlib.redirect_stdout(io.StringIO()) as j3:
        assert ts_.relire(max_n=3) == 3 and appels == ["q0", "q1", "q3"], appels          # 3 par passe, les plus vendues d'abord
        assert ts_.relire(max_n=3) == 2 and appels[3:] == ["q4", "q5"], appels             # le plafond du mois (5) arrete la passe
        assert ts_.relire(max_n=3) == 0 and len(appels) == 5                                # plus un credit ce mois-ci
    e3 = ts_.etat_relire()
    assert e3["n"] == 5 and set(e3["faites"]) == {"q0", "q1", "q2", "q3", "q4", "q5"} and "5 / 5" in j3.getvalue(), (e3, j3.getvalue())
    os.environ["LR_RELIRE_MOIS"] = "50"
    ts_.lire = lambda: {"a_relire": [["panne", 12, 9], ["apres", 12, 8]]}
    assert ts_.relire() == 0 and appels[-1] == "panne", "budget du mois ou panne : on s'arrete, rien n'est compte"
    assert ts_.etat_relire()["n"] == 5
finally:
    historique.rechercher, historique._cache, historique.actif, ts_.lire = vr, vc, va, vl
    os.environ.pop("LR_RELIRE_MOIS", None)
    if os.path.exists(ts_._chemin_relire()): os.remove(ts_._chemin_relire())
assert "tendance_sortes.relire_si_besoin()" in src("server.py")
assert "a_relire" in json.load(open(ch2, encoding="utf-8")) and "a_relire" not in json.dumps(ts_.page()), "la liste a relire reste sur le serveur"

app = src("ui/app.html")
for m in ("data-tmode=", "tiq-nj", "resteTD", "it-vper", "data-per="):
    assert m in app, m
# 26 nov 2026 (Mathieu : « bug apres avoir refresh », le titre et la recherche de Trending descendus par-dessus les onglets) : pendant
# « tirer pour actualiser », #vue est decale par un transform ; la position de l'en-tete collant se mesure SANS ce decalage, et se
# remesure une fois la page remontee
sx = src("source/src_app.html")
assert "const ptrY = () =>" in sx and "tf.getBoundingClientRect().top - ptrY()" in sx and "APRES_PTR.f = fixer" in sx and "if (APRES_PTR.f) APRES_PTR.f()" in sx
assert "f.getBoundingClientRect().bottom - ptrY()" in sx, "la bande fixe des Breaks : la meme mesure"
assert "t.fait" in src("source/src_app.html") and "14 joueurs" not in src("source/src_app.html"), "les chiffres du fait viennent du serveur, pas de l'ecran"
for m in ("data-td=", "feuilleSorte", "data-tmode=", "badgeTend", "bandeTend", "ajusterPS", "psg", "tiq-mode"):
    assert m in app, m
s0 = src("source/src_app.html")
assert "t.niveau !== 'carte') return ''" in s0                              # le badge de la tuile : seulement LA carte du joueur
assert "100 = le niveau des 60 jours d’avant" in s0 and "Un fait, pas une promesse." in s0 and "environ ${a} %" in s0
# la fenetre SlabIQ : deux colonnes a l'ordi et un resserrement tant qu'elle deborde (« tout sur une page sans scroll »)
assert ".ps2.s1 " in s0 and ".ps2.s3 " in s0 and "feuille:has(> .ps2){max-width:880px}" in s0
print("TENDANCE DES CARTES OK")
