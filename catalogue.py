"""
LOCKERROOM - catalogue de produits (checklists + composition des boites).

Un fichier JSON par produit dans catalogue/ (format : catalogue/SCHEMA.md).
Le breaker choisit le produit : l'app sait deja quelles cartes il contient,
combien de chaque sorte sortent par boite, et calcule la liste de prix.

  - liste()             : produits offerts (le plus recent d'abord)
  - charger(id)         : le produit, avec le taux par boite de chaque sous-ensemble
  - cartes_attendues()  : chaque carte du produit et son nombre d'exemplaires
                          attendus dans N boites
"""
import json
import os
import re

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogue")
_CACHE = {}


def dossier_ajouts():
    """24 oct 2026 - checklists importees (Excel Beckett) : sur le disque des donnees (gardees entre deux deploiements)."""
    base = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "catalogue_ajouts")


def _fichiers():
    """Chemins des produits ; un produit importe remplace celui livre avec l'app (meme nom de fichier)."""
    out = {}
    for d in (DOSSIER, dossier_ajouts()):
        try:
            for f in os.listdir(d):
                if f.endswith(".json"):
                    out[f] = os.path.join(d, f)
        except OSError:
            continue
    return [out[k] for k in sorted(out)]


def _lire(chemin):
    if not os.path.isabs(chemin):
        chemin = os.path.join(DOSSIER, chemin)
    mt = os.path.getmtime(chemin)
    if _CACHE.get(chemin, (None,))[0] != mt:
        with open(chemin, encoding="utf-8") as f:
            _CACHE[chemin] = (mt, json.load(f))
    return _CACHE[chemin][1]


def enregistrer_ajout(prod):
    os.makedirs(dossier_ajouts(), exist_ok=True)
    chemin = os.path.join(dossier_ajouts(), prod["id"] + ".json")
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in prod.items() if not k.startswith("_")}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)
    _CACHE.pop(chemin, None)
    return chemin


def _racine(se, nom, prof=0):
    s = se.get(nom) or {}
    p = s.get("parallele_de")
    if p and p in se and p != nom and prof < 6:
        return _racine(se, p, prof + 1)
    return nom


def _liste_de(prod, se, nom):
    """Cartes d'un sous-ensemble : les siennes, ou celles de son sous-ensemble parent."""
    propres = prod["_par_se"].get(nom)
    if propres:
        return propres
    r = _racine(se, nom)
    return prod["_par_se"].get(r) or []


def taux_par_boite(prod):
    """{sous_ensemble: exemplaires attendus par boite}. Les lignes combinees de
    la composition (« X, Y ou Z : 1 par boite ») sont reparties entre leurs
    membres sans taux connu, au prorata du tirage imprime (nb de cartes x
    numerotation ; 100 si non numerote)."""
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    taux = {n: float(s["par_boite"]) for n, s in se.items() if s.get("par_boite") not in (None, "")}
    for g in prod.get("groupes_boite") or []:
        membres = [m for m in g.get("sous_ensembles") or [] if m in se]
        if not membres or g.get("par_boite") in (None, ""):
            continue
        connus = sum(taux[m] for m in membres if m in taux)
        inconnus = [m for m in membres if m not in taux]
        reste = max(0.0, float(g["par_boite"]) - connus)
        if not inconnus or reste <= 0:
            continue
        poids = {}
        for m in inconnus:                      # 26 oct 2026 : exemplaires imprimes = somme des tirages de ses cartes
            lc = _liste_de(prod, se, m) if prod.get("_par_se") is not None else []
            propres = bool((prod.get("_par_se") or {}).get(m))       # une parallele reprend les cartes du parent : SON tirage compte
            if lc and propres and any(c.get("tirage") for c in lc):
                poids[m] = sum(float(c.get("tirage") or se[m].get("tirage") or 100) for c in lc)
            else:
                nb = se[m].get("nb_cartes") or len(lc) or 1
                poids[m] = nb * float(se[m].get("tirage") or 100)
        total = sum(poids.values()) or 1.0
        for m in inconnus:
            taux[m] = reste * poids[m] / total
    # 26 oct 2026 - les cartes de base d'une boite hobby (rarement publiees) : ce qui reste des cartes de la boite
    # (paquets x cartes par paquet) une fois tout le reste compte
    fmt = next((f for f in prod.get("formats") or [] if f.get("paquets") and f.get("cartes_par_paquet")), None)
    if fmt:
        base = [n for n, s in se.items() if s.get("groupe") == "base" and not s.get("parallele_de") and n not in taux
                and not re.search(r"variation|short print|\bsp\b|ssp", n, re.I)]
        if len(base) == 1:
            reste_b = float(fmt["paquets"]) * float(fmt["cartes_par_paquet"]) - sum(taux.values())
            if reste_b > 0:
                taux[base[0]] = round(reste_b, 2)
    _estimer_par_tirage(prod, se, taux)
    return taux


# 30 oct 2026 (Mathieu : « ta methode d'evaluation des odds et du retour sur investissement doit etre robuste ») ----------
# Un sous-ensemble NUMEROTE sans cote publiee (ex. une parallele /199, Population Count 500) : on sait combien d'exemplaires
# existent (cartes x tirage). Les sous-ensembles numerotes du MEME produit dont la cote est connue donnent le nombre de
# boites produites (exemplaires / cote par boite) ; leur mediane (au moins 2) donne la cote estimee des autres.
# Marquees « estimees » (prod["_estimees"]) : comptees dans le calcul, montrees comme telles a l'admin.
_RE_TIR_NOM = re.compile(r"/\s*(\d{1,5})\b")
_RE_TIR_IMPRIME = re.compile(r"(?:chiffre imprim\w*|limit\w*)[^()]*\((\d[\d\s\u00a0\u202f]*)\)", re.I)


def tirage_de(s):
    """Le tirage d'un sous-ensemble : le champ, sinon « /199 » dans le nom, sinon le chiffre imprime des Population Count."""
    t = s.get("tirage")
    if t:
        try:
            return int(t)
        except (TypeError, ValueError):
            pass
    m = _RE_TIR_NOM.search(str(s.get("nom") or ""))
    if m:
        return int(m.group(1))
    m = _RE_TIR_IMPRIME.search(str(s.get("cotes") or ""))
    if m:
        return int(re.sub(r"\D", "", m.group(1)) or 0) or None
    vs = set(_RE_TIR_NOM.findall(str(s.get("cotes") or "")))
    return int(vs.pop()) if len(vs) == 1 else None


def _nb_cartes(prod, se, nom):
    s = se.get(nom) or {}
    if s.get("nb_cartes"):
        return int(s["nb_cartes"])
    return len(_liste_de(prod, se, nom)) if prod.get("_par_se") is not None else 0


def _estimer_par_tirage(prod, se, taux):
    if prod.get("_par_se") is None:
        par = {}
        for c in prod.get("cartes") or []:
            par.setdefault(c.get("sous_ensemble"), []).append(c)
        prod["_par_se"] = par
    boites = []
    for n, t in taux.items():
        s = se.get(n) or {}
        tir = tirage_de(s)                       # cote publiee, ou tiree de la composition de la boite (groupes)
        k = _nb_cartes(prod, se, n)
        if tir and 1 < tir <= 5000 and k and t and t > 0:
            boites.append(k * tir / t)
    est = []
    if len(boites) >= 2:
        boites.sort()
        b = boites[len(boites) // 2] if len(boites) % 2 else (boites[len(boites) // 2 - 1] + boites[len(boites) // 2]) / 2
        for n, s in se.items():
            if n in taux or hors_boite_hobby(s):
                continue
            tir, k = tirage_de(s), _nb_cartes(prod, se, n)
            if tir and 1 < tir <= 5000 and k:
                taux[n] = round(k * tir / b, 5)
                est.append(n)
    # 2) le meme sous-ensemble dans la meme ligne de produit d'une autre saison (cote PUBLIEE la-bas) : Outburst Retro
    #    Young Guns 2026-27 (« cotes non publiees ») prend celle de 2025-26
    src = {}
    try:
        import checklist_import as ci
        ligne = ci._mots_ligne(prod.get("nom"))
        an = int((re.search(r"(19|20)\d{2}", str(prod.get("nom"))) or [0])[0] or 0)
        refs = {}
        if ligne:
            for f in _fichiers():
                d = _lire(f)
                if d.get("id") == prod.get("id") or str(d.get("sport") or "hockey") != str(prod.get("sport") or "hockey") \
                        or ci._mots_ligne(d.get("nom")) != ligne:
                    continue
                a2 = int((re.search(r"(19|20)\d{2}", str(d.get("nom"))) or [0])[0] or 0)
                for x in d.get("sous_ensembles") or []:
                    try:
                        pb = float(x.get("par_boite"))
                    except (TypeError, ValueError):
                        continue
                    if pb > 0:
                        k = ci.cle_sous(x["nom"])
                        if k not in refs or abs(an - a2) < refs[k][1]:
                            refs[k] = (pb, abs(an - a2), d.get("nom"))
        for n, s in se.items():
            if n in taux or hors_boite_hobby(s):
                continue
            r = refs.get(ci.cle_sous(n))
            if r:
                taux[n] = r[0]
                est.append(n)
                src[n] = r[2]
    except Exception:
        pass
    prod["_estimees"] = est
    prod["_estimees_src"] = src
    return est


def hors_boite_hobby(s):
    """Ce qui ne sort pas d'une boite hobby (retail, ePack seulement, hors checklist, plaques, 1/1) : jamais une cote manquante."""
    nom, txt = str(s.get("nom") or ""), str(s.get("cotes") or "")
    if s.get("tirage") == 1 or tirage_de(s) == 1 or re.search(r"printing plate|\bplates?\b|1/1|one of one", nom, re.I):
        return True
    if re.search(r"liste commune|uniquement en versions", txt, re.I):
        return True                                          # la liste des versions de couleur, pas une carte
    if re.search(r"absent\w* d(e la|es?) bo[iî]tes? hobby|exclusi\w* (e-?pack|retail|walmart|target|amazon)|hors checklist", txt, re.I):
        return True
    if txt and _RE_SANS_HOBBY.search(txt) and not _RE_HOBBY.search(txt):
        return True
    return bool(re.search(r"oversized|retail|blaster|hanger|tin\b|mega", nom, re.I))


_RE_SANS_HOBBY = re.compile(r"absent|retail|hanger|blaster|advent|mega|tin\b|dollar|starter|oversized|walmart|target|amazon", re.I)
_RE_HOBBY = re.compile(r"\bh\b|hobby|e-?pack", re.I)


def etat_cotes(prod):
    """26 oct 2026 (Mathieu : « une fleche verte lorsque nous avons la checklist avec tous les odds calcules ») -
    les sous-ensembles d'une boite HOBBY dont on ne connait pas la chance de sortir (donc absents du calcul).
    30 oct 2026 : ne comptent pas (hors_boite_hobby) : retail, ePack seulement, hors checklist, plaques, 1/1 ; « non
    publiees » : le fabricant ne donne pas la cote (le calcul les laisse de cote : il est prudent, jamais gonfle) ;
    « estimees » : numerotees, cote tiree du tirage imprime. -> {manquantes, non_publiees, estimees, complete}"""
    taux = prod.get("_taux") or taux_par_boite(prod)
    est = set(prod.get("_estimees") or [])
    manq, non_pub = [], []
    for s in prod.get("sous_ensembles") or []:
        if (taux.get(s["nom"]) or 0) > 0 or s.get("par_boite"):
            continue
        if hors_boite_hobby(s):
            continue
        txt = str(s.get("cotes") or "")
        if re.search(r"random|non publi|not published|non annonc|unannounced", txt, re.I):
            non_pub.append(s["nom"])                    # le fabricant ne publie pas la cote
            continue
        manq.append(s["nom"])
    return {"manquantes": manq, "non_publiees": non_pub, "estimees": sorted(est), "complete": not manq}


def charger(pid):
    for f in _fichiers():
        d = _lire(f)
        if d.get("id") == pid and d.get("cartes"):
            if "_par_se" not in d or "_taux" not in d:
                par = {}
                for c in d["cartes"]:
                    par.setdefault(c.get("sous_ensemble"), []).append(c)
                taux = taux_par_boite(d)          # 27 oct 2026 (revue) : calcules d'abord, poses ensemble (autre fil : pas de KeyError)
                d.update(_taux=taux, _par_se=par)
            return d
    return None


def liste():
    out = []
    for f in _fichiers():
        d = _lire(f)
        if not d.get("cartes"):
            continue
        p = charger(d["id"])
        t = p["_taux"]
        recrues = sum(v for k, v in t.items() if (next((s for s in p["sous_ensembles"] if s["nom"] == k), {}) or {}).get("groupe") == "recrue")
        hits = sum(v for k, v in t.items() if (next((s for s in p["sous_ensembles"] if s["nom"] == k), {}) or {}).get("groupe") in ("auto", "memo", "auto_memo"))
        fmt = (p.get("formats") or [{}])[0]
        out.append({"id": p["id"], "nom": p["nom"], "saison": p.get("saison"), "marque": p.get("marque"), "sortie": p.get("sortie"),
                    "format": fmt.get("format"), "paquets": fmt.get("paquets"), "cartes_par_paquet": fmt.get("cartes_par_paquet"),
                    "boites_par_caisse": fmt.get("boites_par_caisse"), "nb_cartes": len(p["cartes"]),
                    "nb_sous_ensembles": len(p.get("sous_ensembles") or []),
                    "recrues_par_boite": round(recrues, 1), "hits_par_boite": round(hits, 2),
                    "cotes_manquantes": len(etat_cotes(p)["manquantes"]), "complete": etat_cotes(p)["complete"],
                    "cotes_estimees": len(p.get("_estimees") or []),
                    "preliminaire": any("preliminaire" in str(n).lower() for n in (p.get("notes") or [])[:1])})
    out.sort(key=lambda x: str(x.get("sortie") or ""), reverse=True)
    return out


_RE_DEUX = re.compile(r"\s*/\s*")


def cartes_attendues(prod, boites):
    """[(carte, sous_ensemble, exemplaires attendus dans `boites` boites)] -
    une ligne par carte de chaque sous-ensemble qui a un taux connu (les
    paralleles reprennent la liste de leur sous-ensemble parent)."""
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    out = []
    for nom, t in prod["_taux"].items():
        if nom not in se or t <= 0:
            continue
        liste_c = _liste_de(prod, se, nom)
        if not liste_c:
            continue
        # 26 oct 2026 (Mathieu : « valide ta methodologie ») : dans un meme sous-ensemble, une carte /99 sort 3 fois
        # moins qu'une /299 : chaque carte pese son tirage (exemplaires imprimes), pas 1. Tirages tous pareils (ou
        # inconnus) : poids egaux, comme avant.
        poids = poids_cartes(se[nom], liste_c) if prod["_par_se"].get(nom) else [1.0] * len(liste_c)
        tot = sum(poids) or 1.0
        for c, w in zip(liste_c, poids):
            out.append((c, se[nom], t * float(boites) * w / tot))
    return out


def poids_cartes(s, liste_c):
    """Poids de tirage de chaque carte d'un sous-ensemble (proportionnel au nombre d'exemplaires imprimes).
    Carte non numerotee dans un sous-ensemble ou d'autres le sont : au moins 100 et au moins le plus gros tirage connu."""
    tirs = [c.get("tirage") or s.get("tirage") for c in liste_c]
    connus = [float(x) for x in tirs if x]
    # 31 oct 2026 (Stature 2025-26 : McDavid, Gretzky, Bedard... « SSP » dans les autos) : une carte marquee SP sort environ
    # 2,5 fois moins que les autres du meme sous-ensemble, une SSP environ 7 fois moins (estimation : Upper Deck ne publie
    # pas le ratio). Sans marque : 1.
    rare = [SP_POIDS.get(str(c.get("sp") or "").upper(), 1.0) for c in liste_c]
    if not connus or len(set(connus)) == 1 and len(connus) == len(tirs):
        return rare
    defaut = max(100.0, max(connus))
    return [(float(x) if x else defaut) * r for x, r in zip(tirs, rare)]


SP_POIDS = {"SP": 0.4, "SSP": 0.15}


def joueurs(prod):
    return sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("joueur")})
