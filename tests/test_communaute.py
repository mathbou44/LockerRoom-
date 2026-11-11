"""11 nov 2026 (Mathieu : « ce que nos utilisateurs regardent, suivent, ajoutent ») : les signaux de la communaute, par jour
et par joueur, sans rien qui relie un compte."""
import os, sys, tempfile, json
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import communaute
communaute.noter("connor bedard", "fiche", compte="a@x.com")
communaute.noter("Connor Bedard", "watch", compte="b@x.com")
communaute.noter_titre("2023-24 Upper Deck Young Guns Connor Bedard #201 PSA 10", "annonce", compte="a@x.com")
communaute.noter("X", "fiche")                          # pas un nom : ignore
communaute.noter("Lane Hutson", "pirate")              # pas une sorte connue : ignore
communaute.ecrire()
d = communaute.lire()["jours"]
jour = list(d)[0]
e = d[jour]["Connor Bedard"]
assert e["fiche"] == 1 and e["watch"] == 1 and e["annonce"] == 1 and e["comptes"] == 2, e
brut = open(os.path.join(comptes.DONNEES, "communaute.json")).read()
assert "a@x.com" not in brut and "b@x.com" not in brut                  # aucun compte en clair
assert set(d[jour]) == {"Connor Bedard"}, d[jour]
p = communaute.par_joueur(30)
assert p["Connor Bedard"][0] > 0 and p["Connor Bedard"][0] == p["Connor Bedard"][1]
assert len(communaute.serie("Connor Bedard", jours=10)) == 10
print("COMMUNAUTE OK", e)
