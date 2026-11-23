"""
LOCKERROOM - serveur web (Flask). Outils pour breakers, boutiques eBay et
boutiques physiques de cartes de sport (hockey, NFL, NBA, MLB). App separee de Hall of Cardz :
autre dossier, autre base (lockerroom.db), autre port (8430).

Lancer : Lancer_LockerRoom.bat  (ou : python server.py)
  Sur ce PC       : http://localhost:8430
  iPhone (wifi)   : http://<ip-du-pc>:8430

Routes :
  /                  l'app (ui/app.html)
  /b/<jeton>         page publique d'un break (transparence, lecture seule)
  /api/b/<jeton>     donnees de cette page
  POST /api/<methode> appelle Api.<methode>(*args JSON)
"""
import json
import os
import sys
import shutil
import threading
import time
from datetime import date, datetime, timedelta, timezone

DOSSIER = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("LOCKERROOM_PORT", "8430"))
_VERROU = None


def _prendre_verrou():
    """Une seule copie a la fois (sinon deux serveurs sur le meme port)."""
    global _VERROU
    fd = os.open(os.path.join(DOSSIER, ".serveur.lock"), os.O_RDWR | os.O_CREAT)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    _VERROU = fd
    return True


# 20 nov 2026 : la memoire du serveur (voir admin.limiter_arenes) : 2 zones de memoire C au lieu de 8 par processeur,
# AVANT que les fils (gunicorn, taches de fond) ne demarrent. Linux seulement.
try:
    import admin as _adm_mem  # noqa: E402
    _adm_mem.limiter_arenes()
except Exception as _e_mem:
    print("Memoire (zones) : " + repr(_e_mem), flush=True)

from flask import Flask, abort, jsonify, request, send_from_directory  # noqa: E402

import lockerroom  # noqa: E402
try:                                        # 3 nov 2026 (revue de securite) : aucune image geante decodee, partout dans l'app
    import warnings as _w
    from PIL import Image as _Img
    _Img.MAX_IMAGE_PIXELS = 40_000_000
    _w.simplefilter("error", _Img.DecompressionBombWarning)
except ImportError:
    pass

DOSSIER_UI = os.path.join(DOSSIER, "ui")
app = Flask(__name__, static_folder=None)


_APP_CACHE = {}


def _page_app():
    """app.html lue une fois (relue si le fichier change) ; compressee par _compresser. no-cache + ETag :
    le navigateur revalide en une requete et recoit 304 si rien n'a change."""
    from flask import Response
    chemin = os.path.join(DOSSIER_UI, "app.html")
    mt = os.path.getmtime(chemin)
    if _APP_CACHE.get("mt") != mt:
        with open(chemin, "rb") as f:
            brut = f.read()
        import hashlib
        _APP_CACHE.update(mt=mt, brut=brut, etag='"' + hashlib.md5(brut).hexdigest()[:16] + '"')
    if request.headers.get("If-None-Match") == _APP_CACHE["etag"]:
        return Response(status=304, headers={"ETag": _APP_CACHE["etag"]})
    ae = request.headers.get("Accept-Encoding") or ""
    if "br" in ae and _brotli_app():
        return Response(_APP_CACHE["br"], mimetype="text/html", headers={"ETag": _APP_CACHE["etag"], "Cache-Control": "no-cache",
                        "Content-Encoding": "br", "Vary": "Accept-Encoding", "Content-Length": str(len(_APP_CACHE["br"]))})
    if "gzip" in ae:
        # 28 oct 2026 (vitesse) : la page (~790 Ko) compressee UNE fois, pas a chaque telechargement (~47 ms)
        if _APP_CACHE.get("gz_mt") != _APP_CACHE["mt"]:
            import gzip
            _APP_CACHE.update(gz=gzip.compress(_APP_CACHE["brut"], 6), gz_mt=_APP_CACHE["mt"])
        return Response(_APP_CACHE["gz"], mimetype="text/html", headers={"ETag": _APP_CACHE["etag"], "Cache-Control": "no-cache",
                        "Content-Encoding": "gzip", "Vary": "Accept-Encoding", "Content-Length": str(len(_APP_CACHE["gz"]))})
    return Response(_APP_CACHE["brut"], mimetype="text/html", headers={"ETag": _APP_CACHE["etag"], "Cache-Control": "no-cache"})


def _brotli_app():
    """12 nov 2026 (nuit de revue, vitesse) : Brotli pour la page de l'app (1,7 Mo) : 488 Ko en gzip -> 402 Ko tout de suite
    (qualite 9, ~0,1 s), puis 371 Ko (qualite 11, ~3 s, calculee une fois a cote). -24 % a telecharger a chaque mise a jour.
    Sans le module brotli : gzip comme avant."""
    try:
        import brotli
    except ImportError:
        return False
    mt = _APP_CACHE["mt"]
    if _APP_CACHE.get("br_mt") != mt:
        _APP_CACHE.update(br=brotli.compress(_APP_CACHE["brut"], quality=9), br_mt=mt)
        brut = _APP_CACHE["brut"]

        def _mieux():
            try:
                b = brotli.compress(brut, quality=11)
                if _APP_CACHE.get("br_mt") == mt:
                    _APP_CACHE["br"] = b
            except Exception:
                pass
        threading.Thread(target=_mieux, daemon=True).start()
    return True


# 24 oct 2026 (Mathieu : « RAPIDITE, l'app doit repondre le plus rapidement possible ») - reponses compressees
# (app.html : ~315 Ko -> ~70 Ko) ; validation par ETag pour les fichiers (le navigateur garde sa copie).
@app.after_request
def _compresser(rep):
    import gzip
    try:
        if (rep.status_code == 200 and not rep.direct_passthrough and "gzip" in (request.headers.get("Accept-Encoding") or "")
                and "Content-Encoding" not in rep.headers
                and (rep.mimetype or "").split("/")[0] in ("text", "application") and rep.mimetype != "application/octet-stream"):
            brut = rep.get_data()
            if len(brut) > 1400:
                z = gzip.compress(brut, 6)
                rep.set_data(z)
                rep.headers["Content-Encoding"] = "gzip"
                rep.headers["Content-Length"] = str(len(z))
                rep.headers.add("Vary", "Accept-Encoding")
    except Exception:
        pass
    return rep

# 3 nov 2026 (revue de securite) : les en-tetes de securite. La CSP bloque tout script, toute connexion et tout cadre venant
# d'un autre site (une faille d'affichage ne peut ni charger un script ailleurs ni envoyer les donnees ailleurs) ; les
# images restent permises partout (photos eBay). Les scripts de nos pages sont dans la page (« unsafe-inline »).
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob: https:; media-src 'self' data: blob:; "
       "connect-src 'self' data: blob:; worker-src 'self' blob:; frame-src 'self'; object-src 'none'; base-uri 'self'; "
       "frame-ancestors 'self'; form-action 'self'; script-src-attr 'none'; manifest-src 'self'; upgrade-insecure-requests")   # 18 nov : plus d'images http, aucun onclick       # 8 nov 2026 : un formulaire injecte ne peut rien envoyer ailleurs


# 8 nov 2026 (Mathieu : « le CSP, si ca vaut la peine, go » ; 2e revue de securite) : plus de « unsafe-inline » pour les
# scripts. Seuls passent les scripts de NOS pages, reconnus par leur empreinte (sha256 de chaque <script> du fichier) : un
# script injecte par une faille d'affichage (titre d'annonce, nom...) ne s'execute plus, meme dans l'app iPhone. Les
# attributs onclick / onerror sont aussi bloques (l'app n'en a plus : data-act / data-oe). Les violations sont notees
# (/csp-rapport) pour l'admin. LR_CSP_SOUPLE=1 remet l'ancienne regle d'un geste si une page casse.
import base64 as _b64  # noqa: E402
import hashlib as _hl  # noqa: E402
import re as _re  # noqa: E402
_RE_SCRIPT = _re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", _re.S | _re.I)
_EMPREINTES = {"mt": None, "h": set()}


def _empreintes_texte(html):
    return {"'sha256-" + _b64.b64encode(_hl.sha256(m.encode("utf-8")).digest()).decode() + "'" for m in _RE_SCRIPT.findall(html or "")}


def _empreintes_ui():
    """Les scripts des pages de ui/ (app.html, break.html, connexion.html...), relues si un fichier change."""
    try:
        fs = sorted(f for f in os.listdir(DOSSIER_UI) if f.endswith(".html"))
        mt = tuple(os.path.getmtime(os.path.join(DOSSIER_UI, f)) for f in fs)
    except OSError:
        return _EMPREINTES["h"]
    if _EMPREINTES["mt"] != mt:
        h = set()
        for f in fs:
            try:
                with open(os.path.join(DOSSIER_UI, f), encoding="utf-8") as fo:
                    h |= _empreintes_texte(fo.read())
            except OSError:
                pass
        _EMPREINTES.update(mt=mt, h=h)
    return _EMPREINTES["h"]


def _csp(rep):
    if os.environ.get("LR_CSP"):
        return os.environ["LR_CSP"]
    if os.environ.get("LR_CSP_SOUPLE") == "1":
        return CSP
    h = set(_empreintes_ui())
    if (rep.mimetype or "") == "text/html" and not rep.direct_passthrough and "Content-Encoding" not in rep.headers:
        try:
            h |= _empreintes_texte(rep.get_data(as_text=True))          # pages faites par le serveur (retours de connexion)
        except Exception:
            pass
    return CSP.replace("script-src 'self' 'unsafe-inline'", "script-src 'self' " + " ".join(sorted(h))) + "; report-uri /csp-rapport"


@app.route("/langue", methods=["POST"])
def choisir_langue():
    """18 nov 2026 (Aikido « Cookie missing HttpOnly ») : le choix de langue de l'app devient un temoin HttpOnly ecrit ici."""
    l = (request.args.get("l") or "").lower()
    if l not in ("fr", "en"):
        return ("", 400)
    from flask import make_response
    r = make_response("", 204)
    r.set_cookie("lr_langue", l, max_age=365 * 86400, samesite="Lax", secure=HEBERGE, httponly=True)
    return r


@app.route("/csp-rapport", methods=["POST"])
def csp_rapport():
    """Le navigateur signale ce que la CSP a bloque : note dans les erreurs de l'admin (sans donnees du compte)."""
    if not _rythme_ok("csp"):
        return ("", 204)
    try:
        d = (request.get_json(force=True, silent=True) or {}).get("csp-report") or {}
        import admin
        admin.noter_erreur("csp", RuntimeError(f"{d.get('violated-directive') or d.get('effective-directive')} : "
                                               f"{str(d.get('blocked-uri') or '')[:80]} @ {str(d.get('document-uri') or '').split('?')[0][-60:]}"
                                               f" l.{d.get('line-number')}"))
    except Exception:
        pass
    return ("", 204)


@app.after_request
def _entetes_securite(rep):
    h = rep.headers
    h.setdefault("Content-Security-Policy", _csp(rep))
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "geolocation=(), microphone=(), payment=()")
    # 18 nov 2026 (Aikido « HSTS header is missing ») : aussi derriere le proxy de Render (X-Forwarded-Proto), 2 ans + sous-domaines
    if HEBERGE or request.is_secure or request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() == "https":
        h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    # 8 nov 2026 (2e revue de securite) : les reponses de l'API et des pages de connexion contiennent des donnees du compte :
    # jamais gardees par un cache (proxy, navigateur partage, appareil prete)
    if request.path.startswith(("/api/", "/auth/", "/connexion", "/deconnexion", "/mes-photos/")) and request.path != "/api/b/":
        if request.path.startswith("/mes-photos/"):
            h["Cache-Control"] = "private, max-age=2592000"
        else:
            h["Cache-Control"] = "no-store"
    return rep


api = lockerroom.Api()

# -- 21 oct 2026 : version hebergee (demo publique) -------------------------------------------
# LOCKERROOM_HEBERGE=1  : serveur de production (gunicorn), pas d'auto-redemarrage
# LOCKERROOM_CODE=...   : code d'acces demande avant d'ouvrir l'app (protege toutes les API)
# LOCKERROOM_SECRET=... : cle de signature du temoin de session (obligatoire si code)
HEBERGE = os.environ.get("LOCKERROOM_HEBERGE") == "1"
CODE_ACCES = os.environ.get("LOCKERROOM_CODE") or ""
app.secret_key = os.environ.get("LOCKERROOM_SECRET") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=HEBERGE)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024        # 5 nov 2026 : photos HD natives (carte jusqu'a 7,5 Mo)
#        # 23 oct 2026 - 2 photos ; 3 nov 2026 : + rasantes et 8 gros plans des coins
# pages qui restent publiques : break partage, retour et avis eBay, pages legales, icones
_PUBLIQUES = ("/b/", "/api/b/", "/api/ebay_retour", "/ebay/suppression-compte", "/confidentialite", "/conditions",
              "/support", "/securite", "/security", "/x/", "/tarifs", "/pricing", "/a-propos", "/about", "/preuve", "/proof", "/slabiq", "/langue", "/robots.txt", "/sitemap.xml", "/logo_sc_", "/syne-800.woff2", "/manrope-", "/barlow-", "/connexion", "/icone", "/favicon", "/manifest.json", "/stripe/webhook", "/apple/notifications", "/sante", "/csp-rapport", "/.well-known/security.txt", "/security.txt")


import comptes  # noqa: E402

_PUBLIQUES_MULTI = _PUBLIQUES + ("/auth/", "/deconnexion", "/demo")


def _ouvrir_session(cid, garder_ok=False):
    """3 nov 2026 (revue de securite) : une connexion = une NOUVELLE session (l'ancienne est videe : pas de fixation), avec un
    identifiant que « Se deconnecter » peut revoquer (le temoin copie ne sert plus apres la deconnexion)."""
    import secrets as _s
    from flask import session
    ok = session.get("ok") if garder_ok else None
    session.clear()
    session.permanent = True
    session["compte"] = cid
    session["sid"] = _s.token_urlsafe(16)
    if ok:
        session["ok"] = ok


# 3 nov 2026 (revue de securite) : les formulaires POST de connexion n'acceptent que notre propre site (pas de « login CSRF »
# depuis un autre site) ; les retours des fournisseurs (Apple poste depuis son site) et les avis signes sont exemptes.
_POST_EXEMPTES = ("/auth/apple/retour", "/auth/google/retour", "/stripe/webhook", "/apple/notifications", "/ebay/suppression-compte", "/api/", "/csp-rapport", "/langue")


def _meme_site():
    import urllib.parse
    o = request.headers.get("Origin")
    if o:
        return o != "null" and urllib.parse.urlparse(o).netloc.lower() == request.host.lower()
    r = request.headers.get("Referer")
    if r:
        return urllib.parse.urlparse(r).netloc.lower() == request.host.lower()
    return not comptes.MULTI                        # aucun en-tete : refuse en ligne (les navigateurs envoient Origin en POST)


# 3 nov 2026 (Render : « HTTP health check failed, timed out after 5 seconds ») : une verification de sante qui ne fait RIEN
# (ni compte, ni base, ni fichier) : elle repond meme quand le serveur est occupe. Render : Health Check Path = /sante
@app.route("/sante")
def sante_render():
    return "ok", 200, {"Content-Type": "text/plain", "Cache-Control": "no-store"}


# 21 nov 2026 (Mathieu : « un pare-feu pour empecher un hacker de ne pas payer ou d'aller chercher mon data ; impenetrable et
# fiable ») : le pare-feu, c'est Cloudflare (regles WAF, limite de debit, DDoS). Mais l'adresse directe de Render
# (xxx.onrender.com) le contournait. Maintenant : Cloudflare ajoute un en-tete secret a chaque requete (Transform Rule) et le
# serveur refuse tout ce qui n'a pas cet en-tete. 3 etapes, dans l'ordre (sinon le site tombe) :
#   1. Cloudflare : Rules > Transform Rules > Modify Request Header : X-SC-Origine = <un long secret>, pour tout le trafic ;
#   2. Render : LR_ORIGINE_JETON = le meme secret ; verifier https://www.slabcoach.com/sante/cloudflare -> « oui » ;
#   3. Render : LR_ORIGINE_BLOQUER = 1 (le refus commence).
# Tant que l'en-tete est verifie, la vraie adresse du visiteur vient de Cloudflare (CF-Connecting-IP) : les limites d'essais
# visent la bonne personne, pas un serveur de Cloudflare partage par des milliers de gens.
_ORIGINE_SECRET = os.environ.get("LR_ORIGINE_JETON") or ""
_ORIGINE_BLOQUER = os.environ.get("LR_ORIGINE_BLOQUER") == "1" and len(_ORIGINE_SECRET) >= 24


def _via_cloudflare():
    import hmac
    v = request.headers.get("X-SC-Origine") or ""
    return bool(_ORIGINE_SECRET) and bool(v) and hmac.compare_digest(v.encode(), _ORIGINE_SECRET.encode())


@app.route("/sante/cloudflare")
def sante_cloudflare():
    return ("oui" if _via_cloudflare() else "non"), 200, {"Content-Type": "text/plain", "Cache-Control": "no-store"}


# 20 nov 2026 (revue de performance : « que tout performe au maximum ») : le serveur ne mesurait pas le temps de ses requetes.
# Chaque requete de plus de LR_LENT_S secondes (2 par defaut) est notee dans le journal (« Lent : ... ») avec sa duree : on
# sait enfin quels ecrans sont lents en vrai, avec les vraies donnees. Rien d'autre n'est garde (ni compte, ni parametre).
try:
    _LENT_S = float(os.environ.get("LR_LENT_S") or 2.0)
except ValueError:
    _LENT_S = 2.0


# 21 nov 2026 (Mathieu : « repasse tous les codes pour maximiser la reponse et la rapidite du serveur ») : le journal de Render
# montre que le serveur est rapide en regime normal, et tres lent 3 a 5 minutes apres CHAQUE mise a jour (caches vides + les
# memes calculs lances 2-3 fois en meme temps). Pour savoir OU le temps passe en vrai (avec les vraies donnees) :
#  - chaque ligne « Lent » dit combien de requetes roulaient en meme temps ;
#  - un gardien note, au plus une fois par 20 s, la pile d'appels (fichier:ligne, jamais une donnee) d'une requete qui dure
#    depuis plus de LR_PILE_S secondes (8 par defaut) : « Pile lente : ... ».
_EN_VOL = {}                      # id du fil -> (debut, chemin)
_TACHES_ICI = HEBERGE and os.environ.get("LOCKERROOM_TACHES", "1") == "1"
_EN_VOL_VERROU = threading.Lock()
try:
    _PILE_S = float(os.environ.get("LR_PILE_S") or 8.0)
except ValueError:
    _PILE_S = 8.0


def en_vol():
    return len(_EN_VOL)


# 21 nov 2026 (2e suivi) : en production, AUCUNE « Pile lente » en 4 heures, meme pour une requete de 98 s : le gardien ne
# disait rien, et on ne savait pas s'il roulait. Maintenant : il s'annonce au demarrage (« Gardien des piles : actif »), il
# est (re)lance par la premiere requete s'il ne roule pas dans CE processus, il ne se tait plus sur une erreur, une requete
# sans pile lisible ne cache plus les autres, et il echantillonne aussi les requetes de 1,5 a 8 s (« Pile : ... », au plus
# 4 par chemin par 10 min) : c'est la que vivent les lenteurs de tous les jours (Deals 3,3 s aux 45 s).
try:
    _PILE_COURT_S = float(os.environ.get("LR_PILE_COURT_S") or 1.5)
except ValueError:
    _PILE_COURT_S = 1.5
_GARDIEN = {"pid": None, "fil": None}


def _pile_lisible(fr):
    import traceback
    pile = [f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in traceback.extract_stack(fr)
            if "site-packages" not in f.filename and "/lib/python" not in f.filename][-7:]
    return " < ".join(reversed(pile)) or "(hors du code de l'app)"


def _gardien_piles():
    print(f"Gardien des piles : actif (pid {os.getpid()}, longue {_PILE_S:.0f} s, echantillon {_PILE_COURT_S:g} s)", flush=True)
    dernier, courts, err_le = 0.0, {}, 0.0
    while True:
        time.sleep(1)
        try:
            m = time.perf_counter()
            with _EN_VOL_VERROU:
                vols = sorted(((m - t0, ch, tid) for tid, (t0, ch) in list(_EN_VOL.items())), reverse=True)
            if not vols or vols[0][0] < min(_PILE_S, _PILE_COURT_S or _PILE_S):
                continue
            cadres = sys._current_frames()
            if m - dernier >= 20:
                for d, ch, tid in vols:
                    if d < _PILE_S:
                        break
                    fr = cadres.get(tid)
                    if fr is None:
                        continue
                    print(f"Pile lente : {ch} {d:.0f} s · {len(vols)} en cours · " + _pile_lisible(fr), flush=True)
                    dernier = m
                    break
            if _PILE_COURT_S > 0:
                for d, ch, tid in vols:
                    if not (_PILE_COURT_S <= d < _PILE_S):
                        continue
                    vus = [t for t in courts.get(ch, ()) if m - t < 600]
                    fr = cadres.get(tid) if len(vus) < 4 else None
                    if fr is not None:
                        print(f"Pile : {ch} {d:.1f} s · " + _pile_lisible(fr), flush=True)
                        vus.append(m)
                    courts[ch] = vus
                if len(courts) > 400:
                    courts.clear()
        except Exception as e:
            if time.time() - err_le > 300:
                err_le = time.time()
                print("Gardien des piles : " + repr(e)[:200], flush=True)


def _gardien_assurer():
    """Le gardien roule dans CE processus (sinon on le lance) : appele au chargement et par chaque requete de l'API."""
    if _PILE_S <= 0:
        return
    f = _GARDIEN.get("fil")
    if _GARDIEN.get("pid") == os.getpid() and f is not None and f.is_alive():
        return
    with _EN_VOL_VERROU:
        f = _GARDIEN.get("fil")
        if _GARDIEN.get("pid") == os.getpid() and f is not None and f.is_alive():
            return
        f = threading.Thread(target=_gardien_piles, daemon=True, name="gardien-piles")
        _GARDIEN["pid"], _GARDIEN["fil"] = os.getpid(), f
        f.start()


@app.before_request
def _chrono_debut():
    from flask import g
    g._t0 = time.perf_counter()
    if request.path.startswith("/api/"):
        with _EN_VOL_VERROU:
            _EN_VOL[threading.get_ident()] = (g._t0, request.path)
        if HEBERGE:
            _gardien_assurer()
    if _TACHES_ICI and _CHAUD["pid"] != os.getpid():
        _worker_assurer()


@app.teardown_request
def _chrono_sortie(_e=None):
    with _EN_VOL_VERROU:
        _EN_VOL.pop(threading.get_ident(), None)


@app.after_request
def _chrono_fin(rep):
    from flask import g
    t0 = getattr(g, "_t0", None)
    if t0 is not None and _LENT_S > 0:
        d = time.perf_counter() - t0
        if d >= _LENT_S and request.path != "/sante":
            print(f"Lent : {request.method} {request.path} {d:.1f} s ({rep.status_code}) · {len(_EN_VOL)} en cours", flush=True)
    return rep


@app.before_request
def _garde():
    from flask import redirect, session
    if request.path in ("/sante", "/sante/cloudflare"):
        return None
    if _ORIGINE_BLOQUER and not _via_cloudflare():        # 21 nov 2026 : seulement par Cloudflare (le pare-feu)
        return ("Accès refusé", 403, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"})
    if request.method == "POST" and not request.path.startswith(_POST_EXEMPTES) and not _meme_site():
        return ("Requête refusée (autre site)", 403)
    comptes.activer(None)
    import lockerroom as _lr                       # 26 oct 2026 - requete venue de l'app iPhone ?
    _lr.marquer_ios("LockerRoomiOS" in (request.headers.get("User-Agent") or ""))
    publique = request.path.startswith(_PUBLIQUES_MULTI)
    if CODE_ACCES and not session.get("ok") and not publique:       # demo : code d'acces d'abord
        return (jsonify({"erreur": "Connexion requise"}), 401) if request.path.startswith("/api/") else redirect("/connexion")
    if comptes.MULTI:
        cid = session.get("compte")
        if cid and session.get("sid") and comptes.session_revoquee(cid, session.get("sid")):
            session.clear()                                          # 3 nov 2026 : session fermee par « Se deconnecter »
            cid = None
        if cid and cid in comptes.lister():
            cid2 = comptes.resoudre(cid)                             # 2 nov 2026 : ancien compte relie -> le compte choisi
            if cid2 != cid:
                session["compte"] = cid = cid2
            comptes.activer(cid)                                     # cette requete ne voit que ce compte
            if request.path.startswith("/api/"):
                try:
                    comptes.vu(cid)                                  # 13 nov 2026 : « vu » = la derniere activite
                except Exception:
                    pass
        elif request.path == "/" and not CODE_ACCES:
            if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
                return redirect("/connexion")                        # app iPhone : pas la vitrine (prix du site)
            return _page_vitrine()                                   # 27 oct 2026 : visiteur -> la vitrine
        elif not publique:
            session.pop("compte", None)
            return (jsonify({"erreur": "Connexion requise"}), 401) if request.path.startswith("/api/") else redirect("/connexion")
    return None


# 28 oct 2026 (Mathieu : « je me connecte a eBay avec Google et ca ne marche plus ») : RELIER eBay depuis Profil, dans
# l'app iPhone. Dans la vue web, « Continuer avec Google » d'eBay partait dans Safari et ne revenait jamais. Maintenant :
# l'app demande un jeton a usage unique (lie a SON compte, 10 min), ouvre le navigateur securise d'iOS sur
# /auth/ebay-lier, et le retour d'eBay ramene un billet a l'app (slabcoachauth://retour), comme la connexion.
_LIER_ETATS = {}      # etat OAuth -> (compte, le, app) ; les jetons a usage unique : lockerroom.LIER


def _lier_permis(cid):
    """3 nov 2026 (revue de securite : un lien « relier » envoye a quelqu'un d'autre lui faisait relier SON eBay / Google au
    compte de l'envoyeur) : on relie seulement (a) depuis l'app iPhone : l'empreinte de son secret part avec, et rien n'est
    relie avant que l'app rende le billet avec ce secret ; ou (b) dans un navigateur deja connecte a CE compte. -> app|"" ou None"""
    import re
    from flask import session
    h = (request.args.get("app") or "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", h):
        return h
    if not comptes.MULTI or session.get("compte") == cid:
        return ""
    return None


@app.route("/auth/ebay-lier")
def auth_ebay_lier():
    from flask import redirect
    import time as _t
    import lockerroom as _lrm
    v = _lrm.LIER.pop(request.args.get("t") or "", None)
    if not v or _t.time() - v[1] > 600 or v[0] not in comptes.lister():
        return redirect("/connexion?erreur=3&r=expire")
    app_h = _lier_permis(v[0])
    if app_h is None:
        return redirect("/connexion?erreur=3&r=lien")
    comptes.activer(v[0])
    r = api.ebay_url_connexion()
    if not r.get("ok"):
        return redirect("/connexion?erreur=1")
    import urllib.parse
    etat = (urllib.parse.parse_qs(urllib.parse.urlparse(r["url"]).query).get("state") or [""])[0]
    for k in [k for k, x in _LIER_ETATS.items() if _t.time() - x[1] > 900]:
        _LIER_ETATS.pop(k, None)
    _LIER_ETATS[etat] = (v[0], _t.time(), app_h)
    _noter_app(r["url"])
    return _lier_navigateur(redirect(r["url"]), r["url"])


@app.route("/auth/ebay")
def auth_ebay():
    """Multi-comptes : UN bouton = inscription + connexion (page officielle d'eBay)."""
    from flask import redirect
    # 10 nov 2026 (Mathieu : dans l'app, « Se connecter avec eBay » s'ouvrait DANS la feuille Safari et fermer la feuille
    # ramenait a la connexion) : Safari avait deja une session SlabCoach (un autre compte) ; eBay etait alors RELIE a ce
    # compte-la, sans billet pour l'app. Ce bouton est toujours une connexion, peu importe la session du navigateur.
    if comptes.MULTI:
        comptes.activer(None)
    r = api.ebay_url_connexion()
    if not r.get("ok"):
        return redirect("/connexion?erreur=1")
    _noter_app(r["url"])
    return _lier_navigateur(redirect(r["url"]), r["url"])


# 27 oct 2026 (Mathieu : « ne pas obliger d'avoir un compte eBay, mais fortement recommande ») : Apple et Google.
def _base_publique():
    """28 oct 2026 : l'adresse ou l'utilisateur EST (slabcoach.com ou www.slabcoach.com), pas une adresse fixe.
    Avant : Apple revenait sur www, que Render redirige vers slabcoach.com, et la redirection perdait le formulaire
    d'Apple (POST) -> « Connexion interrompue ». Les deux adresses sont enregistrees chez Apple et Google."""
    h = (request.host or "").split(",")[0].strip().lower()
    import re
    if HEBERGE and re.fullmatch(r"(www\.)?slabcoach\.com", h):
        return "https://" + h
    return (os.environ.get("LOCKERROOM_URL") or request.host_url).rstrip("/")


# 27 oct 2026 (revue de securite) : une connexion (eBay, Apple, Google) revient seulement dans le NAVIGATEUR qui l'a
# commencee. Sinon quelqu'un pourrait envoyer son propre lien de retour et nous faire entrer dans SON compte.
# Temoin a part, SameSite=None : Apple revient en POST depuis son site.
_TEMOIN_LIEN = "sc_lien"


def _empreinte_etat(etat):
    import hashlib
    return hashlib.sha256(str(etat or "").encode()).hexdigest()[:32]


def _lier_navigateur(reponse, url):
    import urllib.parse
    etat = (urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("state") or [""])[0]
    if etat:
        reponse.set_cookie(_TEMOIN_LIEN, _empreinte_etat(etat), max_age=900, httponly=True, secure=HEBERGE,
                           samesite="None" if HEBERGE else "Lax", path="/")
    return reponse


# 28 oct 2026 (Mathieu : « ca doit marcher avec Google, eBay, Apple ») : dans l'app iPhone, la connexion s'ouvre dans le
# navigateur securise d'iOS (Google refuse les vues web integrees, et « Continuer avec Google » d'eBay aussi). Au retour,
# pas de session dans ce navigateur : un billet a usage unique revient a l'app par slabcoachauth://retour, et l'app
# l'echange contre sa session. Le billet ne sert qu'avec le secret que l'app a garde (son empreinte part au depart).
_APP_ETATS = {}
SCHEMA_APP = "slabcoachauth://retour"


def _noter_app(url):
    import re
    import time
    import urllib.parse
    h = (request.args.get("app") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", h):
        return
    etat = (urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("state") or [""])[0]
    if etat:
        for k in [k for k, v in _APP_ETATS.items() if time.time() - v[1] > 900]:
            _APP_ETATS.pop(k, None)
        _APP_ETATS[etat] = (h, time.time())


def _billet(cid, cible, etat, attente=None):
    """Ouvre la session ici (navigateur normal) ou, pour l'app iPhone, prepare le billet. -> reponse Flask.
    attente (3 nov 2026) : ce qui doit se faire seulement quand l'app rend le billet avec son secret (relier eBay / Google)."""
    from flask import redirect, session
    import secrets as _s
    import time as _t
    app_h = (_APP_ETATS.pop(etat, None) or (None,))[0] if etat else None
    for k in [k for k, v in _BILLETS.items() if _t.time() - v[2] > 120]:
        _BILLETS.pop(k, None)
    b = _s.token_urlsafe(32)
    if app_h:
        _BILLETS[b] = (cid, cible, _t.time(), "", app_h, attente)
        dest = SCHEMA_APP + "?b=" + b
        return (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<body style='margin:0;background:#0B0B0E;color:#F4F2EE;font-family:-apple-system,sans-serif;display:grid;place-items:center;height:100vh'>"
                f"<a href='{dest}' style='padding:16px 26px;border-radius:14px;background:#B9BEFF;color:#0E1026;font-weight:700;text-decoration:none'>"
                f"Revenir à SlabCoach</a><script>location.replace({json.dumps(dest)})</script>", 200, {"Content-Type": "text/html; charset=utf-8"})
    if attente and request.method == "GET":   # un lien sans l'app : seulement dans le navigateur deja connecte a ce compte
        if comptes.MULTI and session.get("compte") != cid:
            return redirect("/connexion?erreur=3&r=lien")
        if not _faire_attente(cid, attente):
            cible = "/#reglages/ebay-erreur" if attente[0] == "ebay" else "/#reglages"
    if request.method == "GET":
        _ouvrir_session(cid, garder_ok=True)
        return redirect(cible)
    _BILLETS[b] = (cid, cible, _t.time(), request.cookies.get(_TEMOIN_LIEN) or "", None, attente)
    suite = "/auth/terminer?b=" + b
    return (f"<!doctype html><meta charset='utf-8'><meta name='referrer' content='no-referrer'>"
            f"<meta http-equiv='refresh' content='0;url={suite}'>"
            f"<script>location.replace({json.dumps(suite)})</script>", 200, {"Content-Type": "text/html; charset=utf-8"})


def _navigateur_lie(etat):
    import hmac
    if not comptes.MULTI:                    # sur le PC du vendeur : un seul utilisateur
        return True
    t = request.cookies.get(_TEMOIN_LIEN) or ""
    return bool(etat) and bool(t) and hmac.compare_digest(t, _empreinte_etat(etat))


@app.route("/auth/<fournisseur>")
def auth_tiers(fournisseur):
    from flask import redirect
    import auth_tiers as at
    if fournisseur not in at.FOURNISSEURS or not comptes.MULTI:
        abort(404)
    try:
        u = at.url_connexion(fournisseur, _base_publique())
    except RuntimeError:
        return redirect("/connexion?erreur=2")
    _noter_app(u)
    # 2 nov 2026 : « Ajouter Google / Apple » depuis Profil : un jeton a usage unique (lie au compte, 10 min) -> au retour,
    # cette identite est reliee a CE compte au lieu d'en ouvrir un autre
    j = request.args.get("lier") or ""
    if j:
        import time as _t
        import urllib.parse
        import lockerroom as _lrm
        v = _lrm.LIER.pop(j, None)
        if v and _lier_permis(v[0]) is None:
            return redirect("/connexion?erreur=3&r=lien")
        if v and _t.time() - v[1] <= 600 and v[0] in comptes.lister():
            etat = (urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("state") or [""])[0]
            for k in [k for k, x in _LIER_TIERS.items() if _t.time() - x[1] > 900]:
                _LIER_TIERS.pop(k, None)
            if etat:
                _LIER_TIERS[etat] = (v[0], _t.time(), _lier_permis(v[0]))
    return _lier_navigateur(redirect(u), u)


_LIER_TIERS = {}      # etat OAuth -> (compte qui relie Apple / Google, le)


@app.route("/auth/<fournisseur>/retour", methods=["GET", "POST"])
def auth_tiers_retour(fournisseur):
    """Google revient en GET, Apple en POST (form_post). Compte cree au premier passage."""
    from flask import redirect
    import auth_tiers as at
    if fournisseur not in at.FOURNISSEURS or not comptes.MULTI:
        abort(404)
    v = request.values
    if not _navigateur_lie(v.get("state")):
        app.logger.warning("Connexion %s : retour dans un autre navigateur (etat %s, temoin %s)", fournisseur,
                           bool(v.get("state")), bool(request.cookies.get(_TEMOIN_LIEN)))
        print(f"Connexion {fournisseur} : temoin absent ou different (etat={bool(v.get('state'))})", flush=True)
        return redirect("/connexion?erreur=3&r=lien")
    r = at.terminer(fournisseur, v.get("code"), v.get("state"), _base_publique(), v.get("user"))
    if not r.get("ok"):
        app.logger.warning("Connexion %s refusee : %s", fournisseur, r.get("erreur"))
        print(f"Connexion {fournisseur} refusee : {r.get('erreur')}", flush=True)
        return redirect("/connexion?erreur=3&r=" + ("expire" if "expir" in str(r.get("erreur")) else "jeton"))
    cle = fournisseur + ":" + r["sub"]
    lien = _LIER_TIERS.pop(v.get("state") or "", None)
    if lien and lien[0] in comptes.lister():                 # « Ajouter Google / Apple » depuis Profil
        champs = {}
        if r.get("courriel"):
            champs["courriel"] = r["courriel"]
        if r.get("jeton_apple"):
            champs["apple_rt"] = comptes.chiffrer(r["jeton_apple"])
        # 3 nov 2026 (revue) : relie seulement quand l'app rend le billet (ou dans le navigateur connecte a ce compte)
        return _billet(lien[0], "/#reglages/connexion-ok", v.get("state"), attente=("tiers", cle, fournisseur, champs))
    cid, nouveau = comptes.trouver_connexion(cle, r.get("nom"), fournisseur, r.get("courriel"))
    champs = {"connexion": fournisseur} if nouveau or not comptes.info(cid).get("connexion") else {}
    if r.get("courriel") and (nouveau or not comptes.info(cid).get("courriel")):
        champs["courriel"] = r["courriel"]
    if r.get("jeton_apple"):                 # pour le retirer chez Apple si le compte est supprime (chiffre)
        champs["apple_rt"] = comptes.chiffrer(r["jeton_apple"])
    if champs:
        comptes.maj(cid, **champs)
    # 28 oct 2026 : Apple revient en POST depuis SON site. Safari (et l'app iPhone) n'enregistre pas un temoin
    # SameSite=Lax dans la reponse a un POST venu d'un autre site : la session etait perdue -> boucle vers la connexion.
    # Billet a usage unique (2 min) : une petite page repart chez nous en GET, ou la session s'ouvre (voir _billet).
    return _billet(cid, "/#accueil/" + ("bienvenue" if nouveau else "retour"), v.get("state"))


_BILLETS = {}


def _unifier_ebay(cid):
    """10 nov 2026 (Mathieu : son eBay s'est retrouve relie a 2 comptes) : un compte eBay = UN compte SlabCoach. Les autres
    comptes qui ont ce meme eBay (prouve par eBay a chaque fois) sont fusionnes dans celui-ci : cartes, photos et watchlist
    copiees sans doublon, leurs connexions (Apple, Google) ouvrent ensuite celui-ci. Rien n'est efface."""
    try:
        uid = comptes.info(cid).get("ebay_user_id")
        if not uid:
            return
        for autre in comptes.par_champ("ebay_user_id", uid):
            if autre == cid or comptes.info(autre).get("renvoi"):
                continue
            with comptes.utiliser(cid):
                print("Fusion (meme eBay) :", api._fusionner_depuis(autre), flush=True)
            comptes.renvoyer(autre, cid)
    except Exception as e:
        print("Fusion (meme eBay) : " + repr(e), flush=True)


def _faire_attente(cid, attente):
    """Relier ce qui attendait le billet : ("ebay", url de retour, etat) ou ("tiers", cle, fournisseur, champs). -> bool"""
    try:
        comptes.activer(cid)
        if attente[0] == "ebay":
            r = api.ebay_terminer(attente[1], attente[2])
            if r.get("ok"):
                _unifier_ebay(cid)
                _premiere_synchro(cid)
            return bool(r.get("ok"))
        if attente[0] == "tiers":
            # 9 nov 2026 : cette connexion ouvrait un AUTRE compte -> ses cartes et sa watchlist viennent ici (fusion)
            ancien = comptes.par_identite(attente[1]) or comptes.id_pour(attente[1], attente[2])
            comptes.lier_identite(cid, attente[1], attente[2])
            if ancien and ancien != cid and ancien in comptes.lister():
                try:
                    with comptes.utiliser(cid):
                        print("Fusion :", api._fusionner_depuis(ancien), flush=True)
                except Exception as e_:
                    print("Fusion de comptes : " + repr(e_), flush=True)
            champs = dict(attente[3] or {})
            if champs.get("courriel") and comptes.info(cid).get("courriel"):
                champs.pop("courriel")
            if champs:
                comptes.maj(cid, **champs)
            return True
    except Exception as e:
        print("Relier (billet) : " + repr(e), flush=True)
    return False


@app.route("/auth/terminer")
def auth_terminer():
    """2e moitie du retour d'Apple : meme site, en GET -> le temoin de session s'enregistre (Safari compris)."""
    from flask import redirect, session
    import hmac
    import time as _t
    b = request.args.get("b") or ""
    v = _BILLETS.pop(b, None)
    if not v or _t.time() - v[2] > 120:
        return redirect("/connexion?erreur=3")
    cid, cible, _le, lien, app_h, attente = (tuple(v) + (None,))[:6]
    if app_h:                                  # app iPhone : le secret garde par l'app doit correspondre
        import hashlib
        if not hmac.compare_digest(app_h, hashlib.sha256((request.args.get("v") or "").encode()).hexdigest()):
            return redirect("/connexion?erreur=3")
    elif lien and not hmac.compare_digest(lien, request.cookies.get(_TEMOIN_LIEN) or ""):   # meme navigateur seulement
        return redirect("/connexion?erreur=3")
    if cid not in comptes.lister():
        return redirect("/connexion?erreur=3")
    if attente and not app_h and comptes.MULTI and session.get("compte") != cid:
        return redirect("/connexion?erreur=3&r=lien")           # navigateur : il doit deja etre connecte a ce compte
    if attente:                                # 3 nov 2026 : relier eBay / Google seulement maintenant (billet + secret)
        ok = _faire_attente(cid, attente)
        if not ok:
            cible = "/#reglages/ebay-erreur" if attente[0] == "ebay" else "/#reglages"
    _ouvrir_session(cid, garder_ok=True)
    r = redirect(cible)
    r.delete_cookie(_TEMOIN_LIEN, path="/")
    return r


# 27 oct 2026 (revue de securite) : codes d'acces et de demo : 8 essais rates par 15 min par adresse, puis on attend.
_ECHECS = {}


def _ip():
    # 3 nov 2026 (revue de securite) : la DERNIERE adresse de X-Forwarded-For (celle que Render ajoute) ; la premiere est
    # ecrite par le client (une nouvelle a chaque essai contournait la limite d'essais)
    # 21 nov 2026 : derriere Cloudflare (en-tete secret verifie), la vraie adresse du visiteur est CF-Connecting-IP
    if HEBERGE and _via_cloudflare() and request.headers.get("CF-Connecting-IP"):
        return request.headers["CF-Connecting-IP"].strip()
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[-1].strip() if HEBERGE \
        else (request.remote_addr or "")


def _reseau(ip):
    import ipaddress
    try:
        a = ipaddress.ip_address(ip)
        return str(ipaddress.ip_network(f"{ip}/{24 if a.version == 4 else 64}", strict=False))
    except ValueError:
        return ip


def _trop_d_essais():
    import time
    m = time.time()
    for k in [k for k, v in _ECHECS.items() if m - v[-1] > 900]:
        _ECHECS.pop(k, None)
    # 3 nov 2026 (revue de securite) : pas de limite pour tout le serveur (n'importe qui pouvait bloquer tout le monde) ; a la
    # place : 8 essais par adresse, 40 par reseau (/24 en IPv4, /64 en IPv6), et des codes d'appareil a 8 chiffres
    ip = _ip()
    if len([t for t in _ECHECS.get(ip, []) if m - t < 900]) >= 8:
        return True
    res = _reseau(ip)
    return len([t for k, v in _ECHECS.items() if _reseau(k) == res for t in v if m - t < 900]) >= 40


def _noter_echec():
    import time
    _ECHECS.setdefault(_ip(), []).append(time.time())
    _ECHECS[_ip()] = _ECHECS[_ip()][-20:]


# 26 oct 2026 - compte de demonstration pour l'equipe d'Apple (et les essais) : code dans LOCKERROOM_DEMO_CODE.
# Un compte a part, quelques cartes d'exemple ; sans code configure, la route n'existe pas.
# 28 oct 2026 (audit Apple 2.1(b)) : compte GRATUIT (essai termine), pour que l'equipe d'Apple voie l'achat integre.
_DEMO_EBAY_ID = "demo-app-review"


@app.route("/demo", methods=["GET", "POST"])
def demo():
    import hmac
    from flask import redirect, session
    code = os.environ.get("LOCKERROOM_DEMO_CODE") or ""
    if not code or not comptes.MULTI:
        abort(404)
    erreur = ""
    if request.method == "POST" and _trop_d_essais():
        erreur = "<p style='color:#FFB3B3'>Trop d’essais : réessaie dans 15 minutes / Too many tries: wait 15 minutes</p>"
    elif request.method == "POST":
        if hmac.compare_digest(str(request.form.get("code") or "").strip(), code):
            cid, nouveau = comptes.trouver_ou_creer(_DEMO_EBAY_ID, "Demo", "demo")
            comptes.maj(cid, pro_offert=None, essai_bonus_jours=-30, demo=True)
            _ouvrir_session(cid)
            session["ok"] = True
            if nouveau:
                with comptes.utiliser(cid):
                    _remplir_demo()
            return redirect("/")
        _noter_echec()
        erreur = "<p style='color:#FFB3B3'>Code incorrect / Wrong code</p>"
    return _page_langue("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>SlabCoach</title><link rel='icon' href='/favicon.ico?v=2'>"
            "<body style='background:#0B0B0E;color:#F4F2EE;font-family:system-ui;display:grid;place-items:center;min-height:90vh'>"
            "<form method='post' style='display:grid;gap:12px;width:min(320px,90vw)'><img src='/logo_sc_gold_poli.png' width='72' style='margin:auto' alt=''>"
            "<b style='font-size:22px'>SlabCoach · démo / demo</b><input name='code' autocomplete='off' autofocus placeholder='Code d’accès / Access code' "
            "style='padding:12px;border-radius:10px;border:1px solid #2B2A32;background:#151519;color:#F4F2EE;font-size:16px'>"
            f"{erreur}<button style='padding:12px;border-radius:10px;border:0;background:#E9CF8E;font-weight:700;font-size:16px'>Entrer / Enter</button>"
            "<a href='/connexion' style='color:#A9A6B1;font-size:13px'>‹ Retour / Back</a></form></body>")


def _remplir_demo():
    """Quelques vraies cartes d'exemple (inventaire) pour que l'equipe d'Apple voie l'app remplie."""
    exemples = [("Connor Bedard", "2023-24", "Upper Deck", "Series 2", "Young Guns", "451", 1, 120.0, 165.0),
                ("Macklin Celebrini", "2024-25", "Upper Deck", "Series 1", "Young Guns", "201", 1, 95.0, 140.0),
                ("Ivan Demidov", "2025-26", "Upper Deck", "Series 1", "Young Guns", "205", 1, 60.0, 89.0),
                ("Matthew Schaefer", "2025-26", "Upper Deck", "Series 2", "Young Guns", "451", 1, 110.0, 160.0),
                ("Lane Hutson", "2024-25", "Upper Deck", "Series 1", "Young Guns Canvas", "C-91", 1, 30.0, 48.0),
                ("Sidney Crosby", "2025-26", "Upper Deck", "SP Authentic", "Base", "1", 0, 2.0, 4.0)]
    for j, an, m, s_, par, num, rc, cout, prix in exemples:
        try:
            api.carte_sauver({"joueur": j, "annee": an, "marque": m, "set_nom": s_, "parallele": par, "numero": num,
                              "recrue": rc, "cout": cout, "prix_demande": prix, "sport": "hockey"})
        except Exception as e:
            print("Demo : " + repr(e), flush=True)


@app.route("/deconnexion")
def deconnexion():
    from flask import redirect, session
    if session.get("compte") and session.get("sid"):
        comptes.revoquer_session(session["compte"], session["sid"])
    session.clear()
    return redirect("/auth/code" if request.args.get("suite") == "code" else "/connexion")


def _premiere_synchro(cid):
    """Nouveau client : ses annonces, ventes et la sante arrivent sans qu'il touche a rien."""
    def tache():
        with comptes.utiliser(cid):
            try:
                api.ebay_synchroniser(90)
                api.sante_rafraichir(40)
            except Exception as e:
                print("Premiere synchro : " + str(e), flush=True)
    threading.Thread(target=tache, daemon=True, name="premiere_synchro").start()


_PAGE_EBAY = ("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>SlabCoach</title>"
              "<body style='background:#0B0B0E;color:#F4F2EE;font-family:system-ui;display:grid;place-items:center;min-height:90vh;margin:0'>"
              "<main style='display:grid;gap:16px;width:min(340px,88vw);text-align:center'><img src='/logo_sc_gold_poli.png' width='80' style='margin:auto' alt=''>"
              "<b style='font-size:26px'>SlabCoach</b><span style='color:#A9A6B1'>Ton inventaire eBay, tes prix et tes ventes, tout seuls.</span>"
              "{erreur}<a href='/auth/ebay' style='padding:15px;border-radius:12px;background:#B9BEFF;color:#0B0B0E;font-weight:700;font-size:17px;text-decoration:none'>"
              "Se connecter avec eBay</a><span style='color:#8C8996;font-size:13px'>Aucun mot de passe dans l’app · ton compte est créé tout seul</span>"
              "<span style='font-size:13px'><a href='/confidentialite' style='color:#A9A6B1'>Confidentialité</a> · "
              "<a href='/conditions' style='color:#A9A6B1'>Conditions</a></span></main></body>")



def _page_connexion():
    """27 oct 2026 - la page « Se connecter avec eBay » (ui/connexion.html : noir et or, le logo avec son reflet)."""
    try:
        with open(os.path.join(DOSSIER_UI, "connexion.html"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return _PAGE_EBAY

_BOUTONS_TIERS = {
    "apple": ("<a class='btn-t apple' href='/auth/apple'><svg viewBox='0 0 17 20' aria-hidden='true'><path fill='currentColor' d='M14.1 10.6c0-2.4 2-3.6 2.1-3.7-1.1-1.7-2.9-1.9-3.5-1.9-1.5-.2-2.9.9-3.7.9-.8 0-1.9-.9-3.2-.8-1.6 0-3.1 1-4 2.4-1.7 3-.4 7.3 1.2 9.7.8 1.2 1.8 2.5 3 2.4 1.2 0 1.7-.8 3.1-.8s1.9.8 3.2.8c1.3 0 2.1-1.2 2.9-2.4.9-1.3 1.3-2.6 1.3-2.7 0 0-2.4-.9-2.4-3.9zM11.8 3.4c.7-.8 1.1-1.9 1-3-.9 0-2.1.6-2.8 1.4-.6.7-1.2 1.8-1 2.9 1.1.1 2.1-.5 2.8-1.3z'/></svg>"
              "Continuer avec Apple</a>"),
    "google": ("<a class='btn-t google' href='/auth/google'><svg viewBox='0 0 18 18' aria-hidden='true'><path fill='#4285F4' d='M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z'/>"
               "<path fill='#34A853' d='M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z'/>"
               "<path fill='#FBBC05' d='M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8z'/><path fill='#EA4335' d='M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.1 6.6 3.6 9 3.6z'/></svg>"
               "Continuer avec Google</a>"),
}


# 24 oct 2026 - pages de connexion en francais ou en anglais : ?lang=, sinon le choix de l'app (temoin lr_langue),
# sinon la langue du navigateur ; un lien en haut a gauche pour changer.
_EN = [("Ton inventaire eBay, tes prix et tes ventes, tout seuls.", "Your eBay inventory, prices and sales, on autopilot."),
       ("Se connecter avec eBay", "Sign in with eBay"), ("Aucun mot de passe dans l’app · ton compte est créé tout seul",
       "No password in the app · your account is created automatically"), ("Confidentialité", "Privacy"),
       (">Conditions<", ">Terms<"), ("Connexion eBay interrompue : réessaie", "eBay sign-in interrupted: try again"),
       ("Code incorrect", "Wrong code"), ("Code d’accès", "Access code"), (">Entrer<", ">Enter<"),
       ('<html lang="fr">', '<html lang="en">'), ("Collectionne plus. <em>Cherche moins.</em>", "Collect more. <em>Search less.</em>"),
       ("SlabCoach · Collectionne plus. Cherche moins.", "SlabCoach · Collect more. Search less."),
       ("Deals sous la valeur", "Deals under value"), ("Vraies valeurs", "Real values"), ("Chances de breaks", "Break odds"),
       ("Inventaire et ventes eBay", "eBay inventory and sales"),
       ("Code de démonstration", "Demo code"), ("Continuer avec Apple", "Continue with Apple"), ("Continuer avec Google", "Continue with Google"),
       ("Recommandé", "Recommended"), ("Déjà un compte ? Connecte-toi de la même façon, ou ",
       "Already have an account? Sign in the same way, or "), ("entre un code d’appareil", "enter a device code"), (">Démo<", ">Demo<"), ("Ton inventaire et tes ventes arrivent tout seuls", "Your inventory and sales come in on their own"),
       ('<div class="ou">ou</div>', '<div class="ou">or</div>'), ("Pas de compte eBay ? Aucun problème.", "No eBay account? No problem."),
       ("Cette connexion n’est pas encore offerte : utilise eBay", "This sign-in isn’t available yet: use eBay"),
       ("Connexion interrompue : réessaie", "Sign-in interrupted: try again"), ("‹ Retour au site", "‹ Back to site"),
       ("14 jours de Pro offerts · aucune carte de crédit", "14 days of Pro on us · no credit card"),
       ("Trop d’essais : réessaie dans 15 minutes", "Too many attempts: try again in 15 minutes"),
       ("Paiement par Stripe ou Apple · aucun mot de passe gardé · données jamais vendues", "Payment by Stripe or Apple · no password kept · data never sold"),
       (">Sécurité</a>", ">Security</a>")]


def _langue():
    l = (request.args.get("lang") or request.cookies.get("lr_langue") or "").lower()
    if l in ("fr", "en"):
        return l
    return "en" if (request.accept_languages.best_match(["fr", "en"]) or "fr") == "en" else "fr"


# 16 nov 2026 (Mathieu : « une page principale qui montre tous nos avantages en menu defilant, une page d'abonnement, une page
# de qui nous sommes et notre but ») : le site en 3 pages, une base commune (barre, menu, pied) et le contenu de chaque page
SITE_PAGES = {
    "accueil": ("/", "site_accueil.html", "SlabCoach · L’app des cartes de sport", "SlabCoach · The sports card app",
                "Deals sous la valeur, SlabIQ et le bon moment pour acheter, vraie valeur, collection, ventes eBay et breaks. Gratuit, 14 jours de Pro offerts.",
                "Deals under value, SlabIQ and the right moment to buy, real value, collection, eBay sales and breaks. Free, 14 days of Pro on us."),
    "tarifs": ("/tarifs", "site_tarifs.html", "Tarifs · SlabCoach", "Pricing · SlabCoach",
               "Gratuit pour toujours, ou Pro à 7,99 $ CA par mois. 14 jours de Pro offerts, sans carte de crédit.",
               "Free forever, or Pro at $7.99 CAD a month. 14 days of Pro on us, no credit card."),
    "preuve": ("/preuve", None, "La preuve en direct · SlabCoach", "Live proof · SlabCoach",
               "Chaque jour, ce que SlabCoach dit est fige, enchaine et horodate avant de connaitre la suite. Les resultats arrivent 30, 60 et 90 jours plus tard.",
               "Every day, what SlabCoach says is frozen, chained and timestamped before the outcome is known. Results come 30, 60 and 90 days later."),
    "slabiq": ("/slabiq", "site_slabiq.html", "SlabIQ · SlabCoach", "SlabIQ · SlabCoach",
               "Une lettre de A+ à E pour chaque carte de sport. Apprise sur plus de 415 000 ventes réelles, testée sur des ventes qu’elle n’avait jamais vues.",
               "One letter from A+ to E for every sports card. Learned from 415,000+ real sales, tested on sales it had never seen."),
    "securite": ("/securite", "site_securite.html", "Sécurité · SlabCoach", "Security · SlabCoach",
                 "Paiement par Stripe ou Apple, aucun mot de passe gardé, connexion chiffrée, comptes séparés, données jamais vendues.",
                 "Payment by Stripe or Apple, no password kept, encrypted connection, separate accounts, data never sold."),
    "apropos": ("/a-propos", "site_apropos.html", "Qui nous sommes · SlabCoach", "About us · SlabCoach",
                "SlabCoach est fait au Québec par un collectionneur qui voulait passer plus de temps avec ses cartes, et moins à chercher.",
                "SlabCoach is made in Quebec by a collector who wanted to spend more time with his cards, and less time searching."),
}


def _page_vitrine(page="accueil", contenu_force=None):
    """27 oct 2026 - slabcoach.com pour un visiteur ; 16 nov 2026 : trois pages (accueil, tarifs, qui nous sommes)."""
    import html as _h
    chemin, fichier, t_fr, t_en, d_fr, d_en = SITE_PAGES.get(page) or SITE_PAGES["accueil"]
    try:
        with open(os.path.join(DOSSIER_UI, "site_base.html"), encoding="utf-8") as f:
            html = f.read()
        if contenu_force is not None:
            contenu = contenu_force
        else:
            with open(os.path.join(DOSSIER_UI, fichier), encoding="utf-8") as f:
                contenu = f.read()
    except OSError:
        from flask import redirect
        return redirect("/connexion")
    l = _langue()
    autre = "fr" if l == "en" else "en"
    html = (html.replace("{{CONTENU}}", contenu).replace("{{SCRIPT}}", "")
            .replace("{{TITRE}}", _h.escape(t_en if l == "en" else t_fr)).replace("{{DESC}}", _h.escape(d_en if l == "en" else d_fr))
            .replace("{{CHEMIN}}", chemin))
    for k in SITE_PAGES:
        html = html.replace("{{ACT_" + k.upper() + "}}", "actif" if k == page else "")
    # 21 nov 2026 (page Securite) : ces 2 lignes s'affichent seulement si c'est vrai en ce moment
    if "{{SECU_" in html:
        cf = _via_cloudflare() or bool(request.headers.get("CF-Ray"))
        try:
            import sauvegarde
            sv = sauvegarde.actif()
        except Exception:
            sv = False
        html = html.replace("{{SECU_CF}}", _SECU_CF if cf else "").replace("{{SECU_SAUV}}", _SECU_SAUV if sv else "")
    # 20 nov 2026 (Mathieu : « toutes les bonnes notes sur notre site en slide show, automatiquement ») : les vraies notes App Store
    try:
        import avis_app
        html = avis_app.injecter(html, contenu)
    except Exception:
        html = html.replace("{{AVIS_LIGNE}}", "").replace("{{AVIS_SECTION}}", "")
    # 19 nov 2026 (audit du site) : le Pro annuel n'est annonce que s'il est vraiment offert (le prix Stripe existe) ; sinon le
    # client qui le choisit recevait « Le forfait annuel n'est pas encore offert »
    try:
        import paiements
        annuel = bool(paiements.prix_pro_annuel())
    except Exception:
        annuel = False
    if not annuel:
        html = html.replace("</head>", "<style>.si-annuel{display:none !important} @media (min-width:901px){ .forfaits.trois:has(> .si-annuel){grid-template-columns:repeat(2,minmax(0,1fr)); max-width:760px} }</style></head>", 1)
    html = html.replace('<html lang="fr">', f'<html lang="{l}">').replace(
        '<a class="btn holo" href="/connexion"><span class="fr">Commencer</span>',
        f'<a class="lang" href="?lang={autre}">{"Français" if autre == "fr" else "English"}</a><a class="btn holo" href="/connexion"><span class="fr">Commencer</span>', 1)
    from flask import make_response
    r = make_response(html)
    if request.args.get("lang") in ("fr", "en"):
        r.set_cookie("lr_langue", l, max_age=365 * 86400, samesite="Lax", secure=HEBERGE, httponly=True)   # 12 nov 2026 (Aikido) : jamais en clair ; 18 nov : HttpOnly
    return r


@app.route("/tarifs")
@app.route("/pricing")
def page_tarifs():
    if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
        from flask import redirect
        return redirect("/connexion")                                # app iPhone : pas les prix du site (regles d'Apple)
    return _page_vitrine("tarifs")


def _bloc_bareme(t):
    """19 nov 2026 (audit : « 5x ici, 10x la ») : le meme test que la page SlabIQ et l'accueil (ui/slabiq_tests.json, refait a
    chaque version de SlabIQ par outils/tests_site.py) : les lettres fixees avec les ventes d'AVANT une date, les reventes
    mesurees APRES, sur des ventes que SlabIQ n'avait jamais vues. Plus aucun prix tire des ventes eBay sur cette page."""
    try:
        with open(os.path.join(DOSSIER_UI, "slabiq_tests.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return ""
    L = d.get("lettres") or {}
    if not L.get("E") or not d.get("x_ahaut_e"):
        return ""
    nb = lambda v: f"{v:,}".replace(",", "\u00a0")
    MF = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    def jr(x):
        try:
            a = date.fromisoformat(x)
        except (TypeError, ValueError):
            return x, x
        return f"{a.day}{'er' if a.day == 1 else ''} {MF[a.month - 1]} {a.year}", f"{ME[a.month - 1]} {a.day}, {a.year}"
    c_fr, c_en = jr(d.get("coupe"))
    r0_fr, r0_en = jr(d.get("revente_des"))
    r1_fr, r1_en = jr(d.get("revente_fin"))
    x = int(round(d["x_ahaut_e"]))
    lig = "".join(f'<tr><td><b>{l}</b></td><td class="n">{nb(L[l]["cartes"])}</td><td class="n{" vert" if l in ("A+", "A") else ""}">{str(L[l]["reventes"]).replace(".", ",")}</td></tr>'
                  for l in ("A+", "A", "A-", "B+", "B", "C", "D", "E") if L.get(l))
    return f"""<section><div class="conteneur">
  <p class="kicker holo-t">{t("Les lettres SlabIQ", "SlabIQ letters")}</p>
  <h2>{t(f'Une carte A ou A+ se revend <span class="holo-t">{x} fois</span> plus souvent qu’une carte E', f'An A or A+ card resells <span class="holo-t">{x} times</span> more often than an E card')}</h2>
  <p class="intro">{t(f"Le test : chaque carte reçoit sa lettre avec seulement les ventes d’avant le {c_fr}. Puis on compte ses reventes entre le {r0_fr} et le {r1_fr} : des ventes que SlabIQ n’avait jamais vues.", f"The test: every card gets its letter using only sales before {c_en}. Then we count its resales between {r0_en} and {r1_en}: sales SlabIQ had never seen.")}</p>
  <div style="overflow-x:auto"><table class="tab-f"><thead><tr><th>{t("Lettre", "Letter")}</th><th>{t("Cartes", "Cards")}</th><th>{t("Reventes par carte", "Resales per card")}</th></tr></thead><tbody>{lig}</tbody></table></div>
  <p class="note">{t(f"{nb(d.get('ventes_total', 0))} ventes de hockey, {nb(d.get('joueurs', 0))} joueurs. Refait à chaque nouvelle version de SlabIQ ; les mêmes chiffres que sur la page SlabIQ.", f"{nb(d.get('ventes_total', 0))} hockey sales, {nb(d.get('joueurs', 0))} players. Redone with every new SlabIQ version; the same numbers as on the SlabIQ page.")}</p>
</div></section>"""


def _bloc_collectionneurs(t):
    # 19 nov 2026 (audit du site) : plus affiche sur /preuve : cette ancienne simulation n'est pas refaite avec chaque version de
    # SlabIQ ; la simulation testee (outils/tests_site.py) est sur la page SlabIQ
    """16 nov 2026 (Mathieu : « deux collectionneurs, le meme budget, avec et sans SlabIQ ; le montrer sur le site » ; « montre
    la difference entre les deux, pas des negatifs ») : l'avance de la collection avec SlabIQ sur celle sans, en gros chiffres."""
    try:
        import simulation_iq
        d = simulation_iq.lire()
    except Exception:
        d = {}
    T = d.get("total") or {}
    if not T.get("n") or T.get("avantage_pct") is None:
        return ""
    plus = lambda v: f"+{max(0, round(v))}\u00a0%"
    pt = d.get("par_type") or {}
    nom_t = {"joueur": t("Un joueur", "One player"), "equipe": t("Une équipe", "One team"), "panier": t("5 joueurs", "5 players")}
    lignes = "".join(f'<tr><td>{nom_t.get(k, k)}</td><td class="n vert">{round(v["b_gagne"] * 100)}\u00a0%</td><td class="n vert">{plus(v["avantage_pct"])}</td><td class="n">{v["n"]:,}</td></tr>'.replace(",", "\u00a0")
                     for k, v in pt.items() if v.get("n") and v.get("avantage_pct") is not None)
    pj = d.get("par_joueur") or {}
    gagnes = sum(1 for v in pj.values() if v.get("b_gagne", 0) > 0.5)
    ex = ""
    for x in (d.get("exemples") or [])[:5]:
        a_, b_ = x["A"], x["B"]
        if a_["total"] <= 0 or b_["total"] <= a_["total"]:
            continue
        ex += (f'<tr><td>{x["nom"]}</td><td class="n">${a_["total"]:,.0f}</td><td class="n vert">${b_["total"]:,.0f}</td>'
               f'<td class="n vert">{plus(100 * (b_["total"] / a_["total"] - 1))}</td></tr>')
    n_ = f'{T["n"]:,}'.replace(",", "\u00a0")
    return f"""<section><div class="conteneur">
  <style>.sim-k{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:22px 0}}
  .sim-k > div{{padding:20px 22px;border-radius:20px;border:1.5px solid transparent;background:linear-gradient(#141419,#141419) padding-box,linear-gradient(120deg,rgba(184,188,255,.8),rgba(242,179,214,.55),rgba(159,230,210,.55),rgba(241,213,142,.6)) border-box}}
  .sim-k b{{display:block;font:800 clamp(44px,6vw,64px)/1 'Barlow Condensed',sans-serif;background:linear-gradient(100deg,#F2B3D6,#F1D58E,#9FE6D2,#B8BCFF);-webkit-background-clip:text;background-clip:text;color:transparent}}
  .sim-k h3{{margin:10px 0 4px;font-size:20px}} .sim-k p{{margin:0;color:#A9A6B4}} .sim-t td.n{{white-space:nowrap}}</style>
  <p class="kicker holo-t">{t("Deux collectionneurs, le même budget", "Two collectors, the same budget")}</p>
  <h2>{t(f'Avec SlabIQ, la collection vaut <span class="holo-t">{plus(T["avantage_pct"])}</span> de plus', f'With SlabIQ, the collection is worth <span class="holo-t">{plus(T["avantage_pct"])}</span> more')}</h2>
  <p class="intro">{t("Deux personnes commencent à collectionner avec le même budget chaque mois. L’une achète au hasard, ou quand tout le monde en parle. L’autre suit SlabIQ : quoi acheter, quand, et quand attendre. On compare ce que valent leurs cartes à la fin.", "Two people start collecting with the same monthly budget. One buys at random, or when everyone is talking about it. The other follows SlabIQ: what to buy, when, and when to wait. We compare what their cards are worth at the end.")}</p>
  <div class="sim-k">
    <div><b>{plus(T["avantage_pct"])}</b><h3>{t("de valeur en plus", "more value")}</h3><p>{t("pour la collection avec SlabIQ, à budget égal.", "for the collection with SlabIQ, same budget.")}</p></div>
    <div><b>{round(T["b_gagne"] * 100)}\u00a0%</b><h3>{t("des collections", "of collections")}</h3><p>{t(f"finissent devant avec SlabIQ, sur {n_} tests.", f"finish ahead with SlabIQ, out of {n_} tests.")}</p></div>
    <div><b>{gagnes}/{len(pj)}</b><h3>{t("joueurs", "players")}</h3><p>{t("où SlabIQ fait mieux que l’achat au hasard.", "where SlabIQ beats buying at random.")}</p></div>
  </div>
  <div style="overflow-x:auto"><table class="tab-f sim-t"><thead><tr><th>{t("Collection", "Collection")}</th><th>{t("SlabIQ devant", "SlabIQ ahead")}</th><th>{t("Valeur en plus", "More value")}</th><th>{t("Tests", "Tests")}</th></tr></thead><tbody>{lignes}</tbody></table></div>
  {f'<h3 class="mo-titre">{t("Exemples : 1 an, 100 $ par mois", "Examples: 1 year, $100 a month")}</h3><div style="overflow-x:auto"><table class="tab-f sim-t"><thead><tr><th>{t("Joueur", "Player")}</th><th>{t("Sans SlabIQ", "Without")}</th><th>{t("Avec SlabIQ", "With")}</th><th>{t("En plus", "More")}</th></tr></thead><tbody>{ex}</tbody></table></div>' if ex else ''}
  <p class="note">{t(f"{n_} scénarios : {d.get('joueurs', 0)} joueurs seuls, leurs équipes et des groupes de 5 joueurs ; départs tous les 2 mois ; 6 mois et 1 an ; 50, 100 et 250 $ par mois ; acheteur au hasard ou « quand ça monte » ; 3 réglages de SlabIQ. Les cartes : la Young Guns de chaque joueur (raw et PSA 10), aux prix des vraies ventes, frais d’achat et port compris pour les deux. SlabIQ ne voit jamais le futur : chaque achat se décide avec les ventes d’avant. Valeur à la fin : les ventes réelles du dernier mois, plus l’argent pas encore dépensé. Les exemples sont le résultat médian de chaque joueur. Le test en direct ci-dessous, figé chaque jour, continue la preuve.", f"{n_} scenarios: {d.get('joueurs', 0)} single players, their teams and groups of 5 players; starts every 2 months; 6 months and 1 year; $50, $100 and $250 a month; random or “buy when it’s rising” buyer; 3 SlabIQ settings. The cards: each player’s Young Guns (raw and PSA 10), at real sale prices, buying fees and shipping included for both. SlabIQ never sees the future: every purchase is decided with past sales only. End value: real sales of the last month, plus money not yet spent. Examples are each player’s median result. The live test below, frozen every day, continues the proof.")}</p>
</div></section>"""


@app.route("/preuve")
@app.route("/proof")
def page_preuve():
    import preuve
    import html as _h
    p = preuve.public()
    t = lambda fr, en: f'<span class="fr">{fr}</span><span class="en">{en}</span>'
    ch = list(reversed(p["chaine"]))
    rs = (p.get("resultats") or {}).get("par_horizon") or {}
    lignes_r = ""
    for h in ("30", "60", "90"):
        r = rs.get(h) or {}
        sa, av = r.get("sans"), r.get("avec")
        if sa and av:
            lignes_r += (f'<tr><td>{h} {t("jours", "days")}</td><td class="n rouge">{sa["mediane_pct"]:+.1f} %</td><td class="n vert">{av["mediane_pct"]:+.1f} %</td>'
                         f'<td class="n">{av["vaut_plus_pct"]} % / {sa["vaut_plus_pct"]} %</td><td class="n">{av["n"]} / {sa["n"]}</td></tr>')
    lignes_a = ""
    for h in ("30", "60", "90"):
        r = rs.get(h) or {}
        av, at, al = r.get("autres_avec"), r.get("autres_attendre"), r.get("autres")
        if al:
            f_ = lambda x: (f'{x["mediane_pct"]:+.1f} % <small>({x["vaut_plus_pct"]} % +, n={x["n"]})</small>') if x else "—"
            lignes_a += (f'<tr><td>{h} {t("jours", "days")}</td><td class="n">{f_(al)}</td><td class="n vert">{f_(av)}</td><td class="n rouge">{f_(at)}</td></tr>')
    if ch:
        prem = ch[-1]["jour"]
        try:
            pret = (date.fromisoformat(prem) + timedelta(days=30 + 14)).isoformat()
        except ValueError:
            pret = ""
    else:
        prem, pret = "", ""
    res_html = (f'<table class="tab-f"><thead><tr><th>{t("Après", "After")}</th><th>{t("Sans SlabCoach", "Without SlabCoach")}</th><th>{t("Avec SlabCoach", "With SlabCoach")}</th>'
                f'<th>{t("Valaient plus (avec / sans)", "Worth more (with / without)")}</th><th>{t("Cartes (avec / sans)", "Cards (with / without)")}</th></tr></thead><tbody>{lignes_r}</tbody></table>') if lignes_r else (
        f'<p class="intro">{t(f"Les premiers résultats en direct arrivent vers le {pret} : il faut 30 jours, puis 2 semaines de ventes pour mesurer la valeur.", f"The first live results arrive around {pret}: it takes 30 days, then 2 weeks of sales to measure value.")}</p>' if pret else "")
    if lignes_a:
        res_html += (f'<h3 class="mo-titre">{t("Les autres cartes du Radar (autos, patchs, numérotées)", "Other Radar cards (autos, patches, numbered)")}</h3>'
                     f'<table class="tab-f"><thead><tr><th>{t("Après", "After")}</th><th>{t("Tous les deals", "All deals")}</th><th>{t("Bon moment", "Good moment")}</th><th>{t("Attendre", "Wait")}</th></tr></thead><tbody>{lignes_a}</tbody></table>')
    v = p.get("verification") or {}
    def _rang(e):
        j = _h.escape(e["jour"])
        fich = ('<a href="/preuve/' + j + '.json">JSON</a> · ') if e.get("fichier") else ((t("public après %d j" % p["public_apres_j"], "public after %d d" % p["public_apres_j"]) if p.get("fichiers_publics") else t("empreinte seulement", "fingerprint only")) + " · ")
        ots = ('<a href="/preuve/' + j + '.json.ots">.ots</a>') if e.get("ots") else ""
        return ("<tr><td>" + j + '</td><td class="n">' + str(e.get("n_marche", 0)) + " + " + str(e.get("n_radar", 0)) + "</td>"
                + '<td><code title="' + _h.escape(e["sha256"]) + '">' + _h.escape(e["sha256"][:16]) + "…</code></td>"
                + "<td>" + ("✓ Bitcoin" if e.get("ots") else t("en attente", "pending")) + "</td><td>" + fich + ots + "</td></tr>")
    rangs = "".join(_rang(e) for e in ch[:120])
    contenu = f"""<div class="page-tete"><div class="conteneur">
  <p class="kicker holo-t">{t("La preuve en direct", "Live proof")}</p>
  <h1>{t('Pas de résultats arrangés. <span class="holo-t">Tout est figé avant.</span>', 'No cherry-picked results. <span class="holo-t">Everything is frozen first.</span>')}</h1>
  <p class="sous-titre">{t("Chaque jour, ce que SlabCoach dit est enregistré avant de connaître la suite. Personne, pas même nous, ne peut le changer après coup.", "Every day, what SlabCoach says is recorded before the outcome is known. No one, not even us, can change it afterwards.")}</p>
</div></div>
<section style="padding-top:24px"><div class="conteneur">
  <div class="etapes">
    <div class="etape"><b>1</b><h3>{t("Figé chaque jour", "Frozen every day")}</h3><p>{t("Le prix de chaque Young Guns suivie, le moment SlabIQ, le score et chaque deal du Radar, autos, patchs et numérotées compris (un échantillon tiré au hasard est re-mesuré à 30, 60 et 90 jours).", "The price of every tracked Young Guns, the SlabIQ moment, the score and every Radar deal, autos, patches and numbered included (a random sample is re-measured at 30, 60 and 90 days).")}</p></div>
    <div class="etape"><b>2</b><h3>{t("Empreinte horodatée", "Timestamped fingerprint")}</h3><p>{t("L’empreinte du fichier (SHA-256) est enchaînée à la veille et ancrée dans Bitcoin (OpenTimestamps). Changer un seul chiffre casse la preuve.", "The file’s fingerprint (SHA-256) is chained to the day before and anchored in Bitcoin (OpenTimestamps). Changing a single number breaks the proof.")}</p></div>
    <div class="etape"><b>3</b><h3>{t("Le résultat, plus tard", "The result, later")}</h3><p>{t("30, 60 et 90 jours après, on mesure ce que les cartes valaient vraiment. L’empreinte de chaque jour est publique dès le jour même ; les fichiers complets seront publiés quand nos licences de données le permettront.", "30, 60 and 90 days later, we measure what the cards were really worth. Each day’s fingerprint is public the same day; the full files will be published once our data licences allow it.")}</p></div>
  </div>
</div></section>
{_bloc_bareme(t)}

<section><div class="conteneur">
  <p class="kicker holo-t">{t("Résultats en direct", "Live results")}</p>
  <h2>{t("Sans SlabCoach contre avec SlabCoach", "Without vs with SlabCoach")}</h2>
  {res_html}
</div></section>
<section><div class="conteneur">
  <p class="kicker holo-t">{t("La chaîne", "The chain")}</p>
  <h2>{t(f"{len(ch)} jour(s) figé(s)", f"{len(ch)} day(s) frozen")} · {"✓ " + t("chaîne intacte", "chain intact") if v.get("ok") else t("à vérifier", "to check")}</h2>
  <div style="overflow-x:auto"><table class="tab-f"><thead><tr><th>{t("Jour", "Day")}</th><th>{t("Cartes + deals", "Cards + deals")}</th><th>SHA-256</th><th>{t("Horodatage", "Timestamp")}</th><th>{t("Fichiers", "Files")}</th></tr></thead><tbody>{rangs}</tbody></table></div>
  <p class="note">{t("Pour vérifier : télécharge le fichier JSON d’un jour et son .ots, puis lance « ots verify » (opentimestamps.org). L’empreinte SHA-256 du JSON doit être celle de la chaîne.", "To verify: download a day’s JSON file and its .ots, then run “ots verify” (opentimestamps.org). The JSON’s SHA-256 must match the chain.")} <a href="/preuve/chaine.json">chaine.json</a></p>
</div></section>"""
    return _page_vitrine("preuve", contenu)


@app.route("/preuve/chaine.json")
def preuve_chaine():
    import preuve
    return jsonify(preuve.chaine())


@app.route("/preuve/<jour>.json")
def preuve_fichier(jour):
    import preuve
    import re as _re
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", jour or "") or jour > (date.today() - timedelta(days=preuve.DELAI_PUBLIC_J)).isoformat():
        return jsonify({"erreur": "Pas encore public"}), 404
    if not preuve.fichiers_publics():                # 19 nov 2026 (audit) : des prix tires d'eBay : pas publics sans licence
        return jsonify({"erreur": "Réservé : publié quand nos licences de données le permettront ; l’empreinte du jour est publique"}), 404
    try:
        corps = preuve.lire_jour(jour)
    except OSError:
        return jsonify({"erreur": "Introuvable"}), 404
    from flask import Response
    return Response(corps, mimetype="application/json", headers={"Content-Disposition": f"attachment; filename={jour}.json"})


@app.route("/preuve/<jour>.json.ots")
def preuve_ots(jour):
    import preuve
    import re as _re
    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", jour or ""):
        return jsonify({"erreur": "Introuvable"}), 404
    ch = os.path.join(preuve.dossier(), jour + ".ots")
    if not os.path.exists(ch):
        return jsonify({"erreur": "Pas encore horodaté"}), 404
    from flask import send_file
    return send_file(ch, mimetype="application/octet-stream", as_attachment=True, download_name=jour + ".json.ots")


@app.route("/slabiq")
def page_slabiq():
    """18 nov 2026 (Mathieu : « une page dediee, c'est vraiment fort ce qu'on construit »)."""
    if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
        from flask import redirect
        return redirect("/connexion")
    return _page_vitrine("slabiq")


_SECU_CF = ('<li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/><circle cx="12" cy="12" r="9"/></svg><div><b><span class="fr">Derrière un pare-feu</span>'
            '<span class="en">Behind a firewall</span></b><span class="fr">Le site passe par Cloudflare : pare-feu applicatif et protection contre les attaques '
            'par saturation, avant même d’arriver chez nous.</span><span class="en">The site runs through Cloudflare: a web application firewall and protection '
            'against flood attacks, before traffic even reaches us.</span></div></li>')
_SECU_SAUV = ('<li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg><div><b><span class="fr">Sauvegardé chaque nuit</span><span class="en">Backed up every night</span></b>'
              '<span class="fr">Une copie de toutes les données part chaque nuit hors de notre hébergeur. Un compte supprimé en disparaît aussi, après 8 semaines au plus.</span>'
              '<span class="en">A copy of all data leaves our host every night. A deleted account disappears from it too, within 8 weeks at most.</span></div></li>')


@app.route("/securite")
@app.route("/security")
def page_securite():
    if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):      # comme /a-propos : la vitrine a des prix du site
        from flask import redirect
        return redirect("/connexion")
    return _page_vitrine("securite")


@app.route("/x/<jeton>/<nom>")
def fichier_temporaire(jeton, nom):
    """21 nov 2026 : un fichier fabrique pour l'app iPhone (liste de consignation), 20 min, lien impossible a deviner."""
    import re as _re
    import exports_temp
    f = exports_temp.lire(jeton) if _re.fullmatch(r"[0-9a-f]{32}", str(jeton or "")) else None
    if not f:
        return ("Ce lien n’est plus valide : refais l’export dans l’app. / This link expired: export again in the app.", 404,
                {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"})
    h = {"Content-Type": f["type"], "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex"}
    if not f["type"].startswith("text/html"):       # a l'ordi (?d=1) : telecharge ; au cell : Safari l'ouvre (apercu, Partager)
        h["Content-Disposition"] = ("attachment" if request.args.get("d") == "1" else "inline") + '; filename="' + _re.sub(r"[^A-Za-z0-9._-]+", "-", f["nom"]) + '"'
    return (f["octets"], 200, h)


@app.route("/a-propos")
@app.route("/about")
def page_apropos():
    if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
        from flask import redirect
        return redirect("/connexion")
    return _page_vitrine("apropos")


def _page_langue(html):
    from flask import make_response
    l = _langue()
    if l == "en":
        for a, b in _EN:
            html = html.replace(a, b)
    autre = "fr" if l == "en" else "en"
    lien = (f"<a href='?lang={autre}' style='position:fixed;top:calc(env(safe-area-inset-top,0px) + 10px);left:calc(env(safe-area-inset-left,0px) + 14px);padding:7px 12px;border-radius:999px;"
            f"border:1px solid #34333D;background:rgba(21,21,25,.7);color:#F4F2EE;font:700 13px system-ui;text-decoration:none;z-index:5'>"
            f"{'Français' if autre == 'fr' else 'English'}</a>")
    r = make_response(html.replace("</body>", lien + "</body>"))
    if request.args.get("lang") in ("fr", "en"):
        r.set_cookie("lr_langue", l, max_age=365 * 86400, samesite="Lax", secure=HEBERGE, httponly=True)   # 12 nov 2026 (Aikido) : jamais en clair ; 18 nov : HttpOnly
    return r


# 2 nov 2026 (Mathieu : « un utilisateur doit voir la meme chose sur son ordi que sur son cell ») : le code d'appareil.
# Sur le telephone (Profil > Ouvrir sur un autre appareil) : 8 chiffres (6 avant le 3 nov 2026), 10 min. Ici, sur l'ordi : on l'entre et la session
# s'ouvre sur le MEME compte, peu importe comment on s'est connecte la premiere fois.
@app.route("/auth/code", methods=["GET", "POST"])
def auth_code():
    from flask import redirect
    if not comptes.MULTI:
        return redirect("/")
    msg = ""
    if request.method == "POST":
        if _trop_d_essais():
            msg = "Trop d’essais : réessaie dans 15 minutes"
        else:
            cid = comptes.code_utiliser(request.form.get("code"))
            if cid:
                _ouvrir_session(cid, garder_ok=True)
                return redirect("/#accueil")
            _noter_echec()
            msg = "Code invalide ou expiré : demande un nouveau code sur ton téléphone"
    return _page_langue("""<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SlabCoach · Code d’appareil</title><link rel="icon" href="/favicon.ico?v=2">
<style>@font-face{font-family:'Barlow';font-weight:600;src:url(/barlow-600.woff2) format('woff2')}
@font-face{font-family:'Barlow Condensed';font-weight:700;src:url(/barlow-cond-700.woff2) format('woff2')}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0B0B0E;color:#F4F2EE;font-family:'Barlow',system-ui,sans-serif;padding:16px}
form{width:min(380px,100%);display:grid;gap:14px;text-align:center}h1{margin:12px 0 0;font-size:26px}p{margin:0;color:#A9A6B1;line-height:1.45}
input{font:700 40px 'Barlow Condensed',sans-serif;letter-spacing:.35em;text-align:center;padding:14px 0 14px .35em;border-radius:16px;border:1px solid #393845;background:#1C1C24;color:#F4F2EE;width:100%;box-sizing:border-box}
button{padding:16px;border-radius:14px;border:0;font:700 18px 'Barlow Condensed',sans-serif;letter-spacing:.06em;text-transform:uppercase;background:#B9BEFF;color:#0E1026;cursor:pointer}
.err{color:#FFB3B3}a{color:#A9A6B1;font-size:14px}</style>
<form method="post"><img src="/logo_sc_gold_poli.png" width="64" style="margin:auto" alt="">
<h1>Ouvrir mon compte ici</h1>
<p>Sur ton téléphone : <b>Profil › Ouvrir sur un autre appareil</b>. Entre le code à 8 chiffres affiché.</p>
<input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="10" pattern="[0-9 ]*" placeholder="0000 0000" autofocus required>
""" + (f"<p class='err'>{msg}</p>" if msg else "") + """<button type="submit">Ouvrir</button><a href="/connexion">‹ Autres façons de se connecter</a></form></html>""")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    import hmac
    from flask import redirect, session
    if comptes.MULTI and (not CODE_ACCES or session.get("ok")):
        if session.get("compte") in comptes.lister():
            return redirect("/")
        err = request.args.get("erreur")
        e = ("<div class='erreur'>Connexion eBay interrompue : réessaie</div>" if err == "1" else
             "<div class='erreur'>Cette connexion n’est pas encore offerte : utilise eBay</div>" if err == "2" else
             "<div class='erreur'>Connexion interrompue : réessaie" + {"lien": " (le retour n’est pas arrivé dans ce navigateur)",
                "jeton": " (le service n’a pas confirmé ton identité)", "expire": " (connexion expirée)"}.get(request.args.get("r"), "")
             + "</div>" if err else "")
        page = _page_connexion().replace("{erreur}", e)
        import auth_tiers
        ios = "LockerRoomiOS" in (request.headers.get("User-Agent") or "")
        flux_app = "SlabCoachAuth" in (request.headers.get("User-Agent") or "")    # 28 oct 2026 : app avec navigateur securise
        autres = [f for f in auth_tiers.actifs() if not (ios and f == "google" and not flux_app)]   # Google refuse les vues web
        page = page.replace("{autres}", "".join(_BOUTONS_TIERS[f] for f in ("apple", "google") if f in autres))
        if ios:                                   # app iPhone : pas de lien vers la vitrine (prix du site)
            page = page.replace('<a href="/">‹ Retour au site</a>', "")
            page = page.replace('<a class="confiance" href="/securite">', '<div class="confiance">').replace("données jamais vendues</span></a>", "données jamais vendues</span></div>")
        if not autres:
            page = page.replace('<div class="ou">ou</div>', "")
        # 2 nov 2026 : ouvrir le compte de l'autre appareil. 9 nov 2026 (Mathieu : 2 comptes, « un moyen beton pour que ca
        # n'arrive pas aux utilisateurs ») : partout, le rappel de se connecter pareil. 10 nov 2026 (« trop d'info ») : 1 ligne
        page = page.replace("{rappel}", "<div class='rappel-meme'>Déjà un compte ? Connecte-toi de la même façon, ou "
                            "<a href='/auth/code'>entre un code d’appareil</a></div>")
        demo = os.environ.get("LOCKERROOM_DEMO_CODE") and "LockerRoomiOS" in (request.headers.get("User-Agent") or "")
        page = page.replace("{demo}", "<a href='/demo'>Démo / Demo</a>" if demo else "")
        return _page_langue(page)
    if not CODE_ACCES:
        return redirect("/")
    erreur = ""
    if request.method == "POST" and _trop_d_essais():
        erreur = "<p style='color:#FFB3B3'>Trop d’essais : réessaie dans 15 minutes</p>"
    elif request.method == "POST":
        if hmac.compare_digest(str(request.form.get("code") or ""), CODE_ACCES):
            session.permanent = True
            session["ok"] = True
            return redirect("/connexion" if comptes.MULTI else "/")
        _noter_echec()
        erreur = "<p style='color:#FFB3B3'>Code incorrect</p>"
    return _page_langue("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>SlabCoach</title><link rel='icon' href='/favicon.ico?v=2'>"
            "<body style='background:#0B0B0E;color:#F4F2EE;font-family:system-ui;display:grid;place-items:center;min-height:90vh'>"
            "<form method='post' style='display:grid;gap:12px;width:min(320px,90vw)'><img src='/logo_sc_gold_poli.png' width='72' style='margin:auto' alt=''>"
            "<b style='font-size:22px'>SlabCoach</b><input name='code' type='password' autofocus placeholder='Code d’accès' "
            "style='padding:12px;border-radius:10px;border:1px solid #2B2A32;background:#151519;color:#F4F2EE;font-size:16px'>"
            f"{erreur}<button style='padding:12px;border-radius:10px;border:0;background:#B9BEFF;font-weight:700;font-size:16px'>Entrer</button>"
            "<a href='/confidentialite' style='color:#A9A6B1;font-size:13px'>Confidentialité</a></form></body>")


def _dans_app_ios():
    # 28 oct 2026 (audit Apple 3.1.1) : ?ios=1 quand l'app ouvre une page dans le navigateur integre (sans son agent)
    return "LockerRoomiOS" in (request.headers.get("User-Agent") or "") or request.args.get("ios") == "1"


def _page_legale(nom):
    """27 oct 2026 (revue Apple 3.1.1) : dans l'app iPhone, rien sur l'achat par le site (prix, Stripe) : au Canada,
    Apple interdit d'orienter vers un autre moyen de paiement. Sur le web : la page complete."""
    if not _dans_app_ios():
        return send_from_directory(DOSSIER_UI, nom)
    import re as _re
    from flask import Response
    with open(os.path.join(DOSSIER_UI, nom), encoding="utf-8") as f:
        html = f.read()
    for _ in range(3):                        # elements « web-seul » (p, li, span), du plus interne au plus externe
        html = _re.sub(r'<(p|li|span)\b[^>]*class="web-seul"[^>]*>(?:(?!<\1\b)[\s\S])*?</\1>', "", html)
    html = html.replace(".ios-seul{display:none}", "")
    html = html.replace('<a href="/">Ouvrir l\'app</a>', "")             # pas de chemin vers le site (prix) depuis l'app
    for page in ("support", "confidentialite", "conditions"):
        html = html.replace(f'href="/{page}"', f'href="/{page}?ios=1"')
    return Response(html, mimetype="text/html")


@app.route("/confidentialite")
def page_confidentialite():
    return _page_legale("confidentialite.html")


# 20 nov 2026 (Cloudflare Security Insights : « Security.txt not configured ») : qui contacter pour signaler une faille (RFC 9116)
@app.route("/.well-known/security.txt")
@app.route("/security.txt")
def security_txt():
    from flask import Response
    fin = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT00:00:00.000Z")
    return Response("Contact: mailto:support@slabcoach.com\n"
                    f"Expires: {fin}\n"
                    "Preferred-Languages: fr, en\n"
                    "Canonical: https://slabcoach.com/.well-known/security.txt\n", mimetype="text/plain")


@app.route("/conditions")
def page_conditions():
    return _page_legale("conditions.html")


@app.route("/support")
def page_support():
    """27 oct 2026 - page de support (exigee par Apple et Stripe) : contact et questions frequentes."""
    return _page_legale("support.html")


@app.route("/")
def racine():
    return _page_app()


def _break_public(jeton):
    """Page publique d'un break : en multi-comptes, on trouve le compte qui l'a cree."""
    import re
    import time
    import comptes as _c
    if not _c.MULTI:
        return api.break_public(jeton)
    # 27 oct 2026 (revue) : avant, CHAQUE visite ouvrait la base de tous les comptes. Maintenant : forme du lien verifiee,
    # compte memorise une fois trouve, lien inconnu oublie 10 min (pas de 2e recherche complete).
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", str(jeton or "")):
        return None
    m = time.time()
    cid = _BREAKS_TROUVES.get(jeton)
    if cid and cid in _c.lister():
        with _c.utiliser(cid):
            d = api.break_public(jeton)
        if d:
            return d
        _BREAKS_TROUVES.pop(jeton, None)
    if m - _BREAKS_INCONNUS.get(jeton, 0) < 600:
        return None
    for cid in _c.lister():
        with _c.utiliser(cid):
            d = api.break_public(jeton)
            if d:
                _BREAKS_TROUVES[jeton] = cid
                return d
    if len(_BREAKS_INCONNUS) > 5000:
        _BREAKS_INCONNUS.clear()
    _BREAKS_INCONNUS[jeton] = m
    return None


_BREAKS_TROUVES, _BREAKS_INCONNUS = {}, {}


@app.route("/b/<jeton>")
def page_break(jeton):
    if not _break_public(jeton):
        abort(404)
    # 18 nov 2026 : le temoin de langue est HttpOnly (Aikido) : le serveur ecrit la langue dans <html lang>, la page la lit la
    l = request.args.get("lang") if request.args.get("lang") in ("fr", "en") else request.cookies.get("lr_langue")
    if l not in ("fr", "en"):
        return send_from_directory(DOSSIER_UI, "break.html")
    with open(os.path.join(DOSSIER_UI, "break.html"), encoding="utf-8") as f:
        return f.read().replace('<html lang="fr">', f'<html lang="{l}" data-langue="{l}">', 1)


@app.route("/api/b/<jeton>")
def donnees_break(jeton):
    d = _break_public(jeton)
    if not d:
        return jsonify({"erreur": "Break introuvable"}), 404
    return jsonify(d)


@app.route("/api/ebay_retour")
def ebay_retour():
    """Page ou eBay renvoie le vendeur apres « Accepter » (auth accepted URL)."""
    from flask import redirect
    if not _navigateur_lie(request.args.get("state")):
        return redirect("/connexion?erreur=1" if not comptes.courant() else "/#reglages/ebay-erreur")
    lie = _LIER_ETATS.pop(request.args.get("state") or "", None)
    if lie and lie[0] in comptes.lister():            # 28 oct 2026 : eBay relie depuis l'app (navigateur securise)
        # 3 nov 2026 (revue) : rien n'est relie ici ; seulement quand l'app rend le billet avec son secret (ou dans le
        # navigateur deja connecte a ce compte)
        return _billet(lie[0], "/#reglages/ebay-ok", request.args.get("state"), attente=("ebay", request.url, request.args.get("state")))
    import ebay_compte
    if comptes.MULTI and (not comptes.courant() or ebay_compte.attente_existe(request.args.get("state"))):
        comptes.activer(None)                         # 10 nov 2026 : une connexion, meme si ce navigateur a une session
        r = ebay_compte.connexion_compte(request.url, request.args.get("state"))
        if not r.get("ok"):
            return redirect("/connexion?erreur=1")
        _unifier_ebay(r["compte"])
        _premiere_synchro(r["compte"])
        return _billet(r["compte"], "/#accueil/" + ("bienvenue" if r.get("nouveau") else "retour"), request.args.get("state"))
    r = api.ebay_terminer(request.url, request.args.get("state"))
    if r.get("ok") and comptes.MULTI and comptes.courant():      # 28 oct 2026 : eBay relie depuis Reglages -> import tout seul
        _unifier_ebay(comptes.courant())
        _premiere_synchro(comptes.courant())
    return redirect("/#reglages/" + ("ebay-ok" if r.get("ok") else "ebay-erreur"))


@app.route("/apple/notifications", methods=["POST"])
def apple_notifications():
    """27 oct 2026 - avis signes d'Apple (App Store Server Notifications v2) : renouvellement, annulation, remboursement."""
    import achats_apple
    code, msg = achats_apple.recevoir_avis(request.get_data(), comptes)
    if code >= 400:
        app.logger.warning("Avis Apple refuse : %s", msg)
    return jsonify({"recu": msg}), code


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """24 oct 2026 - avis signes de Stripe : seul chemin qui donne (ou retire) le forfait Pro."""
    import paiements
    code, msg = paiements.recevoir(request.get_data(), request.headers.get("Stripe-Signature"))
    if code >= 400:
        app.logger.warning("Stripe webhook refuse : %s", msg)
    return jsonify({"recu": msg}), code


@app.route("/ebay/suppression-compte", methods=["GET", "POST"])
def ebay_suppression_compte():
    """21 oct 2026 - avis obligatoire d'eBay (Marketplace Account Deletion)."""
    import ebay_avis
    if request.method == "GET":
        code = request.args.get("challenge_code")
        if not code:
            abort(400)
        try:
            return jsonify(ebay_avis.reponse_defi(code))
        except RuntimeError:
            abort(503)
    if not ebay_avis.recevoir(request.get_data(), request.headers.get("X-EBAY-SIGNATURE")):
        return ("", 412)                    # 27 oct 2026 : signature absente ou invalide -> rien n'est supprime
    return ("", 204)


@app.route("/mes-photos/<nom>")
def mes_photos(nom):
    """27 oct 2026 : photos des cartes gardees dans l'inventaire, seulement pour le compte connecte (voir _garde)."""
    import photos_cartes
    f = photos_cartes.chemin(nom)
    if not f:
        abort(404)
    return send_from_directory(os.path.dirname(f), os.path.basename(f), mimetype="image/jpeg", max_age=30 * 86400)


_EXPORT_V = {}                 # 19 nov 2026 : sport -> debut de l'export en cours (expire seul apres 10 min)


@app.route("/admin/ventes_export.tsv.gz")
def admin_ventes_export():
    """18 nov 2026 (Mathieu : « travaille sur SlabIQ cette nuit avec nos nouvelles donnees ») : TOUTES nos ventes archivees
    (titre, prix CAD, date, recherche) d'un sport, compressees. Envoyees EN CONTINU (le telechargement demarre tout de suite,
    meme pour des centaines de milliers de ventes ; avant : le fichier entier etait prepare d'abord et rien ne se passait)."""
    import sqlite3
    import zlib
    from flask import Response, stream_with_context
    import base_ventes as _bv
    if not api._est_admin(reel=True):
        abort(403)
    sport = request.args.get("sport") if request.args.get("sport") in ("hockey", "baseball") else "hockey"

    # 18 nov 2026 (« ca a crashe, le site ne repond plus ») : l'export d'un coup tenait le processeur ; la verification de sante
    # de Render (5 s) ne repondait plus et Render a tue le serveur. Maintenant : un seul export a la fois, par petits blocs,
    # avec une pause entre chaque bloc (les autres requetes passent)
    # 19 nov 2026 (Mathieu : « pourquoi ca telecharge pas ? ») : le verrou etait pris AVANT que le flux demarre ; un
    # telechargement annule avant le premier octet ne le rendait jamais et tous les suivants etaient refuses. Maintenant :
    # un export a la fois PAR SPORT, et un export oublie expire seul apres 10 minutes.
    if time.time() - _EXPORT_V.get(sport, 0) < 600:
        return ("Un export est déjà en cours : attends qu'il finisse", 429)
    _EXPORT_V[sport] = time.time()

    def flux():
      try:
        z = zlib.compressobj(4, zlib.DEFLATED, 31)
        yield z.compress(b"titre\tprix\tle\tq\n")
        c = _bv._cx(sport)
        try:
            cur = c.execute("SELECT titre, prix, le, q FROM ventes")
            while True:
                rows = cur.fetchmany(1500)
                if not rows:
                    break
                time.sleep(0.05)
                bloc = "".join("%s\t%s\t%s\t%s\n" % (str(t or "").replace("\t", " ").replace("\n", " "), p_, le or "",
                                                       str(q or "").replace("\t", " ").replace("\n", " ")) for t, p_, le, q in rows)
                out = z.compress(bloc.encode("utf-8"))
                if out:
                    yield out
        except sqlite3.Error:
            pass
        finally:
            c.close()
        yield z.flush()
      finally:
        _EXPORT_V.pop(sport, None)
    return Response(stream_with_context(flux()), mimetype="application/gzip",
                    headers={"Content-Disposition": f'attachment; filename="ventes_{sport}.tsv.gz"', "Cache-Control": "no-store",
                             "X-Accel-Buffering": "no"})


@app.route("/admin/slabiq_donnees.json.gz")
def admin_slabiq_donnees():
    """12 nov 2026 : les donnees du dernier test de prediction SlabIQ (admin seulement, verifie), pour le rejouer ailleurs."""
    from flask import send_file
    import comptes as _c
    if not api._est_admin(reel=True):
        abort(403)
    p = os.path.join(_c.DONNEES, "slabiq_test_donnees.json.gz")
    if not os.path.exists(p):
        return ("Lance d'abord le test de prediction SlabIQ", 404)
    return send_file(p, mimetype="application/gzip", as_attachment=True, download_name="slabiq_donnees.json.gz", max_age=0)


@app.route("/admin/banque_yg.json.gz")
def admin_banque_yg_export():
    """15 nov 2026 : la banque Young Guns (ventes 18 mois, offre du jour, nouvelles) pour l'entrainement de SlabIQ (admin)."""
    from flask import Response as _R
    if not api._est_admin(reel=True):
        abort(403)
    import banque_yg
    b, nom = banque_yg.exporter()
    return _R(b, mimetype="application/gzip", headers={"Content-Disposition": f"attachment; filename={nom}", "Cache-Control": "no-store"})


@app.route("/admin/sauvegarde.zip")
def admin_sauvegarde_zip():
    """12 nov 2026 (liste du lancement : « une sauvegarde hors de Render chaque semaine ») : toutes les donnees du serveur
    (comptes, inventaires, photos, ventes, modele SlabIQ) en un .zip, pour l'admin seulement (verifie, jamais en vue
    simulee). Les caches qui se refont seuls sont laisses de cote. Le fichier est ecrit a part, envoye, puis efface."""
    import tempfile
    from flask import send_file
    if not api._est_admin(reel=True):
        abort(403)
    import sauvegarde                          # 13 nov 2026 : le meme .zip que la sauvegarde de nuit (SQLite coherent)
    taille = sauvegarde.taille_donnees()
    libre = shutil.disk_usage(tempfile.gettempdir()).free
    if libre < taille * 1.1 + 200e6:
        return ("Pas assez d'espace libre pour la sauvegarde (%d Mo de donnees, %d Mo libres)" % (taille // 1e6, libre // 1e6), 507)
    tmp = tempfile.NamedTemporaryFile(prefix="slabcoach_", suffix=".zip", delete=False)
    tmp.close()
    sauvegarde.faire_zip(tmp.name)
    nom = "slabcoach_sauvegarde_" + time.strftime("%Y-%m-%d") + ".zip"
    f = open(tmp.name, "rb")
    rep = send_file(f, mimetype="application/zip", as_attachment=True, download_name=nom, max_age=0)
    try:
        os.remove(tmp.name)
    except OSError:
        def _effacer():
            try:
                f.close()
                os.remove(tmp.name)
            except OSError:
                pass
        rep.call_on_close(_effacer)
    return rep


@app.route("/admin/entrainement.zip")
def admin_entrainement_zip():
    """3 nov 2026 : l'export de la banque d'entrainement (dataset.jsonl + photos), pour l'admin seulement."""
    from flask import send_file
    import entrainement
    if not api._est_admin():
        abort(403)
    ch, nom = entrainement.exporter()
    f = open(ch, "rb")
    rep = send_file(f, mimetype="application/zip", as_attachment=True, download_name=nom, max_age=0)
    try:
        os.remove(ch)                      # Linux (Render) : le fichier ouvert reste lisible, rien ne traine sur le disque
    except OSError:                        # 3 nov 2026 (revue) : Windows refuse : on l'efface apres l'envoi
        def _effacer():
            try:
                f.close()
                os.remove(ch)
            except OSError:
                pass
        rep.call_on_close(_effacer)
    return rep


@app.route("/<path:nom>")
def statiques(nom):
    # 4 nov 2026 (vitesse) : les polices ne changent jamais (30 jours, immuables) ; images et logos : 1 jour (noms fixes,
    # une nouvelle version arrive le lendemain au pire) ; le reste (js, css, html) : revalide a chaque fois (ETag)
    ext = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
    age = 30 * 86400 if ext in ("woff2", "woff", "ttf", "otf") else 86400 if ext in ("svg", "png", "jpg", "jpeg", "webp", "ico", "gif") else None
    rep = send_from_directory(DOSSIER_UI, nom, max_age=age)
    if ext in ("woff2", "woff", "ttf", "otf"):
        rep.headers["Cache-Control"] = "public, max-age=%d, immutable" % (30 * 86400)
    return rep


# multi-comptes : ce qui touche le serveur entier (nos cles, l'environnement, les avis) n'est pas aux clients
_RESERVEES_SERVEUR = {"ebay_cles_sauver", "ebay_environnement", "ebay_avis_regler", "ebay_avis_jeton", "valeurs_maj"}
# 27 oct 2026 (revue de securite) : sur le PC (sans code d'acces), un autre appareil du meme wifi peut LIRE l'app mais
# pas ecrire sur eBay, ni toucher aux cles : ces gestes restent sur le PC lui-meme (ou avec LOCKERROOM_CODE).
_ECRITURES_EBAY = {"ebay_publier", "annonce_publier", "ebay_changer_prix", "ebay_miser", "ebay_cles_sauver", "ebay_avis_regler",
                   "ebay_avis_jeton", "ebay_deconnecter", "ebay_environnement", "ebay_terminer", "ebay_url_connexion", "ebay_promouvoir",
                   "prix_auto_appliquer", "prix_auto_regler", "offres_envoyer", "ebay_prix_lot", "annonce_reviser", "watch_vers_ebay", "annonce_promotion",
                   "cartes_retirer"}


# 8 nov 2026 (Mathieu : « je veux que l'app soit ultra securisee ») : un rythme maximum par compte (et par adresse sans
# compte) sur l'API : un script ou un compte vole ne peut pas marteler le serveur, vider les quotas partages (eBay,
# SoldComps, IA) ni ralentir les autres. Les gestes couteux ont leur propre plafond, plus bas. Bien au-dessus d'un usage
# normal (l'ouverture de l'app fait une trentaine d'appels).
_RYTHME_MAX = int(os.environ.get("LR_API_PAR_MIN") or 300)
_RYTHME_LOURD_MAX = int(os.environ.get("LR_API_LOURD_PAR_MIN") or 40)
_LOURDS = {"photo_identifier", "photos_trier", "paires_verifier", "lot_soumettre", "lot_relancer", "scan_decouper", "annonce_detail", "valeur_carte", "carte_gradations", "annonce_preparer", "carte_comps", "joueur_fiche",
           "deals_pourquoi", "ebay_publier", "annonce_publier", "cartes_retirer", "serie_programmer", "ebay_prix_lot", "offres_envoyer",
           "carte_photos_studio", "carte_etat", "demande_envoyer", "code_appareil", "ebay_jeton_lier", "connexion_jeton_lier",
           "sante_rafraichir", "alertes_verifier", "alarmes_verifier", "ebay_synchroniser", "importer_annonces_ebay", "importer_ventes_ebay", "radar_chercher", "deals_encans_rafraichir"}
# 12 nov 2026 (revue de securite) : des methodes publiques de l'Api servent au serveur lui-meme, jamais a l'ecran
_INTERNES = {"chemin_db", "sport_de"}
_RYTHME = {}
_RYTHME_VERROU = threading.Lock()


def _rythme_ok(nom):
    import collections
    qui = comptes.courant() or ("ip:" + _ip())
    m = time.time()
    with _RYTHME_VERROU:
        if len(_RYTHME) > 20000:                               # menage : les cles silencieuses depuis 2 min
            for k in [k for k, q in _RYTHME.items() if not q or m - q[-1] > 120]:
                _RYTHME.pop(k, None)
        ok = True
        for k, lim in (((qui, "*"), _RYTHME_MAX),) + ((((qui, "lourd"), _RYTHME_LOURD_MAX),) if nom in _LOURDS else ()):
            q = _RYTHME.setdefault(k, collections.deque())
            while q and m - q[0] > 60:
                q.popleft()
            if len(q) >= lim:
                ok = False
        if ok:
            _RYTHME[(qui, "*")].append(m)
            if nom in _LOURDS:
                _RYTHME[(qui, "lourd")].append(m)
    return ok


def _hote_local_ok():
    """3 nov 2026 (revue de securite) : sur le PC, l'API ne repond qu'a une adresse de la machine ou du reseau local
    (contre le « DNS rebinding » : un site qui se fait passer pour 127.0.0.1)."""
    import ipaddress
    h = (request.host or "").rsplit(":", 1)[0].strip("[]").lower()
    if h in ("localhost", "127.0.0.1", "::1") or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        import socket
        return h in {socket.gethostname().lower(), socket.getfqdn().lower(), socket.gethostname().lower() + ".local"}


# 21 nov 2026 (vitesse) : le journal montre les MEMES lectures lancees 2 ou 3 fois au meme instant par le meme ecran
# (inventaire_scores x3 : 53, 83 et 110 s ; inventaire_tableaux x3 ; admin_resume x2...). Chacune refaisait tout le calcul et
# elles se ralentissaient entre elles. Maintenant : une seule calcule, les autres attendent SA reponse. Seulement pour des
# lectures, seulement entre appels identiques de la MEME session (memes temoins, meme appareil) : rien ne change au resultat.
_PARTAGEABLES = frozenset("""inventaire_scores inventaire_tableaux inventaire_liste analyse_break accueil acheteur_accueil mes_deals
deals_liste admin_resume budget_etat catalogue_liste astuces astuces_baseball watch_liste accueil_live conseils quoi_de_neuf
accueil_progres joueur_fiche tendance_joueur produits_liste bilan reglages_lire collection collection_sets admin_ceo
baseball_statut baseball_joueur consignataires_liste forfait tendances_iq""".split())
_VOLS = {}
_VOLS_VERROU = threading.Lock()


def _appel_partage(nom, args, m):
    if nom not in _PARTAGEABLES:
        return m(*args)
    try:
        import hashlib
        qui = hashlib.sha256(((request.headers.get("Cookie") or "") + "|" + (request.headers.get("User-Agent") or "")).encode()).hexdigest()
        cle = (comptes.courant(), qui, nom, json.dumps(args, sort_keys=True, default=str))
    except Exception:
        return m(*args)
    with _VOLS_VERROU:
        v = _VOLS.get(cle)
        chef = v is None
        if chef:
            v = _VOLS[cle] = {"ev": threading.Event(), "res": None, "ok": False}
    if not chef:
        if v["ev"].wait(100) and v["ok"]:
            return v["res"]
        return m(*args)                      # le premier a echoue ou tarde trop : ce fil fait son propre calcul
    try:
        v["res"] = m(*args)
        v["ok"] = True
        return v["res"]
    finally:
        with _VOLS_VERROU:
            _VOLS.pop(cle, None)
        v["ev"].set()


@app.route("/api/<nom>", methods=["POST"])
def dispatcher(nom):
    if nom.startswith("_") or nom in _INTERNES:
        return jsonify({"erreur": "méthode non autorisée"}), 403
    o = request.headers.get("Origin")
    if o:                                    # 27 oct 2026 : appels venus d'un autre site refuses (en plus de SameSite)
        import urllib.parse
        # 3 nov 2026 (revue de securite) : « Origin: null » (iframe isolee, page locale) aussi refuse
        if o == "null" or urllib.parse.urlparse(o).netloc.lower() != request.host.lower():
            return jsonify({"erreur": "Origine refusée"}), 403
    # 3 nov 2026 (revue) : du JSON seulement (un formulaire d'un autre site ne peut pas l'envoyer sans permission du navigateur)
    if request.mimetype != "application/json":
        return jsonify({"erreur": "Requête refusée"}), 415
    if not comptes.MULTI and not _hote_local_ok():
        return jsonify({"erreur": "Hôte refusé"}), 403
    if comptes.MULTI and nom in _RESERVEES_SERVEUR:
        return jsonify({"erreur": "Réglage du serveur : non modifiable ici"}), 403
    if not comptes.MULTI and not CODE_ACCES and nom in _ECRITURES_EBAY and request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"erreur": "Sur un autre appareil, ajoute un code d’accès (LOCKERROOM_CODE) pour écrire sur eBay"}), 403
    m = getattr(api, nom, None)
    if m is None or not callable(m):
        return jsonify({"erreur": f"méthode inconnue : {nom}"}), 404
    if comptes.MULTI and not _rythme_ok(nom):
        return jsonify({"erreur": "Trop de demandes d’un coup : attends une minute"}), 429
    args = request.get_json(silent=True)
    if args is None:
        args = []
    if not isinstance(args, list):
        args = [args]
    try:
        try:                                 # 9 nov 2026 : l'activite anonyme (le nom de la fonction, jamais ses donnees)
            import activite
            activite.noter_api(nom, comptes.courant())
        except Exception:
            pass
        res = _appel_partage(nom, args, m)
        if nom == "ebay_url_connexion" and isinstance(res, dict) and res.get("url"):
            return _lier_navigateur(jsonify(res), res["url"])
        return jsonify(res)
    except Exception as e:  # l'ecran affiche l'erreur dans un toast
        try:
            import admin
            admin.noter_erreur("api " + nom, e)
        except Exception:
            pass
        app.logger.exception("Erreur API %s", nom)
        # 4 nov 2026 (revue) : sur le PC aussi, un message propre a l'ecran (le detail : la console et Admin > Erreurs)
        if not HEBERGE and os.environ.get("LR_DEBUG"):
            return jsonify({"erreur": f"{type(e).__name__} : {e}"}), 500
        return jsonify({"erreur": "Erreur du serveur : réessaie dans un instant"}), 500


# -- redemarrage automatique quand le code change (la boucle du .bat relance) --
def _empreinte():
    fichiers = [os.path.join(DOSSIER, f) for f in os.listdir(DOSSIER) if f.endswith(".py")]
    return tuple(sorted((f, os.path.getmtime(f)) for f in fichiers))


def _surveiller():
    depart = _empreinte()
    while True:
        time.sleep(5)
        try:
            if _empreinte() != depart:
                print("Code mis a jour - redemarrage...", flush=True)
                time.sleep(1)
                os._exit(3)          # code 3 : Lancer_LockerRoom.bat relance tout seul
        except Exception:
            pass


def _valeurs_auto():
    """Valeur des joueurs (algo SlabCoach) : recalculee au demarrage si elle a
    plus de 20 h, puis verifiee chaque heure. Prototype : la source est le
    dossier de Hall of Cardz sur ce PC (lecture seule) ; sans source, les
    valeurs deja la (ou celles par defaut) restent."""
    import valeurs
    # 3 nov 2026 (Mathieu : « c'est tellement long a charger l'app apres une mise a jour ») : apres un deploiement, les
    # 3 premieres minutes servent l'app (les gens rouvrent tous l'app en meme temps) ; les gros calculs attendent
    time.sleep(CALME_DEMARRAGE_S)
    while True:
        try:
            age = time.time() - os.path.getmtime(valeurs.CHEMIN) if os.path.exists(valeurs.CHEMIN) else 1e9
            if age > 20 * 3600:                 # 27 oct 2026 : depuis les ventes SoldComps (plus Hall of Cardz)
                print("Mise a jour de la valeur des joueurs...", flush=True)
                r = api.valeurs_maj()
                print("  ", {k: r.get(k) for k in ("ok", "joueurs", "ventes")}, flush=True)
        except Exception as e:
            print("Valeur des joueurs : " + str(e), flush=True)
        try:                                    # 23 oct 2026 - nouvelles de l'accueil (toutes les 2 h)
            import nouvelles
            nouvelles.rafraichir_si_besoin()
        except Exception as e:
            print("Nouvelles : " + str(e), flush=True)
        try:                                    # 24 oct 2026 - deals pour les acheteurs (chasseur partage, chaque heure)
            import deals
            deals.chasser_si_besoin()
        except Exception as e:
            print("Deals : " + str(e), flush=True)
        try:                                    # 24 oct 2026 - nouveaux produits sur eBay (chaque semaine)
            import nouveaux_produits
            nouveaux_produits.detecter_si_besoin()
        except Exception as e:
            print("Nouveaux produits : " + str(e), flush=True)
        try:                                    # 25 oct 2026 - nouvelles checklists GTS (gogts.net, chaque jour)
            import nouveaux_produits
            nouveaux_produits.gts_si_besoin()
        except Exception as e:
            print("Checklists GTS : " + str(e), flush=True)
        try:                                    # 25 oct 2026 - les vraies ventes de la communaute (chaque jour)
            import ventes_communaute
            ventes_communaute.rafraichir_si_besoin()
        except Exception as e:
            print("Ventes communaute : " + str(e), flush=True)
        try:                                    # 26 oct 2026 - la base des ventes (tendances) : quelques recherches par heure
            import base_ventes
            base_ventes.enrichir_si_besoin()
        except Exception as e:
            print("Base des ventes : " + str(e), flush=True)
        try:                                    # 22 nov 2026 - le mega test : 3 ans de ventes de la meme carte (CompSniper)
            import mega_test
            mega_test.continuer_si_besoin()
        except Exception as e:
            print("Mega test : " + repr(e)[:160], flush=True)
        try:                                    # 10 nov 2026 - le banc de validation (backtest valeur, deals, tendance ; 1 fois/jour)
            import banc
            banc.passe_si_besoin()
        except Exception as e:
            print("Banc de validation : " + str(e), flush=True)
        try:                                    # 10 nov 2026 - la demande des joueurs sans ventes eBay (LNH, Wikipedia) + le labo
            import demande_legale
            demande_legale.passe_si_besoin()
        except Exception as e:
            print("Demande legale : " + str(e), flush=True)
        try:                                    # 10 nov 2026 - Highlightly : un essai par jour (cle, quota, donnees) pour l'admin
            import highlightly
            t_ = highlightly.statut().get("test") or {}
            if highlightly.actif() and time.time() - (t_.get("le") or 0) > 86400:
                highlightly.test()
        except Exception as e:
            print("Highlightly : " + str(e), flush=True)
        try:                                    # 10 nov 2026 - l'Indice joueur de la semaine (stats Highlightly + publiques)
            import indice_joueurs
            indice_joueurs.passe_si_besoin()
        except Exception as e:
            print("Indice joueurs : " + str(e), flush=True)
        try:                                    # 23 nov 2026 - le signal par joueur (admin) : les matchs du soir, le journal, la note
            import signal_joueurs
            signal_joueurs.passe_si_besoin()
        except Exception as e:
            print("Signal joueurs : " + str(e), flush=True)
        try:                                    # 11 nov 2026 - Score SlabCoach : la memoire du marche (chaque jour), reappris (chaque semaine)
            import score_appris
            r_sa = score_appris.taches_si_besoin()
            if r_sa.get("reapprendre") or (r_sa.get("jour") or {}).get("ajoutees"):
                print("Score SlabCoach : " + json.dumps(r_sa)[:300], flush=True)
        except Exception as e:
            print("Score SlabCoach (reappris) : " + str(e), flush=True)
        try:                                    # 13 nov 2026 - le produit de chaque code de carte (#BDB- -> Black Diamond), 1 fois/jour
            import base_ventes as _bv_codes
            n_codes = _bv_codes.apprendre_codes_si_besoin()
            if n_codes:
                print("Codes de cartes appris :", n_codes, flush=True)
        except Exception as e:
            print("Codes de cartes : " + str(e), flush=True)
        try:                                    # 13 nov 2026 - la sauvegarde de nuit vers Cloudflare R2 (3 h a 6 h, Montreal)
            import sauvegarde
            if sauvegarde.passe_si_besoin():
                print("Sauvegarde R2 lancee", flush=True)
        except Exception as e:
            print("Sauvegarde R2 : " + str(e), flush=True)
        try:                                    # 12 nov 2026 - les types de cartes qui comptent (nos ventes, 1 fois/semaine)
            import types_cartes
            if types_cartes.passe_si_besoin():
                print("Types de cartes : passe lancee", flush=True)
        except Exception as e:
            print("Types de cartes : " + str(e), flush=True)
        try:                                    # 16 nov 2026 - deux collectionneurs, avec et sans SlabIQ (1 fois/semaine)
            import simulation_iq
            if simulation_iq.passe_si_besoin():
                print("Simulation SlabIQ : passe lancee", flush=True)
        except Exception as e:
            print("Simulation SlabIQ : " + str(e), flush=True)
        try:                                    # 16 nov 2026 - SlabIQ contre l'expert : la boucle (1 fois/semaine)
            import slabiq_expert
            if slabiq_expert.passe_si_besoin():
                print("SlabIQ expert : boucle lancee", flush=True)
        except Exception as e:
            print("SlabIQ expert : " + str(e), flush=True)
        try:                                    # 17 nov 2026 - la cote marche des joueurs (moyenne 90 j, liquidite ; 1 fois/semaine)
            import cote_marche
            if cote_marche.passe_si_besoin():
                print("Cote marche : passe lancee", flush=True)
            cote_marche.balayer_si_besoin()     # 17 nov 2026 : chaque joueur mesure chez SoldComps, une fois par semaine
            cote_marche.blitz_reprendre_si_besoin()   # 18 nov 2026 : un push redemarre le serveur : le blitz reprend
            import deals as _dl_                # 17 nov 2026 : les valeurs « estimees » rejugees avec les archives (Misa PMG)
            threading.Thread(target=_dl_.reestimer_approx, daemon=True, name="reestimer-approx").start()
        except Exception as e:
            print("Cote marche : " + str(e), flush=True)
        try:                                    # 18 nov 2026 - le calendrier des sorties (nouvelles « nouveau produit »), toutes les 12 h
            import sorties
            sorties.rafraichir_si_besoin()
        except Exception as e:
            print("Sorties : " + str(e), flush=True)
        try:                                    # 19 nov 2026 - la chance de series de chaque equipe (12 h) et les sets cultes (semaine)
            import series as _se_, sets_cultes as _sc_
            _se_.rafraichir_si_besoin()
            _sc_.recalculer_si_besoin()
        except Exception as e:
            print("Series / sets cultes : " + str(e), flush=True)
        try:                                    # 18 nov 2026 - l'audit Pro : les annonces Pro contre leurs comps, en coulisse (1 fois/semaine)
            if lockerroom.Api.audit_pro_si_besoin():
                print("Audit Pro : passe lancee", flush=True)
        except Exception as e:
            print("Audit Pro : " + str(e), flush=True)
        try:                                    # 17 nov 2026 - la validation du bareme par le marche + sa boucle (1 fois/semaine)
            import validation_iq
            if validation_iq.passe_si_besoin():
                print("Validation SlabIQ : passe lancee", flush=True)
        except Exception as e:
            print("Validation SlabIQ : " + str(e), flush=True)
        try:                                    # 16 nov 2026 - les joueurs cles et leur marche bas (1 fois/jour, verifie)
            import marche_cles
            if marche_cles.passe_si_besoin():
                print("Marche des joueurs cles : passe lancee", flush=True)
        except Exception as e:
            print("Marche des joueurs cles : " + str(e), flush=True)
        try:                                    # 21 nov 2026 - a acheter / a vendre : le marche de chaque joueur (1 fois/jour, verifie)
            import marche_joueurs
            if marche_joueurs.passe_si_besoin():
                print("Marche des joueurs : passe lancee", flush=True)
        except Exception as e:
            print("Marche des joueurs : " + str(e), flush=True)
        try:                                    # 12 nov 2026 - SlabIQ : le test et le journal en direct (1 fois/semaine)
            import slabiq_test
            if slabiq_test.passe_si_besoin():
                print("SlabIQ : test et journal en direct lances", flush=True)
        except Exception as e:
            print("SlabIQ journal : " + str(e), flush=True)
        try:                                    # 10 nov 2026 - TheCardAPI : les ventes de hockey d'hier -> nos archives (1 fois/jour)
            import thecardapi
            thecardapi.moissonner_si_besoin()
        except Exception as e:
            print("TheCardAPI moisson : " + str(e), flush=True)
        try:                                    # 13 nov 2026 - le baseball : la liste MLB + les fiches des joueurs qui se vendent
            import mlb
            mlb.passe_si_besoin()
        except Exception as e:
            print("MLB : " + str(e), flush=True)
        try:                                    # 27 oct 2026 - population PSA des fiches connues (PSA_TENDANCES=1, 1 fois/jour)
            import psa
            n_psa = psa.rafraichir_si_besoin()
            if n_psa:
                print("Population PSA :", n_psa, "fiches", flush=True)
        except Exception as e:
            print("Population PSA : " + str(e), flush=True)
        try:                                    # 25 oct 2026 - demandes pas encore triees par l'agent
            import demandes
            demandes.trier_en_attente()
        except Exception as e:
            print("Demandes : " + str(e), flush=True)
        time.sleep(3600)


def _watch_boucle():
    """29 oct 2026 (Mathieu : watchlist, « vraiment proche de finir, il faut qu'il place son enchere ») : toutes les 5 min,
    les encans suivis qui finissent dans 75 min, relus sur eBay ; l'alerte part 15 min avant la fin."""
    import comptes as _c
    time.sleep(90)
    while True:
        try:                                    # 31 oct 2026 : les deals qui finissent dans 2 h, relus sur eBay (prix du moment)
            import deals
            rf = deals.fin_proche_si_besoin()
            if rf and rf.get("sortis"):
                print("Deals (fin proche) :", rf, flush=True)
            rp = deals.prix_fixes_si_besoin()            # 3 nov 2026 : les prix fixes aussi, aux 20 min
            if rp and rp.get("sortis"):
                print("Deals (prix fixes) :", rp, flush=True)
        except Exception as e:
            print("Deals (fin proche) : " + str(e), flush=True)
        for cid in (_c.lister() if _c.MULTI else [None]):
            with _c.utiliser(cid):
                try:
                    r = api.watch_proches()
                    if r.get("envoyees"):
                        print("Watchlist :", cid or "", r["envoyees"], flush=True)
                except Exception as e:
                    print("Watchlist : " + str(e), flush=True)
                try:                             # 31 oct 2026 : mes joueurs suivis dans les deals (si coche)
                    rj = api.alarmes_mes_joueurs()
                    if rj.get("envoyees"):
                        print("Mes joueurs :", cid or "", rj["envoyees"], flush=True)
                except Exception as e:
                    print("Mes joueurs : " + str(e), flush=True)
        try:                                     # 13 nov 2026 : pres de la limite de memoire, les memoires de confort videes
            import admin as _adm
            _adm.soupape()
        except Exception as e:
            print("Memoire : " + str(e), flush=True)
        time.sleep(300)


def _ebay_auto():
    """Toutes les heures : annonces et ventes relues (compte connecte), puis prix compares au marche (cles eBay)."""
    import ebay_compte
    time.sleep(60)
    import comptes as _c
    while True:
        try:                                     # 15 nov 2026 : la banque Young Guns, l'offre du jour (une fois par jour, Browse)
            import banque_yg
            n_o = banque_yg.offre_du_jour()
            if n_o:
                print("Banque YG : offre du jour lue pour", n_o, "joueurs", flush=True)
        except Exception as e:
            print("Banque YG (offre) : " + repr(e)[:160], flush=True)
        for cid in (_c.lister() if _c.MULTI else [None]):      # multi : chaque client a tour de role
            with _c.utiliser(cid):
                try:
                    st = ebay_compte.statut()
                    if st.get("connecte"):
                        r = api.ebay_synchroniser(30)
                        print("Synchro eBay :", cid or "", {k: r.get(k) for k in ("ok", "annonces", "ventes", "erreur")}, flush=True)
                    try:                         # 9 nov 2026 : le % des frais eBay suit les frais reels de ses ventes
                        rf = api.frais_calibrer()
                        if rf.get("change"):
                            print("Frais eBay :", cid or "", rf, flush=True)
                    except Exception as e:
                        print("Frais eBay : " + str(e), flush=True)
                    try:                         # 26 oct 2026 : les alertes de prix de chaque compte
                        ra = api.alertes_verifier()
                        if ra.get("nouvelles"):
                            print("Alertes :", cid or "", ra, flush=True)
                    except Exception as e:
                        print("Alertes : " + str(e), flush=True)
                    try:                         # 29 oct 2026 : les alertes cochees (deals, encans, joueur en feu, offres, vendu)
                        rm = api.alarmes_verifier()
                        if rm.get("envoyees"):
                            print("Alarmes :", cid or "", rm["envoyees"], flush=True)
                    except Exception as e:
                        print("Alarmes : " + str(e), flush=True)
                    if st.get("cles_ok") and st.get("connecte" if _c.MULTI else "cles_ok"):
                        r = api.sante_rafraichir(40)
                        print("Sante :", cid or "", {k: r.get(k) for k in ("evaluees", "rachats", "erreur")}, flush=True)
                        try:                     # 28 oct 2026 : acheteurs interesses (1 appel eBay par heure, pour l'accueil)
                            import ebay_offres
                            ebay_offres.eligibles(force=True)
                        except Exception as e:
                            print("Offres : " + str(e), flush=True)
                        try:                     # 27 oct 2026 : mode Auto des prix (si le vendeur l'a choisi)
                            rp = api.prix_auto_appliquer()
                            if rp.get("faits") or rp.get("erreur"):
                                print("Prix auto :", cid or "", rp, flush=True)
                        except Exception as e:
                            print("Prix auto : " + str(e), flush=True)
                    if cid == (_c.lister() if _c.MULTI else [None])[0]:     # 27 oct 2026 : le pouls du hobby (commun a tous)
                        try:
                            import pouls
                            pouls.rafraichir_si_besoin()
                        except Exception as e:
                            print("Pouls : " + str(e), flush=True)
                        try:                     # 9 nov 2026 : veille eBay (frais, regles, douanes), une fois par jour
                            import veille_ebay
                            rv = veille_ebay.rafraichir_si_besoin(_alerter_admins)
                            if rv:
                                print("Veille eBay :", rv, flush=True)
                        except Exception as e:
                            print("Veille eBay : " + str(e), flush=True)
                        try:                     # 28 oct 2026 : la forme des joueurs des tendances (LNH)
                            import nhl
                            nhl.rafraichir_si_besoin()
                        except Exception as e:
                            print("LNH : " + str(e), flush=True)
                except Exception as e:
                    print("Synchro eBay : " + str(e), flush=True)
        time.sleep(3600)


def _alerter_admins(titre, texte):
    """9 nov 2026 : une notification aux iPhone des comptes admin (veille eBay)."""
    import comptes as _c
    for cid in (_c.lister() if _c.MULTI else [None]):
        with _c.utiliser(cid):
            try:
                if api._est_admin_compte():
                    api._push(titre, texte, {"lien": "#admin/serveur"})
            except Exception as e:
                print("Alerte admin : " + str(e), flush=True)


def _verifier_secrets():
    """27 oct 2026 (revue) : en ligne, les jetons eBay doivent etre chiffres. On le dit fort dans le journal de Render."""
    if comptes.MULTI and not os.environ.get("LOCKERROOM_CLE"):
        app.logger.error("ATTENTION : LOCKERROOM_CLE absente -> jetons eBay NON chiffres sur le disque. Ajoute-la dans Render.")
        print("ATTENTION : LOCKERROOM_CLE absente : jetons eBay non chiffres", flush=True)


def demarrer_taches():
    _verifier_secrets()
    try:                                     # 9 nov 2026 : les frais d'importation appris la veille, des le demarrage
        import veille_ebay
        veille_ebay.appliquer()
    except Exception as e:
        print("Veille eBay : " + str(e), flush=True)
    threading.Thread(target=_valeurs_auto, daemon=True).start()
    threading.Thread(target=_ebay_auto, daemon=True).start()
    threading.Thread(target=_watch_boucle, daemon=True, name="watchlist").start()
    threading.Thread(target=_revalider_deals, daemon=True, name="revalider").start()
    _CHAUD["pid"] = os.getpid()               # ce processus-ci se rechauffe (un worker copie du maitre le fera pour lui-meme)
    threading.Thread(target=_rechauffer, daemon=True, name="rechauffer").start()
    threading.Thread(target=_reprendre_banque_yg, daemon=True, name="banque-yg-reprise").start()
    threading.Thread(target=_moment_yg_boucle, daemon=True, name="moment-yg").start()


def _reprendre_banque_yg():
    """15 nov 2026 : une collecte de la banque Young Guns coupee par un redemarrage (deploiement) reprend toute seule."""
    time.sleep(CALME_DEMARRAGE_S + 30)
    try:
        import banque_yg
        banque_yg.reprendre_si_besoin()
    except Exception as e:
        print("Banque YG (reprise) : " + repr(e)[:160], flush=True)
    try:                                         # 22 nov 2026 : le mega test reprend lui aussi apres un redemarrage
        time.sleep(60)
        import mega_test
        mega_test.continuer_si_besoin()
    except Exception as e:
        print("Mega test (reprise) : " + repr(e)[:160], flush=True)


def _valeur_actuelle(titre):
    """La valeur d'une carte aujourd'hui (mediane de ses ventes des 30 derniers jours, sans aucun appel) ou None."""
    import statistics
    import vendues
    vc = vendues.memes_cache(titre, n=40, age_max=30 * 86400) or {}
    lim = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    pts = [float(b) for a, b in (vc.get("points") or []) if b and str(a or "")[:10] >= lim]
    return round(statistics.median(pts), 2) if len(pts) >= 3 else None


def moment_yg_tour():
    """Une passe : la mise a jour de la semaine (ventes recentes), l'iteration de la semaine (SlabIQ remesure ses regles et
    essaie mieux), les etats du jour et la verification du journal en direct. -> resume."""
    import banque_yg
    import moment_yg
    out = {}
    if banque_yg.ETAT["en_cours"]:
        return {"attente": "collecte en cours"}
    r = banque_yg.rafraichir_si_besoin()
    if r:
        out["mise_a_jour"] = {k: r.get(k) for k in ("credits", "ventes", "requetes", "fini", "erreur")}
    try:
        der = float(banque_yg._meta("itere_le") or 0)
    except ValueError:
        der = 0.0
    if time.time() - der >= 7 * 86400 or banque_yg._meta("moment_v") != moment_yg.VERSION:
        it = moment_yg.iterer_maintenant()
        banque_yg._meta("itere_le", time.time())
        banque_yg._meta("moment_v", moment_yg.VERSION)
        out["iteration"] = {"change": it["change"], "feu_vert": (it["validation"] or {}).get("feu_vert")}
    elif banque_yg._meta("moment_jour") != date.today().isoformat():
        out["etats"] = moment_yg.calculer_jour()
    banque_yg._meta("moment_jour", date.today().isoformat())
    out["journal_verifies"] = moment_yg.journal_verifier(_valeur_actuelle)
    # 16 nov 2026 (Mathieu : « on doit etre bullet proof si on se fait challenger ») : chaque jour, ce que SlabCoach dit est
    # fige, enchaine et horodate AVANT de connaitre la suite (voir preuve.py)
    try:
        import preuve
        p = preuve.tour()
        if p.get("fige"):
            out["preuve"] = p["fige"]
    except Exception as e:
        print("Preuve : " + repr(e)[:200], flush=True)
    return out


def _moment_yg_boucle():
    """15 nov 2026 (Mathieu : « on ne doit jamais arreter d'iterer et d'ameliorer SlabIQ ») : toutes les heures, une passe
    (la plupart ne font rien : chaque etape a son rythme, jour ou semaine)."""
    time.sleep(CALME_DEMARRAGE_S + 90)
    while True:
        try:
            r = moment_yg_tour()
            if r and any(k in r for k in ("mise_a_jour", "iteration", "etats")):
                print("Moment YG :", r, flush=True)
        except Exception as e:
            print("Moment YG : " + repr(e)[:200], flush=True)
        time.sleep(3600)


def _rechauffer():
    """4 nov 2026 (vitesse) : apres un deploiement, le premier ecran Deals (1,5 s) et le catalogue (1 s) payaient le calcul
    a froid. 20 s apres le demarrage, doucement en fond : le jugement des deals et la valeur des boites du catalogue.
    20 nov 2026 : travail du serveur, sans compte (comptes.systeme : la racine est permise, le reste est refuse)."""
    with comptes.systeme():
        _rechauffer0()


# 21 nov 2026 (2e suivi vitesse) : LA cause des minutes lentes apres chaque mise a jour. Sur Render, gunicorn precharge l'app
# (« --preload » vient de l'environnement de Render) : server.py est importe dans le processus MAITRE, puis le worker qui
# repond aux clients en est une copie SANS les fils lances a l'import. Tout le travail de fond (chasseur, valeurs, rechauffage)
# roule donc dans le maitre : ce qu'il ecrit sur le disque sert a tous, mais ce qu'il charge en MEMOIRE (modele SlabIQ,
# catalogue, jugement des deals) ne sert a personne, et le premier client du worker payait tout (inventaire 98 s). Preuve :
# « Gardien des piles : actif (pid 43) » imprime par le maitre, avant « Booting worker with pid: 76 ».
# Maintenant : le worker se rechauffe lui-meme, lance par sa premiere requete (la verification de sante de Render arrive
# quelques secondes apres le demarrage, avant les clients). Rien d'autre ne bouge : le travail de fond reste dans le maitre.
_CHAUD = {"pid": None}
_CHAUD_VERROU = threading.Lock()


def _rechauffer_worker():
    try:
        with comptes.systeme():
            t0 = time.time()
            import score_modele
            import demande_legale
            import catalogue as _cat
            score_modele.charger()
            demande_legale.presence_catalogue()
            _cat.liste()
            score_modele.scores(["2024-25 Upper Deck Young Guns Macklin Celebrini #451 RC"], [None])
            print(f"Rechauffage du worker (pid {os.getpid()}) : modele et catalogue prets en {time.time() - t0:.1f} s", flush=True)
            time.sleep(10)
            import deals
            for i, g in enumerate((deals.lire_vite() or {}).get("deals") or []):
                if i % 20 == 0:
                    _attendre_calme(10)          # jamais pendant qu'un client attend une reponse
                deals.valide(g)
            api.catalogue_liste()
            print(f"Rechauffage du worker (pid {os.getpid()}) : deals et catalogue prets", flush=True)
            # 21 nov 2026 (suivi vitesse) : le calcul d'un break est garde 20 min EN MEMOIRE ; le rechauffage des breaks tournait
            # dans le maitre, donc le worker calculait quand meme le premier break demande par un client (jusqu'a 15 s le matin).
            # Les 12 produits les plus recents, doucement (apres 4 min, 20 s entre chaque, jamais pendant qu'un client attend).
            time.sleep(int(os.environ.get("LR_RECHAUFFER_BREAKS_S") or 120) + 120)
            n_b = 0
            for p in sorted(_cat.liste(), key=lambda x: str(x.get("sortie") or ""), reverse=True)[:12]:
                _attendre_calme(30)
                try:
                    api.analyse_break({"produit_id": p["id"], "boites": 1, "mode": "equipes", "cout_boite": 0, "decote": 0,
                                       "prix_demandes": {}, "prix_joueurs": {}, "acheteur": True})
                    n_b += 1
                except Exception as e:
                    print("Rechauffage du worker (break) : " + repr(e)[:120], flush=True)
                time.sleep(20)
            print(f"Rechauffage du worker (pid {os.getpid()}) : {n_b} breaks prets", flush=True)
    except Exception as e:
        print("Rechauffage du worker : " + repr(e)[:200], flush=True)


def _worker_assurer():
    """Le processus qui repond aux clients s'est-il rechauffe ? Sinon (worker copie du maitre), on le lance, une fois."""
    if _CHAUD["pid"] == os.getpid():
        return
    with _CHAUD_VERROU:
        if _CHAUD["pid"] == os.getpid():
            return
        _CHAUD["pid"] = os.getpid()
    threading.Thread(target=_rechauffer_worker, daemon=True, name="rechauffer-worker").start()


def _attendre_calme(maxi=90):
    """Le travail de fond laisse passer les clients : il attend qu'aucune requete de l'app ne roule (au plus maxi secondes)."""
    t0 = time.time()
    while len(_EN_VOL) > 0 and time.time() - t0 < maxi:
        time.sleep(0.5)


def _rechauffer0():
    # 21 nov 2026 (vitesse) : le modele SlabIQ, le catalogue et la presence au catalogue etaient charges par le PREMIER client
    # apres une mise a jour (4,5 s seul ; 50 a 110 s quand plusieurs ecrans le demandaient en meme temps). Maintenant : charges
    # 3 s apres le demarrage, avant que les clients reviennent.
    time.sleep(3)
    try:
        import score_modele
        import demande_legale
        import catalogue as _cat
        score_modele.charger()
        demande_legale.presence_catalogue()
        _cat.liste()
        score_modele.scores(["2024-25 Upper Deck Young Guns Macklin Celebrini #451 RC"], [None])
    except Exception as e:
        print("Rechauffage (modele) : " + repr(e)[:160], flush=True)
    time.sleep(max(0, int(os.environ.get("LR_RECHAUFFER_S") or 20) - 3))
    try:
        import deals
        for i, g in enumerate((deals.lire_vite() or {}).get("deals") or []):
            deals.valide(g)
            if i % 20 == 0:
                time.sleep(0.02)                 # laisse passer les requetes de l'app
        api.catalogue_liste()
    except Exception as e:
        print("Rechauffage : " + repr(e), flush=True)
    # 15 nov 2026 (Mathieu : « la page breaks est excessivement longue a loader ») : le premier calcul d'un produit faisait
    # passer ses ~5 000 cartes dans le modele SlabIQ (5-11 s) ; apres un deploiement, chaque produit est calcule une fois en
    # fond, doucement (le score de chaque joueur est garde 6 h, le calcul entier 20 min)
    # 15 nov 2026 (« ca fait 2 min que ca load ») : le rechauffage des breaks prenait le processeur juste apres un deploiement
    # (27 produits d'affilee) et ralentissait tout le monde : seulement les 8 produits les plus recents, doucement (20 s entre
    # chaque), et pas avant 2 min
    try:
        import catalogue
        time.sleep(int(os.environ.get("LR_RECHAUFFER_BREAKS_S") or 120))
        # 16 nov 2026 : les memes arguments que l'ecran de l'acheteur (meme cle de cache) ; tous les produits, du plus recent
        # au plus vieux : le SlabIQ de leurs joueurs est garde sur le disque, seul le tout premier passage coute
        for p in sorted(catalogue.liste(), key=lambda x: str(x.get("sortie") or ""), reverse=True):
            _attendre_calme()                    # 21 nov 2026 : jamais pendant qu'un client attend une reponse
            try:
                api.analyse_break({"produit_id": p["id"], "boites": 1, "mode": "equipes", "cout_boite": 0, "decote": 0,
                                   "prix_demandes": {}, "prix_joueurs": {}, "acheteur": True})
            except Exception as e:
                print("Rechauffage (break) : " + repr(e)[:120], flush=True)
            time.sleep(20)
    except Exception as e:
        print("Rechauffage (breaks) : " + repr(e), flush=True)


CALME_DEMARRAGE_S = int(os.environ.get("LR_CALME_DEMARRAGE_S") or 180)


def _revalider_deals():
    """31 oct 2026 : une fois apres une mise a jour des regles de comparables (deals.revalider_produits). Puis
    rechauffe : au demarrage (chaque deploiement), les deals sont juges et les encans suivis valorises en arriere-plan,
    pour que le premier ecran Deals de la journee s'ouvre aussi vite que les suivants (serveur Standard : on a la marge)."""
    time.sleep(CALME_DEMARRAGE_S + 30)
    try:
        import deals
        deals.revalider_produits()
        d = deals.lire_vite()
        for i, g in enumerate(d.get("deals") or []):
            deals.valide(g)
            if i % 20 == 0:
                time.sleep(0.02)                 # laisse passer les requetes de l'app
        import lockerroom
        for x in d.get("suivis") or []:
            if not x.get("valeur") and deals.encore_ouvert(x):
                lockerroom.Api._valeur_en_cache(x)
                time.sleep(0.005)
        print("Demarrage : deals et encans suivis prets", flush=True)
    except Exception as e:
        print("Revalidation des deals : " + repr(e), flush=True)


if _TACHES_ICI:
    demarrer_taches()          # gunicorn importe ce fichier : 1 seul worker (voir render.yaml)
if HEBERGE:
    _gardien_assurer()


if __name__ == "__main__":
    if not _prendre_verrou():
        print("SlabCoach tourne deja - tu peux fermer cette fenetre.", flush=True)
        sys.exit(0)
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "<ip-du-pc>"
    print("=" * 56)
    print("SlabCoach - serveur demarre")
    print(f"  Sur ce PC      : http://localhost:{PORT}")
    print(f"  iPhone (wifi)  : http://{ip}:{PORT}")
    print("=" * 56, flush=True)
    threading.Thread(target=_surveiller, daemon=True).start()
    if not HEBERGE:
        demarrer_taches()
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
