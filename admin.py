"""
LOCKERROOM - la console de l'administrateur (25 oct 2026).

Mathieu : « est-ce que je peux avoir une version admin de l'app pour gerer les abonnements les updates etc ? »
-> Abonnes et revenus, Sante du serveur, Catalogue, Demandes des utilisateurs (demandes.py).

Seul l'admin y a acces (PC de Mathieu, ou en ligne un compte eBay liste dans LOCKERROOM_ADMINS).
Jamais une cle ni un jeton dans les reponses : seulement des comptes, des compteurs et des dates.
Les remboursements et annulations restent dans Stripe (lien direct vers le client).
"""
import json
import os
import shutil
import threading
import time
from datetime import datetime, timedelta

DEMARRE = time.time()
_verrou = threading.Lock()


# -- erreurs recentes (les 60 dernieres, gardees sur le disque) ---------------------------------
def _chemin_erreurs():
    import comptes
    return os.path.join(comptes.DONNEES, "erreurs_recentes.json")


def noter_erreur(ou, e):
    try:
        with _verrou:
            try:
                with open(_chemin_erreurs(), encoding="utf-8") as f:
                    l = json.load(f) or []
            except (OSError, ValueError):
                l = []
            l.append({"le": datetime.now().isoformat(timespec="seconds"), "ou": str(ou)[:60],
                      "erreur": (type(e).__name__ + " : " + str(e))[:300]})
            tmp = _chemin_erreurs() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(l[-60:], f, ensure_ascii=False)
            os.replace(tmp, _chemin_erreurs())
    except Exception:
        pass


def erreurs():
    try:
        with open(_chemin_erreurs(), encoding="utf-8") as f:
            return list(reversed(json.load(f) or []))
    except (OSError, ValueError):
        return []


# -- abonnes et revenus --------------------------------------------------------------------------
def _date(s):
    try:
        return datetime.fromisoformat(str(s)[:19])
    except ValueError:
        return None


def abonnes():
    import comptes
    import forfaits
    import paiements
    maint = datetime.now()
    out = []
    for cid in comptes.lister():
        info = comptes.info(cid) or {}
        e = forfaits.etat(cid)
        statut = "pro" if e.get("payant") else "offert" if e.get("offert") else "essai" if e.get("essai") else "gratuit"
        vu = _date(info.get("vu_le"))
        out.append({"id": cid, "username": info.get("username") or "?", "env": info.get("env"), "statut": statut,
                    "cree_le": info.get("cree_le"), "vu_le": info.get("vu_le"),
                    "actif_7j": bool(vu and maint - vu < timedelta(days=7)),
                    "jours_essai": e.get("jours_restants") if e.get("essai") else None,
                    "pro_offert": info.get("pro_offert"), "forfait_fin": info.get("forfait_fin"),
                    "annule": bool(info.get("forfait_annule")), "forfait_statut": info.get("forfait_statut"),
                    "stripe": bool(info.get("stripe_client")),
                    "stripe_url": ("https://dashboard.stripe.com/" + ("test/" if paiements.mode() == "test" else "") +
                                   "customers/" + str(info["stripe_client"])) if info.get("stripe_client") else None})
    out.sort(key=lambda x: str(x.get("vu_le") or ""), reverse=True)
    prix = None
    try:
        prix = paiements.prix_affiche()
    except Exception:
        pass
    n = lambda st: sum(1 for x in out if x["statut"] == st)
    nouveaux = sum(1 for x in out if (_date(x["cree_le"]) or datetime.min) > maint - timedelta(days=7))
    mensuel = None
    if prix:                                    # revenu mensuel estime : abonnes payants x prix (annuel / 12)
        mensuel = round(n("pro") * prix["montant"] / (12 if prix.get("intervalle") == "year" else 1), 2)
    return {"comptes": out, "total": len(out), "pro": n("pro"), "offert": n("offert"), "essai": n("essai"),
            "gratuit": n("gratuit"), "actifs_7j": sum(1 for x in out if x["actif_7j"]), "nouveaux_7j": nouveaux,
            "revenu_mensuel": mensuel, "devise": (prix or {}).get("devise") or "CAD", "prix": prix,
            "stripe_mode": paiements.mode() or None}


def offrir_pro(cid, jours=None):
    """jours=None : a vie ; jours=0 : retirer ; sinon N jours a partir d'aujourd'hui."""
    import comptes
    if cid not in comptes.lister():
        return {"ok": False, "erreur": "Compte introuvable"}
    if jours == 0:
        val = None
    elif jours is None:
        val = "toujours"
    else:
        val = (datetime.now() + timedelta(days=int(jours))).isoformat(timespec="minutes")
    comptes.maj(cid, pro_offert=val)
    return {"ok": True, "pro_offert": val}


def prolonger_essai(cid, jours=7):
    import comptes
    info = comptes.info(cid)
    if not info:
        return {"ok": False, "erreur": "Compte introuvable"}
    import forfaits
    e = forfaits.etat(cid)
    bonus = int(info.get("essai_bonus_jours") or 0)
    if not e.get("essai"):          # essai fini : on repart d'aujourd'hui
        cree = _date(info.get("cree_le")) or datetime.now()
        bonus = max(bonus, (datetime.now() - cree).days - forfaits.ESSAI_JOURS + 1)
    comptes.maj(cid, essai_bonus_jours=bonus + int(jours))
    return {"ok": True, "etat": forfaits.etat(cid)}


# -- sante du serveur ----------------------------------------------------------------------------
def _maj_fichier(nom, cle="maj"):
    import comptes
    try:
        with open(os.path.join(comptes.DONNEES, nom), encoding="utf-8") as f:
            return (json.load(f) or {}).get(cle)
    except (OSError, ValueError):
        return None


def sante():
    import appels_ebay
    import comptes
    import valeurs
    try:
        import vision
        _p, serveur = vision._chemins()
        vs = (vision._lire(serveur).get(vision._mois()) or {})
        photos = {"disponible": vision.disponible(), "ce_mois": vs.get("n", 0), "usd": vs.get("usd", 0.0),
                  "plafond_usd": vision.PLAFOND_SERVEUR_USD}
    except Exception:
        photos = None
    try:
        du = shutil.disk_usage(comptes.DONNEES)
        disque = {"libre_go": round(du.free / 1e9, 2), "total_go": round(du.total / 1e9, 2)}
    except OSError:
        disque = None
    taches = {"deals": _maj_fichier("deals_globaux.json"), "nouvelles": _maj_fichier("nouvelles_cache.json"),
              "nouveaux_produits": _maj_fichier("produits_a_ajouter.json"), "valeurs": (valeurs.statut() or {}).get("maj")}
    try:
        import ventes_communaute
        vc = ventes_communaute.statut()
        taches["ventes_communaute"] = vc.get("maj")
    except Exception:
        vc = None
    return {"version": (os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or "PC",
            "demarre_le": datetime.fromtimestamp(DEMARRE).isoformat(timespec="minutes"),
            "en_ligne_h": round((time.time() - DEMARRE) / 3600, 1),
            "ebay": appels_ebay.resume(), "photos": photos, "disque": disque, "taches": taches,
            "erreurs": erreurs()[:30], "multi": comptes.MULTI, "ventes_communaute": vc}


# -- catalogue -----------------------------------------------------------------------------------
def catalogue_etat():
    import catalogue
    import nouveaux_produits
    produits = []
    for p in catalogue.liste():
        try:
            pr = catalogue.charger(p["id"]) or {}
        except Exception:
            continue
        se = pr.get("sous_ensembles") or []
        produits.append({"id": p["id"], "nom": p["nom"], "sport": pr.get("sport") or "hockey",
                         "nb_cartes": len(pr.get("cartes") or []), "nb_sous": len(se),
                         "sans_cote": len(catalogue.etat_cotes(pr)["manquantes"]),        # 26 oct 2026 : meme regle que la fleche verte
                         "manquantes": catalogue.etat_cotes(pr)["manquantes"][:20], "complete": catalogue.etat_cotes(pr)["complete"],
                         "importe": os.path.exists(os.path.join(catalogue.dossier_ajouts(), p["id"] + ".json")),
                         "sources": pr.get("sources") or []})
    d = nouveaux_produits.lire()
    return {"produits": produits, "a_ajouter": nouveaux_produits.liste(), "maj_recherche": d.get("maj"),
            "ignores": [{"cle": k, "nom": (d["detectes"].get(k) or d["demandes"].get(k) or {}).get("nom") or k} for k in d.get("ignores") or []]}


def remettre(cle):
    import nouveaux_produits
    with nouveaux_produits._verrou:
        d = nouveaux_produits.lire()
        d["ignores"] = [k for k in d.get("ignores") or [] if k != cle]
        nouveaux_produits._ecrire(d)
    return {"ok": True}
