"""12 nov 2026 (Mathieu : « tu as toute la nuit : performance, outils, securite, SlabIQ, layout ») : la revue de la nuit."""
import os, sys, tempfile
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
