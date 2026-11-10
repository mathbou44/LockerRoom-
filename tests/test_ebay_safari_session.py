"""10 nov 2026 (Mathieu : dans l'app, « Se connecter avec eBay » ouvrait l'app DANS la feuille Safari ; fermer la feuille
ramenait a la connexion). Safari avait deja une session SlabCoach (un autre compte) : eBay etait relie a ce compte-la, sans
billet pour l'app. Maintenant : ce bouton est toujours une connexion -> billet pour l'app, et le compte eBay d'abord ouvert
avec eBay absorbe l'autre (meme eBay = un seul compte). python tests/test_ebay_safari_session.py"""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import sys, os, re, hashlib, urllib.parse
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, ebay_compte, auth_tiers as at
    ebay_compte._post_jeton = lambda d: ({"access_token": "AT", "expires_in": 7200, "refresh_token": "RT", "refresh_token_expires_in": 47304000}, None)
    ebay_compte._identite = lambda t: {"userId": "uid-M", "username": "hallofcardz"}
    server._premiere_synchro = lambda cid: None
    at.actif = lambda f: True
    at.terminer = lambda f, code, etat, base, u=None: {"ok": True, "sub": "a-1", "nom": "Mathieu Bourassa"}
    at.url_connexion = lambda f, base: "https://appleid.apple.com/auth/authorize?state=ETATA"
    ordi = server.app.test_client()                       # l'ordi : compte ouvert avec eBay (hallofcardz)
    loc = ordi.get("/auth/ebay").headers["Location"]
    e = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
    assert ordi.get("/api/ebay_retour?state=%%s&code=C" %% e).headers["Location"].endswith("bienvenue")
    natif = comptes.id_pour("uid-M", ebay_compte.environnement())
    with comptes.utiliser(natif):
        server.api.carte_sauver({"titre": "Carte de l ordi", "statut": "En stock"})
    safari = server.app.test_client()                     # Safari : une session Apple (« Mathieu Bourassa »)
    safari.get("/auth/apple"); safari.get("/auth/apple/retour?state=ETATA&code=C")
    cell = [c for c in comptes.lister() if c != natif][0]
    with comptes.utiliser(cell):
        server.api.carte_sauver({"titre": "Carte du cell", "statut": "En stock"})
    comptes.maj(cell, ebay_user_id="uid-M")              # ce que le bogue avait laisse : le meme eBay sur 2 comptes
    # l'app ouvre « Se connecter avec eBay » dans la feuille Safari (qui a la session du cell)
    v = "secret-app-789"; h = hashlib.sha256(v.encode()).hexdigest()
    loc = safari.get("/auth/ebay?app=" + h).headers["Location"]
    e = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
    r = safari.get("/api/ebay_retour?state=%%s&code=C" %% e)
    m = re.search(r"slabcoachauth://retour\\?b=([\\w-]+)", r.get_data(as_text=True))
    assert m, (r.status_code, r.headers.get("Location"), r.get_data(as_text=True)[:200])   # avant : /#reglages/ebay-ok DANS Safari
    app = server.app.test_client()                        # la vue web de l'app rend le billet avec son secret
    r = app.get("/auth/terminer?b=" + m.group(1) + "&v=" + v)
    assert r.headers["Location"].endswith("/#accueil/retour"), r.headers
    assert comptes.info(cell).get("renvoi") == natif and "apple:a-1" in comptes.info(natif).get("identites", [])
    l = app.post("/api/inventaire_liste", json=[]).get_json(); l = l if isinstance(l, list) else l.get("cartes", [])
    assert {"Carte de l ordi", "Carte du cell"} <= {x["titre"] for x in l}, l
    # ensuite, « Continuer avec Apple » sur le cell ouvre le meme compte
    tel = server.app.test_client(); tel.get("/auth/apple"); tel.get("/auth/apple/retour?state=ETATA&code=C")
    l = tel.post("/api/inventaire_liste", json=[]).get_json(); l = l if isinstance(l, list) else l.get("cartes", [])
    assert "Carte de l ordi" in {x["titre"] for x in l}, l
    print("SAFARI SESSION OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="sandbox",
               LOCKERROOM_EBAY_APP_ID_SANDBOX="App-SBX-1234", LOCKERROOM_EBAY_CERT_ID_SANDBOX="Cert-5678",
               LOCKERROOM_EBAY_RUNAME_SANDBOX="Ru-9999")
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-2500:])
    sys.exit(0 if "SAFARI SESSION OK" in r.stdout else 1)
