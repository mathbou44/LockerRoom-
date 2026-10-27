"""
LOCKERROOM - nouvelles des sports et du hobby pour l'accueil (23 oct 2026).

Mathieu : « ajouter les fonctions de nouvelles et suivi d'heures a l'accueil
[de SlabCoach] ... varie les sources ». Repris de Hall of Cardz (sa version
test), pour tous les sports de SlabCoach.

  - Sources (gratuites, publiques) : ESPN (un flux par ligue), Google News en
    anglais ET en francais (le vrai editeur : TSN, RDS, La Presse, NHL.com...),
    et le hobby (cartes de la ligue). Images : celle de l'article quand le flux
    en donne une.
  - Un seul cache pour tout le serveur (les nouvelles sont les memes pour tous),
    relu au plus toutes les 2 h, en arriere-plan. Chaque client voit les sports
    de SON inventaire, ses joueurs d'abord.
Aucun appel ne bloque l'ecran : sans cache, la liste est vide et se remplit.
"""
import json
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

DOSSIER = os.path.dirname(os.path.abspath(__file__))
FRAICHEUR_S = 2 * 3600
JOURS = 7
_verrou = threading.Lock()
_ETAT = {"en_cours": False}

_ESPN = {"hockey": "nhl", "football": "nfl", "basketball": "nba", "baseball": "mlb"}
_LIGUE_FR = {"hockey": "LNH", "football": "NFL", "basketball": "NBA", "baseball": "MLB"}
_LIGUE_EN = {"hockey": "NHL", "football": "NFL", "basketball": "NBA", "baseball": "MLB"}
_HOBBY = {"hockey": "hockey cards", "football": "football cards", "basketball": "basketball cards", "baseball": "baseball cards"}


def _gn(q, fr=False):
    hl, ceid = ("fr-CA", "CA:fr") if fr else ("en-CA", "CA:en")
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={hl}&gl=CA&ceid={ceid}"


# 27 oct 2026 - revue legale (Mathieu : « assure-toi que tout est legal ») : Google News (flux RSS pour usage personnel
# et non commercial selon Google) et ESPN (titres gratuits seulement pour un usage non commercial) sont retires.
# On garde le flux public de l'editeur, en TITRE + LIEN vers l'article seulement : pas d'image, pas de texte repris.
SANS_IMAGES = True


def sources(sport):
    s = sport if sport in _ESPN else "hockey"
    return [("Sportsnet", "https://www.sportsnet.ca/hockey/nhl/feed/", "ligue")] if s == "hockey" else []


_CLASSES = [
    ("echange", 0, "Échange", r"\btrade[sd]?\b|\bacquires?\b|\bacquired\b|\bdealt\b|échang"),
    ("blessure", -10, "Blessure", r"injur|\bIR\b|day-to-day|surgery|concussion|upper-body|lower-body|blessé|blessure|infirmerie|opéré|commotion"),
    ("contrat", 10, "Contrat", r"extension|\bcontract\b|signs? .*(deal|year)|prolongation|contrat"),
    ("exploit", 8, "Exploit", r"hat trick|career[- ]high|milestone|record|first (career )?(goal|touchdown|home run)|player of the (week|month)|tour du chapeau|triple-double"),
    ("negatif", -12, "Mauvaise nouvelle", r"waive|waivers|sent down|demot|suspend|healthy scratch|ballottage|rétrogradé"),
]
_CLASSES_RE = [(t, imp, lib, re.compile(rx, re.I)) for t, imp, lib, rx in _CLASSES]
_RE_IMG = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)
_NS_MEDIA = "{http://search.yahoo.com/mrss/}"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def classer(titre):
    for t, imp, lib, rx in _CLASSES_RE:
        if rx.search(titre or ""):
            return t, imp, lib
    return None


def _image(it):
    for tag in ("content", "thumbnail"):
        for m in it.iter(_NS_MEDIA + tag):
            u = m.get("url")
            if u and re.search(r"\.(jpe?g|png|webp)|image", u, re.I):
                return u
    u = (it.findtext("image") or "").strip()          # ESPN : <image> dans chaque article
    if u.startswith("http"):
        return u
    enc = it.find("enclosure")
    if enc is not None and str(enc.get("type") or "").startswith("image"):
        return enc.get("url")
    for champ in ("{http://purl.org/rss/1.0/modules/content/}encoded", "description"):
        m = _RE_IMG.search(it.findtext(champ) or "")
        if m and not m.group(1).startswith("data:"):
            return m.group(1)
    return None


def lire_rss(xml, jours=JOURS):
    """[{titre, date, heure, lien, editeur, image}] recents d'un flux RSS."""
    racine = ET.fromstring(xml)
    limite = datetime.now(timezone.utc) - timedelta(days=jours)
    out = []
    for it in racine.iter("item"):
        titre = (it.findtext("title") or "").strip()
        try:
            d = parsedate_to_datetime(it.findtext("pubDate") or "")
        except Exception:
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if d < limite or not titre:
            continue
        src = it.find("source")
        editeur = (src.text or "").strip() if src is not None and src.text else None
        if editeur and titre.endswith(" - " + editeur):
            titre = titre[: -len(editeur) - 3].strip()
        out.append({"titre": titre[:200], "date": d.date().isoformat(), "heure": d.isoformat(), "lien": lien if re.match(r"https?://", lien := (it.findtext("link") or "").strip(), re.I) else "",
                    "editeur": editeur, "image": None if SANS_IMAGES else _image(it)})
    return out


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SlabCoach)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


_RE_OG = re.compile(r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)["'][^>]+content=["']([^"']+)["']|<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["'](?:og:image|twitter:image)["']""", re.I)


def _og_image(url, lecteur=None):
    if not url or not str(url).startswith("http"):
        return None
    try:
        brut = (lecteur or (lambda u: _get(u, timeout=6)))(url)
        html = brut[:200_000].decode("utf-8", "ignore") if isinstance(brut, bytes) else str(brut)[:200_000]
    except Exception:
        return None
    m = _RE_OG.search(html)
    u = (m.group(1) or m.group(2)) if m else None
    return u if u and u.startswith("https://") else None


def chemin_cache():
    import comptes
    return os.path.join(comptes.DONNEES, "nouvelles_cache.json")


def lire_cache():
    try:
        with open(chemin_cache(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def rafraichir(sports_voulus=("hockey", "football", "basketball", "baseball"), lecteur=None):
    """Relit les flux de chaque sport. Retourne le cache ecrit."""
    lecteur = lecteur or _get
    ancien = (lire_cache().get("sports") or {})          # un flux en panne ne vide jamais l'accueil
    cache = {"maj": datetime.now().isoformat(timespec="seconds"), "sports": {}, "etat": {}}
    for sport in sports_voulus:
        items, vus = [], set()
        for nom, url, genre in sources(sport):
            try:
                lus = lire_rss(lecteur(url))
                cache["etat"][f"{sport}:{nom}"] = "ok"
            except Exception as e:
                cache["etat"][f"{sport}:{nom}"] = type(e).__name__
                continue
            for x in lus[:30]:
                cle = norm(x["titre"])[:60]
                if not cle or cle in vus:
                    continue
                vus.add(cle)
                cl = classer(x["titre"])
                items.append(dict(x, source=x.pop("editeur") or nom.replace(" FR", ""), sport=sport, genre=genre,
                                  langue="fr" if nom.endswith(" FR") else "en",
                                  type=cl[0] if cl else ("marche" if genre == "hobby" else "ligue"),
                                  libelle=cl[2] if cl else ("Marché des cartes" if genre == "hobby" else _LIGUE_FR[sport]),
                                  impact=cl[1] if cl else 0))
            time.sleep(0.3)
        items.sort(key=lambda x: x["heure"], reverse=True)
        deja = {x.get("lien"): x.get("image") for x in (ancien.get(sport) or []) if x.get("image")}
        for x in items:
            if not x.get("image") and deja.get(x.get("lien")):
                x["image"] = deja[x["lien"]]
        cache["sports"][sport] = items[:60] or ancien.get(sport) or []
    _ecrire_cache(cache)
    if SANS_IMAGES:
        return cache
    # 24 oct 2026 (Mathieu : « toujours avoir une image ») : 2e passe, la photo de l'article (og:image) quand le flux
    # n'en donne pas - liens directs seulement (pas Google News), 12 par sport, 6 s chacun ; l'accueil a deja ses nouvelles
    change = False
    for sport, items in cache["sports"].items():
        faits = 0
        for x in items[:40]:
            if x.get("image") or faits >= 12 or "news.google." in str(x.get("lien") or ""):
                continue
            faits += 1
            img = _og_image(x.get("lien"), None if lecteur is _get else lecteur)
            if img:
                x["image"], change = img, True
    if change:
        _ecrire_cache(cache)
    return cache


def _ecrire_cache(cache):
    tmp = chemin_cache() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, chemin_cache())


def rafraichir_si_besoin():
    """Lance une relecture en arriere-plan si le cache a plus de 2 h (jamais deux a la fois)."""
    c = lire_cache()
    try:
        age = time.time() - datetime.fromisoformat(c["maj"]).timestamp()
    except Exception:
        age = 1e9
    if age < FRAICHEUR_S:
        return False
    with _verrou:
        if _ETAT["en_cours"]:
            return False
        _ETAT["en_cours"] = True

    def tache():
        try:
            rafraichir()
        except Exception as e:
            print("Nouvelles : " + str(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="nouvelles").start()
    return True


_RE_FR = re.compile(r"[àâçéèêëîïôûù]|\b(le|la|les|des|du|une|pour|avec|dans|sur|est|au|aux|et)\b", re.I)


def langue_de(x):
    """fr / en d'une nouvelle (les anciens caches n'ont pas le champ : on devine au titre)."""
    return x.get("langue") or ("fr" if len(_RE_FR.findall(x.get("titre") or "")) >= 2 else "en")


def _melanger(liste, n):
    a_moi = [x for x in liste if x.get("joueur")]
    par_source = {}
    for x in liste:
        if not x.get("joueur"):
            par_source.setdefault(x["source"], []).append(x)
    melange = list(a_moi[:6])
    while len(melange) < n and any(par_source.values()):
        for k in list(par_source):
            if par_source[k]:
                melange.append(par_source[k].pop(0))
    return melange[:n]


def pour(sports_client, joueurs=(), n=16, langue="fr"):
    """Nouvelles d'un client : ses sports, celles qui nomment SES joueurs d'abord, sources melangees.
    24 oct 2026 (Mathieu) : client anglophone = nouvelles en anglais ; francophone = bilingue (FR / EN en alternance)."""
    c = lire_cache()
    noms = {norm(j): j for j in joueurs or () if len(norm(j).split()) >= 2}
    tous = []
    for s in sports_client or ["hockey"]:
        for x in (c.get("sports") or {}).get(s) or []:
            t = " " + norm(x["titre"]) + " "
            j = next((v for k, v in noms.items() if f" {k} " in t), None)
            y = dict(x, joueur=j)
            if SANS_IMAGES:
                y.pop("image", None)               # anciens caches : jamais d'image d'article a l'ecran
            if "news.google." in str(y.get("lien") or "") or y.get("source") in ("ESPN", "Google News", "Hobby"):
                continue                           # anciens caches : sources retirees
            tous.append(y)
    en = [x for x in tous if langue_de(x) == "en"]
    fr = [x for x in tous if langue_de(x) == "fr"]
    if langue == "en":
        melange = _melanger(en or tous, n)
    else:
        a, b = _melanger(fr, n), _melanger(en, n)
        melange = []
        for i in range(n):                       # FR, EN, FR, EN... (une langue manque : l'autre complete)
            for lst in ((a, b) if i % 2 == 0 else (b, a)):
                if lst:
                    x = lst.pop(0)
                    if x not in melange:
                        melange.append(x)
                    break
        melange = melange[:n]
    avec = next((k for k, x in enumerate(melange) if x.get("image")), None)
    if avec:                                     # la premiere nouvelle a l'ecran : une avec photo si possible
        melange.insert(0, melange.pop(avec))
    return {"items": melange, "maj": c.get("maj"), "etat": c.get("etat") or {}}
