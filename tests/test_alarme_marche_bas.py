"""16 nov 2026 (Mathieu : « une notif quand un de mes joueurs est au marche bas ») : un joueur SUIVI, cle, au marche bas
(verifie) -> une notif (une par 14 jours) ; un joueur non suivi ou un marche normal -> rien."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import alarmes, marche_cles as mc
mc.ecrire({"verif": {"actif": True, "seuil": 0.15}, "cles": {"Sidney Crosby": {"score": 95}, "Connor Mcdavid": {"score": 96}},
           "etats": {"Sidney Crosby": {"indice": 0.78, "n": 20, "ecart_pct": -22}, "Connor Mcdavid": {"indice": 0.98, "n": 30, "ecart_pct": -2}}})
envoyes = []
alarmes._notifier = lambda api, etat, cle, titre, texte, lien, maint=None: (envoyes.append((cle, titre)) or True) if cle not in [c for c, _ in envoyes] else False


class Api:
    def __init__(self, fav): self.fav = fav
    def deals_profil_lire(self): return {"favoris": self.fav}


assert alarmes.marche_bas(Api(["Sidney Crosby", "Connor McDavid"]), {}) == 1
assert len(envoyes) == 1 and "Sidney Crosby" in envoyes[0][1] and "-22" in envoyes[0][1], envoyes
assert alarmes.marche_bas(Api(["Sidney Crosby"]), {}) == 0                 # deja envoyee cette quinzaine
assert alarmes.marche_bas(Api(["Connor McDavid"]), {}) == 0                # marche normal
assert alarmes.marche_bas(Api([]), {}) == 0                                # personne de suivi
assert "marche_bas" in alarmes.TYPES and alarmes.DEFAUT["marche_bas"] is False
print("ALARME MARCHE BAS OK", envoyes)
