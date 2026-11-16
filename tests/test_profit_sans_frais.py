"""16 nov 2026 (Mathieu : « payee 45, vendue 35 : profit 0 ? ») : une vente eBay sans frais connus a son profit refait avec
les frais estimes (13,25 % + 0,40 $), le cout complet (taxes et port) retire."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
from lockerroom import Api
a = Api()
r = a.carte_sauver({"titre": "Trevor Lawrence Prizm Black", "cout": 45})
cid = r.get("id") if isinstance(r, dict) else r
c = a._db()
c.execute("UPDATE cartes SET statut='Vendue', prix_vendu=35, frais=NULL, profit=0, canal='eBay' WHERE id=?", (cid,))
c.commit()
assert a._profit_juste(c, cid) == 1
c.commit()
p = c.execute("SELECT profit FROM cartes WHERE id=?", (cid,)).fetchone()[0]
assert abs(p - (35 - (35 * 0.1325 + 0.40) - 45)) < 0.01, p                    # -15,04
c.execute("UPDATE cartes SET frais=4, port_paye=2, port_charge=5 WHERE id=?", (cid,)); c.commit()
a._profit_juste(c, cid); c.commit()
assert abs(c.execute("SELECT profit FROM cartes WHERE id=?", (cid,)).fetchone()[0] - (35 + 5 - 4 - 2 - 45)) < 0.01   # frais connus
c.close()
print("PROFIT SANS FRAIS OK")
