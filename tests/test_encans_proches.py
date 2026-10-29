"""31 oct 2026 (Mathieu : « les encheres finissent ce soir ») : aux 15 min, les encans de Savage, Remi, CF31 et Slab Sharks
qui finissent dans 6 h sont relus sur eBay sans cache : la mise du moment arrive a l'ecran, un encan dont la mise a trop
monte n'est plus un deal, un suivi deja valorise garde sa valeur, et les encans au-dela de 6 h ne sont pas touches.
python tests/test_encans_proches.py (aucun appel reseau)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_DEALS_VERIF_JOUR"] = "0"
from datetime import datetime, timedelta, timezone
import deals, vendues, cartes_match

maint = datetime.now(timezone.utc)
fin = lambda h: (maint + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
T_DEAL = "2023-24 Upper Deck Canvas Auston Matthews #C70 Toronto Maple Leafs"
T_SUIVI = "1993-94 Upper Deck SP Teemu Selanne PSA 9"
T_LOIN = "2022-23 Upper Deck Clear Cut Connor McDavid #CC-1 Edmonton Oilers"
compte = {"prio": 0}
def ventes(q):
    out = []
    for t, v in ((T_DEAL, 60), (T_SUIVI, 80), (T_LOIN, 70)):
        if (cartes_match.requete_ebay(cartes_match.cible_titre(t)) or "").strip() == q:
            out += [{"titre": t, "prix": v * f, "le": (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d"), "url": f"{t}{d}"}
                    for f, d in ((1.0, 3), (0.95, 9), (1.05, 15))]
    return out
vendues.rechercher = lambda q, fond=True, usage=None, **k: (compte.__setitem__("prio", compte["prio"] + (usage == "prio"))) or {"ventes": ventes(q)}
vendues.en_cache = lambda q: None
vendues.utilises_aujourdhui = lambda usage=None: compte["prio"] if usage == "prio" else 0
deals._jour_mtl = lambda: (maint.strftime("%Y-%m-%d"), 20.0)

# avant : Matthews est un deal a 20 $ (vaut 60), Selanne un suivi deja valorise a 30 $, McDavid un deal qui finit dans 20 h
d0 = deals.lire()
d0["deals"] = [{"item_id": "a1", "titre": T_DEAL, "total": 20.0, "valeur": 60.0, "encan": True, "fin": fin(3), "vendeur": "savage.cards",
                "vu_le": maint.isoformat(timespec="seconds"), "v": deals.VERSION, "ratio": 0.33, "url": "u"},
               {"item_id": "a3", "titre": T_LOIN, "total": 20.0, "valeur": 70.0, "encan": True, "fin": fin(20), "vendeur": "savage.cards",
                "vu_le": maint.isoformat(timespec="seconds"), "v": deals.VERSION, "ratio": 0.29, "url": "u"}]
d0["suivis"] = [{"item_id": "a2", "titre": T_SUIVI, "total": 30.0, "valeur": 80.0, "n": 3, "vendues": [], "encan": True, "fin": fin(2),
                 "vendeur": "remi-card-trader", "vu_le": maint.isoformat(timespec="seconds"), "suivi": True}]
deals._ecrire(d0)

appels = []
def rech(q, **k):
    appels.append(k)
    if k.get("offset"):
        return []
    base = {"port_cad": 0.0, "vendeur_pct": "100", "vendeur_score": 90000, "encan": True, "mises": 9}
    return [dict(base, item_id="a1", titre=T_DEAL, prix_cad=55.0, url="u1", vendeur="savage.cards", fin=fin(3)),      # la mise a monte
            dict(base, item_id="a2", titre=T_SUIVI, prix_cad=41.0, url="u2", vendeur="remi-card-trader", fin=fin(2)),
            dict(base, item_id="a3", titre=T_LOIN, prix_cad=69.0, url="u3", vendeur="savage.cards", fin=fin(20))]       # au-dela de 6 h

r = deals.proches_prio(rech, bassin=deals.Bassin(charger=False), maint=maint)
assert appels and all(k.get("frais") and k.get("encheres") and k.get("vendeurs") == deals.VENDEURS_PRIORITE for k in appels), appels
assert len(appels) == 1                                               # la page finit apres 6 h : une seule recherche
d = deals.lire()
ids = {x["item_id"]: x for x in d["deals"]}
assert "a1" not in ids, ids.get("a1")                                 # 55 $ pour une carte de 60 $ : plus un deal
assert ids["a3"]["total"] == 20.0                                     # au-dela de 6 h : pas touche
s = {x["item_id"]: x for x in d["suivis"]}
assert s["a2"]["total"] == 41.0 and s["a2"]["valeur"] == 80.0, s["a2"]    # mise du moment, valeur gardee
assert d["proches"]["vus"] == 2, d["proches"]

# pas encore 15 min : la passe ne repart pas ; pendant un tour non plus
deals._ETAT.update(proches_le=__import__("time").time(), proches=False)
assert deals.proches_si_besoin() is False
deals._ETAT.update(proches_le=0, en_cours=True)
assert deals.proches_si_besoin() is False
deals._ETAT["en_cours"] = False
print("ok : encans proches")
