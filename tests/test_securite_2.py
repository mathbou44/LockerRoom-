"""8 nov 2026 (Mathieu : « assure-toi que notre application est protegee au maximum ») : 2e revue de securite."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import appels_ebay
# 1. la part de chaque compte dans les recherches eBay partagees
comptes.MULTI = True
os.environ["LR_EBAY_PART_COMPTE"] = "1"                         # 1 % de 5 000 = 50
comptes.activer("abcdefgh1234")
assert sum(1 for _ in range(70) if appels_ebay._part_compte_ok("browse")) == 50
try:
    appels_ebay.exiger("browse", fond=False)
    raise AssertionError("aurait du refuser")
except RuntimeError as e:
    assert "compte" in str(e)
appels_ebay.exiger("browse", fond=True)                          # le chasseur (tache de fond) n'est pas limite par compte
comptes.activer("zzzzzzzz9999")
appels_ebay.exiger("browse", fond=False)                         # un autre compte n'est pas touche
os.environ.pop("LR_EBAY_PART_COMPTE")
comptes.activer(None)
# 2. les codes d'appareil : 8 chiffres seulement
assert comptes.code_utiliser("123456") is None
# 3. les en-tetes : CSP sans formulaire vers ailleurs, l'API jamais en cache
comptes.MULTI = False
import server
c = server.app.test_client()
r = c.get("/sante")
assert "form-action 'self'" in r.headers["Content-Security-Policy"] and r.headers["X-Frame-Options"] == "SAMEORIGIN"
r = c.post("/api/sports_liste", json=[], headers={"Host": "localhost"})
assert r.headers.get("Cache-Control") == "no-store", r.headers
r = c.post("/api/_est_admin", json=[], headers={"Host": "localhost"})
assert r.status_code == 403                                      # jamais une methode privee
r = c.post("/api/sports_liste", data="x", headers={"Host": "localhost", "Content-Type": "text/plain"})
assert r.status_code == 415                                      # du JSON seulement (pas un formulaire d'un autre site)
r = c.post("/api/sports_liste", json=[], headers={"Host": "localhost", "Origin": "https://evil.example"})
assert r.status_code == 403                                      # un autre site
# 3b. CSP stricte : les scripts de nos pages passent par leur empreinte ; plus de « unsafe-inline » ; aucun onclick= dans l'app
from flask import Response
import re as _re
csp = r.headers["Content-Security-Policy"]
assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0] and "'sha256-" in csp and "report-uri /csp-rapport" in csp
with open(os.path.join(server.DOSSIER_UI, "app.html"), encoding="utf-8") as f:
    html = f.read()
assert not _re.search(r"\son[a-z]+=\"", html), "un attribut onclick / onerror dans l'app"
for k in server._empreintes_texte(html):
    assert k in csp
page = Response("<p>retour</p><script>location.replace('/#accueil')</script>", mimetype="text/html")
with server.app.test_request_context("/auth/x"):
    assert list(server._empreintes_texte(page.get_data(as_text=True)))[0] in server._csp(page)
r = c.post("/csp-rapport", json={"csp-report": {"violated-directive": "script-src", "blocked-uri": "inline"}}, headers={"Host": "localhost"})
assert r.status_code == 204
# 4. le rythme par compte : 40 gestes couteux par minute, puis 429 ; un autre compte n'est pas touche
comptes.MULTI = True
comptes.activer("abcdefgh1234")
assert sum(1 for _ in range(50) if server._rythme_ok("photo_identifier")) == server._RYTHME_LOURD_MAX
assert not server._rythme_ok("valeur_carte") and server._rythme_ok("sports_liste")    # les gestes legers passent encore
comptes.activer("zzzzzzzz9999")
assert server._rythme_ok("photo_identifier")
comptes.activer(None); comptes.MULTI = False
print("SECURITE 2 OK")
