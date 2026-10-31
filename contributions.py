"""
SLABCOACH - les checklists envoyees par les utilisateurs (31 oct 2026).

Mathieu : « si un breaker veut un produit, il doit uploader un fichier Excel de la checklist et apres notre programme
s'occupe du reste, le publie pour les autres utilisateurs et le valide aussi ».

Le chemin :
  1. l'utilisateur depose l'Excel (GTS, Beckett, fabricant) ; le meme lecteur que l'admin le lit ;
  2. la validation automatique (ci-dessous) ;
  3. tout est bon : publie pour TOUS les comptes, tout de suite ; sinon : en attente, l'admin publie ou refuse d'un tap.
Un utilisateur ne remplace JAMAIS un produit deja au catalogue : une checklist d'un produit existant va en attente (l'admin
la fusionne s'il le veut). Le nom de celui qui l'a envoyee n'est jamais montre aux autres (seulement a l'admin).
Garde-fous : 10 fichiers par compte par jour ; rien n'est supprime (un produit retire est deplace, jamais efface).
"""
import json
import os
import re
import threading
from datetime import datetime

MAX_JOUR = 10
MIN_CARTES = 40
PART_JOUEURS_CONNUS = 0.15
_verrou = threading.Lock()
_MARQUES = re.compile(r"upper\s*deck|\bud\b|topps|panini|bowman|leaf|o-?pee-?chee|\bopc\b|parkhurst|fleer|donruss|\bscore\b|"
                      r"in the game|\bitg\b|\bsp\b|\bspx\b|futera|select|prizm|chrome|skybox|pinnacle|upper-deck", re.I)


def _base():
    return os.environ.get("LOCKERROOM_DONNEES") or os.path.dirname(os.path.abspath(__file__))


def dossier_attente():
    return os.path.join(_base(), "catalogue_attente")


def dossier_retires():
    return os.path.join(_base(), "catalogue_retires")


def _ecrire(chemin, d):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)


def _lire(chemin, defaut=None):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


# -- quota ------------------------------------------------------------------------------------
def quota_prendre(compte):
    """True si le compte peut encore envoyer un fichier aujourd'hui (et le compte)."""
    ch = os.path.join(dossier_attente(), "_quota.json")
    jour = datetime.now().strftime("%Y-%m-%d")
    with _verrou:
        d = _lire(ch, {}) or {}
        d = {jour: d.get(jour) or {}}
        n = int(d[jour].get(str(compte)) or 0)
        if n >= MAX_JOUR:
            return False
        d[jour][str(compte)] = n + 1
        _ecrire(ch, d)
    return True


# -- validation automatique -------------------------------------------------------------------------
def valider(prod, verif, sport=None):
    """-> liste de raisons (vide = publie tout de suite). Chaque raison est en mots simples."""
    raisons = []
    cartes = prod.get("cartes") or []
    nom = str(prod.get("nom") or "")
    if len(cartes) < MIN_CARTES:
        raisons.append(f"Seulement {len(cartes)} cartes lues : une checklist complète en a plus")
    if not re.search(r"(19|20)\d{2}", nom):
        raisons.append("L’année du produit n’est pas dans le nom du fichier ni dans le fichier")
    if not _MARQUES.search(nom):
        raisons.append("La marque (Upper Deck, Topps, Panini…) n’est pas reconnue dans le nom")
    groupes = {s.get("groupe") for s in prod.get("sous_ensembles") or []}
    if not groupes & {"base", "recrue"}:
        raisons.append("Aucune série de base ni de recrues reconnue")
    for a in (verif or {}).get("alertes") or []:
        if "il en manque" in a:                       # le fichier annonce plus de cartes qu'il n'en contient
            raisons.append(a)
    if (sport or prod.get("sport") or "hockey") == "hockey":
        try:
            import valeurs
            if valeurs.statut().get("nb_joueurs"):
                js = {str(c.get("joueur") or "").strip() for c in cartes if c.get("joueur")}
                js = {j for j in js if j}
                connus = sum(1 for j in js if any(valeurs.connu(x) for x in re.split(r"\s*/\s*", j)))
                if js and connus / len(js) < PART_JOUEURS_CONNUS:
                    raisons.append(f"Peu de joueurs connus ({connus} sur {len(js)}) : à vérifier")
        except Exception:
            pass
    return raisons[:5]


# -- attente ------------------------------------------------------------------------------------------
def mettre_en_attente(prod, compte, raisons, fichier, maj_de=None, verif=None):
    d = {"prod": {k: v for k, v in prod.items() if not str(k).startswith("_")}, "compte": compte, "le": datetime.now().isoformat(timespec="seconds"),
         "raisons": raisons, "fichier": fichier, "maj_de": maj_de, "verification": verif or {}}
    _ecrire(os.path.join(dossier_attente(), prod["id"] + ".json"), d)
    return d


def liste_attente():
    out = []
    try:
        noms = sorted(os.listdir(dossier_attente()))
    except OSError:
        return out
    for f in noms:
        if not f.endswith(".json") or f.startswith("_"):
            continue
        d = _lire(os.path.join(dossier_attente(), f))
        if not d or not d.get("prod"):
            continue
        p = d["prod"]
        out.append({"id": p["id"], "nom": p.get("nom"), "sport": p.get("sport"), "nb_cartes": len(p.get("cartes") or []),
                    "raisons": d.get("raisons") or [], "le": d.get("le"), "compte": d.get("compte"), "fichier": d.get("fichier"),
                    "maj_de": d.get("maj_de")})
    out.sort(key=lambda x: str(x.get("le") or ""), reverse=True)
    return out


def _deplacer(src, nom):
    os.makedirs(dossier_retires(), exist_ok=True)
    dst = os.path.join(dossier_retires(), datetime.now().strftime("%Y%m%d-%H%M%S-") + nom)
    os.replace(src, dst)
    return dst


def publier(pid):
    import catalogue
    ch = os.path.join(dossier_attente(), os.path.basename(str(pid)) + ".json")
    d = _lire(ch)
    if not d or not d.get("prod"):
        return {"ok": False, "erreur": "Rien en attente pour ce produit"}
    prod = d["prod"]
    prod["contribue"] = {"compte": d.get("compte"), "le": d.get("le"), "valide_par_admin": True}
    catalogue.enregistrer_ajout(prod)
    _deplacer(ch, "publie-" + os.path.basename(ch))
    return {"ok": True, "id": prod["id"], "nom": prod.get("nom")}


def refuser(pid):
    ch = os.path.join(dossier_attente(), os.path.basename(str(pid)) + ".json")
    if not os.path.exists(ch):
        return {"ok": False, "erreur": "Rien en attente pour ce produit"}
    _deplacer(ch, "refuse-" + os.path.basename(ch))
    return {"ok": True}


def retirer(pid):
    """Un produit publie par un utilisateur, retire du catalogue (deplace, jamais efface). Jamais un produit de SlabCoach."""
    import catalogue
    ch = os.path.join(catalogue.dossier_ajouts(), os.path.basename(str(pid)) + ".json")
    d = _lire(ch)
    if not d:
        return {"ok": False, "erreur": "Produit introuvable"}
    if not d.get("contribue"):
        return {"ok": False, "erreur": "Ce produit n’a pas été ajouté par un utilisateur"}
    _deplacer(ch, "retire-" + os.path.basename(ch))
    catalogue._CACHE.pop(ch, None)
    return {"ok": True}
