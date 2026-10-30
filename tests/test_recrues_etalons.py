"""31 oct 2026 (Mathieu : « les Bruins (Hagens), les Flyers (Martone), les Blackhawks avec Frondell valent tous autant ou
presque ») : une nouvelle recrue est mise sur l'echelle des recrues CONNUES (etalons), pas seulement comparee aux autres
nouvelles. Aucun reseau."""
import os
import sys
import tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import valeur_produit  # noqa: E402

prod = {"id": "test-etalons"}
d = valeur_produit.lire() if hasattr(valeur_produit, "lire") else {}
# trois nouvelles vedettes (annonces a 100-120 $) et une recrue ordinaire (10 $) ; etalons : demande / annonces connues
e = {"maj": "2026-10-31T10:00:00",
     "annonces_recrues": {"James Hagens": {"m": 60, "h": 120, "n": 40}, "Porter Martone": {"m": 55, "h": 110, "n": 40},
                          "Anton Frondell": {"m": 50, "h": 100, "n": 40}, "Joe Ordinaire": {"m": 4, "h": 10, "n": 20}},
     "annonces_etalons": {"Matthew Schaefer": {"m": 60, "h": 120, "d": 10.8}, "Ivan Demidov": {"m": 40, "h": 75, "d": 6.5},
                          "Lane Hutson": {"m": 30, "h": 55, "d": 4.8}, "X Moyen": {"m": 5, "h": 7, "d": 0.6}}}
valeur_produit._ecrire({**(d or {}), prod["id"]: e})
h = valeur_produit.demande_recrue(prod, "James Hagens")
m = valeur_produit.demande_recrue(prod, "Porter Martone")
f = valeur_produit.demande_recrue(prod, "Anton Frondell")
o = valeur_produit.demande_recrue(prod, "Joe Ordinaire")
assert h > 5 and m > 5 and f > 5, (h, m, f)            # sur l'echelle de Demidov / Schaefer, plus a « joueur ordinaire »
assert max(h, m, f) / min(h, m, f) < 1.5, (h, m, f)      # « valent tous autant ou presque »
assert o < 1.5, o
# sans etalons : l'ancienne regle (relative aux nouvelles)
e.pop("annonces_etalons")
valeur_produit._ecrire({prod["id"]: e})
assert valeur_produit.demande_recrue(prod, "James Hagens") is not None
print("OK test_recrues_etalons", h, m, f, o)
