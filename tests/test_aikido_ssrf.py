"""18 nov 2026 (Aikido) : SSRF et inclusion de fichier : python tests/test_aikido_ssrf.py (aucun appel reseau)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import reseau_sur, catalogue, ebay_compte

def refuse(f, *a, **k):
    try:
        f(*a, **k)
    except (ValueError, reseau_sur.AdresseRefusee):
        return True
    return False

EB = ("ebay.us", "ebay.ca", "ebay.com")
assert refuse(reseau_sur.suivre, "http://ebay.us/x", EB)                 # pas https
assert refuse(reseau_sur.suivre, "https://127.0.0.1/x", EB)              # pas eBay
assert refuse(reseau_sur.suivre, "https://evil.com/ebay.us", EB)
assert refuse(reseau_sur.verifier, "https://169.254.169.254/latest/meta-data", None)   # metadonnees du nuage
assert refuse(ebay_compte._lire_image, "https://evil.com/a.jpg")          # le CDN d'eBay seulement
assert refuse(catalogue._lire, "../../etc/passwd")
assert refuse(catalogue._lire, "/etc/passwd")
assert refuse(ebay_compte._lire, "/etc/passwd")
assert refuse(ebay_compte._ecrire, "/tmp/x.json", {})
d = tempfile.mkdtemp()
catalogue.dossier_ajouts = lambda: d
ch = catalogue.enregistrer_ajout({"id": "../../evil", "nom": "x", "cartes": []})
assert os.path.dirname(ch) == d and os.path.basename(ch) == "evil.json", ch
print("AIKIDO SSRF OK")
