"""16 nov 2026 : le bareme SlabIQ ecrit avec l'expert (questionnaires, rondes 1 a 4) : chaque reponse de Mathieu est un test."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import bareme_iq as b

S = lambda t: b.sorte(t)[0]
# la sorte (la carte seulement)
assert S("Lane Hutson 2024-25 Upper Deck Young Guns #201") == "A"                    # YG raw
assert S("Lane Hutson 2024-25 Upper Deck Young Guns PSA 10") == "A+"                 # YG gradee 10
for v in ("Exclusives /100", "High Gloss /10", "Canvas", "Clear Cut", "Outburst", "Deluxe", "Silver Foil", "French", "Retro",
          "Photo Variation SSP"):
    assert S("Ivan Demidov 2025-26 Upper Deck Young Guns Rookie " + v) == "A+", v    # toutes les variantes de YG
assert S("2025-26 Upper Deck Extended Series Outburst Retro Young Guns Kris Letang #OR-29") == "B"    # Retro YG d'un veteran
assert S("2024-25 Upper Deck Series 2 Young Guns Renewed Connor McDavid #201") == "D"                 # Renewed : presque rien (ventes)
# 25 nov 2026 (Mathieu, Makar Renewed Exclusives /100 notee C : « Renewed Exclusives est une carte B ») : une Renewed numerotee suit
# la regle des numerotees ; la Renewed de base reste D
assert b.sorte("2024-25 Upper Deck Young Guns Renewed Exclusives Cale Makar #49 075/100") == ("B", "yg_renewed_num")
assert S("2024-25 Upper Deck Young Guns Renewed Exclusives Zach Hyman") == "B"                        # sans le tirage dans le titre
assert S("2024-25 Upper Deck Young Guns Renewed UD Exclusive #YGR-27 Steven Stamkos 5/100") == "B"
assert S("2024-25 UD Young Guns Renewed High Gloss Sidney Crosby 3/10") == "A-"
assert S("2024-25 Upper Deck Young Guns Renewed Outburst Connor McDavid") == "D"                      # une parallele sans numero : D
assert S("Macklin Celebrini 2024-25 The Cup Rookie Auto Patch RPA /249") == "A+"
assert S("Quinn Hutson 2025-26 SP Authentic Future Watch Auto Patch /100") == "A+"
assert S("Matt Duchene 2009-10 Upper Deck Victory #250") == "D"                       # une base
assert S("2023-24 Upper Deck Series 1 checklist lot Bedard") == "D"
assert S("Mathew Barzal 2017-18 SP Authentic Limited Auto /25") == "B+"              # numerotee /25-/50
assert S("2023-24 Upper Deck Kaboom Connor Bedard") != "A+"                           # pas de Kaboom au hockey
assert S("2023 Panini Kaboom Victor Wembanyama") == "A+"                              # ... mais oui ailleurs

# ronde 5 : les recrues d'avant les YG, les grosses recrues autographes
assert S("1979-80 O-Pee-Chee Wayne Gretzky #18 Rookie RC") == "A"
assert S("1985-86 O-Pee-Chee Mario Lemieux #9 RC PSA 10") == "A+"
assert S("1990-91 Upper Deck Jaromir Jagr #356 Rookie RC") == "A"
assert S("2023-24 O-Pee-Chee Rookie Logan Cooley #601 RC") != "A"                    # une recrue moderne hors YG
assert S("2024-25 Ultimate Collection Macklin Celebrini Rookie Auto Patch /99") == "A"
assert S("2023-24 SPx Rookie Auto Connor Bedard RC") == "B+"                          # 18 nov : SPx, Trilogy, SPGU sous SP Authentic
assert S("2023-24 Trilogy Rookie Auto Patch Connor Bedard RC /399") == "A-"
assert S("2023-24 SP Game Used Rookie Auto Connor Bedard RC") == "B+"
assert S("2023-24 Black Diamond Rookie Gems Auto Connor Bedard RC") == "A"
assert S("2023-24 Stature Rookie Auto Connor Bedard RC") == "A"
assert S("2023-24 Upper Deck Splendor Rookie Auto Connor Bedard RC") == "A+"
assert S("2024-25 Tableau Rookie Auto Macklin Celebrini RC") == "A+"
assert S("2023-24 SP Authentic Future Watch Auto Connor Bedard RC") == "A+"
# 18 nov : courtes impressions
assert S("2023-24 O-Pee-Chee Platinum Marquee Rookies SSP Connor Bedard RC") == "A-"
assert S("2023-24 Upper Deck Allure 16-Bit Alex Ovechkin") == "A-"
assert S("2023-24 Upper Deck Allure 16-Bit Alex Ovechkin PSA 10") == "A+"
assert S("2023-24 O-Pee-Chee Platinum Marquee Rookies Photo Variation SP Logan Cooley RC") == "B+"
assert S("2023-24 Upper Deck Short Print Variation Sidney Crosby PSA 10") == "A+"
assert S("2025-26 Upper Deck Series 2 Fanimation Connor McDavid") != "A-"         # 18 nov : mesure x0,64, retire des SSP
assert S("2025-26 Upper Deck Series 1 Pro Visions Connor McDavid") == "A-"
assert S("2025-26 Upper Deck Series 1 Holotypes Macklin Celebrini PSA 10") == "A+"
assert S("2025-26 Upper Deck Series 1 Dazzlers Lane Hutson") == "C"              # 18 nov : la Dazzlers de base C (Mathieu)
assert S("2025-26 Upper Deck Series 1 Dazzlers Gold Lane Hutson") == "A-"
assert b.note_joueur("Marc-Andre Fleury")[1] == "A-"
assert b.note_joueur("Brandon Hagel")[1] == "B"
assert b.note_joueur("Matthew Tkachuk")[1] == "B+"

# 16 nov (« genre de carte qui devrait etre E ») : l'insert n'est pas le joueur ; un joueur sans demande donne E
import cartes_match
assert cartes_match.joueur_du_titre("2021-22 Upper Deck SPX Hockey Finite Rookies Sampo Ranta F-28 276/299") == "sampo ranta"
assert cartes_match.joueur_du_titre("2023-24 Engrained Hockey Rookie Signature Shots Vincent Iorio RSS-VI 096/299") == "vincent iorio"
assert b.lettre(b.note_finale(b.NOTE["C"], b.JOUEUR_INCONNU)) == "E"
assert b.note_finale(b.NOTE["B"], b.note_joueur("X", {"demande": 30, "notoriete": 13})[0]) < 65            # un joueur peu demande : hors du Radar
assert not b.recrue_recente("2021-22 Upper Deck SPX Finite Rookies Sampo Ranta", True)

# le joueur : la cote de collection de l'expert
assert b.note_joueur("Cole Caufield")[1] == "A+"
assert b.note_joueur("Jakub Dobes")[1] == "B"
assert b.note_joueur("Brendan Smith")[1] == "D"
assert b.note_joueur("Inconnu Total")[2] == "inconnu"
assert b.note_joueur("Inconnu Total", recrue=True)[1] == "B"                          # « rookie inconnu = B »
assert b.note_joueur("X", {"demande": 99, "notoriete": 99})[1] in ("A+", "A")
assert b.note_joueur("X", {"demande": 50, "notoriete": 40})[1] in ("C", "D")
assert b.note_joueur("X", {"demande": 15, "notoriete": 10})[1] == "E"

# la note finale : le plus faible domine
L = lambda s, j: b.lettre(b.note_finale(b.NOTE[s], b.NOTE[j]))
assert L("A", "C") == "C"            # « une YG raw d'un joueur moyen -> C »
assert L("D", "A+") == "C"           # « une base d'une superstar -> C »
assert L("A", "A+") == "A"           # Celebrini YG raw
assert L("A+", "B") == "B+"          # Quinn Hutson FW Auto Patch
assert L("A+", "B+") == "A-"         # Duchene YG PSA 10, Scheifele Cup RPA
assert L("A", "D") == "C"            # Brendan Smith YG
# en feu : un demi-cran
assert b.lettre(b.note_finale(b.NOTE["A"], b.NOTE["B+"]) + b.FEU_PTS) == "A-"   # Marner YG B+ -> A-
# 17 nov 2026 : tous les paralleles de YG (couleurs, Acetate) ; les courtes impressions non numerotees
assert S("2024-25 Upper Deck Young Guns Acetate Lane Hutson") == "A+"
assert S("2024-25 Upper Deck Young Guns Outburst Gold Macklin Celebrini") == "A+"
assert S("2024-25 Upper Deck Young Guns Detroit Red Wings Marco Kasper") == "A"          # Red Wings n'est pas un parallele
assert S("2025-26 O-Pee-Chee Platinum Marquee Rookies Photo Variation Ivan Demidov") == "B+"
assert S("Lane Hutson 2024-25 SP Authentic #50") == "D"                                  # SP Authentic n'est pas une SP
assert len(b.familles()) >= 6 and b.familles()[0]["lettre"] == "A+"
# 18 nov 2026 (Mathieu, reponses aux questions de la nuit)
assert S("2025-26 Upper Deck Series 2 Fluorescence Ivan Demidov") == "D"
assert S("2025-26 SP Hockey Ivan Demidov #12") == "D"                              # « SP » le produit, pas un short print
assert S("2025-26 Upper Deck MVP Ivan Demidov SP") == "B+"                         # « SP » = short print
print("BAREME IQ OK")

# 22 nov 2026 (Mathieu, Schaefer / Gatcomb Young Guns #499 notee A+ : « plus B que A+, c'est une Young Guns duo ») : la carte
# des Young Guns a deux recrues (le « checklist ») n'est la Young Guns d'aucun des deux : B ; la vraie YG ne bouge pas
import bareme_iq as _bq
assert _bq.sorte("2025-26 Upper Deck Series 2 Matthew Schaefer Marc Gatcomb Young Guns #499 RC") == ("B", "yg_duo")
assert _bq.sorte("2015-16 Upper Deck Young Guns Checklist Connor McDavid Max Domi #249")[1] == "yg_duo"
assert _bq.sorte("2025-26 Upper Deck Series 2 Matthew Schaefer Young Guns #451 RC")[1] == "yg"
assert _bq.sorte("2023-24 Upper Deck Young Guns Connor Bedard #451 PSA 10") == ("A+", "yg10")
assert _bq.sorte("2024-25 Upper Deck Young Guns lot of 12 rookies") == ("D", "lot_checklist")
print("BAREME IQ : YOUNG GUNS DUO OK")
