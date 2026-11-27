"""27 nov 2026 (Mathieu, 26 nov 21 h 24 : « il bug encore, je peux cliquer dessus 3095x et rien se passe » : le bouton etait
repare et en ligne depuis 30 minutes, mais son onglet, ouvert avant, roulait encore l'ancienne page ; « je veux pas cliquer,
tout doit se faire auto »). Une nouvelle version en ligne : la page ouverte le sait et se recharge seule, au moment sur, jamais
en boucle.   python tests/test_nouvelle_version.py   (flask + node ; aucun appel reseau)"""
import json, os, re, subprocess, sys, tempfile, textwrap
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
app = open(os.path.join(RACINE, "ui", "app.html"), encoding="utf-8").read()

# ---- 1. la page porte la balise (vide : le serveur y ecrit l'empreinte) et l'app lit l'en-tete de chaque reponse
for nom, t in (("source", src), ("app", app)):
    assert t.count('<meta name="sc-v" content="">') == 1, nom
assert "verVue(r.headers.get('X-App-V'))" in src and re.search(r"verVue\(r\.headers\.get\(['\"]X-App-V['\"]\)\)", app)

# ---- 2. le serveur : la meme empreinte dans la page, dans son ETag et dans chaque reponse ; elle change avec la page
SCRIPT = textwrap.dedent('''
    import os, sys, shutil, re, time
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server
    ui = os.path.join(os.environ["LOCKERROOM_DONNEES"], "ui"); os.makedirs(ui)
    shutil.copy(os.path.join(%(ici)r, "ui", "app.html"), os.path.join(ui, "app.html"))
    vrai = server.DOSSIER_UI
    c = server.app.test_client()
    def page(**h):
        server.DOSSIER_UI = ui
        try: return c.get("/", headers=h)
        finally: server.DOSSIER_UI = vrai
    def sante():
        server.DOSSIER_UI = ui
        try: return c.get("/sante")
        finally: server.DOSSIER_UI = vrai
    server.DOSSIER_UI = ui; server._APP_V.update(t=0.0, v=""); server._APP_CACHE.clear()
    v1 = server._version_app(); server.DOSSIER_UI = vrai
    assert re.fullmatch(r"[0-9a-f]{16}", v1), v1
    r = page()
    if r.status_code in (301, 302):                      # un compte est exige pour la page : on lit alors la page en memoire
        html = server._APP_CACHE["brut"].decode("utf-8")
    else:
        assert r.status_code == 200, r.status_code
        html = r.get_data(as_text=True)
        assert r.headers["ETag"] == '"' + v1 + '"' and r.headers["X-App-V"] == v1, dict(r.headers)
    assert html.count('<meta name="sc-v" content="' + v1 + '">') == 1 and '<meta name="sc-v" content="">' not in html
    s = sante(); assert s.status_code == 200 and s.headers["X-App-V"] == v1, dict(s.headers)
    server.DOSSIER_UI = ui
    a = c.post("/api/forfait", json=[]); server.DOSSIER_UI = vrai
    assert a.headers.get("X-App-V") == v1, (a.status_code, dict(a.headers))
    # la verification de sante ne relit pas le fichier a chaque fois (une fois aux 5 secondes)
    n = [0]; vrai_charger = server._charger_app
    def compte(): n[0] += 1; return vrai_charger()
    server._charger_app = compte
    for _ in range(50): sante()
    assert n[0] == 0, n
    # une nouvelle page (mise en ligne) : nouvelle empreinte partout
    with open(os.path.join(ui, "app.html"), "ab") as f: f.write(b"<!-- nouvelle version -->")
    t = time.time() + 5; os.utime(os.path.join(ui, "app.html"), (t, t))
    server._APP_V["t"] = 0.0
    s = sante(); v2 = s.headers["X-App-V"]
    assert n[0] == 1 and v2 != v1 and re.fullmatch(r"[0-9a-f]{16}", v2), (n, v1, v2)
    server._charger_app = vrai_charger
    server.DOSSIER_UI = ui; brut = server._charger_app()["brut"].decode("utf-8"); server.DOSSIER_UI = vrai
    assert ('<meta name="sc-v" content="' + v2 + '">') in brut and server._APP_CACHE["etag"] == '"' + v2 + '"'
    # sans page (dossier vide) : pas d'en-tete, pas d'erreur
    vide = os.path.join(os.environ["LOCKERROOM_DONNEES"], "vide"); os.makedirs(vide)
    server.DOSSIER_UI = vide; server._APP_V.update(t=0.0, v=""); server._APP_CACHE.clear()
    s = c.get("/sante"); server.DOSSIER_UI = vrai
    assert s.status_code == 200 and "X-App-V" not in s.headers, dict(s.headers)
    print("SERVEUR OK")
''')
d = tempfile.mkdtemp()
env = dict(os.environ, LOCKERROOM_DONNEES=d, LOCKERROOM_TACHES="0", LOCKERROOM_SECRET="s" * 32)
env.pop("LOCKERROOM_MULTI", None)
r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": RACINE}], env=env, capture_output=True, text=True)
assert "SERVEUR OK" in r.stdout, (r.stdout[-800:], r.stderr[-2500:])

# ---- 3. l'app : la vraie fonction, executee pour vrai (node), dans tous les cas
m = re.search(r"var VER = \{.*?\n(?=async function appelServeur\(nom, corps, essai2\)\{)", src, re.S)
assert m, "le bloc de la nouvelle version"
JS = """
let META = 'aaa';
const sess = {}; let sessCasse = false;
globalThis.sessionStorage = {getItem: k => { if (sessCasse) throw new Error('x'); return k in sess ? sess[k] : null; }, setItem: (k, v) => { if (sessCasse) throw new Error('x'); sess[k] = String(v); }};
let recharges = 0; globalThis.location = {hash: '#deals', reload: () => { recharges++; }};
const dom = {feuille: {hidden: true}, actif: null, fen: [], champs: [], special: null, classes: new Set()};
globalThis.document = {hidden: false, querySelector: s => s.startsWith('meta') ? {content: META} : dom.special, getElementById: () => dom.feuille,
  body: {classList: {contains: c => dom.classes.has(c)}}, get activeElement(){ return dom.actif; }, querySelectorAll: s => s === '.fen' ? dom.fen : dom.champs,
  addEventListener: () => {}, documentElement: {scrollHeight: 0}};
globalThis.window = {scrollY: 0, scrollTo: () => {}}; globalThis.innerHeight = 800;
const ecouteurs = {}; globalThis.addEventListener = (n, f) => { ecouteurs[n] = f; }; globalThis.setInterval = () => 0;
let minuteries = []; globalThis.setTimeout = (f, ms) => { minuteries.push([f, ms]); return minuteries.length; }; globalThis.clearTimeout = () => {};
let SERVEUR = 'aaa', panne = false, lus = 0; globalThis.fetch = async (u, o) => { lus++; if (panne) throw new Error('reseau'); if (u !== '/sante' || o.cache !== 'no-store') throw new Error('mauvais appel'); return {ok: true, headers: {get: () => SERVEUR}}; };
var DERNIERE_ACTION = 0; const tt = (a) => a; const toast = () => {};
""" + m.group(0) + """
const R = {}; const libre = () => { VER.part = false; };
const recule = (min) => { const x = JSON.parse(sess['sc-maj']); x.t -= min * 60000; sess['sc-maj'] = JSON.stringify(x); };
(async () => {
  R.moi = VER.moi;
  verVue('aaa'); verVue(''); verVue(null); R.rien = [minuteries.length, VER.pret];
  verVue('bbb'); verVue('bbb'); verVue('bbb'); R.une_minuterie = minuteries.map(x => x[1]);
  SERVEUR = 'bbb'; R.confirmee = await verConfirmer();
  // occupe : jamais de rechargement
  const cas = {
    fiche: () => dom.classes.add('fen-ouverte'), feuille: () => { dom.feuille.hidden = false; }, vente: () => { location.hash = '#vendre/12'; },
    saisie: () => { dom.actif = {tagName: 'INPUT'}; }, menu: () => { dom.actif = {tagName: 'SELECT'}; }, photo: () => { dom.special = {}; },
    fenetre: () => { dom.fen = [{offsetParent: {}}]; }, texte: () => { dom.champs = [{offsetParent: {}, type: 'text', value: 'bedard', defaultValue: ''}]; },
    fichier: () => { dom.champs = [{offsetParent: {}, type: 'file', files: [1]}]; }, envoi: () => { VER.ecrit = 1; },
  };
  const net = () => { dom.classes.clear(); dom.feuille.hidden = true; location.hash = '#deals'; dom.actif = null; dom.special = null; dom.fen = []; dom.champs = []; VER.ecrit = 0; };
  R.occupe = {};
  for (const [k, f] of Object.entries(cas)) { net(); f(); libre(); R.occupe[k] = [verOccupe(), await verMaj(), recharges]; }
  net(); libre();
  // des champs qui ne bloquent pas : caches, cases a cocher, valeur d'origine, fenetre cachee
  dom.champs = [{offsetParent: null, type: 'text', value: 'x', defaultValue: ''}, {offsetParent: {}, type: 'checkbox', value: 'on', defaultValue: ''}, {offsetParent: {}, type: 'text', value: 'CAD', defaultValue: 'CAD'}, {offsetParent: {}, type: 'file', files: []}];
  dom.fen = [{offsetParent: null}]; dom.actif = {tagName: 'BODY'};
  R.libre = verOccupe();
  lus = 0; R.maj1 = [await verMaj(), recharges, JSON.parse(sess['sc-maj']).v, JSON.parse(sess['sc-maj']).n, JSON.parse(sess['sc-maj']).h, lus];
  libre(); R.trop_tot = [await verMaj(), recharges];                                   // moins de 10 minutes
  recule(11); libre(); R.maj2 = [await verMaj(), recharges, JSON.parse(sess['sc-maj']).n];
  recule(11); libre(); R.boucle = [await verMaj(), recharges];                         // 2 fois pour la meme version : fini
  SERVEUR = 'ccc'; await verConfirmer(); recule(11); libre();
  R.autre_version = [VER.pret, await verMaj(), recharges, JSON.parse(sess['sc-maj']).n];
  // au dernier moment le serveur repond l'ancienne version (retour en arriere) : rien, et on oublie
  SERVEUR = 'ddd'; await verConfirmer(); recule(11); libre(); SERVEUR = 'aaa';
  R.retour = [await verMaj(), recharges, VER.pret];
  SERVEUR = 'ddd'; await verConfirmer(); libre(); panne = true; R.panne = [await verMaj(), recharges, VER.pret]; panne = false;
  libre(); sessCasse = true; R.prive = [await verMaj(), recharges]; sessCasse = false;
  verVue('aaa'); R.revenue = VER.pret;
  // sans balise dans la page : la premiere empreinte vue devient la mienne
  VER.moi = ''; const n0 = minuteries.length; verVue('zzz'); R.sans_balise = [VER.moi, minuteries.length - n0];
  R.ecouteurs = Object.keys(ecouteurs).sort();
  console.log(JSON.stringify(R));
})();
"""
r = subprocess.run(["node", "-e", JS], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-2500:]
R = json.loads(r.stdout)
assert R["moi"] == "aaa" and R["rien"] == [0, ""], R
assert R["une_minuterie"] == [15000], R["une_minuterie"]          # reverifiee 15 s plus tard, une seule fois
assert R["confirmee"] == "bbb"
for k, v in R["occupe"].items():
    assert v == [True, False, 0], (k, v)                            # occupe -> pas de rechargement
assert R["libre"] is False
assert R["maj1"] == [True, 1, "bbb", 1, "#deals", 1], R["maj1"]     # libre : relu une derniere fois, note prise, recharge
assert R["trop_tot"] == [False, 1], R["trop_tot"]
assert R["maj2"] == [True, 2, 2], R["maj2"]
assert R["boucle"] == [False, 2], R["boucle"]
assert R["autre_version"] == ["ccc", True, 3, 1], R["autre_version"]
assert R["retour"] == [False, 3, ""], R["retour"]
assert R["panne"] == [False, 3, "ddd"], R["panne"]                  # serveur injoignable : on ne recharge pas dans le vide
assert R["prive"] == [False, 3], R["prive"]
assert R["revenue"] == ""
assert R["sans_balise"] == ["zzz", 0], R["sans_balise"]
assert R["ecouteurs"] == ["hashchange", "load"], R["ecouteurs"]

# ---- 4. les trois moments surs sont branches, et l'envoi en cours est compte autour de CHAQUE appel
assert "addEventListener('hashchange', () => { if (VER.pret) setTimeout(verMaj, 500); });" in src
assert "if (VER.pret) verMaj(); else if (parti && VER.moi) verConfirmer().then(() => verMaj());" in src
assert "Date.now() - DERNIERE_ACTION > 30000) verMaj(); }, 10000);" in src
assert "try { return await appelServeur0(nom, corps, essai2); } finally { if (ecrit_) VER.ecrit--; }" in src
print("NOUVELLE VERSION OK")
