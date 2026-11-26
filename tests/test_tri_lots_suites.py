"""26 nov 2026 (Mathieu : « corrige ») : deux failles du tri des ventes, vues en verifiant les tendances des cartes et mesurees
sur 1,97 M de ventes (6 628 ventes mal rangees, 371 recherches ; « sidney crosby young guns » : mediane de 20 $ au lieu de 1 831 $).
 1. un lot ecrit avec « + » (« Young Guns + Dazzlers ») passait pour la carte seule ;
 2. sans annee dans la recherche, la suite d'un set (« Young Guns Renewed », « Young Guns Achievement ») passait pour le set.
Et le verdict garde de ces ventes (base_ventes, table accepte) est efface une fois pour etre refait."""
import os, sys, tempfile, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import cartes_match as c

def refus(q, titre):
    return c.raisons_refus(c.cible(q), titre)

# ---- 1. LE LOT ECRIT AVEC « + »
LOTS = [("cole hutson young guns", "2026/27 Upper Deck NHL Cole Hutson Rookie YOUNG GUNS + Dazzlers 🔥🔥🏒🏒"),
        ("calum ritchie young guns outburst", "2024-25 Upper Deck Series 2 #477 Calum Ritchie Young Guns Outburst + Base YG"),
        ("anton lundell young guns", "2021-22 Upper Deck Young Guns #489 Anton Lundell + 3 Rookie Cards RC Mint"),
        ("cutter gauthier young guns", "2024-25 Upper Deck Series 1 - Young Guns Cutter Gauthier #212 (RC) +more"),
        ("evan bouchard young guns", "2018-19 Upper Deck Young Guns #221 Evan Bouchard + O-Pee-Chee Marquee Rookie"),
        ("easton cowan young guns", "2025-26 Upper Deck Series 2 - Young Guns Easton Cowan #462 (RC) + Inserts"),
        ("ivan demidov young guns", "IVAN DEMIDOV 2025-26 UD SERIES 1 YOUNG GUNS ROOKIE #205 CANADIENS Q6438 + Bonus"),
        ("macklin celebrini o-pee-chee glossy", "2024-25 O-Pee-Chee Glossy Macklin Celebrini Rookie + 2 others")]
for q, t in LOTS:
    assert refus(q, t) == ["lot / pas une carte seule"], (q, t, refus(q, t))
# la meme chose pour les comparables d'une annonce (cible_titre)
ct = c.cible_titre("2026-27 Upper Deck Series 1 Young Guns Cole Hutson #201 RC")
assert "lot / pas une carte seule" in c.raisons_refus(ct, "2026-27 Upper Deck Cole Hutson Young Guns #201 + 3 Rookie Cards"), "le lot gonflait aussi les comps d'une annonce"
assert c.raisons_refus(ct, "2026-27 Upper Deck Young Guns Cole Hutson #201 RC") == []
PAS_LOTS = [("dale hawerchuk o-pee-chee", "1982 83 OPC O-Pee-Chee #380 Dale Hawerchuk Rookie Rc Vg-Ex+ Jets"),                 # la cote d'etat
            ("wayne gretzky o-pee-chee ksa 8", "1982-83 OPC O PEE CHEE #106 Wayne Gretzky KSA 8.5 NM-MINT + Edmonton Oilers Card"),
            ("tim horton parkhurst", "1952-53 PARKHURST #58 TIM HORTON 3.5 VERY GOOD + RC ROOKIE MAPLE LEAFS 833"),
            ("joe montana psa 8", "JOE MONTANA 1994 Topps Finest #172 KC Chiefs PSA 8 + COUPONS + FREE SHIPPING!"),        # un envoi offert
            ("ken griffey jr auto psa", "KEN GRIFFEY JR signed 1990 Donruss DIAMOND KING Baseball Card #4 + PSA Auto"),     # un certificat
            ("steve yzerman game used", "2002-03 Parkhurst ITG Steve Yzerman Stick + Jersey SJ-5 GAME USED Memorabilia"),   # la meme carte
            ("macklin celebrini smith young guns", "MACKLIN CELEBRINI + WILL SMITH 2024-25 UPPER DECK YOUNG GUNS ROOKIE RC #499"),   # 2 joueurs
            ("quinn hughes young guns psa", "2019/20 UD UPPER DECK Jack + Quinn Hughes YOUNG GUNS RC ROOKIES PSA 9"),
            ("easton cowan outburst round draft", "Easton Cowan Round 1 Draft OUTBURST ROOKIE ++ - 2025-26 Upper Deck #748")]
for q, t in PAS_LOTS:
    assert "lot / pas une carte seule" not in refus(q, t), (q, t, refus(q, t))
assert c._plus_lot("Young Guns + Dazzlers") == ("dazzlers", "") and c._plus_lot("Young Guns EX+ Jets") is None and c._plus_lot("YG RC") is None
assert c.decoder("Cole Hutson Young Guns + Dazzlers")["plus"] and not c.decoder("Cole Hutson Young Guns")["plus"]
assert c.decoder("Cole Hutson Young Guns + Dazzlers")["exclu"] is False, "le champ « exclu » ne change pas (le Radar, la lettre SlabIQ et le test du site s'en servent)"
# une recherche qui est elle-meme un lot garde les lots
assert "lot / pas une carte seule" not in refus("cole hutson young guns lot", "Cole Hutson Young Guns + Dazzlers lot")

# ---- 2. LA SUITE D'UN SET (« RENEWED », « ACHIEVEMENT »)
AUTRES = [("matthew tkachuk young guns psa 10", "2024 UPPER DECK YOUNG GUNS RENEWED #231 MATTHEW TKACHUK PSA 10", "renewed"),
          ("sidney crosby young guns", "2024-25 UD Series 1 Young Guns Renewed Sidney Crosby YGR-10 Penguins 9934", "renewed"),
          ("connor mcdavid young guns", "2024-25 Upper Deck Young Guns Renewed Connor McDavid #201 Edmonton Oilers", "renewed"),
          ("connor mcdavid young guns", "Upper Deck 2024-25 Series Two Young Guns Connor McDavid Oilers #201 Renewd Clean", "renewed"),
          ("marc-andre fleury young guns", "Upper Deck Young Guns Marc-Andre Fleury #YGR-9 Pittsburgh Penguins", "renewed"),      # le code seul
          ("mark scheifele young guns", "2025 26 Upper Deck Mark Scheifele Young Guns Achievement #YGA-6 Jets", "achievement"),
          ("cale makar young guns", "2025-26 Upper Deck Cale Makar Young Guns #YGA-10", "achievement"),
          ("brad marchand young guns", "2024-25 Series 2 2024-25 Young Guns Level Achievement Brad Marchand READ 11q9", "achievement")]
for q, t, mot in AUTRES:
    assert refus(q, t) == ["autre carte (" + mot + ")"], (q, t, refus(q, t))
MEMES = [("matthew tkachuk young guns psa 10", "2016-17 Upper Deck Young Guns #231 Matthew Tkachuk PSA 10"),
         ("sidney crosby young guns", "Sidney Crosby 2005-06 Upper Deck Young Guns Rookie #201"),
         ("sidney crosby young guns renewed", "2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10"),      # la recherche le nomme
         ("sidney crosby ygr-10", "2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10"),
         ("anze kopitar", "2024-25 Upper Deck Series 1 Young Guns Renewed Anze Kopitar #YGR-17"),                   # le joueur seul : tout
         ("connor mcdavid edmonton oilers psa 9", "Connor McDavid 2024 Upper Deck 201 Young Guns Renewed PSA 9 Edmonton Oilers"),   # une equipe
         ("connor mcdavid upper deck", "2024-25 Upper Deck Young Guns Renewed Connor McDavid #201"),              # une marque
         ("jaromir jagr young guns", "2001 UPPER DECK #226 JAROMIR JAGR YOUNG GUNS FLASHBACK"),                   # sa seule « Young Guns »
         ("zach benson auto", "Upper Deck Game Dated Moments Zach Benson Sabres RC Achievement Auto #23")]
for q, t in MEMES:
    assert refus(q, t) == [], (q, t, refus(q, t))
assert refus("sidney crosby young guns renewed", "2005-06 Upper Deck Young Guns Sidney Crosby #201"), "l'inverse tenait deja : la Renewed n'est pas la vraie"
assert c.cible("sidney crosby young guns")["carte_nommee"] and c.cible("macklin celebrini dazzlers blue")["carte_nommee"]
for q in ("anze kopitar", "connor mcdavid upper deck", "connor mcdavid edmonton oilers psa 9", "nolan ryan patch", "auto /25"):
    assert not c.cible(q)["carte_nommee"], q
# les comparables d'une annonce gardent leur regle (les mots d'identite) : rien ne change pour eux
ren = c.cible_titre("2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10")
assert c.raisons_refus(ren, "2024-25 UD Series 1 Young Guns Renewed Sidney Crosby YGR-10 Penguins") == []
vraie = c.cible_titre("2005-06 Upper Deck Young Guns Sidney Crosby #201")
assert c.raisons_refus(vraie, "2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10")

# ---- 3. LE VERDICT GARDE EST REFAIT UNE FOIS (base_ventes)
import base_ventes as b
import comptes
ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
cx = b._cx()
V = [("sidney crosby young guns", "1", "2024-25 Upper Deck Young Guns Renewed Sidney Crosby #YGR-10", 20.0),
     ("sidney crosby young guns", "2", "Sidney Crosby 2005-06 Upper Deck Young Guns Rookie #201", 1800.0),
     ("cole hutson young guns", "3", "Cole Hutson Young Guns + Dazzlers", 57.0),
     ("cole hutson young guns", "4", "2026-27 Upper Deck Young Guns Cole Hutson #201", 40.0),
     ("mark scheifele young guns", "5", "Mark Scheifele Young Guns Achievement #YGA-6", 19.0),
     ("mark scheifele young guns", "6", "Mark Scheifele Young Guns lot", 9.0)]
cx.execute("CREATE TABLE IF NOT EXISTS accepte (q TEXT, cle TEXT, ok INTEGER, PRIMARY KEY (q, cle))")
for q, cle, t, p in V:
    cx.execute("INSERT INTO ventes (q, cle, titre, prix, le) VALUES (?,?,?,?,?)", (q, cle, t, p, "2026-11-20"))
    cx.execute("INSERT INTO accepte VALUES (?,?,?)", (q, cle, 0 if cle == "6" else 1))
cx.commit(); cx.close()
assert b.retrier_si_regle_change() == 3, "les 3 verdicts « garde » des ventes Renewed, « + » et Achievement sont effaces"
cx = sqlite3.connect(ch)
assert sorted(cx.execute("SELECT cle, ok FROM accepte")) == [("2", 1), ("4", 1), ("6", 0)], "les autres verdicts restent (un refus aussi)"
assert cx.execute("PRAGMA user_version").fetchone()[0] == b.TRI_VERSION
cx.execute("INSERT INTO accepte VALUES ('sidney crosby young guns', '1', 1)"); cx.commit(); cx.close()
assert b.retrier_si_regle_change() == 0, "une seule fois par base"
cx = sqlite3.connect(ch); assert cx.execute("SELECT COUNT(*) FROM accepte").fetchone()[0] == 4; cx.close()
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "base_ventes.py"), encoding="utf-8").read()
assert "    retrier_si_regle_change()\n" in src.split("def cartes_toutes(")[1][:400], "cartes_toutes refait le tri avant de lire"
print("TRI LOTS ET SUITES OK")
