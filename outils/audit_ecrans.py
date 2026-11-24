"""Audit des ecrans (24 nov 2026, Mathieu : « Repasse chaque fonction et calcul. Il faut un audit intense de l'app »).
Chaque ecran de l'app, dans une vue donnee (pro, gratuit, admin : la vue simulee par le SERVEUR, comme Mathieu), a la taille
d'un iPhone avec ses marges : les erreurs JavaScript, les appels au serveur qui echouent, la page qui glisse pour rien, ce qui
depasse en largeur, le francais reste en anglais, et surtout les BOUTONS MORTS : chaque bouton sans geste branche est
touche ; s'il ne se passe rien (aucun changement a l'ecran, aucune navigation, aucun appel), il est note.
Usage : python3 outils/audit_ecrans.py <vue> <langue> [largeur hauteur] [route ...]   ->   /tmp/audit_ecrans_<vue>_<langue>.json
Il faut Playwright, Chrome (/usr/bin/google-chrome) et le serveur local d'UNE personne (l'admin) sur le port 8431 :
  env -u LOCKERROOM_MULTI LOCKERROOM_DONNEES=/tmp/srv_m LOCKERROOM_PORT=8431 LR_CALME_DEMARRAGE_S=99999 LR_RECHAUFFER_S=99999 python3 server.py
Pas dans la suite de tests (elle n'a pas de navigateur). Une vue a la fois : la vue simulee est gardee par le serveur.
Limite : le serveur local a peu de donnees (pas de compte eBay relie) ; beaucoup d'ecrans sont dans leur etat vide.
Les « erreurs_detail » du Radar ne sont montrees qu'au vrai admin : ce n'est pas du francais oublie."""
import asyncio, json, re, sys, time
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8431"
ROUTES = ["accueil", "deals", "deals/watch", "inventaire", "vendre", "valeur", "breaks", "analyse/2025-26-upper-deck-splendor", "bilan", "ventes",
          "reglages", "guide", "calendrier", "comptoir", "joueur/Connor%20McDavid", "sante", "idees", "offres", "traiter", "notifs", "alertes", "iq"]
DANGER = re.compile(r"sign out|log ?out|d[ée]connex|delete|supprim|remove|retir|vider|reset|r[ée]initial|effac|publish|publi|acheter|buy now|payer|subscribe|abonn|go pro|passer pro", re.I)
FR = re.compile(r"\b(les|des|une|pour|avec|sans|ton|tes|mes|dans|sont|aux|cette|voir|tous|cartes|ventes|mise|joueurs|[ée]quipes|aucun|aucune|ajouter|fermer|annuler|r[ée]glages|vendre|acheter|bient[oô]t|jours|semaine|mois|prix|carte)\b|[àâçéèêëîïôûù]", re.I)
CACHE = "document.querySelectorAll('.pop-fond, .pop, .tuto-fond').forEach(x => { x.style.display = 'none'; }); try { if (!document.querySelector('#fond-feuille').hidden) fermerFeuille(); } catch (e) {}"

JS_MESURES = """(() => { const d = document.scrollingElement; const vis = (e) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none' && e.offsetParent !== null; };
  const large = [...document.querySelectorAll('main *, .ecran *')].filter(vis).filter(e => { const r = e.getBoundingClientRect(); return r.right > innerWidth + 2 && r.left < innerWidth && !e.closest('[style*=overflow], .d-car, .histoires, .acc-ticker, .tk-piste, .io-fvl, .br-g, .post-car, .chips, .d-ronds, .seg-def, .i-filtres, .rail, .defile-x') && (() => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { if (getComputedStyle(p).overflowX !== 'visible') return false; } return true; })(); }).slice(0, 4).map(e => (e.className || e.tagName) + ' : ' + (e.textContent || '').trim().slice(0, 40));
  const textes = []; const w = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const n = w.currentNode, t = (n.nodeValue || '').replace(/\\s+/g, ' ').trim(); if (t.length > 2 && n.parentElement && vis(n.parentElement) && !n.parentElement.closest('script, style, [data-nom], .tuile-inv .ti-n, .w-t, .sd-t, .nl-t, .tk-t')) textes.push(t.slice(0, 90)); }
  return {page: d.scrollHeight, ecran: innerHeight, depasse: d.scrollHeight - innerHeight, largeur: d.scrollWidth - innerWidth, large, textes: [...new Set(textes)].slice(0, 400),
    vide: !(document.querySelector('main, .ecran') || {}).textContent, titre: ((document.querySelector('.ecran .titre, .ecran h1, .ecran h2') || {}).textContent || '').trim().slice(0, 40)}; })()"""

JS_SUSPECTS = """(() => { const vis = (e) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.pointerEvents !== 'none' && e.offsetParent !== null; };
  const sig = (e) => [e.tagName, e.id || '', (typeof e.className === 'string' ? e.className : '').split(' ').slice(0, 3).join('.'), (e.textContent || e.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 40)].join('|');
  const L = [...document.querySelectorAll('button, [role=button], [role=tab], a')].filter(vis).filter(e => !e.closest('.onglets, #nav-cote, .nav-cote, .haut, header'))
    .filter(e => { if (e.disabled || typeof e.onclick === 'function') return false; if (e.tagName === 'A' && (e.getAttribute('href') || '').trim()) return false;
      if ((e.type === 'submit' || !e.getAttribute('type')) && e.closest('form')) return false; if (e.closest('label, summary')) return false; if (e.getAttribute('aria-selected') === 'true' || e.getAttribute('aria-pressed') === 'true') return false; return true; });
  const vus = new Set(); return L.map(sig).filter(s => !vus.has(s) && vus.add(s)).slice(0, 30); })()"""

JS_TOUCHER = """async (cible) => { const vis = (e) => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 4 && r.height > 4 && cs.visibility !== 'hidden' && cs.display !== 'none' && e.offsetParent !== null; };
  const sig = (e) => [e.tagName, e.id || '', (typeof e.className === 'string' ? e.className : '').split(' ').slice(0, 3).join('.'), (e.textContent || e.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 40)].join('|');
  const e = [...document.querySelectorAll('button, [role=button], [role=tab], a')].filter(vis).find(x => sig(x) === cible && typeof x.onclick !== 'function');
  if (!e) return {absent: true};
  const dors = (ms) => new Promise(r => setTimeout(r, ms));
  const compter = async (geste) => { let n = 0; const mo = new MutationObserver(m => { n += m.length; }); mo.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
    const h0 = location.hash, f0 = window.__nappels || 0; if (geste) geste(); await dors(500); mo.disconnect(); return {n, hash: location.hash !== h0, appels: (window.__nappels || 0) - f0}; };
  const repos = await compter(null);
  const r = await compter(() => e.click());
  const parti = !e.isConnected || !vis(e);                 // le bouton a disparu : il a ferme quelque chose
  return {repos: repos.n, n: r.n, hash: r.hash, appels: r.appels, parti, mort: !parti && !r.hash && r.appels <= 0 && r.n <= repos.n}; }"""


async def main(vue, lang, w, h, routes):
    rapport = {"vue": vue, "langue": lang, "taille": [w, h], "le": time.strftime("%Y-%m-%d %H:%M"), "ecrans": []}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        c = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="en-CA" if lang == "en" else "fr-CA", has_touch=True, is_mobile=True)
        await c.add_init_script("window.__nappels = 0; const f0 = window.fetch; window.fetch = function(){ window.__nappels++; return f0.apply(this, arguments); };")
        pg = await c.new_page()
        err, api = [], []
        pg.on("pageerror", lambda e: err.append(str(e)[:240]))
        async def rep(r):
            try:
                if "/api/" in r.url and r.status >= 400:
                    api.append(f"{r.status} {r.url.split('/api/')[1][:40]}")
                elif "/api/" in r.url and "json" in (r.headers.get("content-type") or ""):
                    t = await r.text()
                    if '"ok": false' in t[:60] or '"ok":false' in t[:60]:
                        api.append(f"refus {r.url.split('/api/')[1][:40]} : {t[:110]}")
            except Exception:
                pass
        pg.on("response", lambda r: asyncio.ensure_future(rep(r)))
        cdp = await c.new_cdp_session(pg)
        await cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 59 if h > 700 else 20, "bottom": 34 if h > 700 else 0, "left": 0, "right": 0}})
        await pg.goto(BASE + "/#accueil"); await pg.wait_for_timeout(5000)
        v = await pg.evaluate("API.admin_vue('%s').then(r => r.vue).catch(e => 'ERREUR ' + e.message)" % vue)
        if lang == "en":
            await pg.evaluate("try { localStorage.setItem('lr_langue', 'en'); } catch (e) {}")
        await pg.reload(); await pg.wait_for_timeout(4000)
        for _ in range(12):                              # la vue simulee doit etre arrivee jusqu'a l'ecran avant de mesurer quoi que ce soit
            if await pg.evaluate("!!(S.forfait && (S.forfait.vue || 'admin') === '%s')" % vue):
                break
            await pg.evaluate("API.forfait().then(f => { S.forfait = f; }).catch(() => {})"); await pg.wait_for_timeout(900)
        else:
            print("ABANDON : la vue", vue, "n'est pas arrivee a l'ecran", flush=True); await b.close(); return
        rapport["vue_serveur"] = v
        rapport["forfait"] = await pg.evaluate("(() => { const f = S.forfait || {}; return {admin: !!f.admin, comps: f.comps, pro: !!f.pro, forfait: f.forfait, vue: f.vue, langue: typeof LANGUE !== 'undefined' ? LANGUE : document.documentElement.lang}; })()")
        print("vue :", v, rapport["forfait"], flush=True)
        restes = []
        for route in routes:
            err.clear(); api.clear()
            await pg.evaluate("location.hash = '#accueil'"); await pg.wait_for_timeout(350)
            await pg.evaluate("location.hash = '#%s'" % route); await pg.wait_for_timeout(4200)
            await pg.evaluate(CACHE); await pg.wait_for_timeout(300)
            ou = await pg.evaluate("location.hash")
            m = await pg.evaluate(JS_MESURES)
            reste = await pg.evaluate("(() => { const r = []; if (document.body.classList.contains('fen-ouverte')) r.push('fiche d annonce'); if (document.querySelector('.vd')) r.push('vente'); const ff = document.querySelector('#fond-feuille'); if (ff && !ff.hidden) r.push('feuille'); return r; })()")
            if reste:
                restes.append(f"{route} : encore ouvert en arrivant : {', '.join(reste)}")
                await pg.evaluate("try { fermerAnnonce(); } catch (e) {}")
            e = {"route": route, "arrive": ou, "titre": m["titre"], "depasse": m["depasse"], "largeur": m["largeur"], "large": m["large"], "erreurs_js": list(dict.fromkeys(err))[:5], "api": list(dict.fromkeys(api))[:6], "morts": [], "vivants": 0}
            if lang == "en":
                e["francais"] = [t for t in m["textes"] if FR.search(t)][:14]
            if ou.lstrip("#").split("/")[0] == route.split("/")[0]:
                sus = await pg.evaluate(JS_SUSPECTS)
                e["suspects"] = len(sus)
                for s in sus:
                    if DANGER.search(s):
                        continue
                    r = await pg.evaluate(JS_TOUCHER, s)
                    if r.get("absent"):
                        continue
                    if r.get("mort"):
                        e["morts"].append(s)
                    else:
                        e["vivants"] += 1
                    await pg.evaluate(CACHE)
                    if (await pg.evaluate("location.hash")) != ou or r.get("hash"):
                        await pg.evaluate("location.hash = '#%s'" % route); await pg.wait_for_timeout(2600); await pg.evaluate(CACHE)
                    else:
                        await pg.wait_for_timeout(150)
            rapport["ecrans"].append(e)
            print(f"{route:38} -> {ou:24} glisse {e['depasse']:5} | js {len(e['erreurs_js'])} | api {len(e['api'])} | suspects {e.get('suspects', 0):2} morts {len(e['morts'])}" + (f" | fr {len(e.get('francais', []))}" if lang == 'en' else ""), flush=True)
        await pg.evaluate("API.admin_vue('admin').catch(() => {})")
        await b.close()
    rapport["restes"] = restes
    for x in restes:
        print("RESTE", x, flush=True)
    json.dump(rapport, open(f"/tmp/audit_ecrans_{vue}_{lang}.json", "w"), ensure_ascii=False, indent=1)
    print("FINI", flush=True)

a = sys.argv[1:]
vue, lang = (a[0] if a else "pro"), (a[1] if len(a) > 1 else "en")
w, h = (int(a[2]), int(a[3])) if len(a) > 3 and a[2].isdigit() else (430, 932)
routes = [x for x in a[2:] if not x.isdigit()] or ROUTES
asyncio.run(main(vue, lang, w, h, routes))
