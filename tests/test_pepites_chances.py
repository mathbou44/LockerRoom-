"""5 nov 2026 : les pepites (nom mal ecrit sur eBay, jugees avec le nom corrige) et la chance de gagner un encan a sa
mise max (apprise des encans finis ; un genre perdu d'avance n'est plus montre). Aucun reseau."""
import os, sys, tempfile, sqlite3
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import fautes, chances, deals

# 1. les fautes : realistes, jamais le vrai nom, et la correction remet le nom
v = fautes.variantes("Auston Matthews", 2)
assert v[0] == "mathews" and "matthews" not in v, v
assert "gretsky" in fautes.variantes("Wayne Gretzky", 3)
assert fautes.variantes("Carey Price") == [] and fautes.variantes("Patrick Roy") == []
assert fautes.corriger("2016 Young Guns AUSTON MATHEWS #201", "mathews", "Auston Matthews") == "2016 Young Guns AUSTON Matthews #201"
assert fautes.corriger("2016 Young Guns Auston Matthews #201", "mathews", "Auston Matthews") is None     # bien ecrit : pas une pepite
assert len(fautes.requetes(deals.VEDETTES)) >= 40

# 2. pepites() : une annonce mal ecrite est jugee avec le nom corrige ; une bien ecrite est ignoree
fin = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat().replace("+00:00", "Z")
vus = []
def rech(q, **k):
    if not k.get("encheres"):
        return []
    return [{"item_id": "p1", "titre": "2016-17 Upper Deck Young Guns Auston Mathews #201", "total": 40.0, "prix_cad": 40.0, "port_cad": 0,
             "encan": True, "fin": fin, "url": "https://www.ebay.ca/itm/111111111111"},
            {"item_id": "p2", "titre": "2016-17 Upper Deck Young Guns Auston Matthews #201", "total": 40.0, "encan": True, "fin": fin}]
juges = []
vrai_juger = deals._juger
deals._juger = lambda a, r, *x, **k: juges.append((a["item_id"], a["titre"], r.get("faute"), a.get("titre_ebay")))
deals.VEDETTES[:] = ["Auston Matthews"] + [n for n in deals.VEDETTES if n != "Auston Matthews"]
deals._verificateur = lambda *a, **k: None
deals._verifier_tard = lambda *a, **k: None
deals.pepites(rechercher=rech, bassin=deals.Bassin(charger=False), n=1)
deals._juger = vrai_juger
assert juges == [("p1", "2016-17 Upper Deck Young Guns Auston Matthews #201", "mathews", "2016-17 Upper Deck Young Guns Auston Mathews #201")], juges

# 3. chances : 20 encans finis du meme genre, 1 seul sous la mise max -> cache ; un autre genre gagne souvent -> garde
maint = datetime.now(timezone.utc)
passe = (maint - timedelta(hours=5)).isoformat()
encs = [{"item_id": str(100000000000 + i), "encan": True, "valeur": 100.0, "mise_max": 70.0, "fin": passe, "vendeur": "savage.cards", "recrue": True}
        for i in range(20)]
encs += [{"item_id": str(200000000000 + i), "encan": True, "valeur": 30.0, "mise_max": 21.0, "fin": passe, "vendeur": "petitvendeur", "vendeur_score": 300}
         for i in range(20)]
assert chances.archiver(encs) == 40
c = sqlite3.connect(os.path.join(comptes.DONNEES, "base_ventes.sqlite"))
c.execute("CREATE TABLE IF NOT EXISTS ventes (q TEXT, cle TEXT, titre TEXT, prix REAL, le TEXT, photo TEXT, url TEXT, offre INTEGER, vu_le TEXT, PRIMARY KEY (q, cle))")
jour = maint.strftime("%Y-%m-%d")
for i in range(20):
    c.execute("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", ("q", f"k{i}", "t", 65.0 if i == 0 else 105.0, jour, None, f"https://www.ebay.com/itm/{100000000000 + i}", 0, jour))
    c.execute("INSERT INTO ventes VALUES (?,?,?,?,?,?,?,?,?)", ("q", f"m{i}", "t", 15.0 if i < 12 else 28.0, jour, None, f"https://www.ebay.com/itm/titre-x/{200000000000 + i}?h=1", 0, jour))
c.commit(); c.close()
r = chances.resoudre(maint)
assert r["trouves"] == 40, r
gros = {"encan": True, "valeur": 120.0, "mise_max": 84.0, "vendeur": "savage.cards", "recrue": True}
petit = {"encan": True, "valeur": 40.0, "mise_max": 28.0, "vendeur": "autre", "vendeur_score": 900}
cg, cp = chances.chance(gros), chances.chance(petit)
assert cg[2] == "genre" and cg[0] < 0.12 and chances.a_cacher(gros, cg), cg
assert cp[2] == "genre" and cp[0] > 0.5 and not chances.a_cacher(petit, cp), cp
# un genre jamais vu (assez d'encans au total) : la moyenne de tous, jamais cache sur elle
autre = {"encan": True, "valeur": 500.0, "mise_max": 350.0, "vendeur": "x", "vendeur_score": 50000}
ca = chances.chance(autre)
assert ca and ca[2] == "tous" and not chances.a_cacher(autre, ca), ca
# 4. deals_liste : l'encan perdu d'avance n'est pas montre, l'autre garde sa chance
import lockerroom
l = lockerroom.Api._avec_chances([dict(gros, item_id="g"), dict(petit, item_id="p"), {"item_id": "f", "encan": False, "valeur": 10}])
# 11 nov 2026 (« demain c'est la fin de Savage, Remi et CF31 et y'a rien ») : un gros vendeur suivi n'est JAMAIS cache,
# il garde sa chance (la fiche la dit) ; un autre vendeur perdu d'avance l'est toujours
assert [x["item_id"] for x in l] == ["g", "p", "f"], l
assert l[0]["chance"]["p"] < 0.12 and l[1]["chance"]["niveau"] == "genre", l
for v in ("remi-card-trader", "CF31_Sports_Cards", "slabsharksinc"):
    assert [x["item_id"] for x in lockerroom.Api._avec_chances([dict(gros, item_id="v", vendeur=v)])] == ["v"], v
vrai_ch = chances.chance
chances.chance = lambda x: (0.05, 30, "genre")
assert lockerroom.Api._avec_chances([dict(petit, item_id="q")]) == []
chances.chance = vrai_ch
print("PEPITES CHANCES OK")
