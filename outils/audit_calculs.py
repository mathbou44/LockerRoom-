"""Audit des calculs d'argent (24 nov 2026, Mathieu : « Repasse chaque fonction et calcul »). Chaque calcul de l'app est refait
ICI, a part, avec sa formule ecrite en clair, sur un compte seme de chiffres connus ; tout ecart de plus d'un cent est note.
Aucun reseau. Usage : python3 outils/audit_calculs.py [--test]   (--test : sort en erreur au premier ecart)."""
import os, sys, tempfile, math
from datetime import datetime
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
for k in ("LR_SURTAXE_US", "LR_TPS_IMPORT", "LR_IMPORT_DEFAUT", "LR_TAXE_ACHAT", "LR_FRAIS_REVENTE_PCT", "LR_FRAIS_REVENTE_FIXE"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import calcul, deals, lockerroom

ECARTS, FAITS = [], []
def voir(nom, obtenu, attendu, tol=0.011):
    ok = (obtenu == attendu) if not isinstance(attendu, (int, float)) or isinstance(attendu, bool) else (obtenu is not None and abs(float(obtenu) - float(attendu)) <= tol)
    FAITS.append(nom)
    if not ok:
        ECARTS.append(f"{nom} : obtenu {obtenu!r}, attendu {attendu!r}")
    return ok

api = lockerroom.Api(os.path.join(tempfile.mkdtemp(), "audit.db"))
R = api.reglages_lire()
PCT, FIXE = R["frais_ebay_pct"] / 100, R["frais_ebay_fixe"]
MOIS = datetime.now().strftime("%Y-%m")
JOUR = MOIS + "-10 12:00:00"

# ---- 1. le profit d'une vente eBay : frais sur (prix + port charge) ; 0,30 $ par commande de 10 $ et moins, 0,40 $ au-dessus
def profit_ebay(prix, cout, port_paye, port_charge, pct=PCT, fixe=FIXE):
    base = prix + port_charge
    f = (0.30 if 0 < base <= 10 and fixe > 0.30 else fixe) if prix else 0.0
    frais = round(base * pct + f, 2)
    net = round(base - frais - port_paye, 2)
    return frais, net, round(net - cout, 2)

VENTES = [  # (titre, cout, prix, port_paye, port_charge, canal, frais du canal)
    ("YG McDavid", 120.0, 300.0, 18.5, 20.0, "eBay", None), ("Base a 8 $", 1.0, 8.0, 1.5, 2.0, "eBay", None),
    ("Pile 10 $", 4.0, 9.0, 0.0, 1.0, "eBay", None), ("Juste au-dessus", 4.0, 9.01, 0.0, 1.0, "eBay", None),
    ("Auto /99", 55.5, 149.99, 22.0, 0.0, "eBay", None), ("Sans cout", None, 40.0, 5.0, 5.0, "eBay", None),
    ("Au comptoir", 10.0, 30.0, 0.0, 0.0, "Magasin", 0.0), ("En break", 25.0, 60.0, 4.0, 0.0, "Break", 6.84),
    ("A perte", 80.0, 45.0, 12.0, 15.0, "eBay", None)]
ids, att = [], {}
for titre, cout, prix, pp, pc, canal, frais in VENTES:
    d = {"titre": titre, "prix_demande": prix}
    if cout is not None:
        d["cout"] = cout
    r = api.carte_sauver(d)
    cid = r.get("id") or (r.get("carte") or {}).get("id")
    ids.append(cid)
    v = api.carte_vendre(cid, {"canal": canal, "prix": prix, "port_paye": pp, "port_charge": pc, "frais": frais, "date": JOUR})
    if canal == "eBay":
        fr, net, pr = profit_ebay(prix, cout or 0.0, pp, pc)
    else:
        fr = frais or 0.0; net = prix - fr - pp; pr = round(net - (cout or 0.0), 2)
    att[cid] = (canal, prix, fr, pr, cout, pp, pc)
    voir(f"vente « {titre} » : frais", v.get("frais"), fr)
    voir(f"vente « {titre} » : profit", v.get("profit"), pr)
# deux cas ecrits a la main, sans la formule : 300 + 20 de port charge, 13,25 % + 0,40 = 42,80 de frais ; net 258,70 ; profit 138,70
if abs(PCT - 0.1325) < 1e-9 and abs(FIXE - 0.40) < 1e-9:
    voir("a la main : McDavid frais", profit_ebay(300, 120, 18.5, 20)[0], 42.80)
    voir("a la main : McDavid profit", profit_ebay(300, 120, 18.5, 20)[2], 138.70)
    voir("a la main : carte a 8 $ (0,30 $ par commande)", profit_ebay(8, 1, 1.5, 2)[0], round(10 * 0.1325 + 0.30, 2))
    voir("a la main : 10,01 $ (0,40 $)", profit_ebay(9.01, 4, 0, 1)[0], round(10.01 * 0.1325 + 0.40, 2))

# ---- 2. le bilan du mois : par canal, la somme des ventes ; le profit seulement des ventes dont le cout est connu
b = api.bilan(MOIS)
for canal in ("eBay", "Magasin", "Break"):
    L = [x for x in att.values() if x[0] == canal]
    voir(f"bilan {canal} : nombre", (b["canaux"].get(canal) or {}).get("nb"), len(L), 0)
    voir(f"bilan {canal} : revenus", (b["canaux"].get(canal) or {}).get("revenus"), round(sum(x[1] for x in L), 2))
    voir(f"bilan {canal} : profit (cout connu seulement)", (b["canaux"].get(canal) or {}).get("profit"), round(sum(x[3] for x in L if x[4] is not None), 2))
voir("bilan : cout des cartes", b["detail"]["couts"], round(sum(x[4] or 0 for x in att.values()), 2))
voir("bilan : frais", b["detail"]["frais"], round(sum(x[2] for x in att.values()), 2))
voir("bilan : livraison nette (payee - chargee)", b["detail"]["port"], round(sum(x[5] - x[6] for x in att.values()), 2))
voir("bilan : ventes sans cout", b["detail"]["sans_cout"], 1, 0)
voir("bilan : un autre mois est vide", api.bilan("2019-01")["canaux"], {})

# ---- 3. l'inventaire : « A vendre » = la somme des prix demandes des cartes pas vendues, hors collection
STOCK = [("Stock 1", 25.0, 10.0, None), ("Stock 2", 99.99, 40.0, None), ("Stock 3", 5.0, None, None), ("Ma collection", None, 30.0, "Collection")]
for titre, prix, cout, lieu in STOCK:
    d = {"titre": titre}
    if prix is not None: d["prix_demande"] = prix
    if cout is not None: d["cout"] = cout
    if lieu: d["emplacement"] = lieu; d["valeur"] = 200.0
    api.carte_sauver(d)
t = api.inventaire_tableaux()
voir("inventaire : nombre a vendre", t["vente"]["n"], 3, 0)
voir("inventaire : valeur a vendre", t["vente"]["valeur"], round(25.0 + 99.99 + 5.0, 2))
voir("inventaire : collection, nombre", t["collection"]["n"], 1, 0)

# ---- 4. la revente d'un deal : ce qui reste, et le plus qu'on peut payer pour garder 30 % et 15 $ de profit
for v in (27.0, 60.0, 80.0, 150.0, 400.0, 2500.0):
    net = v - deals.FRAIS_PCT * (v + deals.PORT_REVENTE) - deals.FRAIS_FIXE - deals.ENVOI_NET
    voir(f"revente de {v:g} $ : net", deals.net_revente(v), net, 0.006)
    budget = max(0.0, min(net / (1 + deals.PROFIT_MIN), net - deals.PROFIT_MIN_D))
    voir(f"revente de {v:g} $ : budget", deals._budget(v), budget, 0.006)
    for tx in (0.05, 0.14975, 0.13):
        pm = deals.prix_max(v, taxe=tx)
        paye = pm * (1 + tx)
        voir(f"valeur {v:g} $, taxe {tx:.3f} : payer le max tient pile dans le budget", paye, budget, 0.006)
        if pm > 0:
            profit = net - paye
            voir(f"valeur {v:g} $, taxe {tx:.3f} : au moins 15 $ et 30 % de profit", profit >= deals.PROFIT_MIN_D - 0.006 and profit >= deals.PROFIT_MIN * paye - 0.006, True)
voir("revente : une carte a 0 $", deals.net_revente(0), 0.0)
# les taxes d'un achat : la province ; aux Etats-Unis, 50 % du prix + la taxe sur le tout
voir("achat au Canada, Alberta", deals.cout_achat(100, deals.taxe_de({"lieu": "CA", "_prov": "AB"})), 105.0)
voir("achat au Canada, Quebec", deals.cout_achat(100, deals.taxe_de({"lieu": "CA"})), 114.98)
voir("achat aux Etats-Unis, 100 $ + 20 $ de port (Quebec)", deals.cout_achat(120, deals.taxe_de({"lieu": "US", "total": 120, "port": 20})), round(1.05 * (120 + 0.5 * 100), 2), 0.02)

# ---- 5. un break : le total des places couvre le cout, la marge et les frais ; aucune place sous le plancher
for evs, cout, marge, pct, fixe, plancher in (([50, 30, 10, 5, 5], 400.0, 0.25, 0.109, 0.30, 5.0), ([1] * 32, 1650.0, 0.20, 0.109, 0.30, 5.0),
                                              ([900, 40, 3, 0, 0, 0], 300.0, 0.0, 0.0, 0.0, 1.0)):
    n = len(evs)
    cible = (cout * (1 + marge) + fixe * n) / max(0.01, 1 - pct)
    prix = calcul.repartir(evs, cible, plancher, 1.0)
    voir(f"break de {n} places : le total atteint la cible", sum(prix) >= cible - 0.01, True)
    voir(f"break de {n} places : le total ne depasse pas la cible de plus d'un cran par place", sum(prix) <= cible + 10.0 * n + 0.01, True)
    voir(f"break de {n} places : aucune sous le plancher", min(prix) >= plancher - 1e-9, True)
    voir(f"break de {n} places : la plus forte valeur paie le plus", prix[evs.index(max(evs))] == max(prix), True)
    # ce que le vendeur garde si tout se vend : revenus - frais - cout >= la marge visee
    pb = calcul.profit_break(sum(prix), n, cout, pct, fixe)
    voir(f"break de {n} places : le profit atteint la marge", pb["profit"] >= cout * marge - 0.05, True)
    voir(f"break de {n} places : profit = revenus - frais - cout", pb["profit"], round(sum(prix) - round(sum(prix) * pct + fixe * n, 2) - cout, 2))

# ---- 6. le rachat au comptoir : 30 % sous 10 $, 50 % sous 50 $, 60 % sous 200 $, 70 % au-dessus ; +10 % en credit
o = calcul.offre_rachat([5, 10, 49.99, 50, 199.99, 200, 1000])
attendu = [5 * .30, 10 * .50, 49.99 * .50, 50 * .60, 199.99 * .60, 200 * .70, 1000 * .70]
for x, a in zip(o["lignes"], attendu):
    voir(f"rachat d'une carte de {x['valeur']:g} $", x["offre"], round(a, 2))
voir("rachat : total comptant", o["comptant"], round(sum(round(a, 2) for a in attendu), 2))
voir("rachat : credit (+10 %)", o["credit"], round(o["comptant"] * 1.10, 2))

# ---- 7. le prix d'une place suit la valeur de ses cartes, et ne depend pas de l'ordre de la liste
liste = [{"joueur": "A", "equipe": "EDM", "recrue": True, "auto": True, "tirage": 25}, {"joueur": "B", "equipe": "TOR", "categorie": "base"},
         {"joueur": "C", "equipe": "MTL", "recrue": True}, {"joueur": "D", "equipe": "BOS", "categorie": "insert"}]
p1 = {x["cle"]: x["prix"] for x in calcul.prix_places(liste, 1, 200.0, mode="equipes", sport="hockey")["places"]}
p2 = {x["cle"]: x["prix"] for x in calcul.prix_places(liste[::-1], 1, 200.0, mode="equipes", sport="hockey")["places"]}
voir("break : meme prix, peu importe l'ordre de la liste", p1, p2)
voir("break : auto recrue /25 > recrue > insertion > base", p1["EDM"] > p1["MTL"] > p1["BOS"] > p1["TOR"], True)
voir("break : les 32 equipes ont une place", len(p1), 32, 0)
# a valeur EGALE, l'arrondi donne le cran de plus aux premieres de la liste : ecart d'un cran au plus (connu, sans risque)
egal = [{"joueur": j, "equipe": e, "recrue": True} for j, e in (("A", "EDM"), ("B", "TOR"), ("C", "MTL"))]
pe = [x["prix"] for x in calcul.prix_places(egal, 1, 200.0, mode="equipes", sport="hockey")["places"] if x["cle"] in ("EDM", "TOR", "MTL")]
voir("break : a valeur egale, un cran d'ecart au plus", max(pe) - min(pe) <= 5.0, True)

# ---- 8. faire grader : le gain = ce que la carte gradee rapporte, moins ce que la carte brute rapporte, moins le cout
import gradation
for bas, haut in ((9, 9), (8, 10), (10, 10), (7, 8), (None, 9)):
    pr = gradation.probas(bas, haut)
    voir(f"gradation : les chances de {bas} a {haut} font 100 %", sum(pr.values()), 1.0, 0.002)
    voir(f"gradation : aucune note au-dessus de 10 ni chance negative ({bas} a {haut})", all(1 <= g <= 10 and p > 0 for g, p in pr.items()), True)
TAUX_, PCT_, FIXE_, PORT_ = 1.40, 0.1325, 0.40, 20.0
vals = {10: {"valeur": 400.0, "n": 6}, 9: {"valeur": 150.0, "n": 9}, 8: {"valeur": 90.0, "n": 4}}
g = gradation.calculer(100.0, vals, 9, 9, TAUX_, PCT_, FIXE_, 1, PORT_, compagnie="PSA", taxes_pct=0)
pr = gradation.probas(9, 9)
ev = sum(p * vals[n]["valeur"] for n, p in pr.items())
cout = round(g["service"]["prix_usd"] * TAUX_ + PORT_, 2)
net_ = lambda v: v * (1 - PCT_) - FIXE_
voir("gradation : valeur esperee", g.get("valeur_esperee"), round(ev, 2))
voir("gradation : cout (service en $ US x taux + port)", g.get("cout"), cout)
voir("gradation : gain", g.get("gain"), round(net_(ev) - net_(100.0) - cout, 2))
gain = net_(ev) - net_(100.0) - cout
voir("gradation : verdict", g.get("verdict") in ("oui", "pari_10") if gain > max(15.0, 0.10 * cout) else g.get("verdict") in ("non", "juste", "pari_10"), True)
voir("gradation : le service choisi couvre la valeur declaree", g["service"].get("max_usd") is None or g["service"]["max_usd"] >= g["valeur_declaree_usd"] or not g.get("plafond"), True)
# une carte qui ne vaut pas la peine : gradee 60 $ au mieux, brute 50 $
g2 = gradation.calculer(50.0, {10: {"valeur": 60.0, "n": 5}, 9: {"valeur": 52.0, "n": 5}, 8: {"valeur": 45.0, "n": 5}}, 9, 9, TAUX_, PCT_, FIXE_, 1, PORT_)
voir("gradation : une carte qui n'en vaut pas la peine dit non", g2.get("verdict"), "non")
voir("gradation : sans ventes gradees, aucun verdict invente", gradation.calculer(100.0, {}, 9, 9, TAUX_).get("verdict"), "pas_assez")

if __name__ == "__main__":
    print(f"AUDIT DES CALCULS : {len(FAITS)} verifications, {len(ECARTS)} ecart(s)")
    for e in ECARTS:
        print("  ECART", e)
    if "--test" in sys.argv and ECARTS:
        sys.exit(1)
