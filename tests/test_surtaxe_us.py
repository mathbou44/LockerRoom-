"""24 nov 2026 (audit des calculs ; Mathieu : « ce sont les tarifs, on doit en tenir compte. Renseigne-toi ») : une carte des
Etats-Unis achetee par un Canadien paie la surtaxe du Canada (50 % du PRIX de la carte depuis le 8 sept. 2026, numero
tarifaire 4911.91.00 ; ASFC, Avis des douanes 26-23 : sans minimum, la TPS sur la valeur + la surtaxe). Avant : +49,7 % de
(prix + port), juste pour UNE commande. Aucun reseau."""
import os, sys, tempfile
from datetime import datetime, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
for k in ("LR_SURTAXE_US", "LR_TPS_IMPORT", "LR_IMPORT_DEFAUT", "LR_TAXE_ACHAT"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, lockerroom, veille_ebay
from lockerroom import Api
assert deals.SURTAXE_US == 0.50 and deals.TPS_IMPORT == 0.05
pres = lambda a, b, e=0.006: abs(a - b) <= e

# 1. SA commande du 8 novembre, au cent : 106,17 + 18,58 de port ; 53,09 de frais d'importation ; 8,89 de TPS ; 186,73 en tout
P, S = 106.17, 18.58
cmd = {"lieu": "US", "total": P + S, "port": S}
assert pres(0.50 * P, 53.09) and pres(0.05 * (P + S + 0.50 * P), 8.89)
assert pres((P + S) * (1 + deals.taxe_de(cmd)), 186.73, 0.02)
assert pres(lockerroom._paye(P + S, cmd), 186.73, 0.02)
assert pres(Api._frais_reels(dict(cmd), "CA", "")["total_reel"], 186.73, 0.02)
# la meme annonce, relue : eBay donne ses frais d'importation -> le meme total
lue = {"lieu": "US", "import_lu": True, "import_cad": 53.09, "prix_cad": P, "port_cad": S}
assert deals._taux_import(lue) == (0.5, None) and pres((P + S) * (1 + deals.taxe_de(lue)), 186.73, 0.02)
# 2. la surtaxe ne touche PAS le port : avant, +49,7 % pour tout le monde
chere = {"lieu": "US", "total": 500.0, "port": 0.0}                              # carte chere, port gratuit : +57,5 % (avant 49,7)
assert pres(deals.taxe_de(chere), 0.575, 0.0002) and pres(lockerroom._paye(500, chere), 787.50)
petite = {"lieu": "US", "total": 30.0, "port": 20.0}                             # 10 $ + 20 $ de port : 6,75 $ (avant 14,91 $)
assert pres(30 * deals.taxe_de(petite), 6.75, 0.01)
assert pres(deals.taxe_de({"lieu": "US", "prix_cad": 100.0, "port_cad": None}), 1.05 * (115 + 50) / 115 - 1, 0.0002)   # port inconnu : 15 $
# 3. la province : la TVH la ou il y en a, la TPS ailleurs
assert deals.taxe_import("ON") == 0.13 and deals.taxe_import("NS") == 0.14 and deals.taxe_import("NB") == 0.15
assert deals.taxe_import("QC") == deals.taxe_import("AB") == deals.taxe_import("BC") == deals.taxe_import("") == 0.05
assert pres(deals.taxe_de({**chere, "_prov": "ON"}), 1.13 * 1.5 - 1, 0.0002)     # +69,5 % en Ontario
assert pres(Api._frais_reels(dict(chere), "CA", "ON")["total_reel"], 847.50)
# 4. le Canada et l'acheteur americain : inchanges
assert deals.taxe_de({"lieu": "CA", "total": 500.0}) == deals.TAXE_ACHAT
assert deals.taxe_de({"lieu": "US", "total": 500.0}, "US") == deals.TAXE_US
assert deals.taxe_de({"lieu": "US", "total": 500.0, "taxe": 0.31}) == 0.31       # un chiffre deja calcule est garde
assert deals.taxe_de({"lieu": "JP", "total": 500.0}) == deals.IMPORT_DEFAUT      # ailleurs, pas relue : le chiffre prudent
assert deals.taxe_de({"lieu": "US", "import_lu": True, "import_cad": 0, "prix_cad": 50, "_prov": "ON"}) == 0.13   # le vendeur expedie lui-meme
# 5. un encan se juge a sa MISE MAX : la facture a la mise max tient pile dans le budget (avant : au prix du moment)
for val, port in ((300.0, 20.0), (80.0, 25.0), (1500.0, 0.0), (60.0, 30.0)):
    enc = {"lieu": "US", "encan": True, "total": 5.0 + port, "port": port, "valeur": val}
    f = deals.taxe_de(enc)
    assert f == deals.taxe_de({k: v for k, v in enc.items() if k != "valeur"}, valeur=val)
    tmax = deals.prix_max(val, taxe=f)
    assert pres(lockerroom._paye(tmax, enc), deals._budget(val), 0.02), (val, port, tmax)
    if tmax > enc["total"] and port:                                             # au prix du moment, le port pese plus
        assert f > deals.taxe_de(enc, total=enc["total"])
# un prix fixe : « c'est un deal » <=> la facture a CE prix tient dans le budget (le test est exact des deux manieres)
for tot in (120.0, 150.0, 151.5, 180.0):
    x = {"lieu": "US", "total": tot, "port": 20.0, "valeur": 300.0}
    exact = lockerroom._paye(tot, x) <= deals._budget(300.0) + 0.005
    assert (tot <= deals.prix_max(300.0, taxe=deals.taxe_de(x)) + 1e-6) == exact
    assert (tot <= deals.prix_max(300.0, taxe=deals.taxe_de(x, valeur=300.0)) + 1e-6) == exact
# 6. un deal garde avant ce jour (la part du total seulement) retrouve son taux ; le taux lu suit ensuite la mise
vieux = {"lieu": "US", "import_lu": True, "import_cad": 50.0, "import_pct": 0.4167, "port": 20.0, "total": 220.0}
assert pres(deals._taux_import(vieux)[0], 0.5, 0.002)
assert deals.achat(lue)["import_taux"] == 0.5 and deals.achat({"lieu": "US"}) == {"lieu": "US"}
assert deals._taux_import({"lieu": "US", "import_lu": True, "import_pct": 0.42}) == (None, 0.42)       # la part seule : gardee
assert pres(deals.taxe_de({"lieu": "US", "import_lu": True, "import_pct": 0.42}), 0.42 + 0.05 * 1.42, 0.0002)
# 7. la veille : la surtaxe suit ce qu'eBay facture (15 annonces americaines relues au moins)
vu = datetime.now(timezone.utc).isoformat()
ann = [{"item_id": str(i), "lieu": "US", "import_lu": True, "import_cad": 25.0, "prix_cad": 100.0, "port_cad": 20.0, "vu_le": vu} for i in range(16)]
assert veille_ebay.calibrer_surtaxe({}, ann[:10]) is None                        # trop peu : rien ne change
assert veille_ebay.calibrer_surtaxe({}, [dict(a, lieu="GB") for a in ann]) is None
d = {}
assert veille_ebay.calibrer_surtaxe(d, ann) == 0.25 and d["surtaxe_n"] == 16
os.environ["LR_SURTAXE_US"] = "50"                                               # Render l'impose : la veille n'y touche pas
veille_ebay.appliquer(d)
assert deals.SURTAXE_US == 0.50
os.environ.pop("LR_SURTAXE_US")
veille_ebay.appliquer(d)
assert deals.SURTAXE_US == 0.25 and pres(deals.taxe_de(chere), 1.05 * 1.25 - 1, 0.0002)
assert veille_ebay.resume()["surtaxe_us"] == 25.0
deals.SURTAXE_US = 0.0                                                           # la surtaxe levee : comme un achat au Canada
assert deals.taxe_de(chere) == deals.TAXE_ACHAT
print("OK test_surtaxe_us")
