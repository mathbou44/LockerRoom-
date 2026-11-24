"""24 nov 2026 (Mathieu : « repasse chaque fonction ; un audit intense avant le release ») : l'audit de TOUTES les fonctions de
l'API (outils/audit_api.py) tourne a chaque suite de tests. Chaque fonction est appelee comme l'app le fait, sans reseau, par
un compte gratuit et par personne, avec des arguments normaux puis tordus. Ce qui ne doit jamais casser :
  - aucune fonction d'admin ne repond a un compte ordinaire ;
  - aucune fonction ne repond sans session ;
  - aucun champ reserve (valeur tiree des ventes eBay) ne sort pour un compte ordinaire ;
  - un appel sans argument, ou avec le mauvais nombre d'arguments, ne finit jamais en « Erreur du serveur »."""
import os
import subprocess
import sys
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, os.path.join(ICI, "outils", "audit_api.py"), "--test"], capture_output=True, text=True, timeout=600)
assert "AUDIT API OK" in r.stdout, (r.stdout[-1500:], r.stderr[-1500:])
ligne = next(l for l in r.stdout.splitlines() if " fonctions, " in l)
print("OK test_audit_api :", ligne)
