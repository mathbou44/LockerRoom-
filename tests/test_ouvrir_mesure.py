"""23 nov 2026 (Mathieu, devant « Keep sealed -93 % » sur la boite d'Ice : « tu veux dire quoi par keep sealed ? ») :
1. le verdict « ouvrir / scellee » ne parait que si au moins la moitie de la valeur de la boite vient de VRAIES ventes
   (Ice et Artifacts : 0 %, nos valeurs par defaut, d'ou -93 % : on annoncait plus que ce qu'on mesure) ;
2. le badge dit « Vaut plus scellee » (plus « Garder scellee -93 % ») ; l'astuce de l'accueil dit d'ou vient le chiffre."""
import os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp(prefix="lr_ouvrir_"))
import marche
# 1. la regle
assert marche.OUVRIR_PART_MIN == 50.0
assert marche.verdict_ouvrir(15.22, 220, 0.0) is None, "Ice : 0 % de vraies ventes, aucun verdict"
assert marche.verdict_ouvrir(15.22, 220, 49.9) is None
v = marche.verdict_ouvrir(130, 220, 66.3)
assert v and v["verdict"] == "garder" and v["pct"] == -41 and v["mesure_pct"] == 66, v
assert marche.verdict_ouvrir(120, 100, 50.0)["verdict"] == "ouvrir" and marche.verdict_ouvrir(95, 100, 90)["verdict"] == "neutre"
assert marche.verdict_ouvrir(120, 100)["verdict"] == "ouvrir" and marche.verdict_ouvrir(120, 100)["mesure_pct"] is None      # appel direct : comme avant
assert marche.verdict_ouvrir(0, 100, 90) is None and marche.verdict_ouvrir(100, None, 90) is None
# 2. le catalogue : chaque produit porte sa part mesuree ; sans vraies ventes, pas de verdict, meme avec un prix de boite
import lockerroom, valeur_produit, calcul, catalogue, astuces
api = lockerroom.Api()
vrai = valeur_produit.de
valeur_produit.de = lambda pid: {"boite": 200.0}
try:
    api._EV_CACHE.clear()
    P = api.catalogue_liste()["produits"]
    assert len(P) >= 10, len(P)
    avec = [p for p in P if p["ouvrir"]]; sans = [p for p in P if not p["ouvrir"]]
    for p in P:
        part = calcul.prix_catalogue(catalogue.charger(p["id"]), boites=1)["part_mesuree"]
        assert abs(p["ev_mesuree_pct"] - part) < 1e-6, (p["id"], p["ev_mesuree_pct"], part)
        assert bool(p["ouvrir"]) == (part >= 50.0 and p["ev_par_boite"] > 0), (p["id"], part, p["ouvrir"])
    assert sans, "au moins un produit sans vraies ventes dans le depot (sinon ce test ne prouve rien)"
    # l'astuce de l'accueil ne prend jamais un produit sans verdict, et dit la part de vraies ventes
    a = astuces.ouvrir(api, "fr")
    if avec:
        assert a and any(a["titre"].startswith(p["nom"]) for p in avec), a
        assert "vient de vraies ventes" in a["texte"] and "garder scellée" not in a["titre"]
    else:
        assert a is None, a
finally:
    valeur_produit.de = vrai
    api._EV_CACHE.clear()
# 3. les mots a l'ecran
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "tt('Vaut plus scellée', 'Worth more sealed')" in s and "Keep sealed" not in s and "Garder scellée" not in s
app = open(os.path.join(ICI, "ui", "app.html"), encoding="utf-8").read()
assert "Worth more sealed" in app and "Keep sealed" not in app, "reconstruire ui/app.html"
src = open(os.path.join(ICI, "astuces.py"), encoding="utf-8").read()
assert "worth more sealed" in src and "better kept sealed" not in src and "(real sales, without" not in src
print(f"OK test_ouvrir_mesure ({len(avec)} produits avec un verdict, {len(sans)} sans : pas assez de vraies ventes)")
