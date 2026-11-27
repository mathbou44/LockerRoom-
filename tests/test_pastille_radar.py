"""26 nov 2026 (Mathieu, capture du Radar : « Deals 80 » et « 80 » en rouge sur l'onglet, pour une quarantaine de cartes) :
« ca dit 80 deals, je suis loin d'en avoir 80 [...] le chiffre dans la pastille disparait quand on clique sur l'onglet, c'est
suppose etre une notification [...] si la personne arrive, hey j'ai 80 nouvelles cartes, il scroll et il y en a juste 30, ca
marche pas ».
1) le nombre du Radar = les cartes que la personne VOIT (le compte du serveur etait pris AVANT la note SlabIQ minimum) ;
2) la pastille rouge de l'onglet = les cartes de son Radar pas encore vues ; ouvrir le Radar les marque vues, elle part.
Et le curseur « Profit minimum » des Filtres (« il est comme jamme la ») : le verrou de defilement des feuilles annulait son geste."""
import os, re, subprocess, sys, tempfile, json
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
ui = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()


def bloc(debut, fin="\n}\n"):
    i = src.index(debut)
    return src[i:src.index(fin, i) + len(fin)]


# ---- 1. la logique, executee pour vrai (node) : les memes fonctions que l'app
js = "\n".join([bloc("const nbTxt = n =>", "\n"), bloc("const RADAR_VUS = (() => {", "\n})();\n"), bloc("const surRadar = () =>", "\n"), bloc("const idsRadar = () =>", "\n"),
                bloc("function pastilleRadar(){"), bloc("function radarListe(ids, accueil){"), bloc("function dealsMontres(d, F, pf){"), bloc("function nbDealsGarde(n){")])
essai = r'''
const mem = {}; const localStorage = {getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); }};
const location = {hash: '#accueil'}; const S = {}; const pD = {hidden: true, textContent: ''}; const $ = (q) => q === '#pastille-deals' ? pD : null;
''' + js + r'''
const out = [];
const voir = () => pD.hidden ? '' : pD.textContent;
// le serveur compte 10 deals ; 6 passent la note minimum (C et plus = 50) : ce sont ces 6 que la personne voit
const d = {deals: [95, 90, 80, 70, 60, 55, 40, null, 30, 20].map((s, i) => ({item_id: 'd' + i, score: s})), suivis: [{item_id: 's1', score: 77}, {item_id: 's2', score: 10}]};
const m = dealsMontres(d, {iq_min: null}, {iq_min: 50});
out.push(m.deals.length, m.suivis.length, dealsMontres(d, {iq_min: 0}, {iq_min: 50}).deals.length, dealsMontres(d, {}, null).deals.length);
const ids = [...m.deals, ...m.suivis].map(x => x.item_id);
out.push(radarListe(ids), voir());                         // a l'accueil, jamais vues : 7 nouvelles
location.hash = '#deals'; out.push(pastilleRadar(), voir());   // on ouvre le Radar : la pastille part
location.hash = '#accueil'; out.push(pastilleRadar(), voir()); // de retour : toujours rien (tout est vu)
out.push(radarListe([...ids, 'n1', 'n2']), voir());         // 2 nouvelles cartes arrivent
location.hash = '#deals/watch'; out.push(pastilleRadar());  // la Watchlist est dans le Radar : vu aussi
location.hash = '#inventaire'; out.push(pastilleRadar(), radarListe(['a1', 'a2', 'd0'], true), voir());   // l'accueil apporte 2 cartes pas encore vues
out.push(JSON.parse(mem.lr_radar_vus).length, nbDealsGarde(), nbDealsGarde(7), mem.lr_radar_n);
S.nbDeals = null; out.push(nbDealsGarde());                 // relu de l'appareil au demarrage suivant
console.log(JSON.stringify(out));
'''
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(essai)
r = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=60)
assert r.returncode == 0, r.stderr[-800:]
o = json.loads(r.stdout)
assert o[:4] == [6, 1, 10, 4], "la note minimum : celle des Filtres, sinon celle du profil, sinon B (65) ; 0 = toutes : %r" % o[:4]
assert o[4:6] == [7, "7"], "a l'accueil : les 7 cartes du Radar jamais vues"
assert o[6:8] == [0, ""], "ouvrir le Radar : la pastille part"
assert o[8:10] == [0, ""], "de retour a l'accueil : rien, tout est vu"
assert o[10:12] == [2, "2"], "deux nouvelles cartes : 2"
assert o[12] == 0 and o[13] == 0, "la Watchlist fait partie du Radar"
assert o[14:16] == [2, "2"], "les cartes que l'accueil montre deja comptent aussi (2 jamais vues, d0 l'etait)"
assert o[16] == 9 and o[17] is None and o[18] == 7 and o[19] == "7" and o[20] == 7, o[16:]

# ---- 2. le Radar des deals : le nombre de l'onglet et « cachees » viennent de la grille, pas du compte du serveur
k = src.index("async function chargerDeals(frais){")
cd = src[k:src.index("S.dealsParId = Object.fromEntries(", k)]
assert "pD.textContent = d.n" not in src and "dn.textContent = d.n" not in src, "plus le compte du serveur (avant la note minimum)"
assert "const m_ = dealsMontres(d, F, S.dealsProfil); d = Object.assign({}, d, {deals: m_.deals}); SU = m_.suivis;" in cd
assert "const nAff = (d.deals || []).length + SU.length" in cd and "dn.textContent = nAff || ''" in cd and "d.n = nAff;" in cd
assert "nbDealsGarde(nAff); radarListe([...(d.deals || []), ...SU].map(x => x.item_id));" in cd
# ---- 3. l'accueil (deals) : le meme nombre, relu en fond avec les memes filtres ; le Radar « Mes cibles » n'est jamais relance
v = bloc("async function verifierRadar(){")
assert "if (!comps() || surRadar() || Date.now() - (S.radarVerifLe || 0) < 600000" in v and "API.deals_liste(S.dealsF)" in v and "dealsMontres(d, S.dealsF, pf)" in v
assert "mes_deals" not in v, "le Radar « Mes cibles » refait des recherches eBay : jamais relance en fond"
a = bloc("function nbRadarAccueil(a){")
assert "verifierRadar(); pastilleRadar(); const n = nbDealsGarde(); return n != null ? n : ((a && a.nb_deals) || 0);" in a
assert "radarListe(a.deals.map(x => x && x.item_id), true);" in a
assert "pD.textContent" not in bloc("function radarNb(n, le){"), "radarNb ne peint plus la pastille : c'est pastilleRadar"
assert "radarListe([...tous.entries()].filter(([, x]) => !x.recherche).map(([id]) => id));" in src
# ---- 4. le routeur : la pastille part des qu'on arrive sur le Radar (avant meme que la liste charge)
rt = bloc("function route(){", "const vues = {")
assert "pastilleRadar();" in rt and rt.index("pastilleRadar();") < rt.index("$$('.onglets a').forEach")
assert len(re.findall(r"getElementById\('pastille-deals'\)|\$\('#pastille-deals'\)", src)) == 1, "un seul endroit ecrit la pastille du Radar"

# ---- 5. le curseur des Filtres : le verrou de defilement des feuilles ne l'annule plus
t = src.index("const SEL = '#fen-annonce, .fond-feuille, .vd, .dp, .pop2-fond, #scan';")
verrou = src[t:src.index("})();", t)]
sauf, annule = verrou.index("if (t && t.closest && t.closest('input[type=range]')) return;"), verrou.index("if (!f || !defile(t, f)) { if (e.cancelable) e.preventDefault(); }")
assert sauf < annule, "le curseur est epargne AVANT l'annulation du geste"
assert 'type="range" class="fd-r" id="fd-r"' in src

# ---- 6. l'app construite
u = ui.replace(" ", "")
assert "RADAR_VUS" in ui and "lr_radar_vus" in ui and "dealsMontres" in ui and 'input[type=range]"))return;if(!f||!defile(t,f))' in u, "ui/app.html n'est pas reconstruit"
print("test_pastille_radar OK")
