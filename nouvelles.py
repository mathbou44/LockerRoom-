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
import xml.etree.ElementTree as ET
try:                                         # 9 nov 2026 (Aikido) : XML lu avec defusedxml (pas d'entites ni de bombes XML)
    from defusedxml.ElementTree import fromstring as _xml_sur
except ImportError:                          # pragma: no cover
    _xml_sur = ET.fromstring
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


# 27 oct 2026 - revue legale (Mathieu : « assure-toi que tout est legal ») : Google News (flux RSS pour usage personnel
# et non commercial selon Google) et ESPN (titres gratuits seulement pour un usage non commercial) sont retires.
# On garde le flux public de l'editeur, en TITRE + LIEN vers l'article seulement : pas d'image, pas de texte repris.
SANS_IMAGES = True


# 13 nov 2026 (Mathieu : « pas juste Wikipedia, tous les sites de nouvelles legit et legaux qu'on peut utiliser ») : les
# flux RSS publics des EDITEURS eux-memes, en anglais et en francais (le marche du Quebec), toujours en TITRE + LIEN vers
# l'article (aucun texte, aucune image). Exclus : Google News, ESPN et Yahoo (leurs conditions interdisent l'usage
# commercial). LR_NOUVELLES_SOURCES (cles separees par des virgules) choisit les flux ; l'etat de chacun est garde
# (cache["etat"]) : un flux en panne ou retire est simplement saute.
SOURCES_HOCKEY = [
    ("sportsnet", "Sportsnet", "https://www.sportsnet.ca/hockey/nhl/feed/"),
    ("cbc", "CBC Sports", "https://www.cbc.ca/webfeed/rss/rss-sports-nhl"),
    ("dailyfaceoff", "Daily Faceoff", "https://www.dailyfaceoff.com/feed"),
    ("lapresse", "La Presse", "https://www.lapresse.ca/sports/hockey/rss"),
    ("radiocanada", "Radio-Canada Sports", "https://ici.radio-canada.ca/rss/771"),
    ("habseyes", "Habs Eyes on the Prize", "https://www.habseyesontheprize.com/rss/index.xml"),
    ("thn", "The Hockey News", "https://thehockeynews.com/.rss/full/"),
]


# 27 nov 2026, 21 h 06 (Mathieu, une nouvelle de Radio-Canada Sports sur le cross-country : « en quoi ca a rapport avec le hockey ? ») :
# le flux de Radio-Canada Sports couvre TOUS les sports. D'un flux general, on ne garde que les titres qui parlent de hockey (le mot,
# la ligue, une equipe, un terme du jeu) ; les flux hockey (Sportsnet NHL, La Presse hockey...) ne changent pas.
GENERALES = {"Radio-Canada Sports"}
_HOCKEY_RE = re.compile(r"hockey|\b(LNH|NHL|LHJMQ|LCH|OHL|WHL|AHL|LAH|PWHL|LPHF)\b|coupe stanley|stanley cup|repêchage de la lnh|gardien de but", re.I)
# les equipes : en majuscule (« Championnat canadien » n'est pas le Canadien) et sans les noms partages avec le football ou le baseball
_EQUIPES_RE = re.compile(r"\b(Canadien|Canadiens|Maple Leafs|Sénateurs|Senators|Bruins|Oilers|Flames|Canucks|Islanders|Flyers|Penguins|Capitals|"
                         r"Hurricanes|Blue Jackets|Red Wings|Sabres|Blackhawks|Predators|Avalanche|Kraken|Golden Knights|Ducks|Sharks|Mammoth|"
                         r"Rocket de Laval|Victoire de Montréal|Remparts|Saguenéens)\b")


def parle_hockey(titre):
    t = str(titre or "")
    return bool(_HOCKEY_RE.search(t) or _EQUIPES_RE.search(t))


def sources(sport):
    s = sport if sport in _ESPN else "hockey"
    if s != "hockey":
        return []
    voulues = {x.strip() for x in (os.environ.get("LR_NOUVELLES_SOURCES") or "").split(",") if x.strip()}
    return [(nom, url, "ligue") for cle, nom, url in SOURCES_HOCKEY if not voulues or cle in voulues]


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
    racine = _xml_sur(xml)
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
    import reseau_sur                          # 9 nov 2026 (Aikido, SSRF) : https public seulement (liens venus des flux)
    return reseau_sur.lire(url, headers={"User-Agent": "Mozilla/5.0 (SlabCoach)"}, timeout=timeout)


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
            c = json.load(f) or {}
    except (OSError, ValueError):
        return {}
    for sp, L in (c.get("sports") or {}).items():          # 27 nov 2026 : un vieux cache garde les titres hors hockey d'un flux general
        c["sports"][sp] = [x for x in L or [] if x.get("source") not in GENERALES or parle_hockey(x.get("titre"))]
    return c


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
                if nom in GENERALES and not parle_hockey(x.get("titre")):
                    continue
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
        cache["sports"][sport] = items[:60] or [x for x in (ancien.get(sport) or []) if x.get("source") not in GENERALES or parle_hockey(x.get("titre"))]
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


# 23 nov 2026 (Mathieu, capture « Canadiens Acquire Dylan Larkin » perdue parmi les autres : « les trades des gros joueurs
# doivent stand out des news ; on doit voir que cette news est speciale ; de meme pour tout ce qui est WOW ») : une nouvelle
# est WOW quand elle nomme un GROS joueur et annonce un echange ferme (pas une rumeur), une entree au Temple, un grand honneur,
# un trophee ou un exploit. Elle porte « wow » (type, joueur, et pour un echange : le sens pour ses cartes), et la plus
# recente monte en tete. Une seule par joueur et par type : dix sources qui repetent le meme echange ne font pas dix bandeaux.
WOW_TYPES = ("echange", "temple", "honneur", "trophee", "exploit")
WOW_EPINGLE_H = 48                 # heures en tete de liste
_GROS = {"le": 0.0, "v": ({}, {})}


def _gros_joueurs():
    """({nom normalise: nom} pour un echange, {…} pour le reste). Un gros joueur : un joueur cle (marche_cles), une vedette,
    un Indice eleve ou une grande carriere. Plus large pour un echange (un bon joueur qui change de club, ca compte). 15 min."""
    if time.time() - _GROS["le"] < 900:
        return _GROS["v"]
    _GROS["le"] = time.time()
    ech, gros = {}, {}
    try:
        import marche_cles
        for nom in (marche_cles.lire() or {}).get("cles") or {}:
            ech[norm(nom)] = gros[norm(nom)] = nom
    except Exception:
        pass
    try:
        import deals
        for nom in deals.VEDETTES:
            ech[norm(nom)] = gros[norm(nom)] = nom
    except Exception:
        pass
    try:
        import demande_legale
        import indice_joueurs
        I = (indice_joueurs.lire() or {}).get("indice") or {}
        for nom, e in ((demande_legale.lire() or {}).get("joueurs") or {}).items():
            pts = float((((e or {}).get("nhl") or {}).get("carriere") or {}).get("points") or 0)
            ind = float((I.get(nom) or {}).get("indice") or 0)
            if pts >= 400 or ind >= 60:
                ech[norm(nom)] = nom
            if pts >= 600 or ind >= 70:
                gros[norm(nom)] = nom
    except Exception:
        pass
    _GROS["v"] = (ech, gros)
    return _GROS["v"]


def wow_de(titre, gros=None):
    """Le « wow » d'une manchette -> {type, joueur, sens?, de?, vers?} ou None."""
    try:
        import indice_joueurs as ij
    except Exception:
        return None
    if ij.ECHANGE_FERME.search(titre or ""):          # un echange (poids 0 dans classer_evenement : on le reconnait ici)
        if ij.ECHANGE_RUMEUR.search(titre or ""):
            return None
        ty = "echange"
    else:
        ty, _po = ij.classer_evenement(titre or "")
        if ty not in WOW_TYPES or ty == "echange":
            return None
    ech, autres = gros if gros is not None else _gros_joueurs()
    noms = ech if ty == "echange" else autres
    t = " " + norm(titre) + " "
    j = next((nom for k, nom in noms.items() if f" {k} " in t), None)
    if not j and ty == "echange":                     # « Larkin traded to Canadiens » : le nom de famille seul, s'il n'y en a qu'un
        fam = {}
        for k, nom in noms.items():
            p = k.split()
            if len(p) >= 2 and len(p[-1]) >= 6:
                fam.setdefault(p[-1], []).append(nom)
        j = next((l[0] for w, l in fam.items() if len(l) == 1 and f" {w} " in t), None)
    if not j:
        return None
    out = {"type": ty, "joueur": j}
    if ty == "echange":
        try:
            x = ij.echange_de(j)
            if x:
                out.update(sens=x.get("sens"), de=x.get("de_nom"), vers=x.get("vers_nom"))
            else:                                     # pas encore note : le club d'arrivee nomme dans le titre
                import demande_legale
                club = ij.abrev_equipe(((((demande_legale.lire() or {}).get("joueurs") or {}).get(j) or {}).get("nhl") or {}).get("equipe"))
                S = ij.equipes_du_titre(titre)
                arr = (S - {club}) if club in S else S
                if club and len(arr) == 1:
                    v = next(iter(arr))
                    out.update(sens=ij.sens_echange(club, v), de=ij.EQUIPES_NOM.get(club, club), vers=ij.EQUIPES_NOM.get(v, v))
        except Exception:
            pass
    return out


def marquer_wow(items, langue="fr", gros=None, maintenant=None):
    """Pose « wow » sur UNE nouvelle par (joueur, type) (celle de la langue du client si possible) -> celles a epingler (48 h)."""
    choisis = {}
    for x in items:
        w = wow_de(x.get("titre"), gros)
        if not w:
            continue
        k = (w["joueur"], w["type"])
        if k not in choisis or (langue_de(choisis[k][0]) != langue and langue_de(x) == langue):
            choisis[k] = (x, w)
    lim = (maintenant or datetime.now(timezone.utc)) - timedelta(hours=WOW_EPINGLE_H)
    epingles = []
    for x, w in choisis.values():
        x["wow"] = w
        try:
            h = datetime.fromisoformat(str(x.get("heure") or x.get("date")))
            h = h if h.tzinfo else h.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if h >= lim:
            epingles.append((h, x))
    return [x for _h, x in sorted(epingles, key=lambda e: e[0], reverse=True)][:2]


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
    try:
        epingles = marquer_wow(tous, langue)
    except Exception as e:
        print("Nouvelles (wow) : " + repr(e)[:160], flush=True)
        epingles = []
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
    for x in reversed(epingles):                 # 23 nov 2026 : le WOW recent passe devant tout le reste
        melange = [x] + [y for y in melange if y is not x and y.get("lien") != x.get("lien")]
    melange = melange[:max(n, len(epingles))]
    return {"items": melange, "maj": c.get("maj"), "etat": c.get("etat") or {}}
