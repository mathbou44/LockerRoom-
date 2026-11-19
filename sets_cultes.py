"""
SLABCOACH - les sets tres collectionnes et leurs cartes cles (19 nov 2026).

Mathieu : « pour notre clientele de collectionneurs : savoir quel set de quelle annee et quelles cartes de quels joueurs sont
les plus collectionnes ; juste les hautement / tres collectionnes ; je dois comprendre en 1 seconde ».

Une pastille seulement quand la carte est d'un set tres collectionne (« Culte »), et « Carte cle » quand c'est LA carte du set.
Deux sources, rien d'invente :
  1. la liste des forums et des references du hobby : Beckett Hockey (les 7 plus grands sets), la liste TCDB « Must Have Sets
     for Hockey Collectors », Sports Illustrated (le « Mount Rushmore » des cartes LNH), The Hockey News (The Cup, le haut du
     hobby) ;
  2. nos ventes (337 000 ventes, nov 2026) : par set-annee, la demande, la part gradee (on fait grader ce qu'on garde), l'argent
     depense et la tenue de la valeur (meme carte, meme grade, sur des mois). Les Young Guns sortent en tete chaque annee ; les
     cartes cles sortent seules (Celebrini #451, Hughes #201, Kaprizov #451, Bedard #451, McDavid #201, Crosby #201).
Les cartes cles des Young Guns recentes se recalculent chaque semaine sur nos ventes (les 3 joueurs qui font le plus d'argent).
Aucune donnee PSA (pop, Set Registry) : l'entente PSA l'interdit dans une app payante.
"""
import json
import os
import re
import threading
import time

_R = lambda p: re.compile(p, re.I)
OPC = r"\bo-?pee-?chee\b|\bopc\b"
# (annee de depart de la saison, produit, libelle, joueurs cles). an None = toutes les annees.
CULTES = [
    (1951, _R(r"\bparkhurst\b"), "1951-52 Parkhurst", ("gordie howe", "maurice richard")),
    (1953, _R(r"\bparkhurst\b"), "1953-54 Parkhurst", ("jean beliveau",)),
    (1958, _R(r"\btopps\b"), "1958-59 Topps", ("bobby hull",)),
    (1966, _R(r"\btopps\b"), "1966-67 Topps", ("bobby orr",)),
    (1970, _R(OPC), "1970-71 O-Pee-Chee", ("gilbert perreault", "bobby clarke", "darryl sittler")),
    (1971, _R(OPC), "1971-72 O-Pee-Chee", ("ken dryden", "guy lafleur", "marcel dionne")),
    (1972, _R(OPC), "1972-73 O-Pee-Chee", ()),
    (1974, _R(OPC), "1974-75 O-Pee-Chee", ("denis potvin", "lanny mcdonald", "borje salming")),
    (1978, _R(OPC), "1978-79 O-Pee-Chee", ("mike bossy",)),
    (1979, _R(OPC + r"|\btopps\b"), "1979-80 O-Pee-Chee", ("wayne gretzky", "mark messier")),
    (1980, _R(OPC), "1980-81 O-Pee-Chee", ("mark messier", "ray bourque", "paul coffey")),
    (1984, _R(OPC), "1984-85 O-Pee-Chee", ("steve yzerman",)),
    (1985, _R(OPC + r"|\btopps\b"), "1985-86 O-Pee-Chee", ("mario lemieux",)),
    (1986, _R(OPC), "1986-87 O-Pee-Chee", ("patrick roy",)),
    (1990, _R(r"\bpremier\b"), "1990-91 O-Pee-Chee Premier", ("jaromir jagr", "sergei fedorov", "martin brodeur")),
    (None, _R(r"\bthe cup\b"), "The Cup", ()),
]
# les Young Guns les plus collectionnees (nos ventes : score 79 et plus) et leurs cartes cles connues
YG_CULTES = {2005: ("sidney crosby", "alexander ovechkin", "alex ovechkin"), 2013: ("nathan mackinnon",), 2015: ("connor mcdavid", "jack eichel"),
             2016: ("auston matthews", "mitch marner", "patrik laine"), 2018: ("elias pettersson", "rasmus dahlin"),
             2019: ("jack hughes", "cale makar", "quinn hughes"), 2020: ("kirill kaprizov", "alexis lafreniere"),
             2021: ("cole caufield", "lucas raymond"), 2022: ("juraj slafkovsky", "wyatt johnston", "matt boldy"),
             2023: ("connor bedard", "brock faber"), 2024: ("macklin celebrini", "lane hutson")}
AN = re.compile(r"\b(19[5-9]\d|20[0-3]\d)(?:\s*[-/]\s*\d{2,4})?\b")
_MEM = {"t": 0.0, "d": {}}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "sets_cultes.json")


def _appris():
    """Les cartes cles des Young Guns recalculees sur nos ventes ({annee: [joueurs]})."""
    if time.time() - _MEM["t"] > 300:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _MEM["d"] = json.load(f)
        except (OSError, ValueError):
            _MEM["d"] = {}
        _MEM["t"] = time.time()
    return _MEM["d"]


def _norm(s):
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace(".", " ").split())


def _annee(t):
    m = AN.search(t)
    return int(m.group(1)) if m else None


def info(titre, joueur=None):
    """{"set": libelle, "cle": bool} si la carte est d'un set tres collectionne ; sinon None."""
    t = " " + str(titre or "") + " "
    an = _annee(t)
    if not an:
        return None
    j = _norm(joueur)
    tl = _norm(t)
    try:
        import bareme_iq
        so = bareme_iq.sorte(titre)[1]
    except Exception:
        so = ""
    if so in ("yg", "yg10", "yg_variante") and not re.search(r"\brenewed\b|\bretro\b", tl):
        ap = (_appris().get("yg") or {}).get(str(an))
        if an in YG_CULTES or str(an) in (_appris().get("annees") or []):
            cles = set(YG_CULTES.get(an, ())) | set(ap or ())
            return {"set": f"{an}-{str(an + 1)[2:]} Young Guns", "cle": bool(j and j in cles) or any(c in tl for c in cles)}
    for a0, rx, lib, cles in CULTES:
        if (a0 is None or a0 == an) and rx.search(t):
            if a0 is None:                                   # The Cup : la carte cle, c'est la recrue patch auto (RPA)
                return {"set": f"{an}-{str(an + 1)[2:]} {lib}", "cle": so == "cup_rpa"}
            if a0 < 1990 and re.search(r"\breprint\b|\breissue\b|\bheritage\b|\barchives\b|\bbuyback\b|\bcustom\b", tl):
                return None
            return {"set": lib, "cle": bool(j and j in cles) or any(c in tl for c in cles)}
    return None


def recalculer(jours=365):
    """Chaque semaine : les 3 joueurs qui font le plus d'argent dans chaque annee de Young Guns (nos ventes)."""
    import base_ventes
    import bareme_iq
    par = {}
    for j, t, p, le in base_ventes.ventes_titres(jours):
        so = bareme_iq.sorte(t)[1]
        an = _annee(t)
        if not an or so not in ("yg", "yg10", "yg_variante") or re.search(r"renewed|retro", t, re.I):
            continue
        d = par.setdefault(str(an), {})
        d[_norm(j)] = d.get(_norm(j), 0.0) + float(p or 0)
    yg = {an: [k for k, _ in sorted(d.items(), key=lambda x: -x[1])[:3]] for an, d in par.items() if sum(d.values()) >= 5000}
    # une nouvelle annee devient « culte » quand on y depense autant que la mediane des annees cultes connues
    tot = {an: sum(d.values()) for an, d in par.items()}
    ref = sorted(tot.get(str(a), 0.0) for a in YG_CULTES)
    seuil = ref[len(ref) // 2] if ref else float("inf")
    annees = sorted(an for an, v in tot.items() if int(an) not in YG_CULTES and v >= seuil > 0)
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"le": time.time(), "yg": yg, "annees": annees}, f, ensure_ascii=False)
    os.replace(tmp, _chemin())
    _MEM["t"] = 0.0
    return yg


def recalculer_si_besoin():
    d = _appris()
    if time.time() - float(d.get("le") or 0) < 7 * 86400:
        return False
    threading.Thread(target=recalculer, daemon=True, name="sets-cultes").start()
    return True
