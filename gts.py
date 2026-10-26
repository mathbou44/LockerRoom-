"""
LOCKERROOM - les checklists Excel de GTS Distribution (gogts.net) (25 oct 2026).

Mathieu : « essaie d'aller chercher toutes les checklists comme celle-ci » (gogts.net : « PDF Checklist »,
« EXCEL Checklist ») et « c'est l'admin (moi) qui les telecharge pour eviter qu'on ait n'importe quoi ».

  - le serveur lit la categorie « Hockey Card Checklists » de gogts.net (quelques pages, gardee 12 h) ;
  - pour chaque produit : deja au catalogue ou pas ;
  - l'admin touche « Importer » (ou « Importer les nouveaux ») : le serveur telecharge l'Excel de la page
    du produit et l'importe (checklist_import : sous-ensembles, recrues, numerotation, cotes hobby).
Rien n'est importe tout seul : la liste des nouveautes apparait dans « Produits a ajouter », l'admin decide.
Seul gogts.net est contacte (adresses verifiees), fichiers de 12 Mo au plus.
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HOTES = ("gogts.net", "www.gogts.net")
CATEGORIES = {"hockey": "https://gogts.net/trading-card-checklists/hockey-card-checklists/"}
FRAICHEUR_S = 12 * 3600
MAX_PAGES = 12
MAX_OCTETS = 12_000_000
UA = "Mozilla/5.0 (SlabCoach checklist import; +https://slabcoach.com)"
_verrou = threading.Lock()

_RE_PAGE = re.compile(r"""href=["'](https?://(?:www\.)?gogts\.net/([a-z0-9][a-z0-9-]*checklists?[a-z0-9-]*)/?)["']""", re.I)
_RE_XLSX = re.compile(r"""href=["'](https?://(?:www\.)?gogts\.net/wp-content/uploads/[^"'<>]+?\.(?:xlsx|xlsm|csv))["']""", re.I)
_RE_SAISON = re.compile(r"^((?:19|20)\d{2})(?:-(\d{2}))?-")
_PAS_PRODUIT = re.compile(r"^(trading-card-checklists|checklists?|hockey-card-checklists|.*-card-checklists)$")


def _sur(url):
    try:
        u = urllib.parse.urlparse(str(url))
    except ValueError:
        return False
    return u.scheme == "https" and (u.hostname or "").lower() in HOTES


def _get(url, max_octets=3_000_000, timeout=25):
    if not _sur(url):
        raise ValueError("adresse refusée (gogts.net seulement)")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if not _sur(r.geturl()):
            raise ValueError("redirection refusée")
        brut = r.read(max_octets + 1)
    if len(brut) > max_octets:
        raise ValueError("fichier trop lourd")
    return brut


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "gts_checklists.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


_MAJ = {"ud": "UD", "sp": "SP", "spx": "SPx", "opc": "OPC", "o-pee-chee": "O-Pee-Chee", "nhl": "NHL", "ahl": "AHL", "pwhl": "PWHL",
        "chl": "CHL", "usa": "USA", "ice": "ICE", "mvp": "MVP", "ii": "II", "iii": "III", "&": "&"}


def nom_de_slug(slug):
    """« 2026-27-upper-deck-series-1-nhl-hockey-cards-checklist » -> « 2026-27 Upper Deck Series 1 » ;
    « 2024-25-upper-deck-series-two-... » -> « 2024-25 Upper Deck Series 2 »."""
    s = str(slug or "").lower().strip("/")
    m = _RE_SAISON.match(s + "-")
    if not m:
        return None, None
    saison = m.group(1) + ("-" + m.group(2) if m.group(2) else "")
    reste = s[len(saison):].strip("-")
    reste = re.sub(r"-(nhl-)?hockey(-trading)?(-cards?)?(-checklists?)?$|-(cards?-)?checklists?$", "", reste)
    reste = reste.replace("o-pee-chee", "o§pee§chee")
    mots = [w.replace("§", "-") for w in reste.split("-") if w]
    mots = [w for w in mots if w not in ("nhl", "hockey", "cards", "card", "checklist", "checklists", "trading")]
    txt = " ".join(mots)
    txt = re.sub(r"\bseries one\b", "series 1", txt)
    txt = re.sub(r"\bseries two\b", "series 2", txt)
    nom = " ".join(_MAJ.get(w, w if any(ch.isdigit() for ch in w) else w.capitalize()) for w in txt.split())
    return (saison + " " + nom).strip(), saison


def _page(sport, n):
    base = CATEGORIES[sport]
    url = base if n == 1 else base + f"page/{n}/"
    html = _get(url).decode("utf-8", "ignore")
    out = []
    for url_p, slug in _RE_PAGE.findall(html):
        if _PAS_PRODUIT.match(slug.lower()):
            continue
        nom, saison = nom_de_slug(slug)
        if nom:
            out.append({"url": url_p.rstrip("/") + "/", "slug": slug.lower(), "nom": nom, "saison": saison})
    return out


def saison_min(maint=None):
    """La plus vieille saison qu'on garde : l'avant-derniere (2024-25 en octobre 2026)."""
    maint = maint or datetime.now()
    a = (maint.year if maint.month >= 6 else maint.year - 1) - 2
    return a


def lister(sport="hockey", force=False, maint=None):
    """[{url, slug, nom, saison}] des checklists GTS recentes (gardee 12 h)."""
    if sport not in CATEGORIES:
        return {"ok": True, "produits": [], "maj": None}
    d = _lire()
    e = d.get(sport) or {}
    if e and not force and time.time() - e.get("le", 0) < FRAICHEUR_S:
        return {"ok": True, "produits": e.get("produits") or [], "maj": e.get("maj"), "cache": True}
    a_min = saison_min(maint)
    vus, prods, erreur = set(), [], None
    with ThreadPoolExecutor(max_workers=4) as ex:
        for debut in range(1, MAX_PAGES + 1, 4):
            pages = list(ex.map(lambda n: _essai_page(sport, n), range(debut, min(debut + 4, MAX_PAGES + 1))))
            fini = False
            for p in pages:
                if isinstance(p, Exception):
                    erreur = erreur or type(p).__name__
                    fini = True
                    continue
                if not p:
                    fini = True
                for x in p:
                    if x["slug"] not in vus:
                        vus.add(x["slug"])
                        prods.append(x)
                if p and all(int(x["saison"][:4]) < a_min for x in p):
                    fini = True                        # pages triees du plus recent au plus vieux
            if fini:
                break
    prods = [x for x in prods if int(x["saison"][:4]) >= a_min]
    prods.sort(key=lambda x: (x["saison"], x["nom"]), reverse=True)
    if not prods and erreur:
        return {"ok": False, "erreur": "gogts.net injoignable (" + erreur + ")", "produits": e.get("produits") or []}
    with _verrou:
        d = _lire()
        d[sport] = {"le": time.time(), "maj": datetime.now().isoformat(timespec="minutes"), "produits": prods}
        _ecrire(d)
    return {"ok": True, "produits": prods, "maj": d[sport]["maj"]}


def _essai_page(sport, n):
    try:
        return _page(sport, n)
    except Exception as e:                              # page absente (fin de la liste) ou reseau
        if getattr(e, "code", None) == 404:
            return []
        return e


def excel_de(url_page):
    """L'adresse de l'« EXCEL Checklist » d'une page produit GTS (ou None)."""
    html = _get(url_page).decode("utf-8", "ignore")
    liens = _RE_XLSX.findall(html)
    liens.sort(key=lambda u: (not u.lower().endswith(".xlsx"), "checklist" not in u.lower()))
    return liens[0] if liens else None


def telecharger(url_page):
    """-> (octets, nom_du_fichier). ValueError si pas d'Excel sur la page."""
    u = excel_de(url_page)
    if not u:
        raise ValueError("pas de lien Excel sur cette page GTS")
    brut = _get(u, max_octets=MAX_OCTETS, timeout=40)
    return brut, urllib.parse.unquote(u.rsplit("/", 1)[-1])
