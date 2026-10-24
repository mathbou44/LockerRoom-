"""Abonnement Pro (Stripe) : python tests/test_paiements.py  (demande flask et cryptography). Aucun appel reseau."""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json, time, hmac, hashlib, urllib.parse, io
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, ebay_compte, paiements, ebay_avis
    ebay_compte._post_jeton = lambda d: ({"access_token": "AT", "expires_in": 7200, "refresh_token": "RT", "refresh_token_expires_in": 47304000}, None)
    ebay_compte._identite = lambda t: {"userId": "uid-A", "username": "vendeur"}
    server._premiere_synchro = lambda cid: None

    # Stripe simule : on note les appels, on repond comme Stripe
    APPELS = []
    ABO = {"id": "sub_1", "customer": "cus_1", "status": "active", "metadata": {}, "cancel_at_period_end": False,
           "items": {"data": [{"current_period_end": 1790000000}]}}
    def faux(methode, chemin, params=None, ouvrir=None):
        APPELS.append((methode, chemin, paiements._form(params or {})))
        if chemin.startswith("prices/"):
            return {"unit_amount": 100, "currency": "cad", "recurring": {"interval": "month"}}
        if chemin == "checkout/sessions":
            return {"url": "https://checkout.stripe.com/c/pay/cs_test_1"}
        if chemin == "billing_portal/sessions":
            return {"url": "https://billing.stripe.com/p/session/1"}
        if chemin.startswith("subscriptions/"):
            return ABO
        raise AssertionError(chemin)
    paiements._appel = faux

    c = server.app.test_client()
    loc = c.get("/auth/ebay").headers["Location"]
    etat = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
    c.get("/api/ebay_retour?state=%%s&code=C" %% etat)
    cid = comptes.lister()[0]
    ABO["metadata"]["compte"] = cid

    f = c.post("/api/forfait", json=[]).get_json()
    assert f["multi"] and f["forfait"] == "gratuit" and f["paiements"] and f["mode_paiement"] == "test", f
    # 24 oct 2026 : nouveau compte = essai Pro de 14 jours (photos illimitees), puis 25 photos par mois
    assert f["prix"] == {"montant": 1.0, "devise": "CAD", "intervalle": "month"} and f["essai"] and f["photos_limite"] is None, f
    comptes.maj(cid, cree_le="2026-01-01T00:00:00")
    f = c.post("/api/forfait", json=[]).get_json()
    assert not f["essai"] and not f["pro"] and f["photos_limite"] == 25, f
    # l'ecran ne peut PAS se donner Pro
    c.post("/api/reglages_sauver", json=[{"forfait": "pro"}])
    assert c.post("/api/forfait", json=[]).get_json()["forfait"] == "gratuit"
    r = c.post("/api/abonnement_payer", json=[]).get_json()
    assert r["ok"] and r["url"].startswith("https://checkout.stripe.com"), r
    p = dict(APPELS[-1][2])
    assert p["mode"] == "subscription" and p["client_reference_id"] == cid and p["line_items[0][price]"] == "price_test_pro"
    assert p["subscription_data[metadata][compte]"] == cid and p["success_url"].endswith("/#reglages/pro-ok")

    SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
    def envoyer(ev, secret=SECRET, decalage=0):
        corps = json.dumps(ev).encode()
        t = str(int(time.time()) - decalage)
        sig = hmac.new(secret.encode(), t.encode() + b"." + corps, hashlib.sha256).hexdigest()
        return c.post("/stripe/webhook", data=corps, headers={"Stripe-Signature": "t=%%s,v1=%%s" %% (t, sig), "Content-Type": "application/json"})

    paye = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"mode": "subscription",
            "client_reference_id": cid, "customer": "cus_1", "subscription": "sub_1"}}}
    assert envoyer(paye, secret="whsec_faux").status_code == 400          # signature d'un autre
    assert envoyer(paye, decalage=900).status_code == 400                  # trop vieux (rejeu)
    assert c.post("/stripe/webhook", data=b"{}").status_code == 400        # pas de signature
    assert comptes.info(cid).get("forfait") is None
    assert envoyer(paye).status_code == 200
    i = comptes.info(cid)
    assert i["forfait"] == "pro" and i["stripe_client"] == "cus_1" and i["forfait_fin"] == 1790000000, i
    assert envoyer(paye).get_json()["recu"] == "déjà traité"
    f = c.post("/api/forfait", json=[]).get_json()
    assert f["forfait"] == "pro" and f["photos_limite"] is None and f["client"], f
    assert c.post("/api/abonnement_gerer", json=[]).get_json()["url"].startswith("https://billing.stripe.com")

    # annulation demandee : Pro jusqu'a la fin de la periode, puis gratuit
    ABO.update(cancel_at_period_end=True)
    envoyer({"id": "evt_2", "type": "customer.subscription.updated", "data": {"object": {"id": "sub_1", "customer": "cus_1", "metadata": {"compte": cid}}}})
    assert comptes.info(cid)["forfait"] == "pro" and comptes.info(cid)["forfait_annule"] is True
    ABO.update(status="canceled")
    envoyer({"id": "evt_3", "type": "customer.subscription.deleted", "data": {"object": {"id": "sub_1", "customer": "cus_1", "metadata": {}}}})
    assert comptes.info(cid)["forfait"] == "gratuit"
    # un abonnement sans metadonnee retrouve le compte par son client Stripe
    ABO.update(status="active", metadata={})
    envoyer({"id": "evt_4", "type": "customer.subscription.created", "data": {"object": {"id": "sub_1", "customer": "cus_1", "metadata": {}}}})
    assert comptes.info(cid)["forfait"] == "pro"

    # avis de suppression eBay : jeton et adresse donnes par Render
    d = ebay_avis.reponse_defi("abc")
    attendu = hashlib.sha256(("abc" + os.environ["LOCKERROOM_EBAY_AVIS_JETON"] + "https://lr.onrender.com/ebay/suppression-compte").encode()).hexdigest()
    assert d["challengeResponse"] == attendu
    assert c.get("/ebay/suppression-compte?challenge_code=abc").get_json()["challengeResponse"] == attendu
    assert ebay_avis.jeton_valide(os.environ["LOCKERROOM_EBAY_AVIS_JETON"]) and not ebay_avis.jeton_valide("a+b")
    assert c.post("/api/reglages_lire", json=[]).get_json()["epn_campid"] == "5339000001"
    print("PAIEMENTS OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="production",
               LOCKERROOM_EBAY_APP_ID="App-PRD-1234", LOCKERROOM_EBAY_CERT_ID="Cert-5678", LOCKERROOM_EBAY_RUNAME="Ru-9999",
               STRIPE_CLE_SECRETE="sk_test_faux", STRIPE_PRIX_PRO="price_test_pro", STRIPE_WEBHOOK_SECRET="whsec_test",
               RENDER_EXTERNAL_URL="https://lr.onrender.com", LOCKERROOM_EBAY_AVIS_JETON="J" * 40, LOCKERROOM_EPN_CAMPID="5339000001")
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-2500:])
    sys.exit(0 if "PAIEMENTS OK" in r.stdout else 1)
