"""24 nov 2026 (Mathieu, capture de Tableau par divisions : une 5e place « Other · Sam Bennett · Connor McDavid » : « c'est quoi,
"other division" lol ? »). Les cartes « Team Canada » (Crosby, McDavid, Bennett, Binnington) n'ont pas d'equipe de la ligue :
elles formaient une place « Autre ». Une carte d'equipe nationale suit maintenant le joueur : la division de SON equipe de
la ligue, lue sur ses autres cartes du meme produit. Et les divisions se disent en anglais dans l'app en anglais."""
import json, os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import calcul, lockerroom
DIV = {"Atlantique", "Centrale", "Métropolitaine", "Pacifique"}
p = json.load(open(os.path.join(RACINE, "catalogue", "2025-26-upper-deck-tableau.json"), encoding="utf-8"))
canada = [c for c in p["cartes"] if c.get("equipe") == "Team Canada"]
assert len(canada) >= 8 and {c["joueur"] for c in canada} >= {"Connor McDavid", "Sam Bennett", "Sidney Crosby"}
# 1. l'equipe de la ligue de chaque joueur, lue sur ses autres cartes du produit
lg = calcul.equipes_ligue(p["cartes"], "hockey")
assert (lg["Connor McDavid"], lg["Sam Bennett"], lg["Sidney Crosby"]) == ("EDM", "FLA", "PIT"), lg.get("Connor McDavid")
assert "Team Canada" not in lg.values() and all(calcul.division(e, "hockey") in DIV for e in lg.values())
# 2. la division d'une carte
c = {"joueur": "Connor McDavid", "equipe": "Team Canada"}
assert calcul.divisions_carte(c, ["Team Canada"], "hockey", lg) == ["Pacifique"]
assert calcul.divisions_carte({"joueur": "Sam Bennett"}, ["Team Canada"], "hockey", lg) == ["Atlantique"]
assert calcul.divisions_carte({"joueur": "Connor McDavid / Sam Bennett"}, ["Team Canada"], "hockey", lg) == ["Atlantique", "Pacifique"]   # deux joueurs : moitie chacun
assert calcul.divisions_carte({"joueur": "Un Inconnu"}, ["Team Canada"], "hockey", lg) == ["Autre"]      # aucun indice : rien n'est devine
assert calcul.divisions_carte(c, ["EDM"], "hockey", lg) == ["Pacifique"] and calcul.divisions_carte(c, ["EDM", "TOR"], "hockey", lg) == ["Atlantique", "Pacifique"]
assert calcul.divisions_carte(c, ["Team Canada"], "hockey", None) == ["Autre"]                           # sans la liste : comme avant
# 3. Tableau par divisions : quatre places, plus de « Autre » ; McDavid compte dans le Pacifique
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
arg = {"produit_id": "2025-26-upper-deck-tableau", "boites": 6, "mode": "divisions", "cout_boite": 1650, "marge": 20, "decote": 0,
       "plancher": 5, "prix_demandes": {}, "prix_joueurs": {}, "acheteur": False}
r = api.analyse_break(arg)
cles = [x["cle"] for x in r["places"]]
assert r["ok"] and set(cles) == DIV and "Autre" not in cles, cles
# la valeur des cartes de Team Canada n'a pas disparu : elle est dans les divisions (le total des places ne baisse pas)
tot = sum(x["prix"] for x in r["places"])
assert tot > 0 and abs(tot - sum(x["prix"] for x in api.analyse_break(arg)["places"])) < 0.01
# par equipes : toujours 32 places, aucune « Team Canada » (4 nov) ; la carte nationale de McDavid compte maintenant pour les
# Oilers (avant : sa valeur n'allait a personne)
re_ = api.analyse_break(dict(arg, mode="equipes"))
assert len(re_["places"]) == 32 and not any("Canada" in str(x["cle"]) for x in re_["places"])
assert calcul.equipes_carte(c, ["Team Canada"], "hockey", lg) == ["EDM"] and calcul.equipes_carte(c, ["Team Canada"], "hockey", None) == ["Team Canada"]
assert calcul.equipes_carte({"joueur": "A"}, ["Hartford Whalers"], "hockey", {"A": "CAR"}) == ["Hartford Whalers"]     # une ancienne equipe reste elle-meme
# 4. une liste maison (prix_places) : meme regle
maison = [{"joueur": "A", "equipe": "EDM", "groupe": "base"}, {"joueur": "A", "equipe": "Team Canada", "groupe": "auto"},
          {"joueur": "B", "equipe": "TOR", "groupe": "base"}, {"joueur": "Z", "equipe": "Team Canada", "groupe": "auto"}]
pp = calcul.prix_places(maison, boites=1, cout_boite=100, mode="divisions", sport="hockey")
noms = {x["cle"] for x in pp["places"]}
assert noms == {"Pacifique", "Atlantique", "Autre"}, noms                        # Z n'a aucune carte de la ligue : « Autre » reste pour lui
# 5. une carte tiree pendant le break trouve sa place
places = [{"cle": d} for d in sorted(DIV)]
f = api._place_de_equipe
assert f(places, "divisions", "Team Canada", "Connor McDavid", "hockey", lg)["cle"] == "Pacifique"
assert f([{"cle": "EDM"}, {"cle": "TOR"}], "equipes", "Team Canada", "Connor McDavid", "hockey", lg)["cle"] == "EDM"
assert f(places, "divisions", "Team Canada", "Connor McDavid", "hockey") is None and f(places, "divisions", "EDM", "X", "hockey")["cle"] == "Pacifique"
# 6. en anglais : Pacific, Metropolitan, Atlantic, Central
en = json.load(open(os.path.join(RACINE, "i18n", "en_09.json"), encoding="utf-8"))
assert (en["Pacifique"], en["Métropolitaine"], en["Atlantique"], en["Centrale"]) == ("Pacific", "Metropolitan", "Atlantic", "Central")
print("OK test_divisions_nationales")
