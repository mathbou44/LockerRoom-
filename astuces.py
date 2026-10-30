"""
LOCKERROOM - « Le savais-tu ? » : des astuces verifiees, melees aux nouvelles de l'accueil (26 oct 2026).

Mathieu : « ajouter dans les news des tips et renommer la section Tips & News. Genre : savais-tu que les cartes des
nouveaux produits tendent a descendre de x % avant de remonter ? et leur donner le truc. Une douzaine, pertinents,
valides, testes et verifies, pour aider les utilisateurs de tous les niveaux ».

Deux sortes d'astuces :
  - CALCULEES sur les vraies donnees de SlabCoach (ventes SoldComps de la base, checklists, frais du compte) :
    le chiffre est celui du jour, et l'astuce disparait s'il n'y a pas assez de donnees pour l'affirmer ;
  - SOURCEES : un fait publie (source et lien affiches), et le calcul qu'on peut refaire soi-meme.
Chaque astuce : titre, le chiffre, le truc (quoi faire), niveau (debutant / tous / avance), source.
"""
import json
import math
import os
import re
import statistics
import time
from datetime import datetime, timedelta

FRAICHEUR_S = 6 * 3600
_CACHE = {"le": 0.0, "cle": None, "l": []}


def _med(l):
    return statistics.median(l) if l else None


def T(langue):
    return (lambda fr, en: en if langue == "en" else fr)


def _pct(a, b):
    return round(100 * (b - a) / a) if a else None


# -- 1. la chute apres la sortie (ventes reelles des recrues des produits sortis depuis moins de 4 mois) ---------
def chute_sortie(api=None, langue="fr"):
    t = T(langue)
    import catalogue
    import valeur_produit
    out = []
    for p in catalogue.liste():
        try:
            sortie = datetime.fromisoformat(str(p.get("sortie") or "")[:10])
        except ValueError:
            continue
        if not timedelta(days=12) <= datetime.now() - sortie <= timedelta(days=120):
            continue
        e = valeur_produit.de(p["id"]).get("sous") or {}
        for sn, s in e.items():
            if not re.search(r"young guns|rookie|recrue|future watch", sn, re.I):
                continue
            for j, x in (s.get("joueurs") or {}).items():
                pts = sorted((str(d)[:10], float(v)) for d, v in (x.get("p") or []) if d and v)
                if len(pts) < 6:
                    continue
                d0 = datetime.fromisoformat(pts[0][0])
                d1 = datetime.fromisoformat(pts[-1][0])
                if (d1 - d0).days < 10:
                    continue
                debut = [v for d, v in pts if datetime.fromisoformat(d) <= d0 + timedelta(days=6)]
                fin = [v for d, v in pts if datetime.fromisoformat(d) >= d1 - timedelta(days=6)]
                if len(debut) >= 2 and len(fin) >= 2:
                    out.append({"produit": p["nom"], "carte": sn, "joueur": j, "debut": _med(debut), "fin": _med(fin),
                                "pct": _pct(_med(debut), _med(fin)), "jours": (d1 - d0).days})
    if len(out) < 5:
        return None
    pcts = sorted(x["pct"] for x in out)
    baisse = sum(1 for x in pcts if x < 0)
    ex = min(out, key=lambda x: x["pct"])
    prod = max({x["produit"] for x in out}, key=lambda n: sum(1 for x in out if x["produit"] == n))
    return {"id": "chute_sortie", "niveau": "tous", "genre": "acheter",
            "titre": t(f"Les recrues de {prod} : {_med(pcts):+.0f} % depuis leur 1re semaine", f"{prod} rookies: {_med(pcts):+.0f}% since their first week"),
            "chiffre": f"{_med(pcts):+.0f} %",
            "texte": t(f"Sur {len(out)} cartes de recrues suivies dans SlabCoach, {baisse} valent moins qu’à leur 1re semaine de ventes "
                       f"(médiane {_med(pcts):+.0f} %). Exemple : {ex['joueur']}, {ex['carte']}, {ex['debut']:.0f} $ → {ex['fin']:.0f} $.",
                       f"Of {len(out)} rookie cards tracked in SlabCoach, {baisse} are worth less than in their first week of sales "
                       f"(median {_med(pcts):+.0f}%). Example: {ex['joueur']}, {ex['carte']}, ${ex['debut']:.0f} → ${ex['fin']:.0f}."),
            "truc": t("Les premières semaines, peu de boîtes sont ouvertes et les acheteurs paient pour être les premiers. Sauf pour une "
                      "vraie vedette, attends 3 à 6 semaines : l’offre monte et le prix se stabilise.",
                      "In the first weeks few boxes are opened and buyers pay to be first. Unless it’s a true star, wait 3 to 6 weeks: "
                      "supply grows and the price settles."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"), "lien": "#valeur", "calcule": True}


# -- 2. un exemple publie : Bedard ------------------------------------------------------------------------------
def bedard(api=None, langue="fr"):
    t = T(langue)
    return {"id": "bedard", "niveau": "debutant", "genre": "acheter",
            "titre": t("Young Guns de Bedard : −68 % en 12 jours", "Bedard Young Guns: −68% in 12 days"),
            "chiffre": "−68 %",
            "texte": t("Le 6 mars 2024, la première Young Guns de Connor Bedard s’est vendue 1 200 $ sur eBay. Douze jours plus tard, "
                       "elle partait à 389 $ (offre acceptée) : chaque boîte ouverte ajoutait des copies sur le marché.",
                       "On March 6, 2024, the first Connor Bedard Young Guns sold for $1,200 on eBay. Twelve days later it went for "
                       "$389 (accepted offer): every box opened added copies to the market."),
            "truc": t("Une recrue très attendue coûte le plus cher le jour de la sortie. Mets une alerte de prix au lieu d’acheter le premier jour.",
                      "A hyped rookie is most expensive on release day. Set a price alert instead of buying on day one."),
            "source": "Puck Junk, 2024-03-21", "url": "https://puckjunk.com/2024/03/21/the-decline-of-connor-bedards-young-guns-card/",
            "lien": "#alertes", "calcule": False}


# -- 3. les frais : une petite carte ne rapporte presque rien -----------------------------------------------------
def frais(api=None, langue="fr"):
    t = T(langue)
    r = api.reglages_lire()
    fp, ff = (r.get("frais_ebay_pct") or 0) / 100, r.get("frais_ebay_fixe") or 0
    if not fp:
        return None
    net5 = 5 * (1 - fp) - ff
    return {"id": "frais", "niveau": "debutant", "genre": "vendre",
            "titre": t(f"Une carte vendue 5 $ te laisse {net5:.2f} $", f"A card sold for $5 leaves you ${net5:.2f}"),
            "chiffre": t(f"{net5:.2f} $", f"${net5:.2f}"),
            "texte": t(f"Avec tes frais eBay ({fp * 100:.1f} % + {ff:.2f} $ par vente), une carte à 5 $ te rapporte {net5:.2f} $ avant "
                       "l’enveloppe et le timbre. C’est pour ça que SlabCoach ne compte pas les cartes de moins de 1,50 $ dans la "
                       "valeur d’un break : elles ne se revendent pas.",
                       f"With your eBay fees ({fp * 100:.1f}% + ${ff:.2f} per sale), a $5 card nets ${net5:.2f} before the envelope and "
                       "stamp. That’s why SlabCoach ignores cards under $1.50 in a break’s value: they don’t resell."),
            "truc": t("Vends les petites cartes en lot (équipe, joueur, set) et garde la vente à l’unité pour ce qui vaut 10 $ et plus.",
                      "Sell small cards as lots (team, player, set) and keep single sales for cards worth $10 and up."),
            "source": t("Tes frais (Réglages), calcul SlabCoach", "Your fees (Settings), SlabCoach math"), "lien": "#reglages", "calcule": True}


# -- 4. la numerotation : la rarete se calcule -------------------------------------------------------------------
def numerotation(api=None, langue="fr"):
    t = T(langue)
    return {"id": "numerotation", "niveau": "debutant", "genre": "info",
            "titre": t("Une /10 est 10 fois plus rare qu’une /99", "A /10 is 10 times rarer than a /99"),
            "chiffre": "×10",
            "texte": t("Le chiffre après la barre, c’est le nombre d’exemplaires imprimés de CETTE carte : une /99 existe en 99 copies, "
                       "une /10 en 10, une 1/1 en une seule. Dans un break, chacune sort en proportion de son tirage.",
                       "The number after the slash is how many copies of THAT card were printed: a /99 exists in 99 copies, a /10 in 10, "
                       "a 1/1 in one. In a break, each comes out in proportion to its print run."),
            "truc": t("Compare toujours la même numérotation : une /99 ne se compare pas à une /25 ni à une non numérotée. Dans Valeur, "
                      "écris « /99 » et SlabCoach ne garde que les /99.",
                      "Always compare the same numbering: a /99 isn’t comparable to a /25 or an unnumbered card. In Value, type “/99” "
                      "and SlabCoach keeps only /99s."),
            "source": t("Tirage = exemplaires imprimés", "Print run = copies printed"), "lien": "#valeur", "calcule": False}


# -- 5. la gradation ---------------------------------------------------------------------------------------------
def gradation(api=None, langue="fr"):
    t = T(langue)
    return {"id": "gradation", "niveau": "tous", "genre": "vendre",
            "titre": t("Faire grader une recrue de base : souvent à perte", "Grading a base rookie: often a loss"),
            "chiffre": t("6 sur 12", "6 of 12"),
            "texte": t("Parmi les 12 cartes de recrue de base modernes les plus gradées chez PSA, 6 valent moins que le prix de la "
                       "gradation (environ 20 $), même en PSA 10.",
                       "Of the 12 most-graded modern base rookie cards at PSA, 6 are worth less than the grading fee (about $20), even in PSA 10."),
            "truc": t("Fais grader seulement si (prix PSA 10 − prix brute) dépasse gradation + envoi + frais, ET si ta carte est bien "
                      "centrée, sans coin ni bord abîmé. Sinon, vends-la brute.",
                      "Grade only if (PSA 10 price − raw price) beats grading + shipping + fees, AND your card is well centered with "
                      "clean corners and edges. Otherwise sell it raw."),
            "source": "Sports Illustrated Collectibles", "url": "https://www.si.com/collectibles/inside-the-hobby/grading-ultra-modern-base-rookie-cards-may-be-a-waste-of-money",
            "lien": "#valeur", "calcule": False}


# -- 6. prime PSA 10 mesuree --------------------------------------------------------------------------------------
def prime_psa10(api=None, langue="fr"):
    t = T(langue)
    import base_ventes
    import cartes_match
    try:
        c = base_ventes._cx()
        try:
            plan = c.execute("SELECT q, cible FROM plan WHERE fait_le IS NOT NULL").fetchall()
            ventes = {}
            for q, titre, prix in c.execute("SELECT q, titre, prix FROM ventes WHERE le >= ?", ((datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),)):
                ventes.setdefault(q, []).append((titre, prix))
        finally:
            c.close()
    except Exception:
        return None
    ratios = []
    for q, full in plan:
        cib = cartes_match.cible(full)
        cib10 = cartes_match.cible(full + " psa 10")
        brute = [p for t, p in ventes.get(q) or [] if not cartes_match.raisons_refus(cib, t)]
        p10 = [p for t, p in ventes.get(q) or [] if not cartes_match.raisons_refus(cib10, t)]
        if len(brute) >= 3 and len(p10) >= 3:
            ratios.append(_med(p10) / _med(brute))
    if len(ratios) < 4:
        return None
    m = _med(ratios)
    return {"id": "psa10", "niveau": "avance", "genre": "vendre",
            "titre": t(f"Une PSA 10 se vend {m:.1f} fois le prix d’une brute", f"A PSA 10 sells for {m:.1f}× a raw copy"),
            "chiffre": f"×{m:.1f}",
            "texte": t(f"Mesuré sur {len(ratios)} cartes suivies dans SlabCoach (ventes des 60 derniers jours) : médiane ×{m:.1f}, "
                       f"de ×{min(ratios):.1f} à ×{max(ratios):.1f}.",
                       f"Measured on {len(ratios)} cards tracked in SlabCoach (last 60 days of sales): median ×{m:.1f}, "
                       f"from ×{min(ratios):.1f} to ×{max(ratios):.1f}."),
            "truc": t("Avant de faire grader, cherche ta carte en « PSA 10 » et en brute dans Valeur : la différence doit payer la "
                      "gradation, l’envoi et le risque d’avoir un 9.",
                      "Before grading, look up your card as “PSA 10” and raw in Value: the gap must pay for grading, shipping and the "
                      "risk of getting a 9."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"), "lien": "#valeur", "calcule": True}


# -- 7. les offres acceptees ---------------------------------------------------------------------------------------
def offres(api=None, langue="fr"):
    t = T(langue)
    import base_ventes
    try:
        c = base_ventes._cx()
        try:
            d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            n, o = c.execute("SELECT COUNT(*), SUM(offre) FROM ventes WHERE le >= ?", (d,)).fetchone()
        finally:
            c.close()
    except Exception:
        return None
    if not n or n < 200:
        return None
    pct = round(100 * (o or 0) / n)
    return {"id": "offres", "niveau": "tous", "genre": "acheter",
            "titre": t(f"{pct} % des cartes se vendent par offre acceptée", f"{pct}% of cards sell through an accepted offer"),
            "chiffre": f"{pct} %",
            "texte": t(f"Sur {n:,} ventes eBay des 30 derniers jours dans la base SlabCoach, {pct} % sont parties par « Faire une offre ». "
                       "SlabCoach compte le vrai prix accepté, pas le prix affiché.".replace(",", " "),
                       f"Of {n:,} eBay sales in the last 30 days in SlabCoach’s database, {pct}% went through “Make offer”. SlabCoach "
                       "counts the real accepted price, not the listed one."),
            "truc": t("Quand une annonce accepte les offres, propose autour de la médiane des ventes que montre SlabCoach : le prix "
                      "affiché n’est qu’un point de départ.",
                      "When a listing takes offers, offer around the sales median SlabCoach shows: the listed price is only a starting point."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"), "lien": "#deals", "calcule": True}


# -- 8. le jour ou ca vend -----------------------------------------------------------------------------------------
def jours(api=None, langue="fr"):
    t = T(langue)
    import base_ventes
    try:
        c = base_ventes._cx()
        try:
            d = (datetime.now() - timedelta(days=56)).strftime("%Y-%m-%d")
            l = c.execute("SELECT le FROM ventes WHERE le >= ? AND le < ?", (d, datetime.now().strftime("%Y-%m-%d"))).fetchall()
        finally:
            c.close()
    except Exception:
        return None
    if len(l) < 500:
        return None
    cpt = [0] * 7
    for (le,) in l:
        try:
            cpt[datetime.fromisoformat(le).weekday()] += 1
        except ValueError:
            pass
    noms = t("lundi mardi mercredi jeudi vendredi samedi dimanche", "Monday Tuesday Wednesday Thursday Friday Saturday Sunday").split()
    moy = sum(cpt) / 7
    top = max(range(7), key=lambda k: cpt[k])
    bas = min(range(7), key=lambda k: cpt[k])
    if cpt[top] < moy * 1.08:
        return None                               # pas de vraie difference : on ne dit rien
    return {"id": "jours", "niveau": "avance", "genre": "vendre",
            "titre": t(f"Le {noms[top]}, il se vend {round(100 * (cpt[top] / moy - 1))} % plus de cartes",
                       f"On {noms[top]}, {round(100 * (cpt[top] / moy - 1))}% more cards sell"),
            "chiffre": noms[top].capitalize(),
            "texte": t(f"Sur {len(l):,} ventes des 8 dernières semaines : le {noms[top]} est le jour le plus actif, le {noms[bas]} le plus "
                       f"calme ({round(100 * (1 - cpt[bas] / moy))} % sous la moyenne).".replace(",", " "),
                       f"Of {len(l):,} sales over the last 8 weeks: {noms[top]} is the busiest day, {noms[bas]} the quietest "
                       f"({round(100 * (1 - cpt[bas] / moy))}% under average)."),
            "truc": t(f"Pour un encan, fais-le finir un {noms[top]} : c’est le jour où les acheteurs achètent le plus.",
                      f"For an auction, make it end on a {noms[top]}: that’s when buyers buy the most."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"), "lien": "#vendre", "calcule": True}


# -- 9. la chance d'une carte precise dans une boite (checklist et cotes) -----------------------------------------
def chance_boite(api=None, langue="fr"):
    t = T(langue)
    import catalogue
    import valeurs
    dem = (valeurs._charger() or {}).get("joueurs") or {}
    l = sorted(catalogue.liste(), key=lambda p: str(p.get("sortie") or ""), reverse=True)
    for p in l:
        prod = catalogue.charger(p["id"])
        if not prod:
            continue
        se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
        par = {}
        for c, s, n in catalogue.cartes_attendues(prod, 1):
            if s.get("groupe") == "recrue" and not s.get("parallele_de") and c.get("joueur") and "/" not in c["joueur"]:
                par.setdefault((c["joueur"], s["nom"]), 0.0)
                par[(c["joueur"], s["nom"])] += n
        if not par:
            continue
        (j, sn), lam = max(par.items(), key=lambda kv: (float(dem.get(kv[0][0]) or 0), kv[1]))
        p1 = 1 - math.exp(-lam)
        n_rec = len({k[0] for k in par if k[1] == sn})
        return {"id": "chance_boite", "niveau": "tous", "genre": "break",
                "titre": t(f"{j}, {sn} : 1 boîte sur {round(1 / p1)}", f"{j}, {sn}: 1 box in {round(1 / p1)}"),
                "chiffre": f"1 / {round(1 / p1)}",
                "texte": t(f"Une boîte hobby de {prod['nom']} contient en moyenne {sum(v for (jj, s2), v in par.items() if s2 == sn):.0f} "
                           f"{sn} parmi {n_rec} possibles : la chance d’avoir celle de {j} dans UNE boîte est d’environ {p1 * 100:.0f} %. "
                           f"Sur une caisse de 12 boîtes : {100 * (1 - math.exp(-12 * lam)):.0f} %.",
                           f"A {prod['nom']} hobby box holds on average {sum(v for (jj, s2), v in par.items() if s2 == sn):.0f} {sn} out of "
                           f"{n_rec} possible: the chance to get {j}’s in ONE box is about {p1 * 100:.0f}%. In a 12-box case: "
                           f"{100 * (1 - math.exp(-12 * lam)):.0f}%."),
                "truc": t("Acheter une boîte pour UN joueur, c’est un pari. Pour une carte précise, l’acheter seule coûte souvent moins "
                          "cher ; pour le plaisir d’ouvrir, regarde le score des places dans Breaks.",
                          "Buying a box for ONE player is a gamble. For a specific card, buying it single is often cheaper; for the fun "
                          "of opening, check the spot scores in Breaks."),
                "source": t("Checklist et cotes du fabricant, calcul SlabCoach", "Manufacturer checklist and odds, SlabCoach math"), "lien": "#analyse", "calcule": True}
    return None


# -- 10. ouvrir ou garder scellee ------------------------------------------------------------------------------------
def ouvrir(api=None, langue="fr"):
    t = T(langue)
    try:
        l = [p for p in api.catalogue_liste().get("produits") or [] if (p.get("ouvrir") or {}).get("verdict") and p.get("prix_boite")]
    except Exception:
        return None
    if not l:
        return None
    l = [x for x in l if x["ouvrir"]["verdict"] in ("ouvrir", "garder")]       # « neutre » : rien a dire
    if not l:
        return None
    p = max(l, key=lambda x: abs((x.get("ouvrir") or {}).get("pct") or 0))
    o = p["ouvrir"]
    garder = o["verdict"] == "garder"
    return {"id": "ouvrir", "niveau": "tous", "genre": "break",
            "titre": t(f"{p['nom']} : {'mieux vaut la garder scellée' if garder else 'ses cartes valent plus que la boîte'}",
                       f"{p['nom']}: {'better kept sealed' if garder else 'its cards are worth more than the box'}"),
            "chiffre": f"{o['pct']:+d} %" if isinstance(o.get("pct"), int) else "",
            "texte": t(f"Une boîte se vend {p['prix_boite']:.0f} $ scellée ; ses cartes revendables valent en moyenne {p['ev_par_boite']:.0f} $ "
                       "(ventes réelles, sans les cartes de moins de 1,50 $).",
                       f"A box sells for ${p['prix_boite']:.0f} sealed; its resellable cards are worth ${p['ev_par_boite']:.0f} on average "
                       "(real sales, without cards under $1.50)."),
            "truc": t("Garder scellée : revends la boîte, ou garde-la. Ouvrir : seulement si tu acceptes le hasard, car la moyenne cache "
                      "beaucoup de boîtes sous leur prix.",
                      "Sealed: resell the box or keep it. Open: only if you accept the luck of the draw, since the average hides many "
                      "boxes below their price."),
            "source": t("Ventes eBay réelles et checklist, calcul SlabCoach", "Real eBay sales and checklist, SlabCoach math"), "lien": "#analyse", "calcule": True}


# -- 11. les parallels hobby seulement (checklist GTS) ----------------------------------------------------------------
def hobby_seulement(api=None, langue="fr"):
    t = T(langue)
    import catalogue
    for p in sorted(catalogue.liste(), key=lambda p: str(p.get("sortie") or ""), reverse=True):
        prod = catalogue.charger(p["id"])
        se = prod.get("sous_ensembles") or []
        hob = [s["nom"] for s in se if s.get("tirage") and re.search(r"hobby", str(s.get("cotes") or ""), re.I)
               and not re.search(r"blaster|retail|hanger|mega|tin\b", str(s.get("cotes") or ""), re.I)]
        if len(hob) >= 3:
            return {"id": "hobby", "niveau": "debutant", "genre": "acheter",
                    "titre": t(f"{len(hob)} parallèles numérotées : boîtes hobby seulement", f"{len(hob)} numbered parallels: hobby boxes only"),
                    "chiffre": str(len(hob)),
                    "texte": t(f"Dans {prod['nom']}, {len(hob)} parallèles numérotées ne sortent que dans les boîtes hobby et e-Pack "
                               f"(ex. {', '.join(hob[:3])}). Un blaster de magasin ne peut pas les donner.",
                               f"In {prod['nom']}, {len(hob)} numbered parallels only come in hobby boxes and e-Pack "
                               f"(e.g. {', '.join(hob[:3])}). A store blaster can’t give them."),
                    "truc": t("Tu chasses une numérotée ? Achète du hobby. Tu ouvres juste pour le plaisir ? Le retail coûte moins cher par paquet.",
                              "Chasing a numbered card? Buy hobby. Just opening for fun? Retail is cheaper per pack."),
                    "source": t("Checklist officielle (cotes du fabricant)", "Official checklist (manufacturer odds)"), "lien": "#analyse", "calcule": True}
    return None


# -- 12. Young Guns vs Canvas (meme produit, ventes reelles) -----------------------------------------------------------
def yg_canvas(api=None, langue="fr"):
    t = T(langue)
    import catalogue
    import valeur_produit
    for p in sorted(catalogue.liste(), key=lambda p: str(p.get("sortie") or ""), reverse=True):
        e = valeur_produit.de(p["id"]).get("sous") or {}
        yg = next((s for n, s in e.items() if re.fullmatch(r"(base set - )?young guns", n.strip(), re.I)), None)
        cv = next((s for n, s in e.items() if re.search(r"canvas.*young guns|young guns.*canvas", n, re.I)), None)
        if not yg or not cv:
            continue
        r = []
        for j, x in (yg.get("joueurs") or {}).items():
            y = (cv.get("joueurs") or {}).get(j)
            if y and x.get("n", 0) >= 3 and y.get("n", 0) >= 3 and x.get("m"):
                r.append(y["m"] / x["m"])
        if len(r) >= 5:
            m = _med(r)
            return {"id": "canvas", "niveau": "debutant", "genre": "info",
                    "titre": t(f"Une Canvas Young Guns vaut {m:.1f} fois la Young Guns", f"A Canvas Young Guns is worth {m:.1f}× the Young Guns"),
                    "chiffre": f"×{m:.1f}",
                    "texte": t(f"Dans {p['nom']}, pour {len(r)} recrues vendues dans les deux versions, la Canvas se vend en médiane "
                               f"{m:.1f} fois la Young Guns de base.",
                               f"In {p['nom']}, for {len(r)} rookies sold in both versions, the Canvas sells for a median {m:.1f}× the base Young Guns."),
                    "truc": t("Même joueur, prix différent : vérifie toujours la version (Canvas, Clear Cut, Exclusives /100…) avant de comparer un prix.",
                              "Same player, different price: always check the version (Canvas, Clear Cut, Exclusives /100…) before comparing prices."),
                    "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"), "lien": "#valeur", "calcule": True}
    return None


# -- 13. les prix demandes vs vendus ------------------------------------------------------------------------------------
def demande_vs_vendu(api=None, langue="fr"):
    t = T(langue)
    return {"id": "demande", "niveau": "debutant", "genre": "acheter",
            "titre": t("Le prix affiché n’est pas le prix de la carte", "The listed price isn’t the card’s price"),
            "chiffre": t("Vendu", "Sold"),
            "texte": t("Sur eBay, chacun affiche le prix qu’il veut ; seules les ventes conclues disent ce que les acheteurs paient. "
                       "Vu dans SlabCoach : 6 annonces d’une Red Prism /199 à 21 $, une seule vente… à 3 $.",
                       "On eBay anyone can list at any price; only completed sales show what buyers pay. Seen in SlabCoach: 6 listings of "
                       "a Red Prism /199 at $21, a single sale… at $3."),
            "truc": t("Juge un prix avec les « vendues » de SlabCoach (ou le filtre « Objets vendus » d’eBay), jamais avec les annonces.",
                      "Judge a price with SlabCoach’s “sold” (or eBay’s “Sold items” filter), never with listings."),
            "source": t("Règle SlabCoach : valeur = ventes réelles", "SlabCoach rule: value = real sales"), "lien": "#valeur", "calcule": False}


# -- 27 oct 2026 : le pouls du hobby, un indice (jamais une affirmation) -----------------------------------------
def pouls_hobby(api=None, langue="fr"):
    import pouls
    t = T(langue)
    x = pouls.indice(langue)
    if not x:
        return None
    n = x["nom"]
    return {"id": "pouls", "niveau": "tous", "genre": "acheter",
            "titre": t(f"Psst… ça bouge du côté de {n}", f"Psst… things are moving around {n}"),
            "chiffre": {3: t("Ça chauffe", "Heating up"), 2: t("Ça monte", "Rising")}.get(x["chaleur"], t("Ça bouge", "Moving")),
            "texte": t(f"Ces jours-ci, {n} se vendent plus vite que d’habitude sur eBay. Jette un œil à ce qui part.",
                       f"These days, {n} are selling faster than usual on eBay. Take a look at what’s moving."),
            "truc": t("Quand un créneau chauffe, les acheteurs sont au rendez-vous : c’est souvent un bon moment pour lister ce que tu "
                      "as dans ce créneau, et un moins bon pour acheter au gros prix.",
                      "When a niche heats up, buyers show up: it’s often a good time to list what you have in it, and a less good "
                      "one to buy at top price."),
            "source": t("Ventes eBay réelles (SoldComps), comparées aux semaines précédentes, calcul SlabCoach",
                        "Real eBay sales (SoldComps) vs previous weeks, SlabCoach math"), "lien": "#pouls/" + x["cle"], "calcule": True}


# -- 28 oct 2026 : un joueur en feu (forme LNH des 5 derniers matchs), un indice ------------------------------------
def joueur_en_feu(api=None, langue="fr"):
    import nhl
    t = T(langue)
    f = nhl.en_feu()
    if not f:
        return None
    j = f["joueur"]
    return {"id": "en_feu", "niveau": "tous", "genre": "acheter",
            "titre": t(f"Psst… {j} : {f['points']} points à ses {f['matchs']} derniers matchs", f"Psst… {j}: {f['points']} points in his last {f['matchs']} games"),
            "chiffre": t(f"{f['points']} pts", f"{f['points']} pts"),
            "texte": t(f"{f['buts']} buts et {f['passes']} passes en {f['matchs']} matchs. Une séquence comme ça se voit souvent dans le prix de ses cartes. Jette un œil.",
                       f"{f['buts']} goals and {f['passes']} assists in {f['matchs']} games. A streak like this often shows up in his card prices. Take a look."),
            "truc": t("Une séquence fait monter les prix vite, puis ils se calment souvent quand elle s’arrête : vends pendant la vague, achète après.",
                      "A streak lifts prices fast, and they often cool off when it ends: sell during the wave, buy after."),
            "source": t("Statistiques publiques de la LNH, calcul SlabCoach", "Public NHL stats, SlabCoach math"),
            "lien": "#joueur/" + j, "calcule": True}


# -- 31 oct 2026 : nos nouvelles du marche (ventes reelles, regles strictes : voir nouvelles_donnees.py) ---------------
def marche_hausse(api=None, langue="fr"):
    import nouvelles_donnees
    return nouvelles_donnees.nouvelle_mouvement(1, langue)


def marche_baisse(api=None, langue="fr"):
    import nouvelles_donnees
    return nouvelles_donnees.nouvelle_mouvement(-1, langue)


def marche_prime(api=None, langue="fr"):
    import nouvelles_donnees
    return nouvelles_donnees.nouvelle_prime(langue)


# == 31 oct 2026 (Mathieu : « des tips plus avances, que meme du monde avance trouve interessants ; trouves sur Internet,
# dans des forums ; et bases sur nos donnees ; valider que tout ce qu'on sort est vrai ») ===============================
# Chaque fait SOURCE a ete relu a la source le 31 oct 2026 (lien affiche). Chaque fait CALCULE ne sort que s'il y a assez de
# ventes pour l'affirmer (sinon l'astuce ne s'affiche pas).

def centrage_psa(api=None, langue="fr"):
    t = T(langue)
    return {"id": "centrage", "niveau": "avance", "genre": "vendre",
            "titre": t("PSA 10 : 60/40 au plus devant, 75/25 au dos", "PSA 10: 60/40 at most on front, 75/25 on back"),
            "chiffre": "60/40",
            "texte": t("Les normes de PSA demandent, pour un 10, un centrage d’environ 55/45 à 60/40 sur le devant et 75/25 au dos ; "
                       "pour un 9, environ 60/40 à 65/35 devant et 90/10 au dos. Une carte parfaite mais décentrée à 65/35 ne peut pas avoir 10.",
                       "PSA’s standards ask, for a 10, about 55/45 to 60/40 centering on the front and 75/25 on the back; for a 9, about "
                       "60/40 to 65/35 front and 90/10 back. A flawless card centered 65/35 can’t get a 10."),
            "truc": t("Avant d’envoyer : mesure les bordures gauche/droite et haut/bas (une règle suffit). Au-delà de 60/40 devant, "
                      "compte sur un 9 au mieux et refais le calcul de rentabilité avec le prix d’un 9.",
                      "Before submitting: measure left/right and top/bottom borders (a ruler is enough). Past 60/40 on the front, "
                      "expect a 9 at best and redo the math with a 9’s price."),
            "source": "PSA, Card Grading Standards", "url": "https://www.psacard.com/resources/cardgradingstandards",
            "lien": "#valeur", "calcule": False}


def pop_bedard(api=None, langue="fr"):
    t = T(langue)
    return {"id": "pop", "niveau": "avance", "genre": "acheter",
            "titre": t("Bedard YG : 6 000 PSA 9 et 10 en 12 semaines", "Bedard YG: 6,000 PSA 9s and 10s in 12 weeks"),
            "chiffre": "6 000+",
            "texte": t("Entre la sortie (6 mars 2024) et la fin mai, plus de 6 000 Young Guns de Bedard ont reçu un PSA 9 ou 10, environ "
                       "75 par jour. Quand la population est aussi haute, les vendeurs se font concurrence : The Hockey News note qu’ils "
                       "peuvent accepter 80 à 90 % des dernières ventes.",
                       "Between release (March 6, 2024) and late May, over 6,000 Bedard Young Guns got a PSA 9 or 10, about 75 a day. "
                       "With a population that high, sellers compete: The Hockey News notes they may settle for 80 to 90% of recent sales."),
            "truc": t("Carte à grosse population (une recrue vedette gradée) : fais une offre sous les dernières ventes, il y aura une autre "
                      "copie demain. Petite population : le vendeur a le gros bout du bâton, compare plus large avant de payer.",
                      "High-population card (a graded star rookie): offer under recent sales, there’ll be another copy tomorrow. "
                      "Low population: the seller holds the cards, compare more widely before paying."),
            "source": "The Hockey News, 2024-05-27",
            "url": "https://thehockeynews.com/collectibles/card-market/sports-card-investing-population-count-explained-and-what-it-means-to-you",
            "lien": "#deals", "calcule": False}


def echange(api=None, langue="fr"):
    t = T(langue)
    return {"id": "echange", "niveau": "avance", "genre": "vendre",
            "titre": t("Un échange : la YG d’O’Reilly de 10 $ à 25-30 $ en une nuit", "A trade: O’Reilly’s YG went from $10 to $25-30 overnight"),
            "chiffre": "×2,5",
            "texte": t("Quand Ryan O’Reilly a été échangé de St. Louis à Toronto (février 2023), sa Young Guns brute est passée d’environ "
                       "10 $ à 25-30 $ du jour au lendemain ; le dimanche suivant, des marchands l’affichaient à 40 $. Un nouveau marché "
                       "amène de nouveaux acheteurs.",
                       "When Ryan O’Reilly was traded from St. Louis to Toronto (February 2023), his raw Young Guns jumped from about $10 "
                       "to $25-30 overnight; the next Sunday, dealers had it at $40. A new market brings new buyers."),
            "truc": t("Avant la date limite des échanges, regarde les joueurs cités dans les rumeurs vers un gros marché ou un aspirant : "
                      "vends dans les jours qui suivent l’échange, ou garde jusqu’aux séries si la nouvelle équipe va loin. Les marqueurs gardent mieux leur valeur que "
                      "les défenseurs et les gardiens.",
                      "Before the trade deadline, watch players rumored to a big market or a contender: sell in the days after the trade, "
                      "or hold through the playoffs if the new team goes deep. Scorers hold value better than defensemen and goalies."),
            "source": "The Hockey News, 2024-02-28",
            "url": "https://thehockeynews.com/collectibles/tips-tuesday-strategizing-the-hockey-card-market-ahead-of-the-nhl-trade-deadline",
            "lien": "#deals", "calcule": False}


def cotes_s2(api=None, langue="fr"):
    t = T(langue)
    return {"id": "cotes_s2", "niveau": "avance", "genre": "break",
            "titre": t("Clear Cut Young Guns : 1 paquet sur 144, une par 12 boîtes", "Clear Cut Young Guns: 1 in 144 packs, one per 12 boxes"),
            "chiffre": "1:144",
            "texte": t("Dans 2025-26 Upper Deck Series 2 (12 paquets par boîte hobby) : 6 Young Guns par boîte (1:2 paquets), une Canvas "
                       "Young Guns par 2 boîtes (1:24), une Outburst Silver Young Guns par 5 boîtes (1:60), une Clear Cut Young Guns par "
                       "12 boîtes (1:144). Et la recrue que tu veux n’est qu’une parmi des dizaines.",
                       "In 2025-26 Upper Deck Series 2 (12 packs per hobby box): 6 Young Guns per box (1:2 packs), one Canvas Young Guns "
                       "per 2 boxes (1:24), one Outburst Silver Young Guns per 5 boxes (1:60), one Clear Cut Young Guns per 12 boxes "
                       "(1:144). And the rookie you want is just one of dozens."),
            "truc": t("Pour UNE parallèle d’UN joueur, divise : (paquets par carte × nombre de recrues) ÷ 12 = boîtes à ouvrir en moyenne. "
                      "Compare avec son prix à l’unité : c’est souvent moins cher de l’acheter seule.",
                      "For ONE parallel of ONE player, divide: (packs per card × number of rookies) ÷ 12 = boxes to open on average. "
                      "Compare with its single price: buying it alone is often cheaper."),
            "source": "Cardboard Connection (cotes Upper Deck)",
            "url": "https://www.cardboardconnection.com/2025-26-upper-deck-series-2-hockey-hobby-box-set-review-and-checklist",
            "lien": "#analyse", "calcule": False}


def _ratio_variante(suffixe_haut, suffixe_bas="", jours=60, min_ventes=3, min_cartes=4):
    """Pour les cartes suivies : mediane(prix de la version « haut ») / mediane(prix de la version « bas ») sur les ventes
    reelles des `jours` derniers jours, la MEME carte (cartes_match). -> (mediane des rapports, rapports) ou None."""
    import base_ventes
    import cartes_match
    try:
        c = base_ventes._cx()
        try:
            plan = c.execute("SELECT q, cible FROM plan WHERE fait_le IS NOT NULL").fetchall()
            ventes = {}
            for q, titre, prix in c.execute("SELECT q, titre, prix FROM ventes WHERE le >= ?", ((datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d"),)):
                ventes.setdefault(q, []).append((titre, prix))
        finally:
            c.close()
    except Exception:
        return None
    r = []
    for q, full in plan:
        ch = cartes_match.cible((full + " " + suffixe_haut).strip())
        cb = cartes_match.cible((full + " " + suffixe_bas).strip())
        h = [p for ti, p in ventes.get(q) or [] if p and not cartes_match.raisons_refus(ch, ti)]
        b = [p for ti, p in ventes.get(q) or [] if p and not cartes_match.raisons_refus(cb, ti)]
        if len(h) >= min_ventes and len(b) >= min_ventes and _med(b):
            r.append(_med(h) / _med(b))
    if len(r) < min_cartes:
        return None
    return _med(r), r


def bgs_vs_psa(api=None, langue="fr"):
    t = T(langue)
    x = _ratio_variante("bgs 9.5", "psa 10")
    if not x:
        return None
    m, r = x
    pct = round(100 * m)
    return {"id": "bgs_psa", "niveau": "avance", "genre": "vendre",
            "titre": t(f"Une BGS 9.5 se vend {pct} % du prix d’une PSA 10", f"A BGS 9.5 sells for {pct}% of a PSA 10"),
            "chiffre": f"{pct} %",
            "texte": t(f"Mesuré sur {len(r)} cartes suivies dans SlabCoach, vendues dans les deux gradations dans les 60 derniers jours : "
                       f"médiane {pct} % (de {round(100 * min(r))} à {round(100 * max(r))} %).",
                       f"Measured on {len(r)} cards tracked in SlabCoach, sold in both grades in the last 60 days: median {pct}% "
                       f"(from {round(100 * min(r))} to {round(100 * max(r))}%)."),
            "truc": t("Pas pareil d’une compagnie à l’autre : ne compare jamais une BGS 9.5 aux ventes de PSA 10 (ni l’inverse). "
                      "Dans Valeur, écris la gradation exacte.",
                      "Not the same from one grader to another: never compare a BGS 9.5 to PSA 10 sales (or the reverse). In Value, "
                      "type the exact grade."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"),
            "lien": "#valeur", "calcule": True}


def prime_exclusives(api=None, langue="fr"):
    t = T(langue)
    x = _ratio_variante("exclusives /100", "")
    if not x:
        return None
    m, r = x
    return {"id": "exclusives", "niveau": "avance", "genre": "acheter",
            "titre": t(f"Une Exclusives /100 vaut {m:.1f} fois la Young Guns de base", f"An Exclusives /100 is worth {m:.1f}× the base Young Guns"),
            "chiffre": f"×{m:.1f}",
            "texte": t(f"Mesuré sur {len(r)} recrues suivies dans SlabCoach, vendues dans les deux versions dans les 60 derniers jours : "
                       f"médiane ×{m:.1f} (de ×{min(r):.1f} à ×{max(r):.1f}).",
                       f"Measured on {len(r)} rookies tracked in SlabCoach, sold in both versions in the last 60 days: median "
                       f"×{m:.1f} (from ×{min(r):.1f} to ×{max(r):.1f})."),
            "truc": t("Une Exclusives sous ce multiple de sa Young Guns est souvent une aubaine ; au-dessus, tu paies la rareté du "
                      "joueur, vérifie ses ventes à lui.",
                      "An Exclusives under this multiple of its Young Guns is often a bargain; above it, you pay for the player’s "
                      "scarcity, check his own sales."),
            "source": t("Ventes eBay réelles (SoldComps), calcul SlabCoach", "Real eBay sales (SoldComps), SlabCoach math"),
            "lien": "#valeur", "calcule": True}


GENERATEURS = [pouls_hobby, joueur_en_feu, marche_hausse, marche_baisse, marche_prime, chute_sortie, bedard, frais, numerotation, gradation, prime_psa10, offres, jours, chance_boite, ouvrir,
               hobby_seulement, yg_canvas, demande_vs_vendu, centrage_psa, pop_bedard, echange, cotes_s2, bgs_vs_psa, prime_exclusives]


def liste(api, niveau=None, force=False, langue="fr"):
    cle = (niveau, langue)
    if not force and _CACHE["cle"] == cle and time.time() - _CACHE["le"] < FRAICHEUR_S:
        return _CACHE["l"]
    out = []
    for g in GENERATEURS:
        try:
            x = g(api, langue)
        except Exception as e:
            print("Astuce " + g.__name__ + " : " + repr(e), flush=True)
            x = None
        if x:
            if langue != "en":                         # 3,94 $ et ×2,1 en francais
                for k in ("titre", "chiffre", "texte"):
                    x[k] = re.sub(r"(?<=\d)\.(?=\d)", ",", str(x.get(k) or ""))
            out.append(x)
    # debutant / retour : d'abord les bases ; avance : d'abord les chiffres
    ordre = {"debutant": ["debutant", "tous", "avance"], "retour": ["debutant", "tous", "avance"],
             "expert": ["avance", "tous", "debutant"]}.get(niveau or "", ["tous", "debutant", "avance"])
    out.sort(key=lambda x: (ordre.index(x["niveau"]) if x["niveau"] in ordre else 9, not x.get("calcule")))
    _CACHE.update(le=time.time(), cle=cle, l=out)
    return out
