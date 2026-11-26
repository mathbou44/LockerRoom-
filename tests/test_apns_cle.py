"""25 nov 2026 (Mathieu met ses cles APNs dans Render : « Server error » a la notification d'essai, et plus d'admin sur son
iPhone) : la cle collee sans ses lignes BEGIN / END faisait planter l'envoi, l'erreur au journal contenait les octets de la
cle, et la 2e verification admin devenait « possible » sans pouvoir envoyer son code. La cle se lit sous toutes ses formes,
une cle illisible ne plante rien, ne s'ecrit nulle part et ne bloque pas l'admin."""
import base64, io, os, sys, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import apns

cle = ec.generate_private_key(ec.SECP256R1())
pem = cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
corps = "".join(pem.strip().splitlines()[1:-1])
num = cle.private_numbers().private_value
formes = {"fichier": pem, "\\n ecrits": pem.replace("\n", "\\n"), "une ligne": pem.replace("\n", " "), "corps seul": corps,
          "corps sur des lignes": "\n".join(pem.strip().splitlines()[1:-1]), "fichier en base64": base64.b64encode(pem.encode()).decode(),
          "entre guillemets": '"' + pem + '"', "fins de ligne Windows": pem.replace("\n", "\r\n")}
for nom, v in formes.items():
    k = serialization.load_pem_private_key(apns.cle_pem(v).encode(), password=None)
    assert k.private_numbers().private_value == num, nom

os.environ.update(APNS_KEY_ID="ABC123DEFG", APNS_TEAM_ID="TEAM123456")
for nom, v in formes.items():                            # le jeton se signe avec chaque forme
    os.environ["APNS_KEY"] = v
    apns._JWT.update(le=0.0, v=None)
    assert apns.pret(), nom
    assert apns.jeton_auth().count(".") == 2, nom

# une cle illisible : une erreur propre, sans un octet de la cle ; l'envoi rend « erreur » sans planter ; rien au journal
for mauvais in ("pas une cle", corps[:60], corps[:-9] + "!!!", "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----", ""):
    os.environ["APNS_KEY"] = mauvais or " "
    apns._JWT.update(le=0.0, v=None)
    try:
        apns.cle_pem(mauvais) and apns._charger_cle()
        raise AssertionError("aurait du refuser : " + mauvais[:20])
    except apns.CleIllisible as e:
        assert str(e).startswith("APNS_KEY illisible") and e.__cause__ is None and e.__suppress_context__
    assert not apns.pret()
os.environ["APNS_KEY"] = corps[:-9] + "!!!"
apns._JWT.update(le=0.0, v=None); apns.DERNIER.clear()
sortie = io.StringIO()
with contextlib.redirect_stdout(sortie):
    assert apns.envoyer("a" * 64, "t", "x") == "erreur"
assert apns.DERNIER["code"] == 0 and apns.DERNIER["texte"].startswith("APNS_KEY illisible")
journal = sortie.getvalue()
assert "APNS_KEY illisible" in journal and corps[:24] not in journal and "\\x" not in journal, journal

src = lambda f: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f), encoding="utf-8").read()
assert "+ repr(e)" not in src("apns.py").split("def envoyer")[1].split("import httpx")[0]
for f in ("alarmes.py", "marche.py"):
    assert '"Push : " + repr(e)' not in src(f), f
lr = src("lockerroom.py")
assert "apns.pret() and bool(self._jetons_admin())" in lr and '"Render : " + d["texte"]' in lr
print("APNS CLE OK", len(formes), "formes")
