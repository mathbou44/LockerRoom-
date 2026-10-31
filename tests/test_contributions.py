"""31 oct 2026 - checklist envoyee par un utilisateur : validee et publiee seule, ou en attente pour l'admin. Aucun reseau."""
import base64, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = tempfile.mkdtemp()
os.environ["LOCKERROOM_DONNEES"] = D
import catalogue, comptes, contributions, lockerroom, valeurs

JOUEURS = ["Connor McDavid", "Leon Draisaitl", "Auston Matthews", "Nathan MacKinnon", "Cale Makar", "Sidney Crosby", "Nikita Kucherov",
           "David Pastrnak", "Jack Hughes", "Quinn Hughes", "Kirill Kaprizov", "Jason Robertson", "Mitch Marner", "Matthew Tkachuk",
           "Brady Tkachuk", "Tim Stutzle", "Jack Eichel", "Mikko Rantanen", "Elias Pettersson", "Artemi Panarin", "Igor Shesterkin",
           "Connor Bedard", "Macklin Celebrini", "Ivan Demidov", "Lane Hutson", "Matvei Michkov", "Leo Carlsson", "Logan Cooley",
           "Adam Fantilli", "Will Smith", "Juraj Slafkovsky", "Shane Wright", "Owen Power", "Mason McTavish", "Matty Beniers",
           "Wyatt Johnston", "Luke Hughes", "Dylan Guenther", "Kent Johnson", "Marco Rossi", "Cole Caufield", "Nick Suzuki", "Zach Hyman"]

def csv(n_base, faux=False):
    l = ["Set Name,Card,Description,Team"]
    for i in range(n_base):
        j = ("Zork Blip" + str(i)) if faux else JOUEURS[i % len(JOUEURS)]
        l.append(f"Base Set,{i + 1},{j},Edmonton Oilers")
    for i in range(10):
        l.append(f"Young Guns,{201 + i},{('Qux Flarb' + str(i)) if faux else JOUEURS[-(i + 1)]},Montreal Canadiens")
    return base64.b64encode("\n".join(l).encode()).decode()

def main():
    api = lockerroom.Api()
    comptes.MULTI = True
    comptes.courant = lambda: "c1"
    api._est_admin = lambda: False
    valeurs.statut = lambda: {"nb_joueurs": 100}
    valeurs.connu = lambda j: j in JOUEURS
    # 1. bonne checklist : publiee pour tous, marquee « contribue »
    r = api.catalogue_importer({"fichier": csv(60), "nom_fichier": "2031-32 Upper Deck Zeta Hockey.csv", "sport": "hockey"})
    assert r["ok"] and r.get("publie") and not r.get("attente"), r
    p = catalogue.charger(r["id"])
    assert p and p.get("contribue", {}).get("compte") == "c1"
    # 2. la meme : deja au catalogue, jamais remplacee
    r2 = api.catalogue_importer({"fichier": csv(60), "nom_fichier": "2031-32 Upper Deck Zeta Hockey.csv", "sport": "hockey"})
    assert r2["ok"] and r2.get("deja"), r2
    # 3. joueurs inconnus et sans marque : en attente, pas au catalogue
    r3 = api.catalogue_importer({"fichier": csv(60, faux=True), "nom_fichier": "2031-32 Mystery Cards.csv", "sport": "hockey"})
    assert r3["ok"] and r3.get("attente") and r3["raisons"], r3
    assert not catalogue.charger(r3["id"])
    att = contributions.liste_attente()
    assert [x["id"] for x in att] == [r3["id"]]
    # 4. trop court : en attente
    r4 = api.catalogue_importer({"fichier": csv(12), "nom_fichier": "2031-32 Topps Mini Hockey.csv", "sport": "hockey"})
    assert r4.get("attente") and any("cartes lues" in x for x in r4["raisons"]), r4
    # 5. l'admin : publier, refuser, retirer ; un utilisateur ne peut pas
    assert not api.admin_contribution(r3["id"], "publier")["ok"]
    api._est_admin = lambda: True
    assert api.admin_contributions()["ok"] and len(api.admin_contributions()["attente"]) == 2
    assert api.admin_contribution(r3["id"], "publier")["ok"] and catalogue.charger(r3["id"])
    assert api.admin_contribution(r4["id"], "refuser")["ok"] and not contributions.liste_attente()
    assert api.admin_contribution(r["id"], "retirer")["ok"] and not catalogue.charger(r["id"])
    assert os.listdir(contributions.dossier_retires())                 # deplace, jamais efface
    # 6. quota : 10 par jour
    api._est_admin = lambda: False
    comptes.courant = lambda: "c2"
    for _ in range(contributions.MAX_JOUR):
        assert contributions.quota_prendre("c2")
    assert "par jour" in api.catalogue_importer({"fichier": csv(60), "nom_fichier": "x.csv"})["erreur"]
    print("ok")

if __name__ == "__main__":
    main()
