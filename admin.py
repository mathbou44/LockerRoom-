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
        rv = info.get("renvoi")
        out.append({"id": cid, "username": info.get("username") or "?", "env": info.get("env"), "statut": statut,
                    "relie_a": ((comptes.info(comptes.resoudre(cid)) or {}).get("username") or "?") if rv else None,
                    "admin": est_compte_admin(cid), "connexion": info.get("env"),
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


def _admins():
    return {x.strip().lower() for x in os.environ.get("LOCKERROOM_ADMINS", "").split(",") if x.strip()}


def est_compte_admin(cid):
    import comptes
    e = comptes.info(cid) or {}
    noms = {cid, e.get("ebay_username")} | ({e.get("username")} if e.get("env") in ("production", "sandbox") else set())
    return bool({str(x).strip().lower() for x in noms if x} & _admins())


def supprimer_compte(cid, moi, nom_confirme):
    """13 nov 2026 (Mathieu : « supprimer un de mes comptes » dans Abonnes) : l'admin supprime un compte, pour de bon.
    Garde-fous : jamais le compte avec lequel l'admin est connecte (ni celui ou il est relie), jamais un compte admin, et le
    nom du compte doit etre retape. Un ancien compte RELIE (renvoi vers un autre) : seulement son dossier ; ses connexions
    (eBay, Apple, Google) sont deja passees au compte choisi, on ne touche ni a Stripe ni a Apple (sinon la connexion du
    compte choisi serait coupee)."""
    import comptes
    if cid not in comptes.lister():
        return {"ok": False, "erreur": "Compte introuvable"}
    e = comptes.info(cid) or {}
    if str(nom_confirme or "").strip().lower() != str(e.get("username") or "").strip().lower():
        return {"ok": False, "erreur": "Le nom retapé ne correspond pas au compte"}
    if cid in (moi, comptes.resoudre(moi)) or comptes.resoudre(cid) == comptes.resoudre(moi) and not e.get("renvoi"):
        return {"ok": False, "erreur": "C’est le compte avec lequel tu es connecté : impossible de le supprimer d’ici"}
    if est_compte_admin(cid) and not e.get("renvoi"):
        return {"ok": False, "erreur": "Compte administrateur : impossible de le supprimer"}
    if e.get("renvoi"):
        comptes.supprimer(cid)
        print("Admin : ancien compte relie supprime", flush=True)
        return {"ok": True, "supprimes": [cid], "relie": True}
    import lockerroom
    groupe = lockerroom.effacer_compte(cid)
    return {"ok": True, "supprimes": groupe}


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


# 13 nov 2026 (Mathieu : « ca devrait etre V2.5.1 ; on fait pour suivre l'industrie ») : versions semantiques MAJEURE.MINEURE.
# CORRECTIF, montees a chaque livraison : un correctif seulement -> CORRECTIF + 1 (2.5.1 -> 2.5.2) ; une nouvelle fonction
# -> MINEURE + 1 et CORRECTIF a 0 (2.5.2 -> 2.6.0) ; un gros changement (refonte, rupture) -> MAJEURE + 1 (-> 3.0.0).
# Avant : un compteur de livraisons (v1 a v251) ; 2.5.1 reprend la 251e. Separee du numero de l'app iPhone (App Store).
VERSION_APP = "2.7.1"


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
    # 10 nov 2026 (Mathieu : « les stats doivent etre mises a jour regulierement, tout ce qui est vivant ») : la fraicheur
    # de chaque donnee vivante (stats LNH, popularite, forme, labo, banc de validation)
    try:
        import demande_legale
        dl = demande_legale.lire()
        J = list((dl.get("joueurs") or {}).values())
        iso = lambda t: datetime.fromtimestamp(t).isoformat(timespec="minutes") if t and t < time.time() + 86400 else None
        taches["stats_lnh"] = iso(max((e.get("le_nhl") or 0) for e in J) if J else 0)
        taches["popularite"] = iso(max((e.get("le_wiki") or 0) for e in J) if J else 0)
        taches["labo_demande"] = (dl.get("labo") or {}).get("le")
    except Exception:
        pass
    try:
        taches["forme_lnh"] = datetime.fromtimestamp(os.path.getmtime(os.path.join(comptes.DONNEES, "nhl_forme.json"))).isoformat(timespec="minutes")
    except OSError:
        pass
    try:
        import banc
        taches["banc"] = (banc.lire().get("dernier") or {}).get("le") or None
    except Exception:
        pass
    try:
        import ventes_communaute
        vc = ventes_communaute.statut()
        taches["ventes_communaute"] = vc.get("maj")
    except Exception:
        vc = None
    # 12 nov 2026 (Mathieu : « je ne sais pas ce qui roule en background, si j'ai mes mises a jour, c'est quoi la version ») :
    # toutes les taches de fond, chacune avec sa derniere passe
    def iso_mt(nom):
        try:
            return datetime.fromtimestamp(os.path.getmtime(os.path.join(comptes.DONNEES, nom))).isoformat(timespec="minutes")
        except OSError:
            return None
    for k, nom in (("indice_joueurs", "indice_joueurs.json"), ("historique_indice", "indice_hist.json"), ("types_cartes", "types_cartes.json"),
                   ("codes_produits", "codes_produits.json"), ("encans_archive", "encans_archive.json"), ("slabiq_journal", "slabiq_journal.json"),
                   ("patchs", "patchs_cache.json")):
        try:
            v_ = iso_mt(nom)
            if v_:
                taches[k] = v_
        except Exception:
            pass
    try:
        import slabiq_test
        taches["slabiq_test"] = (slabiq_test.lire().get("rapport") or {}).get("le")
    except Exception:
        pass
    try:
        import sauvegarde
        sv = sauvegarde.statut()
        taches["sauvegarde"] = sv.get("dernier_ok") if sv.get("actif") else None
    except Exception:
        pass
    return {"version": (os.environ.get("RENDER_GIT_COMMIT") or "")[:7] or "PC", "version_app": VERSION_APP,
            "demarre_le": datetime.fromtimestamp(DEMARRE).isoformat(timespec="minutes"),
            "en_ligne_h": round((time.time() - DEMARRE) / 3600, 1),
            "ebay": appels_ebay.resume(), "photos": photos, "disque": disque, "taches": taches,
            "erreurs": erreurs()[:30], "multi": comptes.MULTI, "ventes_communaute": vc, "memoire": memoire()}


# 13 nov 2026 (Render : « Web Service lockerroom exceeded its memory limit », redemarrage automatique) : la memoire est
# suivie (le processus et tout le conteneur, contre sa limite) ; au-dessus de 80 % de la limite, les memoires de confort
# (Radars gardes, scores deja calcules, ventes en cache) sont videes avant que Render ne coupe tout
def _lire_entier(ch):
    try:
        with open(ch) as f:
            v = f.read().strip()
        return None if v == "max" else int(v)
    except (OSError, ValueError):
        return None


def memoire():
    rss = None
    try:
        with open("/proc/self/status") as f:
            rss = next(int(l.split()[1]) // 1024 for l in f if l.startswith("VmRSS"))
    except (OSError, StopIteration, ValueError):
        pass
    cur = _lire_entier("/sys/fs/cgroup/memory.current") or _lire_entier("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    lim = _lire_entier("/sys/fs/cgroup/memory.max") or _lire_entier("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if lim and lim > 1 << 45:
        lim = None                                   # pas de limite reelle
    return {"processus_mo": rss, "conteneur_mo": cur // (1 << 20) if cur else None, "limite_mo": lim // (1 << 20) if lim else None,
            "soupapes": _SOUPAPE["n"], "derniere_soupape": _SOUPAPE["le"]}


_SOUPAPE = {"n": 0, "le": None}
SOUPAPE_PCT = 0.80


def soupape():
    """Aux 5 min (server.py) : pres de la limite, on vide les memoires de confort (rien de perdu : elles se refont)."""
    m = memoire()
    utilise, lim = m.get("conteneur_mo") or m.get("processus_mo"), m.get("limite_mo")
    if not utilise or not lim or utilise < SOUPAPE_PCT * lim:
        return None
    videes = []
    try:
        import lockerroom
        n = len(lockerroom.Api._RADAR)
        lockerroom.Api._RADAR.clear()
        videes.append(f"radars:{n}")
    except Exception:
        pass
    try:
        import score_slab
        n = len(score_slab._LOT["d"])
        score_slab._LOT["d"].clear()
        videes.append(f"scores:{n}")
    except Exception:
        pass
    try:
        import deals
        deals._HIT_FORT.clear()
        deals._LU.update(cle=None, d={})
    except Exception:
        pass
    import gc
    gc.collect()
    _SOUPAPE["n"] += 1
    _SOUPAPE["le"] = datetime.now().isoformat(timespec="minutes")
    print(f"Memoire : {utilise} / {lim} Mo, memoires videes ({', '.join(videes)})", flush=True)
    return videes


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
                         # 30 oct 2026 : cotes estimees (tirage imprime, ou la meme ligne d'une autre saison) et non publiees
                         "estimees": [{"nom": n, "source": (pr.get("_estimees_src") or {}).get(n), "par_boite": round((pr.get("_taux") or {}).get(n) or 0, 4)}
                                      for n in catalogue.etat_cotes(pr)["estimees"]][:40],
                         "non_publiees": catalogue.etat_cotes(pr)["non_publiees"][:20],
                         "importe": os.path.exists(os.path.join(catalogue.dossier_ajouts(), p["id"] + ".json")),
                         "contribue": bool(pr.get("contribue")),
                         "sources": pr.get("sources") or []})
    d = nouveaux_produits.lire()
    import contributions
    return {"produits": produits, "a_ajouter": nouveaux_produits.liste(), "maj_recherche": d.get("maj"),
            "attente": len(contributions.liste_attente()),
            "ignores": [{"cle": k, "nom": (d["detectes"].get(k) or d["demandes"].get(k) or {}).get("nom") or k} for k in d.get("ignores") or []]}


def remettre(cle):
    import nouveaux_produits
    with nouveaux_produits._verrou:
        d = nouveaux_produits.lire()
        d["ignores"] = [k for k in d.get("ignores") or [] if k != cle]
        nouveaux_produits._ecrire(d)
    return {"ok": True}
