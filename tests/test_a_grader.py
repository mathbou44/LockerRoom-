"""26 nov 2026 (Mathieu : « savoir les cartes qui valent le plus la peine d'etre gradees [...] toutes les paralleles vendues en
PSA 10 ; la version raw versus la PSA 10 pour le meme genre de time frame ; le meilleur rapport achat versus vente ; dans Admin,
le temps qu'elle soit parfaite »). La liste « A grader » : chaque vente rangee par son TITRE, la meme periode, des medianes,
ce qui reste apres les frais ; jamais une chance de 10 supposee."""
import os, sys, tempfile, json, time
from datetime import datetime, timedelta, timezone, date
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import a_grader, grader
AUJ = datetime.now(timezone.utc).date()
jr = lambda k: (AUJ - timedelta(days=k)).isoformat()
cl = a_grader.classer
YG = "2024-25 Upper Deck Cutter Gauthier Young Guns #212"

# ---- 1. une vente = une carte exacte (joueur, mots de l'app, annee, /N, numero) et une note
assert cl(YG + " RC") == (("cutter gauthier", "cutter gauthier young guns", 2024, None, "212"), "raw")
assert cl(YG + " PSA 10 GEM MINT") == (("cutter gauthier", "cutter gauthier young guns", 2024, None, "212"), "10")
assert cl(YG + " PSA 9 MINT")[1] == "9"
assert cl("2024-25 Upper Deck Canvas Young Guns Cutter Gauthier #C96 PSA 10")[0][1] == "cutter gauthier young guns canvas", "une parallele = une autre carte"
assert cl("2023-24 Upper Deck Connor Bedard Young Guns Exclusives /100 PSA 10")[0][3] == 100, "une numerotee /100 reste une carte a part"
# ecartees : elles fausseraient un prix
for t, pq in ((YG + " PSA 10?", "une raw qui espere"), (YG + " Possible PSA 10", "une raw qui espere"), (YG + " PSA 10 ready", "une raw qui espere"), (YG + " PSA 10 contender", "une raw qui espere"),
              (YG + " PSA Ready", "pas de note"), (YG + " BGS 9.5", "une autre compagnie"), (YG + " CGC 10", "une autre compagnie"), (YG + " PSA 8", "une autre note"),
              (YG + " creased corner", "abimee"), (YG + " LOT of 3", "un lot"), (YG + " + Dazzlers", "un lot ecrit avec +"),
              ("Cutter Gauthier PSA 10 rookie card Ducks", "aucune carte nommee"), ("2026-27 Upper Deck Jack Hughes Gold PSA 10", "une couleur seule n'est pas une carte")):
    assert cl(t) is None, (t, pq, cl(t))
assert a_grader.P10_MIN == 5 and a_grader.RAW_MIN == 5 and a_grader.P9_MIN == 3 and a_grader.frais_psa() == grader.FRAIS_PSA + grader.ENVOI_PSA == 41.0
print("TITRES OK")

# ---- 2. la liste : la meme periode, des medianes, ce qui reste apres les frais
def V(pre, titre, prix, jours):
    return [(f"{pre}{i}", titre, p, jr(j), None) for i, (p, j) in enumerate(zip(prix, jours))]
ventes = (V("gr", YG, [36, 38, 40, 38, 37, 200, 39], [3, 10, 20, 30, 40, 44, 60])                           # raw : mediane 38 (une vente a 200 $ ne la tire pas)
          + V("g10", YG + " PSA 10", [400, 410, 406, 395, 420], [5, 15, 25, 35, 45]) + V("g9", YG + " PSA 9", [88, 90, 92], [6, 16, 26])
          + V("gx", YG + " PSA 10?", [60, 65], [4, 8])                                                                   # ecartees
          + [("gdup", YG + " PSA 10", 406, jr(15), None)] * 3                                                           # la meme vente trouvee 3 fois
          # une carte tres vendue : sa raw n'est connue que depuis 14 jours ; sa PSA 10 d'il y a 3 mois (moins chere) ne compte pas
          + V("br", "2023-24 Upper Deck Connor Bedard Young Guns #451", [300] * 8, [1, 2, 4, 6, 8, 10, 12, 14])
          + V("b10", "2023-24 Upper Deck Connor Bedard Young Guns #451 PSA 10", [1000] * 6, [1, 3, 5, 7, 9, 11]) + V("b10v", "2023-24 Upper Deck Connor Bedard Young Guns #451 PSA 10", [600] * 6, [60, 70, 80, 90, 100, 110])
          # pas assez de PSA 10 (4) ; pas assez de raw (3) ; une PSA 10 qui ne rapporte pas
          + V("mr", "2024-25 Upper Deck Matvei Michkov Young Guns #492", [40] * 6, [1, 2, 3, 4, 5, 6]) + V("m10", "2024-25 Upper Deck Matvei Michkov Young Guns #492 PSA 10", [300] * 4, [1, 2, 3, 4])
          + V("hr", "2024-25 Upper Deck Lane Hutson Young Guns #229", [110] * 3, [1, 2, 3]) + V("h10", "2024-25 Upper Deck Lane Hutson Young Guns #229 PSA 10", [750] * 6, [1, 2, 3, 4, 5, 6])
          + V("pr", "2024-25 Upper Deck Zayne Parekh Young Guns #233", [30] * 6, [1, 2, 3, 4, 5, 6]) + V("p10", "2024-25 Upper Deck Zayne Parekh Young Guns #233 PSA 10", [60] * 5, [1, 2, 3, 4, 5]) + V("p9", "2024-25 Upper Deck Zayne Parekh Young Guns #233 PSA 9", [25] * 3, [1, 2, 3])
          # deux numeros = deux cartes ; une vente trop vieille ; des prix trop etales (deux cartes melangees)
          + V("vieux", YG + " PSA 10", [9999], [200])
          + V("er", "2024-25 Upper Deck Will Smith Young Guns #701", [10, 12, 60, 70, 80, 11], [1, 2, 3, 4, 5, 6]) + V("e10", "2024-25 Upper Deck Will Smith Young Guns #701 PSA 10", [400] * 5, [1, 2, 3, 4, 5]))
R = a_grader.analyser(ventes)
par = {x["joueur"]: x for x in R["cartes"]}
assert set(par) == {"Cutter Gauthier", "Connor Bedard", "Zayne Parekh"}, set(par)
g = par["Cutter Gauthier"]
assert g["raw"] == 38 and g["n_raw"] == 6 and g["psa10"] == 406 and g["n10"] == 6 and g["psa9"] == 90 and g["n9"] == 3, g      # la vente triplee compte une fois ;
assert g["jours"] == 45, "la raw d'il y a 60 jours est hors de la periode commune (la PSA 10 n'est connue que depuis 45 jours)"
assert g["annee"] == 2024 and g["num"] == "212" and g["nom"] == "Young Guns" and g["q"] == "cutter gauthier young guns"
net10, net9 = 406 * (1 - 0.1325) - 0.40, 90 * (1 - 0.1325) - 0.40
assert g["reste10"] == round(net10 - 38 - 41, 2) and g["reste9"] == round(net9 - 38 - 41, 2) and g["reste9"] < 0 < g["reste10"]
assert g["seuil"] == round(-(net9 - 79) / (net10 - net9), 3) and 0 < g["seuil"] < 0.02, g["seuil"]                              # la part de 10 qu'il faut pour ne pas perdre
assert g["rapport"] == round(406 / 38, 2) and g["rendement"] == round(net10 / 79, 2)
b = par["Connor Bedard"]
assert b["psa10"] == 1000 and b["n10"] == 6 and b["jours"] == 14 and b["psa9"] is None and b["reste9"] is None and b["seuil"] is None, b   # LA MEME PERIODE
z = par["Zayne Parekh"]
assert z["reste10"] < 0 and z["reste9"] < 0 and z["seuil"] is None, "elle perd meme en 10 : pas de seuil"
assert [x["joueur"] for x in R["cartes"]] == sorted(par, key=lambda j: -par[j]["rendement"]), "classee par ce qui revient pour 1 $ mis si elle revient 10"
assert R["ecartees"] == {"peu de PSA 10": 1, "peu de raw": 1, "periode trop courte": 0, "prix trop etales": 1, "raw melangee a des gradees": 0}, R["ecartees"]
assert "chance" not in json.dumps(R) and "espere" not in json.dumps(R), "jamais une chance de 10 ni un profit espere"
# une vente sans numero ni annee : a la carte si elle n'a qu'un numero et qu'une saison ; sinon ecartee
R2 = a_grader.analyser(V("r", YG, [38] * 5, [1, 2, 3, 4, 5]) + V("s", "Upper Deck Cutter Gauthier Young Guns rookie", [38] * 3, [1, 2, 3]) + V("t", YG + " PSA 10", [406] * 5, [1, 2, 3, 4, 5]))
assert R2["cartes"][0]["n_raw"] == 8
R3 = a_grader.analyser(V("r", YG, [38] * 5, [1, 2, 3, 4, 5]) + V("u", "2023-24 Upper Deck Cutter Gauthier Young Guns #999", [5] * 5, [1, 2, 3, 4, 5]) + V("s", "Upper Deck Cutter Gauthier Young Guns rookie", [1] * 3, [1, 2, 3]) + V("t", YG + " PSA 10", [406] * 5, [1, 2, 3, 4, 5]))
assert R3["cartes"][0]["n_raw"] == 5 and R3["cartes"][0]["raw"] == 38, "deux saisons existent : la vente sans annee n'est a personne"
# ---- 2b. 26 nov, 16 h 36 (Mathieu : « le temps est important la-dedans » ; son « Oui ») : les 60 derniers jours quand la carte s'y vend
# assez (raw, PSA 10, et PSA 9 si elle a un prix PSA 9), sinon les 120 jours. Les memes cartes dans la liste : seule la mesure change.
# 26 nov, 18 h 50 (« besoin de plus de data [...] au moins entre 500 et 1 000 » ; son choix : 12 mois + 500 joueurs) : trois periodes,
# la plus recente d'abord : 60 jours, sinon 120, sinon 12 mois.
assert a_grader.JOURS_RECENT == 60 and a_grader.FENETRES == (60, 120) and a_grader.JOURS == 365
for x in R["cartes"]:
    assert x["fenetre"] == 60, "tout se vend dans les 60 derniers jours : mesure sur 60 jours (%r)" % x["joueur"]
assert R["jours_recent"] == 60 and R["n_recent"] == 3 and R["jours"] == 365 and R["fenetres"] == [60, 120, 365] and R["par_fenetre"] == {"60": 3}
MI = "2025-26 Upper Deck Michael Misa Young Guns #201"
def misa(raw_r, raw_v, p10_r, p10_v, p9_r=(), p9_v=()):
    recents, vieux = [2, 6, 10, 20, 30, 40, 50, 55], [70, 80, 90, 100, 105, 110, 112, 115]
    L = []
    for pre, titre, prix, jours in (("ar", MI, raw_r, recents), ("av", MI, raw_v, vieux), ("br", MI + " PSA 10", p10_r, recents), ("bv", MI + " PSA 10", p10_v, vieux),
                                    ("cr", MI + " PSA 9", p9_r, recents), ("cv", MI + " PSA 9", p9_v, vieux)):
        L += V(pre, titre, list(prix), jours[:len(prix)])
    return a_grader.analyser(L)["cartes"][0]
# la PSA 10 a baisse depuis 3 mois : on lit le prix d'aujourd'hui (les 60 derniers jours), pas la moyenne des 4 mois
m = misa([41] * 6, [41] * 6, [309] * 5, [520] * 6, [100] * 3, [150] * 4)
assert (m["fenetre"], m["raw"], m["psa10"], m["psa9"], m["n10"], m["n9"]) == (60, 41, 309, 100, 5, 3), m
assert m["n_raw"] == 5 and m["jours"] == 30, "toujours la meme periode : la raw d'il y a 40 jours precede la premiere PSA 10 recente (30 jours)"
assert m["rendement"] == round((309 * (1 - 0.1325) - 0.40) / (41 + 41), 2) == 3.26
# pas assez de PSA 10 dans les 60 derniers jours (4) : les 120 jours, comme avant
m = misa([41] * 6, [41] * 6, [309] * 4, [520] * 6, [100] * 3, [150] * 4)
assert (m["fenetre"], m["n10"], m["psa10"], m["n_raw"]) == (120, 10, 520, 12), m
# pas assez de raw dans les 60 derniers jours (4) : les 120 jours
m = misa([41] * 4, [50] * 6, [309] * 5, [520] * 6)
assert (m["fenetre"], m["n_raw"], m["n10"]) == (120, 10, 11), m
# assez de raw et de PSA 10 dans 60 jours, mais la PSA 9 y perdrait son prix (2 ventes) alors que 120 jours le donnent : 120 jours
m = misa([41] * 6, [41] * 6, [309] * 5, [520] * 6, [100] * 2, [150] * 4)
assert m["fenetre"] == 120 and m["psa9"] is not None and m["n9"] == 6 and m["seuil"] is not None, m
# ... et sans prix PSA 9 nulle part, rien a perdre : 60 jours
m = misa([41] * 6, [41] * 6, [309] * 5, [520] * 6, [100] * 2, [150] * 0)
assert m["fenetre"] == 60 and m["psa9"] is None and m["psa10"] == 309, m
# des prix trop etales dans les 60 derniers jours (deux cartes melangees ?) : on garde la mesure des 120 jours
m = misa([10, 12, 60, 70, 80, 11], [41] * 8, [309] * 5, [309] * 6)
assert m["fenetre"] == 120 and m["n_raw"] == 12 and m["raw"] == 41, m
# 12 mois : une carte RARE en PSA 10 (2 ventes dans 120 jours, 6 dans l'annee) entre dans la liste, mesuree sur ses 12 mois, sur
# la periode commune (la raw doit etre connue aussi loin) ; la fiche dit sa vraie periode
def rare(raw_j, p10_j, p10_prix=300):
    L = V("qr", MI, [41] * len(raw_j), raw_j) + V("qp", MI + " PSA 10", [p10_prix] * len(p10_j), p10_j)
    return a_grader.analyser(L)
Rr = rare([5, 40, 90, 150, 220, 300, 340], [10, 100, 160, 200, 260, 330])
m = Rr["cartes"][0]
assert (m["fenetre"], m["n10"], m["n_raw"], m["jours"]) == (365, 6, 6, 330) and Rr["par_fenetre"] == {"365": 1}, m
assert rare([5, 40, 90, 100, 110], [10, 100, 160, 200, 260, 330])["cartes"] == [], "la raw n'est connue que depuis 110 jours : la meme periode n'a pas 5 PSA 10"
assert rare([5, 40, 90, 150, 220, 300, 340], [10, 100, 160, 200, 380, 400])["cartes"] == [], "une vente de plus de 12 mois ne compte pas"
# le prix a triple dans l'annee (trop etale sur 12 mois) mais il se tient depuis 60 jours : la carte RESTE, mesuree sur 60 jours
L3 = V("tr", MI, [41] * 6 + [12] * 8, [2, 6, 10, 20, 30, 40, 100, 150, 200, 250, 300, 320, 340, 350]) \
    + V("tp", MI + " PSA 10", [900] * 5 + [150] * 8, [3, 7, 11, 21, 31, 100, 150, 200, 250, 300, 320, 340, 350])
m = a_grader.analyser(L3)["cartes"][0]
assert (m["fenetre"], m["raw"], m["psa10"]) == (60, 41, 900), m
# 26 nov, 19 h 13 (Mathieu, la fiche Dylan Larkin Young Guns Canvas, raw 152 $ / PSA 10 131 $ : « impossible, une raw ne se vend
# jamais plus chere qu'une PSA 10 »). Les vraies ventes : 3 « raw » sur 5 au titre automatique d'eBay, sans note : des gradees.
LK = "2015-16 Upper Deck - Ud Canvas Young Guns Dylan Larkin #C112 (RC)"
def larkin(raw_prix):                                       # raw et PSA 10 vendues les memes jours : la meme periode
    return a_grader.analyser(V("lr", LK, raw_prix, [3 + i % 5 for i in range(len(raw_prix))]) + V("lp", LK + " PSA 10", [122, 131, 178, 178, 131], [3, 4, 5, 6, 7]))
Rl = larkin([64, 152, 156, 51, 171])
assert Rl["cartes"] == [] and Rl["ecartees"]["raw melangee a des gradees"] == 1, "2 vraies raw seulement : la carte sort de la liste"
Rl = larkin([44, 152, 156, 41, 171, 38, 36, 40, 131])        # 131 $ = le prix de la PSA 10 : jetee aussi
m = Rl["cartes"][0]
assert (m["raw"], m["n_raw"], m["psa10"]) == (40, 5, 131) and Rl["raw_gradees"] == 4 and m["raw"] < m["psa10"], m
for R_ in (R, Rr, Rl):
    assert all(x["raw"] < x["psa10"] for x in R_["cartes"]), "jamais une raw au prix de la PSA 10 ou plus"
assert R["raw_gradees"] == 0
# une fenetre demandee de 60 jours ou moins : pas de deuxieme lecture
R45 = a_grader.analyser(ventes, jours=45)
assert R45["jours_recent"] is None and R45["n_recent"] == 0 and all(x["fenetre"] == 45 for x in R45["cartes"]) and R45["cartes"]
print("LISTE OK")

# ---- 3. sur le serveur : la collecte PSA + nos archives pour les memes joueurs ; une vente vue des deux cotes compte une fois
import banque_psa, base_ventes, indice_joueurs
banque_psa._run_maj()
c = banque_psa._cx()
c.execute("INSERT INTO plan (q, phase, joueur, ordre) VALUES ('cutter gauthier psa 10', 1, 'Cutter Gauthier', 0)")
for i, (p, j) in enumerate(zip([400, 410, 406, 395, 420], [2, 3, 4, 5, 6])):
    c.execute("INSERT INTO ventes (cle, q, joueur, titre, prix, le) VALUES (?,?,?,?,?,?)", (f"1234567890{i}", "cutter gauthier psa 10", "Cutter Gauthier", YG + " PSA 10", p, jr(j)))
c.commit(); c.close()
base_ventes.noter("cutter gauthier young guns", [{"titre": YG + f" RC {i}", "prix": 38.0, "le": jr(2 + i), "url": f"https://www.ebay.com/itm/99999999{i:03d}"} for i in range(6)]
                  + [{"titre": YG + " PSA 10", "prix": 400.0, "le": jr(2), "url": "https://www.ebay.com/itm/12345678900"}], sport="hockey")      # la meme vente que la collecte
base_ventes.noter("cutter gauthierx autre", [{"titre": YG + " RC", "prix": 1.0, "le": jr(2), "url": "https://www.ebay.com/itm/777777777001"}], sport="hockey")   # un autre « joueur »
assert a_grader._cle_vente("https://www.ebay.com/itm/12345678900?x=1") == "12345678900" == a_grader._cle_vente("12345678900")
assert a_grader.page()["cartes"] == [] and a_grader.refaire_si_besoin() is not None            # la collecte a des ventes : la liste part
for _ in range(400):
    if not a_grader.ETAT["en_cours"]: break
    time.sleep(0.05)
P = a_grader.page()
assert P["ok"] and len(P["cartes"]) == 1 and P["cartes"][0]["joueur"] == "Cutter Gauthier" and P["cartes"][0]["n10"] == 5 and P["cartes"][0]["n_raw"] == 5 and P["lues"] == 11, (P["cartes"], P["lues"])
assert a_grader.refaire_si_besoin() is None, "refaite une fois par semaine, pas a chaque tour"
# 26 nov, 15 h 06 (Mathieu : « dans trend on devrait voir la liste du top 100 a grader qui se refresh chaque semaine ») : chaque
# semaine, et une fois de plus quand la collecte PSA vient de finir (ses ventes sont plus recentes que la liste)
assert a_grader.REFAIRE_J == 7 and a_grader.N_TOP == 100
os.utime(a_grader._chemin(), (time.time() - 8 * 86400,) * 2)
assert a_grader.refaire_si_besoin() is not None, "une liste de plus de 7 jours est refaite"
for _ in range(400):
    if not a_grader.ETAT["en_cours"]: break
    time.sleep(0.05)
banque_psa._run_maj(statut="terminee", battement=time.time() + 60)
assert a_grader.refaire_si_besoin() is not None, "la collecte vient de finir : la liste est refaite"
for _ in range(400):
    if not a_grader.ETAT["en_cours"]: break
    time.sleep(0.05)
banque_psa._run_maj(statut="terminee", battement=time.time() - 3600)
assert a_grader.refaire_si_besoin() is None

# 26 nov, 15 h 29 (Mathieu : « je vois beaucoup de Young Guns ») : la liste datait d'avant les recherches raw de la collecte. Pendant
# une collecte, elle suit : refaite a chaque tour de la boucle (une fois l'heure), jamais deux fois dans la meme heure
def attendre_calcul():
    for _ in range(600):
        if not a_grader.ETAT["en_cours"]:
            return
        time.sleep(0.05)
    raise AssertionError("le calcul ne finit pas")


attendre_calcul()
banque_psa._run_maj(statut="en_cours", battement=time.time())
assert a_grader.REFAIRE_COLLECTE_MIN == 110
os.utime(a_grader._chemin(), (time.time() - 55 * 60,) * 2)
assert a_grader.refaire_si_besoin() is None, "une liste de moins de 2 heures n'est pas refaite, meme pendant la collecte"
os.utime(a_grader._chemin(), (time.time() - 115 * 60,) * 2)
assert a_grader.refaire_si_besoin() is not None, "pendant la collecte, une liste de pres de 2 heures est refaite"
attendre_calcul()
banque_psa._run_maj(statut="erreur", battement=time.time() - 3600)
os.utime(a_grader._chemin(), (time.time() - 115 * 60,) * 2)
assert a_grader.refaire_si_besoin() is None, "collecte arretee : retour au rythme de la semaine"
# 26 nov, 16 h 36 : une regle de calcul change (les 60 derniers jours) : la liste faite avec l'ancienne regle est refaite seule, une fois
assert a_grader.VERSION == 5 and a_grader.lire()["version"] == 5          # 5 : la pastille « A grader » (27 nov)
with open(a_grader._chemin(), encoding="utf-8") as f_:
    anc = json.load(f_)
anc.pop("version")
with open(a_grader._chemin(), "w", encoding="utf-8") as f_:
    json.dump(anc, f_)
os.utime(a_grader._chemin(), (time.time() - 20 * 60,) * 2)
assert a_grader.refaire_si_besoin() is not None, "une liste sans version (faite avant la regle) est refaite"
attendre_calcul()
assert a_grader.lire()["version"] == a_grader.VERSION and a_grader.refaire_si_besoin() is None, "une seule fois"
banque_psa._run_maj(statut="terminee", battement=time.time() - 3600)

# ---- 3b. la couverture est MESUREE : parmi les ventes dont le titre dit PSA 10 (ou PSA 9), combien sont rangees, et pourquoi pas
pq = []
assert a_grader.classer("Connor Bedard PSA 10 rookie card gem", "Connor Bedard", pq) is None and pq == ["sorte pas reconnue"]
pq = []
assert a_grader.classer("2023-24 UD Young Guns Connor Bedard #451 PSA 10?", "Connor Bedard", pq) is None and pq == ["pas encore gradee"]
pq = []
assert a_grader.classer("2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10 GEM MINT", "Connor Bedard", pq) and pq == []
assert a_grader.classer("2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10 GEM MINT", "Connor Bedard"), "sans la liste : comme avant"
rt = a_grader._RE_NOTE_TITRE
assert rt.search("Bedard YG PSA 10 GEM").group(1) == "10" and rt.search("Bedard YG PSA-9").group(1) == "9"
assert not rt.search("Bedard YG PSA 9.5") and not rt.search("Bedard YG PSA 100") and not rt.search("Bedard YG BGS 10")
assert a_grader._duos("2024-25 Upper Deck Fleer Retro Macklin Celebrini Metal Universe #12 PSA 10 GEM MINT", "Macklin Celebrini") == \
    {"fleer retro", "retro metal", "metal universe"}
jr_ = lambda k: (datetime.now(timezone.utc) - timedelta(days=k)).strftime("%Y-%m-%d")
lot = [("c%d" % k, "2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 10 GEM MINT", 900.0, jr_(3 + k), "Connor Bedard") for k in range(6)]
lot += [("m%d" % k, "Connor Bedard PSA 10 Fancy Hologram gem mint", 50.0, jr_(4 + k), "Connor Bedard") for k in range(4)]
lot += [("e1", "2023-24 UD Young Guns Connor Bedard #451 PSA 10?", 300.0, jr_(5), "Connor Bedard"),
        ("n1", "2023-24 Upper Deck Connor Bedard Young Guns #451 RC PSA 9 MINT", 400.0, jr_(6), "Connor Bedard"),
        ("r1", "2023-24 Upper Deck Connor Bedard Young Guns #451 RC", 250.0, jr_(7), "Connor Bedard")]
cv = a_grader.analyser(lot)["couverture"]
assert cv["10"]["lues"] == 11 and cv["10"]["rangees"] == 6, cv["10"]
assert cv["10"]["raisons"] == {"sorte pas reconnue": 4, "pas encore gradee": 1}, cv["10"]
assert cv["9"] == {"lues": 1, "rangees": 1, "autre_joueur": 0, "raisons": {}, "par_numero": 0}, cv["9"]
assert ["fancy hologram", 4] in cv["sortes_inconnues"], cv["sortes_inconnues"]
assert cv["exemples"]["fancy hologram"] == ["Connor Bedard PSA 10 Fancy Hologram gem mint"] * 2, "deux vrais titres par paire de mots, pour ecrire la regle"
assert set(cv["exemples"]) == {d for d, _ in cv["sortes_inconnues"]} and cv["exemples_lot"] == []
# 26 nov, 16 h 18 (le serveur : « ozzie cardinals », « emmitt cowboys » dans les mots sans sorte) : la recherche « will smith psa 10 »
# ramene aussi d'autres Smith. Une vente qui ne nomme pas le joueur cherche est comptee a part, hors de la mesure
nm = a_grader._nomme
assert nm("2024-25 Upper Deck Will Smith Young Guns #701 PSA 10", "Will Smith") and not nm("1987 Topps Ozzie Smith Cardinals HOF PSA 10", "Will Smith")
assert nm("2005-06 UD Alexander Ovechkin Young Guns PSA 10", "Alex Ovechkin") and nm("2020-21 UD Alexis Lafreniere YG PSA 10", "Alexis Lafrenière")
assert not nm("2023-24 Upper Deck Connor Bedard Young Guns #451 PSA 10", "Connor McDavid")
smith = [("s%d" % k, "2024-25 Upper Deck Will Smith Young Guns #701 PSA 10 GEM MINT", 300.0, jr_(3 + k), "Will Smith") for k in range(3)]
smith += [("o%d" % k, "1987 Topps Ozzie Smith Cardinals HOF #749 PSA 10", 80.0, jr_(3 + k), "Will Smith") for k in range(4)]
smith += [("w1", "Will Smith PSA 10 rookie gem mint", 90.0, jr_(5), "Will Smith")]
cs = a_grader.analyser(smith)["couverture"]
assert cs["10"]["autre_joueur"] == 4 and cs["10"]["lues"] == 4 and cs["10"]["rangees"] == 3 and cs["10"]["raisons"] == {"sorte pas reconnue": 1}, cs["10"]
assert not any("ozzie" in d or "cardinals" in d for d, _ in cs["sortes_inconnues"]), cs["sortes_inconnues"]
# ---- 3c. 26 nov, 17 h 02 (le fichier de la collecte PSA) : 877 ventes PSA 10 ecrites comme l'etiquette PSA, sans le nom de la sorte
# (« 2024 UD #451 MACKLIN CELEBRINI PSA 10 ») : ce sont surtout des Young Guns. Rangees par leur NUMERO dans la Young Guns du meme
# joueur et de la meme saison, si elle existe deja par ses ventes normales et si le prix leur ressemble. Jamais une fausse.
et = a_grader._etiquette
assert et("2024 UD #451 MACKLIN CELEBRINI PSA 10", "Macklin Celebrini") == ("macklin celebrini", 2024, "451", "10", frozenset())
assert et("2025 UD UD CANVAS #C-231 IVAN DEMIDOV ROOKIE RC PSA 9", "Ivan Demidov") == ("ivan demidov", 2025, "c231", "9", frozenset({"canvas"}))
assert et("2023-24 Upper Deck Connor Bedard Rookie Card #451 PSA 10 Gem Mint Blackhawks", "Connor Bedard")[:4] == ("connor bedard", 2023, "451", "10")
assert et("2005 UPPER DECK ROOKIE CLASS #2 ALEXANDER OVECHKIN RC PSA 10", "Alex Ovechkin") is None, "un mot distinctif (une autre sorte) : pas une etiquette"
assert et("2024 UD FLEER ULTRA MEDALLIONS #M-12 MACKLIN CELEBRINI ROOKIE RC PSA 10", "Macklin Celebrini") is None
assert et("2024 UD #451 MACKLIN CELEBRINI /100 PSA 10", "Macklin Celebrini") is None, "une carte numerotee : jamais"
assert et("2024 UD #451 MACKLIN CELEBRINI", "Macklin Celebrini") is None and et("2024 UD #451 MACKLIN CELEBRINI PSA 8", "Macklin Celebrini") is None
assert et("2024 UD MACKLIN CELEBRINI PSA 10", "Macklin Celebrini") is None and et("UD #451 MACKLIN CELEBRINI PSA 10", "Macklin Celebrini") is None, "il faut le numero ET l'annee"
MC = "2024-25 Upper Deck Macklin Celebrini Young Guns #451"
def celebrini(n10_normales, etiquettes, raw=6, autres=()):
    L = V("zr", MC, [520] * raw, [1, 2, 3, 4, 5, 8][:raw]) + V("zn", MC + " PSA 10", [3000] * n10_normales, [3, 5, 7, 9, 11][:n10_normales])
    L += [("ze%d" % k, t, p, jr(4 + k), "Macklin Celebrini") for k, (t, p) in enumerate(etiquettes)] + list(autres)
    return a_grader.analyser(L)
lab = "2024 UD #451 MACKLIN CELEBRINI PSA 10"
R0 = celebrini(3, [])
assert R0["cartes"] == [] and R0["ecartees"]["peu de PSA 10"] == 1, "3 ventes PSA 10 normales : pas assez"
R1 = celebrini(3, [(lab, 3100), (lab + " GEM MT", 2900), ("2024 UPPER DECK #451 MACKLIN CELEBRINI ROOKIE RC PSA 10", 3050)])
c1 = R1["cartes"][0]
assert (c1["nom"], c1["num"], c1["n10"], c1["psa10"], c1["n_raw"]) == ("Young Guns", "451", 6, 3000, 5), c1
cv1 = R1["couverture"]
assert cv1["10"]["par_numero"] == 3 and cv1["10"]["rangees"] == 6 and cv1["10"]["lues"] == 6 and not cv1["10"]["raisons"].get("sorte pas reconnue"), cv1["10"]
assert cv1["etiquettes"] == {"vues": 3, "rangees": 3, "pas de Young Guns a ce numero": 0, "carte trop peu vendue": 0, "prix trop different": 0}, cv1["etiquettes"]
# un prix qui ne ressemble pas (une parallele vendue sans son nom ?) : dehors ; un autre numero (une autre serie, une carte de base) : dehors
R2 = celebrini(3, [(lab, 3100), (lab, 9000), (lab, 900), ("2024 UD #743 MACKLIN CELEBRINI ROOKIE RC PSA 10", 3000), ("2025 UPPER DECK #136 MACKLIN CELEBRINI PSA 10", 3000)])
assert R2["cartes"] == [] and R2["couverture"]["etiquettes"] == {"vues": 5, "rangees": 1, "pas de Young Guns a ce numero": 2, "carte trop peu vendue": 0, "prix trop different": 2}
# la carte n'a pas encore 3 ventes PSA 10 normales : on ne construit pas un prix sur des etiquettes seules
R3 = celebrini(2, [(lab, 3000)] * 4)
assert R3["cartes"] == [] and R3["couverture"]["etiquettes"]["carte trop peu vendue"] == 4 and R3["couverture"]["10"]["par_numero"] == 0
# une etiquette « UD CANVAS #C-211 » ne va QUE dans la Young Guns Canvas de ce numero, jamais dans la Young Guns
CA = "2024-25 Upper Deck Macklin Celebrini Young Guns Canvas #C211"
R4 = celebrini(3, [("2024 UD UD CANVAS #C-211 MACKLIN CELEBRINI ROOKIE RC PSA 10", 900)] * 2,
               autres=V("yr", CA, [150] * 6, [1, 2, 3, 4, 5, 8]) + V("yn", CA + " PSA 10", [900] * 3, [3, 5, 7]))
par4 = {x["nom"]: x for x in R4["cartes"]}
assert set(par4) == {"Young Guns Canvas"} and par4["Young Guns Canvas"]["n10"] == 5 and R4["couverture"]["10"]["par_numero"] == 2, par4
# jamais pour une raw : « 2024 UD #451 MACKLIN CELEBRINI » sans note reste dehors
R5 = celebrini(5, [], raw=4, autres=[("zz%d" % k, "2024 UD #451 MACKLIN CELEBRINI", 500, jr(3 + k), "Macklin Celebrini") for k in range(3)])
assert R5["cartes"] == [] and R5["ecartees"]["peu de raw"] == 1
# sans joueur cherche (nos archives : une recherche par carte), rien n'est mis a part
assert a_grader.analyser([(c, t, p, d, None) for c, t, p, d, _ in smith])["couverture"]["10"]["autre_joueur"] == 0
T = a_grader.top_tendances()
assert len(T["cartes"]) == 1 and T["n"] == 1 and T["semaine"] == 7 and T["frais_psa"] == 41.0 and T["le"]
# 26 nov, 14 h 58 (journal : la collecte PSA morte sur « database is locked » 22 s apres le depart du calcul) : pendant que la liste
# se calcule, la base de la collecte n'est JAMAIS tenue ouverte : une ecriture passe tout de suite
import sqlite3
g_ = a_grader._ventes_serveur()
next(g_)
c2 = sqlite3.connect(banque_psa._chemin(), timeout=0.2)
c2.execute("UPDATE collecte SET texte='ecrit pendant le calcul' WHERE id=1"); c2.commit(); c2.close()
cb = base_ventes._cx(); chemin_archives = cb.execute("PRAGMA database_list").fetchone()[2]; cb.close()
c3 = sqlite3.connect(chemin_archives, timeout=0.2)
list(g_)
c3.execute("CREATE TABLE IF NOT EXISTS essai_ecriture (x)"); c3.execute("DROP TABLE essai_ecriture"); c3.commit(); c3.close()
assert "LIMIT 5000" in open(os.path.join(RACINE, "a_grader.py"), encoding="utf-8").read()
print("SERVEUR OK")

# ---- 4. admin seulement (des prix) ; l'ecran ; l'export
import lockerroom
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin = lambda reel=False: False
assert api.admin_a_grader()["ok"] is False and api.admin_a_grader_calculer()["ok"] is False
api._est_admin = lambda reel=False: True
assert len(api.admin_a_grader()["cartes"]) == 1
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()
srv = open(os.path.join(RACINE, "server.py"), encoding="utf-8").read()
assert "async function feuilleAGrader(){" in src and "API.admin_a_grader_calculer()" in src and 'id="bp-liste"' in src and "feuilleAGrader" in app
# la liste ne s'ouvre que d'un seul endroit : le bouton de la fenetre admin « Donnees PSA » (elle montre des prix)
assert src.count("setTimeout(feuilleAGrader, 220)") == 1 and "const bl = $('#bp-liste'); if (bl) bl.onclick" in src
hors = src.replace("async function feuilleAGrader(){", "").replace("setTimeout(feuilleAGrader, 220)", "").replace("setTimeout(feuilleAGrader, 1500)", "").replace("!$('#fond-feuille').hidden) feuilleAGrader();", "")
assert "feuilleAGrader" not in hors, "aucun autre appel"
assert '@app.route("/admin/psa_export.tsv.gz")' in srv and "if not api._est_admin(reel=True):\n        abort(403)\n    if time.time() - _EXPORT_V.get(\"psa\", 0) < 600:" in srv
assert "a_grader.refaire_si_besoin()" in srv
# Trending : la liste n'est envoyee QU'A l'admin (elle porte des prix) : ni au Pro, ni au Gratuit, ni a l'admin en vue client
import forfaits, tendance_sortes
api._tendances_iq0 = lambda: {"ok": True, "cats": {"bas": [], "haut": []}, "compte": {}}
tendance_sortes.page = lambda: None
vrai_pro = forfaits.est_pro
try:
    api._est_admin = lambda reel=False: True
    ra = api.tendances_iq()
    assert ra["a_grader"]["cartes"][0]["joueur"] == "Cutter Gauthier" and ra["a_grader"]["cartes"][0]["raw"] == 38.0
    api._est_admin = lambda reel=False: False                # un Pro (ou l'admin qui regarde l'app comme un client)
    forfaits.est_pro = lambda: True
    assert "a_grader" not in api.tendances_iq() and "psa10" not in json.dumps(api.tendances_iq())
    forfaits.est_pro = lambda: False                         # un Gratuit
    assert "a_grader" not in api.tendances_iq() and "psa10" not in json.dumps(api.tendances_iq())
finally:
    forfaits.est_pro = vrai_pro
assert "if isinstance(r, dict) and r.get(\"ok\") and self._est_admin():\n                import a_grader" in open(os.path.join(RACINE, "lockerroom.py"), encoding="utf-8").read()
# l'ecran : un 3e onglet seulement quand le serveur envoie la liste ; une ligne sans prix ; les prix au toucher
assert "const AG = SO && r.a_grader && (r.a_grader.cartes || []).length ? r.a_grader : null;" in src and "...(AG ? [['grader', tt('À grader', 'To grade')]] : [])" in src
lg = src[src.index("        const ligneG = (x, i) =>"):src.index("        const ouvrirG = (x) =>")]
assert "argent(" not in lg and "x.raw" not in lg and "x.psa10" not in lg, "la ligne de Trending ne montre aucun prix"
assert "function agCarte(x, rg){" in src and "const ligne = (x, i) => agCarte(x, i + 1);" in src and "Admin seulement pour l’instant" in src
print("ADMIN OK")
