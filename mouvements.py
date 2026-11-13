"""
SLABCOACH - pourquoi les cartes d'un joueur bougent (13 nov 2026).

Mathieu : « notre modele doit analyser et comprendre pourquoi les mouvements se font et pourquoi il y a des spikes de ventes
de certains joueurs dans le temps. Lorsqu'un joueur est cible, cherche tout ce qui aurait pu faire baisser ou augmenter sa
valeur ou faire augmenter significativement sa liquidite. »

1. Le journal des evenements : chaque jour, les evenements de l'Indice (Temple, honneur, trophee, exploit, rappel, contrat,
   echange, blessure, mauvaise nouvelle : des TITRES de nouvelles publiques) sont gardes un an par joueur. Plus l'equipe et
   « en feu » du jour (quoi_de_neuf.hist_lire, 45 jours).
2. Pour un joueur : ses ventes (nos archives, un an), semaine par semaine. Le PRIX : chaque vente comparee a la mediane de SA
   carte (la meme carte d'une semaine a l'autre, pas une PSA 10 contre une base). La LIQUIDITE : combien de ventes, contre
   les 6 semaines d'avant. Un mouvement : ventes x 2 et plus (4 et plus), ou prix +/- 18 % et plus.
3. Pour chaque mouvement, les causes possibles autour (la semaine et les 7 jours d'avant) : un evenement du journal, un
   changement d'equipe, une semaine « en feu », la sortie d'un produit ou il a une carte (catalogue). Rien trouve : on le dit
   (souvent l'offre : beaucoup de cartes mises en vente d'un coup).
4. Ce que les evenements font, en general (tous les joueurs) : pour chaque type d'evenement, le prix et les ventes des 14
   jours apres contre les 28 d'avant. Le modele apprend ainsi ce qui fait VRAIMENT bouger les cartes.
Prix tires d'eBay : admin seulement (licence).
"""
import json
import math
import os
import re
import statistics
import threading
from datetime import date, timedelta

JOURNAL_J = 400
SEUIL_VOLUME = 2.0
SEUIL_VOLUME_MIN = 4
SEUIL_PRIX = 0.18                 # en log : environ +/- 20 %
_verrou = threading.Lock()
_CACHE = {"mt": None, "d": None}


# -- 1. le journal des evenements ----------------------------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "mouvements_journal.json")


def journal():
    p = _chemin()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _CACHE["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _CACHE["d"] = json.load(f) or {}
            _CACHE["mt"] = mt
        except (OSError, ValueError):
            return _CACHE["d"] or {}
    return _CACHE["d"] or {}


def journal_noter(I, aujourdhui=None):
    """L'Indice du jour -> les evenements de chaque joueur gardes (sans doublon : meme titre), un an."""
    jour = (aujourdhui or date.today()).isoformat()
    lim = (date.fromisoformat(jour) - timedelta(days=JOURNAL_J)).isoformat()
    n = 0
    with _verrou:
        d = json.loads(json.dumps(journal()))
        for nom, v in (I or {}).items():
            evs = v.get("evenements") or []
            if not evs:
                continue
            l = d.setdefault(nom, [])
            vus = {e.get("titre") for e in l}
            for e in evs:
                if e.get("titre") and e["titre"] not in vus:
                    l.append({"date": str(e.get("date") or jour)[:10], "type": e.get("type"), "sens": e.get("sens"),
                              "titre": str(e["titre"])[:160], "lien": e.get("lien")})
                    vus.add(e["titre"])
                    n += 1
            d[nom] = [e for e in l if e["date"] >= lim][-200:]
        p = _chemin()
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(p + ".tmp", p)
        _CACHE["mt"], _CACHE["d"] = os.path.getmtime(p), d
    return n


# -- 2. les semaines d'un joueur ------------------------------------------------------------------------------------------
def _lundi(j):
    d = date.fromisoformat(str(j)[:10])
    return (d - timedelta(days=d.weekday())).isoformat()


def _a_le_joueur(titre, nom):
    import cartes_match
    t = cartes_match.norm(titre or "")
    p = cartes_match.norm(nom or "").split()
    if len(p) < 2:
        return False
    return bool(re.search(r"\b" + re.escape(p[-1]) + r"\b", t)) and (re.search(r"\b" + re.escape(p[0]) + r"\b", t) is not None or f" {p[0][0]} " in f" {t} ")


def semaines(ventes, nom=None):
    """Les ventes d'un joueur -> [{semaine, n, prix (log, relatif a la carte), n_prix}], dans l'ordre."""
    import cartes_match
    par_carte = {}
    L = []
    for v in ventes or []:
        try:
            p = float(v.get("prix") or 0)
        except (TypeError, ValueError):
            continue
        if p <= 0 or not v.get("le") or (nom and not _a_le_joueur(v.get("titre"), nom)):
            continue
        cib = cartes_match.cible_titre(v.get("titre") or "")
        if cib.get("exclu"):
            continue
        k = (cartes_match.requete_ebay(cib) or "") + "|" + str(cib.get("annee")) + "|" + str((cib.get("grade") or {}).get("note"))
        par_carte.setdefault(k, []).append(math.log(p))
        L.append((str(v["le"])[:10], k, math.log(p)))
    med = {k: statistics.median(l) for k, l in par_carte.items() if len(l) >= 2}
    S = {}
    for j, k, lp in L:
        s = S.setdefault(_lundi(j), {"n": 0, "rel": []})
        s["n"] += 1
        if k in med:
            s["rel"].append(lp - med[k])
    if not S:
        return []
    # toutes les semaines entre la premiere et la derniere (une semaine sans vente compte : 0)
    d0, d1 = date.fromisoformat(min(S)), date.fromisoformat(max(S))
    out = []
    d = d0
    while d <= d1:
        s = S.get(d.isoformat(), {"n": 0, "rel": []})
        out.append({"semaine": d.isoformat(), "n": s["n"], "prix": statistics.median(s["rel"]) if s["rel"] else None, "n_prix": len(s["rel"])})
        d += timedelta(days=7)
    return out


def mouvements(sem):
    """Les semaines -> les mouvements (volume ou prix), le plus fort d'abord."""
    out = []
    for i, s in enumerate(sem):
        avant = sem[max(0, i - 6):i]
        if len(avant) < 3:
            continue
        base_n = max(1.0, statistics.median([a["n"] for a in avant]))
        px_av = [a["prix"] for a in sem[max(0, i - 4):i] if a["prix"] is not None and a["n_prix"] >= 2]
        dvol = s["n"] / base_n
        dprix = (s["prix"] - statistics.mean(px_av)) if (s["prix"] is not None and s["n_prix"] >= 3 and len(px_av) >= 2) else None
        vol = dvol >= SEUIL_VOLUME and s["n"] >= SEUIL_VOLUME_MIN
        prix = dprix is not None and abs(dprix) >= SEUIL_PRIX
        if vol or prix:
            out.append({"semaine": s["semaine"], "ventes": s["n"], "ventes_x": round(dvol, 1), "volume": vol,
                        "prix_pct": round(100 * (math.exp(dprix) - 1)) if dprix is not None else None, "prix": prix,
                        "force": (math.log(dvol) if vol else 0) + (abs(dprix) * 3 if prix else 0)})
    return out


# -- 3. les causes ------------------------------------------------------------------------------------------------------
NOMS_TYPES = {"temple": "Temple de la renommée", "honneur": "Honneur", "trophee": "Trophée", "exploit": "Exploit", "rappel": "Rappel / début",
              "contrat": "Contrat", "echange": "Échange", "blessure": "Blessure", "negatif": "Mauvaise nouvelle", "equipe": "Changement d'équipe",
              "feu": "En feu (grosse semaine)", "sortie": "Sortie d'un produit"}


def _produits_sortis(nom, d0, d1):
    """Les produits du catalogue sortis entre d0 et d1 ou le joueur a une carte."""
    import glob
    import cartes_match
    k = cartes_match.norm(nom)
    out = []
    for ch in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogue", "*.json")):
        try:
            with open(ch, encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, ValueError):
            continue
        s = str(p.get("sortie") or "")[:10]
        if not s or not (d0 <= s <= d1):
            continue
        if any(cartes_match.norm(c.get("joueur")) == k for c in p.get("cartes") or [] if isinstance(c, dict)):
            out.append({"type": "sortie", "date": s, "titre": p.get("nom") or p.get("id")})
    return out


def causes(nom, semaine, J=None, hist=None):
    """Ce qui a pu faire bouger les cartes cette semaine-la (la semaine et les 7 jours d'avant)."""
    d1 = (date.fromisoformat(semaine) + timedelta(days=6)).isoformat()
    d0 = (date.fromisoformat(semaine) - timedelta(days=7)).isoformat()
    J = journal() if J is None else J
    out = [dict(e) for e in J.get(nom) or [] if d0 <= str(e.get("date") or "") <= d1]
    if hist is None:
        try:
            import quoi_de_neuf
            hist = quoi_de_neuf.hist_lire()
        except Exception:
            hist = {}
    jours = sorted(k for k in hist if d0 <= k <= d1)
    if jours:
        avant = None
        for k in sorted(k for k in hist if k < d0)[-1:]:
            avant = (hist[k].get(nom) or [None, None, 0])
        eqs = [(hist[k].get(nom) or [None, None, 0]) for k in jours]
        eq0 = (avant or eqs[0])[1]
        for k, e in zip(jours, eqs):
            if e[1] and eq0 and e[1] != eq0:
                out.append({"type": "equipe", "date": k, "titre": f"{eq0} → {e[1]}"})
                break
        if any(e[2] for e in eqs) and not (avant and avant[2]):
            out.append({"type": "feu", "date": next(k for k, e in zip(jours, eqs) if e[2]), "titre": "Une grosse semaine de points"})
    try:
        out += _produits_sortis(nom, d0, d1)
    except Exception:
        pass
    for e in out:
        e["nom_type"] = NOMS_TYPES.get(e.get("type"), e.get("type"))
    out.sort(key=lambda e: e.get("date") or "")
    return out


def analyser(nom, ventes=None, n_max=5):
    """Pour un joueur : ses mouvements de l'annee (prix et liquidite) et leurs causes possibles. Admin (prix d'eBay)."""
    if ventes is None:
        import vendues
        ventes = vendues.archives_joueur(nom, jours=365, max_=3000)
    sem = semaines(ventes, nom)
    mv = mouvements(sem)
    mv.sort(key=lambda m: m["semaine"], reverse=True)
    J, hist = journal(), None
    try:
        import quoi_de_neuf
        hist = quoi_de_neuf.hist_lire()
    except Exception:
        hist = {}
    for m in mv[:n_max]:
        m["causes"] = causes(nom, m["semaine"], J, hist)
        m.pop("force", None)
    return {"joueur": nom, "semaines": len(sem), "ventes": sum(s["n"] for s in sem), "mouvements": mv[:n_max],
            "courbe": [{"semaine": s["semaine"], "n": s["n"]} for s in sem[-26:]]}


# -- 4. ce que les evenements font, en general ------------------------------------------------------------------------------
def effets(noms=None, ventes_de=None, jours_apres=14, jours_avant=28):
    """Pour chaque type d'evenement du journal : le prix (relatif a chaque carte) et les ventes par jour des 14 jours apres,
    contre les 28 jours d'avant. -> {type: {n, prix_pct, ventes_x}} (n = evenements mesures)."""
    J = journal()
    noms = noms or list(J)
    acc = {}
    for nom in noms:
        evs = J.get(nom) or []
        if not evs:
            continue
        if ventes_de:
            ventes = ventes_de(nom)
        else:
            import vendues
            ventes = vendues.archives_joueur(nom, jours=400, max_=3000)
        import cartes_match
        par_carte, L = {}, []
        for v in ventes or []:
            try:
                p = float(v.get("prix") or 0)
            except (TypeError, ValueError):
                continue
            if p <= 0 or not v.get("le") or not _a_le_joueur(v.get("titre"), nom):
                continue
            cib = cartes_match.cible_titre(v.get("titre") or "")
            k = (cartes_match.requete_ebay(cib) or "") + "|" + str(cib.get("annee")) + "|" + str((cib.get("grade") or {}).get("note"))
            par_carte.setdefault(k, []).append(math.log(p))
            L.append((str(v["le"])[:10], k, math.log(p)))
        med = {k: statistics.median(l) for k, l in par_carte.items() if len(l) >= 2}
        for e in evs:
            try:
                d = date.fromisoformat(str(e.get("date"))[:10])
            except ValueError:
                continue
            a0, a1 = (d - timedelta(days=jours_avant)).isoformat(), d.isoformat()
            p0, p1 = d.isoformat(), (d + timedelta(days=jours_apres)).isoformat()
            av = [lp - med[k] for j, k, lp in L if a0 <= j < a1 and k in med]
            ap = [lp - med[k] for j, k, lp in L if p0 <= j <= p1 and k in med]
            n_av = sum(1 for j, _k, _l in L if a0 <= j < a1)
            n_ap = sum(1 for j, _k, _l in L if p0 <= j <= p1)
            if len(av) < 2 or len(ap) < 2:
                continue
            a = acc.setdefault(e.get("type") or "?", {"n": 0, "dp": [], "dv": []})
            a["n"] += 1
            a["dp"].append(statistics.median(ap) - statistics.median(av))
            a["dv"].append((n_ap / jours_apres) / max(n_av / jours_avant, 1 / jours_avant))
    return {t: {"n": a["n"], "nom": NOMS_TYPES.get(t, t), "prix_pct": round(100 * (math.exp(statistics.median(a["dp"])) - 1)),
                "ventes_x": round(statistics.median(a["dv"]), 2)} for t, a in acc.items()}
