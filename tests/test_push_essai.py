"""24 nov 2026 (Mathieu : « toujours pas recu de notifications ») : la notification d'essai dit POURQUOI rien n'arrive.
Constat en production le meme soir : son iPhone s'enregistre bien (POST /api/push_enregistrer 200, app LockerRoomiOS/1.1) et
le journal n'a aucune ligne « APNs » : rien ne permettait de savoir si le serveur est branche a Apple."""
import os, sys, tempfile
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
for k in ("APNS_KEY_ID", "APNS_TEAM_ID", "APNS_KEY", "LOCKERROOM_MULTI"):
    os.environ.pop(k, None)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import apns, lockerroom
api = lockerroom.Api()
# 1. le serveur n'est pas branche a Apple : on le dit, et le vrai admin voit quelles variables manquent
r = api.push_essai()
assert r["ok"] is False and r["cause"] == "serveur" and r["appareils"] == 0, r
assert r["detail"] is None or "APNS_KEY_ID" in r["detail"], r
# 2. branche, mais aucun iPhone n'a accepte
os.environ.update(APNS_KEY_ID="K", APNS_TEAM_ID="T", APNS_KEY="cle")
r = api.push_essai()
assert r["ok"] is False and r["cause"] == "appareil", r
# 3. un iPhone, Apple accepte
assert api.push_enregistrer("ab" * 32)["ok"]
envois = []
apns.envoyer = lambda j, titre, texte, donnees=None, client=None: (envois.append((j, titre, donnees)), "ok")[1]
r = api.push_essai()
assert r["ok"] and r["envoyees"] == 1 and r["appareils"] == 1 and r["cause"] is None, r
assert envois and envois[0][1] == "SlabCoach" and envois[0][2] == {"lien": "#notifs"}
# 4. Apple refuse : on le dit (le detail d'Apple ne va qu'au vrai admin)
def refuse(j, titre, texte, donnees=None, client=None):
    apns.DERNIER.update(code=403, texte='{"reason":"InvalidProviderToken"}')
    return "erreur"
apns.envoyer = refuse
r = api.push_essai()
assert r["ok"] is False and r["cause"] == "apple" and r["envoyees"] == 0, r
assert r["detail"] is None or "InvalidProviderToken" in r["detail"], r
# 5. l'ecran : le lien n'existe que dans l'app iPhone, et chaque cause a sa phrase
s = open(os.path.join(RACINE, "source", "src_app.html"), encoding="utf-8").read()
assert "${NATIF ? `<button class=\"lien-doux\" id=\"nt-essai\"" in s and "API.push_essai()" in s
for cause in ("serveur:", "appareil:", "apple:"):
    assert cause in s[s.index("const es = $('#nt-essai')"):s.index("const es = $('#nt-essai')") + 1500], cause
print("OK test_push_essai")
