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
    return taux


_RE_SANS_HOBBY = re.compile(r"absent|retail|hanger|blaster|advent|mega|tin\b|dollar|starter|oversized|walmart|target|amazon", re.I)
_RE_HOBBY = re.compile(r"\bh\b|hobby|e-?pack", re.I)


def etat_cotes(prod):
    """26 oct 2026 (Mathieu : « une fleche verte lorsque nous avons la checklist avec tous les odds calcules ») -
    les sous-ensembles d'une boite HOBBY dont on ne connait pas la chance de sortir (donc absents du calcul).
    Ne comptent pas : plaques d'impression, 1/1, et ce qui ne sort que dans le retail. -> {manquantes: [noms], complete}"""
    taux = prod.get("_taux") or taux_par_boite(prod)
    manq, non_pub = [], []
    for s in prod.get("sous_ensembles") or []:
        if (taux.get(s["nom"]) or 0) > 0 or s.get("par_boite"):
            continue
        if s.get("tirage") == 1 or re.search(r"printing plate|\bplates?\b|1/1|one of one", s["nom"], re.I):
            continue
        txt = str(s.get("cotes") or "")
        if txt and _RE_SANS_HOBBY.search(txt) and not _RE_HOBBY.search(re.sub(r"absent de la bo[iî]te hobby", "", txt, flags=re.I)):
            continue
        if re.search(r"oversized|retail|blaster|hanger|tin\b|mega", s["nom"], re.I):
            continue
        if re.search(r"random", txt, re.I):          # « Random Inserts » : le fabricant ne publie pas la cote
            non_pub.append(s["nom"])
            continue
        manq.append(s["nom"])
    return {"manquantes": manq, "non_publiees": non_pub, "complete": not manq}


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
    if not connus or len(set(connus)) == 1 and len(connus) == len(tirs):
        return [1.0] * len(liste_c)
    defaut = max(100.0, max(connus))
    return [float(x) if x else defaut for x in tirs]


def joueurs(prod):
    return sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("joueur")})
