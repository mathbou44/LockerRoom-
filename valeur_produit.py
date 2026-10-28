"""
LOCKERROOM - la valeur des cartes d'un produit, mesuree sur les VENTES reelles (25 oct 2026).

Mathieu : « pour la Series 1 2026-27, Boston a James Hagens, il vaut cher, l'equipe se vend donc plus cher
dans un break que Dallas qui n'a pas de bonnes recrues » et « base-toi toujours sur les last sold ».

Pour chaque produit : quelques recherches de ventes (SoldComps, 240 ventes chacune) sur ses sous-ensembles
qui comptent (Young Guns, Canvas Young Guns, autos, patchs...) ; chaque vente est rattachee au joueur de la
checklist (nom de famille + memes mots + meme annee, cartes_match) ; mediane par joueur et par sous-ensemble.
Aussi le prix d'une boite (ventes de boites scellees). Garde 7 jours (DONNEES/valeurs_produits.json).
Budget : environ 4 a 6 recherches par produit et par semaine.
"""
import json
import os
import re
import statistics
import threading
import time
from datetime import datetime

FRAICHEUR_S = 7 * 86400
MAX_SOUS = 5                    # sous-ensembles mesures par produit (les plus importants)
_verrou = threading.Lock()
_EN_COURS = set()


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "valeurs_produits.json")


_CACHE = {"mt": None, "d": {}}


def lire():
    """26 oct 2026 : en memoire tant que le fichier ne change pas (lu des milliers de fois par analyse de break :
    le relire a chaque carte rendait l'ecran tres lent en ligne, jusqu'a l'erreur du serveur)."""
    import time as _t
    if _CACHE.get("vu") and _t.time() - _CACHE["vu"] < 2.0 and _CACHE["mt"] is not None:
        return _CACHE["d"]           # 28 oct 2026 (vitesse) : la date du fichier regardee au plus toutes les 2 s (avant : ~26 000 fois)
    _CACHE["vu"] = _t.time()
    try:
        mt = os.path.getmtime(_chemin())
    except OSError:
        return {}
    if _CACHE["mt"] != mt:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                _CACHE.update(mt=mt, d=json.load(f) or {})
        except (OSError, ValueError):
            return _CACHE["d"]
    return _CACHE["d"]


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


def de(pid):
    """{"maj", "boite", "sous": {nom: {"mediane", "n", "joueurs": {joueur: {"m", "n"}}}}} ou {}."""
    return (lire().get(pid) or {})


def _importants(prod):
    """Les sous-ensembles qui font la valeur d'un break : recrues de base, autos, patchs (les plus frequents d'abord)."""
    se = prod.get("sous_ensembles") or []
    rang = {"recrue": 0, "auto_memo": 1, "auto": 2, "memo": 3, "insert": 5, "base": 6}
    choix = [s for s in se if (s.get("groupe") in ("recrue", "auto", "memo", "auto_memo")) and not s.get("tirage")
             and not re.search(r"printing plate|oversized|1/1", s["nom"], re.I)]
    choix.sort(key=lambda s: (rang.get(s.get("groupe"), 9), -(s.get("par_boite") or 0)))
    return choix[:MAX_SOUS]


def _court(prod):
    """« 2026-27 Upper Deck Series 1 » -> (« 2026-27 », « upper deck »)."""
    saison = str(prod.get("saison") or (re.search(r"(19|20)\d{2}(-\d{2})?", prod.get("nom") or "") or [""])[0])
    marque = str(prod.get("marque") or "").lower()
    return saison, marque


def recrues_du_produit(prod):
    se = {s["nom"]: s for s in prod.get("sous_ensembles") or []}
    return sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("joueur") and "/" not in c["joueur"]
                   and (se.get(c.get("sous_ensemble")) or {}).get("groupe") == "recrue"
                   and not (se.get(c.get("sous_ensemble")) or {}).get("parallele_de")})


def annonces_recrues(prod, chercher=None):
    """26 oct 2026 (Mathieu : « dans les Series 1, 2, Extended, on cherche les rookies : Boston (Hagens) devrait etre
    parmi les plus chers avec Chicago, Philadelphie, Washington ») - une recrue toute neuve n'a encore aucune vente :
    sa cote se lit dans ses cartes deja en vente (prospect, junior, autres produits). Mediane des annonces eBay
    a son nom (API Browse, gratuite) -> {joueur: mediane $ CA}. Seulement les recrues que l'indice ne connait pas."""
    import cartes_match
    import ebay_compte
    import valeurs
    chercher = chercher or (lambda q: ebay_compte.rechercher(q, categorie="261328", limite=50, fond=True))
    out = {}
    for j in recrues_du_produit(prod):
        if valeurs.connu(j):
            continue
        try:
            res = chercher(f"{j} hockey card") or []
        except (RuntimeError, OSError):
            break
        fam = cartes_match.norm(j).split()[-1]
        prix = [round((a.get("prix_cad") or 0) + (a.get("port_cad") or 0), 2) for a in res
                if fam in cartes_match.norm(a.get("titre") or "").split() and not cartes_match.decoder(a.get("titre") or "").get("exclu")
                and (a.get("prix_cad") or 0) > 0]
        if len(prix) >= 3:
            out[j] = {"m": round(statistics.median(prix), 2), "n": len(prix)}
    return out


def demande_recrue(prod, joueur):
    """Demande relative d'une recrue sans ventes (meme echelle que valeurs.demande : ~0,6 = un joueur ordinaire),
    d'apres ses annonces comparees aux autres recrues du produit. None si on ne sait pas."""
    a = (de(prod["id"]).get("annonces_recrues") or {})
    j = a.get(joueur)
    if not j:
        return None
    ref = statistics.median([x["m"] for x in a.values()]) if a else None
    if not ref:
        return None
    return round(max(0.2, min(15.0, 0.6 * (j["m"] / ref) ** 1.2)), 2)


def mesurer(prod, rechercher=None, chercher_annonces=None):
    import cartes_match
    import vendues
    rechercher = rechercher or vendues.rechercher
    saison, marque = _court(prod)
    out = {"maj": datetime.now().isoformat(timespec="seconds"), "sous": {}, "boite": None}
    try:
        out["annonces_recrues"] = annonces_recrues(prod, chercher_annonces)
    except Exception as e:
        out["erreur_annonces"] = type(e).__name__
    for s in (_importants(prod) if (vendues.actif() or rechercher is not vendues.rechercher) else []):
        nom = s["nom"]
        q = " ".join(x for x in (saison, marque if marque not in nom.lower() else "", nom) if x)
        r = rechercher(q, fond=True)
        if r.get("erreur") and not r.get("ventes"):
            out["erreur"] = r["erreur"]
            break
        joueurs = sorted({c["joueur"] for c in prod.get("cartes") or [] if c.get("sous_ensemble") == nom and c.get("joueur")})
        fam = {}
        for j in joueurs:
            for p in j.split("/"):
                f = cartes_match.norm(p.strip()).split()[-1:] or [""]
                if len(f[0]) >= 3:
                    fam.setdefault(f[0], []).append(j)
        par = {}
        cibles = {}
        for v in r.get("ventes") or []:
            t = cartes_match.norm(v["titre"])
            cand = {j for w in set(t.split()) for j in fam.get(w, [])}
            if len(cand) != 1:
                continue                                   # aucun joueur, ou deux (carte double, lot) : on passe
            j = cand.pop()
            if j not in cibles:
                cibles[j] = cartes_match.cible(f"{saison} {j} {nom}")
            if cartes_match.raisons_refus(cibles[j], v["titre"]):
                continue
            par.setdefault(j, []).append(v)
        js = {}
        for j, lv in par.items():
            l = [v["prix"] for v in lv]
            m = cartes_match.mediane_robuste(l)[0] if len(l) >= 3 else round(statistics.median(l), 2)
            # 26 oct 2026 - tendance et courbe du joueur (fiche joueur, tendances de la semaine)
            lv = sorted(lv, key=lambda v: str(v.get("le") or ""), reverse=True)
            js[j] = {"m": round(m, 2), "n": len(l), "t": vendues.tendance(lv), "p": [[v.get("le"), v["prix"]] for v in lv[:40] if v.get("le")]}
        tous = [x["m"] for x in js.values()]
        out["sous"][nom] = {"mediane": round(statistics.median(tous), 2) if tous else None, "n": sum(x["n"] for x in js.values()),
                            "joueurs": js}
    # le prix d'une boite scellee (hobby)
    try:
        q = f"{prod.get('nom')} hobby box"
        r = rechercher(q, fond=True)
        prix = [v["prix"] for v in r.get("ventes") or []
                if re.search(r"\bbox\b", v["titre"], re.I) and not re.search(r"\bcase\b|\bpack\b|\bbreak\b|\bspot\b|\bblaster\b|\bempty\b",
                                                                             v["titre"], re.I)
                and saison.split("-")[0] in v["titre"]]
        if len(prix) >= 2:
            out["boite"] = round(cartes_match.mediane_robuste(prix)[0] if len(prix) >= 4 else statistics.median(prix), 2)
    except Exception:
        pass
    with _verrou:
        d = dict(lire())
        d[prod["id"]] = out
        _ecrire(d)
    return out


def mesurer_si_besoin(prod, attendre=False):
    """Mesure en arriere-plan si plus vieux que 7 jours (ou jamais mesure). attendre=True : tout de suite."""
    e = de(prod["id"])
    try:
        age = time.time() - datetime.fromisoformat(str(e.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    if age < FRAICHEUR_S and not e.get("erreur"):
        return e
    if attendre:
        return mesurer(prod)
    with _verrou:
        if prod["id"] in _EN_COURS:
            return e
        _EN_COURS.add(prod["id"])

    def tache():
        try:
            mesurer(prod)
        except Exception as x:
            print("Valeur produit : " + repr(x), flush=True)
        finally:
            _EN_COURS.discard(prod["id"])
    threading.Thread(target=tache, daemon=True, name="valeur_produit").start()
    return e


def valeur(prod, nom_sous, joueur, defaut):
    """La valeur d'UNE carte (sous-ensemble, joueur) : sa mediane vendue si mesuree ; sinon la mediane du
    sous-ensemble x la demande relative du joueur (s'il est connu) ; sinon `defaut` (le modele d'avant)."""
    e = (de(prod["id"]).get("sous") or {}).get(nom_sous)
    if not e:
        return defaut, False
    j = (e.get("joueurs") or {}).get(joueur)
    if j and j.get("n", 0) >= 2:
        return j["m"], True
    if e.get("mediane"):
        if j:                                            # une seule vente : a mi-chemin avec la mediane
            return round((j["m"] + e["mediane"]) / 2, 2), True
        return round(e["mediane"] * 0.6, 2), True        # joueur jamais vendu : sous la mediane (les vedettes se vendent)
    return defaut, False
