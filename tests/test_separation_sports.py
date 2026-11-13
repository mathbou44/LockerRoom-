"""13 nov 2026 (Mathieu : « bien separer les sports pour ne pas creer de bruit et de confusion ; tout melanger serait une
catastrophe ») : un sport = un monde. Une carte de baseball n'entre jamais dans un moteur du hockey."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = tempfile.mkdtemp()
import sports, mlb, base_ventes, score_slab, deals

mlb._ecrire("mlb_joueurs.json", {"le": 9e12, "joueurs": mlb.lire_liste([{"id": 1, "fullName": "Paul Skenes"}, {"id": 2, "fullName": "Konnor Griffin"}], "MLB")})
# 1. une seule regle pour le sport d'une carte
assert sports.sport_de("2025 Topps Chrome Paul Skenes Auto /99") == "baseball"          # joueur MLB connu
assert sports.sport_de("2025 Bowman Chrome 1st Bowman Konnor Griffin") == "baseball"
assert sports.sport_de("2015-16 Upper Deck Young Guns Connor McDavid") == "hockey"
assert sports.sport_de("2024-25 Panini Prizm Victor Wembanyama Los Angeles Lakers") != "hockey"
# 2. qui sert quoi
assert sports.sert("score", "hockey") and not sports.sert("score", "baseball") and not sports.sert("deals", "baseball")
assert sports.sert("ventes", "baseball") and not sports.sert("ventes", "basketball")
# 3. les ventes : une recherche de baseball faite par l'app va dans la base du baseball
V = lambda t, u: {"titre": t, "prix": 40, "le": "2026-11-12", "url": u}
base_ventes.noter("paul skenes topps chrome", [V("2025 Topps Chrome Paul Skenes Refractor", "a1"), V("Paul Skenes 2025 Topps Chrome RC", "a2")])
base_ventes.noter("demidov young guns", [V("2024-25 Upper Deck Young Guns Ivan Demidov", "b1")])
assert base_ventes.nombre("baseball") == 2 and base_ventes.nombre() == 1, (base_ventes.nombre("baseball"), base_ventes.nombre())
# 4. SlabIQ : pas de score du hockey sur une carte de baseball
r = score_slab.score("2025 Topps Chrome Paul Skenes Auto /99")
assert r["score"] is None and r["sport"] == "baseball" and r["bientot"]
# 5. le chasseur : une carte de baseball n'est ni jugee ni payee avec les credits du hockey
appels = []
st, dl = {}, {}
a = {"item_id": "1", "titre": "2025 Topps Chrome Paul Skenes Auto /99", "prix_cad": 80, "encan": True, "vendeur": "savage.cards",
     "fin": "2026-11-14T20:00:00Z"}
from datetime import datetime, timezone
deals._juger0(a, {"q": None, "flux": "vendeurs", "suivi": True}, [], [], datetime.now(timezone.utc), dl, st,
              verif=lambda cib: appels.append(cib) or [])
assert not appels and not dl and st.get("autre_sport", 0) + st.get("annonces", 0) <= 1 and "1" not in dl, st
assert deals._sport_servi({"titre": "2015-16 Upper Deck Young Guns Connor McDavid"}, {}) is True
assert deals._sport_servi({"titre": "2025 Topps Chrome Paul Skenes Auto /99"}, {}) is False
assert deals._sport_servi({"titre": "2025 Topps Chrome Paul Skenes Auto /99 Pittsburgh Pirates"}, {"suivi": True}) is False
assert deals._noter_suivi({}, dict(a, titre="2025 Topps Chrome Paul Skenes Auto /99 Pittsburgh Pirates PSA 10"), None, datetime.now(timezone.utc)) in ("autre_sport", "joueur_inconnu", "pas_hockey")
print("OK separation des sports", st)
