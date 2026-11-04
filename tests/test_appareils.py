"""2 nov 2026 : un utilisateur voit la meme chose sur son ordi et son cell (identites reliees, courriel, code d'appareil)."""
import os, sys, tempfile
D = tempfile.mkdtemp()
os.environ["LOCKERROOM_DONNEES"] = D
os.environ["LOCKERROOM_MULTI"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes

# 1. Apple puis Google avec le MEME courriel verifie : un seul compte
a, n1 = comptes.trouver_connexion("apple:001", "Mathieu", "apple", "m@exemple.com")
comptes.maj(a, courriel="m@exemple.com", connexion="apple")
g, n2 = comptes.trouver_connexion("google:xyz", "Mathieu", "google", "M@Exemple.com")
assert n1 and not n2 and g == a, (a, g)
assert comptes.trouver_connexion("google:xyz", "Mathieu", "google", None)[0] == a       # l'identite reliee suffit ensuite
# 2. courriel relais d'Apple : pas de rapprochement par courriel
r, n3 = comptes.trouver_connexion("apple:002", "X", "apple", "abc@privaterelay.appleid.com")
comptes.maj(r, courriel="abc@privaterelay.appleid.com")
o, n4 = comptes.trouver_connexion("google:autre", "X", "google", "abc@privaterelay.appleid.com")
assert n3 and n4 and o != r
# 3. relier depuis Profil : l'ancien compte Google de « o » renvoie vers « r » (ses donnees restent)
comptes.lier_identite(r, "google:autre", "google")
assert comptes.resoudre(o) == r and comptes.info(o).get("renvoi") == r and o in comptes.lister()
assert comptes.trouver_connexion("google:autre", "X", "google", None)[0] == r
# 4. code d'appareil : 6 chiffres, un seul usage, ouvre le bon compte
c = comptes.code_creer(a)
assert len(c) == 8 and c.isdigit()          # 3 nov 2026 : 8 chiffres
assert comptes.code_utiliser("12") is None
assert comptes.code_utiliser(c[:3] + " " + c[3:]) == a
assert comptes.code_utiliser(c) is None                     # deja utilise
# 5. la route /auth/code ouvre la session du compte
import server
cl = server.app.test_client()
c2 = comptes.code_creer(a)
rep = cl.post("/auth/code", data={"code": c2}, headers={"Origin": "http://localhost"})
assert rep.status_code == 302 and rep.headers["Location"].endswith("/#accueil"), rep.status_code
with cl.session_transaction() as s:
    assert s["compte"] == a
assert "Code invalide" in cl.post("/auth/code", data={"code": "000000"}, headers={"Origin": "http://localhost"}).get_data(as_text=True)
# 6. une session ouverte sur un ancien compte relie passe au compte choisi
cl2 = server.app.test_client()
with cl2.session_transaction() as s:
    s["compte"] = o
cl2.get("/api/forfait")
with cl2.session_transaction() as s:
    assert s["compte"] == r, s.get("compte")
print("ok appareils")
