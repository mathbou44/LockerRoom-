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
import math
import re
import statistics
import time
from datetime import datetime, timedelta

FRAICHEUR_S = 6 * 3600


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
            "titre": t(f"Une carte vendue 5 $ sur eBay te laisse {net5:.2f} $", f"A card sold for $5 on eBay leaves you ${net5:.2f}"),
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
    return {"id": "numerotation", "niveau": "tous", "genre": "vendre",
            # 18 nov 2026 (Mathieu : « un peu trop evident ») : ce qu'un collectionneur actif ne sait pas toujours : le NUMERO
            # de la copie compte aussi, pas seulement le tirage
            "titre": t("Une 87/99 de Crosby vaut plus qu’une 12/99", "A Crosby 87/99 is worth more than a 12/99"),
            "chiffre": "#87",
            "texte": t("Même carte, même tirage : la copie dont le numéro est celui du chandail du joueur (87/99 pour Crosby, 97/99 "
                       "pour McDavid), la 1re (1/99) et la dernière (99/99) se vendent plus cher. Les acheteurs les cherchent, "
                       "et il n’y en a qu’une de chaque.",
                       "Same card, same print run: the copy numbered to the player’s jersey (87/99 for Crosby, 97/99 for McDavid), "
                       "the first (1/99) and the last (99/99) sell higher. Buyers hunt for them, and there’s only one of each."),
            "truc": t("Avant de vendre une numérotée, regarde son numéro : si c’est le chandail, la 1re ou la dernière, dis-le dans "
                      "le titre (« Jersey # », « First numbered ») et ne la brade pas.",
                      "Before selling a numbered card, check its number: if it’s the jersey, the first or the last, say so in the "
                      "title (“Jersey #”, “First numbered”) and don’t sell it cheap."),
            "source": t("Pratique du marché des cartes numérotées", "Numbered card market practice"), "lien": "#valeur", "calcule": False}


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
            plan = c.execute("SELECT q, cible FROM plan WHERE fait_le IS NOT NULL AND cible NOT LIKE 'sorte %'").fetchall()
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
            "titre": t("PSA 10 : 55/45 au plus devant, 75/25 au dos", "PSA 10: 55/45 at most on front, 75/25 on back"),
            "chiffre": "55/45",
            "texte": t("Les normes de PSA (psacard.com) demandent, pour un 10, un centrage d’environ 55/45 sur le devant et 75/25 au dos ; "
                       "pour un 9, environ 60/40 devant et 90/10 au dos. Une carte parfaite mais décentrée à 58/42 ne peut pas avoir 10.",
                       "PSA’s standards (psacard.com) ask, for a 10, about 55/45 centering on the front and 75/25 on the back; for a 9, about "
                       "60/40 front and 90/10 back. A flawless card centered 58/42 can’t get a 10."),
            "truc": t("Avant d’envoyer : mesure les bordures gauche/droite et haut/bas (une règle suffit). Au-delà de 55/45 devant, "
                      "compte sur un 9 au mieux et refais le calcul de rentabilité avec le prix d’un 9.",
                      "Before submitting: measure left/right and top/bottom borders (a ruler is enough). Past 55/45 on the front, "
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
            plan = c.execute("SELECT q, cible FROM plan WHERE fait_le IS NOT NULL AND cible NOT LIKE 'sorte %'").fetchall()
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


# -- 18 nov 2026 (Mathieu : « des tips plus pousses, ce que les connaisseurs savent ; va chercher l'info, valide-la ») --------
# Chaque chiffre vient de la fiche du produit (cotes et tirages d'Upper Deck, repris par Cardboard Connection / Checklist Insider)
def allure_16bit(api=None, langue="fr"):
    t = T(langue)
    return {"id": "allure_16bit", "niveau": "avance", "genre": "acheter",
            "titre": t("Allure : la 16-Bit, l’insert que les connaisseurs chassent", "Allure: 16-Bit, the insert collectors hunt"),
            "chiffre": "1:720",
            "texte": t("Dans Allure 2025-26, la 16-Bit (le design en pixels de jeu vidéo, 16 joueurs : vedettes et recrues) sort 1 paquet sur "
                       "720 en hobby et 1 sur 1 800 en blaster. C’est plus rare qu’une Impressions (1:600) et 80 fois plus rare qu’une "
                       "Hue’s Next? (1:9). Elle n’est pas numérotée : beaucoup de vendeurs la sous-estiment.",
                       "In 2025-26 Allure, 16-Bit (the pixel video-game design, 16 players: stars and rookies) falls 1 in 720 hobby packs and "
                       "1 in 1,800 blaster packs. That’s rarer than Impressions (1:600) and 80 times rarer than Hue’s Next? (1:9). "
                       "It isn’t numbered, so many sellers underprice it."),
            "truc": t("Cherche « 16-Bit » sans « /» : une annonce mal titrée (juste « Allure insert ») est souvent la bonne affaire.",
                      "Search “16-Bit” without a “/”: a poorly titled listing (just “Allure insert”) is often the deal."),
            "source": "Cardboard Connection, 2025-26 Upper Deck Allure",
            "url": "https://www.cardboardconnection.com/2025-26-upper-deck-allure-hockey-set-review-and-checklist",
            "lien": "#valeur/16-Bit%20Allure", "calcule": False}


def pmg_metal(api=None, langue="fr"):
    t = T(langue)
    return {"id": "pmg_metal", "niveau": "avance", "genre": "acheter",
            "titre": t("Metal Universe : la PMG bleue /50 sort seulement des Hot Boxes", "Metal Universe: the Blue PMG /50 only comes from Hot Boxes"),
            "chiffre": "/10",
            "texte": t("Les Precious Metal Gems, l’icône des années 90 : rouge /100, bleue /50 (seulement dans les boîtes « Hot Box »), "
                       "verte /10, or 1/1, toutes hobby ou ePack. La verte /10 est la vraie chasse : 10 copies, et les collectionneurs "
                       "nostalgiques paient pour.",
                       "Precious Metal Gems, the ’90s icon: red /100, blue /50 (only in “Hot Box” boxes), green /10, gold 1/1, all hobby "
                       "or ePack. The green /10 is the real chase: 10 copies, and nostalgic collectors pay for them."),
            "truc": t("Une annonce « PMG » sans couleur ni numéro : demande la photo du dos. Une PMG rouge vendue au prix d’une verte, "
                      "c’est l’erreur la plus fréquente.",
                      "A “PMG” listing with no color or number: ask for a photo of the back. A red PMG sold at a green’s price is the most "
                      "common mistake."),
            "source": "Checklist Insider, 2025-26 Skybox Metal Universe",
            "url": "https://www.checklistinsider.com/2025-26-skybox-metal-universe-hockey",
            "lien": "#valeur/Precious%20Metal%20Gems", "calcule": False}


def opc_platinum(api=None, langue="fr"):
    t = T(langue)
    return {"id": "opc_platinum", "niveau": "avance", "genre": "acheter",
            "titre": t("OPC Platinum : la Red Prism /199 n’est pas la chasse", "OPC Platinum: the Red Prism /199 isn’t the chase"),
            "chiffre": "/25",
            "texte": t("Les Marquee Rookies ont 13 parallèles. Les numérotées vont de Violet Pixels /299 à Golden Treasures 1/1 ; la Red "
                       "Prism /199 est l’une des plus communes. La vraie chasse : Seismic Gold /50, Orange Checkers /25 (hobby seulement) "
                       "et Bioluminescence /5.",
                       "Marquee Rookies have 13 parallels. Numbered ones run from Violet Pixels /299 to Golden Treasures 1/1; the Red "
                       "Prism /199 is one of the most common. The real chase: Seismic Gold /50, Orange Checkers /25 (hobby only) and "
                       "Bioluminescence /5."),
            "truc": t("Ne paie pas une Red Prism comme une carte rare. Une Orange Checkers vient forcément d’une boîte hobby : un bon "
                      "signe pour l’état.",
                      "Don’t pay for a Red Prism like a rare card. An Orange Checkers always comes from a hobby box: a good sign for "
                      "condition."),
            "source": "Cardboard Connection, 2025-26 O-Pee-Chee Platinum",
            "url": "https://www.cardboardconnection.com/2025-26-upper-deck-o-pee-chee-platinum-hockey-set-review-and-checklist",
            "lien": "#valeur/Marquee%20Rookies", "calcule": False}


def cup_niveaux(api=None, langue="fr"):
    t = T(langue)
    return {"id": "cup_niveaux", "niveau": "avance", "genre": "acheter",
            "titre": t("The Cup : une RPA /99, c’est un top prospect", "The Cup: a /99 RPA means a top prospect"),
            "chiffre": "/99",
            "texte": t("Dans The Cup, Upper Deck classe les recrues en niveaux : niveau 1 numéroté /249, niveau 2 /99 pour les meilleurs "
                       "espoirs (Celebrini en 2024-25). Le tirage te dit donc qui Upper Deck voit comme une vedette. Parallèles : Gold "
                       "Spectrum /36, Gold /24, Red /4, Green /3, Black 1/1.",
                       "In The Cup, Upper Deck sorts rookies into tiers: level 1 numbered /249, level 2 /99 for the top prospects "
                       "(Celebrini in 2024-25). So the print run tells you who Upper Deck sees as a star. Parallels: Gold Spectrum /36, "
                       "Gold /24, Red /4, Green /3, Black 1/1."),
            "truc": t("Compare une RPA avec une RPA du même niveau : une /249 d’un bon joueur peut coûter moins qu’une /99 d’un joueur "
                      "moyen, et rattraper plus vite.",
                      "Compare an RPA with an RPA of the same tier: a good player’s /249 can cost less than an average player’s /99 and "
                      "catch up faster."),
            "source": "Cardboard Connection, 2024-25 Upper Deck The Cup",
            "url": "https://www.cardboardconnection.com/2024-25-upper-deck-the-cup-hockey-set-review-and-checklist",
            "lien": "#valeur/The%20Cup%20Rookie%20Patch%20Auto", "calcule": False}


def hanger_yg(api=None, langue="fr"):
    t = T(langue)
    return {"id": "hanger_yg", "niveau": "avance", "genre": "break",
            "titre": t("Au détail, prends les hangers : les cotes du hobby", "At retail, pick hangers: hobby odds"),
            "chiffre": "1:24",
            "texte": t("Series 2 2025-26 : une Canvas Young Guns sort 1 paquet sur 24 en hobby… et en hanger, contre 1 sur 48 en blaster "
                       "ou en mega. Les hangers donnent aussi une Young Guns par paquet. L’Outburst Young Guns : 1:60 en hobby, 1:90 en "
                       "hanger, 1:180 en blaster. Les Exclusives /100 et les Outburst Gold et Red : hobby et ePack seulement.",
                       "2025-26 Series 2: a Canvas Young Guns falls 1 in 24 hobby packs… and 1 in 24 hanger packs, vs 1 in 48 in blaster "
                       "or mega. Hangers also give one Young Guns per pack. Outburst Young Guns: 1:60 hobby, 1:90 hanger, 1:180 blaster. "
                       "Exclusives /100 and Outburst Gold and Red: hobby and ePack only."),
            "truc": t("Au Walmart ou chez Costco, entre un blaster et un hanger au même prix : le hanger. Et ne cherche jamais une "
                      "Exclusives dans du détail.",
                      "At Walmart or Costco, between a blaster and a hanger at the same price: the hanger. And never hunt an Exclusives "
                      "in retail."),
            "source": "Breakninja (cotes officielles Upper Deck), 2025-26 Series 2",
            "url": "https://www.breakninja.com/hockey/25-26-Upper-Deck-Series-2-Hockey-Checklist-Odds.php",
            "lien": "#analyse", "calcule": False}


def fin_encan(api=None, langue="fr"):
    t = T(langue)
    return {"id": "fin_encan", "niveau": "avance", "genre": "vendre",
            "titre": t("Finis tes encans le dimanche soir, jamais le vendredi", "End your auctions Sunday evening, never Friday"),
            "chiffre": t("Dim.", "Sun."),
            "texte": t("Le conseil qui revient chez les vendeurs aguerris (forum de PSA / Collectors Universe) : un encan qui finit le "
                       "dimanche soir attire plus de mises ; le vendredi et le samedi soir, les acheteurs sont sortis. Les mises se "
                       "jouent dans les dernières minutes : la fin compte plus que le début.",
                       "The advice that keeps coming back from seasoned sellers (PSA / Collectors Universe forum): an auction ending "
                       "Sunday evening draws more bids; Friday and Saturday nights, buyers are out. Bids happen in the last minutes: "
                       "the end matters more than the start."),
            "truc": t("Lance un encan de 7 jours un dimanche vers 19 h (heure de l’Est) : il finira le dimanche suivant à la même heure, "
                      "quand le Canada et les États-Unis sont devant leur téléphone.",
                      "Start a 7-day auction on a Sunday around 7 pm Eastern: it ends the next Sunday at the same time, when Canada and "
                      "the US are on their phones."),
            "source": "Forum Collectors Universe (vendeurs eBay)",
            "url": "https://forums.collectors.com/discussion/928711/question-for-ebay-sellers",
            "lien": "#vendre", "calcule": False}


GENERATEURS = [pouls_hobby, joueur_en_feu, marche_hausse, marche_baisse, marche_prime, chute_sortie, bedard, frais, numerotation, gradation, prime_psa10, offres, jours, chance_boite, ouvrir,
               hobby_seulement, yg_canvas, demande_vs_vendu, centrage_psa, pop_bedard, echange, cotes_s2, bgs_vs_psa, prime_exclusives,
               allure_16bit, pmg_metal, opc_platinum, cup_niveaux, hanger_yg, fin_encan]


_PAR_COMPTE = {"frais"}                 # les seules astuces qui lisent les reglages du compte
_GLOBAL = {}                           # langue -> {"le", "l"} : le reste est le meme pour tout le monde
_VERROU = __import__("threading").Lock()
_EN_COURS = set()


def _calculer(api, langue, gens):
    out = []
    for g in gens:
        try:
            x = g(api, langue)
        except Exception as e:
            print("Astuce " + g.__name__ + " : " + repr(e), flush=True)
            x = None
        if x:
            if langue != "en":                         # 3,94 $ et x2,1 en francais
                for k in ("titre", "chiffre", "texte"):
                    x[k] = re.sub(r"(?<=\d)\.(?=\d)", ",", str(x.get(k) or ""))
            out.append((g.__name__, x))
    return out


def _globales(api, langue, force=False):
    """4 nov 2026 (tournee vitesse) : les astuces communes sont calculees une fois pour tous (10 a 20 s), pas par compte ;
    perimees -> on rend les anciennes tout de suite et on recalcule en fond.
    21 nov 2026 (Mathieu : « aucun tips, rien que des nouvelles, pourquoi ? ») : juste apres un deploiement, le cache est vide et
    le 1er appel calculait SUR PLACE : 132 s ce matin (serveur occupe par les breaks). Cloudflare coupe a 100 s, l'app recevait
    une erreur et restait sans astuces. Maintenant le calcul se fait toujours en fond : la reponse part tout de suite avec les
    trucs du hobby (qui ne dependent d'aucun calcul), et les chiffres du jour s'ajoutent au prochain appel."""
    gens = [g for g in GENERATEURS if g.__name__ not in _PAR_COMPTE]
    c = _GLOBAL.get(langue)
    if force:
        l = _calculer(api, langue, gens)
        _GLOBAL[langue] = {"le": time.time(), "l": l}
        return l
    if not c or time.time() - c["le"] >= FRAICHEUR_S:
        with _VERROU:
            lance = langue not in _EN_COURS
            _EN_COURS.add(langue)
        if lance:
            import contextvars, threading
            ctx = contextvars.copy_context()

            def fond():
                try:
                    _GLOBAL[langue] = {"le": time.time(), "l": _calculer(api, langue, gens)}
                finally:
                    _EN_COURS.discard(langue)
            threading.Thread(target=lambda: ctx.run(fond), daemon=True).start()
    return c["l"] if c else []


# -- 20 nov 2026 (Mathieu : « ou sont les tips and tricks ? Il y a une infinite de trucs pour aider les collectionneurs ») : une banque
# de trucs de hockey qui ne dependent d'aucune donnee eBay (permis pour le public), pour acheter, vendre, grader, proteger. Les faits
# precis sont sources ; les autres sont des regles de prudence du hobby. Une partie change chaque jour (voir liste()).
def _hk(id_, niveau, genre, titre, texte, truc, source="SlabCoach", url="", lien="#valeur"):
    return {"id": id_, "niveau": niveau, "genre": genre, "titre": titre, "chiffre": "", "texte": texte, "truc": truc,
            "source": source, "url": url, "lien": lien, "calcule": False, "sport": "hockey"}


def astuces_hockey(langue="fr"):
    t = T(langue)
    SI = "Sports Illustrated Collectibles"
    return [
        _hk("hk_vendu", "debutant", "acheter", t("Le vrai prix : ce qui s’est vendu", "The real price: what sold"),
            t("Une annonce affiche le prix que le vendeur espère. Ce qui compte, c’est le prix des ventes conclues de la même carte.",
              "A listing shows the price the seller hopes for. What counts is the price of completed sales of the same card."),
            t("Avant d’acheter, regarde les ventes récentes, jamais les annonces.", "Before you buy, look at recent sales, never at listings."),
            SI, "https://www.si.com/collectibles/the-five-rookie-mistakes-new-card-collectors-make"),
        _hk("hk_meme", "debutant", "acheter", t("Compare la même carte, pas une cousine", "Compare the same card, not a cousin"),
            t("La base, une parallèle numérotée et la même carte gradée 10 n’ont pas le même prix, même si la photo se ressemble.",
              "The base, a numbered parallel and the same card graded 10 don’t share a price, even if the photo looks alike."),
            t("Vérifie l’année, le set, la parallèle, le numéro et la note avant de comparer un prix.",
              "Check year, set, parallel, number and grade before you compare a price.")),
        _hk("hk_max", "tous", "acheter", t("Ta mise max, décidée avant l’encan", "Your max bid, decided before the auction"),
            t("Dans les dernières secondes d’un encan, on paie souvent trop cher sous la pression.",
              "In an auction’s final seconds, people often overpay under pressure."),
            t("Fixe ton prix maximum avant et ne le dépasse pas : la même carte reviendra.", "Set your max before and don’t go over it: the same card will come back."),
            lien="#deals"),
        _hk("hk_offre", "tous", "acheter", t("Les annonces « ou meilleure offre »", "“Or best offer” listings"),
            t("Beaucoup de vendeurs acceptent une offre raisonnable sous le prix affiché.", "Many sellers accept a reasonable offer under the asking price."),
            t("Une offre polie, proche des ventes récentes, passe souvent.", "A polite offer close to recent sales often goes through."), lien="#deals"),
        _hk("hk_trop_beau", "debutant", "acheter", t("Trop beau pour être vrai ?", "Too good to be true?"),
            t("Les fausses autos, les patchs trafiqués et les fausses étiquettes existent. Un prix très bas est le premier signal.",
              "Fake autographs, doctored patches and fake labels exist. A very low price is the first warning sign."),
            t("Une grosse carte à petit prix : regarde le vendeur, les photos du dos et l’étiquette avant de payer.",
              "A big card at a small price: check the seller, the back photos and the label before you pay."),
            SI, "https://www.si.com/collectibles/inside-the-hobby/the-hobby-u-avoiding-common-new-card-collector-mistakes"),
        _hk("hk_vendeur", "debutant", "acheter", t("Le vendeur compte autant que la carte", "The seller matters as much as the card"),
            t("Un vendeur avec beaucoup de ventes et une note proche de 100 % est plus sûr.", "A seller with many sales and a rating near 100% is safer."),
            t("Peu d’évaluations et un prix très bas : prudence.", "Few ratings and a very low price: be careful.")),
        _hk("hk_photos", "tous", "acheter", t("Demande le dos et les coins", "Ask for the back and the corners"),
            t("Une photo de face ne montre pas les coins blanchis, les bords ni le centrage du dos.",
              "A front photo doesn’t show whitened corners, edges or back centering."),
            t("Pas de photo du dos sur une carte chère ? Demande-la avant d’acheter.", "No back photo on an expensive card? Ask for it before you buy.")),
        _hk("hk_centrage", "avance", "grader", t("Le centrage avant de grader", "Centering before grading"),
            t("Une carte mal centrée n’aura pas un 10, même avec des coins parfaits.", "A poorly centered card won’t get a 10, even with perfect corners."),
            t("Mesure le centrage (la caméra de SlabCoach le fait) avant de payer une gradation.", "Measure centering (SlabCoach’s camera does it) before paying to grade."),
            lien="#vendre"),
        _hk("hk_grader", "tous", "grader", t("Grader seulement si ça rapporte", "Grade only if it pays"),
            t("La gradation coûte de l’argent et du temps. Pour une carte de faible valeur, elle coûte souvent plus que ce qu’elle ajoute.",
              "Grading costs money and time. For a low-value card, it often costs more than it adds."),
            t("Gradue les recrues recherchées en très bon état ; garde les autres brutes.", "Grade sought-after rookies in great shape; keep the rest raw.")),
        _hk("hk_yg", "debutant", "acheter", t("Les Young Guns, la recrue de référence", "Young Guns, the benchmark rookie"),
            t("Dans Upper Deck Series 1 et 2, les Young Guns sont les cartes recrues que les collectionneurs de hockey suivent le plus.",
              "In Upper Deck Series 1 and 2, Young Guns are the rookie cards hockey collectors follow most."),
            t("Pour une première recrue d’un joueur, commence par sa Young Guns.", "For a player’s first rookie card, start with his Young Guns.")),
        _hk("hk_tirage", "tous", "acheter", t("Rare ne veut pas dire recherché", "Rare doesn’t mean sought after"),
            t("Une /25 d’un joueur que personne ne suit se vend moins qu’une base d’une vedette.", "A /25 of a player nobody follows sells for less than a star’s base."),
            t("Le joueur d’abord, le tirage ensuite.", "The player first, the print run second.")),
        _hk("hk_hausse", "avance", "vendre", t("Ce qui monte vite redescend souvent", "What rises fast often comes back down"),
            t("Après un gros coup de chaleur (une série de buts, une nouvelle), les prix reviennent souvent vers leur niveau d’avant : nos tests sur les ventes l’ont mesuré.",
              "After a big spike (a scoring streak, a headline), prices often drift back toward where they were: our tests on sales measured it."),
            t("Tu veux vendre ? Profite de l’emballement. Tu veux acheter ? Attends qu’il passe.", "Selling? Ride the hype. Buying? Wait for it to pass.")),
        _hk("hk_frais", "debutant", "vendre", t("Compte les frais avant ton prix", "Count the fees before your price"),
            t("Les frais de vente et l’envoi grugent une partie de chaque vente.", "Selling fees and shipping eat part of every sale."),
            t("Fixe ton prix pour que ton profit reste positif une fois les frais payés.", "Set your price so your profit stays positive after fees."), lien="#vendre"),
        _hk("hk_lot", "tous", "vendre", t("Sépare les bonnes cartes des lots", "Pull the good cards out of lots"),
            t("Les acheteurs cherchent une ou deux cartes précises et paient rarement plus pour le reste du lot.",
              "Buyers look for one or two specific cards and rarely pay more for the rest of the lot."),
            t("Vends les cartes de valeur seules ; regroupe seulement les petites.", "Sell valuable cards on their own; only group the small ones."),
            "Sports Collectors Daily", "https://www.sportscollectorsdaily.com/selling-sports-cards-on-ebay-for-cash/", "#vendre"),
        _hk("hk_titre", "debutant", "vendre", t("Un bon titre se fait trouver", "A good title gets found"),
            t("Les acheteurs cherchent par année, joueur, set, numéro et parallèle.", "Buyers search by year, player, set, number and parallel."),
            t("Mets ces 5 éléments dans le titre ; SlabCoach l’écrit pour toi.", "Put those 5 things in the title; SlabCoach writes it for you."), lien="#vendre"),
        _hk("hk_envoi", "tous", "vendre", t("Une carte bien emballée arrive intacte", "A well-packed card arrives intact"),
            t("Une carte de valeur voyage dans un protège-carte et un toploader, avec un envoi suivi.",
              "A valuable card travels in a penny sleeve and a toploader, with tracked shipping."),
            t("Au-dessus de quelques dizaines de dollars, prends toujours un envoi suivi.", "Above a few tens of dollars, always use tracked shipping.")),
        _hk("hk_cout", "tous", "collection", t("Note ce que tu as payé", "Write down what you paid"),
            t("Sans le prix payé, impossible de savoir si une vente rapporte.", "Without the price paid, you can’t know whether a sale makes money."),
            t("Entre le coût de chaque carte : SlabCoach calcule ton vrai profit.", "Enter each card’s cost: SlabCoach works out your real profit."), lien="#inventaire"),
        _hk("hk_budget", "debutant", "collection", t("Un budget par mois", "A monthly budget"),
            t("Le hobby va vite : sans limite, les petits achats s’additionnent.", "The hobby moves fast: without a limit, small buys add up."),
            t("Fixe ton budget du mois ; l’app te dit ce qu’il te reste.", "Set your monthly budget; the app tells you what’s left."), lien="#guide"),
        _hk("hk_focus", "debutant", "collection", t("Choisis ton terrain de jeu", "Pick your playing field"),
            t("Un joueur, une équipe ou un set : une collection ciblée est plus simple à suivre et plus agréable.",
              "One player, one team or one set: a focused collection is easier to follow and more fun."),
            t("Ajoute tes joueurs dans le Radar : il cherche pour toi.", "Add your players to the Radar: it searches for you."), lien="#deals"),
        _hk("hk_break", "tous", "acheter", t("Une place de break a un juste prix", "A break spot has a fair price"),
            t("La valeur d’une place dépend de l’équipe, du produit et des cartes possibles.", "A spot’s value depends on the team, the product and the possible cards."),
            t("Calcule la valeur de ta place avant de payer.", "Work out your spot’s value before you pay."), lien="#analyse"),
    ]


# -- 20 nov 2026 (Mathieu : « la sortie de nouveaux produits aussi, on doit l'annoncer ») : un produit du catalogue sorti dans les
# 30 derniers jours (ou qui sort dans les 30 prochains) est annonce en tete des nouvelles de l'accueil. Les donnees du catalogue
# (date, recrues et hits par boite) viennent du fabricant ; rien d'eBay.
SORTIE_JOURS = 30


def sorties(langue="fr", auj=None):
    import datetime as _dt
    import catalogue
    t = T(langue)
    auj = auj or _dt.date.today()
    MF = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    out = []
    try:
        L = catalogue.liste()
    except Exception:
        return []
    for p in L:
        try:
            d = _dt.date.fromisoformat(str(p.get("sortie") or "")[:10])
        except ValueError:
            continue
        ecart = (d - auj).days
        if not -SORTIE_JOURS <= ecart <= SORTIE_JOURS:
            continue
        jour = t(f"{d.day}{'er' if d.day == 1 else ''} {MF[d.month - 1]}", f"{ME[d.month - 1]} {d.day}")
        bouts = []
        nb = lambda x: (str(int(round(float(x)))) if abs(float(x) - round(float(x))) < 0.05 else (f"{float(x):.1f}".replace(".", ",") if langue != "en" else f"{float(x):.1f}"))
        if p.get("recrues_par_boite"):
            bouts.append(t(f"{nb(p['recrues_par_boite'])} recrues par boîte", f"{nb(p['recrues_par_boite'])} rookies per box"))
        if p.get("hits_par_boite"):
            bouts.append(t(f"{nb(p['hits_par_boite'])} hit{'s' if float(p['hits_par_boite']) >= 1.5 else ''} par boîte", f"{nb(p['hits_par_boite'])} hit{'s' if float(p['hits_par_boite']) >= 1.5 else ''} per box"))
        out.append({"id": "sortie_" + str(p["id"]), "niveau": "tous", "genre": "acheter", "sortie": str(d), "calcule": False, "sport": "hockey",
                    "titre": p["nom"], "chiffre": "", "a_venir": ecart > 0,
                    "texte": (t("Sorti le ", "Released ") if ecart <= 0 else t("Sort le ", "Releases ")) + jour + (". " + ", ".join(bouts) + t(" (cotes du fabricant).", " (manufacturer odds).") if bouts else "."),
                    "truc": t("Avant d’acheter une boîte ou une place de break, calcule ce qu’elle vaut vraiment.",
                              "Before buying a box or a break spot, work out what it’s really worth."),
                    "source": t("Catalogue SlabCoach (fabricant)", "SlabCoach catalogue (manufacturer)"), "url": "", "lien": "#analyse"})
    out.sort(key=lambda x: x["sortie"], reverse=True)
    return out


def liste(api, niveau=None, force=False, langue="fr"):
    par = dict(_globales(api, langue, force))
    par.update(_calculer(api, langue, [g for g in GENERATEURS if g.__name__ in _PAR_COMPTE]))
    out = [dict(par[g.__name__]) for g in GENERATEURS if g.__name__ in par]
    # 20 nov 2026 : les trucs du hobby (sans donnees eBay) ; leur ordre change chaque jour, pour en voir de nouveaux
    import datetime as _dt
    hk = astuces_hockey(langue)
    j = _dt.date.today().toordinal() % len(hk)
    out += hk[j:] + hk[:j]
    out = sorties(langue) + out
    # debutant / retour : d'abord les bases ; avance : d'abord les chiffres
    ordre = {"debutant": ["debutant", "tous", "avance"], "retour": ["debutant", "tous", "avance"],
             "expert": ["avance", "tous", "debutant"]}.get(niveau or "", ["tous", "debutant", "avance"])
    out.sort(key=lambda x: (ordre.index(x["niveau"]) if x["niveau"] in ordre else 9, not x.get("calcule")))
    return out


# -- 18 nov 2026 (Mathieu : « renseigne-toi le max possible sur le baseball, surtout le vintage ; tu dois tout connaitre ») :
# les astuces du BASEBALL (vues quand le sport choisi est le baseball). Chaque fait vient d'une source verifiee, citee.
def _bb(id_, niveau, genre, titre, chiffre, texte, truc, source, url, lien="#valeur"):
    return {"id": id_, "niveau": niveau, "genre": genre, "titre": titre, "chiffre": chiffre, "texte": texte, "truc": truc,
            "source": source, "url": url, "lien": lien, "calcule": False, "sport": "baseball"}


def astuces_baseball(langue="fr"):
    t = T(langue)
    return [
        _bb("bb_mantle", "tous", "acheter", t("La Mantle 1952 Topps n’est pas sa recrue", "The 1952 Topps Mantle isn’t his rookie"), "1951",
            t("Sa vraie recrue est la 1951 Bowman #253. La 1952 Topps #311 est sa « première Topps », la carte la plus célèbre d’après-guerre, "
              "et la plus contrefaite.", "His true rookie is the 1951 Bowman #253. The 1952 Topps #311 is his “first Topps”, the most famous "
              "post-war card, and the most counterfeited."),
            t("Une Mantle à bon prix sans boîtier PSA ou SGC : passe ton tour.", "A cheap Mantle without a PSA or SGC slab: walk away."),
            "Sports Collectors Daily", "https://www.sportscollectorsdaily.com/five-tips-for-novice-1950s-collectors/"),
        _bb("bb_high", "avance", "acheter", t("1952 Topps : les « high numbers » #311 à #407", "1952 Topps: the high numbers #311 to #407"), "#311+",
            t("La dernière série est arrivée si tard que les détaillants n’en voulaient pas : elle est bien plus rare que le reste du set. "
              "Beaucoup des survivantes ont abouti au Canada et dans le nord des États-Unis.", "The last series shipped so late that "
              "retailers didn’t want it: it’s far scarcer than the rest of the set. Many survivors ended up in Canada and the northern US."),
            t("Une 1952 Topps de joueur ordinaire numérotée 311 et plus vaut souvent plus qu’une vedette des premières séries.",
              "A 1952 Topps common numbered 311 and up is often worth more than a star from the early series."),
            "Old Sports Cards", "https://www.oldsportscards.com/?p=2603"),
        _bb("bb_junk", "debutant", "vendre", t("1986-1993 : la « junk wax » ne vaut presque rien", "1986-1993: “junk wax” is worth almost nothing"),
            "2,5 M",
            t("Topps a imprimé environ 2,5 millions de copies de chaque carte de 1987, et la recrue Griffey Upper Deck 1989 environ 2 millions. "
              "Les exceptions : les erreurs célèbres (1990 Topps Frank Thomas sans nom, moins de 500 copies) et les Tiffany.",
              "Topps printed about 2.5 million copies of each 1987 card, and the 1989 Upper Deck Griffey rookie about 2 million. The "
              "exceptions: famous errors (1990 Topps Frank Thomas no-name, under 500 copies) and Tiffany cards."),
            t("Ne fais pas grader une base de cette époque : la gradation coûte souvent plus que la carte.",
              "Don’t grade a base card from that era: grading often costs more than the card."),
            "All Vintage Cards", "https://allvintagecards.com/history-of-the-junk-wax-era/"),
        _bb("bb_rc", "debutant", "info", t("Une recrue de baseball : le logo RC après son 1er match", "A baseball rookie: the RC logo after his debut"),
            "RC",
            t("Selon Topps, une recrue est sa 1re carte après un match officiel dans la MLB (une présence au bâton ou un lancer suffit), "
              "marquée du logo RC. Les recrues « flagship » sortent dans Series 1, Series 2 et Update.",
              "Per Topps, a rookie card is his first card after an official MLB game (one at-bat or one pitch is enough), marked with the "
              "RC logo. Flagship rookies come in Series 1, Series 2 and Update."),
            t("Un joueur rappelé en juin ou plus tard rate souvent le flagship de l’année : sa recrue sort l’année suivante.",
              "A player called up in June or later often misses that year’s flagship: his rookie comes the next year."),
            "Topps (Ripped)", "https://ripped.topps.com/mlb-rookie-card-crash-course-part-one-product"),
        _bb("bb_1st", "tous", "acheter", t("Avant la recrue : la « 1st Bowman »", "Before the rookie: the “1st Bowman”"), "1st",
            t("La 1st Bowman est la 1re carte d’un espoir, dans l’uniforme de l’équipe qui l’a repêché, marquée « 1st Bowman ». C’est la "
              "carte d’espoir qui vaut presque toujours le plus, souvent plus que sa recrue.", "The 1st Bowman is a prospect’s first "
              "card, in the uniform of the team that drafted him, stamped “1st Bowman”. It’s the prospect card that almost always carries "
              "the most value, often more than his rookie."),
            t("La reine : la 1st Bowman Chrome AUTO. La version papier vaut bien moins.", "The queen: the 1st Bowman Chrome AUTO. The "
              "paper version is worth far less."),
            "Sports Illustrated", "https://www.si.com/collectibles/inside-the-hobby/posts/what-is-the-best-mlb-prospect-card-to-buy"),
        _bb("bb_rainbow", "avance", "acheter", t("Topps Chrome : la Red /5 sort 1 paquet sur 6 299", "Topps Chrome: the Red /5 falls 1 in 6,299 packs"),
            "/5",
            t("2025 Topps Chrome : Refractor 1:3, Gold /50 1:595, Orange /25 1:681, Black /10 1:1 717, Red /5 1:6 299, SuperFractor 1/1. "
              "Chaque couleur a son prix : ne compare jamais une Gold avec une Orange.", "2025 Topps Chrome: Refractor 1:3, Gold /50 "
              "1:595, Orange /25 1:681, Black /10 1:1,717, Red /5 1:6,299, SuperFractor 1/1. Each color has its price: never compare a "
              "Gold with an Orange."),
            t("La Refractor de base (1 paquet sur 3) n’est pas rare : ne la paie pas comme une numérotée.",
              "The base Refractor (1 in 3 packs) isn’t rare: don’t pay for it like a numbered card."),
            "Cardboard Connection", "https://www.cardboardconnection.com/2025-topps-chrome-baseball-set-review-and-checklist"),
        _bb("bb_mirror", "avance", "acheter", t("Topps flagship : la Golden Mirror SSP", "Topps flagship: the Golden Mirror SSP"), "SSP",
            t("Chaque carte de base a une variation photo « Golden Mirror » : au dos, la mention SSP en or près du numéro. Environ 1 paquet "
              "hobby sur 454, environ 150 copies chacune (non numérotées).", "Every base card has a “Golden Mirror” photo variation: on "
              "the back, a gold SSP label by the card number. About 1 in 454 hobby packs, about 150 copies each (not numbered)."),
            t("Une annonce « variation » sans photo du dos : demande-la. Le mot SSP en or ne ment pas.",
              "A “variation” listing without a back photo: ask for it. The gold SSP label doesn’t lie."),
            "Beckett", "https://beckett.com/news/2023-topps-golden-mirror-image-variations-guide"),
        _bb("bb_vintage_grade", "avance", "vendre", t("Vintage : un PSA 10 d’avant 1970 est presque impossible", "Vintage: a pre-1970 PSA 10 is "
            "almost impossible"), "PSA 8",
            t("Coupées à la main, gardées dans des paquets de cigarettes ou des élastiques : les cartes anciennes ont presque toutes de "
              "l’usure. Le centrage toléré est plus large pour un PSA 8 : environ 75/25 avant 1960, 70/30 dans les années 60.",
              "Hand-cut, stored in cigarette packs or rubber bands: old cards almost all show wear. Centering is judged more loosely for "
              "a PSA 8: about 75/25 before 1960, 70/30 in the ’60s."),
            t("Pour le vintage, SGC est souvent préféré sous 1 000 $ ; PSA rapporte plus au-dessus.",
              "For vintage, SGC is often preferred under $1,000; PSA pays more above that."),
            "Pregrade Cards", "https://pregradecards.com/blog/vintage-baseball-card-grading-t206-wagner-1952-mantle-2026"),
        _bb("bb_prewar", "tous", "info", t("Avant-guerre : le T206, le set le plus collectionné", "Pre-war: T206, the most collected set"), "524",
            t("Le T206 (1909-1911) compte 524 cartes, dont la Honus Wagner, la carte la plus chère du hobby, et quatre Ty Cobb. Le Goudey 1933 "
              "a lancé l’ère des cartes avec gomme : Babe Ruth, deux Lou Gehrig, et la Nap Lajoie jamais vendue en paquet.",
              "T206 (1909-1911) has 524 cards, including Honus Wagner, the hobby’s most valuable card, and four Ty Cobbs. 1933 Goudey "
              "launched the gum-card era: Babe Ruth, two Lou Gehrigs, and the Nap Lajoie never sold in packs."),
            t("En avant-guerre, l’état compte moins : une T206 d’une vedette garde sa valeur même usée.",
              "In pre-war, condition matters less: a star’s T206 holds value even when worn."),
            "Pre-War Cards", "https://prewarcards.com/2019/12/13/best-baseball-card-sets-of-all-time-pre-war-t206-1933-goudey-old-judge-n172/"),
        _bb("bb_trim", "avance", "acheter", t("Vintage : repérer une carte coupée (« trimmed »)", "Vintage: spotting a trimmed card"), t("Bord", "Edge"),
            t("Ne te fie pas à la mesure : les vieilles cartes varient en taille. Compare avec des cartes du même set : un bord plus pâle, "
              "lisse comme du verre ou trop propre pour son âge, ou un coin plié en triangle croche, trahit une coupe.",
              "Don’t rely on measuring: old cards vary in size. Compare with cards from the same set: an edge that’s lighter, glassy-smooth "
              "or too clean for its age, or a corner crease that makes a lopsided triangle, gives away a trim."),
            t("Même dans un boîtier, regarde les bords à la loupe : des cartes altérées ont déjà été gradées.",
              "Even in a slab, check the edges under a loupe: altered cards have been graded before."),
            "Beckett", "https://www.beckett.com/news/how-to-spot-and-protect-yourself-from-trimmed-sports-cards/"),
        _bb("bb_80s", "tous", "acheter", t("Années 80 : les recrues qui valent encore cher", "The ’80s: rookies still worth real money"), "1984",
            t("Malgré la surproduction : 1980 Topps Rickey Henderson #482, 1983 Topps Tony Gwynn #482, et le set 1984 Fleer Update (Clemens, "
              "Puckett, Gooden), tiré en petite quantité. La 1982 Topps Traded Ripken vaut plus que sa vraie recrue, mais n’en est pas une.",
              "Despite overproduction: 1980 Topps Rickey Henderson #482, 1983 Topps Tony Gwynn #482, and the 1984 Fleer Update set (Clemens, "
              "Puckett, Gooden), printed in small quantities. The 1982 Topps Traded Ripken sells for more than his true rookie, but isn’t one."),
            t("Une « recrue » des années 80 : vérifie le set et le numéro, pas seulement l’année.",
              "An ’80s “rookie”: check the set and the card number, not just the year."),
            "Cardboard Connection", "https://www.cardboardconnection.com/10-baseball-rookie-cards-1980s/amp"),
        _bb("bb_iconiques", "tous", "info", t("Les recrues iconiques, décennie par décennie", "The iconic rookies, decade by decade"), "#253",
            t("1951 Bowman Mantle #253 · 1963 Topps Pete Rose #537 · 1980 Topps Rickey Henderson #482 · 1993 SP Derek Jeter #279 · 2001 "
              "Bowman Chrome Pujols auto · 2011 Topps Update Mike Trout #US175 · 2018 Bowman Chrome Ohtani.",
              "1951 Bowman Mantle #253 · 1963 Topps Pete Rose #537 · 1980 Topps Rickey Henderson #482 · 1993 SP Derek Jeter #279 · 2001 "
              "Bowman Chrome Pujols auto · 2011 Topps Update Mike Trout #US175 · 2018 Bowman Chrome Ohtani."),
            t("Le numéro de la carte fait partie du nom : une « Trout 2011 » sans US175 n’est pas LA recrue.",
              "The card number is part of the name: a “2011 Trout” without US175 isn’t THE rookie."),
            "Sports Illustrated", "https://www.si.com/collectibles/the-best-baseball-rookie-cards-from-every-decade"),
        _bb("bb_opc", "avance", "acheter", t("Vintage : la O-Pee-Chee, la Topps canadienne bien plus rare", "Vintage: O-Pee-Chee, the far rarer "
            "Canadian Topps"), "299",
            t("Imprimées pour le petit marché canadien : la recrue Mike Schmidt 1973 compte 299 copies gradées en O-Pee-Chee contre 19 468 "
              "en Topps. Dos bilingue depuis 1970, « Printed in Canada », et un centrage souvent pire : les hautes notes sont rares.",
              "Printed for the small Canadian market: the 1973 Mike Schmidt rookie has 299 graded O-Pee-Chee copies versus 19,468 Topps. "
              "Bilingual backs since 1970, “Printed in Canada”, and often worse centering: high grades are rare."),
            t("Au Québec, on en trouve encore dans les ventes de garage : regarde le dos avant d’acheter un lot.",
              "In Canada they still turn up at garage sales: check the back before buying a lot."),
            "Sports Illustrated", "https://www.si.com/collectibles/5-most-valuable-and-iconic-o-pee-chee-baseball-cards"),
        _bb("bb_espoirs", "tous", "vendre", t("Les espoirs : achète l’hiver, vends le jour du rappel", "Prospects: buy in winter, sell on call-up day"),
            "−60 %",
            t("Le prix d’un espoir culmine souvent au rappel ou au premier match (Caglianone : 1 263 $ le jour de ses débuts, environ 500 $ "
              "ensuite). Le battage retombe vite : Langford PSA 10 de 900 $ à 340 $, Volpe de 1 000 $ à environ 425 $.",
              "A prospect’s price often peaks at the call-up or first game (Caglianone: $1,263 on debut day, about $500 after). Hype fades "
              "fast: Langford PSA 10 from $900 to $340, Volpe from $1,000 to about $425."),
            t("Achète d’octobre à janvier ou pendant une léthargie ; vends dans l’emballement du printemps ou au rappel.",
              "Buy from October to January or during a slump; sell into spring hype or on call-up day."),
            "All Vintage Cards · CLLCT", "https://allvintagecards.com/boom-or-bust-the-pros-cons-of-investing-in-baseball-prospect-cards/"),
        _bb("bb_finest", "avance", "info", t("1993 Finest : la toute première Refractor", "1993 Finest: the very first Refractor"), "~241",
            t("Les Refractors sont nées en 1993 dans Finest : environ 1 paquet sur 15, et un tirage estimé à 241 copies de chaque carte "
              "(jamais confirmé par Topps). Très sensibles au centrage et aux égratignures.",
              "Refractors were born in 1993 Finest: about 1 in 15 packs, with an estimated 241 copies of each card (never confirmed by Topps). "
              "Very sensitive to centering and scratches."),
            t("Pas de numéro au dos : on la reconnaît à son reflet arc-en-ciel. Compare toujours avec une photo d’une gradée.",
              "No number on the back: you spot it by its rainbow shine. Always compare with a photo of a graded one."),
            "Baseball Cardpedia", "https://baseballcardpedia.com/index.php/1993_Finest"),
        _bb("bb_ohtani_jp", "avance", "acheter", t("Ohtani : sa vraie première carte est japonaise", "Ohtani: his true first card is Japanese"), "829",
            t("Avant les Angels, Ohtani jouait au Japon : sa 2013 BBM 1st Version « Red Wing » est sa carte la plus recherchée de cette "
              "époque. Seulement 829 copies gradées par PSA, contre environ 34 000 pour sa Bowman 2018 de base ; une PSA 10 s’est vendue "
              "11 200 $.", "Before the Angels, Ohtani played in Japan: his 2013 BBM 1st Version “Red Wing” is his most sought card from "
              "that era. Only 829 PSA-graded copies, versus about 34,000 for his 2018 base Bowman; a PSA 10 sold for $11,200."),
            t("Le hobby appelle quand même 2018 son année recrue : une carte japonaise ne porte pas le logo RC.",
              "The hobby still calls 2018 his rookie year: a Japanese card doesn’t carry the RC logo."),
            "Sports Illustrated", "https://www.si.com/collectibles/auctions/comparing-shohei-ohtani-japanese-mlb-cards"),
        _bb("bb_1955", "tous", "acheter", t("1955 Topps : trois recrues du Temple dans le plus petit set", "1955 Topps: three Hall of Fame rookies in the "
            "smallest set"), "#164",
            t("206 cartes seulement, le premier Topps à l’horizontale, et trois recrues : Sandy Koufax #123, Harmon Killebrew #124, "
              "Roberto Clemente #164. Même en PSA 1, une Clemente se vend près de 900 $.",
              "Only 206 cards, the first horizontal Topps, and three rookies: Sandy Koufax #123, Harmon Killebrew #124, Roberto Clemente "
              "#164. Even in PSA 1, a Clemente sells for about $900."),
            t("En vintage, une carte usée mais bien centrée se revend souvent mieux qu’une carte propre et décentrée : demande les deux "
              "côtés en photo.", "In vintage, a worn but well-centered card often resells better than a clean off-center one: ask for "
              "photos of both sides."),
            "Sports Illustrated", "https://www.si.com/collectibles/hobby-101/three-iconic-rookie-cards-help-1955-topps"),
        _bb("bb_draft", "tous", "acheter", t("Bowman Draft : les 1st Bowman des repêchés, sans aucune recrue", "Bowman Draft: draftees’ 1st Bowman, no "
            "rookies at all"), "Top 3",
            t("Depuis 2014, Bowman Draft ne contient que des joueurs qui n’ont jamais joué dans la MLB : la 1re carte Bowman des repêchés "
              "de l’année. Les autos des trois premiers choix font la valeur du produit.",
              "Since 2014, Bowman Draft only has players who haven’t debuted in MLB: the year’s draftees’ first Bowman card. The autos "
              "of the top three picks drive the product’s value."),
            t("Acheter une 1st Bowman d’un repêché, c’est parier sur 3 à 5 ans : la plupart ne deviennent pas des vedettes.",
              "Buying a draftee’s 1st Bowman is a 3-to-5-year bet: most don’t become stars."),
            "Topps (Ripped)", "https://ripped.topps.com/bowman-draft"),
        _bb("bb_ginter", "avance", "acheter", t("Allen & Ginter : la mini en bois, 1 seule copie", "Allen & Ginter: the wood mini, one of one"), "1/1",
            t("Allen & Ginter a ses minis : normale et bordure noire (illimitées), « No Number » /50, en bois 1/1 (hobby seulement). Les "
              "mini autos encadrées vont de /99 (vert) à 1/1 (mauve).", "Allen & Ginter has its minis: regular and black border "
              "(unlimited), “No Number” /50, wood 1/1 (hobby only). Framed mini autos run from /99 (green) to 1/1 (purple)."),
            t("Une mini « No Number » n’a pas de numéro au dos : c’est justement ce qui la rend rare. Ne la confonds pas avec une erreur.",
              "A “No Number” mini has no number on the back: that’s exactly what makes it rare. Don’t mistake it for an error."),
            "Cardboard Connection", "https://www.cardboardconnection.com/2025-topps-allen-ginter-baseball-set-review-and-checklist"),
        _bb("bb_bowman55", "avance", "acheter", t("1948-1955 : l’âge d’or de Bowman", "1948-1955: Bowman’s golden age"), "#66",
            t("La 1954 Bowman #66 Ted Williams a été retirée des paquets (dispute de contrat avec Topps) : la plus rare du set. En 1955, le "
              "cadre « télé » brun s’écaille aux coins, et les #225 à #320 sont la série difficile. Bowman disparaît ensuite, achetée par Topps.",
              "The 1954 Bowman #66 Ted Williams was pulled from packs (contract fight with Topps): the set’s scarcest card. In 1955, the "
              "brown “TV” frame chips at the corners, and #225 to #320 are the tough series. Bowman then vanished, bought by Topps."),
            t("Une 1955 Bowman aux coins propres vaut une prime : c’est le défaut que tout le monde a.",
              "A 1955 Bowman with clean corners earns a premium: it’s the flaw everyone has."),
            "All Vintage Cards", "https://allvintagecards.com/1955-bowman-baseball-most-valuable/"),
        _bb("bb_heritage", "avance", "acheter", t("Topps Heritage : toutes les variations ne se valent pas", "Topps Heritage: not all variations are equal"),
            "1:22 487",
            t("Heritage copie un vieux set (2022 = 1973). Les SP du haut du set sortent 1 paquet sur 3. Variation photo : 1:64. Mais Throwback "
              "1:22 487, Error 1:9 506, Nickname 1:4 753 : celles-là sont vraiment rares.", "Heritage copies an old set (2022 = 1973). The "
              "high-numbered SPs fall 1 in 3 packs. Photo variation: 1:64. But Throwback 1:22,487, Error 1:9,506, Nickname 1:4,753: those "
              "are truly rare."),
            t("Une annonce « SP variation » Heritage peut être la commune 1:64 : vérifie laquelle avant de payer le prix d’une rare.",
              "A Heritage “SP variation” listing may be the common 1:64: check which one before paying a rare’s price."),
            "Cardlines", "https://www.cardlines.com/guide-to-2022-topps-heritage-short-prints-and-variations/"),
        _bb("bb_integration", "tous", "info", t("Jackie Robinson : sa vraie recrue est la 1948 Leaf #79", "Jackie Robinson: his true rookie is the 1948 Leaf #79"),
            "#79",
            t("Le set 1948 Leaf (98 cartes numérotées jusqu’à 168) a les 1res cartes de Robinson #79, Satchel Paige #8 (une SP, la plus chère "
              "du set) et Larry Doby #138. La 1949 Bowman #50 de Robinson est souvent vendue comme « RC », mais elle vient après ; sa carte la "
              "plus chère reste la 1952 Topps #312.", "The 1948 Leaf set (98 cards numbered up to 168) has the first cards of Robinson #79, "
              "Satchel Paige #8 (a short print, the set’s priciest) and Larry Doby #138. Robinson’s 1949 Bowman #50 is often sold as an “RC”, "
              "but it came later; his priciest card is still the 1952 Topps #312."),
            t("« RC » dans un titre vintage n’est pas une garantie : vérifie l’année de la 1re carte du joueur.",
              "“RC” in a vintage title isn’t a guarantee: check the year of the player’s first card."),
            "Old Sports Cards", "https://www.oldsportscards.com/?p=1348"),
        _bb("bb_60s", "tous", "acheter", t("Années 60 : les recrues partagées", "The ’60s: shared rookie cards"), "#177",
            t("Plusieurs grandes recrues des années 60 sont sur une carte à 2 ou 4 joueurs : 1968 Topps #177 Nolan Ryan avec Jerry Koosman, "
              "#247 Johnny Bench, 1967 #581 Tom Seaver, 1963 #537 Pete Rose (avec trois autres). Le nom de l’autre joueur dans le titre, "
              "c’est normal.", "Several great ’60s rookies share a card with 2 to 4 players: 1968 Topps #177 Nolan Ryan with Jerry Koosman, "
              "#247 Johnny Bench, 1967 #581 Tom Seaver, 1963 #537 Pete Rose (with three others). Another player’s name in the title is normal."),
            t("Une « Jerry Koosman 1968 » sans le nom de Ryan dans le titre est souvent la même carte #177 : vérifie le numéro.",
              "A “1968 Jerry Koosman” without Ryan’s name in the title is often the same #177 card: check the number."),
            "Cardboard Connection", "https://www.cardboardconnection.com/top-10-baseball-rookie-cards-of-the-1960s"),
        _bb("bb_japon", "avance", "acheter", t("Japon : la vraie 1re carte d’Ichiro est une BBM 1993", "Japan: Ichiro’s true first card is a 1993 BBM"),
            "#239",
            t("Avant la MLB, les vedettes japonaises ont des cartes BBM et Calbee : Ichiro 1993 BBM #239, Matsui 1993 BBM #423, Ohtani 2013 "
              "BBM. Les BBM 1993 sont plus petites que les cartes américaines, et les contrefaçons sont nombreuses.", "Before MLB, Japanese "
              "stars have BBM and Calbee cards: Ichiro 1993 BBM #239, Matsui 1993 BBM #423, Ohtani 2013 BBM. 1993 BBMs are smaller than US "
              "cards, and fakes are common."),
            t("Une Ichiro 1993 BBM ou 1994 Calbee Hokkaido : achète-la gradée seulement. Les fausses ont une impression tachée et des "
              "lettres plus arrondies.", "A 1993 BBM or 1994 Calbee Hokkaido Ichiro: buy it graded only. Fakes have spotty print and "
              "rounder lettering."),
            "Cardboard Connection", "https://www.cardboardconnection.com/top-japanese-ichiro-cards"),
        _bb("bb_70s", "tous", "acheter", t("Années 70 : Brett, Yount, Ozzie, Munson", "The ’70s: Brett, Yount, Ozzie, Munson"), "#228",
            t("Les recrues 70 les plus chères en PSA 8 : 1971 Blyleven #26, 1973 Schmidt #615, 1970 Munson #189, 1975 Brett #228, "
              "1975 Yount #223, 1979 Ozzie Smith #116. La 1971 #709 (Baker, Baylor) est une SP à bordure noire : chaque coin abîmé se voit.",
              "The priciest ’70s rookies in PSA 8: 1971 Blyleven #26, 1973 Schmidt #615, 1970 Munson #189, 1975 Brett #228, 1975 "
              "Yount #223, 1979 Ozzie Smith #116. The 1971 #709 (Baker, Baylor) is a black-bordered short print: every chipped corner shows."),
            t("Pour les années 70, vise le PSA 8 : c’est là que le marché se fait. Un PSA 9 vaut souvent plusieurs fois plus.",
              "For the ’70s, aim for PSA 8: that’s where the market trades. A PSA 9 is often worth several times more."),
            "Cardboard Connection", "https://www.cardboardconnection.com/most-valuable-baseball-rookie-cards-1970s"),
        _bb("bb_90s_inserts", "avance", "acheter", t("Années 90 : les inserts devenus légendaires", "The ’90s: inserts that became legends"), "PMG",
            t("Au milieu de la junk wax, des inserts valent une fortune : 1991 Donruss Elite (la 1re carte numérotée, /10 000), 1993 Finest "
              "Refractor (~241 copies), 1997 Flair Showcase Masterpieces (les 1res 1/1), 1998 Donruss Crusade, 1998 Metal Universe "
              "Precious Metal Gems (50 copies au plus).", "Amid junk wax, some inserts are worth a fortune: 1991 Donruss Elite (the first "
              "numbered card, /10,000), 1993 Finest Refractor (~241 copies), 1997 Flair Showcase Masterpieces (the first 1/1s), 1998 Donruss "
              "Crusade, 1998 Metal Universe Precious Metal Gems (50 copies at most)."),
            t("Une carte des années 90 numérotée ou 1/1 n’est pas de la junk wax : regarde le dos avant de la jeter dans un lot.",
              "A numbered or 1/1 ’90s card isn’t junk wax: check the back before tossing it in a lot."),
            "Sports Illustrated", "https://www.si.com/collectibles/top-5-iconic-1990s-baseball-card-insert-sets"),
    ]
