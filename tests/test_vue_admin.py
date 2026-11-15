"""15 nov 2026 (Mathieu : « faut tout le temps que je refresh, des fois ca refresh pas ; on met admin et on tombe sur pro ») :
la vue admin / pro / gratuit ne vit plus dans le temoin de session (une lecture partie AVANT le changement revenait APRES et
remettait l'ancienne vue : la session permanente renvoie son temoin a chaque reponse)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import lockerroom
from flask import Flask, session
app = Flask("t"); app.secret_key = "x"
api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "t.db"))
api._est_admin0 = lambda: True
api._est_admin_compte = lambda: True
def req(fn, sid="s1", vieux=None):
    with app.test_request_context("/"):
        session["sid"] = sid
        if vieux:
            session["vue_admin"] = vieux          # un vieux temoin (une lecture partie avant le changement)
        return fn()
assert req(lambda: api.admin_vue("pro"))["vue"] == "pro"
assert req(lockerroom.vue_simulee) == "pro"
assert req(lambda: api.admin_vue("admin"))["vue"] == "admin"
# la lecture lente revient avec le vieux temoin « pro » : la vue reste admin
assert req(lockerroom.vue_simulee, vieux="pro") is None
assert req(lambda: api._est_admin()) is True
# une autre session (l'autre appareil) garde sa propre vue
req(lambda: api.admin_vue("gratuit"), sid="s2")
assert req(lockerroom.vue_simulee, sid="s2") == "gratuit" and req(lockerroom.vue_simulee) is None
# un redemarrage du serveur garde la vue
lockerroom._VUES["d"] = None
assert req(lockerroom.vue_simulee, sid="s2") == "gratuit"
# seul le vrai admin change de vue ; hors d'une requete (taches de fond) : jamais de vue simulee
api._est_admin0 = lambda: False
assert req(lambda: api.admin_vue("admin"))["ok"] is False and req(lockerroom.vue_simulee, sid="s2") == "gratuit"
assert lockerroom.vue_simulee() is None
print("OK vue admin")
