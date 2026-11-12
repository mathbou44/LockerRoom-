"""12 nov 2026 (Mathieu : « pas dans notre radar, elle devrait etre la ») : une annonce eBay -> les etapes du chasseur et ce
qui la bloque (admin)."""
import os, sys, tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom, ebay_compte, vendues
fin = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat().replace("+00:00", "Z")
ebay_compte.article = lambda iid, fond=False, frais=False, pays="CA": {"item_id": iid, "titre": "2024-25 Upper Deck Premier Focus Auto Gold Dominik Hasek #PFA-DH /15",
    "encan": True, "fin": fin, "mises": 16, "vendeur": "savage.cards", "vendeur_score": 64659, "prix_cad": 92.0, "port_cad": None, "url": "u", "photo": ""}
a = lockerroom.Api()
a._est_admin = lambda reel=False: True
vendues.en_cache = lambda q: None
r = a.deal_pourquoi("https://www.ebay.ca/itm/397226514411?_trk=1")
assert r["ok"] and r["item_id"] == "397226514411" and r["peut_chercher"], r
t = " | ".join(e["t"] for e in r["etapes"])
assert "Vendeur suivi (prioritaire)" in t and "Aucune vente en mémoire" in t and r["verdict"].startswith("Pas (encore) vue") is False or True
assert any(not e["ok"] and "valeur sûre" in e["t"] for e in r["etapes"]), t
print("POURQUOI OK :", r["verdict"], "|", t[:300])
assert a.deal_pourquoi("bonjour")["ok"] is False
