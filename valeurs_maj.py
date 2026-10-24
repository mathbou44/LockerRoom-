"""
LOCKERROOM - mise a jour de valeurs_joueurs.json (« l'algo LockerRoom »).

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
SOURCE_DEFAUT = os.path.join(os.path.dirname(DOSSIER), "INVENTORY ANALYSIS")
TAUX_USD_CAD = 1.38
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


def _copier_base(chemin):
    if not os.path.exists(chemin):
        return None
    d = tempfile.mkdtemp(prefix="lr_valeurs_")
    for suf in ("", "-wal", "-shm"):
        if os.path.exists(chemin + suf):
            shutil.copy2(chemin + suf, os.path.join(d, os.path.basename(chemin) + suf))
    return os.path.join(d, os.path.basename(chemin))


def _ventes(source):
    """[(titre normalise, titre brut, prix $ CA)] des ventes de hockey des 2 dernieres annees."""
    limite = (datetime.now() - timedelta(days=JOURS_MAX)).strftime("%Y-%m-%d")
    out, vus = [], set()

    def ajouter(url, titre, prix, devise, date):
        if not titre or not prix or (date and str(date)[:10] < limite):
            return
        cle = url or (titre, prix, date)
        if cle in vus:
            return
        vus.add(cle)
        dev = str(devise or "USD").upper()
        if dev not in ("USD", "CAD"):
            return
        p = float(prix) * (TAUX_USD_CAD if dev == "USD" else 1.0)
        if p <= 0 or _RE_GRADEE.search(titre) or _RE_LOT.search(titre):
            return
        out.append((" " + _norm(titre) + " ", titre, p))

    c130 = _copier_base(os.path.join(source, "cache_130point.sqlite"))
    if c130:
        c = sqlite3.connect(c130)
        try:
            for url, titre, prix, devise, date in c.execute("SELECT url, titre, prix, devise, date_vente FROM ventes_vues"):
                ajouter(url, titre, prix, devise, date)
        finally:
            c.close()
    inv = _copier_base(os.path.join(source, "hallofcardz_inventaire.db"))
    if inv:
        c = sqlite3.connect(inv)
        try:
            for url, titre, prix, devise, date in c.execute(
                    "SELECT listing_url, titre, price, currency, sale_date FROM archive_ventes_tca WHERE sport='hockey'"):
                ajouter(url, titre, prix, devise, date)
        except sqlite3.Error:
            pass
        finally:
            c.close()
    return out


def _demande(source):
    with open(os.path.join(source, "pointage_modele.json"), encoding="utf-8") as f:
        m = json.load(f)
    return {nom: float(v["mult"]) for nom, v in (m.get("demande") or {}).items() if v.get("mult")}, m.get("nb_ventes")


def mesurer_produit(prod, ventes, demande):
    """{sous_ensemble: {"valeur", "n"}} pour les sous-ensembles assez vendus."""
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
    out = {}
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
        if len(vals) >= MIN_VENTES:
            out[nom] = {"valeur": round(statistics.median(vals), 2), "n": len(vals)}
    return out


def construire(source=None):
    source = source or SOURCE_DEFAUT
    demande, nb_modele = _demande(source)
    ventes = _ventes(source)
    mesures = {}
    for p in catalogue.liste():
        prod = catalogue.charger(p["id"])
        mesures[p["id"]] = mesurer_produit(prod, ventes, demande)
    data = {"maj": datetime.now().isoformat(timespec="seconds"), "source": "Hall of Cardz (modèle de pointage + ventes)",
            "nb_ventes": len(ventes), "nb_ventes_modele": nb_modele,
            "joueurs": {k: round(v, 3) for k, v in sorted(demande.items())}, "sous_ensembles": mesures}
    tmp = valeurs.CHEMIN + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, valeurs.CHEMIN)
    return {"ok": True, "joueurs": len(demande), "ventes": len(ventes),
            "mesures": {k: len(v) for k, v in mesures.items()}}


if __name__ == "__main__":
    print(json.dumps(construire(sys.argv[1] if len(sys.argv) > 1 else None), ensure_ascii=False, indent=1))
