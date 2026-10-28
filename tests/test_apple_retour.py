"""Retour de « Se connecter avec Apple » en 2 temps (POST d'Apple, puis GET chez nous) : python tests/test_apple_retour.py"""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import sys, os, re, urllib.parse
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, auth_tiers as at
    at.actif = lambda f: True
    at.terminer = lambda f, code, etat, base, u=None: {"ok": True, "sub": "apple-sub-1", "courriel": "x@privaterelay.appleid.com", "nom": "Mathieu"}
    at.url_connexion = lambda f, base: "https://appleid.apple.com/auth/authorize?state=ETAT123&response_mode=form_post"
    c = server.app.test_client()
    r = c.get("/auth/apple"); assert r.status_code == 302 and "sc_lien" in r.headers.get("Set-Cookie", ""), r.headers
    # 1. Apple revient en POST : PAS de session ouverte ici (Safari ne l'enregistrerait pas), un billet a la place
    r = c.post("/auth/apple/retour", data={"state": "ETAT123", "code": "C"})
    assert r.status_code == 200 and "session=" not in (r.headers.get("Set-Cookie") or ""), r.headers
    suite = re.search(r"url=(/auth/terminer\\?b=[\\w-]+)", r.get_data(as_text=True)).group(1)
    assert c.post("/api/inventaire_liste", json=[]).status_code == 401
    # 2. notre page repart en GET : la session s'ouvre et on arrive dans l'app
    r = c.get(suite); assert r.status_code == 302 and r.headers["Location"].endswith("/#accueil/bienvenue"), r.headers
    assert c.post("/api/inventaire_liste", json=[]).status_code == 200
    # billet a usage unique, et inutilisable dans un autre navigateur
    assert "erreur=3" in c.get(suite).headers["Location"]
    d = server.app.test_client(); d.get("/auth/apple")
    r = d.post("/auth/apple/retour", data={"state": "ETAT123", "code": "C"})
    s2 = re.search(r"url=(/auth/terminer\\?b=[\\w-]+)", r.get_data(as_text=True)).group(1)
    e = server.app.test_client()
    assert "erreur=3" in e.get(s2).headers["Location"]
    # 3. app iPhone : connexion dans le navigateur securise, billet ramene a l'app, echange avec le secret de l'app
    import hashlib
    v = "secret-de-l-app-123"; h = hashlib.sha256(v.encode()).hexdigest()
    nav = server.app.test_client()                     # le navigateur securise d'iOS
    nav.get("/auth/apple?app=" + h)
    r = nav.post("/auth/apple/retour", data={"state": "ETAT123", "code": "C"})
    m = re.search(r"slabcoachauth://retour\\?b=([\\w-]+)", r.get_data(as_text=True)); assert m, r.get_data(as_text=True)[:300]
    app = server.app.test_client()                     # la vue web de l'app : aucun temoin du navigateur
    assert "erreur=3" in app.get("/auth/terminer?b=" + m.group(1) + "&v=mauvais").headers["Location"]   # billet brule
    nav.get("/auth/apple?app=" + h)
    r = nav.post("/auth/apple/retour", data={"state": "ETAT123", "code": "C"})
    b = re.search(r"slabcoachauth://retour\\?b=([\\w-]+)", r.get_data(as_text=True)).group(1)
    r = app.get("/auth/terminer?b=" + b + "&v=" + v); assert r.headers["Location"].endswith("/#accueil/retour"), r.headers
    assert app.post("/api/inventaire_liste", json=[]).status_code == 200
    # 4. Google revient en GET : session directe (navigateur normal)
    at.url_connexion = lambda f, base: "https://accounts.google.com/o/oauth2/v2/auth?state=ETATG"
    g = server.app.test_client(); g.get("/auth/google")
    r = g.get("/auth/google/retour?state=ETATG&code=C"); assert r.status_code == 302 and "#accueil" in r.headers["Location"], r.headers
    assert g.post("/api/inventaire_liste", json=[]).status_code == 200
    # 5. page de connexion : Google visible dans l'app qui a le navigateur securise, cache dans l'ancienne
    vieux = server.app.test_client().get("/connexion", headers={"User-Agent": "iPhone LockerRoomiOS/1.0"}).get_data(as_text=True)
    neuf = server.app.test_client().get("/connexion", headers={"User-Agent": "iPhone LockerRoomiOS/1.1 SlabCoachAuth"}).get_data(as_text=True)
    assert "/auth/google" not in vieux and "/auth/google" in neuf and "/auth/apple" in neuf
    print("APPLE RETOUR OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="sandbox")
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-2500:])
    sys.exit(0 if "APPLE RETOUR OK" in r.stdout else 1)
