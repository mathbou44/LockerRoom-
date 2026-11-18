"""17 nov 2026 : la boucle de validation du bareme (validation_iq) : mesures, lettres du marche, corrections et questions."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import validation_iq as v
import slabiq_expert as e
import bareme_iq as b

assert v.crans("B", "A") == 3 and v.crans("A", "B") == -3 and v.crans("B+", "A-") == 1 and v.crans("B", "B") == 0
q = v._quantiles_vers_lettres({"x": 9, "y": 5, "z": 1}, {"x": "C", "y": "A", "z": "B"})
assert q == {"x": "A", "y": "B", "z": "C"}                      # la mesure decide l'ordre, le bareme la forme
assert v._spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
assert v.cle_carte("2024 Young Guns Lane Hutson 12/99 PSA 10") == v.cle_carte("2024 Young Guns Lane Hutson 55/99")

m = {"joueurs": [
        {"nom": "Joueur Fort", "lettre": "D", "marche": "B+", "crans": 4, "stable": True, "n": 40, "source": "ventes"},     # correction auto
        {"nom": "Joueur Mince", "lettre": "C", "marche": "B", "crans": 2, "stable": True, "n": 12, "source": "ventes"},     # question
        {"nom": "Cole Caufield", "lettre": "A+", "marche": "A-", "crans": -2, "stable": True, "n": 200, "source": "expert"},  # hors marche
        {"nom": "Joueur Ok", "lettre": "B", "marche": "B", "crans": 0, "stable": False, "n": 50, "source": "ventes"}],
     "sortes": [{"raison": "patch", "lettre": "B", "marche": "D", "crans": -3, "stable": True, "n": 300, "prime": 0.5},
                {"raison": "numerotee", "lettre": "B+", "marche": "A", "crans": 2, "stable": True, "n": 900, "prime": 1.2}]}
auto, _, Q = v.decider(m)
assert auto == {"Joueur Fort": "B+"}                             # jamais l'expert, jamais une sorte
noms = [x["nom"] for x in Q]
assert "Joueur Mince" in noms and "patch" in noms and "numerotee" not in noms
assert "Cole Caufield" not in noms                                # 18 nov : la valeur d'une vedette cotee par l'expert est hors marche
# la boucle : une correction automatique s'applique ; la reponse de l'expert la remplace et ferme la question
d = e.lire(); d["cotes_auto"] = auto; d["questions_marche"] = Q; e.ecrire(d)
b._AUTO["t"] = b._APPRIS["t"] = b._SORTES["t"] = 0
assert b.note_joueur("Joueur Fort")[1:] == ("B+", "marche")
e.coter("Joueur Fort", "A-"); b._AUTO["t"] = b._APPRIS["t"] = 0
assert b.note_joueur("Joueur Fort")[1:] == ("A-", "expert")
e.coter_sorte("dazzlers", "D"); b._SORTES["t"] = 0
assert b.sorte("2023-24 Upper Deck Dazzlers Connor Bedard #DZ-1")[0] == "D"
assert all(x["nom"] != "dazzlers" for x in e.lire()["questions_marche"])
assert "dazzlers" in v.SORTES_TRANCHEES                            # 18 nov : tranchee par Mathieu
print("VALIDATION IQ OK")
