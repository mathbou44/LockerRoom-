"""31 oct 2026 (Mathieu : « 3 joueurs suivis pour le compte gratuit, au moins 10 pour les payants ; avertir quand ils
pop dans les deals »). Aucun reseau."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alarmes  # noqa: E402
import deals  # noqa: E402
import forfaits  # noqa: E402
import lockerroom  # noqa: E402

deals.valide = lambda x: True
a = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "j.db"))
envois = []
a._push = lambda titre, texte, data=None: envois.append(titre) or True
noms = ["Matvei Gridin", "Bedard", "Canadiens", "Crosby", "Hagens"]
forfaits.est_pro = lambda: False
# 9 nov 2026 (Mathieu : « max de 5 en non pro et 20 en pro »)
r = a.deals_profil_regler({"favoris": noms + ["Celebrini"]})
assert r["ok"] is False and r["pro_requis"] and r["favoris"] == noms and r["favoris_max"] == 5 and "20 avec Pro" in r["erreur"], r
forfaits.est_pro = lambda: True
r = a.deals_profil_regler({"favoris": noms + [f"Joueur {i}" for i in range(18)]})
assert r["ok"] is False and len(r["favoris"]) == 20 and r["favoris_max"] == 20, r
r = a.deals_profil_regler({"favoris": noms})
assert r.get("ok") is not False and r["favoris"] == noms, r

f = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
deals._ecrire({"deals": [{"item_id": "1", "titre": "2025-26 Upper Deck Young Guns Matvei Gridin #470", "total": 30, "valeur": 80, "encan": True, "fin": f},
                         {"item_id": "2", "titre": "2025-26 Upper Deck Young Guns Joe Nobody", "total": 3, "valeur": 10}],
               "suivis": [{"item_id": "3", "titre": "2015-16 SP Authentic Sidney Crosby Auto", "total": 60, "valeur": 200, "encan": True, "fin": f},
                          {"item_id": "4", "titre": "Bedard Young Guns", "total": 190, "valeur": 200, "encan": True, "fin": f}]})
assert alarmes.mes_joueurs(a) == 0                       # pas coche : rien
a.alarmes_regler({"mes_joueurs": True})
n = alarmes.mes_joueurs(a)
assert n == 2, (n, envois)                                # Gridin (deal) et Crosby (encan a 30 %) ; Bedard a 95 % : non
assert alarmes.mes_joueurs(a) == 0                       # une seule fois par annonce
print("OK test_mes_joueurs", envois)
# 9 nov 2026 (« on distingue pas le but de la notif ») : une sorte, un sujet, un detail ; plus d'emoji ; le detail est garde
import marche  # noqa: E402
assert marche.decrire({"item_id": "vendu:3", "titre": "\U0001F4B0 Vendue : Tage Thompson", "total": 55}) == {"sorte": "vente", "sujet": "Tage Thompson", "detail": "Vendue 55 $"}
d = marche.decrire({"item_id": "deal:123456789012", "titre": "Deal −62 % : Gridin YG", "total": 30})
assert d["sorte"] == "deal" and d["sujet"] == "Gridin YG" and d["detail"].startswith("−62 %"), d
assert marche.decrire({"item_id": "77", "alerte_id": 2, "titre": "Will Smith", "total": 12})["sorte"] == "prix"
lst = a.alertes_liste()["notifications"]
assert lst and all(n.get("sorte") and n.get("sujet") for n in lst), lst
assert all(not any(ord(ch) > 0x2600 and ch not in "−" for ch in n["titre"]) for n in lst), [n["titre"] for n in lst]
assert any(n.get("texte") for n in lst)
print("OK notifications lisibles")
