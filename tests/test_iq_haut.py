"""16 nov 2026 : l'alerte « SlabIQ · Mes joueurs montent » (alarmes.iq_haut_juger)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alarmes

assert alarmes.iq_haut_juger(None, 50) is None
assert alarmes.iq_haut_juger(72, 60) == ("monte", 12)          # +12 en 7 jours
assert alarmes.iq_haut_juger(65, 60) is None                   # +5 : rien
assert alarmes.iq_haut_juger(84, 78) == ("haut", None)         # entre dans le haut
assert alarmes.iq_haut_juger(84, 82) is None                   # deja dans le haut : rien
assert alarmes.iq_haut_juger(81, None) == ("haut", None)       # pas d'historique : seuil seulement
assert alarmes.iq_haut_juger(70, None) is None
assert alarmes.iq_haut_juger(95, 80) == ("monte", 15)          # une hausse forte passe avant
assert "iq_haut" in alarmes.TYPES and alarmes.DEFAUT["iq_haut"] is False
print("IQ HAUT OK")
