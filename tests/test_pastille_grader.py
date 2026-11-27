"""27 nov 2026, 11 h 24 (Mathieu : « dans notre tableau trend ou si on a une pastille dans Radar, il faut vraiment, mais vraiment
que ce soit tres, tres simple pour le end user de comprendre rapidement qu'est-ce qui est a grader ou non. On peut meme mettre
cette pastille-la dans les cartes en inventaire, pas encore sur eBay »). UNE pastille « A grader » : elle y est ou elle n'y est
pas ; la meme regle au Radar, dans l'inventaire, dans les Tendances et dans la fiche « Grader ? ».
Mesure sur la liste du 27 nov (fichier PSA de 12 mois + nos archives) : 207 cartes sur 495 ; sur 6 000 vrais titres de
ventes : 582 recoivent la pastille, 0 titre gradee, 0,5 ms par titre (6 microsecondes ensuite).   python tests/test_pastille_grader.py"""
import json, os, re, subprocess, sys, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import a_grader as ag

# ---- 1. la regle (une seule)
v = ag.vaut_grader
assert v({"reste10": 500, "seuil": 0.0}) and v({"reste10": 40, "seuil": 0.25})
assert not v({"reste10": 39.9, "seuil": 0.0}), "moins de 40 $ si elle revient 10 : pas la peine"
assert not v({"reste10": 900, "seuil": 0.26}), "il faut plus de 1 dix sur 4 : trop risque"
assert v({"reste10": 100, "seuil": None, "psa9": None, "rendement": 3.0}) and not v({"reste10": 100, "seuil": None, "psa9": None, "rendement": 2.99})
assert not v({"reste10": 100, "seuil": None, "psa9": 80.0, "rendement": 9}), "PSA 9 connue mais pas de seuil (perd meme en 10) : non"
assert not v({}) and not v({"reste10": "x"})

# ---- 2. la liste dit quelles cartes portent la pastille, et l'index les garde toutes (pas seulement les 200 premieres)
from datetime import datetime, timedelta, timezone
AUJ = datetime.now(timezone.utc).date()
jr = lambda k: (AUJ - timedelta(days=k)).isoformat()
L, n = [], 0
def ventes(titre, prix, nb):
    global n
    for i in range(nb):
        n += 1; L.append((f"v{n}", titre, prix * (1 + (i % 3 - 1) * 0.03), jr(3 + 5 * i), None))
YG = "2024-25 Upper Deck Cutter Gauthier Young Guns #212"
ventes(YG + " RC", 20, 8); ventes(YG + " PSA 10 GEM MINT", 200, 6); ventes(YG + " PSA 9 MINT", 60, 4)        # bonne : seuil 0
Z = "2024-25 Upper Deck Logan Stankoven Young Guns #244"
ventes(Z + " RC", 30, 8); ventes(Z + " PSA 10", 70, 6); ventes(Z + " PSA 9", 25, 4)                            # 10 : +19 $ : non
R = ag.analyser(L)
par = {x["joueur"]: x for x in R["cartes"]}
assert par["Cutter Gauthier"]["grader"] is True and par["Logan Stankoven"]["grader"] is False, {k: (x["reste10"], x["seuil"]) for k, x in par.items()}
assert R["n_grader"] == 1 and len(R["index"]) == 2 and {e["ok"] for e in R["index"]} == {True, False}
with open(ag._chemin(), "w", encoding="utf-8") as f:
    json.dump({**R, "version": ag.VERSION}, f)

# ---- 3. un titre -> sa pastille : jamais au hasard
p = ag.pastille
e = p("2024-25 Upper Deck Series 1 Young Guns Cutter Gauthier #212 Ducks RC")
assert e and e["joueur"] == "Cutter Gauthier" and e["ok"] and e["r"] == par["Cutter Gauthier"]["rendement"], e
assert p("Upper Deck Young Guns Cutter Gauthier rookie #212"), "sans saison : une seule carte de cette sorte pour ce joueur"
for t in (YG + " PSA 10", YG + " BGS 9.5", YG + " SGC 10 graded",                       # gradee : jamais
          "2023-24 Upper Deck Cutter Gauthier Young Guns #212",                         # une autre saison
          "2024-25 Upper Deck Cutter Gauthier Young Guns Canvas #C212",                 # une autre sorte
          "2024-25 Upper Deck Cutter Gauthier Young Guns #999",                         # un autre numero
          "2024-25 Upper Deck Cutter Gauthier Young Guns Exclusives /100 #212",         # un autre tirage
          "2024-25 Upper Deck Macklin Celebrini Young Guns #451",                       # un autre joueur
          "Cutter Gauthier + Logan Stankoven Young Guns lot", "", None, "abc"):
    assert p(t) is None, t
assert ag.mesure(Z + " RC") and ag.mesure(Z + " RC")["ok"] is False and p(Z + " RC") is None, "mesuree sans pastille"
# ce que l'app recoit : les prix seulement pour l'admin
c = ag.pour_client(e)
assert set(c) == {"r", "s", "jours", "nom", "joueur", "an"} and ag.pour_client(e, prix=True)["g10"] == e["g10"] and ag.pour_client(None) is None
# une liste d'avant la pastille (sans index) : la regle est appliquee a la lecture
anc = {k: v_ for k, v_ in R.items() if k not in ("index", "n_grader")}
for x in anc["cartes"]:
    x.pop("grader")
with open(ag._chemin(), "w", encoding="utf-8") as f:
    json.dump(anc, f)
t_ = __import__("time").time() + 3; os.utime(ag._chemin(), (t_, t_))
assert p(YG + " RC") and p(Z + " RC") is None
T = ag.top_tendances()
assert [x["joueur"] for x in T["cartes"]] == ["Cutter Gauthier"] and T["n_grader"] == 1, "l'onglet ne montre que les cartes a la pastille"

# ---- 4. le serveur : admin seulement, a cote des annonces, jamais sur une carte gradee / sur eBay / vendue / en envoi
src = open(os.path.join(RACINE, "lockerroom.py"), encoding="utf-8").read()
i = src.index("    def _a_grader_de(self"); f_ = src[i:src.index("    def deals_liste(self", i)]
assert "if not self._est_admin():\n                return {}" in f_ and "a_grader.pour_client(e, prix=True)" in f_
assert '"a_grader": self._a_grader_de([*lst[:240], *suivis, *pres])' in src
i = src.index("# 27 nov 2026 (Mathieu : « on peut meme mettre cette pastille-la dans les cartes en inventaire"); f_ = src[i:i + 1600]
for bout in ("if self._est_admin():", 'r.get("statut") in ("Vendue", "Listée")', 'r.get("item_number")', 'str(r.get("grade") or "").strip()', 'r.get("envoi_json")', 'r.get("soumission_id")'):
    assert bout in f_, bout
i = src.index("    def carte_grader(self"); f_ = src[i:i + 2600]
assert f_.index("if not comps_permis(self):") < f_.index("a_grader.mesure(titre)") < f_.index("vendues.par_gradation"), "la fiche dit la meme chose que la pastille"
assert '"verdict": "oui" if e.get("ok") else "non"' in f_

# ---- 5. l'app : la phrase (vraie fonction, node) ; un toucher n'ouvre pas la fiche
app = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
m = re.search(r"function agTexte\(a\)\{.*?\n\}\n", app, re.S)
JS = "const tt = (a) => a; const decFr = (x) => String(x).replace('.', ','); const argent = (x) => Math.round(x) + ' $';\n" + m.group(0) + """
console.log(JSON.stringify([agTexte({r: 4.6, s: 0, g10: 2032}), agTexte({r: 2.7, s: 0.12, g10: 59}), agTexte({r: 3.4, s: null, g10: 120}), agTexte({r: 2.5, s: 0.25})]));"""
r = json.loads(subprocess.run(["node", "-e", JS], capture_output=True, text=True, check=True).stdout)
assert r[0] == "Si elle revient PSA 10 : +2032 $ de profit. Même un 9 ne te fait pas perdre. Seulement si elle est belle.", r[0]
assert "Il suffit de 1 dix sur 8 pour ne pas perdre." in r[1] and "Le prix de la PSA 9 n’est pas mesuré." in r[2] and "2,5 fois ta mise" in r[3] and "1 dix sur 4" in r[3], r
for bout in ("[data-sc], [data-cu], [data-se], [data-td], [data-np], [data-agp], .w-go, .x')) return;", "e.target.closest('[data-np],[data-cu],[data-se],[data-agp]'))) fermerNotif(); }, true);",
             "S.agParId = d.a_grader || {};", "ag = agBadge(agDe(x));", "${c.ag && !vendue ? `<span class=\"isl-ag\">${agBadge(c.ag)}</span>` : ''}", "${c.ag && !env ? `<span class=\"sl-ag\">${agBadge(c.ag)}</span>` : ''}",
             "e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); vibrer();", ".sd-b.b-ag{color:#06210F; background:#30D158"):
    assert bout in app, bout
assert "r.source === 'liste'" in app and "agTexte({r: r.rendement, s: r.seuil_10, g10: r.gain})" in app
print("PASTILLE A GRADER OK")
