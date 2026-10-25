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
from datetime import datetime, timedelta

ESSAI_JOURS = 14
LIMITES = {                    # Gratuit (apres l'essai) ; Pro = illimite
    "annonces_mois": 5,        # annonces creees depuis l'app par mois
    "valeur_jour": 5,          # recherches « combien vaut une carte » par jour
    "deals": 5,                # deals visibles
    "repere": 3,               # cartes de l'inventaire avec le repere prix vs marche
    "breaks_produits": 1,      # produits dans l'analyse de breaks
}
_verrou = threading.Lock()


class LimiteAtteinte(Exception):
    def __init__(self, cle, limite):
        self.cle, self.limite = cle, limite
        msg = {"annonces_mois": f"Tes {limite} annonces gratuites du mois sont utilisées : passe au forfait Pro pour continuer.",
               "valeur_jour": f"Tes {limite} recherches gratuites du jour sont utilisées : passe au forfait Pro pour continuer.",
               }.get(cle, "Fonction Pro : passe au forfait Pro pour continuer.")
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
    cid = cid or _compte()
    if not cid:
        return {"pro": True, "essai": False, "payant": True, "jours_restants": None, "local": True}
    info = comptes.info(cid) or {}
    payant = (info.get("forfait") or "gratuit") == "pro"
    don = offert(info)
    try:
        fin = datetime.fromisoformat(str(info.get("cree_le"))[:19]) + timedelta(days=ESSAI_JOURS + int(info.get("essai_bonus_jours") or 0))
    except (ValueError, TypeError):
        fin = None
    essai = (not payant) and (not don) and fin is not None and datetime.now() < fin
    reste = max(0, (fin - datetime.now()).days + 1) if essai else 0
    return {"pro": payant or essai or don, "essai": essai, "payant": payant, "offert": don, "jours_restants": reste,
            "essai_fin": fin.isoformat(timespec="minutes") if fin else None}


def est_pro():
    return etat()["pro"]


def _chemin():
    import comptes
    return os.path.join(comptes.dossier() or comptes.DONNEES, "usage_forfait.json")


def _cle_periode(cle):
    maint = datetime.now()
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
    reste = {k: (None if e["pro"] else max(0, LIMITES[k] - utilise(k))) for k in ("annonces_mois", "valeur_jour")}
    return {**e, "limites": LIMITES, "reste": reste}
