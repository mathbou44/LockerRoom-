"""23 nov 2026 (envoi a Apple) : le chemin de l'equipe d'Apple, de l'ecran de connexion au compte demo.
- dans l'app iPhone seulement, l'ecran de connexion montre le lien « Demo / Demo » (la note au reviseur le nomme ainsi) ;
- le bon code ouvre un compte GRATUIT rempli ; un mauvais code est refuse ;
- le compte demo ne recoit jamais la fenetre « Tu utilises deja SlabCoach ailleurs ? » (elle dit « un nouveau compte vient
  d'etre cree » : faux pour l'equipe d'Apple, et un ecran de plus avant l'app)."""
import os, re, subprocess, sys, tempfile, textwrap
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = textwrap.dedent('''
    import os, sys, json
    sys.path.insert(0, %(ici)r); os.chdir(%(ici)r)
    import server, comptes
    server._premiere_synchro = lambda cid: None
    IOS = {"User-Agent": "Mozilla/5.0 (iPhone) LockerRoomiOS", "Origin": "http://localhost"}
    c = server.app.test_client()
    p = c.get("/connexion", headers=IOS).get_data(as_text=True)
    assert "<a href='/demo'>Démo / Demo</a>" in p and "Retour au site" not in p            # app iPhone : le lien, et pas la vitrine
    assert "/demo" not in server.app.test_client().get("/connexion").get_data(as_text=True)   # navigateur : pas de lien
    assert c.post("/demo", data={"code": "mauvais"}, headers=IOS).status_code == 200          # refuse : la page revient
    r = c.post("/demo", data={"code": "essai-local"}, headers=IOS)
    assert r.status_code == 302 and r.headers["Location"].endswith("/"), r.status_code
    f = c.post("/api/forfait", json=[], headers=IOS).get_json()
    assert f.get("compte_neuf") is False, f.get("compte_neuf")                                # jamais la fenetre « nouveau compte »
    assert not f.get("payant") and not f.get("offert") and not f.get("essai"), (f.get("payant"), f.get("offert"), f.get("essai"))   # GRATUIT : Apple voit l'achat integre
    print("DEMO OK")
''')
d = tempfile.mkdtemp()
env = dict(os.environ, LOCKERROOM_DONNEES=d, LOCKERROOM_MULTI="1", LOCKERROOM_DEMO_CODE="essai-local", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999")
r = subprocess.run([sys.executable, "-c", SCRIPT % {"ici": ICI}], env=env, capture_output=True, text=True, timeout=240)
assert "DEMO OK" in r.stdout, (r.stdout[-600:], r.stderr[-1500:])
# la note au reviseur (mobile/APP_STORE.md) nomme le lien comme l'app l'affiche
note = open(os.path.join(ICI, "mobile", "APP_STORE.md"), encoding="utf-8").read()
assert 'tap "Démo / Demo"' in note and 'tap "Code de démonstration"' not in note
src = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
# le chemin de l'achat integre : la pastille du Profil et le bouton « Voir le Pro » existent dans l'app
# la suppression du compte (regle 5.1.1(v)) : la ligne du Profil le dit, et la note donne le meme chemin
assert "tt('Aide, déconnexion, suppression', 'Help, sign out, delete account')" in src and 'My account > "Help, sign out, delete account" > Delete my SlabCoach account' in note
assert '"GO PRO" badge' in note and "tt('Voir le Pro', 'See Pro')" in src and "data-pro-ouvrir" in src
# la fiche ne promet plus ce que le public ne voit pas (prix tires des ventes, ventes comparables) : motif de refus (2.3.1)
i = note.index("**Nom :** SlabCoach"); j = note.index("## Notes pour l'examen d'Apple"); fiche = re.sub(r"(?m)^>.*$", "", note[i:j]).lower()
for mot in ("vrai prix", "vrais prix", "ventes réelles", "ventes comparables", "comps", "real sold", "comparable sales", "sold prices"):
    assert mot not in fiche, mot
for t in re.findall(r"\*\*Sous-titre[^:]*:\*\* (.+)", note):
    assert len(t.strip()) <= 30, t
for t in re.findall(r"\*\*Mots-clés[^:]*:\*\* (.+)", note):
    assert len(t.strip()) <= 100, t
print("OK test_demo_apple")
