"""27 nov 2026, 22 h 38 (Mathieu, l'ecran apres un scan : « trop d'info, doit fitter dans une fenetre ; le prix des last comps ; si rien
vendu dans les 3 derniers mois on fonce CompSniper ; encore plus rapide ») : Comp rapide (une recherche, la mediane 90 jours, les
dernieres ventes), la meme recherche jamais faite deux fois en meme temps, les archives ecrites en arriere-plan, la fiche courte de
l'IA, et le verrou des comps ouvert pour Pro le temps de ces deux gestes seulement. Plus : une pastille touchable n'est jamais un
<button> (l'inventaire : « tout fucké »)."""
import os, re, sys, tempfile, threading, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import vendues, historique, base_ventes, vision, lockerroom

jr = lambda k: (datetime.now() - timedelta(days=k)).strftime("%Y-%m-%d")
V = lambda titre, prix, j, i: {"titre": titre, "prix": prix, "le": jr(j), "url": f"https://www.ebay.com/itm/{i}", "photo": "https://i.ebayimg.com/x.jpg"}
T = "2025-26 SP Authentic Limited Auto Material Mikhail Sergachev /100"

# ---------- COMP RAPIDE ----------
vendues._coupe = lambda: False
ventes = [V(T + " auto", 150, 3, 1000000001), V(T + " auto", 130, 20, 1000000002), V(T + " auto", 170, 60, 1000000003),
          V(T + " auto PSA 10", 900, 5, 1000000004),                                   # une autre note : refusee (la carte est brute)
          V("2025-26 SP Authentic Limited Auto Material Nikita Kucherov /100 auto", 400, 4, 1000000005),   # un autre joueur
          V(T + " auto", 90, 200, 1000000006)]                                          # plus de 3 mois : liste, pas la mediane
appels = []
vendues.rechercher = lambda q, fond=True, usage=None, sans_cache=False: (appels.append(q), {"ventes": [dict(v) for v in ventes], "erreur": None, "source": "compsniper"})[1]
r = vendues.comp_rapide(T + " auto")
assert r["ok"] and r["periode"] == "3 mois", r
assert r["n"] == 3 and r["mediane"] == 150.0, r                 # 150, 130, 170 : la mediane des 90 jours
assert [v["prix"] for v in r["ventes"]] == [150, 130, 170, 90], r["ventes"]      # les plus recentes d'abord, la meme carte seulement
assert r["note"] == "Brute" and r["source"] == "compsniper" and len(appels) == 1, (r, appels)
assert all(set(v) == {"prix", "le", "titre", "url", "photo", "offre"} for v in r["ventes"])
# rien en 3 mois, la recherche venait de SoldComps (90 jours) : on fonce CompSniper (un an)
ventes = []
cs = []
historique.actif = lambda: True
historique.rechercher = lambda q, **k: (cs.append(q), ([V(T + " auto", 120, 150, 1000000010), V(T + " auto", 100, 250, 1000000011)], None))[1]
vendues.archives = lambda cib, jours=365, max_=400, ignorer=(): []
vendues.rechercher = lambda q, fond=True, usage=None, sans_cache=False: {"ventes": [], "erreur": None}
r = vendues.comp_rapide(T + " auto")
assert len(cs) == 1 and r["periode"] == "12 mois" and r["mediane"] == 110.0 and r["n"] == 2 and r["source"] == "compsniper", r
assert r["derniere"] == jr(150), r
# rien du tout : aucune mediane inventee
historique.rechercher = lambda q, **k: ([], None)
r = vendues.comp_rapide(T + " auto")
assert r["ok"] and r["mediane"] is None and r["periode"] is None and r["ventes"] == [], r
# une seule vente en 3 mois : la vente, pas de mediane
vendues.rechercher = lambda q, fond=True, usage=None, sans_cache=False: {"ventes": [V(T + " auto", 140, 2, 1000000020)], "erreur": None, "source": "compsniper"}
r = vendues.comp_rapide(T + " auto")
assert r["n"] == 1 and r["mediane"] is None and r["ventes"][0]["prix"] == 140, r
# la note de la carte : une PSA 10 prend les ventes PSA 10
vendues.rechercher = lambda q, fond=True, usage=None, sans_cache=False: {"ventes": [V(T + " auto PSA 10", 900, 5, 1000000030), V(T + " auto PSA 10", 1000, 9, 1000000031), V(T + " auto", 150, 3, 1000000032)], "erreur": None, "source": "compsniper"}
r = vendues.comp_rapide(T + " auto PSA 10")
assert r["note"] == "PSA 10" and r["mediane"] == 950.0 and [v["prix"] for v in r["ventes"]] == [900, 1000], r

# ---------- LE VERROU DES COMPS : OUVERT POUR PRO LE TEMPS DU GESTE ----------
importlib = __import__("importlib")
vendues2 = importlib.reload(vendues)                        # le vrai _coupe (le verrou), et la vraie recherche
os.environ.pop("LR_COMPS_PUBLICS", None)
lockerroom.comps_permis.__globals__["vue_simulee"] = lambda: True     # un compte qui n'est pas admin
assert vendues2._coupe() is True                             # Pro, hors du geste : coupe (rien d'autre ne s'ouvre)
with lockerroom._comp_pro_ouvert():
    assert vendues2._coupe() is False
assert vendues2._coupe() is True

class Faux:
    niveau = "gratuit"
    def _niveau_ag(self): return self.niveau
f = Faux()
assert lockerroom.Api.comp_rapide(f, T) == {"ok": False, "raison": "pro"}
vu = []
vendues2.comp_rapide = lambda q: (vu.append((q, vendues2._coupe())), {"ok": True})[1]
f.niveau = "pro"
assert lockerroom.Api.comp_rapide(f, "  " + T + "  ") == {"ok": True} and vu == [(T, False)], vu
assert lockerroom.Api.comp_rapide(f, "abc") == {"ok": False, "raison": "carte"}
# la mediane 3 mois passe aussi par le verrou ouvert (avant : un compte Pro ne recevait rien)
vg = []
vendues2.par_gradation = lambda q, **k: (vg.append(vendues2._coupe()), {"series": [{"cle": "brute", "nom": "Brute", "points": [[jr(3), 100], [jr(9), 120]]}]})[1]
r = lockerroom.Api.mediane_3mois(f, T)
assert r["ok"] and r["mediane"] == 110 and vg == [False], (r, vg)
f.niveau = "gratuit"
assert lockerroom.Api.mediane_3mois(f, T)["raison"] == "pro"
lockerroom.comps_permis.__globals__.pop("vue_simulee", None)
importlib.reload(lockerroom)

# ---------- LA MEME RECHERCHE, JAMAIS DEUX FOIS EN MEME TEMPS ----------
v3 = importlib.reload(vendues)
v3._coupe = lambda: False
n_appels = []
cache = {}
v3._cache_lire = lambda q, age_max=None: cache.get(q)
def appel(q, fond, usage):
    n_appels.append(q); time.sleep(0.4); cache[q.lower()] = [{"prix": 1}]
    return {"ventes": [{"prix": 1}], "erreur": None}
v3._rechercher_appel = appel
res = []
fils = [threading.Thread(target=lambda: res.append(v3.rechercher("sergachev limited auto", fond=False))) for _ in range(3)]
[t.start() for t in fils]; [t.join() for t in fils]
assert len(n_appels) == 1 and len(res) == 3 and all(x["ventes"] for x in res), (n_appels, res)
assert v3._EN_VOL == {}
# les taches de fond ne s'attendent pas (leur propre rythme)
cache.clear(); n_appels.clear()
v3.rechercher("autre carte", fond=True)
assert n_appels == ["autre carte"]

# ---------- LES ARCHIVES EN ARRIERE-PLAN ----------
ecrit = threading.Event()
vrai = base_ventes.noter
base_ventes.noter = lambda q, v, sport=None: (time.sleep(0.3), ecrit.set())
t0 = time.time()
assert base_ventes.noter_plus_tard("q", [{"prix": 1, "le": jr(1)}]) == 1
assert time.time() - t0 < 0.2                       # la reponse n'attend pas l'ecriture
assert ecrit.wait(3)
assert base_ventes.noter_plus_tard("q", []) == 0
base_ventes.noter = vrai

# ---------- LA FICHE COURTE DE L'IA ----------
props = vision.OUTIL_RAPIDE["input_schema"]["properties"]
assert set(props) == set(vision._CHAMPS_RAPIDES) | {"photos"}, set(props)
assert "confiance" not in props and "titre_ebay" not in props and "coins" not in props["photos"]["items"]["properties"]
assert vision.MAX_SORTIE_RAPIDE < 1500 and "MODE RAPIDE" in vision.SYSTEME_RAPIDE
corps = []
vision.DOSSIER = tempfile.mkdtemp()                 # le cache de l'IA dans un dossier de test (jamais celui du depot)
vision._chemin_cache = lambda: os.path.join(vision.DOSSIER, "vision_cache.json")
vision.disponible = lambda: True
vision._verifier_quotas = lambda: None
vision._limite_compte = lambda: 999
vision._reserver = lambda *a: "r"
vision._liberer = lambda r: None
vision._noter = lambda u: 0.001
vision._appeler = lambda c, *a, **k: (corps.append(c), {"content": [{"type": "tool_use", "input": {"est_une_carte": True, "sport": "hockey", "joueur": "Mikhail Sergachev", "annee": "2025-26", "auto": True, "photos": [{"cote": "devant"}]}}]})[1]
PH = "data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff" + b"x" * 400).decode()
vision._decoder = lambda p: (p.encode()[:200], "image/jpeg")
r = vision.identifier([PH], rapide=True)
assert r["ok"] and r["rapide"] and r["champs"]["joueur"] == "Mikhail Sergachev" and r["champs"]["auto"] == 1, r
assert corps[-1]["tools"][0] is vision.OUTIL_RAPIDE and corps[-1]["max_tokens"] == vision.MAX_SORTIE_RAPIDE
assert r["photos"][0]["cote"] == "devant" and r["photos"][0]["coins"] is None
# la fiche courte va dans le cache sous sa propre cle : la complete n'est jamais remplacee par elle
r2 = vision.identifier([PH], rapide=True)
assert r2["cache"] and len(corps) == 1
vision.identifier([PH])                              # la complete : un vrai appel (la courte ne suffit pas)
assert len(corps) == 2 and corps[-1]["tools"][0] is vision.OUTIL
assert vision.identifier([PH], rapide=True)["cache"] and len(corps) == 2    # la complete sert aussi au comp

# ---------- LA RECHERCHE DU SCAN ----------
assert lockerroom.requete_comp({"annee": "2025-26", "joueur": "Mikhail Sergachev", "set_nom": "SP Authentic", "parallele": "Limited Auto Material",
                                "tirage": 100, "auto": 1}) == "2025-26 Mikhail Sergachev SP Authentic Limited Auto Material /100 auto"
assert lockerroom.requete_comp({"annee": "2024-25", "joueur": "Macklin Celebrini", "set_nom": "Series 1", "parallele": "Young Guns", "grade": "PSA 10"}) \
    == "2024-25 Macklin Celebrini Young Guns PSA 10"

# ---------- L'ECRAN ----------
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "src_app.html"), encoding="utf-8").read()
m = re.search(r"const badgeSlab = \(txt, ton, ic, attrs\) => `(.*?)`;\n", src)
assert m and "<button" not in m.group(1) and "role=\"button\"" in m.group(1), "une pastille touchable dans une tuile-bouton casse la grille"
assert "API.comp_rapide(q)" in src and "API.photo_identifier(photos, rapide === true)" in src and "ouvrirScanner({but: 'comp'})" in src
assert "if (enComp) { sr.q = r.q_comp || q; feuilleComp(sr); }" in src                 # le scan Comp rapide ouvre la fenetre, pas la page
print("OK comp rapide")
