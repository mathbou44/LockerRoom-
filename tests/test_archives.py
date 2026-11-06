"""7 nov 2026 (Mathieu : une Nazar Future Watch Auto Inscribed « aucune vente trouvee », 130point en a 6) : eBay ne montre que
90 jours de ventes ; nos archives (base_ventes) gardent tout ce que nos recherches ont vu, et la fiche les relit."""
import os, sys, tempfile
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import base_ventes, vendues, cartes_match

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
base_ventes.noter("frank nazar future watch auto", [
    {"titre": "2024-25 Upper Deck SP Authentic Future Watch Inscribed Frank Nazar Auto 005/999", "prix": 500, "le": jr(218), "url": "u1"},
    {"titre": "2024-25 Sp Authentic - Frank Nazar Future Watch Auto INSCRIBED /999 (Rookie)", "prix": 497.63, "le": jr(237), "url": "u2"},
    {"titre": "2024-25 SP Authentic Future Watch Auto Frank Nazar 355/999", "prix": 116, "le": jr(51), "url": "u3"},     # sans inscription
    {"titre": "2024-25 SP Authentic Future Watch Auto Inscribed Frank Nazar 101/999", "prix": 450, "le": jr(500), "url": "u4"}])  # plus d'un an
c = cartes_match.cible_titre("Frank Nazar 2024-25 SP Authentic Future Watch Auto Inscribed 17/999 Blackhawks")
a = vendues.archives(c)
assert sorted(v["url"] for v in a) == ["u1", "u2"], a
vendues.rechercher = lambda q, fond=False, **k: {"ventes": [], "erreur": None}
r = vendues.memes("Frank Nazar 2024-25 SP Authentic Future Watch Auto Inscribed 17/999 Blackhawks", requete=False)
assert r["nb"] == 2 and r["mediane"], r
print("ARCHIVES OK")
