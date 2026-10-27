"""27 oct 2026 - connexion Apple / Google sans eBay : etat signe, id_token verifie, secret Apple ES256."""
import base64
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("LOCKERROOM_SECRET", "secret-de-test")

from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa  # noqa: E402

import auth_tiers as at  # noqa: E402


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class TestAuthTiers(unittest.TestCase):
    def setUp(self):
        self.cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        n = self.cle.public_key().public_numbers()
        self.jwks = json.dumps({"keys": [{"kty": "RSA", "kid": "k1", "n": b64(n.n.to_bytes(256, "big")), "e": b64(n.e.to_bytes(3, "big"))}]}).encode()
        os.environ["GOOGLE_CLIENT_ID"] = "client-g"
        os.environ["GOOGLE_CLIENT_SECRET"] = "x"
        at._JWKS.clear()

    def jeton(self, **claims):
        c = {"iss": "https://accounts.google.com", "aud": "client-g", "exp": time.time() + 600, "sub": "123", "nonce": "n1"}
        c.update(claims)
        t = b64(json.dumps({"alg": "RS256", "kid": "k1"}).encode()) + "." + b64(json.dumps(c).encode())
        return t + "." + b64(self.cle.sign(t.encode(), padding.PKCS1v15(), hashes.SHA256()))

    def test_id_token_valide(self):
        c = at.verifier_id_token("google", self.jeton(), "n1", lecteur=lambda u: self.jwks)
        self.assertEqual(c["sub"], "123")

    def test_id_token_refuse(self):
        lec = lambda u: self.jwks  # noqa: E731
        for mauvais, nonce in [(self.jeton(aud="autre"), "n1"), (self.jeton(iss="https://pirate"), "n1"),
                               (self.jeton(exp=time.time() - 3600), "n1"), (self.jeton(), "n2")]:
            with self.assertRaises(RuntimeError):
                at.verifier_id_token("google", mauvais, nonce, lecteur=lec)
        t = self.jeton()
        falsifie = t.rsplit(".", 1)[0][:-4] + "AAAA." + t.rsplit(".", 1)[1]
        with self.assertRaises(RuntimeError):
            at.verifier_id_token("google", falsifie, "n1", lecteur=lec)

    def test_etat_signe(self):
        e = at._signer_etat({"f": "apple", "n": "x", "t": int(time.time())})
        self.assertEqual(at._lire_etat(e)["f"], "apple")
        self.assertIsNone(at._lire_etat(e[:-2] + "zz"))
        vieux = at._signer_etat({"f": "apple", "n": "x", "t": int(time.time()) - 3600})
        self.assertIsNone(at._lire_etat(vieux))

    def test_url_et_secret_apple(self):
        pk = ec.generate_private_key(ec.SECP256R1())
        pem = pk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        os.environ.update(APPLE_SERVICES_ID="com.slabcoach.web", APPLE_TEAM_ID="TEAM123", APPLE_KEY_ID="KEY123",
                          APPLE_PRIVATE_KEY=pem.replace("\n", "\\n"))
        self.assertIn("apple", at.actifs())
        u = at.url_connexion("apple", "https://slabcoach.com")
        self.assertIn("response_mode=form_post", u)
        self.assertIn("redirect_uri=https%3A%2F%2Fslabcoach.com%2Fauth%2Fapple%2Fretour", u)
        s = at._secret_apple()
        t, c, sig = s.split(".")
        self.assertEqual(json.loads(base64.urlsafe_b64decode(c + "==")).get("sub"), "com.slabcoach.web")
        brut = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        der = encode_dss_signature(int.from_bytes(brut[:32], "big"), int.from_bytes(brut[32:], "big"))
        pk.public_key().verify(der, (t + "." + c).encode(), ec.ECDSA(hashes.SHA256()))   # signature ES256 valide

    def test_terminer_etat_expire(self):
        r = at.terminer("google", "code", "pas-un-etat", "https://slabcoach.com")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
