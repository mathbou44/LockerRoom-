"""
LOCKERROOM - « Se connecter avec eBay » (OAuth officiel, aucun mot de passe).

Le vendeur se connecte sur la page d'eBay elle-meme et approuve l'app ; eBay
renvoie un code que l'app echange contre un jeton (2 h, renouvele tout seul
pendant ~18 mois). L'app ne voit jamais le mot de passe et le vendeur peut
revoquer l'acces dans son compte eBay (Compte > Preferences de connexion).

Ce que l'app lit (lecture seule) :
  - annonces actives          : Trading API GetMyeBaySelling (ActiveList)
  - commandes et frais reels  : Sell Fulfillment API getOrders (totalMarketplaceFee)
  - nom du compte             : Commerce Identity API

Configuration (une fois, par le vendeur, sur developer.ebay.com) : cles de
PRODUCTION d'une application SlabCoach (App ID, Cert ID) + un RuName dont
l'« auth accepted URL » est http://localhost:8430/api/ebay_retour (ou
n'importe quelle page : l'app accepte aussi l'adresse collee a la main).
Cles et jetons restent dans des fichiers locaux, jamais renvoyes a l'ecran
(seulement les 4 derniers caracteres).
"""
import base64
import json
import re
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import appels_ebay
import comptes

DOSSIER = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))   # heberge : disque persistant
CHEMIN_ENV = os.path.join(DOSSIER, "ebay_env.json")

# 21 oct 2026 (Mathieu : « on prepare le sandbox ? ») - deux environnements eBay
# completement separes : adresses, cles, jetons ET base de donnees (lockerroom.py).
ENVIRONNEMENTS = {
    "production": {"auth": "https://auth.ebay.com/oauth2/authorize",
                   "api": "https://api.ebay.com", "apiz": "https://apiz.ebay.com",
                   "cles": "ebay_cles.json", "jetons": ".ebay_jetons.json", "site_web": "https://www.ebay.ca"},
    "sandbox": {"auth": "https://auth.sandbox.ebay.com/oauth2/authorize",
                "api": "https://api.sandbox.ebay.com", "apiz": "https://apiz.sandbox.ebay.com",
                "cles": "ebay_cles_sandbox.json", "jetons": ".ebay_jetons_sandbox.json", "site_web": "https://sandbox.ebay.ca"},
}


def environnement():
    if comptes.MULTI:                       # heberge : fixe par le serveur (demo = sandbox)
        e = os.environ.get("LOCKERROOM_EBAY_ENV", "production")
        return e if e in ENVIRONNEMENTS else "production"
    e = _lire(CHEMIN_ENV).get("env")
    return e if e in ENVIRONNEMENTS else "production"


def changer_environnement(env):
    if comptes.MULTI:
        raise ValueError("L'environnement eBay est fixé par le serveur")
    if env not in ENVIRONNEMENTS:
        raise ValueError("Environnement inconnu")
    _ecrire(CHEMIN_ENV, {"env": env})
    return statut()


def _env():
    return ENVIRONNEMENTS[environnement()]


CHEMIN_CLES = None        # tests : chemins imposes (sinon selon l'environnement)
CHEMIN_JETONS = None


def chemin_cles():
    return CHEMIN_CLES or os.path.join(DOSSIER, _env()["cles"])


def chemin_jetons():
    if CHEMIN_JETONS:
        return CHEMIN_JETONS
    d = comptes.dossier()                   # multi-comptes : les jetons du client de la session
    return os.path.join(d or DOSSIER, _env()["jetons"])


def _cles_serveur():
    """Heberge : NOS cles, en variables d'environnement (jamais dans un fichier, jamais au client)."""
    suf = "_SANDBOX" if environnement() == "sandbox" else ""
    c = {k: os.environ.get(f"LOCKERROOM_EBAY_{k.upper()}{suf}") for k in ("app_id", "cert_id", "runame")}
    return c if all(c.values()) else None


def url(nom):
    e = _env()
    return {"auth": e["auth"], "jeton": e["api"] + "/identity/v1/oauth2/token", "trading": e["api"] + "/ws/api.dll",
            "commandes": e["api"] + "/sell/fulfillment/v1/order", "identite": e["apiz"] + "/commerce/identity/v1/user/",
            "recherche": e["api"] + "/buy/browse/v1/item_summary/search", "offre": e["api"] + "/buy/offer/v1_beta/bidding",
            "site": e["site_web"]}[nom]


# les noms de scopes sont les memes en sandbox (toujours https://api.ebay.com/...)
SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
    "https://api.ebay.com/oauth/api_scope/commerce.identity.readonly",
]
SCOPE_ECRITURE = "https://api.ebay.com/oauth/api_scope/sell.inventory"      # mettre en vente, changer un prix
SCOPE_MARKETING = "https://api.ebay.com/oauth/api_scope/sell.marketing"  # promouvoir une annonce (% choisi par le vendeur)
SCOPE_MISES = "https://api.ebay.com/oauth/api_scope/buy.offer.auction"      # miser (API Offer : sandbox, ou production approuvee)


def scopes_demandes():
    c = _lire(chemin_cles())
    if os.environ.get("LOCKERROOM_MISES_APPROUVEES") == "1":
        c["mises_approuvees"] = True
    out = list(SCOPES) + [SCOPE_ECRITURE, SCOPE_MARKETING]       # 24 oct 2026 - promotion des annonces (Promoted Listings)
    import ebay_moderne                                           # 27 oct 2026 : politiques d'affaires (mode inventaire)
    out += [s for s in ebay_moderne.scopes_en_plus() if s not in out]
    # 21 oct 2026 - buy.offer.auction est en « Limited Release » : un scope que le jeu de cles
    # n'a pas fait echouer TOUTE la connexion chez eBay (page /n/error). Seulement si permis.
    if c.get("mises_approuvees"):
        out.append(SCOPE_MISES)
    return out


SITE_ID = "2"                         # eBay Canada
NIVEAU = "1193"
_NS = {"e": "urn:ebay:apis:eBLBaseComponents"}
MARGE_S = 120


_VERROUS = {}


def _verrou_de(chemin):
    """27 oct 2026 (revue) : un verrou par fichier de jetons (rafraichir pendant une deconnexion ne la defait plus)."""
    import threading
    return _VERROUS.setdefault(chemin, threading.RLock())


def _lire(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            brut = f.read()
    except OSError:
        return {}
    try:
        return json.loads(comptes.dechiffrer(brut)) or {}
    except ValueError:
        return {}
    except Exception:                         # cle LOCKERROOM_CLE changee ou absente : message clair, rien n'est ecrase
        raise RuntimeError("Jetons eBay illisibles (clé du serveur changée) : reconnecte eBay")


def _ecrire(chemin, data):
    texte = json.dumps(data)
    if os.path.basename(chemin).startswith(".ebay_jetons"):
        texte = comptes.chiffrer(texte)      # LOCKERROOM_CLE definie : jetons chiffres sur le disque
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texte)
    os.replace(tmp, chemin)


def _fin(v):
    v = str(v or "")
    return ("•••• " + v[-4:]) if len(v) >= 8 else ("••••" if v else "")


# -- cles -------------------------------------------------------------------------------
def sauver_cles(app_id=None, cert_id=None, runame=None):
    c = _lire(chemin_cles())
    for k, v in (("app_id", app_id), ("cert_id", cert_id), ("runame", runame)):
        v = str(v or "").strip()
        if v and "•" not in v:
            c[k] = v
    _ecrire(chemin_cles(), c)
    return statut()


def _cles():
    c = _cles_serveur() or _lire(chemin_cles())
    if not (c.get("app_id") and c.get("cert_id") and c.get("runame")):
        raise RuntimeError("Clés eBay manquantes : App ID, Cert ID et RuName dans Réglages")
    if c["runame"] == c["app_id"]:
        # eBay repond alors « temporarily_unavailable » (500) au lieu d'un message clair
        raise RuntimeError("Le RuName enregistré est ton App ID : colle le vrai RuName (User Tokens sur developer.ebay.com)")
    return c


def statut():
    c, j = (_cles_serveur() or _lire(chemin_cles())), _lire(chemin_jetons())
    connecte = bool(j.get("refresh_token")) and j.get("refresh_expire_a", 0) > time.time()
    return {"cles": {"app_id": _fin(c.get("app_id")), "cert_id": _fin(c.get("cert_id")), "runame": _fin(c.get("runame"))},
            "cles_ok": bool(c.get("app_id") and c.get("cert_id") and c.get("runame")) and c.get("runame") != c.get("app_id"),
            "runame_erreur": "Le RuName est ton App ID : colle le vrai RuName" if c.get("runame") and c.get("runame") == c.get("app_id") else None,
            "connecte": connecte, "compte": j.get("compte") if connecte else None,
            "expire_le": datetime.fromtimestamp(j["refresh_expire_a"]).isoformat(timespec="minutes") if connecte else None,
            "derniere_synchro": j.get("derniere_synchro"), "bilan_synchro": j.get("bilan_synchro"),
            "env": environnement(), "site": url("site"),
            "ecriture": connecte and SCOPE_ECRITURE in (j.get("scopes") or []),
            "mises": connecte and SCOPE_MISES in (j.get("scopes") or []),
            "multi": comptes.MULTI, "cles_serveur": bool(_cles_serveur())}


# -- OAuth ----------------------------------------------------------------------------------
def url_connexion():
    c = _cles()
    etat = secrets.token_urlsafe(16)
    if comptes.MULTI and not comptes.courant():
        _attente_ajouter(etat, scopes_demandes())
    else:
        j = _lire(chemin_jetons())
        j["etat_attendu"] = etat
        j["scopes_attendus"] = scopes_demandes()
        _ecrire(chemin_jetons(), j)
    q = urllib.parse.urlencode({"client_id": c["app_id"], "redirect_uri": c["runame"], "response_type": "code",
                                "scope": " ".join(scopes_demandes()), "state": etat, "prompt": "login"}, quote_via=urllib.parse.quote)
    return {"ok": True, "url": url("auth") + "?" + q}


def _post_jeton(data):
    c = _cles()
    auth = base64.b64encode(f"{c['app_id']}:{c['cert_id']}".encode()).decode()
    req = urllib.request.Request(url("jeton"), data=urllib.parse.urlencode(data).encode(), method="POST",
                                 headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        brut = e.read().decode("utf-8", "ignore")[:300]
        print(f"eBay jeton refuse HTTP {e.code} : {brut}", flush=True)          # journal du serveur seulement
        if "invalid_grant" in brut:
            return None, "invalid_grant"
        return None, f"eBay a refusé la connexion (HTTP {e.code}) : réessaie dans un instant"
    except urllib.error.URLError as e:
        return None, f"eBay injoignable : {e.reason}"


def code_depuis(texte):
    """Le code d'autorisation, a partir du code lui-meme ou de l'adresse complete
    de la page ou eBay a renvoye le vendeur (?code=...&state=...)."""
    t = str(texte or "").strip()
    if "code=" in t:
        q = urllib.parse.urlparse(t).query or t.split("?", 1)[-1]
        p = urllib.parse.parse_qs(q)
        return (p.get("code") or [""])[0], (p.get("state") or [None])[0]
    return urllib.parse.unquote(t), None


# -- multi-comptes : connexions en cours (aucun compte encore : c'est eBay qui nous dira qui) ----
def _chemin_attente():
    return os.path.join(comptes.DONNEES, "connexions_en_attente.json")


def _attente_ajouter(etat, scopes):
    a = {k: v for k, v in _lire(_chemin_attente()).items() if v.get("le", 0) > time.time() - 900}
    a[etat] = {"le": time.time(), "scopes": scopes}
    _ecrire(_chemin_attente(), a)


def _attente_prendre(etat):
    a = _lire(_chemin_attente())
    e = a.pop(etat, None) if etat else None
    _ecrire(_chemin_attente(), a)
    return e if e and e.get("le", 0) > time.time() - 900 else None


def _identite(access_token):
    appels_ebay.compter("identity")
    req = urllib.request.Request(url("identite"), headers={"Authorization": "Bearer " + access_token, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def connexion_compte(texte, etat=None):
    """Multi-comptes : « Se connecter avec eBay » EST l'inscription. eBay renvoie le code,
    on apprend qui est le vendeur, son compte est cree au besoin. -> {ok, compte, nouveau}"""
    code, etat_url = code_depuis(texte)
    attente = _attente_prendre(etat or etat_url)
    if not code or not attente:
        return {"ok": False, "erreur": "Connexion eBay expirée : recommence"}
    c = _cles()
    p, err = _post_jeton({"grant_type": "authorization_code", "code": code, "redirect_uri": c["runame"]})
    if err:
        return {"ok": False, "erreur": "Code eBay expiré : recommence la connexion" if err == "invalid_grant" else err}
    try:
        u = _identite(p["access_token"])
    except Exception:
        return {"ok": False, "erreur": "eBay n'a pas confirmé ton identité : recommence"}
    if not u.get("userId"):
        return {"ok": False, "erreur": "eBay n'a pas confirmé ton identité : recommence"}
    relie = next(iter(comptes.par_champ("ebay_user_id", u["userId"])), None)   # 27 oct 2026 : deja relie a un compte Apple / Google
    cid, nouveau = (relie, False) if relie else comptes.trouver_ou_creer(u["userId"], u.get("username"), environnement())
    comptes.maj(cid, ebay_user_id=u["userId"], ebay_username=u.get("username"))   # identite confirmee par eBay
    maintenant = time.time()
    with comptes.utiliser(cid):
        j = _lire(chemin_jetons())
        j.update(access_token=p["access_token"], access_expire_a=maintenant + int(p.get("expires_in", 7200)),
                 refresh_token=p.get("refresh_token"), refresh_expire_a=maintenant + int(p.get("refresh_token_expires_in", 47304000)),
                 scopes=attente.get("scopes") or SCOPES, compte=u.get("username"), ebay_user_id=u["userId"])
        _ecrire(chemin_jetons(), j)
    return {"ok": True, "compte": cid, "nouveau": nouveau, "username": u.get("username")}


def terminer_connexion(texte, etat=None):
    code, etat_url = code_depuis(texte)
    if not code:
        return {"ok": False, "erreur": "Aucun code d'autorisation eBay dans cette adresse"}
    if comptes.MULTI and not comptes.courant():
        return connexion_compte(texte, etat)
    j = _lire(chemin_jetons())
    recu = etat or etat_url
    if (recu and j.get("etat_attendu") and recu != j["etat_attendu"]) or (comptes.MULTI and (not recu or recu != j.get("etat_attendu"))):
        return {"ok": False, "erreur": "Réponse eBay inattendue (état différent) : recommence la connexion"}
    c = _cles()
    p, err = _post_jeton({"grant_type": "authorization_code", "code": code, "redirect_uri": c["runame"]})
    if err:
        return {"ok": False, "erreur": "Code eBay expiré : recommence la connexion" if err == "invalid_grant" else err}
    maintenant = time.time()
    j.update(access_token=p["access_token"], access_expire_a=maintenant + int(p.get("expires_in", 7200)),
             refresh_token=p.get("refresh_token"), refresh_expire_a=maintenant + int(p.get("refresh_token_expires_in", 47304000)))
    j["scopes"] = j.pop("scopes_attendus", None) or SCOPES
    j.pop("etat_attendu", None)
    _ecrire(chemin_jetons(), j)
    try:
        u = _get_json(url("identite"))
        j["compte"] = u.get("username")
        j["ebay_user_id"] = u.get("userId")
        _ecrire(chemin_jetons(), j)
        if comptes.MULTI and comptes.courant():           # 27 oct 2026 : compte Apple / Google qui relie son eBay
            comptes.maj(comptes.courant(), ebay_username=u.get("username"), ebay_user_id=u.get("userId"))
    except Exception:
        pass
    return {"ok": True, **statut()}


def deconnecter():
    ch = chemin_jetons()
    with _verrou_de(ch):
        j = _lire(ch)
        for k in ("access_token", "access_expire_a", "refresh_token", "refresh_expire_a", "compte"):
            j.pop(k, None)
        _ecrire(ch, j)
    return statut()


def jeton():
    ch = chemin_jetons()
    with _verrou_de(ch):                      # un seul rafraichissement a la fois par compte
        j = _lire(ch)
        if j.get("access_token") and j.get("access_expire_a", 0) > time.time() + MARGE_S:
            return j["access_token"]
        if not j.get("refresh_token") or j.get("refresh_expire_a", 0) <= time.time():
            raise RuntimeError("Compte eBay non connecté")
        p, err = _post_jeton({"grant_type": "refresh_token", "refresh_token": j["refresh_token"], "scope": " ".join(j.get("scopes") or SCOPES)})
        j2 = _lire(ch)                        # relu apres l'appel : on ne garde que les champs du jeton
        if j2.get("refresh_token") != j.get("refresh_token"):
            raise RuntimeError("Compte eBay changé pendant la connexion : réessaie")
        if err == "invalid_grant":            # 27 oct 2026 : acces retire chez eBay -> on le dit, on arrete de reessayer
            for k in ("access_token", "access_expire_a", "refresh_token", "refresh_expire_a"):
                j2.pop(k, None)
            _ecrire(ch, j2)
            raise RuntimeError("Accès eBay retiré ou expiré : reconnecte eBay dans Réglages")
        if err:
            raise RuntimeError(err)
        j2.update(access_token=p["access_token"], access_expire_a=time.time() + int(p.get("expires_in", 7200)))
        if p.get("refresh_token"):
            j2.update(refresh_token=p["refresh_token"], refresh_expire_a=time.time() + int(p.get("refresh_token_expires_in", 47304000)))
        _ecrire(ch, j2)
        return j2["access_token"]


# -- lectures ---------------------------------------------------------------------------------
def _get_json(url):
    appels_ebay.compter("identity" if "/identity/" in url else "fulfillment")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + jeton(), "Accept": "application/json",
                                               "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"eBay HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:200]}")


def _num(el, chemin):
    x = el.find(chemin, _NS)
    try:
        return float(x.text) if x is not None and x.text else None
    except ValueError:
        return None


def _txt(el, chemin):
    x = el.find(chemin, _NS)
    return (x.text or "").strip() if x is not None and x.text else ""


def lire_annonces_xml(brut):
    """(annonces, nb_pages) d'une reponse GetMyeBaySelling."""
    racine = ET.fromstring(brut)
    ack = _txt(racine, "e:Ack")
    if ack not in ("Success", "Warning"):
        raise RuntimeError(_txt(racine, "e:Errors/e:LongMessage") or f"eBay : Ack={ack}")
    out = []
    for it in racine.findall("e:ActiveList/e:ItemArray/e:Item", _NS):
        out.append({"item_number": _txt(it, "e:ItemID"), "titre": _txt(it, "e:Title"), "sku": _txt(it, "e:SKU"),
                    "prix": _num(it, "e:SellingStatus/e:CurrentPrice") or _num(it, "e:BuyItNowPrice"),
                    "quantite": _num(it, "e:QuantityAvailable"), "debut": _txt(it, "e:ListingDetails/e:StartTime"),
                    "photo": _txt(it, "e:PictureDetails/e:GalleryURL"), "watchers": int(_num(it, "e:WatchCount") or 0),
                    "categorie": _txt(it, "e:PrimaryCategory/e:CategoryID")})
    pages = _txt(racine, "e:ActiveList/e:PaginationResult/e:TotalNumberOfPages")
    return out, int(pages) if pages.isdigit() else 1


def annonces_actives():
    tout, page, pages = [], 1, 1
    while page <= pages and page <= 50:
        corps = ('<?xml version="1.0" encoding="utf-8"?>'
                 '<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
                 "<ActiveList><Include>true</Include><IncludeWatchCount>true</IncludeWatchCount>"
                 "<Pagination><EntriesPerPage>200</EntriesPerPage>"
                 f"<PageNumber>{page}</PageNumber></Pagination></ActiveList>"
                 "<DetailLevel>ReturnAll</DetailLevel></GetMyeBaySellingRequest>")
        req = urllib.request.Request(url("trading"), data=corps.encode(), method="POST", headers={
            "X-EBAY-API-SITEID": SITE_ID, "X-EBAY-API-COMPATIBILITY-LEVEL": NIVEAU, "X-EBAY-API-CALL-NAME": "GetMyeBaySelling",
            "X-EBAY-API-IAF-TOKEN": jeton(), "Content-Type": "text/xml"})
        appels_ebay.exiger("trading", fond=True)
        appels_ebay.compter("trading")
        with urllib.request.urlopen(req, timeout=40) as r:
            lot, pages = lire_annonces_xml(r.read())
        tout += lot
        page += 1
    return tout


def lire_commandes(payload):
    """Lignes de vente d'une page getOrders : une par article vendu."""
    out = []
    for o in payload.get("orders") or []:
        lignes = o.get("lineItems") or []
        frais_cmd = float(((o.get("totalMarketplaceFee") or {}).get("value")) or 0) or None
        base_tot = sum(float((l.get("lineItemCost") or {}).get("value") or 0) for l in lignes) or 1.0
        for l in lignes:
            prix = float((l.get("lineItemCost") or {}).get("value") or 0)
            port = float(((l.get("deliveryCost") or {}).get("shippingCost") or {}).get("value") or 0)
            out.append({"transaction_id": f"api:{o.get('orderId')}:{l.get('lineItemId')}", "item_number": str(l.get("legacyItemId") or ""),
                        "titre": l.get("title") or "", "sku": l.get("sku") or "", "prix": prix, "port_charge": port,
                        "frais_reels": round(frais_cmd * prix / base_tot, 2) if frais_cmd else None,
                        "date": str(o.get("creationDate") or "")[:10], "acheteur": (o.get("buyer") or {}).get("username") or "",
                        "statut_paiement": o.get("orderPaymentStatus"), "annulee": (o.get("cancelStatus") or {}).get("cancelState") == "CANCELED"})
    return out


def lire_transactions_xml(brut):
    """(ventes, nb_pages) d'une reponse GetSellerTransactions - meme format que lire_commandes."""
    racine = ET.fromstring(brut)
    ack = _txt(racine, "e:Ack")
    if ack not in ("Success", "Warning"):
        raise RuntimeError(_txt(racine, "e:Errors/e:LongMessage") or f"eBay : Ack={ack}")
    out = []
    for t in racine.findall("e:TransactionArray/e:Transaction", _NS):
        iid, tid = _txt(t, "e:Item/e:ItemID"), _txt(t, "e:TransactionID")
        if not iid:
            continue
        statut = _txt(t, "e:Status/e:CompleteStatus") or ""
        out.append({"transaction_id": f"trd:{iid}:{tid}", "item_number": iid,
                    "titre": _txt(t, "e:Item/e:Title") or "", "sku": _txt(t, "e:Item/e:SKU") or "",
                    "prix": _num(t, "e:TransactionPrice") or 0.0,
                    "port_charge": _num(t, "e:ShippingServiceSelected/e:ShippingServiceCost") or 0.0,
                    "frais_reels": None, "date": (_txt(t, "e:CreatedDate") or "")[:10],
                    "acheteur": _txt(t, "e:Buyer/e:UserID") or "",
                    "statut_paiement": "PAID" if _txt(t, "e:PaidTime") else "PENDING",
                    "annulee": statut.lower() == "canceled" or bool(_txt(t, "e:ContainingOrder/e:CancelStatus") == "CancelComplete"),
                    "source": "trading"})
    pages = _txt(racine, "e:PaginationResult/e:TotalNumberOfPages") or "1"
    return out, int(pages) if pages.isdigit() else 1


def ventes_trading(jours=30):
    """22 oct 2026 - 2e source des ventes (API Trading, GetSellerTransactions) : la nouvelle API
    des commandes tarde parfois (sandbox surtout). Frais estimes ici ; les frais reels arrivent
    par commandes() et remplacent l'estimation (voir lockerroom._maj_ventes)."""
    tout, page, pages = [], 1, 1
    while page <= pages and page <= 20:
        corps = ('<?xml version="1.0" encoding="utf-8"?>'
                 '<GetSellerTransactionsRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
                 f"<NumberOfDays>{max(1, min(30, int(jours)))}</NumberOfDays>"
                 f"<Pagination><EntriesPerPage>200</EntriesPerPage><PageNumber>{page}</PageNumber></Pagination>"
                 "<DetailLevel>ReturnAll</DetailLevel></GetSellerTransactionsRequest>")
        r = trading("GetSellerTransactions", corps, fond=True)
        lot, pages = lire_transactions_xml(ET.tostring(r))
        tout += lot
        page += 1
    return tout


def achats(jours=90):
    """25 oct 2026 (Mathieu : « sur Hall of Cardz tu as ete capable d'aller chercher mon cout d'acquisition dans eBay ») :
    tout ce que le compte a ACHETE ou gagne sur eBay (Trading GetOrders, role acheteur, 90 jours max), avec le cout
    REEL paye (prix + port + taxes percues par eBay), reparti au prorata du prix dans une commande a plusieurs articles."""
    fin = datetime.now(timezone.utc)
    debut = fin - timedelta(days=min(90, int(jours)))
    f = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    out, page, pages = [], 1, 1
    while page <= pages and page <= 20:
        corps = ('<?xml version="1.0" encoding="utf-8"?><GetOrdersRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
                 f"<CreateTimeFrom>{f(debut)}</CreateTimeFrom><CreateTimeTo>{f(fin)}</CreateTimeTo>"
                 "<OrderRole>Buyer</OrderRole><OrderStatus>All</OrderStatus>"
                 f"<Pagination><EntriesPerPage>100</EntriesPerPage><PageNumber>{page}</PageNumber></Pagination>"
                 "<DetailLevel>ReturnAll</DetailLevel></GetOrdersRequest>")
        r = trading("GetOrders", corps, fond=True)
        for o in r.findall("e:OrderArray/e:Order", _NS):
            if (_txt(o, "e:OrderStatus") or "") in ("Cancelled", "CancelPending", "Inactive"):
                continue
            trans = o.findall("e:TransactionArray/e:Transaction", _NS)
            paye = _num(o, "e:AmountPaid") or _num(o, "e:Total")
            el = o.find("e:AmountPaid", _NS)
            devise = el.get("currencyID") if el is not None else None
            base = sum((_num(t, "e:TransactionPrice") or 0) * int(_txt(t, "e:QuantityPurchased") or 1) for t in trans) or 0
            for t in trans:
                iid = _txt(t, "e:Item/e:ItemID")
                if not iid:
                    continue
                qte = int(_txt(t, "e:QuantityPurchased") or 1)
                prix = _num(t, "e:TransactionPrice")
                part = (prix or 0) * qte / base if base else 1 / max(1, len(trans))
                out.append({"item_id": iid, "titre": _txt(t, "e:Item/e:Title") or "", "quantite": qte, "prix": prix,
                            "cout_total": round(paye * part, 2) if paye is not None else None, "devise": devise,
                            "date": (_txt(o, "e:CreatedTime") or "")[:10], "commande": _txt(o, "e:OrderID")})
        try:
            pages = int(_txt(r, "e:PaginationResult/e:TotalNumberOfPages") or 1)
        except ValueError:
            pages = 1
        page += 1
    return out


def photo_item(item_id):
    """Photo d'une de TES annonces, meme terminee (90 jours) : Trading GetItem, seulement les photos."""
    item_id = str(item_id or "").strip()
    if not re.fullmatch(r"\d{9,15}", item_id):
        return None
    corps = ('<?xml version="1.0" encoding="utf-8"?><GetItemRequest xmlns="urn:ebay:apis:eBLBaseComponents">'
             f"<ItemID>{item_id}</ItemID><OutputSelector>PictureDetails</OutputSelector></GetItemRequest>")
    try:
        r = trading("GetItem", corps, fond=True)
    except RuntimeError as e:
        if "eBay a refusé" in str(e):
            return None
        raise
    return _txt(r, "e:Item/e:PictureDetails/e:GalleryURL") or _txt(r, "e:Item/e:PictureDetails/e:PictureURL")


def commandes(jours=90):
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    tout, offset = [], 0
    while offset < 5000:
        q = urllib.parse.urlencode({"filter": f"creationdate:[{depuis}..]", "limit": 200, "offset": offset})
        p = _get_json(url("commandes") + "?" + q)
        tout += lire_commandes(p)
        offset += 200
        if offset >= int(p.get("total") or 0):
            break
    return tout


def noter_synchro(bilan):
    j = _lire(chemin_jetons())
    j.update(derniere_synchro=datetime.now().isoformat(timespec="seconds"), bilan_synchro=bilan)
    _ecrire(chemin_jetons(), j)


# -- marche (API Browse, jeton d'application : aucune donnee du compte) ----------------------
TAUX_CAD = {"CAD": 1.0, "USD": 1.38}


def _taux_vers_cad(dev):
    """27 oct 2026 (revue) : le meme taux USD -> CAD que SoldComps (Banque du Canada, du jour) ; devise inconnue : None."""
    if dev == "CAD":
        return 1.0
    if dev == "USD":
        if time.time() - _TAUX_MEMO[1] > 600:
            try:
                import vendues
                _TAUX_MEMO[:] = [float(vendues._taux_usd_cad()), time.time()]
            except Exception:
                _TAUX_MEMO[:] = [TAUX_CAD["USD"], time.time()]
        return _TAUX_MEMO[0]
    return None


_TAUX_MEMO = [TAUX_CAD["USD"], 0.0]


def jeton_application():
    ch = chemin_jetons()
    with _verrou_de(ch):
        j = _lire(ch)
        if j.get("app_token") and j.get("app_expire_a", 0) > time.time() + MARGE_S:
            return j["app_token"]
        p, err = _post_jeton({"grant_type": "client_credentials", "scope": SCOPES[0]})
        if err:
            raise RuntimeError("eBay a refusé la connexion de l'app : réessaie dans un instant" if err == "invalid_grant" else err)
        j2 = _lire(ch)
        j2.update(app_token=p["access_token"], app_expire_a=time.time() + int(p.get("expires_in", 7200)))
        _ecrire(ch, j2)
        return j2["app_token"]


def rechercher(q, categorie=None, prix_max=None, recentes=False, limite=50, fond=True, encheres=False, flux=False, offset=0, vendeurs=None, frais=False):
    """Annonces actives a prix fixe semblables : [{item_id, titre, prix_cad, url, photo}].
    Cache partage (24 h ; 6 h pour les nouveautes) et compteur d'appels (appels_ebay).
    24 oct 2026 - encheres=True : les encans qui finissent le plus tot (prix = mise actuelle, fin, nb de mises)."""
    cle = appels_ebay.cle_recherche(environnement(), q=q[:100], categorie=categorie,
                                     prix_max=round(float(prix_max), 2) if prix_max else None, recentes=bool(recentes), limite=int(limite),
                                     **({"encheres": True} if encheres else {}), **({"flux": True} if flux else {}), **({"offset": int(offset)} if offset else {}),
                                     **({"vendeurs": "|".join(sorted(vendeurs))} if vendeurs else {}))
    # 26 oct 2026 (Mathieu : « on doit trouver le maximum ») : flux = les nouvelles annonces chaque heure (cache 50 min)
    # 31 oct 2026 : frais=True (encans qui finissent bientot chez les gros vendeurs, aux 15 min) : jamais le cache
    deja = None if frais else appels_ebay.cache_lire(cle, "flux" if flux else "encheres" if encheres else "recentes" if recentes else "marche")
    if deja is not None:
        return deja
    appels_ebay.exiger("browse", fond)
    filtres = ["buyingOptions:{AUCTION}" if encheres else "buyingOptions:{FIXED_PRICE}"]
    if prix_max:
        filtres.append(f"price:[..{float(prix_max):.2f}]")
        filtres.append("priceCurrency:CAD")
    # 29 oct 2026 (Mathieu : « les encans de savage, remi, cf_31, dc sports 87, slab shark… je les veux TOUS ») : les annonces
    # de vendeurs precis (filtre officiel « sellers » de la Browse API) ; sans mot-cle, la categorie suffit
    if vendeurs:
        filtres.append("sellers:{" + "|".join(re.sub(r"[^A-Za-z0-9._-]", "", v)[:64] for v in vendeurs if v)[:900] + "}")
    p = {"limit": max(1, min(200, int(limite))), "filter": ",".join(filtres)}
    if q:
        p["q"] = q[:100]
    if offset:
        p["offset"] = int(offset)
    if categorie:
        p["category_ids"] = categorie
    if recentes:
        p["sort"] = "newlyListed"
    if encheres:
        p["sort"] = "endingSoonest"
    adresse = url("recherche") + "?" + urllib.parse.urlencode(p, quote_via=urllib.parse.quote)
    req = urllib.request.Request(adresse, headers={"Authorization": "Bearer " + jeton_application(), "Accept": "application/json",
                                               "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA",
                                               # 27 oct 2026 : le port affiche = le port vers le Canada (pas de faux prix)
                                               "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DCA"})
    appels_ebay.compter("browse")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"eBay HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:200]}")
    res = lire_recherche(d)
    appels_ebay.cache_ecrire(cle, res)
    return res


def _lire_article(d, item_id):
    """Une annonce Browse (getItem / getItems) -> le dict de SlabCoach (prix en $ CA, port, fin, mises...)."""
    pr = d.get("currentBidPrice") or d.get("price") or {}
    dev = pr.get("currency") or "CAD"
    t = _taux_vers_cad(dev) or 0.0              # devise inconnue : prix 0 -> l'annonce n'est pas jugee
    opt = (d.get("shippingOptions") or [{}])[0]
    port = (opt.get("shippingCost") or {}).get("value")
    imgs = [x.get("imageUrl") for x in [d.get("image") or {}] + (d.get("additionalImages") or []) if x.get("imageUrl")]
    vend = d.get("seller") or {}
    return {"item_id": item_id, "titre": d.get("title") or "", "prix_cad": round(float(pr.get("value") or 0) * t, 2),
           "port_cad": round(float(port) * t, 2) if port not in (None, "") else None, "photos": imgs[:12],
           "photo": imgs[0] if imgs else "", "url": d.get("itemWebUrl") or "", "etat": d.get("condition") or "",
           "vendeur": vend.get("username") or "", "vendeur_pct": vend.get("feedbackPercentage"), "vendeur_score": vend.get("feedbackScore"),
           "fin": d.get("itemEndDate"), "mises": d.get("bidCount"), "encan": "AUCTION" in (d.get("buyingOptions") or []),
           "lieu": ((d.get("itemLocation") or {}).get("country") or ""), "service": opt.get("shippingServiceCode") or "",
           "retours": bool((d.get("returnTerms") or {}).get("returnsAccepted")),
           # 31 oct 2026 (mises rapides Gixen) : la devise de l'ANNONCE (une mise se fait dans cette devise, pas en CAD)
           "devise": pr.get("convertedFromCurrency") or dev,
           "prix_devise": float(pr.get("convertedFromValue") or pr.get("value") or 0)}


def article(item_id, fond=False, frais=False):
    """24 oct 2026 - une annonce eBay complete (toutes ses photos, vendeur, livraison, fin) : Browse getItem,
    jeton d'application (aucune donnee de compte). Cache 1 h."""
    item_id = str(item_id or "").strip()
    if not re.fullmatch(r"\d{9,15}", item_id):
        raise RuntimeError("Numéro d'annonce eBay invalide")
    cle = appels_ebay.cle_recherche(environnement(), article=item_id)
    deja = appels_ebay.cache_lire(cle, "article_frais" if frais else "encheres")     # 29 oct : watchlist, fin d'encan : 3 min
    if deja is not None:
        return deja
    appels_ebay.exiger("browse", fond)
    adresse = url("recherche").split("/item_summary/")[0] + "/item/get_item_by_legacy_id?" + urllib.parse.urlencode({"legacy_item_id": item_id})
    req = urllib.request.Request(adresse, headers={"Authorization": "Bearer " + jeton_application(), "Accept": "application/json",
                                               "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA",
                                               # 27 oct 2026 : le port affiche = le port vers le Canada (pas de faux prix)
                                               "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DCA"})
    appels_ebay.compter("browse")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"eBay HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:160]}")
    res = _lire_article(d, item_id)
    appels_ebay.cache_ecrire(cle, res)
    return res


def lire_recherche(d):
    out = []
    for it in d.get("itemSummaries") or []:
        pr = it.get("currentBidPrice") or it.get("price") or {}
        dev = pr.get("currency") or "CAD"
        if dev not in TAUX_CAD or not pr.get("value"):
            continue
        port = ((it.get("shippingOptions") or [{}])[0].get("shippingCost") or {}).get("value")
        out.append({"item_id": str(it.get("legacyItemId") or it.get("itemId") or ""), "titre": it.get("title") or "",
                    "prix_cad": round(float(pr["value"]) * _taux_vers_cad(dev), 2),
                    "port_cad": round(float(port) * _taux_vers_cad(dev), 2) if port not in (None, "") else None,
                    "url": it.get("itemWebUrl") or "", "photo": (it.get("image") or {}).get("imageUrl") or "",
                    "vendeur": (it.get("seller") or {}).get("username") or "",
                    "vendeur_pct": (it.get("seller") or {}).get("feedbackPercentage"),
                    "vendeur_score": (it.get("seller") or {}).get("feedbackScore"),
                    "fin": it.get("itemEndDate"), "mises": it.get("bidCount"),
                    "encan": "AUCTION" in (it.get("buyingOptions") or [])})
    return out


# -- appels Trading generiques (ecriture : toujours declenches par un tap du vendeur) ------------
def trading(appel, corps, fond=False):
    """POST Trading API -> racine XML ; erreur claire si eBay refuse (Ack=Failure)."""
    appels_ebay.exiger("trading", fond)
    appels_ebay.compter("trading")
    req = urllib.request.Request(url("trading"), data=corps.encode("utf-8"), method="POST", headers={
        "X-EBAY-API-SITEID": SITE_ID, "X-EBAY-API-COMPATIBILITY-LEVEL": NIVEAU, "X-EBAY-API-CALL-NAME": appel,
        "X-EBAY-API-IAF-TOKEN": jeton(), "Content-Type": "text/xml"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            racine = ET.fromstring(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"eBay HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:200]}")
    ack = _txt(racine, "e:Ack")
    if ack not in ("Success", "Warning"):
        msgs = [(_txt(er, "e:LongMessage") or _txt(er, "e:ShortMessage")) for er in racine.findall("e:Errors", _NS)
                if _txt(er, "e:SeverityCode") != "Warning"]
        raise RuntimeError("eBay a refusé : " + (" · ".join(m for m in msgs if m) or f"Ack={ack}"))
    return racine


def avertissements(racine):
    return [(_txt(er, "e:ShortMessage") or _txt(er, "e:LongMessage")) for er in racine.findall("e:Errors", _NS)
            if _txt(er, "e:SeverityCode") == "Warning"]


def post_json(adresse, corps, marketplace="EBAY_CA"):
    api = "offer" if "/buy/offer/" in adresse else "autre"
    appels_ebay.exiger(api, fond=False) if api in appels_ebay.LIMITES else None
    appels_ebay.compter(api)
    req = urllib.request.Request(adresse, data=json.dumps(corps).encode(), method="POST", headers={
        "Authorization": "Bearer " + jeton(), "Content-Type": "application/json", "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": marketplace})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            brut = r.read()
            return json.loads(brut) if brut else {}
    except urllib.error.HTTPError as e:
        texte = e.read().decode("utf-8", "ignore")
        try:
            d = json.loads(texte)
            msg = " · ".join(x.get("longMessage") or x.get("message") or "" for x in d.get("errors") or [])
        except ValueError:
            msg = texte[:200]
        if e.code in (401, 403):
            raise RuntimeError("eBay refuse cet accès (" + str(e.code) + ") : " + (msg or "permission manquante")
                               + (" — en production, les mises demandent l'approbation d'eBay (API Offer)" if "/bidding" in adresse else ""))
        raise RuntimeError(f"eBay HTTP {e.code} : {msg}")


def articles_lot(item_ids, fond=True):
    """31 oct 2026 (Mathieu : « les cartes qui arrivent a la fin, 2 dernieres heures : rafraichir le prix eBay souvent, le
    deal change et peut vite devenir un faux deal ») : jusqu'a 20 annonces en UN appel (Browse getItems), jamais le cache.
    -> {item_id: article} ; une annonce absente de la reponse (finie, retiree) n'y est pas."""
    ids = [str(i).strip() for i in item_ids if re.fullmatch(r"\d{9,15}", str(i).strip())][:20]
    if not ids:
        return {}
    appels_ebay.exiger("browse", fond)
    adresse = url("recherche").split("/item_summary/")[0] + "/item/?" + urllib.parse.urlencode({"item_ids": ",".join(f"v1|{i}|0" for i in ids)})
    req = urllib.request.Request(adresse, headers={"Authorization": "Bearer " + jeton_application(), "Accept": "application/json",
                                               "X-EBAY-C-MARKETPLACE-ID": "EBAY_CA", "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3DCA"})
    appels_ebay.compter("browse")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"eBay HTTP {e.code} : {e.read().decode('utf-8', 'ignore')[:160]}")
    out = {}
    for it in d.get("items") or []:
        iid = str(it.get("legacyItemId") or "").strip()
        if not iid and it.get("itemId"):
            parts = str(it["itemId"]).split("|")
            iid = parts[1] if len(parts) > 1 else ""
        if iid:
            out[iid] = _lire_article(it, iid)
    return out
