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
import threading
import time

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


from flask import Flask, abort, jsonify, request, send_from_directory  # noqa: E402

import lockerroom  # noqa: E402

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
    return Response(_APP_CACHE["brut"], mimetype="text/html", headers={"ETag": _APP_CACHE["etag"], "Cache-Control": "no-cache"})


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

api = lockerroom.Api()

# -- 21 oct 2026 : version hebergee (demo publique) -------------------------------------------
# LOCKERROOM_HEBERGE=1  : serveur de production (gunicorn), pas d'auto-redemarrage
# LOCKERROOM_CODE=...   : code d'acces demande avant d'ouvrir l'app (protege toutes les API)
# LOCKERROOM_SECRET=... : cle de signature du temoin de session (obligatoire si code)
HEBERGE = os.environ.get("LOCKERROOM_HEBERGE") == "1"
CODE_ACCES = os.environ.get("LOCKERROOM_CODE") or ""
app.secret_key = os.environ.get("LOCKERROOM_SECRET") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=HEBERGE)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024        # 23 oct 2026 - 2 photos (devant, dos) par requete
# pages qui restent publiques : break partage, retour et avis eBay, pages legales, icones
_PUBLIQUES = ("/b/", "/api/b/", "/api/ebay_retour", "/ebay/suppression-compte", "/confidentialite", "/conditions",
              "/support", "/robots.txt", "/sitemap.xml", "/logo_sc_", "/syne-800.woff2", "/manrope-", "/barlow-", "/connexion", "/icone", "/favicon", "/manifest.json", "/stripe/webhook", "/apple/notifications")


import comptes  # noqa: E402

_PUBLIQUES_MULTI = _PUBLIQUES + ("/auth/", "/deconnexion", "/demo")


@app.before_request
def _garde():
    from flask import redirect, session
    comptes.activer(None)
    import lockerroom as _lr                       # 26 oct 2026 - requete venue de l'app iPhone ?
    _lr.marquer_ios("LockerRoomiOS" in (request.headers.get("User-Agent") or ""))
    publique = request.path.startswith(_PUBLIQUES_MULTI)
    if CODE_ACCES and not session.get("ok") and not publique:       # demo : code d'acces d'abord
        return (jsonify({"erreur": "Connexion requise"}), 401) if request.path.startswith("/api/") else redirect("/connexion")
    if comptes.MULTI:
        cid = session.get("compte")
        if cid and cid in comptes.lister():
            comptes.activer(cid)                                     # cette requete ne voit que ce compte
        elif request.path == "/" and not CODE_ACCES:
            if "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
                return redirect("/connexion")                        # app iPhone : pas la vitrine (prix du site)
            return _page_vitrine()                                   # 27 oct 2026 : visiteur -> la vitrine
        elif not publique:
            session.pop("compte", None)
            return (jsonify({"erreur": "Connexion requise"}), 401) if request.path.startswith("/api/") else redirect("/connexion")
    return None


@app.route("/auth/ebay")
def auth_ebay():
    """Multi-comptes : UN bouton = inscription + connexion (page officielle d'eBay)."""
    from flask import redirect
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


def _billet(cid, cible, etat):
    """Ouvre la session ici (navigateur normal) ou, pour l'app iPhone, prepare le billet. -> reponse Flask."""
    from flask import redirect, session
    import secrets as _s
    import time as _t
    app_h = (_APP_ETATS.pop(etat, None) or (None,))[0] if etat else None
    for k in [k for k, v in _BILLETS.items() if _t.time() - v[2] > 120]:
        _BILLETS.pop(k, None)
    b = _s.token_urlsafe(32)
    if app_h:
        _BILLETS[b] = (cid, cible, _t.time(), "", app_h)
        dest = SCHEMA_APP + "?b=" + b
        return (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<body style='margin:0;background:#0B0B0E;color:#F4F2EE;font-family:-apple-system,sans-serif;display:grid;place-items:center;height:100vh'>"
                f"<a href='{dest}' style='padding:16px 26px;border-radius:14px;background:#B9BEFF;color:#0E1026;font-weight:700;text-decoration:none'>"
                f"Revenir à SlabCoach</a><script>location.replace({json.dumps(dest)})</script>", 200, {"Content-Type": "text/html; charset=utf-8"})
    if request.method == "GET":
        session.permanent = True
        session["compte"] = cid
        return redirect(cible)
    _BILLETS[b] = (cid, cible, _t.time(), request.cookies.get(_TEMOIN_LIEN) or "", None)
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
    return _lier_navigateur(redirect(u), u)


@app.route("/auth/<fournisseur>/retour", methods=["GET", "POST"])
def auth_tiers_retour(fournisseur):
    """Google revient en GET, Apple en POST (form_post). Compte cree au premier passage."""
    from flask import redirect, session
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
    cid, nouveau = comptes.trouver_ou_creer(fournisseur + ":" + r["sub"], r.get("nom"), fournisseur)
    champs = {"connexion": fournisseur}
    if r.get("courriel"):
        champs["courriel"] = r["courriel"]
    if r.get("jeton_apple"):                 # pour le retirer chez Apple si le compte est supprime (chiffre)
        champs["apple_rt"] = comptes.chiffrer(r["jeton_apple"])
    comptes.maj(cid, **champs)
    # 28 oct 2026 : Apple revient en POST depuis SON site. Safari (et l'app iPhone) n'enregistre pas un temoin
    # SameSite=Lax dans la reponse a un POST venu d'un autre site : la session etait perdue -> boucle vers la connexion.
    # Billet a usage unique (2 min) : une petite page repart chez nous en GET, ou la session s'ouvre (voir _billet).
    return _billet(cid, "/#accueil/" + ("bienvenue" if nouveau else "retour"), v.get("state"))


_BILLETS = {}


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
    cid, cible, _le, lien, app_h = v
    if app_h:                                  # app iPhone : le secret garde par l'app doit correspondre
        import hashlib
        if not hmac.compare_digest(app_h, hashlib.sha256((request.args.get("v") or "").encode()).hexdigest()):
            return redirect("/connexion?erreur=3")
    elif lien and not hmac.compare_digest(lien, request.cookies.get(_TEMOIN_LIEN) or ""):   # meme navigateur seulement
        return redirect("/connexion?erreur=3")
    if cid not in comptes.lister():
        return redirect("/connexion?erreur=3")
    session.permanent = True
    session["compte"] = cid
    r = redirect(cible)
    r.delete_cookie(_TEMOIN_LIEN, path="/")
    return r


# 27 oct 2026 (revue de securite) : codes d'acces et de demo : 8 essais rates par 15 min par adresse, puis on attend.
_ECHECS = {}


def _ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip() if HEBERGE \
        else (request.remote_addr or "")


def _trop_d_essais():
    import time
    m = time.time()
    for k in [k for k, v in _ECHECS.items() if m - v[-1] > 900]:
        _ECHECS.pop(k, None)
    return len([t for t in _ECHECS.get(_ip(), []) if m - t < 900]) >= 8


def _noter_echec():
    import time
    _ECHECS.setdefault(_ip(), []).append(time.time())
    _ECHECS[_ip()] = _ECHECS[_ip()][-20:]


# 26 oct 2026 - compte de demonstration pour l'equipe d'Apple (et les essais) : code dans LOCKERROOM_DEMO_CODE.
# Un compte a part, Pro offert, quelques cartes d'exemple ; sans code configure, la route n'existe pas.
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
        erreur = "<p style='color:#FFB3B3'>Trop d’essais : réessaie dans 15 minutes</p>"
    elif request.method == "POST":
        if hmac.compare_digest(str(request.form.get("code") or "").strip(), code):
            cid, nouveau = comptes.trouver_ou_creer(_DEMO_EBAY_ID, "Demo", "demo")
            comptes.maj(cid, pro_offert="toujours", demo=True)
            session.permanent = True
            session["ok"] = True
            session["compte"] = cid
            if nouveau:
                with comptes.utiliser(cid):
                    _remplir_demo()
            return redirect("/")
        _noter_echec()
        erreur = "<p style='color:#FFB3B3'>Code incorrect</p>"
    return _page_langue("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>SlabCoach</title><link rel='icon' href='/favicon.ico?v=2'>"
            "<body style='background:#0B0B0E;color:#F4F2EE;font-family:system-ui;display:grid;place-items:center;min-height:90vh'>"
            "<form method='post' style='display:grid;gap:12px;width:min(320px,90vw)'><img src='/logo_sc_gold_poli.png' width='72' style='margin:auto' alt=''>"
            "<b style='font-size:22px'>SlabCoach · démo</b><input name='code' autocomplete='off' autofocus placeholder='Code d’accès' "
            "style='padding:12px;border-radius:10px;border:1px solid #2B2A32;background:#151519;color:#F4F2EE;font-size:16px'>"
            f"{erreur}<button style='padding:12px;border-radius:10px;border:0;background:#E9CF8E;font-weight:700;font-size:16px'>Entrer</button>"
            "<a href='/connexion' style='color:#A9A6B1;font-size:13px'>‹ Retour</a></form></body>")


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
    session.clear()
    return redirect("/connexion")


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
       ('<html lang="fr">', '<html lang="en">'), ("Joue tes cartes <em>comme un pro.</em>", "Play your cards <em>like a pro.</em>"),
       ("SlabCoach · Joue tes cartes comme un pro", "SlabCoach · Play your cards like a pro"),
       ("Deals sous la valeur", "Deals under value"), ("Vraies valeurs", "Real values"), ("Chances de breaks", "Break odds"),
       ("Inventaire et ventes eBay", "eBay inventory and sales"),
       ("Code de démonstration", "Demo code"), ("Continuer avec Apple", "Continue with Apple"), ("Continuer avec Google", "Continue with Google"),
       ("Recommandé", "Recommended"), ("Ton inventaire et tes ventes arrivent tout seuls", "Your inventory and sales come in on their own"),
       ('<div class="ou">ou</div>', '<div class="ou">or</div>'), ("Pas de compte eBay ? Aucun problème.", "No eBay account? No problem."),
       ("Cette connexion n’est pas encore offerte : utilise eBay", "This sign-in isn’t available yet: use eBay"),
       ("Connexion interrompue : réessaie", "Sign-in interrupted: try again"), ("‹ Retour au site", "‹ Back to site"),
       ("14 jours de Pro offerts · aucune carte de crédit", "14 days of Pro on us · no credit card"),
       ("Trop d’essais : réessaie dans 15 minutes", "Too many attempts: try again in 15 minutes")]


def _langue():
    l = (request.args.get("lang") or request.cookies.get("lr_langue") or "").lower()
    if l in ("fr", "en"):
        return l
    return "en" if (request.accept_languages.best_match(["fr", "en"]) or "fr") == "en" else "fr"


def _page_vitrine():
    """27 oct 2026 - slabcoach.com pour un visiteur : la vitrine (pourquoi nous, Gratuit / essai / Pro, eBay recommande)."""
    try:
        with open(os.path.join(DOSSIER_UI, "vitrine.html"), encoding="utf-8") as f:
            html = f.read()
    except OSError:
        from flask import redirect
        return redirect("/connexion")
    l = _langue()
    autre = "fr" if l == "en" else "en"
    html = html.replace('<html lang="fr">', f'<html lang="{l}">').replace(
        '<a class="btn holo" href="/connexion"><span class="fr">Commencer</span>',
        f'<a class="lang" href="?lang={autre}">{"Français" if autre == "fr" else "English"}</a><a class="btn holo" href="/connexion"><span class="fr">Commencer</span>', 1)
    from flask import make_response
    r = make_response(html)
    if request.args.get("lang") in ("fr", "en"):
        r.set_cookie("lr_langue", l, max_age=365 * 86400, samesite="Lax")
    return r


def _page_langue(html):
    from flask import make_response
    l = _langue()
    if l == "en":
        for a, b in _EN:
            html = html.replace(a, b)
    autre = "fr" if l == "en" else "en"
    lien = (f"<a href='?lang={autre}' style='position:fixed;top:14px;left:14px;padding:7px 12px;border-radius:999px;"
            f"border:1px solid #34333D;background:rgba(21,21,25,.7);color:#F4F2EE;font:700 13px system-ui;text-decoration:none;z-index:5'>"
            f"{'Français' if autre == 'fr' else 'English'}</a>")
    r = make_response(html.replace("</body>", lien + "</body>"))
    if request.args.get("lang") in ("fr", "en"):
        r.set_cookie("lr_langue", l, max_age=365 * 86400, samesite="Lax")
    return r


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
        if not autres:
            page = page.replace('<div class="ou">ou</div>', "")
        if os.environ.get("LOCKERROOM_DEMO_CODE") and "LockerRoomiOS" in (request.headers.get("User-Agent") or ""):
            page = page.replace("</div></main>", "<a class='demo' href='/demo'>Code de démonstration</a></div></main>")
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
    return "LockerRoomiOS" in (request.headers.get("User-Agent") or "")


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
    return Response(html, mimetype="text/html")


@app.route("/confidentialite")
def page_confidentialite():
    return _page_legale("confidentialite.html")


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
    return send_from_directory(DOSSIER_UI, "break.html")


@app.route("/api/b/<jeton>")
def donnees_break(jeton):
    d = _break_public(jeton)
    if not d:
        return jsonify({"erreur": "Break introuvable"}), 404
    return jsonify(d)


@app.route("/api/ebay_retour")
def ebay_retour():
    """Page ou eBay renvoie le vendeur apres « Accepter » (auth accepted URL)."""
    from flask import redirect, session
    if not _navigateur_lie(request.args.get("state")):
        return redirect("/connexion?erreur=1" if not comptes.courant() else "/#reglages/ebay-erreur")
    if comptes.MULTI and not comptes.courant():
        import ebay_compte
        r = ebay_compte.connexion_compte(request.url, request.args.get("state"))
        if not r.get("ok"):
            return redirect("/connexion?erreur=1")
        _premiere_synchro(r["compte"])
        return _billet(r["compte"], "/#accueil/" + ("bienvenue" if r.get("nouveau") else "retour"), request.args.get("state"))
    r = api.ebay_terminer(request.url, request.args.get("state"))
    if r.get("ok") and comptes.MULTI and comptes.courant():      # 28 oct 2026 : eBay relie depuis Reglages -> import tout seul
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


@app.route("/<path:nom>")
def statiques(nom):
    return send_from_directory(DOSSIER_UI, nom)


# multi-comptes : ce qui touche le serveur entier (nos cles, l'environnement, les avis) n'est pas aux clients
_RESERVEES_SERVEUR = {"ebay_cles_sauver", "ebay_environnement", "ebay_avis_regler", "ebay_avis_jeton", "valeurs_maj"}
# 27 oct 2026 (revue de securite) : sur le PC (sans code d'acces), un autre appareil du meme wifi peut LIRE l'app mais
# pas ecrire sur eBay, ni toucher aux cles : ces gestes restent sur le PC lui-meme (ou avec LOCKERROOM_CODE).
_ECRITURES_EBAY = {"ebay_publier", "annonce_publier", "ebay_changer_prix", "ebay_miser", "ebay_cles_sauver", "ebay_avis_regler",
                   "ebay_avis_jeton", "ebay_deconnecter", "ebay_environnement", "ebay_terminer", "ebay_url_connexion", "ebay_promouvoir",
                   "prix_auto_appliquer", "prix_auto_regler", "offres_envoyer"}


@app.route("/api/<nom>", methods=["POST"])
def dispatcher(nom):
    if nom.startswith("_"):
        return jsonify({"erreur": "méthode non autorisée"}), 403
    o = request.headers.get("Origin")
    if o and o != "null":                    # 27 oct 2026 : appels venus d'un autre site refuses (en plus de SameSite)
        import urllib.parse
        if urllib.parse.urlparse(o).netloc.lower() != request.host.lower():
            return jsonify({"erreur": "Origine refusée"}), 403
    if comptes.MULTI and nom in _RESERVEES_SERVEUR:
        return jsonify({"erreur": "Réglage du serveur : non modifiable ici"}), 403
    if not comptes.MULTI and not CODE_ACCES and nom in _ECRITURES_EBAY and request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"erreur": "Sur un autre appareil, ajoute un code d’accès (LOCKERROOM_CODE) pour écrire sur eBay"}), 403
    m = getattr(api, nom, None)
    if m is None or not callable(m):
        return jsonify({"erreur": f"méthode inconnue : {nom}"}), 404
    args = request.get_json(silent=True)
    if args is None:
        args = []
    if not isinstance(args, list):
        args = [args]
    try:
        res = m(*args)
        if nom == "ebay_url_connexion" and isinstance(res, dict) and res.get("url"):
            return _lier_navigateur(jsonify(res), res["url"])
        return jsonify(res)
    except Exception as e:  # l'ecran affiche l'erreur dans un toast
        try:
            import admin
            admin.noter_erreur("api " + nom, e)
        except Exception:
            pass
        if HEBERGE:
            app.logger.exception("Erreur API %s", nom)
            return jsonify({"erreur": "Erreur du serveur : réessaie dans un instant"}), 500
        return jsonify({"erreur": f"{type(e).__name__} : {e}"}), 500


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
    import valeurs_maj
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


def _ebay_auto():
    """Toutes les heures : annonces et ventes relues (compte connecte), puis prix compares au marche (cles eBay)."""
    import ebay_compte
    time.sleep(60)
    import comptes as _c
    while True:
        for cid in (_c.lister() if _c.MULTI else [None]):      # multi : chaque client a tour de role
            with _c.utiliser(cid):
                try:
                    st = ebay_compte.statut()
                    if st.get("connecte"):
                        r = api.ebay_synchroniser(30)
                        print("Synchro eBay :", cid or "", {k: r.get(k) for k in ("ok", "annonces", "ventes", "erreur")}, flush=True)
                    try:                         # 26 oct 2026 : les alertes de prix de chaque compte
                        ra = api.alertes_verifier()
                        if ra.get("nouvelles"):
                            print("Alertes :", cid or "", ra, flush=True)
                    except Exception as e:
                        print("Alertes : " + str(e), flush=True)
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
                        try:                     # 28 oct 2026 : la forme des joueurs des tendances (LNH)
                            import nhl
                            nhl.rafraichir_si_besoin()
                        except Exception as e:
                            print("LNH : " + str(e), flush=True)
                except Exception as e:
                    print("Synchro eBay : " + str(e), flush=True)
        time.sleep(3600)


def _verifier_secrets():
    """27 oct 2026 (revue) : en ligne, les jetons eBay doivent etre chiffres. On le dit fort dans le journal de Render."""
    if comptes.MULTI and not os.environ.get("LOCKERROOM_CLE"):
        app.logger.error("ATTENTION : LOCKERROOM_CLE absente -> jetons eBay NON chiffres sur le disque. Ajoute-la dans Render.")
        print("ATTENTION : LOCKERROOM_CLE absente : jetons eBay non chiffres", flush=True)


def demarrer_taches():
    _verifier_secrets()
    threading.Thread(target=_valeurs_auto, daemon=True).start()
    threading.Thread(target=_ebay_auto, daemon=True).start()


if HEBERGE and os.environ.get("LOCKERROOM_TACHES", "1") == "1":
    demarrer_taches()          # gunicorn importe ce fichier : 1 seul worker (voir render.yaml)


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
