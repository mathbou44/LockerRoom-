"""28 oct 2026 : relier eBay depuis Profil dans l'app iPhone (navigateur securise, Google) : python tests/test_ebay_lier_app.py"""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import sys, os, re, hashlib
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, auth_tiers as at
    at.actif = lambda f: True
    at.terminer = lambda f, code, etat, base, u=None: {"ok": True, "sub": "g-1", "courriel": "x@y.z", "nom": "Mathieu"}
    at.url_connexion = lambda f, base: "https://accounts.google.com/o/oauth2/v2/auth?state=ETATG"
    vue = server.app.test_client()                     # la vue web de l'app, deja connectee
    vue.get("/auth/google"); vue.get("/auth/google/retour?state=ETATG&code=C")
    cid = comptes.lister()[0]
    termines = []
    server.api.ebay_url_connexion = lambda: {"ok": True, "url": "https://auth.sandbox.ebay.com/oauth2/authorize?client_id=x&state=ETATE"}
    def terminer(texte, etat=None):
        termines.append((comptes.courant(), etat)); return {"ok": True}
    server.api.ebay_terminer = terminer
    server._premiere_synchro = lambda c: None
    j = vue.post("/api/ebay_jeton_lier", json=[]).get_json(); assert j["ok"], j
    v = "secret-app-456"; h = hashlib.sha256(v.encode()).hexdigest()
    nav = server.app.test_client()                     # le navigateur securise : AUCUNE session
    r = nav.get("/auth/ebay-lier?t=" + j["jeton"] + "&app=" + h)
    assert r.status_code == 302 and "auth.sandbox.ebay.com" in r.headers["Location"], r.headers
    assert "erreur=3" in server.app.test_client().get("/auth/ebay-lier?t=" + j["jeton"]).headers["Location"]   # usage unique
    r = nav.get("/api/ebay_retour?code=C&state=ETATE")
    m = re.search(r"slabcoachauth://retour\\?b=([\\w-]+)", r.get_data(as_text=True)); assert m, r.get_data(as_text=True)[:300]
    assert termines == [], termines                       # 3 nov 2026 : rien n'est relie avant que l'app rende le billet
    assert "erreur=3" in vue.get("/auth/terminer?b=" + m.group(1) + "&v=mauvais").headers["Location"] and termines == []
    r = nav.get("/api/ebay_retour?code=C&state=ETATE")   # (etat deja utilise : rien)
    j3 = vue.post("/api/ebay_jeton_lier", json=[]).get_json()
    r3 = nav.get("/auth/ebay-lier?t=" + j3["jeton"] + "&app=" + h)
    server.api.ebay_url_connexion = lambda: {"ok": True, "url": "https://auth.sandbox.ebay.com/oauth2/authorize?client_id=x&state=ETATF"}
    r3 = nav.get("/auth/ebay-lier?t=" + vue.post("/api/ebay_jeton_lier", json=[]).get_json()["jeton"] + "&app=" + h)
    r = nav.get("/api/ebay_retour?code=C&state=ETATF")
    m = re.search(r"slabcoachauth://retour\\?b=([\\w-]+)", r.get_data(as_text=True)); assert m, r.get_data(as_text=True)[:300]
    r = vue.get("/auth/terminer?b=" + m.group(1) + "&v=" + v)
    assert termines == [(cid, "ETATF")], termines         # le jeton eBay va dans LE BON compte, avec le secret de l'app
    assert r.headers["Location"].endswith("/#reglages/ebay-ok"), r.headers
    # 3 nov 2026 (revue) : un lien « relier » ouvert dans un navigateur SANS l'app et sans la session de ce compte : refuse
    j4 = vue.post("/api/ebay_jeton_lier", json=[]).get_json()
    assert "r=lien" in server.app.test_client().get("/auth/ebay-lier?t=" + j4["jeton"]).headers["Location"]
    # un retour dans un autre navigateur (sans le temoin) ne relie rien
    j2 = vue.post("/api/ebay_jeton_lier", json=[]).get_json()
    server.app.test_client().get("/auth/ebay-lier?t=" + j2["jeton"] + "&app=" + h)
    r = server.app.test_client().get("/api/ebay_retour?code=C&state=ETATE")
    assert "slabcoachauth" not in r.get_data(as_text=True) and len(termines) == 1, termines
    print("EBAY LIER OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="sandbox")
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-2500:])
    sys.exit(0 if "EBAY LIER OK" in r.stdout else 1)
