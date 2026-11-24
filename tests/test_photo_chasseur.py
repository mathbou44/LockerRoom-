"""24 nov 2026 : la verification par photo du chasseur (deals tres sous la mediane : est-ce bien la meme carte ?).
Depuis le 20 nov au soir, elle ne tournait plus : le chasseur tourne sans compte, et vision demandait le dossier d'un compte
pour lire le compteur du SERVEUR -> « Deals (photo) : SansCompte » a chaque annonce (journal Render, 100 fois en 8 minutes).
En ligne (multi-comptes), sans compte : la photo est verifiee, le cout va au compteur du serveur, et rien n'est « refuse »."""
import os, subprocess, sys, tempfile, textwrap
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json, threading
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import comptes, vision, deals
    assert comptes.MULTI and not comptes.courant()
    appels = []
    vision.disponible = lambda: True
    def faux(corps, timeout=45):
        appels.append(corps)
        autre = "AUTRE" in corps["messages"][0]["content"][1]["text"]
        return {"usage": {"input_tokens": 1500, "output_tokens": 200},
                "content": [{"type": "tool_use", "input": {"meme_carte": not autre, "probleme": "autre joueur" if autre else "aucun", "detail": "essai"}}]}
    vision._appeler = faux
    assert "autre joueur" in vision._PROBLEMES_DEAL
    res = {}
    def chasseur():                                   # comme le fil du chasseur : aucun compte
        res["meme"] = deals.photo_refusee("111", "https://i.ebayimg.com/images/g/a/s-l500.jpg", "2023-24 Upper Deck Young Guns Connor Bedard", "Young Guns Bedard")
        res["autre"] = deals.photo_refusee("222", "https://i.ebayimg.com/images/g/b/s-l500.jpg", "AUTRE carte", "Young Guns Bedard")
        res["v"] = vision.verifier_deal("https://i.ebayimg.com/images/g/c/s-l500.jpg", "titre", "attendu")
    t = threading.Thread(target=chasseur, name="deals"); t.start(); t.join()
    assert res == {"meme": False, "autre": True, "v": {"meme_carte": True, "probleme": "aucun", "detail": "essai"}}, res
    assert len(appels) == 3, len(appels)
    assert not comptes.REFUSES, comptes.REFUSES[:1]                       # plus de « Compte manquant (dossier, fil deals) »
    d = json.load(open(os.path.join(comptes.DONNEES, "vision_serveur.json"), encoding="utf-8"))
    assert list(d.values())[0]["usd"] > 0                                 # le cout va au compteur du serveur
    # le garde-fou du 20 nov reste entier : sans compte, le dossier d'un COMPTE est toujours refuse
    try:
        vision._chemins()
        raise SystemExit("le dossier d'un compte doit rester refuse sans compte")
    except comptes.SansCompte:
        pass
    print("PHOTO OK")
''')
d = tempfile.mkdtemp()
env = dict(os.environ, LOCKERROOM_DONNEES=d, LOCKERROOM_MULTI="1", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999")
r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True, timeout=240)
assert "PHOTO OK" in r.stdout, (r.stdout[-800:], r.stderr[-1800:])
src = open(os.path.join(ICI, "vision.py"), encoding="utf-8").read()
assert "_chemins()[1]" not in src, "le fichier du serveur se lit par _chemin_serveur()"
print("OK test_photo_chasseur")
