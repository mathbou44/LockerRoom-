"""Multi-comptes (serveur heberge) : python tests/test_multi.py  (demande flask et cryptography)."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json, urllib.parse
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, ebay_compte, ebay_avis
    ebay_compte._post_jeton = lambda d: ({"access_token": "AT", "expires_in": 7200, "refresh_token": "RT", "refresh_token_expires_in": 47304000}, None)
    ebay_compte._identite = lambda t: {"userId": "uid-" + t, "username": "vendeur"}
    server._premiere_synchro = lambda cid: None
    def client():
        c = server.app.test_client()
        loc = c.get("/auth/ebay").headers["Location"]
        etat = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
        return c, etat
    a, ea = client()
    assert a.post("/api/inventaire_liste", json=[]).status_code == 401
    assert a.get("/api/ebay_retour?state=%%s&code=C" %% ea).headers["Location"].endswith("bienvenue")
    ebay_compte._identite = lambda t: {"userId": "uid-B", "username": "autre"}
    b, eb = client()
    b.get("/api/ebay_retour?state=%%s&code=C" %% eb)
    a.post("/api/carte_sauver", json=[{"titre": "A seulement"}])
    vb = b.post("/api/inventaire_liste", json=[]).get_json()
    assert not (vb if isinstance(vb, list) else vb.get("cartes")), "fuite entre comptes"
    assert a.post("/api/ebay_cles_sauver", json=[{}]).status_code == 403
    assert len(comptes.lister()) == 2
    ebay_avis.recevoir(json.dumps({"notification": {"data": {"username": "autre"}}}).encode())
    assert len(comptes.lister()) == 1 and b.post("/api/inventaire_liste", json=[]).status_code == 401
    assert a.get("/api/ebay_retour?state=faux&code=C").headers["Location"] != "/#accueil/bienvenue"
    print("MULTI OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="sandbox",
               LOCKERROOM_EBAY_APP_ID_SANDBOX="App-SBX-1234", LOCKERROOM_EBAY_CERT_ID_SANDBOX="Cert-5678",
               LOCKERROOM_EBAY_RUNAME_SANDBOX="Ru-9999")
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-1500:])
    sys.exit(0 if "MULTI OK" in r.stdout else 1)
