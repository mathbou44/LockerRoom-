"""10 nov 2026 (« ca doit jamais arriver ») : aucun nom non defini dans le code (pyflakes), l'erreur qui a casse toutes les
recherches eBay le 9 nov. Saute si pyflakes n'est pas installe."""
import glob
import os
import subprocess
import sys
racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    import pyflakes  # noqa: F401
except ImportError:
    print("pyflakes absent : saute")
    sys.exit(0)
r = subprocess.run([sys.executable, "-m", "pyflakes"] + sorted(glob.glob(os.path.join(racine, "*.py"))), capture_output=True, text=True)
mauvais = [l for l in r.stdout.splitlines() if "undefined name" in l]
assert not mauvais, "\n".join(mauvais)
print("OK aucun nom non defini")
