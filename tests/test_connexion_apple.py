"""24 nov 2026 (revue avant l'envoi a Apple) : l'ecran de connexion, le premier ecran de l'equipe d'Apple.
- regle 3.1.1(a) : hors des Etats-Unis, l'app ne doit orienter vers aucun autre moyen de paiement que l'achat integre :
  DANS l'app iPhone, la page ne nomme plus Stripe (le site, lui, garde sa ligne) ;
- guide d'Apple « Sign in with Apple » : le bouton Apple n'est pas plus petit que les autres, et son titre fait 43 % de la
  hauteur du bouton (50 px -> 21,5 px) ; les titres permis seulement (« Continuer avec Apple » / « Continue with Apple ») ;
- en anglais, plus de phrase restee en francais (la note de l'iPhone)."""
import os, re, subprocess, sys, tempfile, textwrap
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, re
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server
    APP = {"User-Agent": "Mozilla/5.0 (iPhone) LockerRoomiOS/1.1 SlabCoachAuth"}
    VIEILLE = {"User-Agent": "Mozilla/5.0 (iPhone) LockerRoomiOS"}
    c = server.app.test_client()
    for lang in ("fr", "en"):
        app_ = c.get("/connexion?lang=" + lang, headers=APP).get_data(as_text=True)
        web = server.app.test_client().get("/connexion?lang=" + lang).get_data(as_text=True)
        assert "Stripe" not in app_, "l'app iPhone ne nomme pas Stripe (" + lang + ")"
        assert "Stripe" in web                                                   # le site garde sa ligne
        assert ("Aucun mot de passe gardé" if lang == "fr" else "No password kept · data never sold") in app_
        for p in (app_, web):                                                    # les trois boutons, dans UNE pile
            pile = re.search(r'<div class="conn">(.*?)</div>', p, re.S).group(1)
            assert pile.count("href=") == 3 and "/auth/ebay" in pile and "/auth/apple" in pile and "/auth/google" in pile, pile[:200]
            assert ("Continuer avec Apple" if lang == "fr" else "Continue with Apple") in pile
            assert 'class="ou"' not in p
    en = c.get("/connexion?lang=en", headers=VIEILLE).get_data(as_text=True)     # une vieille version de l'app : la note de l'iPhone
    assert "On iPhone, at eBay, enter your eBay email and password" in en and "Sur l’iPhone" not in en
    assert "/auth/google" not in en                                              # Google refuse les vues web integrees
    print("CONNEXION OK")
''')
d = tempfile.mkdtemp()
env = dict(os.environ, LOCKERROOM_DONNEES=d, LOCKERROOM_MULTI="1", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999",
           GOOGLE_CLIENT_ID="essai", GOOGLE_CLIENT_SECRET="essai", APPLE_SERVICES_ID="essai", APPLE_TEAM_ID="essai", APPLE_KEY_ID="essai", APPLE_PRIVATE_KEY="essai")
r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True, timeout=240)
assert "CONNEXION OK" in r.stdout, (r.stdout[-600:], r.stderr[-1500:])

css = open(os.path.join(ICI, "ui", "connexion.html"), encoding="utf-8").read()
m = re.search(r"\.conn \.btn, \.conn \.btn-t\{height:(\d+)px;[^}]*font:\d+ ([\d.]+)px", css)
assert m, "les trois boutons partagent la meme hauteur et la meme taille de titre"
h, t = int(m.group(1)), float(m.group(2))
assert h >= 44 and abs(t / h - 0.43) <= 0.006, (h, t)                           # le titre a 43 % de la hauteur (guide d'Apple)
assert re.search(r"\.conn \.btn-t\.apple\{[^}]*background:#fff; color:#000", css)   # blanc sur fond sombre, logo et titre noirs
assert re.search(r"\.conn \.btn, \.conn \.btn-t\{[^}]*px/1 -apple-system", css)       # la police du systeme d'abord
print("OK test_connexion_apple")
