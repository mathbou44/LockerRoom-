"""18 nov 2026 (Mathieu : « nouveau produit sort bientot, une semaine avant ; sorti le jour meme ; Upper Deck au hockey,
Topps au baseball ») : les sorties du calendrier deviennent des nouvelles selon l'onglet de sport."""
import os, sys, tempfile, json
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import sorties
auj = date(2026, 11, 18)
j = lambda n: (auj + timedelta(days=n)).isoformat()
P = [{"nom": "2026-27 Upper Deck SP Authentic Hockey", "date": j(5)}, {"nom": "2026-27 Upper Deck Ice Hockey", "date": j(0)},
     {"nom": "2026-27 Upper Deck Black Diamond Hockey", "date": j(12)},            # trop loin
     {"nom": "2026-27 Panini Prizm Hockey", "date": j(2)},                          # pas Upper Deck
     {"nom": "2026 Topps Chrome Update Baseball", "date": j(3)}, {"nom": "2026 Bowman Draft Baseball", "date": j(1)},
     {"nom": "2026-27 Upper Deck Artifacts Hockey", "date": j(-3)},                 # sorti il y a 3 jours : plus une nouvelle
     {"nom": "2026-27 Upper Deck MVP Hockey", "date": None}]
for x in P:
    x.update(sport=sorties.sport_de(x["nom"]), marque=sorties.marque_de(x["nom"]), phare=bool(sorties.PHARES.search(x["nom"])))
sorties._ecrire({"le": 0, "produits": P})
h = sorties.annonces("hockey", "fr", auj)
assert [x["titre"] for x in h] == ["Nouveau produit sorti : 2026-27 Upper Deck Ice Hockey", "Nouveau produit : 2026-27 Upper Deck SP Authentic Hockey sort dans 5 jours"], h
b = sorties.annonces("baseball", "en", auj)
assert [x["titre"] for x in b] == ["New product: 2026 Bowman Draft Baseball drops in 1 day", "New product: 2026 Topps Chrome Update Baseball drops in 3 days"], b
assert all(x["produit"] and x["source"] == "SlabCoach" for x in h + b)
assert sorties.annonces("football", "fr", auj) == []
print("SORTIES NOUVELLES OK")
