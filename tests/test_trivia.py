"""20 nov 2026 : le trivia du hobby (Admin, a l'essai). Chaque question a 4 choix differents et une seule bonne reponse ;
les questions de checklist disent vrai (le tirage vient du sous-ensemble nomme) ; la serie de jours ; refuse hors admin."""
import os, sys, tempfile, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta
import trivia, catalogue
for d in range(10):
    j = date(2026, 11, 20) + timedelta(days=d)
    for lg in ("fr", "en"):
        L = trivia.jour(lg, "hockey", j)
        assert 3 <= len(L) <= 5, len(L)
        for q in L:
            assert len(q["choix"]) == 4 and len(set(q["choix"])) == 4 and 0 <= q["bonne"] < 4, q
assert trivia.jour("fr", quand=date(2026, 11, 20)) == trivia.jour("fr", quand=date(2026, 11, 20))       # la meme pour tous
assert trivia.jour("fr", quand=date(2026, 11, 20)) != trivia.jour("fr", quand=date(2026, 11, 21))
# les tirages : vrais selon la checklist
P = trivia.pool_semaine("hockey", date(2026, 11, 20))
prods = {p["nom"]: catalogue.charger(p["id"]) for p in catalogue.liste()}
n = 0
for q in P:
    m = re.match(r"Dans (.+?), « (.+) » est numéroté à…", q["fr"])
    if m:
        se = [s for s in prods[m.group(1)]["sous_ensembles"] if s["nom"] == m.group(2)]
        t = se[0]["tirage"]
        assert q["bonne"][0] == ("1/1" if t == 1 else f"/{t}"), (q, t)
        n += 1
assert n >= 3
# la serie
e = trivia.noter({}, 4, 5, date(2026, 11, 20)); assert e["serie"] == 1
e = trivia.noter(e, 5, 5, date(2026, 11, 20)); assert e["parties"] == 1          # une partie comptee par jour
e = trivia.noter(e, 3, 5, date(2026, 11, 21)); assert e["serie"] == 2 and e["meilleure_serie"] == 2
e = trivia.noter(e, 3, 5, date(2026, 11, 23)); assert e["serie"] == 1 and e["meilleure_serie"] == 2
# l'API : l'admin seulement
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom
a = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
r = a.trivia_jour("hockey", "fr")
assert r["ok"] and r["questions"], r                     # le PC (pas de comptes) = admin
a._est_admin = lambda *x, **k: False
assert not a.trivia_jour("hockey")["ok"] and not a.trivia_fini(3, 5)["ok"]
print("OK test_trivia")
