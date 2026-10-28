"""
SLABCOACH - verification d'un certificat PSA (27 oct 2026, Mathieu : « ajoute l'info de l'API de PSA publique si c'est autorise »).

PSA Public API (api.psacard.com/publicapi, jeton Bearer obtenu avec un compte PSA) :
  GET /cert/GetByCertNumber/{cert}  ->  PSACert : annee, marque, joueur, numero, variante, note, population.
Regles qu'on s'impose, en attendant de relire l'entente d'utilisation de l'API de PSA (« PSA API End User Agreement »,
visible une fois connecte sur psacard.com) :
  - eteint tant que PSA_JETON n'est pas dans Render (et PSA_ACTIF=0 le coupe en tout temps) ;
  - une verification = un certificat, a la demande du vendeur (jamais en lot, jamais en tache de fond) ;
  - au plus PSA_QUOTA appels par jour pour tout le serveur (90 par defaut), resultat garde 30 jours ;
  - on montre les donnees dans l'app avec le lien officiel du certificat ; pas de logo PSA, rien n'est copie dans l'annonce.
27 oct 2026 (Mathieu : « utilise l'API PSA pour nos calculs de tendances et de popularite ») :
  chaque certificat verifie fait connaitre sa fiche PSA (SpecID : annee, marque, variante, numero, joueur). Avec
  PSA_TENDANCES=1, une fois par jour, on relit la population de ces fiches (GET /pop/GetPSASpecPopulation/{SpecID}),
  au plus PSA_QUOTA_TENDANCES appels (20 par defaut, en gardant 40 appels pour les vendeurs). De la, pour les tendances :
  population PSA 10, taux de gem, nouvelles gradations sur 30 jours (la demande des collectionneurs et l'offre a venir).
"""
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request

BASE = "https://api.psacard.com/publicapi"
GARDE_S = 30 * 86400
_verrou = threading.Lock()


def actif():
    """28 oct 2026 - l'entente d'utilisation de l'API de PSA (End-User License Agreement, lue par Mathieu) interdit de rendre
    les donnees disponibles a des tiers, d'en faire des oeuvres derivees ou de les utiliser dans un logiciel par abonnement.
    SlabCoach etant une app par abonnement pour d'autres vendeurs, l'API reste COUPEE tant qu'une entente commerciale ecrite
    avec Collectors Universe n'est pas signee (PSA_LICENCE=1 dans Render, seulement apres la signature)."""
    return (bool(os.environ.get("PSA_JETON", "").strip()) and os.environ.get("PSA_LICENCE", "") == "1"
            and os.environ.get("PSA_ACTIF", "1") != "0")


def _quota():
    try:
        return max(1, int(os.environ.get("PSA_QUOTA") or 90))
    except ValueError:
        return 90


def _chemin():
    d = os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, "psa_cache.json")


def _lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def _get(chemin):
    req = urllib.request.Request(BASE + chemin, headers={"Authorization": "bearer " + os.environ.get("PSA_JETON", "").strip(),
                                                         "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            brut = r.read()
            return r.status, (json.loads(brut) if brut else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, None


def _titre(s):
    """« MACKLIN CELEBRINI » -> « Macklin Celebrini » ; garde les sigles courts (RC, SP, UD)."""
    mots = []
    for m in str(s or "").split():
        mots.append(m if len(m) <= 2 and m.isupper() else m[:1].upper() + m[1:].lower())
    return " ".join(mots)


def note(carte_grade):
    """« GEM MT 10 » -> « 10 » ; « NM-MT 8.5 » -> « 8.5 » ; « AUTHENTIC » -> None."""
    m = re.search(r"(\d{1,2}(?:\.5)?)\s*$", str(carte_grade or "").strip())
    return m.group(1) if m else None


def _analyser(cert, c):
    n = note(c.get("CardGrade"))
    return {"ok": True, "cert": cert, "source": "PSA", "lien": f"https://www.psacard.com/cert/{cert}",
            "annee": str(c.get("Year") or "").strip() or None, "marque": _titre(c.get("Brand")) or None,
            "joueur": _titre(c.get("Subject")) or None, "numero": str(c.get("CardNumber") or "").strip() or None,
            "variante": _titre(c.get("Variety")) or None, "categorie": _titre(c.get("Category")) or None,
            "grade": ("PSA " + n) if n else None, "grade_texte": c.get("GradeDescription") or c.get("CardGrade"),
            "auto_grade": c.get("AutographGrade") or None,
            "pop": c.get("TotalPopulation"), "pop_plus_haute": c.get("PopulationHigher"), "spec_id": c.get("SpecID"),
            "double": bool(c.get("IsDualCert")), "statut": c.get("ItemStatus")}


def verifier(cert):
    """Un certificat PSA -> ce que PSA en dit (ou {ok: False, erreur})."""
    cert = re.sub(r"\D", "", str(cert or ""))
    if not 6 <= len(cert) <= 10:
        return {"ok": False, "erreur": "Numéro de certificat PSA : 6 à 10 chiffres (sur l'étiquette)"}
    if not actif():
        return {"ok": False, "erreur": "La vérification PSA n'est pas encore activée", "inactif": True}
    with _verrou:
        d = _lire()
        g = (d.get("certs") or {}).get(cert)
        if g and time.time() - g.get("le", 0) < GARDE_S:
            return {**g["r"], "garde": True}
        jour = time.strftime("%Y-%m-%d")
        if d.get("jour") != jour:
            d["jour"], d["n"] = jour, 0
        if d.get("n", 0) >= _quota():
            return {"ok": False, "erreur": "Vérifications PSA du jour épuisées : réessaie demain"}
        d["n"] = d.get("n", 0) + 1
        _ecrire(d)
    st, r = _get(f"/cert/GetByCertNumber/{cert}")
    if st in (401, 403, 500) and not r:
        return {"ok": False, "erreur": "PSA ne répond pas pour l'instant (jeton à vérifier)"}
    if st == 0:
        return {"ok": False, "erreur": "PSA ne répond pas : réessaie dans un instant"}
    c = (r or {}).get("PSACert") if isinstance(r, dict) else None
    if st == 204 or not c or not c.get("CertNumber"):
        msg = str((r or {}).get("ServerMessage") or "") if isinstance(r, dict) else ""
        return {"ok": False, "erreur": "Certificat introuvable chez PSA" + (f" ({msg})" if msg and "No data" not in msg else "")}
    res = _analyser(cert, c)
    with _verrou:
        d = _lire()
        certs = d.setdefault("certs", {})
        certs[cert] = {"le": time.time(), "r": res}
        if res.get("spec_id"):                    # la fiche de la carte, pour les tendances (aucune donnee personnelle)
            d.setdefault("specs", {})[str(res["spec_id"])] = {k: res.get(k) for k in ("joueur", "annee", "marque", "variante", "numero")}
        if len(certs) > 5000:                     # garde les plus recents
            for k in sorted(certs, key=lambda k: certs[k].get("le", 0))[:len(certs) - 5000]:
                certs.pop(k, None)
        _ecrire(d)
    return res


# ---------------------------------------------------------------------------------------------------------------
# Population PSA des fiches connues -> signaux de tendance et de popularite
# ---------------------------------------------------------------------------------------------------------------
def tendances_actives():
    return actif() and os.environ.get("PSA_TENDANCES", "") == "1"


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def population(spec_id):
    """Relit la population d'une fiche (un appel), garde une photo par jour. -> derniere photo ou None."""
    spec = str(spec_id)
    with _verrou:
        d = _lire()
        jour = time.strftime("%Y-%m-%d")
        if d.get("jour") != jour:
            d["jour"], d["n"] = jour, 0
        if d.get("n", 0) >= _quota():
            return None
        d["n"] = d.get("n", 0) + 1
        _ecrire(d)
    st, r = _get(f"/pop/GetPSASpecPopulation/{spec}")
    pop = (r or {}).get("PSAPop") if isinstance(r, dict) else None
    if st != 200 or not isinstance(pop, dict):
        return None
    g = lambda k: int(pop.get(k) or 0)
    photo = [time.strftime("%Y-%m-%d"), g("Total"), g("Grade10"), g("Grade9")]
    with _verrou:
        d = _lire()
        p = d.setdefault("pops", {}).setdefault(spec, {"hist": []})
        h = [x for x in p["hist"] if x[0] != photo[0]] + [photo]
        p["hist"], p["le"] = h[-40:], time.time()
        if r.get("Description"):
            p["desc"] = str(r["Description"])[:120]
        _ecrire(d)
    return photo


def rafraichir_si_besoin():
    """Une fois par jour (appele chaque heure par le serveur) : les fiches les moins fraiches d'abord."""
    if not tendances_actives():
        return 0
    d = _lire()
    if time.time() - d.get("pop_tour", 0) < 20 * 3600:
        return 0
    try:
        budget = max(0, int(os.environ.get("PSA_QUOTA_TENDANCES") or 20))
    except ValueError:
        budget = 20
    reste = _quota() - (d.get("n", 0) if d.get("jour") == time.strftime("%Y-%m-%d") else 0) - 40
    budget = min(budget, max(0, reste))
    pops = d.get("pops") or {}
    specs = sorted((d.get("specs") or {}).keys(), key=lambda k: (pops.get(k) or {}).get("le", 0))[:budget]
    n = sum(1 for k in specs if population(k))
    d = _lire()
    d["pop_tour"] = time.time()
    _ecrire(d)
    return n


def stats(spec):
    """Population PSA 10, taux de gem, nouvelles gradations en 30 jours (et en %) d'une fiche."""
    p = (_lire().get("pops") or {}).get(str(spec)) or {}
    h = p.get("hist") or []
    if not h:
        return None
    jour, tot, g10, g9 = h[-1]
    out = {"pop": tot, "pop10": g10, "pop9": g9, "gem_pct": round(100 * g10 / tot) if tot else None, "le": jour}
    import datetime as _dt
    d0 = _dt.date.fromisoformat(jour)
    vieux = [x for x in h if (d0 - _dt.date.fromisoformat(x[0])).days >= 25]
    if vieux:
        a = vieux[-1]
        out["nouvelles_30j"] = tot - a[1]
        out["croissance_pct"] = round(100 * (tot - a[1]) / a[1], 1) if a[1] else None
    return out


def _index():
    idx = {}
    for spec, f in (_lire().get("specs") or {}).items():
        a = re.match(r"(19|20)\d{2}", str(f.get("annee") or ""))
        if f.get("joueur") and a:
            idx.setdefault((_norm(f["joueur"]), a.group(0)), []).append((spec, _norm(f.get("variante"))))
    return idx


def enrichir(items, idx=None):
    """Ajoute x["psa"] (population, gem, croissance, signal) aux cartes des tendances dont on connait la fiche PSA.
    Une carte = meme joueur, meme annee, et la variante PSA (« Young Guns ») dans le nom de la carte."""
    if idx is None:
        idx = _index()
    if not idx:
        return items
    for x in items or []:
        a = re.match(r"(19|20)\d{2}", str(x.get("produit") or x.get("annee") or ""))
        cands = idx.get((_norm(x.get("joueur")), a.group(0) if a else ""))
        if not cands:
            continue
        carte = _norm(x.get("carte"))
        spec = next((sp for sp, v in cands if v and (v in carte or carte in v)), None)
        if not spec:
            continue
        st = stats(spec)
        if not st:
            continue
        pct = x.get("pct")
        c = st.get("croissance_pct")
        if c is not None and pct is not None:
            st["signal"] = "rare" if c < 3 and pct > 0 else "offre" if c > 15 and pct < 0 else "demande" if c > 15 and pct > 0 else None
        x["psa"] = st
    return items


def stats_toutes():
    """Les stats de toutes les fiches suivies (pour l'indice du marche)."""
    return [x for x in (stats(k) for k in ((_lire().get("pops") or {}).keys())) if x]
