"""
SLABCOACH - SlabIQ contre l'oeil de l'expert (16 nov 2026).

Mathieu : « il faut que le Slab Score et les cartes qu'on propose soient exactement le genre de carte qu'un expert qui connait
tout aurait spotte pour acheter : pour revendre (flip), mais aussi comme investissement a moyen et long terme ; corréler le plus
possible vers ca, au fil du temps, comme on a fait avec les tests d'utilisateurs ».

1. LES JUGEMENTS de l'expert (l'admin) : sur les cartes du Radar, un toucher : « flip » (je l'achete pour revendre),
   « garder » (je l'achete pour la garder, placement) ou « passe ». Chaque jugement garde la carte, son prix, sa note SlabIQ
   et sa raison ce jour-la (etiquettes_expert.json).
2. LA MESURE : l'accord entre SlabIQ et l'expert : une carte notee A- et plus (80+) est un « oui » de SlabIQ ; flip ou garder
   est un « oui » de l'expert. -> accord, precision (des A- et plus, combien l'expert achete), rappel (des achats de l'expert,
   combien SlabIQ avait mis A- et plus), par horizon (flip / garder). Plus tard, LE RESULTAT : la meme carte revendue 60 jours
   (flip) et 6 a 12 mois (garder) apres, contre son prix du jour (ventes connues, frais de 13 %).
3. LA BOUCLE (chaque semaine) : des reglages voisins de SlabIQ (le plancher d'une grosse carte d'un joueur evergreen, ...) sont
   rejoues sur les jugements ; un reglage remplace celui en place SEULEMENT s'il s'accorde mieux avec l'expert sur les jugements
   les plus recents (30 %, jamais utilises pour choisir), et seulement avec assez de jugements. Chaque essai est garde.
L'utilisateur ne voit rien de tout ca : une lettre, une raison. L'admin voit le taux d'accord (tableau CEO).
"""
import json
import os
import threading
import time
from datetime import datetime

SEUIL_OUI = 80                 # A- et plus
N_MIN_BOUCLE = 60
PLANCHERS = (None, 75, 80, 85)
_verrou = threading.Lock()
_ETAT = {"en_cours": False}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "etiquettes_expert.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def ecrire(d):
    with _verrou:
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _chemin())


def params():
    """Les reglages en place (choisis par la boucle) ; {} = les defauts de score_slab."""
    return dict(lire().get("params") or {})


def noter(item_id, titre, choix, joueur=None, prix=None, score=None, raison=None):
    """Un jugement de l'expert. choix : flip | garder | passe (un 2e jugement de la meme annonce remplace le 1er)."""
    if choix not in ("flip", "garder", "passe") or not titre:
        return None
    d = lire()
    L = [x for x in d.get("etiquettes") or [] if str(x.get("item_id")) != str(item_id)]
    x = {"item_id": str(item_id or ""), "titre": str(titre)[:200], "joueur": joueur, "prix": prix, "score": score, "raison": raison,
         "choix": choix, "le": datetime.now().isoformat(timespec="seconds")}
    L.append(x)
    d["etiquettes"] = L[-5000:]
    ecrire(d)
    return x


RAISONS_SIGNAL = ("sorte_trop_haut", "sorte_trop_bas", "joueur_trop_haut", "joueur_trop_bas", "mauvais_joueur", "pas_hockey", "lot_reprint", "autre")


def signaler(item_id, titre, raison, joueur=None, score=None, note=None, compte=None):
    """16 nov 2026 (Mathieu : « un bouton pas un bon score : enlever la carte et faire une boucle d'apprentissage ») : un
    signalement d'un utilisateur sur la note d'une carte (la raison choisie), garde pour la revue de l'expert et la boucle."""
    if raison not in RAISONS_SIGNAL or not titre:
        return None
    d = lire()
    L = [x for x in d.get("signalements") or [] if not (str(x.get("item_id")) == str(item_id) and x.get("compte") == compte)]
    x = {"item_id": str(item_id or ""), "titre": str(titre)[:200], "joueur": joueur, "score": score, "raison": raison,
         "note": str(note or "")[:300], "compte": compte, "le": datetime.now().isoformat(timespec="seconds")}
    L.append(x)
    d["signalements"] = L[-5000:]
    ecrire(d)
    return x


def coter_sorte(raison, lettre, compte=None):
    """17 nov 2026 : l'expert tranche une question de la boucle de validation sur une SORTE de carte."""
    d = lire()
    if lettre:
        d.setdefault("sortes", {})[raison] = lettre
    d.setdefault("cotes_hist", []).append({"sorte": raison, "lettre": lettre, "le": datetime.now().isoformat(timespec="seconds"), "compte": compte})
    d["questions_marche"] = [q for q in (d.get("questions_marche") or []) if not (q.get("type") == "sorte" and q.get("nom") == raison)]
    ecrire(d)
    return True


def coter(nom, lettre, compte=None):
    """17 nov 2026 : l'expert repond a une question de SlabIQ (« quelle est la vraie cote de ce joueur ? ») ; lettre=None :
    « je ne sais pas » (la question ne revient pas avant 30 jours)."""
    nom = str(nom or "").strip()
    if not nom:
        return False
    d = lire()
    if lettre:
        d.setdefault("cotes", {})[nom] = lettre
        d.setdefault("cotes_hist", []).append({"nom": nom, "lettre": lettre, "le": datetime.now().isoformat(timespec="seconds"), "compte": compte})
        d["cotes_hist"] = d["cotes_hist"][-3000:]
    else:
        d.setdefault("passes", {})[nom] = datetime.now().isoformat(timespec="seconds")
    d["questions_marche"] = [q for q in (d.get("questions_marche") or []) if not (q.get("type") == "joueur" and q.get("nom") == nom)]
    if lettre:
        (d.get("cotes_auto") or {}).pop(nom, None)
    ecrire(d)
    return True


def passes_recents(jours=30):
    lim = time.time() - jours * 86400
    out = set()
    for n, le in (lire().get("passes") or {}).items():
        try:
            if datetime.fromisoformat(le).timestamp() >= lim:
                out.add(n)
        except (TypeError, ValueError):
            pass
    return out


def faits():
    return {str(x.get("item_id")) for x in lire().get("etiquettes") or []}


def accord(L, oui=lambda x: (x.get("score") or 0) >= SEUIL_OUI):
    """{n, accord, precision, rappel} de SlabIQ (oui = A- et plus) contre l'expert (flip ou garder)."""
    L = [x for x in L if x.get("score") is not None]
    if not L:
        return {"n": 0}
    vp = sum(1 for x in L if oui(x) and x["choix"] != "passe")
    fp = sum(1 for x in L if oui(x) and x["choix"] == "passe")
    fn = sum(1 for x in L if not oui(x) and x["choix"] != "passe")
    vn = len(L) - vp - fp - fn
    return {"n": len(L), "accord": round((vp + vn) / len(L), 3), "precision": round(vp / (vp + fp), 3) if vp + fp else None,
            "rappel": round(vp / (vp + fn), 3) if vp + fn else None}


def mesure():
    """Le taux d'accord, au total et par horizon (flip / garder), et le nombre de jugements."""
    L = lire().get("etiquettes") or []
    out = {"total": accord(L), "achats": sum(1 for x in L if x["choix"] != "passe"), "n": len(L),
           "flip": sum(1 for x in L if x["choix"] == "flip"), "garder": sum(1 for x in L if x["choix"] == "garder")}
    for h in ("flip", "garder"):
        out["par_" + h] = accord([x for x in L if x["choix"] in (h, "passe")])
    return out


def _rejouer(L, p):
    """Les notes des jugements avec les reglages p (score_slab relu sur chaque titre)."""
    import score_slab
    vieux = score_slab._PARAMS.get("v")
    score_slab._PARAMS.update(v=p, t=time.time())
    try:
        return [dict(x, score=(score_slab.score(x["titre"], x.get("joueur")) or {}).get("score")) for x in L]
    finally:
        score_slab._PARAMS.update(v=vieux, t=0.0)


def iterer():
    """La boucle : les reglages voisins sur les jugements ; garde le meilleur seulement s'il bat celui en place sur les 30 %
    les plus recents. -> l'essai (garde dans l'historique)."""
    d = lire()
    L = sorted(d.get("etiquettes") or [], key=lambda x: x.get("le") or "")
    essai = {"le": datetime.now().isoformat(timespec="seconds"), "n": len(L)}
    if len(L) < N_MIN_BOUCLE:
        essai["note"] = f"pas assez de jugements ({len(L)} / {N_MIN_BOUCLE})"
    else:
        coupe = int(len(L) * 0.7)
        appr, test = L[:coupe], L[coupe:]
        en_place = dict(d.get("params") or {})
        res = []
        for pl in PLANCHERS:
            p = {**en_place, "plancher_evergreen": pl}
            res.append((accord(_rejouer(appr, p))["accord"], p))
        best = max(res, key=lambda r: r[0])[1]
        a_place = accord(_rejouer(test, en_place)).get("accord") or 0
        a_best = accord(_rejouer(test, best)).get("accord") or 0
        essai.update(en_place=en_place, challenger=best, accord_en_place=a_place, accord_challenger=a_best)
        if best != en_place and a_best > a_place + 0.02:
            d["params"] = best
            essai["adopte"] = True
    d.setdefault("historique", []).append(essai)
    d["historique"] = d["historique"][-100:]
    d["mesure"] = mesure()
    ecrire(d)
    return essai


def passe_si_besoin():
    """Une fois par semaine (la boucle du serveur)."""
    h = (lire().get("historique") or [{}])[-1]
    try:
        if h and (datetime.now() - datetime.fromisoformat(h.get("le"))).days < 7:
            return None
    except (TypeError, ValueError):
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            e = iterer()
            print("SlabIQ expert : %s" % json.dumps(e, ensure_ascii=False)[:300], flush=True)
        except Exception as ex:
            print("SlabIQ expert : " + repr(ex), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="slabiq-expert").start()
    return True
