"""15 nov 2026 (session SlabIQ) : la prediction « texte » hors pli (oof) de score_appris se fait en blocs de temps contigus
(les ventes sont triees par jour) et non au hasard : chaque pli de validation est un bloc de jours d'un seul tenant, tous les
indices sont couverts une seule fois, et l'apprentissage du pli n'y touche jamais."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
import numpy as np
import score_appris as sa

for n in (5, 17, 1000, 146398):
    plis = sa._plis_temps(n)
    assert len(plis) == 5
    vus = np.concatenate([v for _a, v in plis])
    assert sorted(vus.tolist()) == list(range(n)), n                  # chaque vente une seule fois en validation
    debut = 0
    for a, v in plis:
        assert len(v) and np.all(np.diff(v) == 1), n                   # un bloc contigu (des jours qui se suivent)
        assert v[0] == debut, n                                        # dans l'ordre du temps
        debut = v[-1] + 1
        assert not set(a.tolist()) & set(v.tolist())                  # jamais appris sur ce qu'on predit
        assert len(a) + len(v) == n
# le reapprentissage passe bien par ces plis (et plus par un KFold melange)
import inspect
src = inspect.getsource(sa.entrainer)
assert "_plis_temps(" in src and "shuffle=True" not in src
print("ok test_plis_temps")
