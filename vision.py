"""
LOCKERROOM - « Une photo, un bouton » : la carte reconnue sur la photo
(23 oct 2026).

Mathieu : "garde un modele avance pour limiter les erreurs de lecture le plus
possible. J'aime mieux payer plus cher et donner une experience parfaite".

Principe (grand public) :
  - la cle Anthropic reste SUR LE SERVEUR (variable d'environnement
    ANTHROPIC_API_KEY chez l'hebergeur ; sur le PC de Mathieu : le fichier
    anthropic_cle.txt a cote du code, jamais sur GitHub). Le telephone ne la
    voit jamais : il envoie la photo a NOTRE serveur, qui appelle Anthropic.
  - modele avance (Opus) : le devant ET le dos (numero, annee, set, tirage
    sont souvent au dos). Chaque champ revient avec sa confiance ; sous
    SEUIL_CONFIANCE, l'ecran le marque « a verifier » au lieu d'inventer.
  - protections : compte connecte (serveur), quota par forfait et par mois,
    plafond de depense du serveur par mois, meme photo jamais repayee (cache).

Aucune dependance : appel HTTPS direct (urllib), comme le reste de l'app.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_CLE_LOCALE = os.path.join(DOSSIER, "anthropic_cle.txt")
URL = "https://api.anthropic.com/v1/messages"
VERSION_API = "2023-06-01"
MODELE = os.environ.get("LR_VISION_MODELE") or "claude-opus-5-5"
# $ US par million de jetons (Opus 5.5, oct 2026) - sert au plafond de depense
PRIX_ENTREE, PRIX_SORTIE = 4.0, 20.0
SEUIL_CONFIANCE = 0.85
MAX_PHOTOS = 2
MAX_OCTETS_PHOTO = 4_500_000          # apres decodage ; l'ecran reduit deja a ~1600 px
QUOTA_GRATUIT = int(os.environ.get("LR_VISION_GRATUIT") or 25)        # photos / mois / compte gratuit
PLAFOND_SERVEUR_USD = float(os.environ.get("LR_VISION_PLAFOND_USD") or 50)
_verrou = threading.Lock()

CHAMPS = ("sport", "joueur", "annee", "marque", "set_nom", "parallele", "numero", "tirage", "numero_serie",
          "auto", "relique", "recrue", "equipe", "grade", "cert")

OUTIL = {
    "name": "carte",
    "description": "Fiche de la carte de sport vue sur les photos.",
    "input_schema": {
        "type": "object",
        "properties": {
            "est_une_carte": {"type": "boolean", "description": "false si la photo ne montre pas une carte de sport"},
            "sport": {"type": "string", "enum": ["hockey", "football", "basketball", "baseball", "autre"]},
            "joueur": {"type": "string", "description": "Nom complet, ex. « Connor Bedard ». Deux joueurs : « A / B »."},
            "annee": {"type": "string", "description": "Saison imprimee, ex. « 2023-24 » (hockey/basket) ou « 2024 »."},
            "marque": {"type": "string", "description": "Fabricant : Upper Deck, Panini, Topps, Bowman, O-Pee-Chee..."},
            "set_nom": {"type": "string", "description": "Produit / set, ex. « Series 1 », « Prizm », « The Cup »."},
            "parallele": {"type": "string", "description": "Insert ou parallele, ex. « Young Guns », « Silver Prizm », « Base »."},
            "numero": {"type": "string", "description": "Numero de la carte dans le set (souvent au dos), sans #."},
            "tirage": {"type": ["integer", "null"], "description": "Tirage d'une carte numerotee (le /99 de 12/99), sinon null."},
            "numero_serie": {"type": "string", "description": "Numero estampe complet, ex. « 12/99 », sinon vide."},
            "auto": {"type": "boolean", "description": "Autographe sur la carte ou l'etiquette."},
            "relique": {"type": "boolean", "description": "Morceau de chandail, baton, patch."},
            "recrue": {"type": "boolean", "description": "Carte recrue (RC, Young Guns, Rated Rookie, 1st Bowman...)."},
            "equipe": {"type": "string", "description": "Equipe imprimee sur la carte (nom complet anglais)."},
            # 29 oct 2026 (Mathieu : « pourquoi c'est marque PSA 10 quand y'a meme pas de slab dans la photo ? c'est raw »)
            "slab": {"type": "boolean", "description": "true SEULEMENT si la carte est dans un boitier de gradation scelle (slab) avec l'etiquette "
                                                       "de la compagnie (PSA, BGS, SGC, CGC...) visible sur la photo. Un toploader, un one-touch "
                                                       "magnetique, une pochette ou un support : false."},
            "grade": {"type": "string", "description": "Seulement si slab = true : la compagnie + la note LUES sur l'etiquette, ex. « PSA 10 ». "
                                                        "Carte brute (raw) : vide. Ne devine jamais une note."},
            "cert": {"type": "string", "description": "Numero de certificat de l'etiquette de gradation, sinon vide."},
            "titre_ebay": {"type": "string", "description": "Titre eBay <= 80 caracteres : annee marque set joueur parallele #numero /tirage RC Auto grade."},
            "confiance": {"type": "object", "description": "Pour CHAQUE champ rempli : confiance de 0 a 1 (lu clairement = 0.95+).",
                          "additionalProperties": {"type": "number"}},
            "a_verifier": {"type": "array", "items": {"type": "string"},
                           "description": "Ce qui n'est pas lisible ou ambigu, en francais simple (ex. « le parallele : reflet sur la photo »)."},
            "conseil_photo": {"type": "string", "description": "Si une meilleure photo aiderait : quoi faire, en francais simple. Sinon vide."},
            # 27 oct 2026 : la photo studio (recadrage dans le telephone) et la prise de photo guidee
            "photos": {"type": "array", "description": "Une entree par image, dans l'ordre recu.",
                       "items": {"type": "object", "properties": {
                           "cote": {"type": "string", "enum": ["devant", "dos", "autre"]},
                           "coins": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}},
                                     "description": "Les 4 coins exterieurs de la carte, ou de son etui / slab si elle est dedans (jamais le support), "
                                                    "en coordonnees 0 a 1000 de l'image (x vers la droite, y vers le bas), dans l'ordre : haut-gauche, "
                                                    "haut-droit, bas-droit, bas-gauche, le haut etant le haut de la carte telle qu'on la lit."},
                           "entiere": {"type": "boolean", "description": "true si toute la carte (ou l'etui) est dans la photo, aucun coin coupe"},
                           "nette": {"type": "boolean", "description": "true si le texte imprime est net"},
                           "reflet": {"type": "boolean", "description": "true si un reflet cache du texte ou l'image"},
                           "probleme": {"type": "string", "description": "Si cette photo doit etre reprise : pourquoi, en 6 mots max, en francais. Sinon vide."}},
                           "required": ["cote", "coins", "entiere"]}},
        },
        "required": ["est_une_carte", "sport", "joueur", "confiance", "a_verifier"],
    },
}

SYSTEME = """Tu identifies des cartes de sport (hockey, football NFL, basketball NBA, baseball MLB) pour une app de vendeurs.
Regles :
- Lis ce qui est IMPRIME sur la carte (devant et dos) et sur l'etiquette de gradation. N'invente jamais : un champ illisible reste vide, avec une confiance basse, et va dans a_verifier.
- Le dos donne souvent l'annee (copyright), le numero de la carte et le set ; l'estampe /99 donne le tirage.
- Avec 2 images (le devant puis le dos de la MEME carte) : combine-les. Le numero de serie (ex. 12/99) peut etre au devant
  OU au dos ; l'autographe et le patch se voient au devant ; le dos confirme l'annee, le set, le numero de la carte et
  souvent le nom de l'insert ou du parallele (Exclusives, High Gloss, Canvas...). Une info lue d'un seul cote compte.
- Parallele : decris ce que tu vois (couleur, motif, finition) seulement si tu es sur du nom officiel ; sinon mets-le dans a_verifier.
- Les paralleles qui existent en plusieurs couleurs (Color Flow, Prizm, Refractor, Rainbow, Wave, Mojo, Cracked Ice, Spectrum,
  High Gloss...) : donne TOUJOURS la couleur dans « parallele » (ex. « Color Flow Purple Blue », « Blue Prizm », « Gold Refractor »).
  La couleur change beaucoup le prix. Si tu n'es pas sur du nom exact de la couleur, ecris la couleur que tu vois et mets
  « parallele » dans a_verifier.
- Recrue : RC imprime, Young Guns, Rated Rookie, 1st Bowman, Rookie Ticket...
- Gradation : une carte est gradee SEULEMENT si on voit le slab scelle et son etiquette (PSA, BGS, SGC, CGC...). Dans un
  toploader, un one-touch ou sur un support, elle est brute (raw) : grade et cert vides, et jamais de note dans le titre.
- photos : pour chaque image, les 4 coins exterieurs de la carte (ou de son etui / slab), le plus precis possible, et si la photo est a reprendre (coin coupe, floue, reflet sur le texte).
- Reponds uniquement avec l'outil « carte »."""


_NOTE = re.compile(r"\b(PSA|BGS|SGC|CGC|CSG|TAG|BCCG|KSA|HGA|ISA|GMA)\s*(GEM\s*(MINT|MT)\s*)?\d{1,2}(\.5)?\b", re.I)


class Erreur(Exception):
    """Message pret a montrer a l'utilisateur."""


# -- cle (jamais renvoyee a l'ecran) --------------------------------------------------------
def _cle():
    c = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not c and os.path.exists(CHEMIN_CLE_LOCALE):
        with open(CHEMIN_CLE_LOCALE, encoding="utf-8") as f:
            c = f.read().strip()
    return c


def disponible():
    return bool(_cle())


# -- quotas et plafond ------------------------------------------------------------------------
def _mois():
    return datetime.now().strftime("%Y-%m")


def _lire(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(chemin, d):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, chemin)


def _chemins():
    import comptes
    d = comptes.dossier() or DOSSIER
    return os.path.join(d, "vision_usage.json"), os.path.join(comptes.DONNEES, "vision_serveur.json")


def _limite_compte():
    """None = illimite. PC de Mathieu (sans multi-comptes) : illimite ; client : selon son forfait."""
    import comptes
    if not comptes.MULTI or not comptes.courant():
        return None
    import forfaits                       # 24 oct 2026 - l'essai Pro (14 jours) compte comme Pro
    return None if forfaits.est_pro() else QUOTA_GRATUIT


def statut():
    """Pour l'ecran : disponible ?, photos ce mois, limite. (Jamais la cle.)"""
    perso, _serveur = _chemins()
    u = _lire(perso).get(_mois()) or {}
    lim = _limite_compte()
    return {"disponible": disponible(), "ce_mois": u.get("n", 0), "limite": lim,
            "reste": None if lim is None else max(0, lim - u.get("n", 0)), "modele": "avancé"}


def _verifier_quotas():
    perso, serveur = _chemins()
    lim = _limite_compte()
    n = (_lire(perso).get(_mois()) or {}).get("n", 0)
    if lim is not None and n >= lim:
        raise Erreur(f"Tes {lim} photos gratuites du mois sont utilisées : passe au forfait Pro pour continuer.")
    if (_lire(serveur).get(_mois()) or {}).get("usd", 0) >= PLAFOND_SERVEUR_USD:
        raise Erreur("La reconnaissance photo est en pause pour quelques heures : remplis la fiche à la main.")


def _noter(usage):
    entree, sortie = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    usd = entree / 1e6 * PRIX_ENTREE + sortie / 1e6 * PRIX_SORTIE
    perso, serveur = _chemins()
    with _verrou:
        for chemin in (perso, serveur):
            d = _lire(chemin)
            m = d.setdefault(_mois(), {"n": 0, "usd": 0.0})
            m["n"] += 1
            m["usd"] = round(m["usd"] + usd, 5)
            _ecrire(chemin, d)
    return round(usd, 4)


# -- cache : la meme photo n'est jamais repayee ----------------------------------------------
def _chemin_cache():
    import comptes
    return os.path.join(comptes.dossier() or DOSSIER, "vision_cache.json")


def _empreinte(images):
    h = hashlib.sha256(b"v2-slab")              # 29 oct 2026 : nouvelle regle de gradation -> les anciennes lectures sont refaites
    for b in images:
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()


# -- photos ----------------------------------------------------------------------------------
def _decoder(photo):
    """data:image/jpeg;base64,... ou base64 brut -> (octets, type)."""
    s = str(photo or "")
    m = re.match(r"data:(image/(?:jpeg|png|webp|gif));base64,(.*)$", s, re.S)
    typ, data = (m.group(1), m.group(2)) if m else ("image/jpeg", s)
    try:
        b = base64.b64decode(data, validate=False)
    except (ValueError, TypeError):
        raise Erreur("Photo illisible : reprends-la")
    if len(b) < 2000:
        raise Erreur("Photo trop petite : reprends-la")
    if len(b) > MAX_OCTETS_PHOTO:
        raise Erreur("Photo trop lourde : reprends-la")
    if b[:3] == b"\xff\xd8\xff":
        typ = "image/jpeg"
    elif b[:8] == b"\x89PNG\r\n\x1a\n":
        typ = "image/png"
    elif b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        typ = "image/webp"
    return b, typ


_MODELE_OK = {"m": None}
_CHOIX_AUTO = {"oui": True}      # 28 oct 2026 : le modele refuse tool_choice « tool » : on demande l'outil par la consigne
                                 # (des le 1er appel : avant, chaque redemarrage coutait un appel rate de plus au 1er scan)


def _choix_auto(corps):
    """tool_choice impose -> auto, et la consigne du systeme demande d'appeler l'outil (meme resultat)."""
    tc = corps.get("tool_choice") or {}
    if tc.get("type") not in ("tool", "any"):
        return corps
    nom = tc.get("name") or ((corps.get("tools") or [{}])[0].get("name"))
    consigne = f"\n\nIMPORTANT : reponds UNIQUEMENT en appelant l'outil « {nom} », sans texte autour."
    sysm = corps.get("system")
    if isinstance(sysm, str):
        sysm = sysm + consigne
    elif isinstance(sysm, list):
        sysm = sysm + [{"type": "text", "text": consigne}]
    else:
        sysm = consigne.strip()
    return dict(corps, tool_choice={"type": "auto"}, system=sysm)


def modeles_disponibles():
    """Les modeles que la cle du serveur peut utiliser (API Models d'Anthropic), les plus recents d'abord."""
    req = urllib.request.Request("https://api.anthropic.com/v1/models?limit=100", headers={"x-api-key": _cle(), "anthropic-version": VERSION_API})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
    return [m.get("id") for m in d.get("data") or [] if m.get("id")]


def _meilleur_modele():
    """28 oct 2026 (Mathieu, sur iPhone : « reconnaissance indisponible (modele du serveur) ») : le modele configure
    n'existe pas pour cette cle. On prend le plus recent que la cle peut utiliser : Opus d'abord, sinon Sonnet."""
    try:
        l = modeles_disponibles()
    except Exception as e:
        print("Vision : liste des modeles impossible : " + repr(e), flush=True)
        return None
    for famille in ("opus", "sonnet"):
        for m in l:
            if famille in m.lower():
                return m
    return l[0] if l else None


def _appeler(corps, timeout=90, _reessai=True):
    if _MODELE_OK["m"] and corps.get("model") in (MODELE, None):
        corps = dict(corps, model=_MODELE_OK["m"])
    if _CHOIX_AUTO["oui"]:
        corps = _choix_auto(corps)
    req = urllib.request.Request(URL, data=json.dumps(corps).encode("utf-8"), method="POST", headers={
        "x-api-key": _cle(), "anthropic-version": VERSION_API, "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if _reessai and e.code in (400, 404):
            try:
                corps_err = e.read().decode("utf-8", "ignore")[:400]
            except Exception:
                corps_err = ""
            if "tool_choice" in corps_err and (corps.get("tool_choice") or {}).get("type") in ("tool", "any"):
                print("Vision : tool_choice impose refuse par le modele, on passe en auto", flush=True)
                _CHOIX_AUTO["oui"] = True
                return _appeler(_choix_auto(corps), timeout, _reessai=False)
            if e.code == 404 or ("model" in corps_err.lower() and "not found" in corps_err.lower()):
                m = _meilleur_modele()
                if m and m != corps.get("model"):
                    print(f"Vision : modele {corps.get('model')} refuse, on passe a {m}", flush=True)
                    _MODELE_OK["m"] = m
                    return _appeler(dict(corps, model=m), timeout, _reessai=False)
            _noter_erreur(e.code, corps_err)
            print(f"Vision : HTTP {e.code} {corps_err}", flush=True)
            raise _erreur_http(e.code, corps_err)
        try:
            detail = e.read().decode("utf-8", "ignore")[:400]
        except Exception:
            detail = ""
        print(f"Vision : HTTP {e.code} {detail}", flush=True)
        _noter_erreur(e.code, detail)
        raise _erreur_http(e.code, detail)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Erreur("Pas de connexion avec la reconnaissance : réessaie.")


def _erreur_http(code, detail):
    d = (detail or "").lower()
    if code in (429, 529):
        return Erreur("Beaucoup de demandes en ce moment : réessaie dans une minute.")
    if code in (401, 403):
        return Erreur("Reconnaissance photo indisponible (clé du serveur) : remplis la fiche à la main.")
    if "credit balance" in d or "billing" in d:
        return Erreur("Reconnaissance photo en pause (crédit Anthropic du serveur épuisé) : cherche la carte par son nom.")
    if code == 404 or ("model" in d and "not found" in d):
        return Erreur("Reconnaissance photo indisponible (modèle du serveur) : cherche la carte par son nom.")
    if code == 413 or "image" in d:
        return Erreur("Photo trop lourde pour la reconnaissance : reprends-la de plus près.")
    return Erreur("La reconnaissance n'a pas répondu : réessaie.")


_DERNIERE = {}


def _noter_erreur(code, detail):
    _DERNIERE.update(code=code, detail=re.sub(r"sk-[A-Za-z0-9_-]+", "sk-…", detail or "")[:300], le=time.time())


def derniere_erreur():
    """Pour l'admin : la derniere erreur de l'API de reconnaissance (code + message d'Anthropic, sans cle)."""
    return dict(_DERNIERE) if _DERNIERE else None


def _nettoyer(f):
    """Reponse du modele -> champs de la fiche SlabCoach + champs a verifier."""
    conf = {k: float(v) for k, v in (f.get("confiance") or {}).items() if isinstance(v, (int, float))}
    out = {}
    for k in CHAMPS:
        v = f.get(k)
        if v in (None, "", [], "null"):
            continue
        if k in ("auto", "relique", "recrue"):
            out[k] = 1 if v is True else 0
        elif k == "tirage":
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                continue
        else:
            out[k] = str(v).strip()[:120]
    if out.get("sport") == "autre":
        out.pop("sport")
    if f.get("titre_ebay"):
        out["titre"] = str(f["titre_ebay"]).strip()[:80]
    # 29 oct 2026 : pas de slab vu = carte brute. Une note devinee (« PSA 10 » sur une carte raw) est retiree partout.
    if f.get("slab") is not True:
        out.pop("grade", None)
        out.pop("cert", None)
        if out.get("titre"):
            out["titre"] = re.sub(r"\s+", " ", _NOTE.sub("", out["titre"])).strip()
    douteux = sorted(k for k in out if k in conf and conf[k] < SEUIL_CONFIANCE)
    return {"champs": out, "a_verifier": douteux, "notes": [str(x) for x in (f.get("a_verifier") or [])][:6],
            "conseil_photo": str(f.get("conseil_photo") or "").strip(), "confiance": conf, "photos": _photos(f.get("photos"))}


def _photos(l):
    """Coins (0..1000) et qualite de chaque photo, nettoyes ; une photo douteuse garde au moins son cote."""
    out = []
    for p in (l if isinstance(l, list) else [])[:MAX_PHOTOS]:
        p = p if isinstance(p, dict) else {}
        coins = p.get("coins")
        try:
            coins = [[max(-50, min(1050, int(x))), max(-50, min(1050, int(y)))] for x, y in coins][:4]
        except (TypeError, ValueError):
            coins = None
        if not coins or len(coins) != 4:
            coins = None
        out.append({"cote": p.get("cote") if p.get("cote") in ("devant", "dos", "autre") else None, "coins": coins,
                    "entiere": p.get("entiere") is not False, "nette": p.get("nette") is not False, "reflet": p.get("reflet") is True,
                    "probleme": str(p.get("probleme") or "").strip()[:60]})
    return out


def identifier(photos):
    """photos : 1 ou 2 images (devant, dos) en base64 / data URL.
    -> {"ok", "champs", "a_verifier", "notes", "conseil_photo", "cout_usd", "cache"}."""
    if not disponible():
        raise Erreur("Reconnaissance photo pas encore activée sur ce serveur : remplis la fiche à la main.")
    photos = [p for p in (photos or []) if p][:MAX_PHOTOS]
    if not photos:
        raise Erreur("Ajoute une photo de la carte")
    images = [_decoder(p) for p in photos]
    cle_cache = _empreinte([b for b, _t in images])
    cache = _lire(_chemin_cache())
    if cle_cache in cache:
        return dict(cache[cle_cache], ok=True, cache=True, cout_usd=0)
    _verifier_quotas()
    contenu = []
    for i, (b, typ) in enumerate(images):
        contenu.append({"type": "text", "text": "Devant de la carte :" if i == 0 else "Dos de la carte :"})
        contenu.append({"type": "image", "source": {"type": "base64", "media_type": typ, "data": base64.b64encode(b).decode()}})
    contenu.append({"type": "text", "text": "Remplis la fiche de cette carte."})
    r = _appeler({"model": MODELE, "max_tokens": 1500, "system": SYSTEME, "tools": [OUTIL],
                  "tool_choice": {"type": "tool", "name": "carte"}, "messages": [{"role": "user", "content": contenu}]})
    cout = _noter(r.get("usage") or {})
    fiche = next((b.get("input") for b in r.get("content") or [] if b.get("type") == "tool_use"), None)
    if not fiche:
        raise Erreur("Carte pas reconnue : reprends la photo de plus près, sans reflet.")
    if fiche.get("est_une_carte") is False:
        raise Erreur("Je ne vois pas de carte de sport sur la photo : cadre la carte entière.")
    res = _nettoyer(fiche)
    with _verrou:
        cache = _lire(_chemin_cache())
        cache[cle_cache] = res
        if len(cache) > 2000:                          # garde les plus recentes
            cache = dict(list(cache.items())[-1500:])
        _ecrire(_chemin_cache(), cache)
    return dict(res, ok=True, cache=False, cout_usd=cout)
