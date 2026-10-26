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
              "/connexion", "/icone", "/favicon", "/manifest.json", "/stripe/webhook")


import comptes  # noqa: E402

_PUBLIQUES_MULTI = _PUBLIQUES + ("/auth/ebay", "/deconnexion")


@app.before_request
def _garde():
    from flask import redirect, session
    comptes.activer(None)
    publique = request.path.startswith(_PUBLIQUES_MULTI)
    if CODE_ACCES and not session.get("ok") and not publique:       # demo : code d'acces d'abord
        return (jsonify({"erreur": "Connexion requise"}), 401) if request.path.startswith("/api/") else redirect("/connexion")
    if comptes.MULTI:
        cid = session.get("compte")
        if cid and cid in comptes.lister():
            comptes.activer(cid)                                     # cette requete ne voit que ce compte
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
    return redirect(r["url"])


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


_PAGE_EBAY = ("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>LockerRoom</title>"
              "<body style='background:#0A0D10;color:#F2F5F7;font-family:system-ui;display:grid;place-items:center;min-height:90vh;margin:0'>"
              "<main style='display:grid;gap:16px;width:min(340px,88vw);text-align:center'><img src='/icone.png' width='64' style='margin:auto' alt=''>"
              "<b style='font-size:26px'>LockerRoom</b><span style='color:#A3ACB5'>Ton inventaire eBay, tes prix et tes ventes, tout seuls.</span>"
              "{erreur}<a href='/auth/ebay' style='padding:15px;border-radius:12px;background:#7FD0FF;color:#0A0D10;font-weight:700;font-size:17px;text-decoration:none'>"
              "Se connecter avec eBay</a><span style='color:#87909A;font-size:13px'>Aucun mot de passe dans l’app · ton compte est créé tout seul</span>"
              "<span style='font-size:13px'><a href='/confidentialite' style='color:#A3ACB5'>Confidentialité</a> · "
              "<a href='/conditions' style='color:#A3ACB5'>Conditions</a></span></main></body>")


# 24 oct 2026 - pages de connexion en francais ou en anglais : ?lang=, sinon le choix de l'app (temoin lr_langue),
# sinon la langue du navigateur ; un lien en haut a gauche pour changer.
_EN = [("Ton inventaire eBay, tes prix et tes ventes, tout seuls.", "Your eBay inventory, prices and sales, on autopilot."),
       ("Se connecter avec eBay", "Sign in with eBay"), ("Aucun mot de passe dans l’app · ton compte est créé tout seul",
       "No password in the app · your account is created automatically"), ("Confidentialité", "Privacy"),
       (">Conditions<", ">Terms<"), ("Connexion eBay interrompue : réessaie", "eBay sign-in interrupted: try again"),
       ("Code incorrect", "Wrong code"), ("Code d’accès", "Access code"), (">Entrer<", ">Enter<")]


def _langue():
    l = (request.args.get("lang") or request.cookies.get("lr_langue") or "").lower()
    if l in ("fr", "en"):
        return l
    return "en" if (request.accept_languages.best_match(["fr", "en"]) or "fr") == "en" else "fr"


def _page_langue(html):
    from flask import make_response
    l = _langue()
    if l == "en":
        for a, b in _EN:
            html = html.replace(a, b)
    autre = "fr" if l == "en" else "en"
    lien = (f"<a href='?lang={autre}' style='position:fixed;top:14px;left:14px;padding:7px 12px;border-radius:999px;"
            f"border:1px solid #29313A;color:#F2F5F7;font:700 13px system-ui;text-decoration:none'>"
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
        e = "<span style='color:#FFB3B3'>Connexion eBay interrompue : réessaie</span>" if request.args.get("erreur") else ""
        return _page_langue(_PAGE_EBAY.replace("{erreur}", e))
    if not CODE_ACCES:
        return redirect("/")
    erreur = ""
    if request.method == "POST":
        if hmac.compare_digest(str(request.form.get("code") or ""), CODE_ACCES):
            session.permanent = True
            session["ok"] = True
            return redirect("/connexion" if comptes.MULTI else "/")
        erreur = "<p style='color:#FFB3B3'>Code incorrect</p>"
    return _page_langue("<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'><title>LockerRoom</title>"
            "<body style='background:#0A0D10;color:#F2F5F7;font-family:system-ui;display:grid;place-items:center;min-height:90vh'>"
            "<form method='post' style='display:grid;gap:12px;width:min(320px,90vw)'><img src='/icone.png' width='56' alt=''>"
            "<b style='font-size:22px'>LockerRoom</b><input name='code' type='password' autofocus placeholder='Code d’accès' "
            "style='padding:12px;border-radius:10px;border:1px solid #29313A;background:#14181D;color:#F2F5F7;font-size:16px'>"
            f"{erreur}<button style='padding:12px;border-radius:10px;border:0;background:#7FD0FF;font-weight:700;font-size:16px'>Entrer</button>"
            "<a href='/confidentialite' style='color:#A3ACB5;font-size:13px'>Confidentialité</a></form></body>")


@app.route("/confidentialite")
def page_confidentialite():
    return send_from_directory(DOSSIER_UI, "confidentialite.html")


@app.route("/conditions")
def page_conditions():
    return send_from_directory(DOSSIER_UI, "conditions.html")


@app.route("/")
def racine():
    return _page_app()


def _break_public(jeton):
    """Page publique d'un break : en multi-comptes, on trouve le compte qui l'a cree."""
    import comptes as _c
    if not _c.MULTI:
        return api.break_public(jeton)
    for cid in _c.lister():
        with _c.utiliser(cid):
            d = api.break_public(jeton)
            if d:
                return d
    return None


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
    if comptes.MULTI and not comptes.courant():
        import ebay_compte
        r = ebay_compte.connexion_compte(request.url, request.args.get("state"))
        if not r.get("ok"):
            return redirect("/connexion?erreur=1")
        session.permanent = True
        session["compte"] = r["compte"]
        _premiere_synchro(r["compte"])
        return redirect("/#accueil/" + ("bienvenue" if r.get("nouveau") else "retour"))
    r = api.ebay_terminer(request.url, request.args.get("state"))
    return redirect("/#reglages/" + ("ebay-ok" if r.get("ok") else "ebay-erreur"))


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
    ebay_avis.recevoir(request.get_data())
    return ("", 204)


@app.route("/<path:nom>")
def statiques(nom):
    return send_from_directory(DOSSIER_UI, nom)


# multi-comptes : ce qui touche le serveur entier (nos cles, l'environnement, les avis) n'est pas aux clients
_RESERVEES_SERVEUR = {"ebay_cles_sauver", "ebay_environnement", "ebay_avis_regler", "ebay_avis_jeton", "valeurs_maj"}


@app.route("/api/<nom>", methods=["POST"])
def dispatcher(nom):
    if nom.startswith("_"):
        return jsonify({"erreur": "méthode non autorisée"}), 403
    if comptes.MULTI and nom in _RESERVEES_SERVEUR:
        return jsonify({"erreur": "Réglage du serveur : non modifiable ici"}), 403
    m = getattr(api, nom, None)
    if m is None or not callable(m):
        return jsonify({"erreur": f"méthode inconnue : {nom}"}), 404
    args = request.get_json(silent=True)
    if args is None:
        args = []
    if not isinstance(args, list):
        args = [args]
    try:
        return jsonify(m(*args))
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
    """Valeur des joueurs (algo LockerRoom) : recalculee au demarrage si elle a
    plus de 20 h, puis verifiee chaque heure. Prototype : la source est le
    dossier de Hall of Cardz sur ce PC (lecture seule) ; sans source, les
    valeurs deja la (ou celles par defaut) restent."""
    import valeurs
    import valeurs_maj
    while True:
        try:
            age = time.time() - os.path.getmtime(valeurs.CHEMIN) if os.path.exists(valeurs.CHEMIN) else 1e9
            if age > 20 * 3600 and os.path.isdir(valeurs_maj.SOURCE_DEFAUT):
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
                except Exception as e:
                    print("Synchro eBay : " + str(e), flush=True)
        time.sleep(3600)


def demarrer_taches():
    threading.Thread(target=_valeurs_auto, daemon=True).start()
    threading.Thread(target=_ebay_auto, daemon=True).start()


if HEBERGE and os.environ.get("LOCKERROOM_TACHES", "1") == "1":
    demarrer_taches()          # gunicorn importe ce fichier : 1 seul worker (voir render.yaml)


if __name__ == "__main__":
    if not _prendre_verrou():
        print("LockerRoom tourne deja - tu peux fermer cette fenetre.", flush=True)
        sys.exit(0)
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "<ip-du-pc>"
    print("=" * 56)
    print("LockerRoom - serveur demarre")
    print(f"  Sur ce PC      : http://localhost:{PORT}")
    print(f"  iPhone (wifi)  : http://{ip}:{PORT}")
    print("=" * 56, flush=True)
    threading.Thread(target=_surveiller, daemon=True).start()
    if not HEBERGE:
        demarrer_taches()
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
