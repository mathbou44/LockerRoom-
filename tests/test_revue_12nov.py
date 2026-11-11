"""12 nov 2026 (Mathieu : « tu as toute la nuit : performance, outils, securite, SlabIQ, layout ») : la revue de la nuit."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
comptes.MULTI = False
import server
import lockerroom
c = server.app.test_client()
# 1. les methodes internes ne sont pas appelables par l'API
for nom in ("chemin_db", "sport_de"):
    r = c.post("/api/" + nom, json=[], headers={"Host": "localhost"})
    assert r.status_code == 403, (nom, r.status_code)
assert c.post("/api/sports_liste", json=[], headers={"Host": "localhost"}).status_code == 200
# 2. un reglage geant est refuse ; un reglage normal passe
api = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
try:
    api.reglages_sauver({"nom_boutique": "x" * (lockerroom.REGLAGE_MAX_OCTETS + 10)})
    raise AssertionError("aurait du refuser")
except ValueError:
    pass
assert api.reglages_sauver({"nom_boutique": "Ma boutique"})["nom_boutique"] == "Ma boutique"
# 3. les vendeurs suivis : l'ordre de priorite reste a l'admin ; les autres : alphabetique
import deals
orig = deals.vendeurs_suivis
deals.vendeurs_suivis = lambda: ["zeta_cards", deals.VENDEURS_PRIORITE[0], "alpha_cards"]
api._est_admin = lambda reel=False: False
v = api.deals_vendeurs_liste()["vendeurs"]
assert v == sorted(v, key=str.lower), v
api._est_admin = lambda reel=False: True
assert api.deals_vendeurs_liste()["vendeurs"][0] == deals.VENDEURS_PRIORITE[0]
deals.vendeurs_suivis = orig
# 4. les chiffres eBay de toute l'app : l'admin seulement (en ligne)
comptes.MULTI = True
api._est_admin = lambda reel=False: False
assert api.ebay_appels() == {}
comptes.MULTI = False
print("OK revue 12 nov")
# 5. la page de l'app en Brotli (si le module est la), identique une fois decompressee ; gzip sinon
comptes.MULTI = False
os.environ.pop("LOCKERROOM_CODE", None)
try:
    import brotli
except ImportError:
    brotli = None
if brotli:
    with server.app.test_request_context("/", headers={"Accept-Encoding": "gzip, deflate, br", "Host": "localhost"}):
        r = server._page_app()
    assert r.headers["Content-Encoding"] == "br"
    assert brotli.decompress(r.get_data()) == open(os.path.join(server.DOSSIER_UI, "app.html"), "rb").read()
with server.app.test_request_context("/", headers={"Accept-Encoding": "gzip", "Host": "localhost"}):
    r = server._page_app()
assert r.headers["Content-Encoding"] == "gzip"
print("OK brotli")
# 6. les joueurs du moment : en feu d'abord, sans doublon, jamais un prix
import indice_joueurs
_top = indice_joueurs.top
indice_joueurs.top = lambda n=12, filtre=None, actifs=None: {
    "en_feu": [{"nom": "A", "equipe": "SJS", "semaine": {"pts": 7, "mj": 3}}, {"nom": "B", "semaine": None}],
    "rebond": [{"nom": "A"}, {"nom": "C", "semaine": {"pts": 2, "mj": 2}}], "recrue": [{"nom": "D"}], "en_creux": []}.get(filtre, [])
lockerroom.Api._MOMENT.update(le=0.0, v=None)
r = api.joueurs_du_moment()
assert [j["nom"] for j in r["joueurs"]] == ["A", "B", "C", "D"], r
assert r["joueurs"][0]["pastille"] == "en_feu" and r["joueurs"][2]["pastille"] == "rebond" and r["joueurs"][0]["semaine"] == {"pts": 7, "mj": 3}
assert "prix" not in str(r) and "valeur" not in str(r)
indice_joueurs.top = _top
print("OK joueurs du moment")
# 7. SlabIQ : un titre sans indice (ni joueur connu, ni annee, ni mot de carte) n'a pas de score invente
import score_modele
if score_modele.charger():
    s = score_modele.scores(["Test", "Nike shoes size 10", "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC"])
    assert s[0] is None and s[1] is None and isinstance(s[2], int), s
    assert score_modele.informatif("Connor Bedard") and not score_modele.informatif("asdf qwer")
    print("OK SlabIQ titres sans indice")
# 8. le Score SlabIQ de l'inventaire : un appel, les cartes vendues exclues, les titres sans indice sans score, garde en cache
if score_modele.charger():
    a1 = api.carte_sauver({"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC", "joueur": "Macklin Celebrini", "statut": "En stock"})
    api.carte_sauver({"titre": "Test", "statut": "En stock"})
    api.carte_sauver({"titre": "2023-24 Upper Deck Young Guns Connor Bedard #451", "statut": "Vendue"})
    r = api.inventaire_scores()
    assert r["ok"] and len(r["scores"]) == 1 and all(isinstance(v, int) for v in r["scores"].values()), r
    assert api.inventaire_scores() is r                     # meme inventaire : rien n'est recalcule
    print("OK scores de l'inventaire")
# 9. le Radar garde 5 min (meme compte, meme profil) ; un prix cible ou le profil change -> refait ; frais=True -> refait
import ebay_compte
_rech = ebay_compte.rechercher
appels = []
ebay_compte.rechercher = lambda q, **k: (appels.append(q), [])[1]
lockerroom.Api._RADAR.clear()
r1 = api.mes_deals(); n1 = len(appels)
r2 = api.mes_deals()
assert len(appels) == n1 and "garde_s" in r2, (n1, len(appels))
api.deals_profil_regler({"favoris": ["Connor Bedard"]})
api.mes_deals()
assert len(appels) > n1                                  # le profil a change : le Radar est refait
n2 = len(appels); api.mes_deals(True)
assert len(appels) > n2                                  # tirer pour rafraichir
ebay_compte.rechercher = _rech
# 10. SlabIQ du Radar : un titre deja vu n'est pas recalcule
import score_slab
x1 = [{"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC"}]
score_slab.annoter_lot(x1)
_s = score_slab._annoter_lot
score_slab._annoter_lot = lambda l: (_ for _ in ()).throw(AssertionError("recalcule"))
x2 = [{"titre": "2024-25 Upper Deck Young Guns Macklin Celebrini #201 RC"}]
score_slab.annoter_lot(x2)
assert x2[0].get("score") == x1[0].get("score") and x2[0].get("carte") == x1[0].get("carte")
score_slab._annoter_lot = _s
print("OK Radar garde 5 min + SlabIQ en memoire")
# 11. le Radar survit a un redemarrage (disque) et un Radar vide (eBay lent) ne remplace pas le dernier bon
lockerroom.Api._RADAR.clear()
r0 = api.mes_deals()                                       # relu du disque, sans appel eBay
assert "garde_s" in r0, r0.keys()
k = next(iter(lockerroom.Api._RADAR)); t_, bon = lockerroom.Api._RADAR[k]
bon = {**bon, "pour_toi": [{"joueur": "X", "annonces": [{"item_id": str(i)} for i in range(10)]}]}
lockerroom.Api._RADAR[k] = (t_ - 99999, bon)
_calc = api._mes_deals_calcul
api._mes_deals_calcul = lambda: {"ok": True, "partiel": True, "pour_toi": [], "deals": []}
r = api.mes_deals(True)
assert r.get("ebay_lent") and len(r["pour_toi"][0]["annonces"]) == 10, r
api._mes_deals_calcul = _calc
print("OK Radar sur disque + eBay lent")
# 12. Tendances SlabIQ : des listes par pastille, les criteres de l'indice, jamais un prix
lockerroom.Api._TEND_IQ.update(le=0.0, v=None)
_lire, _top, _st = indice_joueurs.lire, indice_joueurs.top, indice_joueurs.statut
I = {"A": {"indice": 95, "actif": True, "equipe": "SJS", "pastilles": ["en_feu", "recrue"], "semaine": {"pts": 6, "b": 3, "mj": 3}, "criteres": {"forme": 99.2, "buzz": 70}},
     "B": {"indice": 70, "actif": True, "equipe": "CHI", "pastilles": ["rebond"], "creux": {"etat": "rebond", "ppm": 0.5, "avant_ppm": 0.7, "ecart_pct": -28}}}
indice_joueurs.lire = lambda: {"indice": I, "le": "2026-11-12"}
indice_joueurs.top = lambda n=12, filtre=None, actifs=None: [{"nom": k} for k, v in sorted(I.items(), key=lambda kv: -kv[1]["indice"]) if not filtre or filtre in v["pastilles"]][:n]
indice_joueurs.statut = lambda: {"joueurs": 2}
r = api.tendances_iq()
assert r["ok"] and [x["nom"] for x in r["cats"]["en_feu"]] == ["A"] and r["cats"]["rebond"][0]["creux"]["etat"] == "rebond"
assert r["cats"]["top"][0]["rang"] == 1 and r["cats"]["en_feu"][0]["criteres"] == {"forme": 99, "buzz": 70} and r["compte"]["en_feu"] == 1
assert "prix" not in json.dumps(r) and "valeur" not in json.dumps(r)
indice_joueurs.lire, indice_joueurs.top, indice_joueurs.statut = _lire, _top, _st
print("OK Tendances SlabIQ")
# 13. SlabIQ dans les breaks : chaque place recoit un Score SlabIQ (la demande de ce qu'elle donne), sans prix
if score_modele.charger():
    rb = api.analyse_break({"produit_id": "2024-25-the-cup", "boites": 1, "acheteur": True})
    assert rb["ok"] and any(pl.get("iq") is not None for pl in rb["places"]) and rb.get("iq_places")
    j0 = next(j for j in rb["joueurs"] if j.get("iq_joueurs"))
    assert set(j0["iq_joueurs"][0]) >= {"nom", "iq", "meilleur", "carte", "pastilles"}
    print("OK SlabIQ dans les breaks")
# 14. le lot repris ne cree plus de doublons (meme photo -> meme carte) ; les doublons deja la se retirent d'un geste
import base64, io
from PIL import Image as _Im
import random as _r; _r.seed(4); _im = _Im.new("RGB", (600, 840)); _im.putdata([(_r.randrange(256), _r.randrange(256), _r.randrange(256)) for _ in range(600 * 840)]); _b = io.BytesIO(); _im.save(_b, "JPEG", quality=80); PH = "data:image/jpeg;base64," + base64.b64encode(_b.getvalue()).decode()
g1 = api.carte_garder({"carte": {"joueur": "Lane Hutson"}, "titre": "Lane Hutson Red Prism /199", "prix": 20, "photos": [PH], "cle": "aaaaaaaa1111"})
g2 = api.carte_garder({"carte": {"joueur": "Lane Hutson"}, "titre": "Lane Hutson Red Prism /199", "prix": 20, "photos": [PH], "cle": "bbbbbbbb2222"})
assert g1["ok"] and g2.get("deja") and g2["id"] == g1["id"], (g1, g2)
c = api._db(); c.execute("DELETE FROM garder_photos"); c.commit(); c.close()            # comme avant le correctif
g3 = api.carte_garder({"carte": {"joueur": "Lane Hutson"}, "titre": "Lane Hutson Red Prism /199", "prix": 20, "photos": [PH], "cle": "cccccccc3333"})
assert g3["id"] != g1["id"]
assert api.doublons_a_finir()["n"] == 1
assert api.doublons_retirer()["retires"] == 1 and api.doublons_a_finir()["n"] == 0
assert api.carte_lire(g1["id"]) and not api.carte_lire(g3["id"])                        # la plus ancienne reste
print("OK lot sans doublons")
# 15. la sauvegarde .zip : l'admin seulement ; le zip contient les donnees, pas les caches
comptes.MULTI = False
r = c_ = server.app.test_client().get("/admin/sauvegarde.zip", headers={"Host": "localhost"})
assert r.status_code == 200 and r.data[:2] == b"PK", r.status_code
import zipfile as _zf
noms = _zf.ZipFile(io.BytesIO(r.data)).namelist()
assert any(n.endswith(".db") for n in noms) and not any(n.startswith("radar_garde") for n in noms), noms[:10]
print("OK sauvegarde zip")
# 16. recap d'un break : place par place, qui a eu quoi (jamais un prix)
c = api._db()
bid = c.execute("INSERT INTO breaks (nom, mode, statut) VALUES ('The Cup x2', 'equipes', 'ouvert')").lastrowid
p1 = c.execute("INSERT INTO places (break_id, cle, libelle, prix, acheteur, vendu, ordre) VALUES (?, 'MTL', 'Montreal', 40, 'jo123', 1, 1)", (bid,)).lastrowid
c.execute("INSERT INTO places (break_id, cle, libelle, prix, acheteur, vendu, ordre) VALUES (?, 'TOR', 'Toronto', 30, 'max', 1, 2)", (bid,))
c.execute("INSERT INTO frappes (break_id, carte, joueur, valeur, place_id) VALUES (?, 'Hutson RPA /99', 'Lane Hutson', 300, ?)", (bid, p1))
c.commit(); c.close()
rc = api.break_recap(bid, "fr")
assert rc["ok"] and rc["hits"] == 1 and rc["places"][0]["cartes"] == ["Hutson RPA /99"] and rc["places"][1]["cartes"] == []
assert "jo123" in rc["texte"] and "aucun hit" in rc["texte"] and "300" not in rc["texte"]
print("OK recap de break")
# 17. les annonces deja programmees : leurs heures a venir (pour continuer la serie apres la derniere)
from datetime import datetime as _d, timedelta as _t, timezone as _z
c = api._db()
futur = (_d.now(_z.utc) + _t(days=2)).isoformat(); passe = (_d.now(_z.utc) - _t(days=2)).isoformat()
c.execute("INSERT INTO cartes (titre, statut, item_number, debut) VALUES ('a', 'Listée', '111', ?)", (futur,))
c.execute("INSERT INTO cartes (titre, statut, item_number, debut) VALUES ('b', 'Listée', '112', ?)", (passe,))
c.execute("INSERT INTO cartes (titre, statut, debut) VALUES ('c', 'En stock', ?)", (futur,))       # pas sur eBay : ignoree
c.commit(); c.close()
pd = api.programmees_dates()
assert pd["ok"] and len(pd["dates"]) == 1, pd
print("OK annonces deja programmees")

# 18. 13 nov 2026 : les chiffres de SlabIQ (des comptes et un score, jamais un prix ; garde 10 min)
lockerroom.Api._IQ_CHIFFRES.update(le=0.0, v=None)
_r = lockerroom.Api.slabiq_chiffres(lockerroom.Api.__new__(lockerroom.Api))
assert _r["ok"] and "prix" not in json.dumps(_r), _r
assert lockerroom.Api.slabiq_chiffres(lockerroom.Api.__new__(lockerroom.Api)) is _r
print("ok 18 slabiq_chiffres")
