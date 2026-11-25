"""25 nov 2026 (Mathieu : « si tu ouvres le lien, le prix est deja rentre, tu as juste a faire bid ») : un ESSAI, pour l'admin
seulement, des liens d'eBay qui portent le montant. Rien ne change pour les clients ; le montant reste copie (on colle si
rien n'est inscrit) ; SlabCoach ne confirme jamais une mise."""
import os, re
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "/itm/${id}?bolp=1&maxbid=${m}" in s and "/bfl/placebid/${id}?maxbid=${m}&currencyId=" in s
i = s.index("function feuilleMiser(")
f = s[i:s.index("\nfunction ", i + 10)]
assert "S.forfait && S.forfait.admin ? `<div class=\"mi-essai\">" in f, "les essais : admin seulement"
essai = f[f.index("$$('[data-essai]')"):]
essai = essai[:essai.index("const p = $('#mi-passe')")]
assert "copier(" in essai and "ouvrirMisePre(x, v, bt.dataset.essai)" in essai and "place_proxy_bid" not in essai and "API.miser" not in essai
# le bouton de tout le monde n'a pas change : l'annonce s'ouvre comme avant, le montant est copie
assert 'id="mi-go" href="${esc(lienMise(x))}"' in f and "const lienMise = (x) =>" in s and "if (ouvrirMiseEbay(x))" in f
print("OK test_mise_preremplie")
