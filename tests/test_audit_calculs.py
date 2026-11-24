"""24 nov 2026 (Mathieu : « Repasse chaque fonction et calcul ») : l'audit des calculs d'argent tourne avec la suite. Chaque
calcul (profit d'une vente, bilan du mois, valeur a vendre, revente d'un deal, taxes d'un achat, places d'un break, rachat au
comptoir) est refait a part dans outils/audit_calculs.py ; un ecart de plus d'un cent fait echouer ce test."""
import os, subprocess, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, os.path.join(RACINE, "outils", "audit_calculs.py"), "--test"], capture_output=True, text=True, timeout=240,
                   env={k: v for k, v in os.environ.items() if not k.startswith("LR_") and k != "LOCKERROOM_DONNEES"})
sortie = (r.stdout or "") + (r.stderr or "")
assert r.returncode == 0 and " 0 ecart(s)" in sortie, sortie[-1500:]
n = int(sortie.split("AUDIT DES CALCULS : ")[1].split(" ")[0])
assert n >= 115, n
print("OK test_audit_calculs :", sortie.strip().splitlines()[-1])
