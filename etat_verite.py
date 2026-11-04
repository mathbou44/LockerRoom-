"""
SLABCOACH - ce que l'analyseur d'etat apprend (1er nov 2026).

Mathieu : « on doit ameliorer notre analyseur IA ; comment s'y prendre pour l'entrainer ? je veux qu'on soit PARFAIT ».
On ne re-entraine pas le modele : on le CALIBRE sur la verite, pour tous les comptes, sans photo ni nom :
  - la vraie note : quand une carte examinee revient du gradage, son estimation et sa vraie note sont gardees ; l'ecart
    median (15 cartes et plus) decale les fourchettes suivantes, et la precision reelle est montree aux utilisateurs ;
  - les avis : chaque defaut signale peut etre confirme ou rejete ; un type de defaut « a verifier » rejete 70 % du temps
    (10 avis et plus) rend la consigne plus exigeante pour ce type.
"""
import json
import os
import re
import statistics
import threading
from datetime import datetime

_verrou = threading.Lock()


def _chemin(nom):
    import comptes
    return os.path.join(comptes.DONNEES, nom)


def _lire(nom, defaut):
    try:
        with open(_chemin(nom), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _ecrire(nom, d):
    ch = _chemin(nom)
    os.makedirs(os.path.dirname(ch), exist_ok=True)
    tmp = ch + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, ch)


# 3 nov 2026 (revue de securite) : ces apprentissages servent a TOUS les comptes. Un seul compte ne doit pas pouvoir les
# fausser (une carte « revenue » en boucle, 10 faux avis d'un coup) : chaque entree porte l'empreinte du compte, un meme
# examen ne compte qu'une fois, chaque compte pese au plus MAX_PAR_COMPTE, et il faut MIN_COMPTES comptes differents.
MIN_COMPTES = 3
MAX_PAR_COMPTE = 5


def _compte():
    import hashlib
    import comptes
    cid = comptes.courant() if comptes.MULTI else "local"
    return hashlib.sha256(("etat-verite:" + str(cid)).encode()).hexdigest()[:12]


def _multi():
    import comptes
    return comptes.MULTI


def _min_comptes():
    return MIN_COMPTES if _multi() else 1          # sur le PC (un seul utilisateur) : ses propres retours suffisent


def _equilibrer(l):
    """Les entrees, au plus MAX_PAR_COMPTE par compte (les plus recentes). -> (entrees, nombre de comptes)"""
    if not _multi():
        return l, 1
    par = {}
    for x in reversed(l):
        par.setdefault(x.get("compte") or "ancien", []).append(x)
    out = [y for v in par.values() for y in v[:MAX_PAR_COMPTE]]
    return out, len(par)


def note_de(grade):
    """« PSA 10 » -> 10.0 ; « BGS 9.5 » -> 9.5 ; « PSA 8 OC » -> 8.0 ; sinon None."""
    m = re.search(r"(?<![\d.])(10|[1-9](?:[.,]5)?)(?![\d.])", str(grade or ""))
    return float(m.group(1).replace(",", ".")) if m else None


def noter(etat_json, grade, compagnie=None, sous_notes=None):
    """Une carte examinee revient du gradage : on garde l'estimation et la vraie note (et les sous-notes TAG / BGS si
    donnees : 3 nov 2026, elles disent QUELLE categorie l'analyseur surestime)."""
    try:
        e = json.loads(etat_json or "null") if isinstance(etat_json, str) else etat_json
    except ValueError:
        e = None
    reel = note_de(grade)
    if not e or reel is None or e.get("note_min") is None:
        return False
    import hashlib
    emp = hashlib.sha256(json.dumps([e.get("photos"), e.get("note_min"), e.get("note_max")], default=str).encode()).hexdigest()[:16] \
        if e.get("photos") else None
    with _verrou:
        l = [x for x in _lire("etat_verite.json", []) if not emp or x.get("emp") != emp]     # le meme examen : une seule fois
        l.append({"le": datetime.now().strftime("%Y-%m-%d"), "cie": str(compagnie or "")[:10], "lo": e.get("note_min"), "hi": e.get("note_max"),
                  "reel": reel, "notes": e.get("notes"), "zooms": bool(e.get("zooms")), "examen": bool(e.get("examen")),
                  "sous": _sous(sous_notes), "compte": _compte(), "emp": emp})
        _ecrire("etat_verite.json", l[-5000:])
    return True


def _sous(d):
    out = {}
    for k in ("centrage", "coins", "bords", "surface"):
        try:
            v = float(str((d or {}).get(k)).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 10:
            out[k] = v
    return out or None


def ecarts_sous():
    """Par categorie : l'ecart median (vraie sous-note - sous-note estimee), 8 cartes et plus. -> {categorie: (n, ecart)}"""
    par = {}
    l_, nc = _equilibrer(_lire("etat_verite.json", []))
    if nc < _min_comptes():
        return {}
    for x in l_:
        for k, v in (x.get("sous") or {}).items():
            est = (x.get("notes") or {}).get(k)
            if isinstance(est, (int, float)):
                par.setdefault(k, []).append(v - est)
    return {k: (len(l), round(statistics.median(l) * 2) / 2) for k, l in par.items() if len(l) >= 8}


def calibration():
    """L'ecart median (vraie note - milieu de la fourchette) sur les cartes revenues, PSA seulement (son echelle)."""
    l = [x for x in _lire("etat_verite.json", []) if (x.get("cie") or "PSA").upper() == "PSA" and x.get("lo") is not None]
    l, nc = _equilibrer(l)
    if not l or nc < _min_comptes():
        return {"n": 0}
    ec = [x["reel"] - (x["lo"] + (x.get("hi") or x["lo"])) / 2 for x in l]
    return {"n": len(l), "ecart": round(statistics.median(ec) * 2) / 2}


def precision():
    """Pour l'ecran : combien de cartes verifiees, et combien tombaient dans la fourchette (ou a un demi-point)."""
    l = [x for x in _lire("etat_verite.json", []) if x.get("lo") is not None]
    l, nc = _equilibrer(l)
    if len(l) < 10 or nc < _min_comptes():
        return None
    dans = sum(1 for x in l if x["lo"] - 0.5 <= x["reel"] <= (x.get("hi") or x["lo"]) + 0.5)
    return {"n": len(l), "pct": round(100 * dans / len(l))}


def _cle(d):
    z = str(d.get("zone") or "")
    cat = "coins" if z.startswith("coin") else "bords" if z.startswith("bord") else z
    return f"{cat}|{d.get('type')}|{d.get('gravite')}"


def avis(defaut, avant, apres):
    """Un avis sur un defaut (vrai / faux / retire) ; avant : l'avis precedent du meme defaut (pour ne pas compter deux fois)."""
    k = _cle(defaut)
    with _verrou:
        d = _lire("etat_avis.json", {})
        x = d.get(k)
        if isinstance(x, list):                    # l'ancien format [oui, non] : garde comme un seul « ancien » compte
            x = {"comptes": {"ancien": x}}
        x = x or {"comptes": {}}
        h = _compte()
        oui, non = x["comptes"].get(h, [0, 0])
        if avant is True:
            oui -= 1
        elif avant is False:
            non -= 1
        if apres is True:
            oui += 1
        elif apres is False:
            non += 1
        x["comptes"][h] = [max(0, oui), max(0, non)]
        d[k] = x
        _ecrire("etat_avis.json", d)


_LIB = {"coins": "coins", "bords": "bords", "surface": "surface"}


def regles():
    """Les consignes apprises des avis : un type de defaut souvent rejete devient plus exigeant."""
    out = []
    def total(x):                                  # chaque compte pese au plus MAX_PAR_COMPTE avis par type de defaut
        if isinstance(x, list):
            x = {"comptes": {"ancien": x}}
        cs = (x or {}).get("comptes") or {}
        cap = MAX_PAR_COMPTE if _multi() else 10 ** 6
        return (sum(min(cap, v[0]) for v in cs.values()), sum(min(cap, v[1]) for v in cs.values()),
                sum(1 for v in cs.values() if v[0] or v[1]))
    tots = {k: total(x) for k, x in _lire("etat_avis.json", {}).items()}
    for k, (oui, non, nc) in sorted(tots.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        t = oui + non
        if t >= 10 and non / t >= 0.7 and nc >= _min_comptes():
            cat, typ, grav = k.split("|")
            out.append(f"Appris des utilisateurs : {round(100 * non / t)} % des « {typ} » ({grav}) signales sur les {_LIB.get(cat, cat)} etaient "
                       f"faux : signale-le seulement si le zoom le montre clairement.")
    for k, (n, ec) in ecarts_sous().items():       # 3 nov 2026 : les sous-notes revenues (TAG, BGS)
        if ec <= -1:
            out.append(f"Appris de {n} cartes revenues avec sous-notes : la sous-note {_LIB.get(k, k)} etait estimee {abs(ec):g} point trop haute "
                       f"en mediane : sois plus severe sur les {_LIB.get(k, k)} (cherche les petits defauts).")
        elif ec >= 1:
            out.append(f"Appris de {n} cartes revenues avec sous-notes : la sous-note {_LIB.get(k, k)} etait estimee {ec:g} point trop basse "
                       f"en mediane : ne compte pas ce que le zoom ne montre pas clairement.")
    return out[:6]
