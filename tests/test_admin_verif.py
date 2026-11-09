"""9 nov 2026 (Mathieu : « oui pour la validation cell ») : la console admin demande un code envoye sur l'iPhone de l'admin."""
import os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.pop("LOCKERROOM_ADMIN_CODE", None)
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import apns
import lockerroom
from flask import Flask
api = lockerroom.Api(os.path.join(os.environ["LOCKERROOM_DONNEES"], "t.db"))
lockerroom.Api._est_admin_compte = lambda self: True
comptes.MULTI = True
envoyes = []
apns.actif = lambda: True
apns.envoyer = lambda j, t, x, *a, **k: (envoyes.append((j, x)), "ok")[1]
app = Flask("t"); app.secret_key = "x"
J1, J2 = "a" * 64, "b" * 64
with app.test_request_context("/"):
    # sans iPhone relie ni code de secours : impossible de verifier -> l'admin n'est jamais bloque dehors
    assert api._est_admin() and not api._admin_verif_possible()
    api.push_enregistrer(J1)                                  # l'iPhone de l'admin (avant la mise en place)
    assert api._admin_verif_possible() and not api._est_admin()
    f = api.forfait()
    assert f["admin"] is False and f["admin_a_verifier"] is True and f["admin_verif_active"] is True
    api.push_enregistrer(J2)                                  # un telephone ajoute par une session NON confirmee
    r = api.admin_verif_envoyer()
    assert r["ok"] and r["envoye"] == 1 and [j for j, _ in envoyes] == [J1], envoyes   # jamais au telephone d'un intrus
    code = re.search(r"(\d{6})", envoyes[-1][1]).group(1)
    assert not api.admin_verif_valider("000000" if code != "000000" else "111111")["ok"]
    assert api.admin_verif_valider(code)["ok"] and api._est_admin()
    assert not api.admin_verif_valider(code)["ok"]              # un code ne sert qu'une fois
with app.test_request_context("/"):
    # une autre session (autre appareil) : a confirmer de nouveau ; 5 essais au plus
    assert not api._est_admin()
    envoyes.clear(); api.admin_verif_envoyer(); code = re.search(r"(\d{6})", envoyes[-1][1]).group(1)
    faux = "999999" if code != "999999" else "888888"
    for _ in range(5):
        assert not api.admin_verif_valider(faux)["ok"]
    assert not api.admin_verif_valider(code)["ok"]              # bloque apres 5 essais
with app.test_request_context("/"):
    # code de secours (Render), et un telephone enregistre depuis une session confirmee devient de confiance
    os.environ["LOCKERROOM_ADMIN_CODE"] = "secours-1234"
    assert not api.admin_verif_valider("court")["ok"]
    assert api.admin_verif_valider("secours-1234")["ok"] and api._est_admin()
    api.push_enregistrer("c" * 64)
    envoyes.clear(); api.admin_verif_envoyer()
    assert sorted(j for j, _ in envoyes) == [J1, "c" * 64]
os.environ.pop("LOCKERROOM_ADMIN_CODE")
# un compte qui n'est pas admin : rien
lockerroom.Api._est_admin_compte = lambda self: False
with app.test_request_context("/"):
    assert not api.admin_verif_envoyer()["ok"] and not api.admin_verif_valider("123456")["ok"] and not api._est_admin()
print("OK test_admin_verif")
