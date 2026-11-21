"""21 nov 2026 (vitesse) : les Scores SlabIQ de l'inventaire sont gardes sur le disque du compte ; apres un redemarrage rien
n'est recalcule ; une carte ajoutee : seulement elle ; un seul calcul a la fois ; le recalcul du jour se fait en fond."""
import json, os, sys, tempfile, threading, time
d = tempfile.mkdtemp(); os.environ["LOCKERROOM_DONNEES"] = d
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lockerroom, score_modele
api = lockerroom.Api()
for t, j in [("2024-25 Upper Deck Young Guns Macklin Celebrini #451 RC", "Macklin Celebrini"), ("2015-16 Upper Deck Young Guns Connor McDavid #201 PSA 10", "Connor McDavid"),
             ("2023-24 Upper Deck Connor Bedard Young Guns #451", "Connor Bedard")]:
    api.carte_sauver({"titre": t, "joueur": j, "statut": "En stock"})
vrai = score_modele.scores
appels = []
def espion(titres, joueurs=None):
    appels.append(list(titres)); return vrai(titres, joueurs)
score_modele.scores = espion
try:
    r1 = api.inventaire_scores()
    if not r1["scores"]:
        print("OK test_inv_scores_disque (pas de modele ici : rien a verifier)"); sys.exit(0)
    assert len(appels) == 1 and len(appels[0]) == 3, appels
    ch = api._inv_sc_chemin(); assert os.path.exists(ch), ch
    f = json.load(open(ch)); assert len(f["cartes"]) == 3 and f["empreinte"] == str(score_modele._M.get("empreinte", 0.0))
    assert api.inventaire_scores() is r1 and len(appels) == 1                      # en memoire : rien
    lockerroom.Api._INV_SCORES.clear()                                              # comme apres un redemarrage
    r2 = api.inventaire_scores(); assert r2["scores"] == r1["scores"] and len(appels) == 1, "le disque suffit : aucun calcul"
    api.carte_sauver({"titre": "2005-06 The Cup Sidney Crosby Rookie Patch Auto /99", "joueur": "Sidney Crosby", "statut": "En stock"})
    r3 = api.inventaire_scores(); assert len(appels) == 2 and len(appels[1]) == 1, "une carte ajoutee : seulement elle"
    assert all(r3["scores"][k] == v for k, v in r1["scores"].items()) and len(r3["scores"]) >= len(r1["scores"])
    # le meme score qu'un calcul de tout le lot (une carte ne depend pas des autres)
    lockerroom.Api._INV_SCORES.clear(); os.remove(ch); appels.clear()
    r4 = api.inventaire_scores(); assert r4["scores"] == r3["scores"] and len(appels[0]) == 4
    # deux ecrans en meme temps : un seul calcul
    lockerroom.Api._INV_SCORES.clear(); os.remove(ch); appels.clear()
    def lent(titres, joueurs=None):
        appels.append(list(titres)); time.sleep(0.4); return vrai(titres, joueurs)
    score_modele.scores = lent
    res = []
    fils = [threading.Thread(target=lambda: res.append(api.inventaire_scores())) for _ in range(3)]
    [x.start() for x in fils]; [x.join() for x in fils]
    assert len(appels) == 1 and all(x["scores"] == r4["scores"] for x in res), len(appels)
    # un fichier d'hier : servi tout de suite, refait en fond avec la date du jour
    score_modele.scores = espion
    f = json.load(open(ch)); f["jour"] = "2000-01-01"; k0 = next(iter(f["cartes"])); f["cartes"][k0][1] = 1; json.dump(f, open(ch, "w"))
    lockerroom.Api._INV_SCORES.clear(); appels.clear()
    r5 = api.inventaire_scores(); assert r5["scores"][k0] == 1, "le score d'hier est servi sans attendre"
    for _ in range(100):
        if json.load(open(ch)).get("jour") != "2000-01-01" and not lockerroom.Api._INV_SC_FOND: break
        time.sleep(0.1)
    f2 = json.load(open(ch)); assert f2["jour"] == time.strftime("%Y-%m-%d") and f2["cartes"][k0][1] == r4["scores"][k0], f2["jour"]
    assert api.inventaire_scores()["scores"] == r4["scores"]
    # un autre modele (empreinte) : le fichier ne sert plus
    f2["empreinte"] = "autre"; json.dump(f2, open(ch, "w")); lockerroom.Api._INV_SCORES.clear(); appels.clear()
    api.inventaire_scores(); assert len(appels) == 1 and len(appels[0]) == 4
finally:
    score_modele.scores = vrai
print("OK test_inv_scores_disque")
