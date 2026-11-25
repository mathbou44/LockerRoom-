"""
LOCKERROOM - abonnement Pro par Stripe (24 oct 2026).

Mathieu : « activer le mode de paiement pour test si tout fonctionne ... Gratuit +
Pro a 1 $ pour faire tester mes proches ». Choix : Stripe (2,9 % + 0,30 $ CA par
carte + 0,7 % Billing ; mode test gratuit ; page de paiement et portail client
heberges par Stripe : aucun numero de carte ne touche SlabCoach).

  - Le prix vit dans Stripe (STRIPE_PRIX_PRO = un price_...) : le changer = 1 clic
    dans Stripe, rien a redeployer.
  - Le forfait du client est ecrit UNIQUEMENT par l'avis signe de Stripe (webhook) :
    jamais par l'ecran (impossible de se donner Pro en appelant l'API).
  - Cle sk_test_... = mode test (cartes 4242...), sk_live_... = vrais paiements.

Variables (Render) : STRIPE_CLE_SECRETE, STRIPE_PRIX_PRO, STRIPE_WEBHOOK_SECRET.
Aucune dependance : HTTPS direct (urllib), comme le reste de l'app.
"""
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.stripe.com/v1/"
TOLERANCE_S = 300                 # avis plus vieux que 5 min : refuse (rejeu)
EVENEMENTS = ("checkout.session.completed", "customer.subscription.created", "customer.subscription.updated",
              "customer.subscription.deleted")
STATUTS_PRO = ("active", "trialing", "past_due")     # past_due : Stripe reessaie la carte, on ne coupe pas tout de suite
_verrou = threading.Lock()
_cache_prix = {}


class Erreur(Exception):
    pass


def cle():
    return (os.environ.get("STRIPE_CLE_SECRETE") or "").strip()


def prix_pro():
    return (os.environ.get("STRIPE_PRIX_PRO") or "").strip()


def prix_pro_annuel():
    """18 nov 2026 (Mathieu : « une section annuelle avec paiement mensuel, mais pas annulable ; si demande d'annulation, il
    y aura des frais ») : un 2e prix Stripe, MENSUEL et moins cher (STRIPE_PRIX_PRO_ANNUEL = un price_...), avec un
    engagement de 12 mois tenu par SlabCoach : le portail de cet abonnement n'a pas de bouton « Annuler »."""
    return (os.environ.get("STRIPE_PRIX_PRO_ANNUEL") or "").strip()


ENGAGEMENT_MOIS = 12


def frais_annulation(mois_payes, prix_mensuel, prix_engage):
    """Annuler avant 12 mois : on rembourse le rabais deja recu (les mois payes au prix regulier). Jamais negatif."""
    return round(max(0.0, (float(prix_mensuel or 0) - float(prix_engage or 0)) * max(0, int(mois_payes or 0))), 2)


def secret_webhook():
    return (os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()


def actif():
    return bool(cle() and prix_pro())


def mode():
    c = cle()
    return "" if not c else "test" if "_test_" in c else "reel"


def adresse_publique():
    # 24 nov 2026 (vrai paiement de Mathieu : apres avoir paye, Stripe le ramenait sur lockerroom-….onrender.com, ou il
    # n'est PAS connecte : il voyait le site au lieu de son compte Pro) : le retour se fait a l'adresse ou l'utilisateur
    # EST (slabcoach.com ou www.slabcoach.com), comme pour Apple et Google (server._base_publique). L'adresse de Render ne
    # sert plus qu'en dernier recours.
    try:
        from flask import has_request_context, request
        if has_request_context():
            import re
            h = (request.host or "").split(",")[0].strip().lower()
            if re.fullmatch(r"(www\.)?slabcoach\.com", h):
                return "https://" + h
    except Exception:
        pass
    a = (os.environ.get("LOCKERROOM_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    if a:
        return a
    try:
        from flask import has_request_context, request
        if has_request_context():
            return request.host_url.rstrip("/")
    except Exception:
        pass
    return "http://127.0.0.1:8430"


# -- appels a Stripe ---------------------------------------------------------------------------
def _form(d, prefixe=""):
    """{"line_items":[{"price":"p","quantity":1}]} -> [("line_items[0][price]","p"), ...] (format de Stripe)."""
    out = []
    items = d.items() if isinstance(d, dict) else enumerate(d)
    for k, v in items:
        nom = f"{prefixe}[{k}]" if prefixe else str(k)
        if v is None:
            continue
        if isinstance(v, (dict, list, tuple)):
            out += _form(v, nom)
        elif isinstance(v, bool):
            out.append((nom, "true" if v else "false"))
        else:
            out.append((nom, str(v)))
    return out


def _appel(methode, chemin, params=None, ouvrir=None):
    if not cle():
        raise Erreur("Paiements pas encore configurés")
    corps = urllib.parse.urlencode(_form(params or {})).encode() if methode == "POST" else None
    url = API + chemin + ("" if methode == "POST" or not params else "?" + urllib.parse.urlencode(_form(params)))
    req = urllib.request.Request(url, data=corps, method=methode, headers={
        "Authorization": "Bearer " + cle(), "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with (ouvrir or urllib.request.urlopen)(req, timeout=20) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = (json.loads(e.read() or b"{}").get("error") or {}).get("message")
        except Exception:
            msg = None
        raise Erreur(msg or f"Stripe a refusé ({e.code})")
    except urllib.error.URLError:
        raise Erreur("Stripe injoignable : réessaie dans un instant")


def prix_affiche(p=None):
    """{"montant": 1.0, "devise": "CAD", "intervalle": "month"} (garde 1 h ; None si inconnu)."""
    p = p or prix_pro()
    if not actif() or not p:
        return None
    c = _cache_prix.get(p)
    if c and time.time() - c[0] < 3600:
        return c[1]
    try:
        d = _appel("GET", "prices/" + urllib.parse.quote(p))
        r = {"montant": (d.get("unit_amount") or 0) / 100, "devise": str(d.get("currency") or "").upper(),
             "intervalle": (d.get("recurring") or {}).get("interval") or "month"}
    except Erreur:
        return c[1] if c else None
    _cache_prix[p] = (time.time(), r)
    return r


def creer_paiement(compte_id, client=None, essai_jours=0, plan="mensuel"):
    """Page de paiement Stripe (abonnement) -> son adresse. Le compte voyage dans les metadonnees.
    plan « annuel » : le prix engage (mensuel, 12 mois) ; la fin de l'engagement voyage dans les metadonnees."""
    if not actif():
        raise Erreur("Paiements pas encore configurés")
    annuel = plan == "annuel"
    if annuel and not prix_pro_annuel():
        raise Erreur("Le forfait annuel n'est pas encore offert")
    base = adresse_publique()
    meta = {"compte": compte_id}
    if annuel:
        fin = time.gmtime(time.time() + 365 * 86400)
        meta.update(plan="annuel", engagement_fin=time.strftime("%Y-%m-%d", fin))
    p = {"mode": "subscription", "line_items": [{"price": prix_pro_annuel() if annuel else prix_pro(), "quantity": 1}],
         "success_url": base + "/#reglages/pro-ok", "cancel_url": base + "/#reglages",
         "client_reference_id": compte_id, "metadata": dict(meta),
         "subscription_data": {"metadata": dict(meta)}, "allow_promotion_codes": True, "locale": "fr-CA"}
    if annuel:
        p["consent_collection"] = {"terms_of_service": "required"}       # la case « j'accepte » (engagement + frais) chez Stripe
        p["custom_text"] = {"terms_of_service_acceptance": {"message": "Engagement de 12 mois, payé chaque mois. Annuler avant la fin : "
                                                                       "frais égaux au rabais déjà reçu sur les mois payés."}}
    if essai_jours:
        p["subscription_data"]["trial_period_days"] = int(essai_jours)
    if client:
        p["customer"] = client
    d = _appel("POST", "checkout/sessions", p)
    if not d.get("url"):
        raise Erreur("Stripe n'a pas donné de page de paiement")
    return d["url"]


def _config_portail_engage():
    """Un portail Stripe SANS bouton « Annuler » (carte et factures seulement), cree une fois, son id garde sur le disque."""
    import comptes
    ch = os.path.join(comptes.DONNEES, "stripe_portail_engage.json")
    try:
        with open(ch, encoding="utf-8") as f:
            d = json.load(f) or {}
        if d.get("id") and d.get("cle") == mode():
            return d["id"]
    except (OSError, ValueError):
        pass
    r = _appel("POST", "billing_portal/configurations", {
        "features": {"subscription_cancel": {"enabled": False}, "payment_method_update": {"enabled": True},
                     "invoice_history": {"enabled": True}, "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]}},
        "business_profile": {"headline": "SlabCoach Pro · engagement de 12 mois"}})
    with open(ch, "w", encoding="utf-8") as f:
        json.dump({"id": r.get("id"), "cle": mode()}, f)
    return r.get("id")


def portail(client, engage=False):
    """Portail client Stripe : carte, factures, annulation (sans annulation pendant un engagement de 12 mois)."""
    if not client:
        raise Erreur("Aucun abonnement à gérer")
    p = {"customer": client, "return_url": adresse_publique() + "/#reglages"}
    if engage:
        p["configuration"] = _config_portail_engage()
    d = _appel("POST", "billing_portal/sessions", p)
    return d["url"]


# -- avis signes de Stripe (webhook) -----------------------------------------------------------
def verifier_signature(corps, entete, secret=None, maintenant=None, tolerance=TOLERANCE_S):
    """En-tete Stripe-Signature « t=...,v1=... » : HMAC-SHA256 de « t.corps » avec le secret whsec_."""
    secret = secret if secret is not None else secret_webhook()
    if not secret or not entete:
        return False
    t, sigs = None, []
    for morceau in str(entete).split(","):
        k, _, v = morceau.strip().partition("=")
        if k == "t":
            t = v
        elif k == "v1":
            sigs.append(v)
    if not t or not sigs or not t.isdigit():
        return False
    if abs((maintenant or time.time()) - int(t)) > tolerance:
        return False
    corps = corps if isinstance(corps, bytes) else str(corps).encode()
    attendu = hmac.new(secret.encode(), t.encode() + b"." + corps, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(attendu, s) for s in sigs)


def _fin_periode(abo):
    fin = abo.get("current_period_end")
    if not fin:                                     # versions recentes de l'API : sur l'article
        items = ((abo.get("items") or {}).get("data") or [])
        fin = items[0].get("current_period_end") if items else None
    return int(fin) if fin else None


def _depuis_abonnement(abo):
    statut = abo.get("status") or ""
    meta = abo.get("metadata") or {}
    return {"forfait": "pro" if statut in STATUTS_PRO else "gratuit", "forfait_statut": statut, "forfait_source": "stripe",
            "forfait_plan": "annuel" if meta.get("plan") == "annuel" else "mensuel", "engagement_fin": meta.get("engagement_fin"),
            "forfait_debut": abo.get("start_date"),
            "stripe_client": abo.get("customer"), "stripe_abonnement": abo.get("id"),
            "forfait_fin": _fin_periode(abo), "forfait_annule": bool(abo.get("cancel_at_period_end"))}


def traiter(ev, relire=True):
    """Evenement Stripe -> (compte, champs a ecrire) ou None. L'abonnement est relu chez Stripe
    (les avis peuvent arriver dans le desordre : on prend toujours son etat actuel)."""
    t = ev.get("type")
    o = ((ev.get("data") or {}).get("object")) or {}
    if t not in EVENEMENTS:
        return None
    if t == "checkout.session.completed":
        cid = o.get("client_reference_id") or (o.get("metadata") or {}).get("compte")
        if o.get("mode") != "subscription" or not cid:
            return None
        champs = {"forfait": "pro", "forfait_statut": "active", "forfait_source": "stripe", "stripe_client": o.get("customer"),
                  "stripe_abonnement": o.get("subscription")}
        if relire and o.get("subscription"):
            try:
                champs.update(_depuis_abonnement(_appel("GET", "subscriptions/" + o["subscription"])))
            except Erreur:
                pass
        return cid, champs
    abo = o
    if relire and o.get("id"):
        try:
            abo = _appel("GET", "subscriptions/" + o["id"])
        except Erreur:
            abo = o
    cid = (abo.get("metadata") or {}).get("compte") or (o.get("metadata") or {}).get("compte")
    champs = _depuis_abonnement(abo)
    if t == "customer.subscription.deleted":
        champs.update(forfait="gratuit", forfait_statut="canceled", forfait_annule=False)
    return (cid, champs) if cid else ("client:" + str(abo.get("customer") or ""), champs)


def _chemin_vus():
    import comptes
    return os.path.join(comptes.DONNEES, "stripe_evenements.json")


def deja_vu(ev_id):
    """Stripe peut envoyer le meme avis deux fois : on garde les 500 derniers identifiants."""
    if not ev_id:
        return False
    with _verrou:
        try:
            with open(_chemin_vus(), encoding="utf-8") as f:
                vus = json.load(f) or []
        except (OSError, ValueError):
            vus = []
        if ev_id in vus:
            return True
        vus = (vus + [ev_id])[-500:]
        tmp = _chemin_vus() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(vus, f)
        os.replace(tmp, _chemin_vus())
    return False


def recevoir(corps, entete):
    """Route /stripe/webhook : (code HTTP, message). Ecrit le forfait dans l'index des comptes."""
    if not secret_webhook():
        return 503, "webhook non configuré"
    if not verifier_signature(corps, entete):
        return 400, "signature invalide"
    try:
        ev = json.loads(corps)
    except ValueError:
        return 400, "corps illisible"
    # 24 nov 2026 (audit, capture de Mathieu : « No such subscription ... a similar object exists in test mode ») : un avis du
    # mode TEST etait accepte par le serveur en VRAI mode (le secret du webhook dans Render etait celui du mode test). Meme
    # avec une bonne signature, un avis de l'autre mode n'est jamais applique : il ne peut ni donner ni retirer un forfait.
    if isinstance(ev, dict) and isinstance(ev.get("livemode"), bool) and mode() in ("test", "reel") and ev["livemode"] != (mode() == "reel"):
        print(f"Stripe : avis du mode {'reel' if ev['livemode'] else 'test'} ignore (le serveur est en mode {mode()}). Verifier STRIPE_WEBHOOK_SECRET.", flush=True)
        return 200, "autre mode : ignoré"
    r = traiter(ev)
    if not r:
        return 200, "ignoré"
    if deja_vu(ev.get("id")):
        return 200, "déjà traité"
    import comptes
    cid, champs = r
    if cid.startswith("client:"):
        cid = next(iter(comptes.par_champ("stripe_client", cid[7:])), None)
    if not cid or cid not in comptes.lister():
        return 200, "compte inconnu"
    # 27 oct 2026 (revue) : un AUTRE abonnement du meme compte (ancien, ou pris deux fois) qui finit ne retire pas le Pro
    # de celui qui est encore paye.
    if (comptes.info(cid) or {}).get("forfait_source") == "apple" and champs.get("forfait") != "pro":
        return 200, "Pro Apple : ignoré"            # 27 oct 2026 : un avis Stripe ne retire pas un Pro pris chez Apple
    actuel = (comptes.info(cid) or {}).get("stripe_abonnement")
    if (ev.get("type") or "").startswith("customer.subscription.") and actuel and champs.get("stripe_abonnement") \
            and champs["stripe_abonnement"] != actuel and champs.get("forfait") != "pro" \
            and (comptes.info(cid) or {}).get("forfait") == "pro":
        return 200, "autre abonnement : ignoré"
    comptes.maj(cid, **champs)
    return 200, "ok"
