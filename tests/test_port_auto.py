"""24 nov 2026 (Mathieu : « pour les cartes de moins de 30 $ c'est toujours 3 $ de ship ; comment ca, ce n'est pas
automatique ? ») : l'envoi automatique des petites ventes eBay. Eteint par defaut ; ne remplit que les cases VIDES ; un
montant entre a la main (meme 0) n'est jamais ecrase ; la consignation et les autres canaux ne sont pas touches."""
import os, sys, tempfile, sqlite3
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ.pop("LOCKERROOM_MULTI", None)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom
api = lockerroom.Api()
api.reglages_lire()
def poser(titre, prix, port_paye, profit, canal="eBay", cons=None):
    c = api._db()
    try:
        c.execute("INSERT INTO cartes (titre, statut, canal, prix_vendu, port_charge, port_paye, frais, profit, consignataire_id, vendu_le, cree_le) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (titre, "Vendue", canal, prix, 3.0, port_paye, 4.0, profit, cons, "2026-11-23T10:00:00", "2026-11-01T10:00:00"))
        c.commit()
    finally:
        c.close()
def lire():
    c = api._db()
    try:
        return {r[0]: (r[1], r[2]) for r in c.execute("SELECT titre, port_paye, profit FROM cartes")}
    finally:
        c.close()
poser("petite vide", 25.0, None, 19.0)             # la case jamais remplie : c'est elle qu'on vise
poser("petite a zero", 25.0, 0.0, 19.0)            # 0 entre a la main : on n'y touche pas
poser("petite deja 5", 25.0, 5.0, 14.0)            # deja entree
poser("grosse vide", 80.0, None, 60.0)             # au-dessus du seuil
poser("juste au seuil", 30.0, None, 22.0)          # 30 $ n'est pas « moins de 30 $ »
poser("magasin", 10.0, None, 8.0, canal="Magasin") # pas eBay
poser("consignation", 20.0, None, 4.0, cons=7)     # profit = une commission
# 1. eteint par defaut : rien ne bouge, meme apres une « synchro »
assert api.reglages_lire().get("port_auto") == {}
c = api._db(); n = api._port_auto_appliquer(c, api.reglages_lire()); c.commit(); c.close()
assert n == 0 and lire()["petite vide"] == (None, 19.0)
# 2. regle : 3 $ sous 30 $ -> une seule vente change, son profit baisse de 3 $
r = api.port_auto_regler(30, 3)
assert r["ok"] and r["appliquees"] == 1 and r["port_auto"] == {"seuil": 30.0, "montant": 3.0}, r
L = lire()
assert L["petite vide"] == (3.0, 16.0), L["petite vide"]
assert L["petite a zero"] == (0.0, 19.0) and L["petite deja 5"] == (5.0, 14.0)
assert L["grosse vide"] == (None, 60.0) and L["juste au seuil"] == (None, 22.0)
assert L["magasin"] == (None, 8.0) and L["consignation"] == (None, 4.0)
assert api.reglages_lire()["port_auto"] == {"seuil": 30.0, "montant": 3.0}
# 3. une 2e fois : rien de plus (la case n'est plus vide), jamais 3 $ retires deux fois
assert api.port_auto_regler(30, 3)["appliquees"] == 0 and lire()["petite vide"] == (3.0, 16.0)
# 4. une nouvelle vente arrive : la synchro la remplit
poser("nouvelle", 12.0, None, 7.0)
c = api._db(); n = api._port_auto_appliquer(c, api.reglages_lire()); c.commit(); c.close()
assert n == 1 and lire()["nouvelle"] == (3.0, 4.0)
# 5. eteindre : plus rien ne se remplit ; ce qui est pose reste (il se corrige dans la fiche)
assert api.port_auto_regler(0, 0)["port_auto"] == {} and api.reglages_lire()["port_auto"] == {}
poser("apres", 12.0, None, 7.0)
c = api._db(); assert api._port_auto_appliquer(c, api.reglages_lire()) == 0; c.close()
assert lire()["apres"] == (None, 7.0) and lire()["petite vide"] == (3.0, 16.0)
# 6. des montants absurdes sont refuses
assert not api.port_auto_regler(30, 500)["ok"] and not api.port_auto_regler("abc", 3)["ok"] and not api.port_auto_regler(-5, 3)["ok"]
# 7. la synchro des ventes eBay appelle la regle, et l'ecran l'offre la ou le port compte comme du profit
src = open(os.path.join(RACINE, "lockerroom.py"), encoding="utf-8").read()
assert "self._port_auto_appliquer(c, r)" in src and '"port_auto": {},' in src
app = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert 'id="fvd-pa"' in app and "function feuillePortAuto(){" in app and "API.port_auto_regler(s_, m_)" in app
print("OK test_port_auto")
