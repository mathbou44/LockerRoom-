"""
LOCKERROOM - ne manquer aucun nouveau produit pour les breaks (24 oct 2026).

Mathieu : « comment on s'y prend pour etre sur de tout avoir les nouveaux produits ? » -> « Oui go ».

Trois filets, une seule liste « Produits a ajouter » (visible par l'administrateur) :
  1. le serveur repere chaque semaine sur eBay les boites scellees de la saison absentes du catalogue
     (les preventes apparaissent avant la sortie) ;
  2. les utilisateurs signalent un produit manquant (« Il manque un produit ? ») ;
  3. l'admin ajoute le produit en deposant l'Excel Beckett (checklist_import) : il sort de la liste tout seul.
Rien n'est telecharge chez Beckett : seulement l'API eBay deja utilisee (~10 recherches par semaine).
"""
import json
import os
import re
import threading
import time
from datetime import datetime

FRAICHEUR_S = 7 * 86400
MIN_ANNONCES = 3                 # un produit vu dans au moins 3 annonces (evite les titres farfelus)
_verrou = threading.Lock()
_ETAT = {"en_cours": False}

SAISON_DOUBLE = {"hockey", "basketball"}           # 2026-27 ; baseball et football : 2026
_BRUIT = set("""hobby box boxes sealed factory case cases blaster mega retail pack packs tin tins jumbo hanger value
cello fat gravity feed display new brand nib fotl personal break breaks random team
spot spots pyt lot of and with x2 2x 3x 4x 5x 6x 8x 10x 12x 16x 18x 20x 24x 36x box's in hand ship ships free shipping
presale pre sale preorder pre-order confirmed sealed! trading cards card nhl nba mlb nfl hockey basketball baseball football
sports sport official look rare hot sale only priority usa canada qty quantity full""".split())
_ALIAS = [(r"\bud\b", "upper deck"), (r"\bseries one\b", "series 1"), (r"\bseries two\b", "series 2"),
          (r"\bs1\b", "series 1"), (r"\bs2\b", "series 2"), (r"\bo pee chee\b", "o-pee-chee"), (r"\bopc\b", "o-pee-chee"),
          (r"\ballen ginter\b", "allen & ginter"), (r"\ba&g\b", "allen & ginter")]


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "produits_a_ajouter.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f) or {}
    except (OSError, ValueError):
        d = {}
    for k in ("detectes", "demandes", "gts"):
        d.setdefault(k, {})
    d.setdefault("ignores", [])
    return d


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


def saisons(sport, maint=None):
    """Les saisons dont les produits sortent en ce moment (la courante et la precedente)."""
    maint = maint or datetime.now()
    a = maint.year if maint.month >= 6 else maint.year - 1
    if sport in SAISON_DOUBLE:
        return [f"{a}-{str(a + 1)[2:]}", f"{a - 1}-{str(a)[2:]}"]
    return [str(maint.year + (1 if maint.month >= 11 else 0)), str(maint.year - (0 if maint.month >= 11 else 1))]


def _norm(t):
    t = str(t or "").lower().replace("’", "'")
    t = re.sub(r"(20\d{2})\s*[/-]\s*(20)?(\d{2})\b", r"\1-\3", t)        # 2025/26, 2025-2026 -> 2025-26
    t = re.sub(r"\bfirst off the line\b", " fotl ", t)
    t = re.sub(r"\b(lot of|set of|qty|x)\s*\d+\b", " ", t)
    for a, b in _ALIAS:
        t = re.sub(a, b, t)
    return t


def nom_produit(titre, sport=None):
    """« Upper Deck 2025-26 Series 2 Hockey Hobby Box Factory Sealed » -> (« 2025-26 Upper Deck Series 2 », saison)."""
    t = _norm(titre)
    m = re.search(r"\b(20\d{2}(?:-\d{2})?)\b", t)
    if not m:
        return None, None
    saison = m.group(1)
    if sport in SAISON_DOUBLE and "-" not in saison:
        return None, None
    reste = (t[:m.start()] + " " + t[m.end():])
    reste = re.sub(r"\(.*?\)|\[.*?\]", " ", reste)
    reste = re.sub(r"[^a-z0-9&' -]", " ", reste)
    mots = []
    for w in reste.split():
        if w in _BRUIT or re.fullmatch(r"\d+x|x\d+|\d+ct|\d+-?pack|#?\d{3,}", w):
            if mots and w in ("hobby", "box", "blaster", "case", "mega", "retail", "pack", "packs", "sealed", "factory"):
                break                                     # le nom du produit s'arrete au format
            continue
        if not mots and w.isdigit():                      # « 2 » devant le nom (quantite)
            continue
        mots.append(w)
        if len(mots) >= 5:
            break
    if not mots or (len(mots) == 1 and len(mots[0]) < 4):
        return None, None
    nom = saison + " " + " ".join(w if any(ch.isdigit() for ch in w) or w in ("&",) else w.capitalize() for w in mots)
    nom = nom.replace("O-pee-chee", "O-Pee-Chee").replace("Sp ", "SP ").replace("Ud ", "UD ")
    if sport and sport != "hockey":
        nom += " " + sport.capitalize()                   # « 2025 Panini Prizm Football » (Prizm existe dans 3 sports)
    return nom, saison


def cle(nom, sport="hockey"):
    """Cle de comparaison : sport, saison (1re annee), mots de la ligne tries (« hockey/2025:2 deck series upper »)."""
    t = _norm(nom)
    m = re.search(r"\b(20\d{2})", t)
    mots = sorted(set(w for w in re.sub(r"(20\d{2})(-\d{2})?", " ", t).replace("-", " ").split()
                      if w not in _BRUIT))
    return (sport or "hockey") + "/" + (m.group(1) if m else "") + ":" + " ".join(mots)


def _au_catalogue():
    import catalogue
    out = set()
    for p in catalogue.liste():
        try:
            sport = (catalogue.charger(p["id"]) or {}).get("sport") or "hockey"
        except Exception:
            sport = "hockey"
        out.add(cle(p.get("nom"), sport))
    return out


def _deja(k, cat):
    """Le produit est-il au catalogue ? (meme saison, memes mots, ou tous ses mots dans un produit du catalogue)"""
    if k in cat:
        return True
    an, mots = k.split(":", 1)
    ms = set(mots.split())
    return any(c.split(":", 1)[0] == an and ms and ms <= set(c.split(":", 1)[1].split()) for c in cat)


def detecter(rechercher=None, maint=None):
    """Un tour : quelques recherches eBay par sport ; garde les produits absents du catalogue."""
    import ebay_compte
    import sports
    rechercher = rechercher or ebay_compte.rechercher
    d = lire()
    cat = _au_catalogue()
    vus = {}
    appels = 0
    for sport in sports.SPORTS:
        if sport == "f1":                       # 31 oct 2026 : la F1 sert aux deals ; pas de produits F1 au catalogue
            continue
        for s in saisons(sport, maint):
            q = f"{s} {sport} hobby box"
            try:
                annonces = rechercher(q, categorie=None, limite=200, fond=True, recentes=True) or []
                appels += 1
            except (RuntimeError, OSError):
                continue
            for a in annonces:
                nom, saison = nom_produit(a.get("titre"), sport)
                if not nom or saison not in (s, s.split("-")[0]):
                    continue
                k = cle(nom, sport)
                v = vus.setdefault(k, {"nom": nom, "sport": sport, "noms": {}, "n": 0, "photo": None, "prix": []})
                v["n"] += 1
                v["noms"][nom] = v["noms"].get(nom, 0) + 1
                v["photo"] = v["photo"] or a.get("photo")
                if a.get("prix_cad"):
                    v["prix"].append(float(a["prix_cad"]))
    # « 2025-26 Series 2 » et « 2025-26 Upper Deck Series 2 » : le meme produit, on regroupe sous le nom le plus complet
    for k in sorted(vus, key=lambda x: len(x.split(":", 1)[1].split())):
        an, ms = k.split(":", 1)
        plus = [k2 for k2 in vus if k2 != k and k2.split(":", 1)[0] == an and set(ms.split()) < set(k2.split(":", 1)[1].split())]
        if plus and ms:
            cible = max(plus, key=lambda x: vus[x]["n"])
            vus[cible]["n"] += vus[k]["n"]
            vus[cible]["prix"] += vus[k]["prix"]
            vus[k]["n"] = 0
    ici = datetime.now().isoformat(timespec="seconds")
    nouveaux = 0
    for k, v in vus.items():
        if v["n"] < MIN_ANNONCES or _deja(k, cat):
            continue
        nom = max(v["noms"].items(), key=lambda kv: kv[1])[0]          # le nom le plus frequent
        prix = sorted(v["prix"])
        e = d["detectes"].get(k)
        if not e:
            nouveaux += 1
        d["detectes"][k] = {"nom": nom, "sport": v["sport"], "nb_annonces": v["n"], "photo": v["photo"],
                            "prix_boite": prix[len(prix) // 2] if prix else None,
                            "vu_le": (e or {}).get("vu_le") or ici, "maj": ici}
    d["maj"] = ici
    with _verrou:
        _ecrire(d)
    return {"ok": True, "appels": appels, "nouveaux": nouveaux, "a_ajouter": len(liste())}


def detecter_si_besoin():
    """En arriere-plan, au plus une fois par semaine."""
    d = lire()
    try:
        age = time.time() - datetime.fromisoformat(str(d.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    if age < FRAICHEUR_S:
        return False
    with _verrou:
        if _ETAT["en_cours"]:
            return False
        _ETAT["en_cours"] = True

    def tache():
        try:
            detecter()
        except Exception as e:
            print("Nouveaux produits : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="nouveaux_produits").start()
    return True


def demander(nom, sport, compte):
    """Un utilisateur signale un produit manquant (une fois par compte et par produit)."""
    nom = re.sub(r"\s+", " ", str(nom or "")).strip()[:90]
    if len(nom) < 4:
        return {"ok": False, "erreur": "Donne le nom du produit (ex. 2026-27 Upper Deck Series 1)"}
    import sports
    sport = sports.valide(sport)
    k = cle(nom, sport)
    if _deja(k, _au_catalogue()):
        return {"ok": True, "deja": True}
    with _verrou:
        d = lire()
        e = d["demandes"].setdefault(k, {"nom": nom, "sport": sport, "comptes": [], "le": datetime.now().isoformat(timespec="seconds")})
        qui = str(compte or "local")
        if qui not in e["comptes"]:
            e["comptes"] = (e["comptes"] + [qui])[-500:]
        if k in d["ignores"]:
            d["ignores"].remove(k)                          # redemande : on le remontre
        _ecrire(d)
    return {"ok": True, "deja": False}


def liste():
    """Produits a ajouter : demandes d'abord (les plus demandes), puis ceux vus sur eBay (les plus vus)."""
    d = lire()
    cat = _au_catalogue()
    out = {}
    for k, v in d["detectes"].items():
        out[k] = {"cle": k, "nom": v["nom"], "sport": v.get("sport"), "nb_annonces": v.get("nb_annonces", 0),
                  "photo": v.get("photo"), "prix_boite": v.get("prix_boite"), "vu_le": v.get("vu_le"), "demandes": 0}
    for k, v in d["demandes"].items():
        e = out.setdefault(k, {"cle": k, "nom": v["nom"], "sport": v.get("sport"), "nb_annonces": 0, "photo": None,
                               "prix_boite": None, "vu_le": v.get("le"), "demandes": 0})
        e["demandes"] = len(v.get("comptes") or [])
    # 25 oct 2026 - les checklists GTS (gogts.net) des saisons en cours : « Importer » d'un geste
    import checklist_import
    import catalogue
    noms_cat = catalogue.liste()
    for k, v in d["gts"].items():
        if checklist_import.produit_semblable(v["nom"], noms_cat):
            continue
        cible = k if k in out else next((k2 for k2, x in out.items() if checklist_import.produit_semblable(v["nom"], [{"nom": x["nom"]}])), None)
        if cible:
            out[cible]["gts"] = v["url"]
        else:
            out[k] = {"cle": k, "nom": v["nom"], "sport": "hockey", "nb_annonces": 0, "photo": None, "prix_boite": None,
                      "vu_le": v.get("vu_le"), "demandes": 0, "gts": v["url"]}
    res = [x for k, x in out.items() if k not in d["ignores"] and not _deja(k, cat)]
    res.sort(key=lambda x: (-x["demandes"], not x.get("gts"), -x["nb_annonces"], x["nom"]))
    return res


def ignorer(k):
    with _verrou:
        d = lire()
        if k not in d["ignores"]:
            d["ignores"] = (d["ignores"] + [k])[-2000:]
        _ecrire(d)
    return {"ok": True}


_GTS = {"le": 0.0}


def gts_si_besoin(force=False, lister=None):
    """25 oct 2026 - une fois par jour : les checklists GTS des saisons en cours absentes du catalogue
    vont dans « Produits a ajouter » (l'admin les importe d'un geste ; rien n'est importe tout seul)."""
    if not force and time.time() - _GTS["le"] < 86400:
        return None
    _GTS["le"] = time.time()
    import gts
    r = (lister or gts.lister)("hockey")
    if not r.get("ok") and not r.get("produits"):
        return r
    cours = set(saisons("hockey"))
    ici = datetime.now().isoformat(timespec="seconds")
    with _verrou:
        d = lire()
        for x in r.get("produits") or []:
            if x["saison"] not in cours:
                continue
            k = cle(x["nom"], "hockey")
            e = d["gts"].get(k) or {}
            d["gts"][k] = {"nom": x["nom"], "url": x["url"], "vu_le": e.get("vu_le") or ici}
        _ecrire(d)
    return {"ok": True, "n": len(d["gts"])}


def retirer_gts(url):
    with _verrou:
        d = lire()
        d["gts"] = {k: v for k, v in d["gts"].items() if v.get("url") != url}
        _ecrire(d)
