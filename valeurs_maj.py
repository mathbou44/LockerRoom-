"""
LOCKERROOM - mise a jour de valeurs_joueurs.json (« l'algo SlabCoach »).

1. Demande de chaque joueur : modele de pointage de Hall of Cardz
   (pointage_modele.json, cle "demande" : combien les cartes du joueur se
   vendent par rapport a une carte equivalente, mesure sur ~80 000 ventes).
2. Valeur de chaque sous-ensemble de chaque produit du catalogue, pour un
   joueur a 1,0 : mediane de (prix de vente / demande du joueur) sur les
   vraies ventes de CETTE carte (meme saison, meme produit, memes mots,
   meme numerotation, carte brute, un seul exemplaire).

Lecture seule de la source (copie temporaire des bases) : aucune cle,
aucun reseau. Prototype : la source est le dossier de Hall of Cardz sur ce
PC ; version publique : ce fichier est produit sur notre serveur et
telecharge par l'app.

    python valeurs_maj.py ["C:\\chemin\\vers\\INVENTORY ANALYSIS"]
"""
import json
import os
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
from datetime import datetime, timedelta

import catalogue
import valeurs

DOSSIER = os.path.dirname(os.path.abspath(__file__))
MIN_VENTES = 4
JOURS_MAX = 730

_RE_GRADEE = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|gma|csg|hga)\s*-?\s*\d", re.I)
_RE_LOT = re.compile(r"\blots?\b|\bx\s?[2-9]\b|\(\s*[2-9]\s*\)|\bset of\b|\bbreak\b|\bspot\b|\bpick your\b|\bcase\b|"
                     r"\bbox\b|\bpacks?\b|\breprint\b|\bcustom\b|\bcomplete\b|\bteam set\b|\byou pick\b|\bchoose\b", re.I)
_RE_SERIE = re.compile(r"(?<![\d-])/\s*0*(\d{1,4})\b")
_MOTS_VIDES = {"ud", "upper", "deck", "the", "and", "of", "base", "set", "parallel", "parallels", "variation",
               "variations", "card", "cards", "insert", "inserts", "edition", "series", "hockey"}
_SYN = {
    "auto": r"autos?|autograph(?:s|ed)?|signed|signatures?",
    "autos": r"autos?|autograph(?:s|ed)?|signed|signatures?",
    "autograph": r"autos?|autograph(?:s|ed)?|signed|signatures?",
    "autographs": r"autos?|autograph(?:s|ed)?|signed|signatures?",
    "rookie": r"rookies?|rc",
    "rookies": r"rookies?|rc",
    "patch": r"patch(?:es)?|rpa",
    "patches": r"patch(?:es)?|rpa",
    "young": r"young|yg",
    "guns": r"guns|yg",
    "jersey": r"jerseys?|sweaters?|relics?",
    "jerseys": r"jerseys?|sweaters?|relics?",
}
# mots d'un AUTRE produit : une vente qui les porte n'est pas de ce produit
_AUTRES_PRODUITS = {
    "series": ["sp authentic", "the cup", "ultimate", "game used", "artifacts", "mvp", "o pee chee", "opc", "ice",
               "black diamond", "synergy", "allure", "premier", "trilogy", "chronology", "credentials", "spx",
               "fleer", "stature", "metal", "skybox", "parkhurst", "tim hortons", "engrained"],
}
_PRODUITS_MOTS = {
    "sp-authentic": [r"sp\s*authentic", r"\bspa\b"], "the-cup": [r"the\s*cup"], "ultimate-collection": [r"ultimate"],
    "sp-game-used": [r"game\s*used", r"\bspgu\b"],
}


def _norm(t):
    return valeurs.norm_nom(t)


def _jetons(nom):
    t = _norm(nom.replace("&", " and "))
    t = t.replace("black and white", "black white")
    return [m for m in t.split() if m not in _MOTS_VIDES and len(m) >= 2]


def _rx_jeton(m):
    return re.compile(r"\b(?:" + _SYN.get(m, re.escape(m)) + r")\b")


def _saison_rx(saison):
    a = int(str(saison)[:4])
    b = (a + 1) % 100
    return re.compile(rf"\b(?:{a}\s*[-/]\s*{b:02d}|{a % 100:02d}\s*[-/]\s*{b:02d}|{a})\b")


def _ventes(source=None):
    """[(titre normalise, titre brut, prix $ CA)] des ventes de hockey des 2 dernieres annees.
    27 oct 2026 - revue legale : SEULEMENT les ventes SoldComps gardees par base_ventes (licence commerciale de
    SoldComps) ; plus rien de Hall of Cardz (cache 130point lu avec Scrapfly, archive TCA)."""
    import base_ventes
    limite = (datetime.now() - timedelta(days=JOURS_MAX)).strftime("%Y-%m-%d")
    out, vus = [], set()
    try:
        with base_ventes._verrou:
            c = base_ventes._cx()
            try:
                lignes = c.execute("SELECT cle, titre, prix, le FROM ventes WHERE le >= ?", (limite,)).fetchall()
            finally:
                c.close()
    except sqlite3.Error:
        lignes = []
    for cle, titre, prix, le in lignes:
        if not titre or not prix or cle in vus:
            continue
        vus.add(cle)
        p = float(prix)
        if p <= 0 or _RE_GRADEE.search(titre) or _RE_LOT.search(titre):
            continue
        out.append((" " + _norm(titre) + " ", titre, p))
    return out


def _demande(ventes):
    """Demande de chaque joueur, mesuree sur les memes ventes SoldComps : pour chaque sous-ensemble assez vendu,
    (mediane des ventes du joueur) / (mediane de tout le sous-ensemble) ; moyenne geometrique, ramenee vers 1,0
    quand le joueur a peu de ventes. 1,0 = un joueur moyen."""
    import math
    uns = {}
    for p in catalogue.liste():
        prod = catalogue.charger(p["id"])
        for nom, prix_joueurs in _ventes_par_joueur(prod, ventes).items():
            tous = [x for l in prix_joueurs.values() for x in l]
            if len(tous) < MIN_VENTES * 2 or len(prix_joueurs) < 3:
                continue
            m = statistics.median(tous)
            for j, l in prix_joueurs.items():
                uns.setdefault(j, []).append((math.log(max(0.02, statistics.median(l) / m)), len(l)))
    out = {}
    for j, l in uns.items():
        n = sum(k for _, k in l)
        moy = sum(v * k for v, k in l) / n
        out[j] = round(math.exp(moy * n / (n + 3)), 3)           # peu de ventes : on reste pres de 1,0
    return out, len(ventes)


def _ventes_par_joueur(prod, ventes):
    """{sous_ensemble: {joueur normalise: [prix]}} : la meme selection que mesurer_produit, joueur a 1,0."""
    noms_tous = {}
    for c in prod.get("cartes") or []:
        jn = str(c.get("joueur") or "")
        if "/" not in jn and len(_norm(jn).split()) >= 2:
            noms_tous[_norm(jn)] = jn
    r = mesurer_produit(prod, ventes, {v: 1.0 for v in noms_tous.values()}, detail=True)
    return {se: {noms_tous.get(j, j): l for j, l in d.items()} for se, d in r.items()}


def mesurer_produit(prod, ventes, demande, detail=False):
    """{sous_ensemble: {"valeur", "n"}} pour les sous-ensembles assez vendus
    (detail=True : {sous_ensemble: {joueur: [prix bruts]}} pour mesurer la demande)."""
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    rx_saison = _saison_rx(prod.get("saison") or prod["id"][:4])
    suffixe = prod["id"].split("-", 2)[-1] if prod["id"].count("-") >= 2 else prod["id"]
    produit_rx = next((rxs for k, rxs in _PRODUITS_MOTS.items() if suffixe.endswith(k)), None)
    produit_rx = [re.compile(r) for r in produit_rx] if produit_rx else None
    autres = [] if produit_rx else [re.compile(r"\b" + re.escape(m) + r"\b") for m in _AUTRES_PRODUITS["series"]]
    norm_demande = {_norm(k): v for k, v in demande.items()}
    jetons = {n: _jetons(n) for n in se}
    # ventes de la bonne saison et du bon produit, une seule fois
    candidates = []
    for tn, tb, p in ventes:
        if not rx_saison.search(tn) and not rx_saison.search(tb.lower()):
            continue
        if produit_rx and not any(r.search(tn) for r in produit_rx):
            continue
        if autres and any(r.search(tn) for r in autres):
            continue
        candidates.append((tn, tb, p))
    out, det = {}, {}
    for nom, s in se.items():
        j = jetons[nom]
        if not j:
            continue                                    # « Base » : valeur par defaut
        req = [_rx_jeton(m) for m in j]
        excl = set()
        for autre, ja in jetons.items():
            if autre != nom and set(j) <= set(ja):
                excl |= set(ja) - set(j)
        excl_rx = [_rx_jeton(m) for m in excl]
        cartes = catalogue._liste_de(prod, se, nom)
        noms = {}
        for c in cartes:
            jn = str(c.get("joueur") or "")
            if "/" in jn:
                continue
            k = _norm(jn)
            if k in norm_demande and len(k.split()) >= 2:
                noms[k] = norm_demande[k]
        if not noms:
            continue
        tirage = s.get("tirage")
        vals = []
        for tn, tb, p in candidates:
            if any(not r.search(tn) for r in req) or any(r.search(tn) for r in excl_rx):
                continue
            series = [int(x) for x in _RE_SERIE.findall(tb)]
            if tirage and int(tirage) not in series:
                continue
            if not tirage and series:
                continue
            joueur = next((k for k in noms if f" {k} " in tn), None)
            if not joueur:
                continue
            vals.append(p / max(0.05, noms[joueur]))
            det.setdefault(nom, {}).setdefault(joueur, []).append(p)
        if len(vals) >= MIN_VENTES:
            out[nom] = {"valeur": round(statistics.median(vals), 2), "n": len(vals)}
    return det if detail else out


MIN_JOUEURS = int(os.environ.get("LR_VALEURS_MIN_JOUEURS") or 40)


def construire(source=None, forcer=False):
    """Recalcule les valeurs depuis les ventes SoldComps. Tant que la base est trop mince (moins de MIN_JOUEURS
    joueurs mesures), on n'ecrit rien : les valeurs deja la restent."""
    ventes = _ventes()
    demande, nb = _demande(ventes)
    if len(demande) < MIN_JOUEURS and not forcer:
        return {"ok": False, "erreur": f"Pas encore assez de ventes SoldComps ({len(demande)} joueurs mesurés)",
                "joueurs": len(demande), "ventes": len(ventes)}
    mesures = {}
    for p in catalogue.liste():
        prod = catalogue.charger(p["id"])
        mesures[p["id"]] = mesurer_produit(prod, ventes, demande)
    data = {"maj": datetime.now().isoformat(timespec="seconds"), "source": "SoldComps (ventes eBay réelles)",
            "nb_ventes": len(ventes), "nb_ventes_modele": nb,
            "joueurs": {k: round(v, 3) for k, v in sorted(demande.items())}, "sous_ensembles": mesures}
    chemin = valeurs.chemin_ecriture()
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, chemin)
    return {"ok": True, "joueurs": len(demande), "ventes": len(ventes),
            "mesures": {k: len(v) for k, v in mesures.items()}}


if __name__ == "__main__":
    print(json.dumps(construire(forcer="--forcer" in sys.argv), ensure_ascii=False, indent=1))
