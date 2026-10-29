"""
SLABCOACH - le calendrier des sorties de produits (30 oct 2026).

Mathieu : « un petit dashboard avec les release dates des produits Upper Deck et Topps dans mon dashboard admin » et
« une liste des produits populaires sur laquelle je peux cliquer et mettre le fichier, classes par sport ».

Source : le calendrier public de Checklist Insider (page WordPress, lue par son API REST : une date par <h2><time>,
puis les produits de ce jour, chacun avec son lien « ... Guide »). Lu au plus une fois par 12 h, garde sur le disque :
si le site ne repond pas, la derniere liste reste. Rien n'est importe tout seul : l'admin depose le fichier Excel.
"""
import html as _html
import json
import os
import re
import threading
import time
import urllib.request
from datetime import date, datetime

URL = "https://www.checklistinsider.com/ci-api/wp/v2/pages/795"
HOTE = "www.checklistinsider.com"
FRAICHEUR_S = 12 * 3600
UA = "Mozilla/5.0 (SlabCoach release calendar; +https://slabcoach.com)"
_verrou = threading.Lock()

SPORTS = (("hockey", r"\bhockey\b|\bnhl\b"), ("baseball", r"\bbaseball\b|\bmlb\b"), ("basketball", r"\bbasketball\b|\bnba\b|\bwnba\b"),
          ("football", r"\bfootball\b|\bnfl\b"), ("soccer", r"\bsoccer\b|\bfifa\b|premier league|\bmls\b|\buefa\b|bundesliga|la liga"))
MARQUES = (("Upper Deck", r"\bupper deck\b|\bud\b|o-pee-chee|\bopc\b"), ("Topps", r"\btopps\b|\bbowman\b|stadium club"),
           ("Panini", r"\bpanini\b|\bdonruss\b|\bprizm\b|\bselect\b|\boptic\b|\bmosaic\b|national treasures|\bimmaculate\b|\bflawless\b"))
# les lignes les plus recherchees (ce que les collectionneurs et les breakers ouvrent le plus)
PHARES = re.compile(r"series (1|2|one|two)\b|\bextended\b|\bupdate\b|young guns|sp authentic|the cup|\bice\b|artifacts|"
                    r"o-pee-chee(?! platinum)|\bchrome\b|\bbowman\b|stadium club|\bfinest\b|heritage|\bprizm\b|\bselect\b|\boptic\b|"
                    r"\bmosaic\b|\bdonruss\b|national treasures|\bflawless\b|\bimmaculate\b|\bspx\b|synergy|black diamond", re.I)


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "sorties.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


def _texte(h):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def sport_de(nom):
    t = str(nom or "").lower()
    for s, rx in SPORTS:
        if re.search(rx, t):
            return s
    return "autre"


def marque_de(nom):
    t = str(nom or "").lower()
    for m, rx in MARQUES:
        if re.search(rx, t):
            return m
    return "Autre"


def nom_propre(titre):
    """« 2026-27 Upper Deck Series 1 Hockey Guide » -> « 2026-27 Upper Deck Series 1 Hockey »."""
    t = re.sub(r"\s+(guide|checklist|set review|preview|details?)\s*$", "", _texte(titre), flags=re.I)
    return re.sub(r"\s*[|–-]\s*checklist insider.*$", "", t, flags=re.I).strip()


def analyser(rendu):
    """HTML de la page -> [{nom, date (AAAA-MM-JJ ou None = a venir sans date), url}] dans l'ordre de la page."""
    out, vus = [], set()
    blocs = re.split(r"(?=<h2\b)", rendu or "")
    for b in blocs[1:]:
        tete = (re.match(r"<h2\b[^>]*>(.*?)</h2>", b, re.S) or [None, ""])[1]
        m = re.search(r"<time[^>]*datetime=[\"']([0-9]{4}-[0-9]{2}-[0-9]{2})", tete or "")
        if m:
            d = m.group(1)
        elif re.search(r"\btba\b|to be announced|a venir", _texte(tete), re.I):
            d = None
        else:
            continue                                     # un titre qui n'est pas une date (texte de la page)
        for href, txt in re.findall(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", b, re.S):
            nom = nom_propre(txt)
            if len(nom) < 8 or not re.search(r"(19|20)\d{2}", nom):
                continue                                 # l'image du produit (sans texte), « Older Releases »...
            k = (nom.lower(), d)
            if k in vus:
                continue
            vus.add(k)
            out.append({"nom": nom, "date": d, "url": href if href.startswith("https://") else None})
    return out


def _telecharger():
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        if (urllib.request.urlparse(r.geturl()).hostname or "").lower() != HOTE:
            raise ValueError("redirection refusée")
        brut = r.read(6_000_000)
    d = json.loads(brut.decode("utf-8", "ignore"))
    return analyser(((d or {}).get("content") or {}).get("rendered") or "")


def lister(force=False, telecharger=None):
    """{ok, produits: [{nom, date, url, sport, marque, phare}], maj, erreur?} ; gardee 12 h (et sur le disque)."""
    d = _lire()
    if d.get("produits") and not force and time.time() - d.get("le", 0) < FRAICHEUR_S:
        return {"ok": True, "produits": d["produits"], "maj": d.get("maj"), "cache": True}
    try:
        l = (telecharger or _telecharger)()
        if not l:
            raise ValueError("calendrier vide (la page a peut-être changé)")
    except Exception as e:
        if d.get("produits"):
            return {"ok": True, "produits": d["produits"], "maj": d.get("maj"), "erreur": str(e)[:160]}
        return {"ok": False, "produits": [], "erreur": "Calendrier des sorties injoignable : " + str(e)[:160]}
    for x in l:
        x.update(sport=sport_de(x["nom"]), marque=marque_de(x["nom"]), phare=bool(PHARES.search(x["nom"])))
    with _verrou:
        d = {"le": time.time(), "maj": datetime.now().isoformat(timespec="minutes"), "produits": l}
        _ecrire(d)
    return {"ok": True, "produits": l, "maj": d["maj"]}


def jours(d, auj=None):
    try:
        return (date.fromisoformat(str(d)[:10]) - (auj or date.today())).days
    except (TypeError, ValueError):
        return None
