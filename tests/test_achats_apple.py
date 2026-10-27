"""Achat integre Apple (StoreKit 2) : python tests/test_achats_apple.py  (flask + cryptography). Aucun appel reseau.
Chaine de test avec les extensions Apple, et la VRAIE chaine Apple (certificats des tests officiels d'Apple)."""
import os
import subprocess
import sys
import tempfile
import textwrap

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json, time, base64, urllib.parse
    from datetime import datetime, timedelta, timezone
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes, ebay_compte, achats_apple as aa
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    ebay_compte._post_jeton = lambda d: ({"access_token": "AT", "expires_in": 7200, "refresh_token": "RT", "refresh_token_expires_in": 47304000}, None)
    server._premiere_synchro = lambda cid: None

    # 1. la VRAIE chaine d'Apple passe avec la racine epinglee ; les chaines piegees non
    C = json.load(open("tests/apple_certs_test.json"))
    L = lambda k: x509.load_der_x509_certificate(base64.b64decode(C[k + "_BASE64_ENCODED"]))
    aa.verifier_chaine(L("REAL_APPLE_SIGNING_CERTIFICATE"), L("REAL_APPLE_INTERMEDIATE"), datetime.fromtimestamp(1761962975, tz=timezone.utc))
    for f, i in (("LEAF_CERT_INVALID_OID", "INTERMEDIATE_CA"), ("LEAF_CERT_FOR_INTERMEDIATE_CA_INVALID_OID", "INTERMEDIATE_CA_INVALID_OID")):
        try:
            aa.verifier_chaine(L(f), L(i), datetime(2025, 1, 1, tzinfo=timezone.utc), [L("ROOT_CA")]); raise SystemExit("OID faux accepte")
        except aa.Refus:
            pass

    # 2. une chaine de test a nous (memes extensions qu'Apple) pour signer des transactions
    def cert(nom, cle, emetteur, cle_em, ca, oid=None):
        b = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nom)]))
             .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, emetteur)])).public_key(cle.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(datetime(2024, 1, 1, tzinfo=timezone.utc))
             .not_valid_after(datetime(2035, 1, 1, tzinfo=timezone.utc))
             .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
        if oid:
            b = b.add_extension(x509.UnrecognizedExtension(oid, b"\\x05\\x00"), critical=False)
        return b.sign(cle_em, hashes.SHA384() if ca else hashes.SHA256())
    kr, ki, kf = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
    racine = cert("Racine test", kr, "Racine test", kr, True)
    inter = cert("Inter test", ki, "Racine test", kr, True, aa.OID_INTER)
    feuille = cert("Signature test", kf, "Inter test", ki, False, aa.OID_FEUILLE)
    aa._racines = lambda: [racine]
    b64u = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    def signe(d):
        t = b64u(json.dumps({"alg": "ES256", "x5c": [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode() for c in (feuille, inter, racine)]}).encode())
        c_ = b64u(json.dumps(d).encode())
        r, s = decode_dss_signature(kf.sign((t + "." + c_).encode(), ec.ECDSA(hashes.SHA256())))
        return t + "." + c_ + "." + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    maint = time.time()
    def tx(jeton, orig="2000000001", jours=30, **k):
        d = {"bundleId": "com.slabcoach.app", "productId": aa.produit(), "environment": "Sandbox", "appAccountToken": jeton,
             "originalTransactionId": orig, "transactionId": orig + "9", "expiresDate": int((maint + jours * 86400) * 1000),
             "signedDate": int(maint * 1000)}
        d.update(k)
        return d

    # 3. un compte, son jeton, un achat
    def compte(uid):
        ebay_compte._identite = lambda t: {"userId": uid, "username": "v-" + uid}
        c = server.app.test_client()
        loc = c.get("/auth/ebay").headers["Location"]
        etat = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)["state"][0]
        c.get("/api/ebay_retour?state=%%s&code=C" %% etat)
        return c
    a = compte("uid-A")
    info = a.post("/api/apple_achat_info", json=[]).get_json()
    assert info["ok"] and info["produit"] == "com.slabcoach.app.pro.mensuel" and len(info["jeton"]) == 36, info
    cid = next(x for x in comptes.lister() if comptes.info(x).get("ebay_user_id") == "uid-A")
    # l'essai gratuit ne compte pas : on le termine pour voir le vrai effet de l'achat
    comptes.maj(cid, cree_le="2020-01-01T00:00:00")
    assert not a.post("/api/forfait", json=[]).get_json()["pro"]
    j = signe(tx(info["jeton"]))
    r = a.post("/api/apple_achat_valider", json=[j]).get_json()
    assert r["ok"] and r["pro"] and r["payant"] and r["source"] == "apple", r
    assert not a.post("/api/apple_achat_valider", json=[j[:-6] + "AAAAAA"]).get_json()["ok"]         # signature touchee
    assert not a.post("/api/apple_achat_valider", json=[signe(tx(info["jeton"], productId="autre"))]).get_json()["ok"]
    assert not a.post("/api/apple_achat_valider", json=[signe(tx("00000000-0000-0000-0000-000000000000"))]).get_json()["ok"]
    # pas de 2e abonnement par le site
    assert not a.post("/api/abonnement_payer", json=[]).get_json()["ok"]

    # 4. un 2e compte ne peut pas reprendre l'abonnement Apple du 1er
    b = compte("uid-B")
    jb = b.post("/api/apple_achat_info", json=[]).get_json()["jeton"]
    rb = b.post("/api/apple_achats_restaurer", json=[[signe(tx(None, orig="2000000001"))]]).get_json()
    assert not rb["ok"] and "autre compte" in rb["erreur"], rb

    # 5. avis d'Apple : remboursement -> Gratuit, renouvellement -> Pro, doublon ignore, faux avis refuse
    def avis(typ, d, uid, st=None, ren=None):
        data = {"bundleId": "com.slabcoach.app", "environment": "Sandbox", "signedTransactionInfo": signe(d)}
        if ren:
            data["signedRenewalInfo"] = signe(ren)
        p = {"notificationType": typ, "notificationUUID": uid, "data": data, "signedDate": int(maint * 1000)}
        if st:
            p["subtype"] = st
        return server.app.test_client().post("/apple/notifications", json={"signedPayload": signe(p)})
    assert avis("REFUND", tx(info["jeton"], revocationDate=int(maint * 1000)), "u1").status_code == 200
    assert comptes.info(cid)["forfait"] == "gratuit"
    assert avis("DID_RENEW", tx(info["jeton"], jours=60), "u2").status_code == 200
    assert comptes.info(cid)["forfait"] == "pro" and comptes.info(cid)["forfait_fin"] > maint + 50 * 86400
    assert avis("REFUND", tx(info["jeton"]), "u2").get_json()["recu"] == "déjà traité"
    assert comptes.info(cid)["forfait"] == "pro"
    avis("DID_CHANGE_RENEWAL_STATUS", tx(info["jeton"], jours=60), "u3", ren={"autoRenewStatus": 0})
    assert comptes.info(cid)["forfait_annule"] is True
    r = server.app.test_client().post("/apple/notifications", json={"signedPayload": "a.b.c"})
    assert r.status_code == 400
    # 6. un avis perdu : la date de fin passee de plus de 3 jours -> Gratuit tout seul
    comptes.maj(cid, forfait_fin=int(maint - 4 * 86400))
    assert not a.post("/api/forfait", json=[]).get_json()["payant"]
    comptes.maj(cid, forfait_fin=int(maint - 1 * 86400))                                # 1 jour : encore Pro (delai)
    assert a.post("/api/forfait", json=[]).get_json()["payant"]
    # 7. un Pro paye sur le site n'est jamais retire par un avis d'Apple
    cb = next(x for x in comptes.lister() if comptes.info(x).get("ebay_user_id") == "uid-B")
    comptes.maj(cb, forfait="pro", forfait_source="stripe", stripe_abonnement="sub_9", apple_jeton=jb)
    avis("EXPIRED", tx(jb, orig="3000000001", jours=-2), "u4")
    assert comptes.info(cb)["forfait"] == "pro" and comptes.info(cb)["forfait_source"] == "stripe"
    # 8. achat Sandbox refuse si on le demande (APPLE_IAP_SANDBOX=0)
    os.environ["APPLE_IAP_SANDBOX"] = "0"
    assert not a.post("/api/apple_achat_valider", json=[j]).get_json()["ok"]
    os.environ["APPLE_IAP_SANDBOX"] = "1"
    # 9. interrupteur du serveur (LOCKERROOM_EBAY_PRIX=0) : fonctions de prix sur les annonces eBay coupees, le reste vit
    os.environ["LOCKERROOM_EBAY_PRIX"] = "0"
    d = a.post("/api/deals_liste", json=[{}]).get_json()
    assert d["ok"] and d["coupe"] and d["deals"] == [], d
    assert a.post("/api/sante_liste", json=["baisser"]).get_json() == []
    assert a.post("/api/carte_comps", json=["123"]).get_json()["coupe"]
    assert a.post("/api/forfait", json=[]).status_code == 200
    os.environ["LOCKERROOM_EBAY_PRIX"] = "1"
    assert not a.post("/api/deals_liste", json=[{}]).get_json().get("coupe")
    print("ACHATS APPLE OK")
''')

if __name__ == "__main__":
    d = tempfile.mkdtemp()
    env = dict(os.environ, LOCKERROOM_HEBERGE="1", LOCKERROOM_MULTI="1", LOCKERROOM_DONNEES=d, LOCKERROOM_SECRET="s" * 32,
               LOCKERROOM_TACHES="0", LOCKERROOM_CLE="test", LOCKERROOM_EBAY_ENV="production",
               LOCKERROOM_EBAY_APP_ID="App-PRD-1234", LOCKERROOM_EBAY_CERT_ID="Cert-5678", LOCKERROOM_EBAY_RUNAME="Ru-9999",
               STRIPE_CLE_SECRETE="sk_test_faux", STRIPE_PRIX_PRO="price_test_pro", STRIPE_WEBHOOK_SECRET="whsec_test",
               RENDER_EXTERNAL_URL="https://lr.onrender.com", LOCKERROOM_EBAY_AVIS_JETON="J" * 40)
    r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True)
    print(r.stdout or r.stderr[-3000:])
    sys.exit(0 if "ACHATS APPLE OK" in r.stdout else 1)
