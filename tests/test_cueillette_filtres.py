"""26 nov 2026, 17 h 54 (Mathieu : « pour le radar ajoute une section pour selectionner les vendeurs avec lesquels l'utilisateur
peut aller en cueillette ; notre app lui donne les choix [...] il commence a taper le nom et la proposition pop en dessous ; notre
app doit absolument lui proposer le vendeur pour eviter des bugs ou erreurs d'ecriture » ; 19 h 24 : « il n'y a aucun port pour
les vendeurs que l'utilisateur va selectionner [...] donc meilleure marge de profit »)."""
import os, re, subprocess, json, sys, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()

# ---- 1. les propositions : la fonction de l'app, executee pour vrai
m = re.search(r"function vendeursProposes\(tous, choisis, q\)\{.*?\n\}\n", src, re.S)
assert m, "la fonction des propositions"
js = m.group(0) + """
const T = ['savage.cards', 'remi-card-trader', 'cf31_sports_cards', 'SlabSharksInc', 'slab_kings', 'cardshark99', 'sportscards-mtl', 'ab'];
const out = {
  vide: vendeursProposes(T, [], ''), espaces: vendeursProposes(T, [], '  '),
  debut: vendeursProposes(T, [], 'slab'),                 // ceux qui COMMENCENT par « slab » d'abord
  milieu: vendeursProposes(T, [], 'shark'),               // puis ceux qui le contiennent
  ponctuation: vendeursProposes(T, [], 'Remi card'),      // sans les tirets ni les majuscules
  choisi: vendeursProposes(T, ['slabsharksinc'], 'slab'), // jamais un vendeur deja choisi
  inconnu: vendeursProposes(T, [], 'zzz'),
  quatre: vendeursProposes(['a1', 'a2', 'a3', 'a4', 'a5', 'a6'], [], 'a').length,
};
console.log(JSON.stringify(out));
"""
r = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
assert r["vide"] == [] and r["espaces"] == [] and r["inconnu"] == [], r
assert r["debut"] == ["slab_kings", "SlabSharksInc"], r["debut"]
assert r["milieu"] == ["cardshark99", "SlabSharksInc"], r["milieu"]
assert r["ponctuation"] == ["remi-card-trader"], r["ponctuation"]
assert r["choisi"] == ["slab_kings"], r["choisi"]
assert r["quatre"] == 4

# ---- 2. la feuille des filtres : le champ, les propositions SOUS le champ, et jamais un nom libre
filtres = src[src.index("ouvrirFeuille(`<div class=\"io-tete\"><button class=\"io-raz\" id=\"fd-raz\">"):src.index("$('#fd-raz').onclick = () => { vibrer(); appliquer(true); };")]
assert 'id="rv-in"' in filtres and 'id="rv-s" role="listbox"' in filtres and 'id="rv-l"' in filtres
assert filtres.index('id="rv-in"') < filtres.index('id="rv-s"'), "les propositions s'ouvrent sous le champ"
assert filtres.index('id="fd-seul"') < filtres.index('id="rv-g"'), "apres les joueurs"
sub = filtres[filtres.index("$('#rv-aj').onsubmit"):]
assert "const b = $('#rv-s [data-rv]'); if (b) b.click();" in sub[:200], "Entree prend la 1re proposition, jamais le texte tape"
assert "RAM.push($('#rv-in').value" not in filtres and "RAM.push(enCours" not in filtres
assert "API.deals_vendeurs_liste()" in filtres and "API.deals_ramassage(ramN)" in filtres
assert "if (!raz && ramN.join() !== [...RAM0].sort().join())" in filtres, "enregistre seulement si la liste change ; « Réinitialiser » n'y touche pas"
assert "vendeursProposes" in app and "rv-in" in app and "deals_ramassage" in app, "l'app servie"

# ---- 3. le calcul : chez un vendeur en cueillette, le port sort du total et la mise max monte d'autant
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import lockerroom
x = {"vendeur": "SlabSharksInc", "port": 13.0, "total": 43.0, "valeur": 68.0, "mise_max": 22.0}
y = lockerroom.Api._ramasser(x, {"slabsharksinc"})
assert y["ramassage"] is True and y["port"] == 0.0 and y["total"] == 30.0 and y["mise_max"] == 35.0, y
assert lockerroom.Api._ramasser(x, {"autre"}) is x and lockerroom.Api._ramasser(x, set()) is x
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
r = api.deals_ramassage(["SlabSharksInc", "remi-card-trader", "un nom<script>"])
assert r["ramassage"] == ["remi-card-trader", "slabsharksinc", "unnomscript"], r["ramassage"]
assert api._chez_ramassage() == {"slabsharksinc", "remi-card-trader", "unnomscript"}
# ---- 4. 20 h 12 (« il detecte pas cf31 ») : les vendeurs proposes = suivis + ceux de depart + ceux du Radar
import deals as _d
_d.vendeurs_suivis = lambda: ["savage.cards", "wests01"]            # une liste reglee en ligne, sans CF31
_d.lire_vite = lambda: {"deals": [{"item_id": "1", "vendeur": "SlabSharksInc"}, {"item_id": "2", "vendeur": "nouveau_vendeur-99"}, {"item_id": "3", "vendeur": "<b>pas un nom</b>"}],
                        "encans": {"a": {"vendeur": "encan.cards"}}}
r = api.deals_vendeurs_liste()
p_ = [v.lower() for v in r["proposes"]]
assert "cf31_sports_cards" in p_ and "remi-card-trader" in p_ and "savage.cards" in p_, p_
assert "nouveau_vendeur-99" in p_ and "encan.cards" in p_ and p_.count("slabsharksinc") == 1, p_
assert not any("<" in v for v in r["proposes"]) and r["vendeurs"] == ["savage.cards", "wests01"]
assert "r.proposes || r.vendeurs" in src

# ---- 5. 20 h 12 (« le filtre ouvre plus depuis que j'ai pick les local pick up ») : a l'ordi, la barre est rangee dans l'en-tete
# AVANT de brancher ses boutons (sinon le clic va sur l'ancien bouton, retire juste apres)
d0 = src.index("async function chargerDeals(frais){")
cd = src[d0:src.index("\nfunction ", d0 + 10)]
assert "  rangerRecherche();\n  brancherRondsDeals(F, sp);" in cd and cd.count("brancherRondsDeals(F, sp);") == 1, "ranger d'abord, brancher ensuite"
assert "z.scrollIntoView({block: 'nearest'})" in filtres or "scrollIntoView({block: 'nearest'})" in src and "#rv-s{scroll-margin-bottom:96px}" in src
print("test_cueillette_filtres OK")
