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
MAX_OCTETS_PHOTO = 4_500_000          # apres decodage ; l'ecran reduit deja a ~1600 px (envoyee telle quelle a l'IA : < 5 Mo)
MAX_OCTETS_EXAMEN = 8_000_000         # 5 nov 2026 : la camera native HD (jusqu'a 5000 px) ; l'examen re-encode avant l'IA
QUOTA_GRATUIT = int(os.environ.get("LR_VISION_GRATUIT") or 25)        # photos / mois / compte gratuit
# 3 nov 2026 (revue de securite) : un plafond d'usage raisonnable aussi pour le Pro et l'essai (sinon un seul compte, ou des
# comptes d'essai crees en serie, epuisaient le plafond du serveur pour tout le monde)
QUOTA_PRO = int(os.environ.get("LR_VISION_PRO") or 800)              # photos / mois / compte Pro
QUOTA_ESSAI = int(os.environ.get("LR_VISION_ESSAI") or 150)          # photos / mois pendant l'essai gratuit
_EN_COURS = {}                                                        # appels payants en cours, par compte (contre les rafales)
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
  Pas d'etiquette lisible avec un numero de certificat = carte brute. Ne devine jamais une note d'apres l'etat de la carte.
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
    f = forfaits.etat()
    if not f.get("pro"):
        return QUOTA_GRATUIT
    return QUOTA_ESSAI if f.get("essai") else QUOTA_PRO


def statut():
    """Pour l'ecran : disponible ?, photos ce mois, limite. (Jamais la cle.)"""
    perso, _serveur = _chemins()
    u = _lire(perso).get(_mois()) or {}
    lim = _limite_compte()
    return {"disponible": disponible(), "ce_mois": u.get("n", 0), "limite": lim,
            "reste": None if lim is None else max(0, lim - u.get("n", 0)), "modele": "avancé"}


def _reserver(cle, n_deja, lim):
    """3 nov 2026 (revue) : compte les appels en cours (20 requetes en meme temps ne passent plus toutes sur 1 photo restante)."""
    import comptes
    k = (comptes.courant() or "local", cle)
    with _verrou:
        if lim is not None and n_deja + _EN_COURS.get(k, 0) >= lim:
            return None
        _EN_COURS[k] = _EN_COURS.get(k, 0) + 1
    return k


def _liberer(k):
    if k:
        with _verrou:
            _EN_COURS[k] = max(0, _EN_COURS.get(k, 0) - 1)


def _verifier_quotas():
    perso, serveur = _chemins()
    lim = _limite_compte()
    n = (_lire(perso).get(_mois()) or {}).get("n", 0)
    if lim is not None and n + _EN_COURS.get(((__import__("comptes").courant() or "local"), "photo"), 0) >= lim:
        if lim == QUOTA_GRATUIT:
            raise Erreur(f"Tes {lim} photos gratuites du mois sont utilisées : passe au forfait Pro pour continuer.")
        raise Erreur(f"Tu as utilisé tes {lim} lectures de photos de ce mois : remplis la fiche à la main jusqu’au mois prochain.")
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
    h = hashlib.sha256(b"v3-slab-cert")              # 29 oct 2026 : nouvelle regle de gradation -> les anciennes lectures sont refaites
    for b in images:
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()


# -- photos ----------------------------------------------------------------------------------
def _decoder(photo, max_octets=None):
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
    if len(b) > (max_octets or MAX_OCTETS_PHOTO):
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
    # 30 oct 2026 (« encore PSA 10 ») : le modele peut dire slab = true sur une carte brute. Une etiquette de gradation a
    # TOUJOURS un numero de certificat : sans certificat lu (6 chiffres et plus), pas de note.
    cert_lu = re.sub(r"\D", "", str(out.get("cert") or ""))
    if f.get("slab") is not True or len(cert_lu) < 6:
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
    lim_ = _limite_compte()
    res_ = _reserver("photo", (_lire(_chemins()[0]).get(_mois()) or {}).get("n", 0), lim_)
    if res_ is None:
        raise Erreur(f"Tes {lim_} photos du mois sont utilisées.")
    try:
        return _identifier_appel(images, cle_cache)
    finally:
        _liberer(res_)


def _identifier_appel(images, cle_cache):
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


# -- 1er nov 2026 : l'ETAT d'une carte (pre-gradation) ---------------------------------------------------------------
# Mathieu : « pour les cartes ajoutees a la collection, on peut les noter et dire les defauts trouves ? centrage, coins et
# bords ? ». Une estimation sur photo, dite comme telle : une fourchette (jamais une promesse de 10), le centrage en
# ratios, chaque defaut a sa place sur la photo, et ce que la photo ne permet pas de voir.
_ZONES = ["coin haut-gauche", "coin haut-droit", "coin bas-droit", "coin bas-gauche", "bord haut", "bord droit", "bord bas",
          "bord gauche", "surface"]
_DEFAUTS = ["blanchiment", "coin mou", "coin plie", "ebrechure", "entaille", "rayure", "ligne d'impression", "tache",
            "pli", "bosse", "marque d'ecriture", "decentrage", "micro-creux", "point d'encre", "trace de rouleau", "empreinte",
            "perte de lustre", "decollement", "decoloration", "cire", "autre"]
# 2 nov 2026 (Mathieu : « les baremes doivent etre etablis pour que toutes les cartes soient evaluees selon les memes
# criteres et la meme severite ») : l'IA DECRIT (chaque coin, chaque bord, chaque marque de surface, avec des etats fixes) ;
# la note est CALCULEE par bareme.py, la meme table pour toutes les cartes (normes PSA).
import bareme as _bar
_OBS_COMMUN = {"photo": {"type": "integer", "description": "0 = devant, 1 = dos"},
               "certitude": {"type": "string", "enum": list(_bar.CERTITUDES),
                             "description": "« sure » : net dans le zoom ; « probable » ; « incertaine » : le zoom est flou ou cache"},
               "pourquoi": {"type": "string", "description": "Ce que tu vois exactement, 12 mots max (ex. « 3 pixels blancs a la pointe »)"}}
OUTIL_ETAT = {
    "name": "etat",
    "description": "Observation detaillee de l'etat physique d'une carte de sport (pre-gradation). Tu decris ; l'app calcule la note.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evaluable": {"type": "boolean", "description": "false si les photos ne permettent pas de juger l'etat (floue, trop loin, slab, reflet partout)"},
            "raison": {"type": "string", "description": "Si evaluable = false : pourquoi, en francais simple (8 mots max)."},
            "centrage_gd": {"type": "string", "description": "Centrage gauche/droite du DEVANT si tu dois l'estimer, ex. « 55/45 » (le plus grand cote en premier). Vide si l'app l'a mesure ou si pas mesurable."},
            "centrage_hb": {"type": "string", "description": "Centrage haut/bas du DEVANT, meme format. Vide si mesure par l'app ou pas mesurable."},
            "centrage_dos": {"type": "string", "description": "Centrage du DOS (pire des deux axes), si a estimer. Sinon vide."},
            "coins": {"type": "array", "description": "EXACTEMENT 4 coins par face fournie (devant, puis dos), tels que vus dans les ZOOMS.",
                      "items": {"type": "object", "properties": {**_OBS_COMMUN,
                                "coin": {"type": "string", "enum": list(_bar.COINS)},
                                "etat": {"type": "string", "enum": list(_bar.ETATS_COIN)}},
                                "required": ["photo", "coin", "etat", "certitude"]}},
            "bords": {"type": "array", "description": "EXACTEMENT 4 bords par face fournie, tels que vus dans les bandes de ZOOM.",
                      "items": {"type": "object", "properties": {**_OBS_COMMUN,
                                "bord": {"type": "string", "enum": list(_bar.BORDS)},
                                "etat": {"type": "string", "enum": list(_bar.ETATS_BORD)},
                                "position": {"type": "integer", "description": "Ou le long du bord est le pire endroit, 0 a 1000 (gauche->droite ou haut->bas)"}},
                                "required": ["photo", "bord", "etat", "certitude"]}},
            "surface": {"type": "array", "description": "Chaque marque de surface vue sur le CARTON IMPRIME (rien si la surface est propre).",
                        "items": {"type": "object", "properties": {**_OBS_COMMUN,
                                  "type": {"type": "string", "enum": list(_bar.SURFACE)},
                                  "visibilite": {"type": "string", "enum": list(_bar.VISIBILITES),
                                                 "description": "« rasante » : seulement en lumiere rasante ou au zoom ; « de_pres » : visible en regardant de pres ; « visible » : se voit tout de suite"},
                                  "sur_relique": {"type": "boolean", "description": "true si c'est sur une patch, une relique (tissu, fils, coutures), un autocollant d'autographe ou dans sa fenetre : ce n'est alors PAS un defaut"},
                                  "x": {"type": "integer", "description": "Position dans la PHOTO ENTIERE de sa face, 0 a 1000 (vers la droite)"},
                                  "y": {"type": "integer", "description": "Position dans la PHOTO ENTIERE, 0 a 1000 (vers le bas)"}},
                                  "required": ["photo", "type", "visibilite", "certitude", "x", "y"]}},
            "centrage_reperes": {"type": "array", "description": "Pour chaque face et chaque axe : le repere imprime qui sert a mesurer le centrage, lu sur la REGLE 0-1000 de l'image redressee.",
                                 "items": {"type": "object", "properties": {
                                     "photo": {"type": "integer", "description": "0 = devant, 1 = dos"},
                                     "axe": {"type": "string", "enum": ["gd", "hb"], "description": "gd = gauche/droite (regle du haut) ; hb = haut/bas (regle de gauche)"},
                                     "element": {"type": "string", "description": "Le repere, 5 mots max (ex. « bordure imprimee », « bord des fenetres de patch », « cadre dore »)"},
                                     "debut": {"type": "integer", "description": "Position du repere du cote gauche (ou haut) sur la regle, 0 a 1000"},
                                     "fin": {"type": "integer", "description": "Position du MEME repere du cote droit (ou bas) sur la regle, 0 a 1000"}},
                                     "required": ["photo", "axe", "element", "debut", "fin"]}},
            "surface_jugeable": {"type": "boolean", "description": "false si un reflet, un etui ou la resolution empeche de juger la surface"},
            "invisible": {"type": "array", "items": {"type": "string"},
                          "description": "Ce que ces photos ne permettent PAS de verifier, en francais simple (12 mots max chacun)."},
            "conseil": {"type": "string", "description": "Une phrase : grader ou pas, et pourquoi. Sans promesse."},
        },
        "required": ["evaluable", "coins", "bords", "surface", "invisible"],
    },
}
SYSTEME_ETAT = """Tu es un inspecteur de cartes de sport pour un pre-gradage, avec les yeux d'un gradeur PSA experimente : severe,
precis, constant. Tu ne donnes PAS de note : tu DECRIS l'etat avec des mots fixes ; l'app calcule la note avec un bareme unique
(les normes officielles PSA), le meme pour toutes les cartes. Ta constance compte plus que tout : la meme carte doit toujours
recevoir les memes observations.

Tu recois, chacune annoncee par une ligne de texte : la photo entiere du devant ; les ZOOMS de ses 4 coins (carte redressee, en
pleine resolution, un peu de fond autour pour voir l'arete) ; les ZOOMS de ses 4 bords (deux images : haut et bas, puis gauche et
droite, chaque bord coupe en deux moities) ; puis la meme chose pour le dos ; parfois une photo en lumiere rasante.

METHODE (dans cet ordre, sans sauter d'etape) :
1. Les 8 coins (4 par face), un a un, dans les zooms. Regarde la POINTE et les deux aretes qui y arrivent, contre le fond.
   net = pointe nette et carree, aucun blanc ; point_blanc = un tout petit point blanc ou une pointe a peine adoucie, visible
   seulement au zoom ; effilochage_leger = un peu de blanc / de fibres a la pointe, vu de pres ; effilochage = blanc net, visible
   sans zoom ; arrondi_leger = pointe tres legerement ronde ; arrondi = coin rond ; plie = coin plie, ecrase ou dechire.
   UN DEFAUT, UNE SEULE PLACE (9 nov 2026, la Hutson : du blanc le long du bord du haut compte aussi au coin haut-gauche,
   alors que la pointe etait nette) : le coin, c'est la POINTE elle-meme (les 1-2 derniers mm). Des points blancs le long
   d'une arete, meme pres d'un coin, vont au BORD ; le coin reste « net » si sa pointe est nette.
   COIN IMPRIME EN BLANC (la Hutson : « tres beau coin, il est juste blanc ») : le blanc y est l'impression, jamais du
   blanchiment ; juge seulement la FORME de la pointe. Le leger flou ou l'ombre de l'arete d'une carte blanche sur un fond
   noir n'est pas une pointe adoucie : « net », sauf si la pointe est clairement ronde ou ecrasee.
   BORDURE ARGENT / GRISE / METALLIQUE (9 nov 2026, le dos de la Willander Young Guns : coin haut-droit et les deux coins du
   bas touches) : le blanchiment y a peu de contraste. C'est un blanc PUR et MAT, un peu flou ou effiloche, a la pointe
   ou sur la ligne de coupe, plus clair que l'argent (qui est gris et brillant, avec ses stries). Compare la pointe aux
   autres coins de la meme face : celle qui a un liseré blanc plus epais ou une pointe blanche est touchee. Le mince filet
   de lumiere regulier sur toute l'arete (la coupe qui accroche la lumiere) n'est pas du blanchiment.
2. Les 8 bords, moitie par moitie. Une bordure foncee montre tout : la meme severite qu'une bordure claire, mais regarde mieux.
   net ; point_blanc (un seul petit point) ; quelques_points (plusieurs petits points) ; usure_legere (fine usure continue) ;
   encoche (petit creux dans l'arete) ; ebrechures (eclats de couleur) ; usure (usure nette, entaille).
3. La surface du carton imprime : rayures, lignes d'impression, taches, empreintes, perte de lustre, bosses, plis. Note la
   visibilite : rasante (seulement en lumiere rasante ou au zoom), de_pres, visible. Rien a signaler : liste vide.
   Reconnaitre (guide pregradecards.com) : rayure = fine ligne brillante qui ne suit pas le dessin, souvent seulement en
   lumiere rasante ; ligne d'impression = lignes paralleles dans UNE direction sur une zone unie (chrome, refractor) ;
   trace de rouleau = lignes tres faibles, regulierement espacees ; point d'encre = petit point de COULEUR (encre) sur une
   zone unie ; micro-creux = minuscule trou ou cratere qui fait une petite ombre en lumiere rasante (pas un point clair
   pose dessus : ca, c'est de la poussiere) ; empreinte = plaque floue ou laiteuse, avec des stries de doigt ; perte de
   lustre = zone terne dans un reflet qui devrait etre uniforme ; bosse = petit enfoncement qui fait une ombre ;
   decollement = le foil ou le chrome qui se souleve, fait une bulle ou se fissure pres des bords ; decoloration = bordure
   blanche jaunie ou couleurs ternies ; cire = plaque jaunatre ou brunatre, un peu en relief.
   TACHE ou SALETE (9 nov 2026, la Dickinson : une petite tache brune au dos etait une VRAIE tache) : une tache est DANS la
   surface (plate, contour flou, la couleur deteint dans l'impression, elle suit le relief du carton) ; une salete posee
   dessus a un contour net, un petit relief, une ombre ou un reflet a elle, et deborde parfois sur le fond. Une marque brune,
   jaune ou grise sur une zone unie qui n'est pas dans le dessin : tache, sauf si tu vois clairement qu'elle est posee dessus
   (alors « incertaine »). Ne la confonds pas avec la poussiere blanche.
   marque d'ecriture = un chiffre, une lettre ou un trait CREUSE dans le carton (quelqu'un a ecrit sur une feuille posee sur
   la carte) : invisible de face, il ressort en lumiere rasante et dans la DIFFERENCE des deux eclairages comme un trace en
   creux qui ne suit pas l'image. Cherche-le partout, surtout dans les zones unies et sur les visages. PSA : 6 au mieux.
4. Le centrage, dans l'image REDRESSEE avec la REGLE 0-1000 : pour chaque face et chaque axe, choisis UN repere imprime qui
   existe des deux cotes et qui est symetrique par conception : la bordure imprimee d'abord ; sans bordure, le cadre interieur,
   le bord des fenetres de patch, un bloc de texte aligne des deux cotes. Donne sa position a gauche (debut) et a droite (fin)
   sur la regle du haut (axe gd), puis en haut et en bas sur la regle de gauche (axe hb). Lis la regle avec soin (a 5 pres).
   Un axe sans repere symetrique (titre en haut, texte en bas) : ne le donne pas. Laisse centrage_gd / centrage_hb vides.

REGLES :
- N'invente rien. Un reflet, une poussiere sur l'etui, un grain de photo ne sont pas des defauts : si tu ne peux pas trancher,
  certitude = « incertaine » (jamais pour un zoom net : la, decide).
- POUSSIERE ou BLANCHIMENT (9 nov 2026, cartes de Mathieu) : de petits points blancs isoles DANS la surface (loin de l'arete),
  ou poses sur le tapis autour, sont de la poussiere ou des fibres : jamais un defaut de surface. MAIS des points blancs SUR la
  ligne de coupe elle-meme (l'arete), surtout sur une bordure foncee ou coloree (rouge, noire, bleue), sont du BLANCHIMENT
  (carton mis a nu), meme tout petits : point_blanc s'il y en a un, quelques_points s'il y en a plusieurs le long du meme
  bord. Une fibre qui traverse l'arete en debordant sur le fond reste de la poussiere. Si l'app MESURE des points sur la
  ligne de coupe, crois-la sauf si le zoom montre clairement une fibre.
- CARTE TRANSPARENTE (acrylique, Future Watch, Clear Cut) : le filet clair de l'arete est le bord de l'acrylique, pas du
  blanchiment. Juge la forme des coins et des aretes (eclat, fissure) et les rayures de la surface.
- CARTE SANS BORDURE (photo pleine page) : le centrage se juge sur le cadre ou les elements imprimes symetriques ; s'il n'y en
  a pas, ne donne pas de centrage.
- PATCH, RELIQUE, AUTOGRAPHE : le tissu (fils, coutures, broderie, plis du tissu, bord effiloche du tissu), l'autocollant et la
  fenetre decoupee font partie de la carte ; jamais un defaut de surface. Si tu en notes un par prudence : sur_relique = true.
- Carte dans un toploader, une pochette ou sur un support : les aretes sont en partie cachees ; dis-le dans « invisible » et mets
  « incertaine » la ou tu ne vois pas.
- Carte dans un slab de gradation : evaluable = false.
- x et y d'une marque de surface : sa position dans la PHOTO ENTIERE de sa face (0 a 1000), pas dans les zooms.
- Textes courts : pourquoi 12 mots max, invisible 12 mots max, conseil 25 mots max.
- Reponds uniquement avec l'outil « etat »."""


MODELE_ETAT = os.environ.get("LR_ETAT_MODELE") or MODELE            # le plus avance (Opus) ; changeable sans code
try:
    REFLEXION_ETAT = int(os.environ.get("LR_ETAT_REFLEXION") or 8000)   # jetons de reflexion (0 = sans)
except ValueError:
    REFLEXION_ETAT = 8000
# 1er nov 2026 (Mathieu : « l'analyse de la carte : en Pro jusqu'a 30 cartes, en gratuit 3 ») : par mois, a part des lectures
ETAT_GRATUIT = int(os.environ.get("LR_ETAT_GRATUIT") or 3)
ETAT_PRO = int(os.environ.get("LR_ETAT_PRO") or 30)


def _limite_etat():
    import comptes
    if not comptes.MULTI or not comptes.courant():
        return None                                      # PC de Mathieu : illimite
    import forfaits
    return ETAT_PRO if forfaits.est_pro() else ETAT_GRATUIT


def statut_etat():
    perso, _s = _chemins()
    n = (_lire(perso).get(_mois()) or {}).get("etat", 0)
    lim = _limite_etat()
    return {"ce_mois": n, "limite": lim, "reste": None if lim is None else max(0, lim - n)}


def _verifier_etat():
    st = statut_etat()
    if st["limite"] is not None and st["reste"] <= 0:
        import forfaits
        raise Erreur(f"Tes {st['limite']} analyses d'état du mois sont utilisées" + ("" if forfaits.est_pro() else
                     f" : passe au Pro pour en avoir {ETAT_PRO} par mois") + ".")
    _s = _chemins()[1]
    if (_lire(_s).get(_mois()) or {}).get("usd", 0) >= PLAFOND_SERVEUR_USD:
        raise Erreur("L'analyse photo est en pause pour quelques heures : réessaie plus tard.")


def _noter_etat(usage):
    entree, sortie = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    usd = entree / 1e6 * PRIX_ENTREE + sortie / 1e6 * PRIX_SORTIE
    perso, serveur = _chemins()
    with _verrou:
        d = _lire(perso)
        m = d.setdefault(_mois(), {"n": 0, "usd": 0.0})
        m["etat"] = m.get("etat", 0) + 1
        m["usd"] = round(m.get("usd", 0) + usd, 5)
        _ecrire(perso, d)
        d = _lire(serveur)
        m = d.setdefault(_mois(), {"n": 0, "usd": 0.0})
        m["usd"] = round(m.get("usd", 0) + usd, 5)
        _ecrire(serveur, d)


_PSA_ECHELLE = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 10]   # PSA : pas de 9,5
_CAT_ZONE = lambda z: "coins" if z.startswith("coin") else "bords" if z.startswith("bord") else "surface" if z == "surface" else None
_PLAFOND_GRAV = {"fort": 7.0, "moyen": 8.0, "leger": 9.0, "a verifier": 9.5}     # PSA : « leger effilochage a un coin » = 8


def _psa(v, haut=False):
    """Une note sur l'echelle PSA (9,5 n'existe pas : vers le bas, ou 10 seulement si on arrondit vers le haut... jamais)."""
    if v is None:
        return None
    return max(x for x in _PSA_ECHELLE if x <= v + 1e-9) if v < 10 else 10.0


_LIB_ETAT = {"point_blanc": "petit point blanc", "effilochage_leger": "léger effilochage", "effilochage": "effilochage net",
             "arrondi_leger": "pointe légèrement arrondie", "arrondi": "coin arrondi", "plie": "coin plié", "quelques_points": "quelques points blancs",
             "usure_legere": "légère usure", "encoche": "petite encoche", "ebrechures": "ébréchures", "usure": "usure nette"}
_TYPE_COIN = {"point_blanc": "blanchiment", "effilochage_leger": "blanchiment", "effilochage": "blanchiment", "arrondi_leger": "coin mou",
              "arrondi": "coin mou", "plie": "coin plie"}
_TYPE_BORD = {"point_blanc": "blanchiment", "quelques_points": "blanchiment", "usure_legere": "blanchiment", "encoche": "entaille",
              "ebrechures": "ebrechure", "usure": "entaille"}


def _bil(q, u, v):
    """(u, v) de la carte (0..1) -> point de la photo (0..1000), avec le contour q (haut-gauche puis sens horaire)."""
    if not q or len(q) != 4:
        return round(u * 1000), round(v * 1000)
    a = [q[0][0] + (q[1][0] - q[0][0]) * u, q[0][1] + (q[1][1] - q[0][1]) * u]
    b = [q[3][0] + (q[2][0] - q[3][0]) * u, q[3][1] + (q[2][1] - q[3][1]) * u]
    return round(a[0] + (b[0] - a[0]) * v), round(a[1] + (b[1] - a[1]) * v)


_LIB_ETAT_EN = {"point_blanc": "tiny white speck", "effilochage_leger": "light fraying", "effilochage": "clear fraying",
                "arrondi_leger": "slightly rounded tip", "arrondi": "rounded corner", "plie": "bent corner", "quelques_points": "a few white specks",
                "usure_legere": "light wear", "encoche": "small notch", "ebrechures": "chipping", "usure": "clear wear"}


def _noter_observations(f, centrage=None, calibration=None, quads=None, langue="fr"):
    """2 nov 2026 : les observations de l'IA -> sous-notes, fourchette, defauts et explications, TOUJOURS avec le meme bareme
    (bareme.py, normes PSA). Une observation « incertaine » n'abaisse que le bas de la fourchette."""
    import examen
    rat = lambda s_: s_ if re.fullmatch(r"\d{2}/\d{2}", str(s_ or "").strip()) else ""
    quads = quads or []
    nface = 2 if any(int(o.get("photo") or 0) == 1 for o in (f.get("coins") or []) + (f.get("bords") or []) if isinstance(o, dict)) else 1
    coins, bords, surf = {}, {}, []
    for o in f.get("coins") or []:
        if isinstance(o, dict) and o.get("coin") in _bar.COINS and o.get("etat") in _bar.ETATS_COIN:
            coins[(1 if o.get("photo") == 1 else 0, o["coin"])] = o
    for o in f.get("bords") or []:
        if isinstance(o, dict) and o.get("bord") in _bar.BORDS and o.get("etat") in _bar.ETATS_BORD:
            bords[(1 if o.get("photo") == 1 else 0, o["bord"])] = o
    for o in f.get("surface") or []:
        if isinstance(o, dict) and o.get("type") in _bar.SURFACE and o.get("sur_relique") is not True:
            surf.append(o)
    inc = lambda o: o.get("certitude") == "incertaine"
    lim = lambda l: [o for o in l if not inc(o)]
    sj = f.get("surface_jugeable") is not False
    hi = {"coins": _bar.note_coins([o["etat"] for o in lim(coins.values())]),
          "bords": _bar.note_bords([o["etat"] for o in lim(bords.values())]),
          "surface": _bar.note_surface([(o["type"], o.get("visibilite"), 1 if o.get("photo") == 1 else 0) for o in lim(surf)]) if sj else None}
    # 9 nov 2026 (Mathieu : « quand l'IA doute : ne rien montrer ») : un doute n'abaisse plus rien, meme pas le bas de la
    # fourchette, et n'est plus montre (voir les defauts plus bas)
    coins = {k: o for k, o in coins.items() if not inc(o)}
    bords = {k: o for k, o in bords.items() if not inc(o)}
    surf = lim(surf)
    lo = {"coins": _bar.note_coins([o["etat"] for o in coins.values()]),
          "bords": _bar.note_bords([o["etat"] for o in bords.values()]),
          "surface": _bar.note_surface([(o["type"], o.get("visibilite"), 1 if o.get("photo") == 1 else 0) for o in surf]) if sj else None}
    # le centrage : mesure par l'app (tolerances PSA), sinon l'estimation de l'IA avec la meme table
    cg, ch, cd = rat(f.get("centrage_gd")), rat(f.get("centrage_hb")), rat(f.get("centrage_dos"))
    mesure = bool(centrage and centrage.get("devant"))
    if mesure:
        cg, ch = centrage["devant"].get("gd") or cg, centrage["devant"].get("hb") or ch
    if centrage and centrage.get("note") is not None:
        nc = float(centrage["note"])
    else:
        nc = examen.note_centrage({"gd": cg, "hb": ch} if (cg or ch) else None, {"gd": cd} if cd else None)
    # 2 nov 2026 : les reperes nommes par l'IA (lus sur la regle de l'image redressee) completent ce que l'app n'a pas mesure
    rep_ = []
    for o in f.get("centrage_reperes") or []:
        try:
            ph, ax, a_, b_ = (1 if o.get("photo") == 1 else 0), o.get("axe"), int(o.get("debut")), int(o.get("fin"))
        except (TypeError, ValueError, AttributeError):
            continue
        g1, g2 = a_, 1000 - b_
        if ax not in ("gd", "hb") or not (0 < g1 <= 320 and 0 < g2 <= 320):
            continue
        rep_.append({"photo": ph, "axe": ax, "element": str(o.get("element") or "").strip()[:40], "debut": a_, "fin": b_,
                     "ratio": examen._ratio(g1, g2)})
    cent2 = {fc: dict((centrage or {}).get(fc) or {}) for fc in ("devant", "dos")}
    ajoute = False
    for r_ in rep_:
        fc = "devant" if r_["photo"] == 0 else "dos"
        if not cent2[fc].get(r_["axe"]):
            cent2[fc][r_["axe"]] = r_["ratio"]
            r_["utilise"] = True
            ajoute = True
    if ajoute:
        nc = examen.note_centrage(cent2["devant"] if (cent2["devant"].get("gd") or cent2["devant"].get("hb")) else None,
                                  cent2["dos"] if (cent2["dos"].get("gd") or cent2["dos"].get("hb")) else None)
        cg, ch = cent2["devant"].get("gd") or cg, cent2["devant"].get("hb") or ch
        cd = cent2["dos"].get("gd") or cent2["dos"].get("hb") or cd
    hi["centrage"] = lo["centrage"] = float(nc) if nc is not None else None
    # 3 nov 2026 : un decentrage fort mesure sur un element de design (peut-etre dessine ainsi) : le bas de la fourchette
    if centrage and centrage.get("note_bas") is not None and (lo["centrage"] is None or centrage["note_bas"] < lo["centrage"]):
        lo["centrage"] = float(centrage["note_bas"])
    g_hi, g_lo = _bar.globale(hi), _bar.globale(lo)
    if g_hi is None:
        g_hi = g_lo = 9.0
    g_lo = min(g_lo, g_hi)
    calibre = bool(calibration and calibration.get("n", 0) >= 15)
    if calibre:
        dec = max(-1.0, min(0.5, float(calibration.get("ecart") or 0)))
        g_hi, g_lo = _bar.psa(min(10.0, g_hi + dec)), _bar.psa(max(1.0, g_lo + dec))
    # les defauts pour l'ecran (les numeros sur la photo), le pire d'abord
    defauts = []
    def ajouter(cat, o, note_, type_, zone, x, y, lib):
        grav = "a verifier" if inc(o) else "leger" if note_ >= 9 else "moyen" if note_ >= 7 else "fort"
        quoi = str(o.get("pourquoi") or "").strip()[:90]
        defauts.append({"photo": 1 if o.get("photo") == 1 else 0, "zone": zone, "type": type_, "gravite": grav, "x": x, "y": y,
                        "note": note_, "pourquoi": (quoi + " · " if quoi else "") + f"{lib} : {str(note_).replace('.0', '')}/10"})
    uv_coin = {"haut-gauche": (0.02, 0.02), "haut-droit": (0.98, 0.02), "bas-droit": (0.98, 0.98), "bas-gauche": (0.02, 0.98)}
    for (ph, c), o in coins.items():
        n_ = _bar.ETATS_COIN[o["etat"]][0]
        if n_ < 10:
            x, y = _bil(quads[ph] if ph < len(quads) else None, *uv_coin[c])
            ajouter("coins", o, n_, _TYPE_COIN[o["etat"]], "coin " + c, x, y, (_LIB_ETAT_EN if langue == "en" else _LIB_ETAT)[o["etat"]])
    for (ph, b), o in bords.items():
        n_ = _bar.ETATS_BORD[o["etat"]][0]
        if n_ < 10:
            t = max(0.05, min(0.95, (o.get("position") if isinstance(o.get("position"), int) else 500) / 1000))
            u, v = {"haut": (t, 0.01), "bas": (t, 0.99), "gauche": (0.01, t), "droit": (0.99, t)}[b]
            x, y = _bil(quads[ph] if ph < len(quads) else None, u, v)
            ajouter("bords", o, n_, _TYPE_BORD[o["etat"]], "bord " + b, x, y, (_LIB_ETAT_EN if langue == "en" else _LIB_ETAT)[o["etat"]])
    for o in surf:
        vis = o.get("visibilite") if o.get("visibilite") in _bar.VISIBILITES else "de_pres"
        n_ = (_bar.SURFACE_DOS.get(o["type"]) if o.get("photo") == 1 and o["type"] in _bar.SURFACE_DOS else _bar.SURFACE[o["type"]])[_bar.VISIBILITES.index(vis)]
        try:
            x, y = max(0, min(1000, int(o.get("x")))), max(0, min(1000, int(o.get("y"))))
        except (TypeError, ValueError):
            x, y = 500, 500
        t_ = o["type"] if o["type"] in _DEFAUTS else "autre"
        ajouter("surface", o, n_, t_, "surface", x, y, o["type"] + ({"rasante": " (raking light)", "de_pres": " (up close)", "visible": ""} if langue == "en"
                                                                   else {"rasante": " (lumiere rasante)", "de_pres": " (de pres)", "visible": ""})[vis])
    ordre = {"fort": 0, "moyen": 1, "leger": 2, "a verifier": 3}
    defauts.sort(key=lambda d: (ordre[d["gravite"]], d["note"]))
    defauts = defauts[:10]
    # 2 nov 2026 (Mathieu : « sois plus precis dans les raisons ; une valeur precise qui sert reellement d'outil ») : chaque
    # sous-note dit ce qui a ete regarde, combien sont nets, OU est chaque probleme, et la regle PSA qui donne la note
    fr = lambda v: str(v).replace(".0", "").replace(".", ",")
    face_ = lambda ph: ("dos " if ph == 1 else "devant ") if nface > 1 else ""
    def num_de(zone, ph):
        return next((str(i + 1) for i, d in enumerate(defauts) if d["zone"] == zone and d["photo"] == ph), "")
    explications = {}
    for k, obs, etats, nomk, tot in (("coins", coins, _bar.ETATS_COIN, "coin", 4 * nface), ("bords", bords, _bar.ETATS_BORD, "bord", 4 * nface)):
        if not obs:
            continue
        nets = sum(1 for o in obs.values() if o["etat"] == "net")
        mal = sorted(((ph, z, o) for (ph, z), o in obs.items() if o["etat"] != "net"), key=lambda t: etats[t[2]["etat"]][0])
        regle = {"coins": {9: "9 : un tout petit défaut", 8.5: "2-3 points blancs", 8: "8 : léger effilochage à 1-2 coins",
                           7: "7 : effilochage à quelques coins", 6: "6/10", 5: "5 : coin légèrement arrondi", 4: "4 : coin arrondi", 3: "3 : coin plié"},
                 "bords": {9: "9 : de fins points sur un seul bord", 8.5: "points sur 2 bords", 8: "8 : quelques points blancs", 7.5: "usure sur plusieurs bords",
                           7: "7 : légère usure", 6: "6 : petite encoche", 5: "5 : ébréchures", 4: "4 : usure nette"}}[k]
        if not mal:
            explications[k] = f"{tot} {nomk}s regardés au zoom : tous nets"
            continue
        parts = [f"{face_(ph)}{nomk} {z} : {_LIB_ETAT.get(o['etat'], o['etat'])}" + (" (à vérifier)" if inc(o) else "")
                 + (f" [{num_de(nomk + ' ' + z, ph)}]" if num_de(nomk + " " + z, ph) else "") for ph, z, o in mal[:3]]
        t = f"{nets}/{len(obs)} nets · " + " ; ".join(parts)
        if hi.get(k) is not None and hi[k] < 10:
            t += f" → {regle.get(hi[k], fr(hi[k]) + '/10')}"
        if lo.get(k) is not None and hi.get(k) is not None and lo[k] < hi[k]:
            t += f" (→ {fr(lo[k])} si les points à vérifier se confirment)"
        explications[k] = t
    if sj:
        if surf:
            parts = [f"{face_(1 if o.get('photo') == 1 else 0)}{o['type']} " + {"rasante": "(lumière rasante seulement)", "de_pres": "(visible de près)", "visible": "(visible)"}.get(o.get("visibilite"), "")
                     + (" (à vérifier)" if inc(o) else "") for o in surf[:3]]
            explications["surface"] = " ; ".join(parts) + (f" → {fr(hi['surface'])}/10" if hi.get("surface") is not None and hi["surface"] < 10 else "")
        else:
            explications["surface"] = "carton imprimé propre : aucune rayure, tache ni pli vus"
    if hi["centrage"] is not None:
        nomr = {r_["axe"] + str(r_["photo"]): r_["element"] for r_ in rep_ if r_.get("element")}
        bouts = []
        if cg:
            bouts.append(f"G/D {cg}" + (f" ({nomr['gd0']})" if nomr.get("gd0") else ""))
        if ch:
            bouts.append(f"H/B {ch}" + (f" ({nomr['hb0']})" if nomr.get("hb0") else ""))
        if cd:
            bouts.append(f"dos {cd}")
        lim = {10: "10 jusqu’à 55/45", 9: "9 jusqu’à 60/40", 8: "8 jusqu’à 65/35", 7: "7 jusqu’à 70/30", 6: "6 jusqu’à 80/20"}.get(int(hi["centrage"]), f"{fr(hi['centrage'])}/10")
        explications["centrage"] = ("mesuré par l’app : " if mesure else "mesuré sur la règle : ") + " · ".join(bouts) + f" → {lim}"
    elif not (cg or ch):
        explications["centrage"] = "aucun repère symétrique sur cette carte : pas compté dans la note"
    notes = {k: hi[k] for k in ("centrage", "coins", "bords", "surface")}
    # 9 nov 2026 (criteres de TAG fournis par Mathieu) : la note TAG avec les memes observations ; « incertaine » ne compte que
    # pour le bas (comme pour PSA) : le haut = sans les observations incertaines, le bas = avec
    try:
        cdev = [x for x in (cg, ch) if x]
        cdos = [x for x in (cent2["dos"].get("gd"), cent2["dos"].get("hb"), cd) if x]
        _t = lambda c_, b_, s_: _bar.tag([(k[0], o["etat"]) for k, o in c_], [(k[0], o["etat"]) for k, o in b_],
                                        [(1 if o.get("photo") == 1 else 0, o["type"], o.get("visibilite") or "de_pres") for o in s_] if sj else [], cdev, cdos)
        tag_hi = _t([kv for kv in coins.items() if not inc(kv[1])], [kv for kv in bords.items() if not inc(kv[1])], [o for o in surf if not inc(o)])
        tag_lo = _t(list(coins.items()), list(bords.items()), surf)
        tag_ = dict(tag_hi, bas=tag_lo.get("note"), bas_libelle=tag_lo.get("libelle"))
    except Exception as e:
        print("TAG : " + repr(e), flush=True)
        tag_ = None
    return {"evaluable": f.get("evaluable") is not False, "tag": tag_, "raison": str(f.get("raison") or "").strip()[:80],
            "centrage_gd": cg, "centrage_hb": ch, "centrage_dos": cd or ((centrage or {}).get("dos") or {}).get("gd") or "",
            "centrage_mesure": mesure, "notes": notes, "notes_bas": {k: lo[k] for k in ("coins", "bords", "surface")},
            "note_min": g_lo, "note_max": g_hi, "defauts": defauts, "explications": explications,
            "invisible": [str(x).strip()[:160] for x in (f.get("invisible") or [])][:4], "conseil": str(f.get("conseil") or "").strip()[:300],
            "calibre": calibre, "bareme": "PSA-1", "centrage_reperes": rep_,
            "observations": {"coins": [dict(photo=k[0], coin=k[1], etat=o["etat"], certitude=o.get("certitude")) for k, o in coins.items()],
                             "bords": [dict(photo=k[0], bord=k[1], etat=o["etat"], certitude=o.get("certitude")) for k, o in bords.items()]}}


def _nettoyer_etat(f, centrage=None, calibration=None):
    """La reponse du modele -> un examen COHERENT : sous-notes plafonnees par les defauts listes, centrage mesure par l'app
    quand on l'a, note globale jamais au-dessus de la pire sous-note + 0,5, fourchette sur l'echelle PSA, calibration
    (l'ecart moyen avec les vraies notes revenues de PSA) appliquee quand on en a assez."""
    def note(v):
        try:
            return max(1.0, min(10.0, round(float(v) * 2) / 2))
        except (TypeError, ValueError):
            return None
    n = f.get("notes") or {}
    notes = {k: note(n.get(k)) for k in ("centrage", "coins", "bords", "surface")}
    rat = lambda s: s if re.fullmatch(r"\d{2}/\d{2}", str(s or "").strip()) else ""
    defauts = []
    for d in (f.get("defauts") or [])[:12]:
        if not isinstance(d, dict) or d.get("zone") not in _ZONES or d.get("type") not in _DEFAUTS:
            continue
        try:
            x, y = max(0, min(1000, int(d.get("x")))), max(0, min(1000, int(d.get("y"))))
        except (TypeError, ValueError):
            continue
        if d.get("sur_relique") is True:                 # 2 nov 2026 : la texture d'une patch n'est pas une rayure
            continue
        defauts.append({"photo": 1 if d.get("photo") == 1 else 0, "zone": d["zone"], "type": d["type"],
                        "gravite": d.get("gravite") if d.get("gravite") in ("a verifier", "leger", "moyen", "fort") else "leger", "x": x, "y": y,
                        "pourquoi": str(d.get("pourquoi") or "").strip()[:120]})
    ordre = {"fort": 0, "moyen": 1, "leger": 2, "a verifier": 3}
    defauts.sort(key=lambda d: ordre.get(d["gravite"], 4))
    # 1. chaque defaut plafonne la sous-note de sa categorie (un coin blanchi n'est pas un coin a 10)
    for d in defauts:
        k = _CAT_ZONE(d["zone"])
        if k and notes.get(k) is not None:
            notes[k] = min(notes[k], _PLAFOND_GRAV[d["gravite"]])
    # 2. le centrage MESURE par l'app remplace l'estimation
    cg, ch = rat(f.get("centrage_gd")), rat(f.get("centrage_hb"))
    mesure = False
    if centrage and centrage.get("devant"):
        cg, ch = centrage["devant"].get("gd") or cg, centrage["devant"].get("hb") or ch
        mesure = True
    if centrage and centrage.get("note") is not None:
        notes["centrage"] = float(centrage["note"])
    # 3. la note globale : jamais au-dessus de la pire sous-note + 0,5 ; au plus 1 point d'ecart ; echelle PSA
    lo, hi = note(f.get("note_min")), note(f.get("note_max"))
    if lo and hi and hi < lo:
        lo, hi = hi, lo
    vals = [v for v in notes.values() if v]
    pire = min(vals or [10])
    if hi is None:
        hi = pire
    hi = min(hi, pire + 0.5)
    lo = min(lo if lo is not None else hi - 1, hi)
    lo = max(lo, hi - 1, pire - 1)
    if calibration and calibration.get("n", 0) >= 15:
        dec = max(-1.0, min(0.5, float(calibration.get("ecart") or 0)))
        lo, hi = lo + dec, hi + dec
    hi = _psa(min(10.0, hi))
    lo = _psa(max(1.0, min(lo, hi)))
    if defauts or pire < 9.5:                     # jamais « 10 » s'il reste un doute
        hi = min(hi, 9.0)
        lo = min(lo, hi)
    # 4. les explications : chaque categorie avec des defauts renvoie a leurs numeros
    ex = f.get("explications") or {}
    explications = {}
    for k in ("centrage", "coins", "bords", "surface"):
        t = str(ex.get(k) or "").strip()[:140]
        nums = [str(i + 1) for i, d in enumerate(defauts) if _CAT_ZONE(d["zone"]) == k]
        if nums:
            t = (t + " " if t else "") + "(" + ("point " if len(nums) == 1 else "points ") + ", ".join(nums) + ")"
        if k == "centrage" and mesure:
            t = "mesuré par l’app : " + " · ".join(x for x in (cg, ch) if x) + ((" — " + t) if t else "")
        if t and (notes.get(k) or 10) < 10:
            explications[k] = t
    return {"evaluable": f.get("evaluable") is not False, "raison": str(f.get("raison") or "").strip()[:80],
            "centrage_gd": cg, "centrage_hb": ch, "centrage_dos": rat(f.get("centrage_dos")) or ((centrage or {}).get("dos") or {}).get("gd") or "",
            "centrage_mesure": mesure, "notes": notes, "note_min": lo, "note_max": hi, "defauts": defauts, "explications": explications,
            "invisible": [str(x).strip()[:160] for x in (f.get("invisible") or [])][:4], "conseil": str(f.get("conseil") or "").strip()[:300],
            "calibre": bool(calibration and calibration.get("n", 0) >= 15)}


_FACES = ("devant", "dos")


def _infos_mesures(prep):
    """3 nov 2026 : les MESURES de l'app, dites au modele (il les confirme ou les corrige sur les zooms)."""
    out = []
    for face, m in (prep.get("mesures") or {}).items():
        u, q, cp = m.get("usure") or {}, m.get("qualite") or {}, m.get("centrage") or {}
        bouts = []
        for nom, x in (u.get("coins") or {}).items():
            if x.get("mesurable") and x.get("blanc_mm2", 0) >= 0.05:
                bouts.append(f"coin {nom} {x['blanc_mm2']} mm2 de pixels blancs a l'arete")
        for nom, x in (u.get("bords") or {}).items():
            if x.get("mesurable") and x.get("blanc_mm", 0) >= 0.3:
                bouts.append(f"bord {nom} {x['blanc_mm']} mm de blanc en {x['points']} point(s)")
            elif x.get("mesurable") and (x.get("points_fins") or 0) >= 3:
                bouts.append(f"bord {nom} : {x['points_fins']} petits points clairs SUR la ligne de coupe (bordure coloree unie) : "
                             f"probablement du blanchiment (points_blancs ou quelques_points)")
        if bouts:
            out.append(f"MESURE de l'app ({face}) : " + " ; ".join(bouts) + ". Verifie chacun sur les zooms : vrai blanchiment, ou reflet / fond ?")
        elif any(x.get("mesurable") for x in list((u.get("coins") or {}).values()) + list((u.get("bords") or {}).values())):
            out.append(f"MESURE de l'app ({face}) : aucun blanc mesure la ou la bordure est foncee ou coloree : un « net » est attendu sauf si tu vois autre chose.")
        sil = m.get("silhouette") or {}
        sb = []
        for nom, x in (sil.get("coins") or {}).items():
            if x.get("mesurable") and (x.get("relatif") or 0) >= 0.25:
                sb.append(f"coin {nom} : {x['manque_mm2']} mm2 de carton manquant (plus rond que les autres coins)")
        for nom, x in (sil.get("cotes") or {}).items():
            for e_ in (x.get("encoches") or [])[:2] if x.get("mesurable") else []:
                if e_["profondeur_mm"] >= 0.2 and e_["longueur_mm"] >= 0.3:
                    sb.append(f"bord {nom} : creux de {e_['profondeur_mm']} mm sur {e_['longueur_mm']} mm, a {e_['pos_mm']} mm du coin")
        if sb:
            out.append(f"FORME de la carte mesuree par l'app ({face}, la silhouette sur le fond) : " + " ; ".join(sb) + ". Confirme sur les zooms : encoche / coin use, ou ombre / reflet ?")
        elif sil.get("coins") or sil.get("cotes"):
            out.append(f"FORME de la carte ({face}) : aretes droites et coins nets a la mesure de l'app (la ou le fond permet de lire).")
        if q.get("reflets"):
            out.append(f"Reflets ({face}) sur : {', '.join(q['reflets'])} : ce qui est sous un reflet n'est pas jugeable (dis-le dans « invisible »).")
        if q and not q.get("assez_grande"):
            out.append(f"La photo ({face}) est petite ({q.get('px_mm')} px par mm) : les tout petits points blancs ne sont pas visibles ; certitude « incertaine » pour eux.")
        for ax, nom in (("gd", "gauche/droite"), ("hb", "haut/bas")):
            x = cp.get(ax)
            if x and x.get("fiabilite") in ("haute", "moyenne"):
                out.append(f"Centrage {face} {nom} : l'app trouve {x['paires']} paire(s) d'elements imprimes en miroir, {x['ratio']} au pire point"
                           + (" ; DECENTRAGE FORT sur un element de design : dis dans centrage_reperes si cet element est dessine ainsi (asymetrique) ou si la coupe est decentree." if x.get("a_verifier") else "."))
    return out


def _ajouter_mesures(res, mes, quads, defauts=True):
    """Les mesures dans le resultat (l'ecran les montre) ; un blanchiment MESURE que le modele n'a pas vu devient un point
    « a verifier » (il n'abaisse que le bas de la fourchette), jamais sous un reflet.
    9 nov 2026 : defauts=False (l'examen complet) : les mesures passent par la contre-verification ; rien de « a verifier »."""
    if not mes:
        return
    res["mesures"] = {}
    reprendre = []
    for face, m in mes.items():
        ph = 0 if face == "devant" else 1
        u, q = m.get("usure") or {}, m.get("qualite") or {}
        sil = m.get("silhouette") or {}
        res["mesures"][face] = {"coins": u.get("coins") or {}, "bords": u.get("bords") or {}, "px_mm": (q or {}).get("px_mm") or u.get("px_mm"),
                                "qualite": q or None, "silhouette": sil or None,
                                "centrage": {ax: ({k: v for k, v in x.items() if k in ("ratio", "paires", "fiabilite", "a_verifier", "reperes", "bordure")} if x else None)
                                             for ax, x in (m.get("centrage") or {}).items()}}
        reprendre += [f"{face} : {t}" for t in (q or {}).get("a_reprendre") or []]
        reflets = set((q or {}).get("reflets") or [])
        if not (q or {}).get("assez_grande", True):
            continue
        deja = {(d.get("photo"), d.get("zone")) for d in res.get("defauts") or []}
        for nom, x in (u.get("coins") or {}).items():
            if x.get("mesurable") and x.get("blanc_mm2", 0) >= 0.25 and nom not in reflets and (ph, "coin " + nom) not in deja:
                xy = _bil(quads[ph] if quads and ph < len(quads) else None, *{"haut-gauche": (0.02, 0.02), "haut-droit": (0.98, 0.02),
                                                                             "bas-droit": (0.98, 0.98), "bas-gauche": (0.02, 0.98)}[nom])
                res.setdefault("defauts", []).append({"photo": ph, "zone": "coin " + nom, "type": "blanchiment", "gravite": "a verifier",
                                                      "x": xy[0], "y": xy[1], "note": 8 if x["blanc_mm2"] >= 0.6 else 9, "mesure": True,
                                                      "pourquoi": f"mesuré par l'app : {str(x['blanc_mm2']).replace('.', ',')} mm² de blanc à l'arête, à confirmer sur le zoom"})
        # 9 nov 2026 : des points de blanchiment SUR la ligne de coupe d'une bordure coloree, mesures, que le modele n'a pas vus
        for nom, x in (u.get("bords") or {}).items():
            pf = x.get("points_fins") or 0
            if x.get("mesurable") and pf >= 3 and (ph, "bord " + nom) not in deja:
                uv = {"haut": (0.5, 0.01), "bas": (0.5, 0.99), "gauche": (0.01, 0.5), "droit": (0.99, 0.5)}[nom]
                xy = _bil(quads[ph] if quads and ph < len(quads) else None, *uv)
                res.setdefault("defauts", []).append({"photo": ph, "zone": "bord " + nom, "type": "blanchiment", "gravite": "a verifier",
                                                      "x": xy[0], "y": xy[1], "note": 8 if pf >= 5 else 9, "mesure": True,
                                                      "pourquoi": f"mesuré par l'app : {pf} petits points blancs sur l'arête, à confirmer sur le zoom"})
    for face, m in mes.items():
        ph = 0 if face == "devant" else 1
        sil = m.get("silhouette") or {}
        q_ = quads[ph] if quads and ph < len(quads) else None
        deja = {(d.get("photo"), d.get("zone")) for d in res.get("defauts") or []}
        px = sil.get("px_mm") or 0
        for nom, x in (sil.get("coins") or {}).items():
            if x.get("mesurable") and (x.get("relatif") or 0) >= 0.3 and (ph, "coin " + nom) not in deja:
                uv = {"haut-gauche": (0.02, 0.02), "haut-droit": (0.98, 0.02), "bas-droit": (0.98, 0.98), "bas-gauche": (0.02, 0.98)}[nom]
                xy = _bil(q_, *uv)
                res.setdefault("defauts", []).append({"photo": ph, "zone": "coin " + nom, "type": "coin mou", "gravite": "a verifier", "x": xy[0], "y": xy[1],
                                                      "note": 8 if x["relatif"] >= 0.8 else 9, "mesure": True,
                                                      "pourquoi": f"mesuré par l'app : {str(x['manque_mm2']).replace('.', ',')} mm² de carton en moins à la pointe (plus rond que les autres coins), à confirmer sur le zoom"})
        if not px:
            continue
        for nom, x in (sil.get("cotes") or {}).items():
            if not x.get("mesurable"):
                continue
            for e_ in [e_ for e_ in x.get("encoches") or [] if e_["profondeur_mm"] >= 0.2 and e_["longueur_mm"] >= 0.3][:2]:
                if (ph, "bord " + nom) in deja:
                    break
                t = e_["pos_mm"]
                # la carte peut etre couchee : la longueur du cote en mm vient de la silhouette elle-meme
                cote_mm = (sil.get("dims_mm") or {}).get(nom) or (63.5 if nom in ("haut", "bas") else 88.9)
                f = max(0.03, min(0.97, t / cote_mm))
                uv = {"haut": (f, 0.01), "bas": (f, 0.99), "gauche": (0.01, f), "droit": (0.99, f)}[nom]
                xy = _bil(q_, *uv)
                res.setdefault("defauts", []).append({"photo": ph, "zone": "bord " + nom, "type": "entaille", "gravite": "a verifier", "x": xy[0], "y": xy[1],
                                                      "note": 8 if e_["profondeur_mm"] >= 0.4 else 9, "mesure": True,
                                                      "pourquoi": f"mesuré par l'app : l'arête rentre de {str(e_['profondeur_mm']).replace('.', ',')} mm sur {str(e_['longueur_mm']).replace('.', ',')} mm, à confirmer sur le zoom"})
                deja.add((ph, "bord " + nom))
    if not defauts:
        res["defauts"] = [d for d in res.get("defauts") or [] if not d.get("mesure")]
    ajoutes = [d for d in res.get("defauts") or [] if d.get("mesure")]
    if ajoutes and res.get("notes"):
        bas = dict(res.get("notes_bas") or {})
        for cat, zone in (("coins", "coin"), ("bords", "bord")):
            l_ = [d["note"] for d in ajoutes if str(d.get("zone", "")).startswith(zone)]
            if l_:
                bas[cat] = min([v for v in (bas.get(cat), (res["notes"] or {}).get(cat)) if v is not None] + l_)
        tout = {k: (bas.get(k) if bas.get(k) is not None else v) for k, v in res["notes"].items()}
        g = _bar.globale(tout)
        res["notes_bas"] = bas
        if g is not None and res.get("note_min") is not None:
            res["note_min"] = min(res["note_min"], g)
    if reprendre:
        res["a_reprendre"] = reprendre[:4]


# -- 9 nov 2026 : la CONTRE-VERIFICATION --------------------------------------------------------------------------------
# Mathieu (la Hutson) : « ca aucun rapport » : un coin haut-gauche « blanchi » dont la pointe est nette (le blanc etait le
# long du bord du haut, deja compte), un bord droit invente. Et : « quand l'IA doute : ne rien montrer ». Chaque defaut de
# coin ou de bord (vu par l'IA, ou mesure par l'app) est donc revu un a un sur un gros plan PLEINE RESOLUTION de cet
# endroit precis, par un second examen strict : confirme -> il compte ; rejete -> il disparait ; flou -> il ne compte pas,
# et l'app demande une meilleure photo de ce coin.
VERIF_MAX = 12
SYSTEME_VERIF = """Tu es un grader PSA tres strict. Un premier examen d'une carte de sport a releve des defauts de coins et de
bords. Ton travail : CONTRE-VERIFIER chacun sur son gros plan (pleine resolution, carte redressee, un peu de fond autour).
Pour chaque numero :
- « confirme » : tu VOIS le defaut decrit, a cet endroit, dans ce gros plan. Donne l'etat exact que tu vois.
- « rejete » : l'endroit est net ; ou ce qu'on voit est de la poussiere, une fibre posee dessus, un reflet, le grain de la photo,
  l'ombre de l'arete, le dessin imprime ; ou, pour un COIN, la pointe elle-meme (les 1-2 derniers mm) est nette et le blanc
  est plus loin le long d'une arete (il appartient au BORD, pas au coin).
- « flou » : le gros plan ne permet pas de trancher (flou, trop petit, reflet qui cache, coin coupe par la photo).
Regles : un coin se juge a sa POINTE contre le fond ; compare avec les autres coins de la meme face (fournis). Un coin
IMPRIME EN BLANC : le blanc est l'impression, pas du blanchiment ; seule la forme compte, et le flou ou l'ombre de l'arete
contre un fond noir n'est pas une pointe adoucie (rejete, sauf pointe clairement ronde ou ecrasee). Une bordure ARGENT
ou grise : le blanchiment est un blanc pur et mat, un peu effiloche, plus epais qu'aux autres coins ; le mince filet de
lumiere regulier de la coupe, present partout, n'en est pas. Un point blanc
SUR la ligne de coupe d'une bordure coloree ou foncee est du blanchiment ; un point blanc dans la surface est de la poussiere.
Ne confirme jamais par prudence : dans le doute, « flou ». Reponds avec l'outil « verdicts »."""
_ETATS_TOUS = sorted(set(_bar.ETATS_COIN) | set(_bar.ETATS_BORD))
OUTIL_VERIF = {
    "name": "verdicts",
    "description": "Le verdict de chaque defaut contre-verifie.",
    "input_schema": {"type": "object", "properties": {"verdicts": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["confirme", "rejete", "flou"]},
        "etat": {"type": "string", "enum": _ETATS_TOUS, "description": "Si confirme : l'etat exact vu (coins : point_blanc, effilochage_leger, effilochage, arrondi_leger, arrondi, plie ; bords : point_blanc, quelques_points, usure_legere, encoche, ebrechures, usure)"},
        "pourquoi": {"type": "string", "description": "Ce que tu vois, en une phrase courte"}},
        "required": ["n", "verdict"]}}}, "required": ["verdicts"]}}


def _candidats_verif(f, mes):
    """Les defauts a contre-verifier : ceux de l'IA (coins, bords ; pas « incertaine ») et ceux MESURES par l'app la ou
    l'IA voit net. -> [{sorte, ph, nom, etat, vu, obs?, position?}]"""
    out = []
    for sorte, cle, etats in (("coin", "coin", _bar.ETATS_COIN), ("bord", "bord", _bar.ETATS_BORD)):
        for o in f.get(sorte + "s") or []:
            if not isinstance(o, dict) or o.get(cle) not in (_bar.COINS if sorte == "coin" else _bar.BORDS):
                continue
            ph = 1 if o.get("photo") == 1 else 0
            if o.get("etat") in etats and o["etat"] != "net" and o.get("certitude") != "incertaine":
                out.append({"sorte": sorte, "ph": ph, "nom": o[cle], "etat": o["etat"], "vu": str(o.get("pourquoi") or "")[:140], "obs": o,
                            "position": o.get("position") if isinstance(o.get("position"), int) else None})
    for face, m in (mes or {}).items():
        ph = 0 if face == "devant" else 1
        q = m.get("qualite") or {}
        if not q.get("assez_grande", True):
            continue
        reflets = set(q.get("reflets") or [])
        u, sil = m.get("usure") or {}, m.get("silhouette") or {}
        def ajout(sorte, nom, etat, vu):
            # deja dans la liste (l'IA y voit un defaut) : rien ; l'IA y voit net : la mesure le fait revoir
            if any(c["sorte"] == sorte and c["ph"] == ph and c["nom"] == nom for c in out):
                return
            out.append({"sorte": sorte, "ph": ph, "nom": nom, "etat": etat, "vu": vu, "obs": None, "mesure": True, "position": None})
        for nom, x in (u.get("coins") or {}).items():
            if x.get("mesurable") and x.get("blanc_mm2", 0) >= 0.25 and nom not in reflets:
                ajout("coin", nom, "effilochage_leger" if x["blanc_mm2"] >= 0.6 else "point_blanc",
                      f"l'app mesure {x['blanc_mm2']} mm2 de blanc a l'arete du coin")
        for nom, x in (u.get("bords") or {}).items():
            pf = x.get("points_fins") or 0
            if x.get("mesurable") and pf >= 3:
                ajout("bord", nom, "quelques_points" if pf >= 5 else "point_blanc", f"l'app mesure {pf} petits points blancs sur la ligne de coupe")
        for nom, x in (sil.get("coins") or {}).items():
            if x.get("mesurable") and (x.get("relatif") or 0) >= 0.3:
                ajout("coin", nom, "point_blanc" if x["relatif"] < 0.8 else "effilochage_leger",
                      f"l'app mesure {x.get('manque_mm2')} mm2 de carton en moins a la pointe (plus rond que les autres coins)")
        for nom, x in (sil.get("cotes") or {}).items():
            if x.get("mesurable") and any(e_["profondeur_mm"] >= 0.2 and e_["longueur_mm"] >= 0.3 for e_ in x.get("encoches") or []):
                ajout("bord", nom, "encoche", "l'app mesure un petit creux dans l'arete")
    return out[:VERIF_MAX]


def _gros_plan_verif(z, c):
    """Le gros plan d'un candidat dans la carte redressee z (3 % de fond autour) : un coin (carre) ou un bord (bande a
    l'horizontale ; sans position : tout le bord en deux moities)."""
    from PIL import Image
    W, H = z.size
    mx, my = W * 0.03 / 1.06, H * 0.03 / 1.06
    court = min(W, H)
    if c["sorte"] == "coin":
        s = int(court * 0.16)
        x = 0 if "gauche" in c["nom"] else W - s
        y = 0 if "haut" in c["nom"] else H - s
        im = z.crop((x, y, x + s, y + s))
        k = min(4.0, 900 / max(1, s))
        return im.resize((int(s * k), int(s * k)), Image.LANCZOS)
    ep = int(my + court * 0.06) if c["nom"] in ("haut", "bas") else int(mx + court * 0.06)
    if c["nom"] == "haut":
        bande = z.crop((0, 0, W, ep))
    elif c["nom"] == "bas":
        bande = z.crop((0, H - ep, W, H)).rotate(180, expand=True)
    elif c["nom"] == "gauche":
        bande = z.crop((0, 0, ep, H)).rotate(90, expand=True)     # le haut de la carte a gauche (comme le bord droit)
    else:
        bande = z.crop((W - ep, 0, W, H)).rotate(90, expand=True)
    L, E = bande.size
    if c.get("position") is not None:
        t = max(0.0, min(1.0, c["position"] / 1000))
        if c["nom"] == "bas":
            t = 1 - t                                     # la bande du bas est retournee : le sens de lecture s'inverse
        lg = int(L * 0.4)
        x0 = int(max(0, min(L - lg, t * L - lg / 2)))
        im = bande.crop((x0, 0, x0 + lg, E))
    else:
        a, b = bande.crop((0, 0, L // 2, E)), bande.crop((L // 2, 0, L, E))
        im = Image.new("RGB", (L // 2, 2 * E + 8), (60, 60, 60))
        im.paste(a, (0, 0)); im.paste(b, (0, E + 8))
    k = min(3.0, 1400 / max(1, im.size[0]))
    return im.resize((max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))), Image.LANCZOS)


def _contre_verifier(cands, zimgs, langue="fr"):
    """-> {n: {verdict, etat, pourquoi}} ou None (rien a verifier, pas d'images, erreur)."""
    import examen
    cands = [c for c in cands if c["ph"] < len(zimgs or []) and zimgs[c["ph"]] is not None]
    if not cands:
        return None
    contenu = []
    for ph in sorted({c["ph"] for c in cands if c["sorte"] == "coin"}):
        face = "devant" if ph == 0 else "dos"
        contenu += [{"type": "text", "text": f"Pour comparer : les 4 coins du {face}."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(examen.jpeg(examen.mosaique_coins(zimgs[ph], face), 1290, 90)).decode()}}]
    for i, c in enumerate(cands, 1):
        face = "devant" if c["ph"] == 0 else "dos"
        lib = _LIB_ETAT.get(c["etat"], c["etat"])
        ou = f"le {c['sorte']} {c['nom']} du {face}" + ("" if c["sorte"] == "coin" else " (la bande montre ce bord a l'horizontale" + (", le haut de la carte a gauche" if c["nom"] in ("gauche", "droit") else "") + (")" if c.get("position") is not None
                                                                                       else " ; tout le bord, en deux moities l'une sous l'autre)"))
        contenu += [{"type": "text", "text": f"#{i} : {ou}. Le premier examen dit : {lib}" + (f" — « {c['vu']} »" if c.get("vu") else "") + "."},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(examen.jpeg(_gros_plan_verif(zimgs[c["ph"]], c), 1568, 92)).decode()}}]
    contenu.append({"type": "text", "text": f"Donne un verdict pour chacun des {len(cands)} numeros avec l'outil « verdicts »."
                    + (" Write « pourquoi » in plain English." if langue == "en" else " Ecris « pourquoi » en francais simple.")})
    corps = {"model": MODELE_ETAT, "max_tokens": 8000, "system": SYSTEME_VERIF, "tools": [OUTIL_VERIF],
             "thinking": {"type": "enabled", "budget_tokens": 4000}, "tool_choice": {"type": "auto"},
             "messages": [{"role": "user", "content": contenu}]}
    try:
        r = _appeler(corps, timeout=180)
        if not any(b.get("type") == "tool_use" and b.get("name") == "verdicts" for b in r.get("content") or []):
            r = _appeler({"model": MODELE_ETAT, "max_tokens": 2000, "system": SYSTEME_VERIF, "tools": [OUTIL_VERIF],
                          "tool_choice": {"type": "tool", "name": "verdicts"}, "messages": [{"role": "user", "content": contenu}]}, timeout=120)
        _noter_etat(r.get("usage") or {})
    except Exception as e:
        print("Vision (contre-verification) : " + repr(e), flush=True)
        return None
    v = next((b.get("input") for b in r.get("content") or [] if b.get("type") == "tool_use" and b.get("name") == "verdicts"), None)
    if not isinstance(v, dict) or not isinstance(v.get("verdicts"), list):
        return None
    out = {}
    for x in v["verdicts"]:
        try:
            n = int(x.get("n"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= n <= len(cands) and x.get("verdict") in ("confirme", "rejete", "flou"):
            out[n] = {"verdict": x["verdict"], "etat": x.get("etat"), "pourquoi": str(x.get("pourquoi") or "").strip()[:140]}
    return {"cands": cands, "verdicts": out} if out else None


def _appliquer_verif(f, v):
    """Les verdicts dans les observations f (en place). -> (rejetes, flous) : [« dos coin haut-gauche », ...]."""
    rejetes, flous = [], []
    for i, c in enumerate(v["cands"], 1):
        x = v["verdicts"].get(i)
        if not x:
            continue
        etats = _bar.ETATS_COIN if c["sorte"] == "coin" else _bar.ETATS_BORD
        nom = f"{'dos' if c['ph'] == 1 else 'devant'} {c['sorte']} {c['nom']}"
        o = c.get("obs")
        if x["verdict"] == "rejete":
            rejetes.append(nom)
            if o is not None:
                o.update(etat="net", contre_verifie="rejete")
        elif x["verdict"] == "flou":
            flous.append(nom)
            if o is not None:
                o.update(certitude="incertaine", contre_verifie="flou")
        else:
            et = x.get("etat") if x.get("etat") in etats and x.get("etat") != "net" else c["etat"]
            pq = x.get("pourquoi") or c.get("vu") or ""
            if o is not None:
                o.update(etat=et, certitude="sure", contre_verifie="confirme", pourquoi=pq)
            else:
                cle = "coin" if c["sorte"] == "coin" else "bord"
                l = f.setdefault(c["sorte"] + "s", [])
                l[:] = [y for y in l if not (isinstance(y, dict) and (1 if y.get("photo") == 1 else 0) == c["ph"] and y.get(cle) == c["nom"])]
                l.append({"photo": c["ph"], cle: c["nom"], "etat": et, "certitude": "sure", "pourquoi": pq, "contre_verifie": "confirme", "mesure": True})
    return rejetes, flous


def etat(*a, **k):
    """3 nov 2026 (revue de securite) : un examen a la fois par compte, compte dans le quota PENDANT l'appel (une rafale de
    requetes ne depasse plus le quota du mois)."""
    st = statut_etat()
    r_ = _reserver("etat", st["ce_mois"], st["limite"])
    if r_ is None:
        raise Erreur(f"Tes {st['limite']} analyses d'état du mois sont utilisées (ou un examen est déjà en cours).")
    try:
        return _etat(*a, **k)
    finally:
        _liberer(r_)


def _etat(photos, langue="fr", quads=None, rasante=None, calibration=None, regles=None, contexte=None, rasante2=None, gros_plans=None):
    """photos : devant (et dos) en data URL ; quads : les 4 coins de la carte dans chaque photo (0..1000, trouves dans le
    telephone) ; rasante : une photo en lumiere rasante (facultative). Son propre quota par mois (3 gratuit, 30 Pro)."""
    import examen
    if not disponible():
        raise Erreur("Analyse photo pas encore activée sur ce serveur.")
    photos = [p for p in (photos or []) if p][:2]
    if not photos:
        raise Erreur("Il faut au moins la photo du devant")
    brutes = [_decoder(p, MAX_OCTETS_EXAMEN)[0] for p in photos]
    ras = _decoder(rasante, MAX_OCTETS_EXAMEN)[0] if rasante else None
    ras2 = _decoder(rasante2, MAX_OCTETS_EXAMEN)[0] if (rasante and rasante2) else None
    # 3 nov 2026 : les gros plans des coins [{face, coin, photo (data URL)}]
    gps = []
    for g in (gros_plans or [])[:8]:
        if isinstance(g, dict) and g.get("photo") and g.get("coin") in _bar.COINS and g.get("face") in ("devant", "dos"):
            try:
                gps.append({"face": g["face"], "coin": g["coin"], "octets": _decoder(g["photo"], MAX_OCTETS_EXAMEN)[0]})
            except Exception:
                pass
    langue = "en" if str(langue or "").lower().startswith("en") else "fr"
    # 3 nov 2026 (revue) : la cle porte aussi le contexte (slab, patch, auto), les regles apprises et le ROLE de chaque photo
    h = hashlib.sha256(b"etat-v10-" + langue.encode() + json.dumps(quads or [], sort_keys=True).encode()
                       + json.dumps(calibration or {}, sort_keys=True).encode() + json.dumps(contexte or {}, sort_keys=True, default=str).encode()
                       + json.dumps(list(regles or []), ensure_ascii=False).encode())
    for role, b in [(b"dev", brutes[0])] + ([(b"dos", brutes[1])] if len(brutes) > 1 else []) + ([(b"ras", ras)] if ras else []) + ([(b"ras2", ras2)] if ras2 else []):
        h.update(role + hashlib.sha256(b).digest())
    for g in gps:
        h.update((g["face"] + g["coin"]).encode() + hashlib.sha256(g["octets"]).digest())
    cle_cache = h.hexdigest()
    cache = _lire(_chemin_cache())
    if cle_cache in cache:
        return dict(cache[cle_cache], ok=True, cache=True)
    _verifier_etat()
    if examen.disponible():
        prep = examen.preparer(brutes, quads, ras, ras2, gros_plans=gps, slab=bool((contexte or {}).get("slab")))
    else:
        prep = {"images": [(("Photo 0 : le devant." if i == 0 else "Photo 1 : le dos."), b) for i, b in enumerate(brutes)], "centrage": None,
                "note_centrage": None, "zooms": False}
    contenu = []
    for lib, b in prep["images"]:
        contenu.append({"type": "text", "text": lib})
        contenu.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b).decode()}})
    c = prep.get("centrage") or {}
    note_c = prep.get("note_centrage")
    # 3 nov 2026 : un axe « a verifier » (fort decentrage lu sur un element du dessin) n'est pas une mesure : on le retire
    # du centrage mesure et on le dit a part
    verif_c = prep.get("centrage_verifier") or {}
    c = {f: {ax: (None if ax in verif_c.get(f, []) else v) for ax, v in d.items()} for f, d in c.items()}
    c = {f: d for f, d in c.items() if any(d.values())}
    infos = []
    for f, axes in verif_c.items():
        for ax in axes:
            v_ = ((prep.get("centrage") or {}).get(f) or {}).get(ax)
            if v_:
                infos.append(f"Centrage {f} {'gauche/droite' if ax == 'gd' else 'haut/bas'} : l'app lit {v_}, mais sur un element du DESSIN "
                             f"(logo, titre), pas sur une bordure : peut-etre imprime ainsi. Dis dans centrage_reperes ce que tu vois.")
    if c.get("devant"):
        infos.append("CENTRAGE MESURE par l'app (devant) : " + " ; ".join(f"{k} {v}" for k, v in (("gauche/droite", c["devant"].get("gd")),
                                                                                                   ("haut/bas", c["devant"].get("hb"))) if v)
                     + (f" ; dos {c['dos'].get('gd') or c['dos'].get('hb')}" if c.get("dos") else "") + (f" -> sous-note centrage {note_c}." if note_c else "."))
    elif prep.get("zooms"):
        infos.append("L'app n'a pas pu mesurer le centrage (pas de bordure nette) : estime-le, ou dis « non mesurable ».")
    infos += _infos_mesures(prep)
    if prep.get("gros_plans"):
        infos.append("GROS PLANS fournis pour : " + ", ".join(f"{g['face']} {g['coin']}" for g in prep["gros_plans"]) + ". Pour CES coins, "
                     "l'etat et la certitude viennent du gros plan (un blanc de 0,1 mm s'y voit) ; le zoom sert seulement a confirmer. "
                     "Un defaut vu seulement sur un gros plan : mets-le au coin correspondant, x / y = ce coin dans la photo entiere.")
    for r in (regles or [])[:6]:
        infos.append(r)
    cx = contexte or {}                                   # 2 nov 2026 : ce que l'app sait de la carte
    if cx.get("titre"):
        infos.append("La carte : " + str(cx["titre"])[:160] + ".")
    if cx.get("relique"):
        infos.append("CETTE CARTE A UNE PATCH / RELIQUE (tissu) : sa texture, ses fils, ses coutures et ses plis ne sont jamais des "
                     "defauts ; marque sur_relique = true si tu hesites.")
    if cx.get("slab"):                                    # 3 nov 2026 : photographiee dans son slab (PSA, BGS...)
        infos.append("LA CARTE EST DANS UN SLAB (etui de gradation) : les reflets, les rayures et la poussiere du PLASTIQUE ne sont pas "
                     "des defauts de la carte ; l'arete se voit contre le bord interieur de l'etui. Dans le doute, certitude « incertaine ».")
    if cx.get("auto"):
        infos.append("Carte autographiee : l'encre et l'autocollant ne sont pas des defauts de surface.")
    contenu.append({"type": "text", "text": "Evalue l'etat de cette carte : centrage, coins, bords, surface. " + " ".join(infos) + " "
                    + ("Write every text field in plain English." if langue == "en" else "Ecris tous les textes en francais simple (dis « carte », jamais « card »).")})
    # 2 nov 2026 (Mathieu : « l'analyse doit etre tres poussee, aussi parfaite que TAG ; le modele le plus avance s'il faut ») :
    # le modele le plus avance (MODELE) AVEC reflexion : il examine chaque zoom et compare aux descriptions PSA avant de
    # repondre. La reflexion demande tool_choice « auto ». Si l'API la refuse, la meme analyse sans reflexion.
    corps = {"model": MODELE_ETAT, "max_tokens": 16000, "system": SYSTEME_ETAT, "tools": [OUTIL_ETAT],
             "thinking": {"type": "enabled", "budget_tokens": REFLEXION_ETAT}, "tool_choice": {"type": "auto"},
             "messages": [{"role": "user", "content": contenu + [{"type": "text", "text": "Examine chaque zoom un a un, puis reponds avec l'outil « etat »."}]}]}
    try:
        r = _appeler(corps, timeout=240) if REFLEXION_ETAT else None
    except Erreur as e:
        print("Vision (etat) : reflexion refusee, analyse sans : " + str(e), flush=True)
        r = None
    if not r or not any(b.get("type") == "tool_use" for b in r.get("content") or []):
        r = _appeler({"model": MODELE_ETAT, "max_tokens": 3000, "system": SYSTEME_ETAT, "tools": [OUTIL_ETAT],
                      "tool_choice": {"type": "tool", "name": "etat"}, "messages": [{"role": "user", "content": contenu}]}, timeout=120)
    _noter_etat(r.get("usage") or {})
    f = next((b.get("input") for b in r.get("content") or [] if b.get("type") == "tool_use"), None)
    if not f:
        raise Erreur("Analyse impossible : reprends la photo de plus près, sans reflet.")
    # 3 nov 2026 (revue) : un seul axe mesure, « a verifier » (retire de c) : son bas de fourchette compte quand meme
    cent = dict(c, note=note_c, note_bas=prep.get("note_centrage_bas"), verifier=prep.get("centrage_verifier") or {}) \
        if (c or prep.get("note_centrage_bas") is not None) else None
    verif, rejetes, flous = None, [], []
    if isinstance(f.get("coins"), list):
        # 9 nov 2026 : la contre-verification de chaque defaut de coin et de bord, sur son gros plan
        verif = _contre_verifier(_candidats_verif(f, prep.get("mesures") or {}), prep.get("zooms_img") or [], langue)
        if verif:
            rejetes, flous = _appliquer_verif(f, verif)
    q_ok = prep.get("quads") if prep.get("quads") and any(prep["quads"]) else quads
    res = _noter_observations(f, cent, calibration, q_ok, langue) if isinstance(f.get("coins"), list) else _nettoyer_etat(f, cent, calibration)
    res["zooms"] = bool(prep.get("zooms"))
    _ajouter_mesures(res, prep.get("mesures") or {}, q_ok, defauts=not isinstance(f.get("coins"), list))
    res["contre_verif"] = {"fait": bool(verif), "n": len((verif or {}).get("cands") or []), "rejetes": rejetes, "flous": flous}
    if flous:
        res["a_reprendre"] = (res.get("a_reprendre") or []) + [("not sharp enough to judge: " if langue == "en" else "pas assez net pour juger : ")
                                                              + ", ".join(flous[:3]) + (" (take a close-up)" if langue == "en" else " (prends un gros plan)")]
    # 9 nov 2026 (la Hutson : la carte touchait le bas de la photo) : une carte collee au bord de la photo -> ses coins se
    # jugent mal ; on demande un peu de fond tout autour
    for j, q_ in enumerate(q_ok or []):
        if q_ and len(q_) == 4 and any(min(x, y) < 12 or max(x, y) > 988 for x, y in q_):
            res["a_reprendre"] = (res.get("a_reprendre") or []) + [(("front" if j == 0 else "back") + ": the card touches the edge of the photo, leave a little background all around"
                                                                   if langue == "en" else ("devant" if j == 0 else "dos") + " : la carte touche le bord de la photo, laisse un peu de fond tout autour")]
    if prep.get("quads") and any(prep["quads"]):
        res["quads_utilises"] = [[[round(float(x), 1), round(float(y), 1)] for x, y in q] if q else None for q in prep["quads"]]
    if prep.get("gros_plans"):
        res["gros_plans_q"] = [{k: g.get(k) for k in ("face", "coin", "nettete", "net")} for g in prep["gros_plans"]]
        flous = [f"{g['face']} {g['coin']}" for g in prep["gros_plans"] if g.get("net") is False]
        if flous:
            res["a_reprendre"] = (res.get("a_reprendre") or []) + ["gros plan flou (" + ", ".join(flous) + ") : approche-toi moins, touche le coin à l'écran pour le focus"]
    with _verrou:
        cache = _lire(_chemin_cache())
        cache[cle_cache] = res
        if len(cache) > 2000:
            cache = dict(list(cache.items())[-1500:])
        _ecrire(_chemin_cache(), cache)
    return dict(res, ok=True, cache=False)


# -- 2 nov 2026 : la PHOTO d'un deal trop beau ---------------------------------------------------------------------------
# Mathieu : un « Beckett Sennecke Young Guns #701 » a -83 % : la photo montre la Young Guns CHECKLIST Sennecke / Catton (#740),
# le titre ne le dit pas. Un deal tres en dessous de sa valeur (le prix d'une autre carte ?) est verifie sur sa photo : la
# meme carte que celle qu'on a valorisee ? Budget a part (LR_DEALS_PHOTO_JOUR, 40 par jour), une seule fois par annonce.
DEALS_PHOTO_JOUR = 40
_PROBLEMES_DEAL = ["aucun", "checklist", "autre joueur", "autre numero", "autre version", "gradee", "abimee", "reimpression", "pas visible"]
OUTIL_DEAL = {
    "name": "verdict",
    "description": "Dis si la photo montre exactement la carte decrite.",
    "input_schema": {"type": "object", "properties": {
        "meme_carte": {"type": "boolean", "description": "true si la photo montre bien la carte decrite (ou si la photo ne permet pas de juger)"},
        "probleme": {"type": "string", "enum": _PROBLEMES_DEAL},
        "detail": {"type": "string", "description": "Une phrase courte : ce que la photo montre vraiment (ex. « Young Guns Checklist Sennecke / Catton #740 »)"}},
        "required": ["meme_carte", "probleme"]}}
SYSTEME_DEAL = """Tu verifies des annonces eBay de cartes de sport pour une app qui trouve des aubaines. Une annonce semble tres en
dessous de la valeur de la carte que son titre decrit : souvent, c'est une AUTRE carte, moins chere. Regarde la photo et dis
si c'est exactement la carte decrite. Pieges frequents :
- une carte CHECKLIST : le mot « Checklist » imprime, ou deux joueurs cote a cote avec une plage de numeros (ex. « 701-750 ») ;
- un autre joueur, un autre numero de carte, une autre version (base au lieu de Young Guns, Canvas, variante, parallele) ;
- une carte gradee en boitier (slab) alors que le titre decrit une carte raw, ou l'inverse ;
- une reimpression, une carte « custom », une carte abimee (pli, coin arrache).
Si la photo est floue, partielle ou ne permet pas de juger : meme_carte = true et probleme = « pas visible ». N'invente rien."""


def _deals_photo_compteur(ajout=0):
    import comptes
    ch = os.path.join(comptes.DONNEES, "vision_deals.json")
    jour = datetime.now().strftime("%Y-%m-%d")
    with _verrou:
        d = _lire(ch)
        n = int((d.get("jours") or {}).get(jour) or 0)
        if ajout:
            d["jours"] = {jour: n + ajout}
            _ecrire(ch, d)
    return n


def verifier_deal(photo_url, titre, attendu=None):
    """-> {"meme_carte", "probleme", "detail"} ou None (pas de cle, budget du jour atteint, erreur). Jamais d'exception."""
    if not disponible() or not photo_url or not str(photo_url).startswith("https://"):
        return None
    try:
        lim = int(os.environ.get("LR_DEALS_PHOTO_JOUR") or DEALS_PHOTO_JOUR)
    except ValueError:
        lim = DEALS_PHOTO_JOUR
    if _deals_photo_compteur() >= lim:
        return None
    _, serveur = _chemins()
    if (_lire(serveur).get(_mois()) or {}).get("usd", 0) >= PLAFOND_SERVEUR_USD:
        return None
    url = re.sub(r"/s-l\d+\.(jpg|jpeg|png|webp)", r"/s-l1600.\1", str(photo_url))
    texte = f"Titre de l'annonce : {titre}\nLa carte qu'on a valorisee : {attendu or titre}\nEst-ce exactement cette carte ?"
    try:
        r = _appeler({"model": MODELE, "max_tokens": 300, "system": SYSTEME_DEAL, "tools": [OUTIL_DEAL],
                      "tool_choice": {"type": "tool", "name": "verdict"},
                      "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "url", "url": url}},
                                                                 {"type": "text", "text": texte}]}]}, timeout=45)
    except Exception as e:
        print("Vision (deal) : " + repr(e), flush=True)
        return None
    _deals_photo_compteur(1)
    try:
        u = r.get("usage") or {}
        usd = int(u.get("input_tokens") or 0) / 1e6 * PRIX_ENTREE + int(u.get("output_tokens") or 0) / 1e6 * PRIX_SORTIE
        with _verrou:
            d = _lire(serveur)
            m = d.setdefault(_mois(), {"n": 0, "usd": 0.0})
            m["usd"] = round(m["usd"] + usd, 5)
            _ecrire(serveur, d)
    except Exception:
        pass
    v = next((b.get("input") for b in r.get("content") or [] if b.get("type") == "tool_use"), None)
    if not isinstance(v, dict):
        return None
    pb = v.get("probleme") if v.get("probleme") in _PROBLEMES_DEAL else "aucun"
    meme = v.get("meme_carte") is not False or pb in ("aucun", "pas visible")
    return {"meme_carte": bool(meme), "probleme": pb, "detail": str(v.get("detail") or "")[:140]}
