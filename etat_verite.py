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


def note_de(grade):
    """« PSA 10 » -> 10.0 ; « BGS 9.5 » -> 9.5 ; « PSA 8 OC » -> 8.0 ; sinon None."""
    m = re.search(r"(?<![\d.])(10|[1-9](?:[.,]5)?)(?![\d.])", str(grade or ""))
    return float(m.group(1).replace(",", ".")) if m else None


def noter(etat_json, grade, compagnie=None):
    """Une carte examinee revient du gradage : on garde l'estimation et la vraie note."""
    try:
        e = json.loads(etat_json or "null") if isinstance(etat_json, str) else etat_json
    except ValueError:
        e = None
    reel = note_de(grade)
    if not e or reel is None or e.get("note_min") is None:
        return False
    with _verrou:
        l = _lire("etat_verite.json", [])
        l.append({"le": datetime.now().strftime("%Y-%m-%d"), "cie": str(compagnie or "")[:10], "lo": e.get("note_min"), "hi": e.get("note_max"),
                  "reel": reel, "notes": e.get("notes"), "zooms": bool(e.get("zooms")), "examen": bool(e.get("examen"))})
        _ecrire("etat_verite.json", l[-5000:])
    return True


def calibration():
    """L'ecart median (vraie note - milieu de la fourchette) sur les cartes revenues, PSA seulement (son echelle)."""
    l = [x for x in _lire("etat_verite.json", []) if (x.get("cie") or "PSA").upper() == "PSA" and x.get("lo") is not None]
    if not l:
        return {"n": 0}
    ec = [x["reel"] - (x["lo"] + (x.get("hi") or x["lo"])) / 2 for x in l]
    return {"n": len(l), "ecart": round(statistics.median(ec) * 2) / 2}


def precision():
    """Pour l'ecran : combien de cartes verifiees, et combien tombaient dans la fourchette (ou a un demi-point)."""
    l = [x for x in _lire("etat_verite.json", []) if x.get("lo") is not None]
    if len(l) < 10:
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
        oui, non = d.get(k, [0, 0])
        if avant is True:
            oui -= 1
        elif avant is False:
            non -= 1
        if apres is True:
            oui += 1
        elif apres is False:
            non += 1
        d[k] = [max(0, oui), max(0, non)]
        _ecrire("etat_avis.json", d)


_LIB = {"coins": "coins", "bords": "bords", "surface": "surface"}


def regles():
    """Les consignes apprises des avis : un type de defaut souvent rejete devient plus exigeant."""
    out = []
    for k, (oui, non) in sorted(_lire("etat_avis.json", {}).items(), key=lambda kv: -sum(kv[1])):
        t = oui + non
        if t >= 10 and non / t >= 0.7:
            cat, typ, grav = k.split("|")
            out.append(f"Appris des utilisateurs : {round(100 * non / t)} % des « {typ} » ({grav}) signales sur les {_LIB.get(cat, cat)} etaient "
                       f"faux : signale-le seulement si le zoom le montre clairement.")
    return out[:4]
