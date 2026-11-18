"""
SLABCOACH - la cote MARCHE de chaque joueur (17 nov 2026).

Mathieu : « la moyenne de vente d'un joueur dans les 3 derniers mois, disons 30 $, et si ca continue d'augmenter ; avec
cette moyenne on determine la valeur de cotation du joueur en termes de collection ou d'achat ; et le nombre de fois que
ce joueur a ete transige, sa liquidite : ca donne une autre note ».

La source : nos ventes reelles (base_ventes : SoldComps = les ventes eBay conclues, offres acceptees comprises), 90 jours.
La meme regle pour chaque joueur :
  - MOYENNE 90 j : la moyenne taillee (10 % des extremes enleves de chaque cote) et la mediane de toutes ses ventes ;
  - TENDANCE : la mediane des 30 derniers jours contre celle des 60 jours d'avant (en %), seulement avec assez de ventes ;
  - LIQUIDITE : ses ventes par semaine ;
  - VALEUR comparee : ses cartes contre la MEME sorte chez tous les joueurs (sa YG contre une YG typique), pour qu'un joueur
    qui n'a que des bases ne paraisse pas faible et qu'un joueur aux grosses RPA ne paraisse pas fort pour rien.
Trois lettres (meme echelle que le bareme, memes proportions que les cotes des joueurs) : VALEUR, LIQUIDITE et la COTE
MARCHE (les deux ensemble). Le public voit les lettres ; les montants restent a l'admin (regle des comps).
Limite connue : nos ventes viennent des recherches de l'app et du plan (recrues, vedettes, produits du catalogue) : la
liquidite est RELATIVE (un joueur contre les autres), pas le total d'eBay.
"""
import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timedelta

ORDRE = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "E"]
N_MIN = 8                   # ventes en 90 jours pour coter un joueur
N_TEND = 6                  # ventes de chaque cote pour une tendance
_ETAT = {"en_cours": False}
_verrou = threading.Lock()
_MEMO = {"t": 0.0, "d": None}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "cote_marche.json")


def lire():
    import time
    if _MEMO["d"] is not None and time.time() - _MEMO["t"] < 60:
        return _MEMO["d"]
    try:
        with open(_chemin(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    _MEMO.update(t=time.time(), d=d)
    return d


def joueur(nom):
    """La cote marche d'un joueur (lettres, et les chiffres pour l'admin), sinon None."""
    J = (lire().get("joueurs") or {})
    if not nom:
        return None
    x = J.get(nom)
    if x is None:
        import unicodedata
        n_ = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
        k = n_(nom)
        x = next((v for kk, v in J.items() if n_(kk) == k), None)
    return x


def _moy_taillee(v, part=0.1):
    v = sorted(v)
    k = int(len(v) * part)
    v = v[k:len(v) - k] if len(v) - 2 * k >= 3 else v
    return sum(v) / len(v)


def _lettres(valeurs, forme):
    """{cle: mesure} -> {cle: lettre} : rang de la mesure, lettres dans les proportions de `forme` (liste de lettres)."""
    cles = sorted(valeurs, key=lambda k: -valeurs[k])
    dist = sorted((l for l in forme if l in ORDRE), key=ORDRE.index)
    if not cles or not dist:
        return {}
    return {k: dist[min(len(dist) - 1, int(i * len(dist) / len(cles)))] for i, k in enumerate(cles)}


def calculer(rows, maintenant=None):
    """rows = [(titre, prix, jour AAAA-MM-JJ)] -> {joueurs: {nom: {...}}, n, le}."""
    import bareme_iq as bq
    import cartes_match
    import indice_joueurs
    import validation_iq
    maint = maintenant or datetime.now()
    d90 = (maint - timedelta(days=90)).strftime("%Y-%m-%d")
    d30 = (maint - timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        I = (indice_joueurs.lire() or {}).get("indice") or {}
    except Exception:
        I = {}
    connus = {}
    for k in I:
        connus[k.lower()] = k
    for k in bq.JOUEURS_EXPERT:
        connus.setdefault(k.lower(), k)
    import unicodedata
    n_ = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    connus_a = {n_(k): v for k, v in connus.items()}
    par_j, par_s = {}, {}
    for t, p, j in rows:
        if not t or not p or not j or j < d90:
            continue
        so, ra = bq.sorte(t)
        if ra == "lot_checklist":
            continue
        nom = cartes_match.joueur_du_titre(t)
        nom = connus_a.get(n_(nom or ""))
        if not nom:
            continue
        par_j.setdefault(nom, []).append((j, float(p), ra, validation_iq.cle_carte(t)))
        par_s.setdefault(ra, []).append(float(p))
    med_s = {r: statistics.median(v) for r, v in par_s.items() if len(v) >= 10}
    J = {}
    for nom, v in par_j.items():
        if len(v) < N_MIN:
            continue
        prix = [p for _, p, _, _ in v]
        # la tendance : la MEME carte avant et apres (ses ventes des 30 derniers jours contre les 60 d'avant), puis la mediane de
        # ces rapports : une nouvelle serie de bases a 3 $ qui sort ne fait pas croire que le joueur s'effondre
        par_c = {}
        for j_, p_, _, k_ in v:
            par_c.setdefault(k_, ([], []))[0 if j_ >= d30 else 1].append(p_)
        rap = [statistics.median(a_) / statistics.median(b_) for a_, b_ in par_c.values() if a_ and b_ and statistics.median(b_) > 0]
        tend = round(100 * (statistics.median(rap) - 1)) if len(rap) >= 3 else None
        rel = [p / med_s[r] for _, p, r, _ in v if med_s.get(r)]
        J[nom] = {"n": len(v), "cartes_suivies": len(rap), "moyenne": round(_moy_taillee(prix), 2), "mediane": round(statistics.median(prix), 2),
                  "tendance_pct": tend, "par_semaine": round(len(v) / (90 / 7), 1),
                  "valeur_rel": round(statistics.median(rel), 3) if rel else None}
    # le balayage SoldComps (chaque joueur mesure pareil, chaque semaine) : son rythme de ventes et ses vendeurs remplacent le
    # simple compte de nos archives (qui depend de ce que l'app a cherche)
    try:
        B = (lire_balayage().get("joueurs") or {})
        lim_b = (maint - timedelta(days=14)).isoformat()
        for nom, x in J.items():
            b = B.get(nom) or {}
            if b.get("n") and b.get("le", "") >= lim_b:
                x["par_semaine"] = b.get("par_semaine") or x["par_semaine"]
                x["vendeurs"] = b.get("vendeurs")
                x["mesure"] = "balayage"
    except Exception:
        pass
    # les lettres : memes proportions que les cotes actuelles des joueurs cotes ici
    forme = []
    for nom in J:
        c = (I.get(nom) or {}).get("criteres") or {}
        forme.append(bq.note_joueur(nom, c, recrue=float(c.get("recrue") or 0) >= 90)[1])
    val = {k: x["valeur_rel"] for k, x in J.items() if x["valeur_rel"]}
    liq = {k: x["par_semaine"] for k, x in J.items()}
    lv, ll = _lettres(val, forme), _lettres(liq, forme)
    liq_med = statistics.median(liq.values()) if liq else 1.0
    comb = {k: math.sqrt(val[k] * (liq[k] / liq_med)) for k in val}
    lc = _lettres(comb, forme)
    for k, x in J.items():
        x["lettre_valeur"], x["lettre_liquidite"], x["lettre"] = lv.get(k), ll.get(k), lc.get(k)
    return {"le": maint.isoformat(timespec="seconds"), "ventes": sum(x["n"] for x in J.values()), "n": len(J), "joueurs": J}


def ventes(jours=95):
    """[(titre, prix, jour)] de nos ventes reelles de hockey (base_ventes)."""
    import sqlite3
    import comptes
    import score_slab
    ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
    if not os.path.exists(ch):
        return []
    c = sqlite3.connect(ch)
    try:
        lim = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
        rows = c.execute("SELECT titre, prix, substr(le,1,10) FROM ventes WHERE prix >= 2 AND substr(le,1,10) >= ?", (lim,)).fetchall()
    finally:
        c.close()
    return [(t, float(p), j) for t, p, j in rows if t and not score_slab.sport_autre(t)]


def passe(rows=None):
    rows = rows if rows is not None else ventes()
    if len(rows) < 500:
        return {"ok": False, "ventes": len(rows)}
    d = calculer(rows)
    with _verrou:
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _chemin())
    _MEMO["d"] = None
    return {"ok": True, "joueurs": d["n"], "ventes": d["ventes"]}


def passe_si_besoin(forcer=False):
    """Une fois par semaine (« refresh a toutes les semaines, faire varier les cotes de maniere solide »), en arriere-plan."""
    try:
        age = (datetime.now() - datetime.fromisoformat(lire().get("le"))).total_seconds()
        # de nouvelles mesures du balayage depuis la derniere cote : on la refait le jour meme (pas dans une semaine)
        neuves = any((b.get("le") or "") > (lire().get("le") or "") for b in (lire_balayage().get("joueurs") or {}).values())
        if not forcer and age < (86400 if neuves else 7 * 86400):
            return None
    except (TypeError, ValueError):
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            print("Cote marche : %s" % passe(), flush=True)
        except Exception as e:
            print("Cote marche : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="cote-marche").start()
    return True


# ---------------------------------------------------------------------------------------------------------------------
# 17 nov 2026 (Mathieu : « oui, on garde SoldComps » pour mesurer chaque joueur chaque semaine, sans lui) : le BALAYAGE.
# Une recherche SoldComps par joueur suivi par semaine (eBay, 90 jours, 240 ventes au plus, offres acceptees comprises) :
#   - ses ventes vont dans nos archives (base_ventes) : la cote marche les voit ;
#   - son RYTHME : 240 ventes au plafond ne couvrent que quelques jours pour une vedette -> ventes / jours couverts ;
#   - ses VENDEURS distincts quand SoldComps donne le vendeur (comme le « total des vendeurs » de Terapeak).
# Budget a part : LR_BALAYAGE_SEMAINE (900 par defaut, ~130 par jour), une requete par seconde, jamais pendant une panne
# de SoldComps ; les joueurs les plus vieux (ou jamais mesures) d'abord.
# ---------------------------------------------------------------------------------------------------------------------
_BAL = {"en_cours": False}
RATTRAPAGE_JOUR = 300
TRANCHE = 60                     # joueurs par tour de la boucle (une requete par seconde : ~1 minute)


def _chemin_bal():
    import comptes
    return os.path.join(comptes.DONNEES, "cote_marche_balayage.json")


def lire_balayage():
    try:
        with open(_chemin_bal(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ecrire_bal(d):
    tmp = _chemin_bal() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin_bal())


def budget_semaine():
    try:
        return max(0, int(os.environ.get("LR_BALAYAGE_SEMAINE") or 900))
    except ValueError:
        return 900


def _vendeur(it):
    s = it.get("seller") or it.get("sellerUsername") or it.get("sellerName") or it.get("seller_username")
    if isinstance(s, dict):
        s = s.get("username") or s.get("name") or s.get("id")
    return str(s).strip().lower() if s else None


def mesurer_joueur(nom, items, taux):
    """Les ventes SoldComps d'une recherche du joueur -> (ventes gardees pour les archives, mesure du joueur)."""
    import cartes_match
    import score_slab
    import validation_iq
    import vendues
    import unicodedata
    n_ = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    gardees, vendeurs = [], set()
    for it in items or []:
        v = vendues._vers_vente(it, taux)
        if not v or not v.get("le"):
            continue
        t = v["titre"]
        # seulement SES cartes de hockey (Cam Ward le gardien n'est pas Cam Ward le quart-arriere)
        if score_slab.sport_autre(t) or not (validation_iq._RE_HOCKEY_SUR.search(t) or validation_iq._equipe_lnh(t)):
            continue
        if n_(cartes_match.joueur_du_titre(t) or "") != n_(nom):
            continue
        gardees.append(v)
        s = _vendeur(it)
        if s:
            vendeurs.add(s)
    if not gardees:
        return gardees, {"n": 0}
    jours = sorted(v["le"] for v in gardees)
    try:
        couvert = max(1, (datetime.fromisoformat(jours[-1]) - datetime.fromisoformat(jours[0])).days + 1)
    except ValueError:
        couvert = 90
    plein = len(items or []) >= 230                       # au plafond : le rythme vient des jours couverts
    par_jour = len(gardees) / (couvert if plein else 90)
    prix = [v["prix"] for v in gardees]
    return gardees, {"n": len(gardees), "jours_couverts": couvert, "plafond": plein, "par_semaine": round(par_jour * 7, 1),
                     "moyenne": round(_moy_taillee(prix), 2), "mediane": round(statistics.median(prix), 2),
                     "vendeurs": len(vendeurs) or None}


def balayer(n_max=None):
    """Une tranche du balayage (la boucle du serveur l'appelle souvent) : au plus le budget du jour."""
    import base_ventes
    import bareme_iq as bq
    import indice_joueurs
    import vendues
    if not vendues._cle() or time.time() < vendues._PANNE[0]:
        return {"ok": False, "raison": "soldcomps"}
    if _BLITZ["en_cours"]:
        return {"ok": False, "raison": "blitz en cours"}     # jamais les deux en meme temps (les memes recherches)
    d = lire_balayage()
    jour = datetime.now().strftime("%Y-%m-%d")
    fait = (d.get("jours") or {}).get(jour, 0)
    du_jour = -(-budget_semaine() // 7)
    # 17 nov 2026 (Mathieu : « y'a-t-il moyen d'accelerer ? ») : la PREMIERE mesure de chaque joueur se fait en rattrapage
    # (jusqu'a 300 par jour) : tout le monde est mesure en ~3 jours au lieu d'une semaine ; le meme nombre de recherches au
    # total (une par joueur), juste plus vite. Ensuite : le rythme normal de la semaine.
    try:
        _jamais = sum(1 for n in ((indice_joueurs.lire() or {}).get("indice") or {}) if n not in (d.get("joueurs") or {}))
    except Exception:
        _jamais = 0
    if _jamais:
        du_jour = max(du_jour, RATTRAPAGE_JOUR)
    reste = min(du_jour - fait, n_max or 10**9)
    if reste <= 0:
        return {"ok": True, "fait": 0, "raison": "budget du jour"}
    try:
        noms = list(((indice_joueurs.lire() or {}).get("indice") or {}).keys())
    except Exception:
        noms = []
    noms += [k for k in bq.JOUEURS_EXPERT if k not in noms]
    J = d.setdefault("joueurs", {})
    lim = (datetime.now() - timedelta(days=7)).isoformat()
    a_faire = sorted((n for n in noms if (J.get(n) or {}).get("le", "") < lim), key=lambda n: (J.get(n) or {}).get("le", ""))
    taux = vendues._taux_usd_cad() or 1.37
    site = (vendues.sites() or ["EBAY-US"])[0]
    n_fait = 0
    for nom in a_faire[:reste]:
        q = f"{nom} hockey"
        donnees, err = vendues._appel(q, site, usage="balayage")
        if err:
            vendues._noter_erreur(q, err)
            break
        items = (donnees or {}).get("items") or []
        gardees, m = mesurer_joueur(nom, items, taux)
        try:
            if gardees:
                base_ventes.noter(q, gardees, sport="hockey")
        except Exception:
            pass
        J[nom] = {**m, "le": datetime.now().isoformat(timespec="seconds")}
        n_fait += 1
        d.setdefault("jours", {})[jour] = fait + n_fait
        if n_fait % 10 == 0:
            _ecrire_bal(d)
    d["jours"] = {k: v for k, v in (d.get("jours") or {}).items() if k >= (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")}
    _ecrire_bal(d)
    return {"ok": True, "fait": n_fait, "restants": max(0, len(a_faire) - n_fait)}


# 18 nov 2026 (Mathieu : « on devrait utiliser des credits SoldComps pour le baseball ? » -> « oui go ») : une PETITE part fixe
# chaque semaine (LR_BALAYAGE_BB_SEMAINE, 150 recherches par defaut), seulement une fois le blitz du hockey fini : les joueurs
# de baseball de nos ventes, les plus vendus d'abord, une recherche « Nom baseball » chacun ; les ventes de baseball vont dans
# les archives du baseball (jamais melangees au hockey)
def budget_baseball():
    try:
        return max(0, int(os.environ.get("LR_BALAYAGE_BB_SEMAINE") or 150))
    except ValueError:
        return 150


def _noms_baseball(max_=400):
    import mlb
    J = mlb.joueurs()
    out = []
    for k, _n in mlb.noms_du_marche(max_=max_):
        out.append((J.get(k) or {}).get("nom") or k.title())
    if not out:
        out = [(v or {}).get("nom") or k.title() for k, v in list(J.items())[:max_] if (v or {}).get("niveau", "MLB") == "MLB"]
    return out


def balayer_baseball(n_max=None):
    import base_ventes
    import mlb
    import sports
    import vendues
    if not budget_baseball() or not vendues._cle() or time.time() < vendues._PANNE[0]:
        return {"ok": False, "raison": "soldcomps"}
    if _BLITZ["en_cours"] or (lire_balayage().get("blitz") or {}).get("etat") == "en cours":
        return {"ok": False, "raison": "blitz du hockey d'abord"}
    d = lire_balayage()
    jour = datetime.now().strftime("%Y-%m-%d")
    fait = (d.get("jours_bb") or {}).get(jour, 0)
    reste = min(-(-budget_baseball() // 7) - fait, n_max or 10**9)
    if reste <= 0:
        return {"ok": True, "fait": 0, "raison": "budget du jour"}
    B = d.setdefault("baseball", {})
    lim = (datetime.now() - timedelta(days=7)).isoformat()
    a_faire = [n for n in _noms_baseball() if (B.get(n) or {}).get("le", "") < lim]
    a_faire.sort(key=lambda n: (B.get(n) or {}).get("le", ""))
    taux = vendues._taux_usd_cad() or 1.37
    site = (vendues.sites() or ["EBAY-US"])[0]
    n_fait = 0
    for nom in a_faire[:reste]:
        q = f"{nom} baseball"
        donnees, err = vendues._appel(q, site, usage="balayage")
        if err:
            vendues._noter_erreur(q, err)
            break
        gardees = []
        for it in (donnees or {}).get("items") or []:
            v = vendues._vers_vente(it, taux)
            if not v or not v.get("le"):
                continue
            t = v["titre"]
            j = mlb.joueur_du_titre(t)
            if sports.sport_de(t) != "baseball" or not j or mlb._n(j.get("nom") or "") != mlb._n(nom):
                continue
            v.pop("photo", None)
            gardees.append(v)
        try:
            if gardees:
                base_ventes.noter(q, gardees, sport="baseball")
        except Exception:
            pass
        prix = [v["prix"] for v in gardees]
        B[nom] = {"n": len(gardees), "le": datetime.now().isoformat(timespec="seconds"),
                  **({"moyenne": round(_moy_taillee(prix), 2), "mediane": round(statistics.median(prix), 2)} if prix else {})}
        n_fait += 1
        d.setdefault("jours_bb", {})[jour] = fait + n_fait
    d["jours_bb"] = {k: v for k, v in (d.get("jours_bb") or {}).items() if k >= (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")}
    _ecrire_bal(d)
    return {"ok": True, "fait": n_fait, "restants": max(0, len(a_faire) - n_fait)}


def balayer_si_besoin():
    """La boucle du serveur : une tranche de 20 joueurs a la fois, en arriere-plan."""
    if _BAL["en_cours"]:
        return None
    _BAL["en_cours"] = True

    def tache():
        try:
            r = balayer(TRANCHE)
            if r.get("fait"):
                print("Balayage des joueurs : %s" % r, flush=True)
            rb = balayer_baseball(20)
            if rb.get("fait"):
                print("Balayage baseball : %s" % rb, flush=True)
        except Exception as e:
            print("Balayage des joueurs : " + repr(e), flush=True)
        finally:
            _BAL["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="balayage-joueurs").start()
    return True


# ---------------------------------------------------------------------------------------------------------------------
# 17 nov 2026 (Mathieu : « j'ai 25 k de credits SoldComps pas utilises qui finissent demain, donc goooo ») : le BLITZ.
# Un bouton admin : en arriere-plan, une requete par seconde, jusqu'a epuiser les credits (ou un plafond) :
#   1. chaque joueur suivi : sa recherche du balayage (« Nom hockey ») ;
#   2. puis ses sortes qui comptent (Young Guns, auto, patch, PSA 10, numerotee) : ses ventes des 90 jours, bien plus
#      completes ; tout va dans nos archives (base_ventes) et sert ensuite a tout (cote marche, comps, deals).
# Le disque compte : les ventes sont gardees sans leur photo, et le blitz s'arrete a BLITZ_MAX_VENTES lignes ajoutees.
# Il s'arrete aussi au premier « quota atteint » de SoldComps, ou s'il est arrete par l'admin.
# ---------------------------------------------------------------------------------------------------------------------
BLITZ_VARIANTES = ("young guns", "rookie auto", "patch", "psa 10", "numbered")
BLITZ_MAX_REQ = 22000
BLITZ_MAX_VENTES = 900000
_BLITZ = {"en_cours": False, "stop": False}


def _ordre_joueurs():
    """Les joueurs les plus importants d'abord (l'expert, puis la cote, puis le reste)."""
    import bareme_iq as bq
    import indice_joueurs
    try:
        I = (indice_joueurs.lire() or {}).get("indice") or {}
    except Exception:
        I = {}
    noms = list(dict.fromkeys(list(bq.JOUEURS_EXPERT) + list(I)))
    def poids(n):
        c = (I.get(n) or {}).get("criteres") or {}
        return -(bq.NOTE.get(bq.JOUEURS_EXPERT.get(n), 0) or float(c.get("demande") or 0))
    return sorted(noms, key=poids)


def blitz_etat():
    b = dict(lire_balayage().get("blitz") or {}, en_cours=_BLITZ["en_cours"])
    if b.get("etat") == "en cours" and not b["en_cours"]:
        b["etat"] = "interrompu"                        # le serveur a redemarre : il reprend tout seul (ou bouton Reprendre)
    return b


def blitz(max_req=BLITZ_MAX_REQ, reprendre=False):
    """17-18 nov 2026 : reprendre=True continue la ou il s'etait arrete (un redemarrage du serveur, un push, une panne) :
    la position est gardee a chaque recherche ; les compteurs continuent."""
    import base_ventes
    import vendues
    if not vendues._cle():
        return {"ok": False, "raison": "pas de clé SoldComps"}
    d = lire_balayage()
    b = d.setdefault("blitz", {})
    if not reprendre:
        b.update(lance_le=datetime.now().isoformat(timespec="seconds"), requetes=0, ventes=0, pos=0)
    elif "pos" not in b:
        b["pos"] = int(b.get("requetes") or 0)          # un blitz d'avant la reprise : on repart de son nombre de recherches
    b.update(etat="en cours", erreur=None)
    _ecrire_bal(d)
    taux = vendues._taux_usd_cad() or 1.37
    site = (vendues.sites() or ["EBAY-US"])[0]
    noms = _ordre_joueurs()
    J = d.setdefault("joueurs", {})
    taches = [(n, None) for n in noms] + [(n, v) for v in BLITZ_VARIANTES for n in noms]
    echecs = 0
    while b.get("pos", 0) < len(taches):
        if _BLITZ["stop"] or b["requetes"] >= max_req or b["ventes"] >= BLITZ_MAX_VENTES:
            break
        nom, var = taches[b.get("pos", 0)]
        q = f"{nom} hockey" if not var else f"{nom} {var}"
        donnees, err = vendues._appel(q, site, usage="blitz")
        if err:
            b["erreur"] = err
            if "quota" in err or "refusée" in err:
                break                                   # credits epuises ou cle refusee : on arrete
            echecs += 1                                 # une panne (503...) : on attend de plus en plus, puis on REESSAIE la meme
            _ecrire_bal(d)
            time.sleep(min(300, 10 * echecs))
            continue
        echecs = 0
        b["requetes"] += 1
        b["pos"] = b.get("pos", 0) + 1
        items = (donnees or {}).get("items") or []
        gardees, m = mesurer_joueur(nom, items, taux)
        for v in gardees:
            v.pop("photo", None)                        # le disque : pas de photo dans les archives du blitz
        try:
            if gardees:
                b["ventes"] += base_ventes.noter(q, gardees, sport="hockey") or 0
        except Exception:
            pass
        if not var:
            J[nom] = {**m, "le": datetime.now().isoformat(timespec="seconds")}
        if b["requetes"] % 10 == 0:
            _ecrire_bal(d)
    b["etat"] = "arrêté" if _BLITZ["stop"] else ("terminé" if b.get("pos", 0) >= len(taches) else "arrêté")
    b["total"] = len(taches)
    b["fini_le"] = datetime.now().isoformat(timespec="seconds")
    _ecrire_bal(d)
    return {"ok": True, **b}


def blitz_reprendre_si_besoin():
    """Au demarrage du serveur (un push redemarre Render) : un blitz qui etait « en cours » reprend tout seul."""
    b = lire_balayage().get("blitz") or {}
    if b.get("etat") == "en cours" and not _BLITZ["en_cours"]:
        return blitz_lancer(reprendre=True)
    return None


def blitz_lancer(reprendre=False):
    if _BLITZ["en_cours"]:
        return False
    _BLITZ.update(en_cours=True, stop=False)

    def tache():
        try:
            print("Blitz SoldComps : %s" % blitz(reprendre=reprendre), flush=True)
            passe_si_besoin(forcer=True)                 # la cote marche refaite avec tout ce qui est entre
        except Exception as e:
            print("Blitz SoldComps : " + repr(e), flush=True)
        finally:
            _BLITZ["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="blitz-soldcomps").start()
    return True
