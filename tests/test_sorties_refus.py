"""23 nov 2026 (Mathieu, fenetre admin « Sorties a venir » restee sur « Loading… 94 % » : « c'est tres tres long »). Le journal :
le serveur repondait en moins d'une seconde, mais par un refus du site du calendrier, et l'ecran n'affichait rien.
- un refus rend une raison lisible, ecrite au journal ; il n'est pas redemande a chaque ouverture (15 min), sauf « Reessayer » ;
- l'ecran remplace toujours la barre : la raison et « Reessayer », ou « rien a venir » ;
- un site qui refuse notre serveur n'est jamais contourne."""
import io, os, sys, tempfile, urllib.error
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import sorties

def refus(code):
    def f():
        raise urllib.error.HTTPError(sorties.URL, code, "x", {}, io.BytesIO(b""))
    return f

# 1. le refus : une raison claire, rien d'invente
r = sorties.lister(telecharger=refus(403))
assert r["ok"] is False and r["produits"] == [] and "refuse notre serveur (403)" in r["erreur"], r
assert "page introuvable (404)" in sorties.lister(telecharger=refus(404))["erreur"]
# 2. il vient de refuser : la prochaine ouverture ne rappelle pas le site ; « Reessayer » (force) oui
appels = []
vrai = sorties._telecharger
sorties._telecharger = lambda: (appels.append(1), refus(403)())[1]
r = sorties.lister()
assert appels == [] and r["ok"] is False and "refuse notre serveur" in r["erreur"] or "introuvable" in r["erreur"], (appels, r)
r = sorties.lister(force=True)
assert appels == [1] and r["ok"] is False
# 3. apres 15 minutes, on redemande
sorties._ECHEC["le"] -= sorties.ECHEC_S + 1
sorties.lister()
assert appels == [1, 1]
# 4. une liste deja gardee reste montree, avec la raison (jamais un ecran vide)
sorties._ecrire({"le": 0, "maj": "2026-11-01T10:00", "produits": [{"nom": "2026-27 Upper Deck Series 1 Hockey", "date": "2026-12-09"}]})
r = sorties.lister(force=True)
assert r["ok"] is True and len(r["produits"]) == 1 and "refuse notre serveur" in r["erreur"], r
sorties._telecharger = vrai
# 5. l'ecran : plus de retour muet ; et jamais de contournement (pas de faux navigateur dans l'agent)
app = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
i = app.index("async function blocSorties(force){"); bloc = app[i:i + 2600]
assert "if (!$('#adm-sorties') || !r || !r.ok) return;" not in bloc and "if (!l.length) return;" not in bloc
assert "adm-so-re" in bloc and "blocSorties(true)" in bloc and "Aucune sortie Upper Deck ou Topps" in bloc
assert "SlabCoach" in sorties.UA and "Chrome" not in sorties.UA and "Safari" not in sorties.UA
print("OK test_sorties_refus")
