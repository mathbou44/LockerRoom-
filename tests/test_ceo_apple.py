"""23 nov 2026 au soir (Mathieu : « j'ai rien demande a apple encore », puis « planifier mes premiers 5-6 mois ») :
l'envoi a Apple est decoupe en gestes d'un jour, l'ancienne tache est remplacee, et chaque zone du plan a un preparatif date."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ceo
c = ceo._semer({"semis": [], "taches": []})
L = {t["id"]: t for t in c["taches"]}
# Apple : 3 gestes dates avant le long conge americain (jeudi 26), et le plan B a decider avant le 1er decembre
assert [L[i]["echeance"] for i in ("ap_accord", "ap_build", "ap_soumettre", "ap_planb")] == ["2026-11-24", "2026-11-24", "2026-11-25", "2026-11-29"]
assert all(L[i]["prio"] == 1 and L[i]["projet"] == "lancement" for i in ("ap_accord", "ap_build", "ap_soumettre", "ap_planb"))
# 26 nov 2026, 19 h 11 (« refresh les donnees, je ne crois pas que tout est up to date ») : le build est lance (19 h 07), l'envoi
# est redecoupe ; il reste l'accord, TestFlight, l'envoi et le Small Business Program (19 h 08 : « non, pas fait »)
assert L["ap_accord"]["etat"] == "a_faire" and all(L[i]["etat"] == "fait" and L[i]["fait_le"] for i in ("ap_build", "ap_soumettre"))
assert all(L[i]["etat"] == "a_faire" and L[i]["prio"] == 1 and L[i]["projet"] == "lancement" for i in ("ap2_testflight", "ap2_soumettre", "ap2_small"))
assert "mardi" not in L["ap2_testflight"]["titre"] and "mercredi" not in L["ap2_soumettre"]["titre"] and "small-business-program" in L["ap2_small"]["lien"]      # le plan B est passe dans « petites decisions » (menage du 23 nov)
# l'ancienne tache (due le 22) et la decision sur la simulation se ferment seules, avec la raison
assert L["l1_apple"]["etat"] == "fait" and "Remplacée" in L["l1_apple"]["note"]
assert L["t_sim"]["etat"] == "fait" and "enlève" in L["t_sim"]["note"]
# les 6 premiers mois : un projet a part, court (Mathieu : « ca fait beaucoup »), chaque tache datee
P6 = [t for t in c["taches"] if t["projet"] == "six_mois"]
assert 6 <= len(P6) <= 8 and all(t["echeance"] for t in P6) and "six_mois" in ceo.PROJETS
assert L["p6_fevrier"]["echeance"] == "2027-02-15" and "peut changer" in L["p6_fevrier"]["note"]      # la date de Series 2 n'est pas officielle
# rien de tout cela ne promet un profit ni ne cite un prix tire d'eBay
for t in P6 + [L[i] for i in ("ap_accord", "ap_build", "ap_soumettre", "ap_planb")]:
    assert "profit" not in (t["titre"] + t["note"]).lower()
# une seule fois : une tache rouverte a la main le reste
L["t_sim"]["etat"] = "a_faire"; n = len(c["taches"]); c = ceo._semer(c)
assert len(c["taches"]) == n and {t["id"]: t for t in c["taches"]}["t_sim"]["etat"] == "a_faire"
print("OK test_ceo_apple")
