# SlabCoach - 20 nov 2026 (Mathieu : « toutes les bonnes notes sur notre site web en slide show avec le commentaire pour la
# preuve sociale ? Et le nombre de download ? ... que ca se fasse automatiquement »)
#
# Les VRAIES notes de l'App Store, lues chez Apple (jamais ecrites a la main : « pas de faux temoignages ») :
#   - la note moyenne et le nombre de notes : l'API publique iTunes Lookup ;
#   - les commentaires : le flux public des avis d'Apple (Canada et Etats-Unis), les plus recents.
# Mis en cache sur le disque, relu au plus aux 6 heures, en arriere-plan (la page n'attend jamais Apple).
# Le site n'affiche rien tant qu'il n'y a pas assez de vraies notes (un « 5,0 sur 2 notes » fait moins vrai que rien).
# Les telechargements : Apple ne les publie pas ; on montre plutot les comptes SlabCoach (mesure a nous, au-dessus d'un seuil).
import html
import json
import os
import threading
import time
import urllib.request

import reseau

APP_ID = os.environ.get("APP_STORE_APPLE_ID") or "6827726629"     # le meme numero que codemagic.yaml (pas secret)
PAYS = ("ca", "us")
RAFRAICHIR_S = 6 * 3600
MIN_NOTES = int(os.environ.get("LR_AVIS_MIN_NOTES") or 5)          # note moyenne affichee a partir de 5 notes
MIN_AVIS = int(os.environ.get("LR_AVIS_MIN_AVIS") or 3)            # diaporama a partir de 3 bons commentaires
MIN_COMPTES = int(os.environ.get("LR_PREUVE_MIN_COMPTES") or 250)  # « X collectionneurs » a partir de 250 comptes
LIEN_APP = f"https://apps.apple.com/ca/app/id{APP_ID}"

_verrou = threading.Lock()
_en_cours = [False]


def _fichier():
    base = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "avis_app.json")


def _json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SlabCoach/1.0", "Accept": "application/json"})
    with reseau.ouvrir(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", "replace") or "{}")


def _txt(x):
    return (x or {}).get("label", "") if isinstance(x, dict) else str(x or "")


def lire_flux(d, pays):
    """Le flux d'Apple -> [{id, note, titre, texte, auteur, version, date, pays}]. La 1re entree est parfois l'app elle-meme."""
    e = ((d or {}).get("feed") or {}).get("entry") or []
    if isinstance(e, dict):
        e = [e]
    out = []
    for x in e:
        if not isinstance(x, dict) or "im:rating" not in x:
            continue
        try:
            note = int(_txt(x.get("im:rating")))
        except ValueError:
            continue
        out.append({"id": _txt(x.get("id")), "note": note, "titre": _txt(x.get("title")).strip(),
                    "texte": _txt(x.get("content")).strip(), "auteur": _txt((x.get("author") or {}).get("name")).strip(),
                    "version": _txt(x.get("im:version")), "date": _txt(x.get("updated"))[:10], "pays": pays})
    return out


def lire_lookup(d):
    res = (d or {}).get("results") or []
    r = res[0] if res else {}
    return {"moyenne": r.get("averageUserRating"), "nb": r.get("userRatingCount") or 0, "existe": bool(res)}


def rafraichir():
    """Relit Apple ; garde l'ancien cache si Apple ne repond pas."""
    avis, notes = [], {"moyenne": None, "nb": 0}
    tot_n, tot_s = 0, 0.0
    existe, repondu = False, False                  # 24 nov 2026 : l'app est-elle publiee ? (Apple renvoie sa fiche, ou rien)
    for p in PAYS:
        try:
            l = lire_lookup(_json(f"https://itunes.apple.com/lookup?id={APP_ID}&country={p}"))
            repondu, existe = True, existe or l["existe"]
            if l["nb"] and l["moyenne"]:
                tot_n += int(l["nb"])
                tot_s += float(l["moyenne"]) * int(l["nb"])
        except Exception:
            pass
        try:
            avis += lire_flux(_json(f"https://itunes.apple.com/{p}/rss/customerreviews/sortby=mostrecent/id={APP_ID}/json"), p)
        except Exception:
            pass
    if tot_n:
        notes = {"moyenne": round(tot_s / tot_n, 1), "nb": tot_n}
    vus, uniques = set(), []
    for a in avis:
        if a["id"] and a["id"] not in vus:
            vus.add(a["id"])
            uniques.append(a)
    vieux = charger()
    en_ligne_ = existe if repondu else bool(vieux.get("en_ligne"))        # Apple muet : on garde ce qu'on savait
    d = {"maj": time.time(), "notes": notes, "avis": uniques[:200], "en_ligne": en_ligne_}
    if not uniques and not tot_n:
        if vieux.get("avis") or (vieux.get("notes") or {}).get("nb"):
            vieux["maj"] = time.time()      # Apple muet : on garde ce qu'on avait, on reessaie dans 6 h
            vieux["en_ligne"] = en_ligne_
            d = vieux
    try:
        tmp = _fichier() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _fichier())
    except OSError:
        pass
    return d


def charger():
    try:
        with open(_fichier(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def donnees():
    """Le cache, et un rafraichissement en arriere-plan s'il a plus de 6 heures (la page ne l'attend pas)."""
    d = charger()
    if time.time() - float(d.get("maj") or 0) > RAFRAICHIR_S and os.environ.get("LOCKERROOM_TACHES", "1") != "0":
        with _verrou:
            if not _en_cours[0]:
                _en_cours[0] = True

                def _f():
                    try:
                        rafraichir()
                    finally:
                        _en_cours[0] = False
                threading.Thread(target=_f, daemon=True).start()
    return d


def en_ligne():
    """24 nov 2026 (revue avant l'envoi a Apple) : True seulement quand Apple renvoie la fiche de l'app (elle est publiee).
    Tant qu'elle ne l'est pas, le lien « Noter SlabCoach sur l'App Store » mene a une page qui n'existe pas : l'app ne le
    montre pas (un lien mort pendant l'examen = un motif de refus). Il apparait seul, au plus 6 heures apres la publication."""
    try:
        return bool(donnees().get("en_ligne"))
    except Exception:
        return False


def bons_avis(d):
    """4 et 5 etoiles, avec un vrai commentaire (au moins 25 caracteres), du plus recent au plus ancien."""
    l = [a for a in (d.get("avis") or []) if a.get("note", 0) >= 4 and len(a.get("texte") or "") >= 25]
    return sorted(l, key=lambda a: a.get("date") or "", reverse=True)[:16]


def _etoiles(n):
    n = max(0, min(5, int(n)))
    return '<span class="av-et" aria-label="%d / 5">%s<i>%s</i></span>' % (n, "★" * n, "★" * (5 - n))


def _court(t, n=220):
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def _nfr(n):
    return f"{int(n):,}".replace(",", "\u202f")


def _mfr(m):
    return f"{float(m):.1f}".replace(".", ",")


def nb_comptes():
    try:
        import comptes as _c
        ix = _c._index()
        return sum(1 for e in ix.values() if not e.get("renvoi") and (e.get("env") or "production") not in ("sandbox", "demo"))
    except Exception:
        return 0


def html_bandeau(d=None, comptes=None):
    """La petite ligne sous les boutons du haut : « ★ 4,8 · 63 notes sur l'App Store · 1 200 collectionneurs ». Vide sinon."""
    d = d if d is not None else donnees()
    n = d.get("notes") or {}
    morceaux = []
    if (n.get("nb") or 0) >= MIN_NOTES and n.get("moyenne"):
        m, nb = float(n["moyenne"]), int(n["nb"])
        morceaux.append(f'<a class="av-b" href="{LIEN_APP}" target="_blank" rel="noopener"><span class="av-et">★</span> '
                        f'<b><span class="fr">{_mfr(m)}</span><span class="en">{m}</span></b> '
                        f'<span class="fr">· {_nfr(nb)} notes sur l’App Store</span><span class="en">· {nb:,} ratings on the App Store</span></a>')
    c = nb_comptes() if comptes is None else comptes
    if c >= MIN_COMPTES:
        arr = (c // 50) * 50 if c < 1000 else (c // 100) * 100
        morceaux.append(f'<span class="av-b"><b><span class="fr">{_nfr(arr)}+</span><span class="en">{arr:,}+</span></b> '
                        f'<span class="fr">collectionneurs</span><span class="en">collectors</span></span>')
    return f'<div class="av-ligne">{"".join(morceaux)}</div>' if morceaux else ""


def html_section(d=None):
    """Le diaporama des bons commentaires (defilement doux en CSS, pause au survol ; immobile si l'appareil le demande)."""
    d = d if d is not None else donnees()
    l = bons_avis(d)
    if len(l) < MIN_AVIS:
        return ""
    n = d.get("notes") or {}
    tete = ""
    if (n.get("nb") or 0) >= MIN_NOTES and n.get("moyenne"):
        m = float(n["moyenne"])
        tete = (f'<p class="av-moy"><b><span class="fr">{_mfr(m)}</span><span class="en">{m:.1f}</span></b> {_etoiles(round(m))} '
                f'<span class="fr">{_nfr(n["nb"])} notes</span><span class="en">{int(n["nb"]):,} ratings</span></p>')
    cartes = "".join(
        f'<figure class="av-c">{_etoiles(a["note"])}'
        f'{"<b>" + html.escape(_court(a.get("titre"), 70)) + "</b>" if a.get("titre") else ""}'
        f'<blockquote>{html.escape(_court(a.get("texte")))}</blockquote>'
        f'<figcaption>{html.escape(_court(a.get("auteur"), 30))} · App Store</figcaption></figure>' for a in l)
    piste = cartes + cartes.replace('<figure class="av-c">', '<figure class="av-c" aria-hidden="true">')   # 2 fois : la boucle sans saut
    duree = max(30, 7 * len(l))
    return (f'<section id="avis"><div class="conteneur">'
            f'<p class="kicker holo-t"><span class="fr">Ils en parlent</span><span class="en">What collectors say</span></p>'
            f'<h2><span class="fr">Les collectionneurs nous donnent leur note.</span><span class="en">Collectors rate us.</span></h2>{tete}'
            f'<div class="av-fen"><div class="av-piste" style="--av-d:{duree}s">{piste}</div></div>'
            f'<p class="note"><span class="fr">Vrais avis de l’App Store, mis à jour tout seuls.</span><span class="en">Real App Store reviews, updated automatically.</span> '
            f'<a href="{LIEN_APP}" target="_blank" rel="noopener"><span class="fr">Tous les avis</span><span class="en">All reviews</span> →</a></p>'
            f'</div></section>')


CSS = """<style>
.av-ligne{display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:14px; font-size:14px; color:var(--doux, #a9a9b8)}
.av-b{display:inline-flex; align-items:center; gap:6px; color:inherit; text-decoration:none}
.av-b b{color:var(--texte, #fff)}
.av-et{color:#ffcc4d; letter-spacing:1px}
.av-et i{font-style:normal; color:rgba(255,255,255,.18)}
#avis .av-moy{display:flex; align-items:center; gap:10px; margin:6px 0 0; font-size:15px}
#avis .av-moy b{font-size:28px}
.av-fen{overflow:hidden; margin-top:22px; -webkit-mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
  mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent)}
.av-piste{display:flex; gap:16px; width:max-content; animation:av-def var(--av-d, 60s) linear infinite}
.av-fen:hover .av-piste{animation-play-state:paused}
.av-c{margin:0; width:300px; flex:none; display:flex; flex-direction:column; gap:8px; padding:18px; border-radius:18px;
  background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.09)}
.av-c b{font-size:15px}
.av-c blockquote{margin:0; font-size:14.5px; line-height:1.45; color:var(--texte, #fff); opacity:.92}
.av-c figcaption{margin-top:auto; font-size:12.5px; color:var(--doux, #a9a9b8)}
@keyframes av-def{to{transform:translateX(calc(-50% - 8px))}}
@media (prefers-reduced-motion:reduce){.av-piste{animation:none} .av-fen{overflow-x:auto}}
@media (max-width:600px){.av-c{width:250px}}
</style>"""


def injecter(page_html, contenu_html):
    """Remplit {{AVIS_LIGNE}} et {{AVIS_SECTION}} du contenu ; ajoute le CSS seulement s'il y a quelque chose a montrer."""
    if "{{AVIS_LIGNE}}" not in contenu_html and "{{AVIS_SECTION}}" not in contenu_html:
        return page_html
    try:
        d = donnees()
        ligne, sect = html_bandeau(d), html_section(d)
    except Exception:
        ligne, sect = "", ""
    page_html = page_html.replace("{{AVIS_LIGNE}}", ligne).replace("{{AVIS_SECTION}}", sect)
    if ligne or sect:
        page_html = page_html.replace("</head>", CSS + "</head>", 1)
    return page_html
