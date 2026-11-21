"""21 nov 2026 (Mathieu : « un pare-feu ; impenetrable et fiable ») : quand LR_ORIGINE_BLOQUER=1, seul le trafic venu de
Cloudflare (en-tete secret X-SC-Origine) passe ; l'adresse directe de Render est refusee. La vraie IP vient alors de Cloudflare."""
import os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI); os.chdir(ICI)
os.environ.update(LOCKERROOM_DONNEES=tempfile.mkdtemp(), LOCKERROOM_MULTI="1", LOCKERROOM_TACHES="0", LOCKERROOM_HEBERGE="1",
                  LR_ORIGINE_JETON="s" * 30, LR_ORIGINE_BLOQUER="1", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999")
import server
cl = server.app.test_client()
B = {"X-SC-Origine": "s" * 30}
assert cl.get("/sante").status_code == 200                                   # Render verifie la sante en direct
assert cl.get("/connexion").status_code == 403                                # adresse directe : refusee
assert cl.get("/connexion", headers={"X-SC-Origine": "s" * 29 + "x"}).status_code == 403
assert cl.get("/connexion", headers=B).status_code == 200                     # par Cloudflare : ok
assert cl.get("/sante/cloudflare").get_data(as_text=True) == "non"
assert cl.get("/sante/cloudflare", headers=B).get_data(as_text=True) == "oui"
with server.app.test_request_context("/", headers={**B, "CF-Connecting-IP": "203.0.113.9", "X-Forwarded-For": "1.1.1.1, 172.64.0.1"}):
    assert server._ip() == "203.0.113.9"
with server.app.test_request_context("/", headers={"CF-Connecting-IP": "203.0.113.9", "X-Forwarded-For": "1.1.1.1, 172.64.0.1"}):
    assert server._ip() == "172.64.0.1"                                       # sans le secret : CF-Connecting-IP ignore (falsifiable)
print("OK test_pare_feu")
