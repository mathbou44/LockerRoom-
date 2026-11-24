"""24 nov 2026 (audit des calculs avant le lancement).
1. La taxe d'un achat au Canada etait celle du Quebec (14,975 %) pour tout le monde : le « Total » d'une carte etait gonfle de
   pres de 10 % pour un acheteur de l'Alberta. Elle suit la province choisie ; sans province : le Quebec, comme avant.
2. eBay : 0,30 $ par commande de 10 $ et moins, 0,40 $ au-dessus (le calcul prenait toujours 0,40 $)."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import calcul
import deals
import lockerroom
from lockerroom import Api

# 1. les taux de 2026 (TPS ou TVH + taxe provinciale)
T = deals.TAXES_PROVINCE
assert T == {"AB": 5.0, "BC": 12.0, "MB": 12.0, "NB": 15.0, "NL": 15.0, "NS": 14.0, "NT": 5.0, "NU": 5.0, "ON": 13.0, "PE": 15.0,
             "QC": 14.975, "SK": 11.0, "YT": 5.0}
assert deals.taxe_province("ab") == 0.05 and deals.taxe_province(" ON ") == 0.13 and deals.taxe_province("QC") == 0.14975
assert deals.taxe_province("") == deals.TAXE_ACHAT == deals.taxe_province("ZZ") == deals.taxe_province(None)   # inconnue : comme avant
ca = {"lieu": "CA", "total": 100}
assert deals.taxe_de(ca) == deals.TAXE_ACHAT                                   # le chasseur (admin, sans province) : inchange
assert deals.taxe_de({**ca, "_prov": "AB"}) == 0.05 and deals.taxe_de({**ca, "_prov": "NS"}) == 0.14
assert deals.taxe_de({"lieu": "US", "_prov": "AB"}) == deals.IMPORT_DEFAUT      # une carte des Etats-Unis : les frais d'importation, inchanges
assert deals.taxe_de({"lieu": "US", "_pays": "US", "_prov": "AB"}) == deals.TAXE_US   # un acheteur americain : sa taxe a lui
assert deals.taxe_de({"lieu": "US", "import_lu": True, "import_pct": 0.0, "_prov": "AB"}) == 0.05   # relue, sans frais d'importation
# le « Total » d'une annonce : prix + port, plus la taxe de SA province
x = Api._frais_reels({"total": 100.0, "lieu": "CA"}, "CA", "AB")
assert x["total_reel"] == 105.0 and x["etranger"] is False
assert Api._frais_reels({"total": 100.0, "lieu": "CA"}, "CA", "")["total_reel"] == 114.98
assert Api._frais_reels({"total": 100.0, "lieu": "CA"}, "CA")["total_reel"] == 114.98           # sans province : le Quebec
# le reglage : garde, valide a la lecture
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
assert api._province() == ""
assert api.reglages_sauver({"province": "on"})["province"] == "on" and api._province() == "ON"
api.reglages_sauver({"province": "Narnia"})
assert api._province() == ""                                                     # une province inconnue ne casse rien : le Quebec

# 2. le frais par commande d'eBay
assert calcul.profit_vente(8, 2)["frais"] == round(8 * 0.1325 + 0.30, 2) == 1.36          # 10 $ et moins : 0,30 $
assert calcul.profit_vente(10, 0)["frais"] == round(10 * 0.1325 + 0.30, 2)                # 10 $ pile : 0,30 $
assert calcul.profit_vente(12, 2)["frais"] == round(12 * 0.1325 + 0.40, 2) == 1.99        # au-dessus : 0,40 $
assert calcul.profit_vente(8, 2, port_charge=3)["frais"] == round(11 * 0.1325 + 0.40, 2)  # la commande compte le port charge
assert calcul.profit_vente(8, 2, frais_fixe=0.0)["frais"] == round(8 * 0.1325, 2)         # un frais fixe a 0 reste a 0
assert calcul.profit_vente(0, 2)["frais"] == 0.0
print("OK test_taxe_province")
