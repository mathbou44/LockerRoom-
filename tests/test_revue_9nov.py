"""9 nov 2026 (revue complete, « aucun faux indice ») : la parallele et la numerotation de la fiche servent a la comparaison ;
une valeur tiree d'une ou deux ventes n'est pas gardee comme valeur de la carte. Aucun reseau."""
import os, sys, tempfile
from datetime import datetime, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import suivi_valeur, lockerroom, vendues, cartes_match
t = suivi_valeur._titre({"titre": "2025-26 Upper Deck Young Guns Taylor Makar", "tirage": 250, "parallele": "Deluxe"})
assert "/250" in t and "Deluxe" in t, t
cib = cartes_match.cible_titre(t)
assert cartes_match.raisons_refus(cib, "2025-26 Upper Deck Young Guns Taylor Makar #238 RC")          # la base : refusee
assert suivi_valeur._titre({"titre": "2023 UD Young Guns Deluxe Makar 221/250", "tirage": 250, "parallele": "Deluxe"}).count("250") == 1
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
cid = a.carte_sauver({"titre": "2023-24 Upper Deck Young Guns Logan Cooley #451", "joueur": "Logan Cooley", "statut": "En stock", "prix_demande": 40})
cid = cid.get("id") if isinstance(cid, dict) else cid
j = lambda n: (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
vendues.memes_annonce = lambda *x, **k: {"ventes": [{"prix": 12.0, "le": j(3), "titre": "Cooley YG"}]}
r = a.carte_valeur(cid)
assert r["n"] == 1 and a.carte_lire(cid).get("valeur") is None, (r, a.carte_lire(cid))     # 1 vente : pas gardee
vendues.memes_annonce = lambda *x, **k: {"ventes": [{"prix": p, "le": j(d), "titre": "Cooley YG"} for p, d in ((20, 3), (22, 5), (21, 9))]}
r = a.carte_valeur(cid)
assert a.carte_lire(cid).get("valeur"), r                                                     # 3 ventes coherentes : gardee
print("OK test_revue_9nov")
