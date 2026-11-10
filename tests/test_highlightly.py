"""10 nov 2026 (Mathieu : « teste le tout et assure-toi que c'est securitaire ») : l'adaptateur Highlightly."""
import io
import json
import os
import sys
import tempfile
import urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import highlightly as h

CLE = "cle-secrete-ABCD"
assert not h.actif() and h.test()["erreur"].startswith("HIGHLIGHTLY_CLE")          # sans cle : inactif, aucun appel
os.environ["HIGHLIGHTLY_CLE"] = CLE
vus = []


class Rep(io.BytesIO):
    def __init__(self, corps, ct="application/json", entetes=None):
        super().__init__(corps)
        self.headers = {"Content-Type": ct, **(entetes or {})}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


JOUEURS = {"data": [{"id": 58504952, "fullName": "Connor McDavid", "logo": "https://x/img.png"}, {"id": "pas un nombre", "fullName": "X"}],
           "pagination": {"totalCount": 1, "offset": 0, "limit": 20}, "plan": {"tier": "BASIC"}}
STATS = [{"id": 58504952, "fullName": "Connor McDavid", "logo": "https://x/l.png", "perSeason": [
    {"stats": [{"name": "Total Points", "value": 132, "category": "Offense"}, {"name": "<b>Goals</b>", "value": "64", "category": "Offense"},
               {"name": "Bidon", "value": {"a": 1}, "category": "General"}],
     "teams": [{"id": 22, "logo": "https://x/t.png", "name": "Oilers", "league": "NHL", "displayName": "Edmonton Oilers", "abbreviation": "EDM"}],
     "league": "Nhl", "season": 2023, "seasonBreakdown": "Entire"},
    {"stats": [{"name": "Total Points", "value": 40, "category": "Offense"}], "teams": [], "league": "OHL", "season": 2014, "seasonBreakdown": "Season"}]}]
mode = {"m": "ok"}


def ouvrir(req, timeout=None):
    vus.append(req)
    assert req.full_url.startswith("https://") and ".highlightly.net/" in req.full_url
    assert CLE not in req.full_url                                       # jamais la cle dans l'adresse
    assert req.get_header("X-rapidapi-key") == CLE
    assert timeout and timeout <= 15
    if mode["m"] == "401":
        raise urllib.error.HTTPError(req.full_url, 401, "cle " + CLE + " refusee", {}, None)
    if mode["m"] == "html":
        return Rep(b"<html>pub</html>", "text/html")
    if mode["m"] == "gros":
        return Rep(b"[" + b"1," * (2 * 1024 * 1024) + b"1]")
    if req.full_url.startswith("https://sports.highlightly.net/") and mode["m"] == "ligue":
        raise urllib.error.HTTPError(req.full_url, 403, "abonnement ligue", {}, None)
    corps = STATS if "/statistics" in req.full_url else JOUEURS
    return Rep(json.dumps(corps).encode(), entetes={"x-ratelimit-requests-remaining": "97", "x-ratelimit-requests-limit": "100"})


h._OUVREUR.open = ouvrir

# 1. un essai complet : le joueur, ses saisons (LNH et OHL), sans logos, sans HTML, types verifies
r = h.test()
assert r["ok"] and r["cle"] == "…ABCD" and CLE not in json.dumps(r), r
assert r["ligues"] == ["Nhl", "OHL"] and r["saisons"] == 2 and r["restant"] == 97, r
s = h.stats(58504952)
assert s["saisons"][0]["stats"] == {"Total Points": 132, "Goals": 64.0}, s                 # HTML retire, valeur bizarre jetee
assert "logo" not in json.dumps(s) and "https://x/" not in json.dumps(s)
assert h.chercher("Connor McDavid") == [{"id": 58504952, "nom": "Connor McDavid"}]
print("OK highlightly essai")

# 2. le cache : la meme question ne coute rien
n = len(vus)
h.stats_joueur("Connor McDavid")
assert len(vus) == n
print("OK highlightly cache")

# 3. une cle refusee : l'erreur ne contient jamais la cle
mode["m"] = "401"
h._ETAT["base"].clear()
assert h.chercher("Sidney Crosby") == []
assert CLE not in json.dumps(h.statut()) and CLE not in json.dumps(h._ETAT, default=str)
# 4. une reponse qui n'est pas du JSON, ou trop grosse : refusee
for m in ("html", "gros"):
    mode["m"] = m
    h._PANNE[:] = [0.0, 0]
    assert h.chercher("Nathan MacKinnon " + m) == []
print("OK highlightly erreurs")

# 5. abonnement d'une ligue (pas « tous les sports ») : l'autre adresse est essayee, puis retenue
mode["m"] = "ligue"
h._ETAT["base"].clear()
h._PANNE[:] = [0.0, 0]
assert h.chercher("Cale Makar")
assert h._ETAT["base"]["nhl"] == "https://nhl.highlightly.net"

# 6. une redirection vers un autre site est refusee (la cle n'y part pas)
import urllib.request
red = h._PasDeRedirection()
try:
    red.redirect_request(urllib.request.Request("https://nhl.highlightly.net/players"), None, 302, "x", {}, "https://mechant.example/")
    raise AssertionError("redirection acceptee")
except urllib.error.HTTPError:
    pass
assert not h.HOTE_OK.match("https://highlightly.net.mechant.example/x") and not h.HOTE_OK.match("http://nhl.highlightly.net/x")

# 7. le plafond du jour a nous
os.environ["LR_HIGHLIGHTLY_JOUR"] = "1"
mode["m"] = "ok"
assert h._appel("/players", {"name": "x"})[1] == "plafond du jour"
print("OK highlightly securite")
