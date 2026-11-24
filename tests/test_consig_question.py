"""23 nov 2026 (Mathieu, 59 cartes a envoyer en consignation : « rien se passe quand je clique »). Reproduit : un 2e toucher sur
Exporter / Imprimer pendant que la question « Retirer N annonces d'eBay ? » est affichee en posait une 2e par-dessus ; « Annuler »
remettait alors l'ANCIENNE question, dont les boutons n'avaient plus de geste (aucun appel ne partait au serveur).
Une seule question a la fois, et le bandeau d'origine est garde une seule fois."""
import os
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
i = s.index("function feuilleConsigner(cartes){"); f = s[i:i + 9000]
assert "let ebayFait = !surEbay, question = false;" in f and "const bandeau0 = ($('#cs-eb') || {}).innerHTML || '';" in f
assert "if (question) { z0.scrollIntoView({block: 'nearest'}); return false; }" in f and "const txt0 = bandeau0;" in f
assert "const txt0 = z0.innerHTML;" not in f, "le bandeau ne se relit plus dans la page (il pouvait deja etre la question)"
assert "z0.classList.remove('csg-q'); question = false;" in f
# la question reste DANS la fenetre, et rien ne part sans le oui
assert "API.consig_retirer_ebay(" in f and f.index("if (!oui) { z0.innerHTML = txt0; return false; }") < f.index("API.consig_retirer_ebay(")
print("OK test_consig_question")
