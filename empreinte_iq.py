"""
SLABCOACH - l'empreinte du code qui decide de SlabIQ (19 nov 2026).

Mathieu : « a chaque version significative de SlabIQ (sa methode de recherche Pro), refaire les resultats des tests et les
mettre sur notre page ». L'empreinte change quand une regle de decision change (le bareme, la note, la validation par le
marche, la vitrine, les sets cultes, les seuils du Radar), jamais pour un commentaire. Les resultats publies
(ui/slabiq_tests.json) gardent l'empreinte de la version testee : tests/test_site_a_jour.py echoue tant qu'ils ne sont pas
refaits (outils/tests_site.py --ecrire).
"""
import ast
import hashlib
import os
import re

ICI = os.path.dirname(os.path.abspath(__file__))
FICHIERS = ("bareme_iq.py", "score_slab.py", "validation_iq.py", "vitrine.py", "sets_cultes.py")
CONSTANTES = ("RADAR_SCORE_MIN", "RADAR_SCORE_MIN_SUIVI", "RADAR_PRIX_MIN", "RADAR_FIXE_MIN", "RADAR_FIXE_MIN_SUIVI", "FEU_PTS")
_VAL = r"(?:int\(os\.environ\.get\([^)]*\)\s*or\s*)?([0-9.]+)"


def _sans_docstrings(arbre):
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    return arbre


def empreinte():
    h = hashlib.sha256()
    for f in FICHIERS:
        h.update(ast.dump(_sans_docstrings(ast.parse(open(os.path.join(ICI, f), encoding="utf-8").read()))).encode())
    src = open(os.path.join(ICI, "lockerroom.py"), encoding="utf-8").read()
    for k in CONSTANTES:
        m = re.search(r"\b" + k + r"\s*=\s*" + _VAL, src)
        h.update(f"{k}={m.group(1) if m else None}".encode())
    m = re.search(r"    def _radar_digne\(.*?\n    @staticmethod|    def _radar_digne\(.*?\n    def ", src, re.S)
    corps = m.group(0) if m else ""
    h.update(ast.dump(_sans_docstrings(ast.parse("class _X:\n" + re.sub(r"\n    @staticmethod$|\n    def $", "", corps)))).encode() if corps else b"")
    return h.hexdigest()[:16]
