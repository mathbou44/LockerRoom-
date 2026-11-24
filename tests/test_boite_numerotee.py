"""24 nov 2026 (Mathieu, capture de Splendor en vue Pro : un crochet vert sur la tuile, puis « This product's pull odds aren't
known yet » : « ?? »). Splendor : 1 carte par boite, aucune cote publiee (« Random Inserts »), mais chaque carte est
NUMEROTEE. Les tirages imprimes donnent les chances : la part d'un sous-ensemble = ses exemplaires / tous les exemplaires,
fois les cartes de la boite. La regle ne joue que si AUCUNE cote n'est publiee et que 90 % des sous-ensembles sont numerotes."""
import copy, glob, json, os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import catalogue, lockerroom
lire = lambda i: json.load(open(os.path.join(RACINE, "catalogue", i + ".json"), encoding="utf-8"))

# 1. Splendor : chaque sous-ensemble a une cote, leur somme = la carte de la boite, au prorata des tirages
p = lire("2025-26-upper-deck-splendor")
assert not any(s.get("par_boite") for s in p["sous_ensembles"])                  # aucune cote publiee
t = catalogue.taux_par_boite(p)
assert p.get("_boite_numerotee") and len(t) == len(p["sous_ensembles"]) == 96, len(t)
assert abs(sum(t.values()) - 1.0) < 0.001, sum(t.values())                       # 1 carte par boite
se = {s["nom"]: s for s in p["sous_ensembles"]}
ex = lambda n: catalogue._exemplaires(p, se, n)
a, b = "Borderless Base", "Borderless Base Gold Parallel"
assert abs(t[a] / t[b] - ex(a) / ex(b)) < 0.01 and t[a] > t[b] > 0               # /36 sort plus souvent que /5, au prorata
assert set(p["_estimees"]) == set(t)                                             # dites « estimees » a l'admin
e = catalogue.etat_cotes(p)
assert e["complete"] and not e["manquantes"] and not e["non_publiees"] and len(e["estimees"]) == 96
# 2. l'ecran « J'achete une place » a maintenant de quoi classer : des joueurs, et des chances qui se tiennent
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "a.db"))
r = api.analyse_break({"produit_id": "2025-26-upper-deck-splendor", "boites": 1, "mode": "equipes", "cout_boite": 0, "marge": "",
                       "decote": 0, "prix_demandes": {}, "prix_joueurs": {}, "acheteur": True})
J = r.get("joueurs") or []
hit = lambda x: ((x.get("chances") or {}).get("hit") or {}).get("p") or 0
assert r["ok"] and len(J) >= 150 and len(r.get("places") or []) >= 30, (len(J), len(r.get("places") or []))
assert 0.90 <= sum(hit(x) for x in J) <= 1.10, sum(hit(x) for x in J)            # 1 carte par boite : les chances font ~1
assert 0.005 < max(hit(x) for x in J) < 0.10                                     # personne n'a une chance folle
r6 = api.analyse_break({"produit_id": "2025-26-upper-deck-splendor", "boites": 6, "mode": "equipes", "cout_boite": 0, "marge": "",
                        "decote": 0, "prix_demandes": {}, "prix_joueurs": {}, "acheteur": True})
m1, m6 = max(J, key=hit), None
m6 = next(x for x in r6["joueurs"] if x["cle"] == m1["cle"])
assert hit(m1) < hit(m6) < 6 * hit(m1) + 1e-9                                    # une caisse : plus de chances, jamais plus que 6 fois
# 3. la regle ne touche AUCUN autre produit du catalogue (ils ont tous au moins une cote publiee)
for f in sorted(glob.glob(os.path.join(RACINE, "catalogue", "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    if not isinstance(d, dict) or not d.get("sous_ensembles") or d["id"] == p["id"]:
        continue
    catalogue.taux_par_boite(d)
    assert not d.get("_boite_numerotee"), d["id"]
L = catalogue.liste()
assert L and all(x.get("sans_cotes") is False for x in L), [x["id"] for x in L if x.get("sans_cotes") is not False]
assert next(x for x in L if x["id"] == p["id"])["cotes_estimees"] == 96
# 4. les garde-fous, sur des copies : une cote publiee -> la regle se tait ; trop peu de tirages -> aucune cote inventee
q = copy.deepcopy(lire("2025-26-upper-deck-splendor"))
q["sous_ensembles"][0]["par_boite"] = 0.05
tq = catalogue.taux_par_boite(q)
assert not q.get("_boite_numerotee") and len(tq) < 10, len(tq)
q = copy.deepcopy(lire("2025-26-upper-deck-splendor"))
for s in q["sous_ensembles"][:20]:
    s["tirage"] = None
for c in q["cartes"]:
    c["tirage"] = None
tq = catalogue.taux_par_boite(q)
assert not q.get("_boite_numerotee") and not tq, len(tq)                         # 20 sur 96 sans tirage : rien n'est devine
# un seul sous-ensemble sans tirage : il ne recoit aucune cote, mais il compte dans le total (les autres ne gonflent pas)
q = copy.deepcopy(lire("2025-26-upper-deck-splendor"))
nom0 = q["sous_ensembles"][0]["nom"]
q["sous_ensembles"][0]["tirage"] = None
for c in q["cartes"]:
    if c.get("sous_ensemble") == nom0:
        c["tirage"] = None
tq = catalogue.taux_par_boite(q)
assert q.get("_boite_numerotee") and nom0 not in tq and len(tq) == 95 and 0.90 < sum(tq.values()) < 1.0, (len(tq), sum(tq.values()))
# sans format de boite : rien
q = copy.deepcopy(lire("2025-26-upper-deck-splendor"))
q["formats"] = []
assert not catalogue.taux_par_boite(q)
# 5. l'ecran : un produit sans aucune cote ne porte plus le crochet vert
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert "p.sans_cotes ? `<span class=\"ck-manq\">${capsule(tt('Cotes à venir', 'Odds coming'), 'or petit')}</span>`" in src
print("OK test_boite_numerotee")
