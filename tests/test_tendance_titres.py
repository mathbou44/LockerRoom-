"""26 nov 2026, 21 h 26 (Mathieu, capture de l'onglet Cartes des Tendances : « juste des Young Guns, ca fait boboche, on dirait qu'on
bug ou on est incomplet » ; « oui go » le 27 nov). Les cartes sont aussi lues dans le TITRE de chaque vente (a_grader.classer), pas
seulement par la recherche qui l'a ramenee : la Future Watch Auto /999 d'un joueur, vendue sous « <joueur> hockey », est mesuree."""
import os, sys, tempfile
from datetime import datetime, timedelta
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import base_ventes, tendance_sortes as ts
AUJ = datetime.now()
jr = lambda k: (AUJ - timedelta(days=k)).strftime("%Y-%m-%d")
assert ts.CARTES_MIN == 3 and ts.TITRES_PRIX_MIN == 12.0
n = [0]
def ventes(titre, avant, recent, k_av=8, k_re=8):
    out = []
    for i in range(k_av):
        n[0] += 1; out.append({"titre": titre, "prix": float(avant + (i % 3)), "le": jr(35 + 6 * i), "url": f"https://www.ebay.com/itm/5000{n[0]:08d}"})
    for i in range(k_re):
        n[0] += 1; out.append({"titre": titre, "prix": float(recent + (i % 3)), "le": jr(2 + 3 * i), "url": f"https://www.ebay.com/itm/5000{n[0]:08d}"})
    return out
J = ["Connor Bedard", "Macklin Celebrini", "Lane Hutson", "Matvei Michkov"]
# des recherches LARGES (« <joueur> hockey ») : elles ne nomment aucune carte, la mesure d'avant ne les lisait pas
for i, j in enumerate(J):
    base_ventes.noter(j.lower() + " hockey", ventes(f"2024-25 SP Authentic Future Watch Auto {j} /999 RC", 200 + 40 * i, 150 + 30 * i)
                      + ventes(f"2024-25 Upper Deck Young Guns {j} #201 RC", 80, 60)
                      + ventes(f"2024-25 SP Authentic Future Watch Auto {j} /999 RC PSA 10", 600, 610, 6, 6)
                      + ventes(f"2024-25 Upper Deck MVP {j} #12", 2, 2), sport="hockey")                      # 2 $ : sous le prix minimum
# la Young Guns de Bedard a AUSSI sa propre recherche : les titres ne doivent pas l'ajouter une 2e fois
base_ventes.noter("connor bedard young guns", ventes("2024-25 Upper Deck Young Guns Connor Bedard #201 RC", 80, 60), sport="hockey")
T = ts.cartes_des_titres(maint=AUJ)
par = {(c["joueur"], c["q"]): c for c in T}
qs = sorted({c["q"].split(" ", 2)[2] if len(c["q"].split(" ", 2)) > 2 else c["q"] for c in T})
assert any("future watch" in q and "/999" in q and "psa" not in q for q in qs), qs
assert any("future watch" in q and q.endswith("psa 10") for q in qs), qs                  # la gradee a part
assert not any("mvp" in q for q in qs), "une carte a 2 $ n'entre pas"
fw = [c for c in T if "future watch" in c["q"] and "psa" not in c["q"]]
assert len(fw) == 4 and all(len(c["ventes"]) == 16 and c["lu_le"] == jr(2) and c["titres"] for c in fw), [(c["joueur"], len(c["ventes"])) for c in fw]
assert all(len(v) == 4 and v[3] == 2024 for c in fw for v in c["ventes"]), "chaque vente garde sa date, son prix, son numero et sa saison"
# une vente vue par deux recherches n'est comptee qu'une fois
bed = [c for c in T if c["joueur"] == "connor bedard" and "young guns" in c["q"] and "psa" not in c["q"]]
assert len(bed) == 1 and len(bed[0]["ventes"]) == 32, [len(c["ventes"]) for c in bed]   # 16 de chaque recherche (des numeros differents)
# ajouter_titres : seulement ce que les recherches n'ont pas deja
rech = [c for c in base_ventes.cartes_toutes(jours=ts.JOURS_LUS, n_min=4, max_q=20000, detail=True) if (c.get("sport") or "hockey") == "hockey"]
avant = ts.listes(rech, AUJ)
tout = ts.ajouter_titres(rech, T)
plus = [c for c in tout if c.get("titres")]
assert not any(c["joueur"] == "connor bedard" and c["q"].endswith("young guns") for c in plus), "la Young Guns de Bedard a deja sa recherche"
assert sum(1 for c in plus if "future watch" in c["q"] and "psa" not in c["q"]) == 4
apres = ts.listes(tout, AUJ)
assert "future watch" not in " ".join(avant["sortes"]) and any("future watch" in k and "/999" in k for k in apres["sortes"]), (list(avant["sortes"]), list(apres["sortes"]))
k = next(k for k in apres["sortes"] if "future watch" in k and "/999" in k and "psa" not in k)
s = apres["sortes"][k]
assert s["n_cartes"] == 4 and s["sens"] == "baisse" and -35 <= s["pct"] <= -15, s        # 200 -> 150 : environ -25 %
assert apres["n_cartes"] > avant["n_cartes"]
# les cartes deja mesurees par leur recherche ne changent pas
cle = lambda x: (x["joueur"], x["sorte"], x["saison"])
a0 = {cle(x): x["pct"] for x in avant["cartes"].values()} if isinstance(avant["cartes"], dict) else {cle(x): x["pct"] for x in avant["cartes"]}
a1 = {cle(x): x["pct"] for x in apres["cartes"].values()} if isinstance(apres["cartes"], dict) else {cle(x): x["pct"] for x in apres["cartes"]}
assert a0 and all(a1.get(k_) == v for k_, v in a0.items()), "meme pourcentage qu'avant pour les cartes des recherches"
# jamais un prix dans ce qui sort (le public ne voit que des pourcentages)
import json
txt = json.dumps(ts.public(s)).lower()
assert "$" not in txt and not any(m_ in txt for m_ in ('"prix', '"mediane', '"valeur'))
# le calcul complet : les titres s'ajoutent ; s'ils plantent, les recherches seules restent
r = ts.calculer(AUJ)
assert any("future watch" in k_ for k_ in r["sortes"]), list(r["sortes"])
# ce qui se RELIT (des credits) : seulement de vraies recherches, jamais le nom d'une carte lue dans les titres
src = open(os.path.join(RACINE, "tendance_sortes.py"), encoding="utf-8").read()
assert 'r["a_relire"] = a_relire(recherches, maint or datetime.now())' in src
assert not any("future watch" in str(x) for x in (r.get("a_relire") or [])), r.get("a_relire")
vrai = ts.cartes_des_titres
ts.cartes_des_titres = lambda **k_: (_ for _ in ()).throw(RuntimeError("panne"))
try:
    r2 = ts.calculer(AUJ)
    assert "sortes" in r2 and not any("future watch" in k_ for k_ in r2["sortes"])
finally:
    ts.cartes_des_titres = vrai
print("test_tendance_titres OK")
