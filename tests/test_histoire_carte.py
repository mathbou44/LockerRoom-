"""13 nov 2026 (Mathieu : « pourquoi cette carte-la est interessante, surtout les cartes des annees 90 ») : l'histoire d'une
carte, cherchee UNE fois (web), gardee, sans prix ni population ; budget par jour."""
import json, os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import histoire_carte as H
appels = []
def faux(corps):
    appels.append(corps)
    assert any(t.get("type", "").startswith("web_search") for t in corps["tools"])
    assert "PSA" not in corps["messages"][0]["content"].split("La carte :")[1].split("\n")[0]      # le grade n'est pas envoye
    js = {"speciale": True, "fr": "Premier produit Pinnacle a utiliser le Dufex. Hasek venait d'arriver a Buffalo. Elle vaut 200 $.",
          "en": "Pinnacle's first Dufex product. Hasek had just joined Buffalo.", "sources": [{"titre": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Pinnacle"},
                                                                                             {"titre": "g", "url": "https://www.google.com/x"}]}
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Voici.\n<json>" + json.dumps(js) + "</json>"}]}
t1 = "1992-93 Pinnacle Dominik Hasek #229 PSA 9"
t2 = "1992-93 Pinnacle Dominik Hasek #229 BGS 8.5"          # la meme carte, autre grade : la meme histoire
h = H.generer(t1, "Dominik Hasek", appeler=faux)
assert h["fr"].startswith("Premier") and "200" not in h["fr"], h                # la phrase avec un prix est retiree
assert [s["url"] for s in h["sources"]] == ["https://en.wikipedia.org/wiki/Pinnacle"]
assert H.generer(t2, "Dominik Hasek", appeler=faux)["fr"] == h["fr"] and len(appels) == 1
assert H.identite(t1)[0] == H.identite(t2)[0] and H.identite("1993-94 Pinnacle Dominik Hasek #50")[0] != H.identite(t1)[0]
# budget du jour
os.environ["LR_HISTOIRE_JOUR"] = "1"
assert H.generer("1995-96 Zenith Dominik Hasek Z-Team", appeler=faux) == {"erreur": "budget"}
os.environ["LR_HISTOIRE_JOUR"] = "5"
# une reponse illisible : rien de garde, rien d'invente
r = H.generer("1996-97 Leaf Limited Dominik Hasek", appeler=lambda c: {"content": [{"type": "text", "text": "je ne sais pas"}]})
assert r == {"erreur": "rien"} and H.lire("1996-97 Leaf Limited Dominik Hasek") is None
# pause_turn : on relance
n = []
def pause(corps):
    n.append(1)
    return {"stop_reason": "pause_turn", "content": [{"type": "text", "text": "..."}]} if len(n) == 1 else faux(corps)
assert H.generer("1998-99 BAP Dominik Hasek Auto", appeler=pause)["fr"] and len(n) == 2
print("HISTOIRE OK")
