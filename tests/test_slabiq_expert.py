"""16 nov 2026 (Mathieu : « SlabIQ doit proposer ce qu'un expert aurait achete : flip ou garder ») : les jugements, l'accord
de SlabIQ avec l'expert, et la boucle qui ne change un reglage que s'il fait mieux sur les jugements recents ; la raison d'une
note (long terme pour la grosse carte d'un evergreen)."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import slabiq_expert as se, score_slab

# 1. les jugements et l'accord
assert se.noter("1", "Carte A", "flip", score=90)
assert se.noter("2", "Carte B", "garder", score=84)
assert se.noter("3", "Carte C", "passe", score=40)
assert se.noter("4", "Carte D", "passe", score=88)          # SlabIQ dit oui, l'expert non
assert se.noter("5", "Carte E", "garder", score=60)         # l'expert achete, SlabIQ non
assert se.noter("x", "", "flip") is None and se.noter("y", "T", "peut-etre") is None
assert se.noter("4", "Carte D", "flip", score=88)           # un 2e jugement remplace le 1er
m = se.mesure()
assert m["n"] == 5 and m["flip"] == 2 and m["garder"] == 2, m
t = m["total"]
assert t["accord"] == 0.8 and t["precision"] == 1.0 and t["rappel"] == 0.75, t
assert se.faits() == {"1", "2", "3", "4", "5"}

# 2. la boucle : pas assez de jugements -> rien ne change
e = se.iterer()
assert "pas assez" in e.get("note", "") and se.params() == {}, e

# 3. la boucle : un reglage n'est adopte que s'il bat celui en place sur les jugements RECENTS
import types
calls = []
def faux_score(titre, joueur=None):
    p = score_slab.parametres()
    pe = p.get("plancher_evergreen")
    base = 60 if "evergreen" in titre else 30
    return {"score": max(base, pe) if (pe and "evergreen" in titre) else base}
score_slab.score = faux_score
d = se.lire(); d["etiquettes"] = []
for i in range(80):
    d["etiquettes"].append({"item_id": str(i), "titre": f"carte evergreen {i}", "choix": "garder", "score": 60, "le": f"2026-11-{1 + i % 28:02d}T00:{i:02d}"})
d["params"] = {"plancher_evergreen": None}
se.ecrire(d)
e = se.iterer()
assert e.get("adopte") and se.params()["plancher_evergreen"] in (80, 85), e   # l'expert garde ces cartes : le plancher A- aide
print("SLABIQ EXPERT OK", t, e["accord_en_place"], "->", e["accord_challenger"])
