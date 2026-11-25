"""
LOCKERROOM - Gratuit ou Pro (24 oct 2026).

Mathieu : « defenir ce qui est free et payant, aide moi » et « lorsque l'app est en version base doit etre
en gris en haut a droite et lorsque pro, doit etre gold et sexy ... l'utilisateur doit se sentir premium ».

Ce que disent les etudes (resume dans la reponse a Mathieu) :
  - environ 80 % de l'app gratuite, les 20 % qui font gagner du temps ou de l'argent en Pro ;
  - un essai Pro complet au depart (« reverse trial », 14 jours) : on tient a ce qu'on a deja utilise ;
  - montrer la fonction Pro verrouillee au moment ou on en a besoin (pas la cacher) ;
  - l'ecart de valeur entre Gratuit et Pro est ce qui fait passer au Pro.

Les limites ne touchent jamais les donnees de l'utilisateur : son inventaire, ses ventes et son profit
restent gratuits et illimites. PC de Mathieu (sans multi-comptes) : tout est Pro.
"""
import json
import os
import threading
import time
from datetime import datetime, timedelta

ESSAI_JOURS = 14
# 24 nov 2026 (Mathieu : « 8,99 serait deja mieux ; pour l'annuel, un rabais de 20 % ») : LE prix annonce, ecrit ici une seule
# fois. Le site, les conditions et la description des pages doivent dire ces chiffres (tests/test_audit_coherence.py). Le
# prix FACTURE vit dans Stripe (STRIPE_PRIX_PRO, STRIPE_PRIX_PRO_ANNUEL) et chez Apple : les changer la aussi, le meme jour.
PRIX_PRO = 8.99                # $ CA par mois (7,99 avant)
RABAIS_ANNUEL = 0.20           # engagement de 12 mois, paye chaque mois (25 % avant)
PRIX_PRO_ANNUEL = round(PRIX_PRO * (1 - RABAIS_ANNUEL), 2)      # 7,19 $ par mois
ECONOMIE_ANNUEL = round((PRIX_PRO - PRIX_PRO_ANNUEL) * 12, 2)   # 21,60 $ sur l'annee
LIMITES = {                    # Gratuit (apres l'essai) ; Pro = illimite
    # 21 nov 2026 (Mathieu : « c'est trop peu ; le gratuit doit donner envie de rester avec nous, pas de partir parce qu'il
    # n'est capable de rien faire ; 10 annonces max par mois sur eBay, 20 recherches max par semaine dans le Radar ») :
    # 10 annonces par mois (5 avant), 15 cartes dans le Radar (6 avant, dont ses 3 meilleures), 20 recherches par semaine
    # dans le Radar (aucune avant)
    "annonces_mois": 10,       # annonces creees depuis l'app par mois
    "radar_semaine": 20,       # recherches dans le Radar par semaine
    "valeur_jour": 5,          # recherches « combien vaut une carte » par jour
    "deals": 5,                # deals visibles
    "repere": 3,               # cartes de l'inventaire avec le repere prix vs marche
    "breaks_produits": 1,      # produits dans l'analyse de breaks
    "preparer_jour": 20,       # 27 oct 2026 : annonces preparees (prix suggere) par jour - protege le quota eBay partage
    "offres_jour": 3,          # 28 oct 2026 : offres envoyees aux acheteurs interesses, par jour
}
_verrou = threading.Lock()


class LimiteAtteinte(Exception):
    def __init__(self, cle, limite):
        self.cle, self.limite = cle, limite
        msg = {"annonces_mois": f"Tes {limite} annonces gratuites du mois sont utilisées : passe au forfait Pro pour continuer.",
               "valeur_jour": f"Tes {limite} recherches gratuites du jour sont utilisées : passe au forfait Pro pour continuer.",
               "preparer_jour": f"Tes {limite} annonces préparées du jour sont utilisées : reviens demain ou passe au forfait Pro.",
               "offres_jour": f"Tes {limite} offres gratuites du jour sont envoyées : reviens demain ou passe au forfait Pro.",
               "radar_semaine": f"Tes {limite} recherches gratuites de la semaine sont utilisées : reviens lundi ou passe au forfait Pro.",
               }.get(cle, "Fonction Pro : passe au forfait Pro pour continuer.")
        try:                                  # 27 oct 2026 (revue Apple 3.1.1) : dans l'app iPhone, pas d'appel a acheter ailleurs
            import lockerroom
            if lockerroom.est_ios():
                msg = {"annonces_mois": f"Tes {limite} annonces gratuites du mois sont utilisées : reviens le mois prochain.",
                       "valeur_jour": f"Tes {limite} recherches gratuites du jour sont utilisées : reviens demain.",
                       "preparer_jour": f"Tes {limite} annonces préparées du jour sont utilisées : reviens demain.",
                       "offres_jour": f"Tes {limite} offres gratuites du jour sont envoyées : reviens demain.",
                       "radar_semaine": f"Tes {limite} recherches gratuites de la semaine sont utilisées : reviens lundi.",
                       }.get(cle, "Limite du forfait gratuit atteinte.")
        except Exception:
            pass
        super().__init__(msg)


def _compte():
    import comptes
    return comptes.courant() if comptes.MULTI else None


def offert(info):
    """25 oct 2026 - Pro offert par l'admin : « toujours » ou jusqu'a une date (champ distinct de Stripe)."""
    o = str((info or {}).get("pro_offert") or "")
    if o == "toujours":
        return True
    try:
        return bool(o) and datetime.now() < datetime.fromisoformat(o[:19])
    except ValueError:
        return False


def etat(cid=None):
    """{pro, essai, jours_restants, payant, offert} du compte courant (ou du compte cid, pour l'admin)."""
    import comptes
    if cid is None:                              # 10 nov 2026 : l'admin regarde l'app comme un utilisateur Pro ou Gratuit
        try:
            import lockerroom
            v = lockerroom.vue_simulee()
        except Exception:
            v = None
        if v == "gratuit":
            return {"pro": False, "essai": False, "payant": False, "offert": False, "jours_restants": 0, "source": None,
                    "annule": False, "essai_fin": None, "simule": "gratuit"}
        if v == "platine":
            return {"pro": True, "platine": True, "essai": False, "payant": True, "offert": False, "jours_restants": None, "source": "stripe",
                    "annule": False, "essai_fin": None, "simule": "platine"}
        if v == "pro":
            return {"pro": True, "essai": False, "payant": True, "offert": False, "jours_restants": None, "source": "stripe",
                    "annule": False, "essai_fin": None, "simule": "pro"}
    cid = cid or _compte()
    if not cid:
        return {"pro": True, "essai": False, "payant": True, "jours_restants": None, "local": True}
    info = comptes.info(cid) or {}
    payant = (info.get("forfait") or "gratuit") in ("pro", "platine")
    platine = platine_ouvert() and ((info.get("forfait") or "") == "platine" or offert({"pro_offert": info.get("platine_offert")}))
    if payant and info.get("forfait_source") == "apple":       # 27 oct 2026 : filet si un avis d'Apple se perd
        try:
            payant = time.time() < float(info.get("forfait_fin") or 0) + 3 * 86400
        except (TypeError, ValueError):
            payant = False
    don = offert(info)
    try:
        fin = datetime.fromisoformat(str(info.get("cree_le"))[:19]) + timedelta(days=ESSAI_JOURS + int(info.get("essai_bonus_jours") or 0))
    except (ValueError, TypeError):
        fin = None
    essai = (not payant) and (not don) and fin is not None and datetime.now() < fin
    reste = max(0, (fin - datetime.now()).days + 1) if essai else 0
    return {"pro": payant or essai or don or platine, "platine": bool(platine), "essai": essai, "payant": payant, "offert": don, "jours_restants": reste,
            "source": info.get("forfait_source") if payant else None, "annule": bool(info.get("forfait_annule")),
            "essai_fin": fin.isoformat(timespec="minutes") if fin else None}


def est_pro():
    return etat()["pro"]


def platine_ouvert():
    """16 nov 2026 : la version Platine (comps et prix calcules) s'ouvre aux abonnes avec LR_PLATINE=1, une fois la licence
    commerciale des ventes obtenue. Avant : seul l'admin (et sa vue « comme un Platine »)."""
    return os.environ.get("LR_PLATINE") == "1"


def est_platine():
    """Le compte courant a-t-il la version Platine ? (jamais avant platine_ouvert(), sauf la vue simulee de l'admin)"""
    e = etat()
    return bool(e.get("platine")) and (e.get("simule") == "platine" or platine_ouvert())


def _chemin():
    import comptes
    return os.path.join(comptes.dossier() or comptes.DONNEES, "usage_forfait.json")


def _cle_periode(cle):
    maint = datetime.now()
    if cle.endswith("_semaine"):              # la semaine ISO (du lundi au dimanche)
        return maint.strftime("%G-S%V")
    return maint.strftime("%Y-%m") if cle.endswith("_mois") else maint.strftime("%Y-%m-%d")


def utilise(cle):
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    return int((d.get(_cle_periode(cle)) or {}).get(cle) or 0)


def verifier(cle):
    """Leve LimiteAtteinte si un compte Gratuit (hors essai) a tout utilise."""
    if est_pro():
        return
    if utilise(cle) >= LIMITES[cle]:
        raise LimiteAtteinte(cle, LIMITES[cle])


def compter(cle):
    if _compte() is None:
        return
    with _verrou:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        p = _cle_periode(cle)
        d = {k: v for k, v in d.items() if k >= (datetime.now() - timedelta(days=62)).strftime("%Y-%m")}   # garde 2 mois
        d.setdefault(p, {})[cle] = int(d.get(p, {}).get(cle) or 0) + 1
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _chemin())


def produit_permis(pid):
    """Gratuit : l'analyse de breaks sur 1 produit par mois (le premier choisi) ; Pro : tous."""
    if est_pro() or _compte() is None:
        return True
    with _verrou:
        try:
            with open(_chemin(), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        p = datetime.now().strftime("%Y-%m")
        vus = (d.get(p) or {}).get("breaks_ids") or []
        if pid in vus:
            return True
        if len(vus) >= LIMITES["breaks_produits"]:
            return False
        d.setdefault(p, {})["breaks_ids"] = vus + [pid]
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, _chemin())
    return True


def resume():
    """Pour l'ecran : forfait, essai, et ce qui reste dans le Gratuit."""
    e = etat()
    reste = {k: (None if e["pro"] else max(0, LIMITES[k] - utilise(k))) for k in ("annonces_mois", "valeur_jour", "radar_semaine")}
    lim = dict(LIMITES)
    try:                                         # 21 nov 2026 : les cartes visibles du Radar en Gratuit (pour la fenetre « Passer Pro »)
        import lockerroom
        lim["radar_cartes"] = lockerroom.Api.RADAR_GRATUIT
    except Exception:
        pass
    return {**e, "limites": lim, "reste": reste}
