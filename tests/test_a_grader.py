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
assert R["ecartees"] == {"peu de PSA 10": 1, "peu de raw": 1, "periode trop courte": 0, "prix trop etales": 1}, R["ecartees"]
assert "chance" not in json.dumps(R) and "espere" not in json.dumps(R), "jamais une chance de 10 ni un profit espere"
# une vente sans numero ni annee : a la carte si elle n'a qu'un numero et qu'une saison ; sinon ecartee
R2 = a_grader.analyser(V("r", YG, [38] * 5, [1, 2, 3, 4, 5]) + V("s", "Upper Deck Cutter Gauthier Young Guns rookie", [38] * 3, [1, 2, 3]) + V("t", YG + " PSA 10", [406] * 5, [1, 2, 3, 4, 5]))
assert R2["cartes"][0]["n_raw"] == 8
R3 = a_grader.analyser(V("r", YG, [38] * 5, [1, 2, 3, 4, 5]) + V("u", "2023-24 Upper Deck Cutter Gauthier Young Guns #999", [5] * 5, [1, 2, 3, 4, 5]) + V("s", "Upper Deck Cutter Gauthier Young Guns rookie", [1] * 3, [1, 2, 3]) + V("t", YG + " PSA 10", [406] * 5, [1, 2, 3, 4, 5]))
assert R3["cartes"][0]["n_raw"] == 5 and R3["cartes"][0]["raw"] == 38, "deux saisons existent : la vente sans annee n'est a personne"
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
assert a_grader.refaire_si_besoin() is None, "refaite une fois par 20 heures, pas a chaque tour"
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
print("ADMIN OK")
