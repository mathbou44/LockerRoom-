"""27 nov 2026 (v6) : la regle « A grader » avec les vrais frais, les PSA 8 et la confiance par carte (modeles/a_grader_confiance.json)."""
import os, sys, json, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import a_grader as ag
import deals

# ---- 1. les frais : le palier PSA suit la valeur de la PSA 10 ; la taxe et l'envoi s'ajoutent
T = deals.TAXE_ACHAT
assert ag.frais_psa_de(300) == 56.99 * (1 + T) + 8, "Value (56,99 $ CA) jusqu'a 500 $ US"
assert ag.frais_psa_de(800) == 59.99 * 1.425 * (1 + T) + 8, "au-dela de 500 $ US : Standard"
assert ag.frais_psa_de(2000) == 79.99 * 1.425 * (1 + T) + 8 and ag.frais_psa_de(2500) == 199 * 1.425 * (1 + T) + 8 and ag.frais_psa_de(5000) == 349 * 1.425 * (1 + T) + 8
X = {"raw": 40.0, "psa10": 400.0, "psa9": 120.0, "psa8": 38.0, "c10": 30, "c9": 20, "c8": 10, "c7": 0, "n10": 12, "et_raw": 1.3, "et10": 1.2,
     "p10_90": 400.0, "p10_365": 380.0, "age_j": 300, "fenetre": 60, "annee": 2024, "q": "macklin celebrini young guns", "elan_j": 0.02, "n_j": 3}
a, b = ag.regle(X), ag.regle(X, proprio=True)
assert a["cout"] == (40 + 6) * (1 + T) + ag.frais_psa_de(400) and b["cout"] == deals.net_revente(40) + ag.frais_psa_de(400) and b["cout"] < a["cout"]
assert a["vn"] == 20 / 30 * 120 + 10 / 30 * 38, "pas 10 : une 9 ou une 8 dans la proportion vendue de la carte"
assert ag.regle(dict(X, age_j=100))["v10"] == 400 * 0.8, "une carte de moins de 6 mois : sa PSA 10 x 0,80"
assert ag.regle(dict(X, psa8=None))["vn"] == 20 / 30 * 120 + 10 / 30 * 40 * 0.85, "PSA 8 pas mesuree : 85 % de la raw"
print("FRAIS OK")

# ---- 2. le modele : du texte (jamais pickle), les memes variables, deux versions (acheter la raw / deja a soi)
m = json.load(open(os.path.join(RACINE, "modeles", "a_grader_confiance.json"), encoding="utf-8"))
assert tuple(m["variables"]) == ag.VARIABLES and set(m["modeles"]) == {"achat", "proprio"} and m["promesse"] == ag.PROMESSE == 0.5
assert all(len(v["arbres"]) == 3 and len(v["coef"]) == len(ag.VARIABLES) for v in m["modeles"].values())
assert len(ag.variables(X)) == len(ag.VARIABLES)
c_bon, c_proprio = ag.confiance(X), ag.confiance(X, proprio=True)
perd = dict(X, raw=150.0, psa10=180.0, psa9=90.0, psa8=140.0)                  # meme un 10 ne paie pas
c_perd = ag.confiance(perd)
assert 0 <= c_perd < 0.3 < c_bon <= 1 and 0 <= c_proprio <= 1, (c_bon, c_proprio, c_perd)
B = {"reste10": 100, "seuil": 0.1, "c10": 30, "c9": 20, "c8": 10, "c7": 0}
assert ag.vaut_grader(dict(B, conf=ag.CONFIANCE_MIN)) and not ag.vaut_grader(dict(B, conf=ag.CONFIANCE_MIN - 0.001))
print("CONFIANCE OK", round(c_bon, 3), round(c_proprio, 3), round(c_perd, 3))

# ---- 3. selon le forfait (27 nov 2026) : le gratuit recoit la pastille seule, jamais un chiffre ; le Pro, jamais un prix
e = {"r": 2.5, "s": 0.2, "c": 0.91, "jours": 60, "nom": "Young Guns", "joueur": "Macklin Celebrini", "an": 2024, "raw": 40, "p10": 400, "p9": 120, "g10": 150}
assert ag.pour_client(e, verrou=True) == {"verrou": True, "nom": "Young Guns", "joueur": "Macklin Celebrini", "an": 2024}
assert set(ag.pour_client(e)) == {"r", "s", "c", "jours", "nom", "joueur", "an"} and ag.pour_client(e, prix=True)["g10"] == 150
assert ag.pourquoi_non({"ok": False, "g10": 20, "s": 0.1, "c": 0.99}) == "gain" and ag.pourquoi_non({"ok": False, "g10": 90, "s": 0.1, "c": 0.5}) == "confiance"
assert ag.pourquoi_non({"ok": False, "g10": 90, "s": 0.3, "c": 0.95}) == "chance" and ag.pourquoi_non({"ok": True}) is None
print("FORFAITS OK")
