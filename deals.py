"""
LOCKERROOM - les deals pour les acheteurs (24 oct 2026).

Mathieu : « revoir la page deal ... ajouter des filtres au debut pour le/les sports choisis, deal se finissant
le plus tot, meilleur deal etc. Comme dans hall of cardz, on doit pouvoir voir les comp en cliquant sur la
pastille du deal ».

Un chasseur partage par tout le serveur (les deals sont les memes pour tous) : chaque heure, quelques
recherches eBay (joueurs les plus demandes x cartes recrues du catalogue), prix fixe ET encans qui finissent
bientot. Une annonce est un deal si elle coute 70 % ou moins de la mediane des MEMES cartes (cartes_match).
Chaque deal garde ses comparables (pour la pastille). Budget : ~15 recherches par heure.
"""
import statistics
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

RATIO_DEAL = 0.70
PAR_TOUR_ENCANS = 30             # 26 oct 2026 (Mathieu : « aucune enchere se terminant ? ») : 30 recherches d encans par heure
VERSION = 4                      # 27 oct 2026 : valeur SURE (numeros speciaux, recence, coherence), vendeur, etat (v4)
ENCAN_H = 48                     # 26 oct 2026 (Mathieu : « tous les deals d'encheres de 48 h et moins ») ; avant : 6 h
ENCAN_VERIF_H = 6                # une recherche de ventes ciblee pour un encan : seulement s'il finit dans 6 h (la mise monte)
PAGES_ENCANS = 3                 # flux d'encans : jusqu'a 3 pages de 200 (les plus proches de la fin d'abord)
PAR_TOUR = 20                    # requetes prix fixe par tour (les plus recentes d'abord) : la liste entiere en 6 h
FRAICHEUR_S = 3600
_verrou = threading.Lock()
_ETAT = {"en_cours": False}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "deals_globaux.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _chemin())


_VALIDES = {}
_BANNIS = {"mt": None, "s": set()}


def _bannis():
    try:
        mt = os.path.getmtime(_chemin())
    except OSError:
        return _BANNIS["s"]
    if mt != _BANNIS["mt"]:
        d = lire()
        _BANNIS.update(mt=mt, s=set(d.get("bannis") or []))
    return _BANNIS["s"]


def corriger(item_id, valeur, gain, total):
    """26 oct 2026 - la fenetre d'une annonce a recalcule sa valeur avec les ventes de la meme carte : pas assez de
    ventes, ou plus sous 70 % de la valeur, ou pas de profit -> retiree ; sinon sa valeur est mise a jour."""
    iid = str(item_id)
    d = lire()
    l = d.get("deals") or []
    x = next((g for g in l if str(g.get("item_id")) == iid), None)
    if not x:
        return False
    with _verrou:
        d = lire()
        l = d.get("deals") or []
        if not valeur or (gain is not None and gain <= 1) or (total and total > valeur * RATIO_DEAL and not x.get("encan")):
            d["deals"] = [g for g in l if str(g.get("item_id")) != iid]
        else:
            for g in l:
                if str(g.get("item_id")) == iid:
                    g.update(valeur=valeur, ratio=round(total / valeur, 3) if total else g.get("ratio"))
        _ecrire(d)
    return True


def bannir(item_id):
    """26 oct 2026 - « pas un deal » signale par l'admin : retire pour tout le monde."""
    with _verrou:
        d = lire()
        d["bannis"] = (list(d.get("bannis") or []) + [str(item_id)])[-3000:]
        d["deals"] = [x for x in d.get("deals") or [] if str(x.get("item_id")) != str(item_id)]
        _ecrire(d)
    return {"ok": True}


def valide(x):
    """La carte passe-t-elle les regles ACTUELLES du filtre ? (les deals gardes d'avant une correction sont retires)."""
    import cartes_match
    if int(x.get("v") or 0) < VERSION or str(x.get("item_id")) in _bannis():
        return False
    k = (x.get("item_id"), x.get("q"), x.get("titre"))
    if k not in _VALIDES:
        if len(_VALIDES) > 5000:
            _VALIDES.clear()
        _VALIDES[k] = not x.get("q") or not cartes_match.raisons_refus(cartes_match.cible(x["q"]), x.get("titre") or "")
    return _VALIDES[k]


def requetes():
    """Les cartes que les acheteurs cherchent : recrues des produits du catalogue, joueurs les plus demandes d'abord."""
    import catalogue
    import valeurs
    dem = (valeurs._charger() or {}).get("joueurs") or {}
    out = []
    for p in catalogue.liste():
        try:
            prod = catalogue.charger(p["id"])
        except Exception:
            continue
        nom = str(prod.get("nom") or "")
        insert = "young guns" if "series" in nom.lower() or "extended" in nom.lower() else \
                 "future watch" if "sp authentic" in nom.lower() else "rookie"
        for c in prod.get("cartes") or []:
            if not c.get("recrue") or not c.get("joueur"):
                continue
            j = str(c["joueur"]).split("/")[0].strip()
            out.append({"q": f"{j} {insert}", "joueur": j, "sport": prod.get("sport") or "hockey",
                        "poids": float(dem.get(j) or 1.0)})
    vus, uniq = set(), []
    for r in sorted(out, key=lambda x: -x["poids"]):
        if r["q"].lower() not in vus:
            vus.add(r["q"].lower())
            uniq.append(r)
    return uniq[:120]


PORT_INCONNU = 15.0              # 27 oct 2026 : port non affiche (calcule a l'adresse) -> on compte 15 $ pour ne pas surestimer le deal


def _total(a):
    port = a.get("port_cad")
    return round((a.get("prix_cad") or 0) + (PORT_INCONNU if port is None and a.get("prix_cad") else (port or 0)), 2)


def memes_ventes(cib, ventes):
    """Les ventes de la MEME carte (sans doublons : une vente vue par deux recherches ne compte qu'une fois)."""
    import cartes_match
    vus, out = set(), []
    for v in ventes or []:
        if not v.get("prix"):
            continue
        k = v.get("url") or f"{v.get('titre')}|{v.get('le')}|{v.get('prix')}"
        if k in vus:
            continue
        vus.add(k)
        if not cartes_match.raisons_refus(cib, v.get("titre") or ""):
            out.append(v)
    return out


# 27 oct 2026 (Mathieu : « quand on va etre live, je veux pas que les utilisateurs aient de faux deals ou de faux prix »)
# Une valeur ne sert a juger un deal que si elle est SURE :
#   - les numeros speciaux (1/99, 99/99, 1/1) ne comparent jamais une copie ordinaire ;
#   - les ventes recentes d'abord (60 jours si on en a 3), et la tendance : si les 3 dernieres ventes sont plus basses,
#     c'est elles qui comptent (une recrue qui baisse) ;
#   - 3 ventes au moins, ou 2 ventes recentes (45 jours) qui se ressemblent (ecart de 35 % au plus) ;
#   - des ventes coherentes entre elles : trop d'ecart = on ne sait pas -> pas de deal.
MIN_VENTES_SURES = 3
JOURS_RECENTS = 60


def _jours(v, maint=None):
    try:
        d = datetime.fromisoformat(str(v.get("le"))[:10])
    except ValueError:
        return 999
    return ((maint or datetime.now()).replace(tzinfo=None) - d).days


def valeur_sure(pv, titre_annonce=""):
    """(valeur, ventes retenues) ou (None, raison)."""
    import cartes_match
    if not cartes_match.serie_speciale(titre_annonce):
        pv = [v for v in pv if not cartes_match.serie_speciale(v.get("titre") or "")]
    pv = [v for v in pv if not cartes_match.abimee(v.get("titre") or "")]
    recentes = [v for v in pv if _jours(v) <= JOURS_RECENTS]
    if len(recentes) >= MIN_VENTES_SURES:
        pv = recentes
    if len(pv) < 2:
        return None, "pas assez de ventes"
    prix = sorted(float(v["prix"]) for v in pv)
    if len(pv) == 2:
        if prix[1] > prix[0] * 1.35 or any(_jours(v) > 45 for v in pv):
            return None, "2 ventes trop differentes ou trop vieilles"
        return round(prix[0], 2), pv                         # 2 ventes : la plus basse
    m, garde = cartes_match.mediane_robuste(prix)
    if len(garde) < MIN_VENTES_SURES:
        return None, "ventes trop dispersees"
    if len(garde) >= 4:
        q1, _q2, q3 = statistics.quantiles(garde, n=4)
    if len(garde) >= 4 and (q3 - q1) > max(0.9 * m, 3.0):      # 3 $ : une carte a 1-3 $ varie toujours un peu
        return None, "ventes trop dispersees"
    if len(garde) == 3 and garde[-1] > garde[0] * 2.5:
        return None, "ventes trop dispersees"
    dernieres = sorted(pv, key=lambda v: str(v.get("le") or ""), reverse=True)[:3]
    if len(dernieres) == 3:
        m = min(m, statistics.median(float(v["prix"]) for v in dernieres))
    return round(m, 2), pv


def valeur_annonce(a, ventes, actives, cib=None):
    """La valeur de LA carte d'une annonce : ventes de la meme carte, seulement si elle est SURE (valeur_sure) ; les
    autres annonces de la meme carte (moins 15 %) ne servent que de plafond. -> (valeur, source, n, ventes) ou None."""
    import cartes_match
    cib = cib or cartes_match.cible_titre(a.get("titre") or "")
    pv = memes_ventes(cib, ventes)
    if len(pv) < 2:
        return None
    m, pv = valeur_sure(pv, a.get("titre") or "")
    if m is None:
        return None
    pa = [_total(x) for x in actives or [] if x.get("item_id") != a.get("item_id")
          and not cartes_match.raisons_refus(cib, x.get("titre") or "")]
    if len(pa) >= 3:
        m = min(m, cartes_match.mediane_robuste(pa)[0] * 0.85)
    pv.sort(key=lambda v: str(v.get("le") or ""), reverse=True)
    return round(m, 2), "vendues", len(pv), [{k: v.get(k) for k in ("titre", "prix", "le", "photo", "url")} for v in pv[:6]]


def _diag(d, **k):
    """26 oct 2026 (Mathieu : « sommes-nous certains ? ») : ce que le chasseur a vraiment verifie, heure par heure."""
    h = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    g = d.setdefault("diag", {})
    b = g.setdefault(h, {})
    for c, v in k.items():
        b[c] = b.get(c, 0) + v
    for c in sorted(g)[:-30]:
        g.pop(c, None)


def diagnostic(d=None):
    """Les 24 dernieres heures : recherches, annonces de la bonne carte, encans finissant dans 48 h, refus par raison."""
    d = d or lire()
    lim = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H")
    tot = {}
    for h, b in (d.get("diag") or {}).items():
        if h >= lim:
            for c, v in b.items():
                tot[c] = tot.get(c, 0) + v
    return tot


class Bassin:
    """26 oct 2026 (Mathieu : « on doit trouver le maximum ») : TOUTES les ventes deja connues (base des ventes + cache
    SoldComps des 3 derniers jours), indexees par mot. La valeur d'une annonce se cherche dans toutes ces ventes, pas
    seulement dans celles de sa recherche : beaucoup plus d'annonces ont leurs 2 ventes de la meme carte, sans appel de plus.
    Memoire bornee : les MAX ventes les plus recentes des `jours` derniers jours, en tuples compacts."""
    MAX = 150000

    def __init__(self, jours=90, charger=True):
        self.par_mot, self.vus, self.n = {}, set(), 0
        self.depuis = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
        if charger:
            self._charger()

    def ajouter(self, ventes):
        import cartes_match
        for v in ventes or []:
            if self.n >= self.MAX or not v.get("prix") or not v.get("titre") or str(v.get("le") or "9")[:10] < self.depuis:
                continue
            k = v.get("url") or f"{v['titre']}|{v.get('le')}|{v['prix']}"
            if k in self.vus:
                continue
            self.vus.add(k)
            self.n += 1
            tl = cartes_match.norm(v["titre"])
            e = (" " + tl + " ", v["titre"], float(v["prix"]), v.get("le"), v.get("photo"), v.get("url"))
            for w in set(tl.split()):
                if len(w) >= 4 and w.isalpha():
                    self.par_mot.setdefault(w, []).append(e)

    def _charger(self):
        import sqlite3
        try:
            import vendues
            c = vendues._cx()
            try:
                for (brut,) in c.execute("SELECT ventes FROM cache ORDER BY le DESC"):
                    try:
                        self.ajouter(json.loads(brut))
                    except ValueError:
                        pass
            finally:
                c.close()
        except sqlite3.Error:
            pass
        try:
            import base_ventes
            c = base_ventes._cx()
            try:
                self.ajouter([{"titre": a, "prix": b, "le": cc, "photo": d, "url": e} for a, b, cc, d, e in
                              c.execute("SELECT titre, prix, le, photo, url FROM ventes WHERE le >= ? ORDER BY le DESC LIMIT ?",
                                        (self.depuis, self.MAX))])
            finally:
                c.close()
        except (sqlite3.Error, ImportError):
            pass

    def candidats(self, cib):
        """Les ventes qui ont le mot le plus rare du joueur et tous les mots exiges (ensuite raisons_refus garde la meme carte)."""
        mots = [m for m in (cib.get("joueur") or "").split() + list(cib.get("mots") or []) if len(m) >= 4 and m.isalpha()]
        if not mots:
            return []
        cle = min(mots, key=lambda m: len(self.par_mot.get(m, ())))
        req = [" " + w + " " for m in cib.get("mots") or [] for w in m.split() if len(w) >= 2]
        # meme carte : la plupart de ses mots d'identite (produit, insert), autographe et gradation pareils
        ident = [" " + w + " " for w in cib.get("ident") or ()]
        tol = len(ident) // 3
        auto, grade = bool(cib.get("auto")), bool(cib.get("grade") or cib.get("veut_grade"))
        out = []
        for tl, ti, p, le, ph, u in self.par_mot.get(cle, ()):
            if not all(w in tl for w in req):
                continue
            if ident and sum(1 for w in ident if w not in tl) > tol:
                continue
            if not auto and (" auto " in tl or "autograph" in tl):
                continue                                # vente d'une auto, notre carte n'en est pas une
            if not grade and _RE_GRADE_V.search(tl):
                continue
            out.append({"titre": ti, "prix": p, "le": le, "photo": ph, "url": u})
            if len(out) >= 300:                         # les plus recentes suffisent pour la mediane
                break
        return out


import re as _re
_RE_GRADE_V = _re.compile(r" (psa|bgs|sgc|cgc|beckett) ?\d")
VERIF_JOUR = 40                  # recherches SoldComps ciblees par jour pour confirmer une annonce prometteuse


def _verificateur(d, st, bassin):
    """Une annonce qui a l'air d'un deal mais sans 2 ventes connues de la MEME carte : une recherche SoldComps de CETTE
    carte (budget : LR_DEALS_VERIF_JOUR, 40 par jour par defaut), puis on la juge sur ses vraies ventes."""
    import cartes_match
    import vendues
    try:
        max_ = int(os.environ.get("LR_DEALS_VERIF_JOUR") or VERIF_JOUR)
    except ValueError:
        max_ = VERIF_JOUR
    jour = datetime.now().strftime("%Y-%m-%d")
    v = d.setdefault("verif", {})
    if v.get("jour") != jour:
        v.clear()
        v.update(jour=jour, n=0)
    faites = set()

    def f(cib):
        q = (cartes_match.requete_ebay(cib) or "").strip()
        if not q or q in faites:
            return None
        if v["n"] >= max_:
            st["verif_budget"] = st.get("verif_budget", 0) + 1
            return None
        faites.add(q)
        r = vendues.rechercher(q, fond=True)
        if r.get("erreur"):
            st["erreurs_ventes"] = st.get("erreurs_ventes", 0) + 1
            return None
        if not r.get("cache"):
            v["n"] += 1
        st["verifs"] = st.get("verifs", 0) + 1
        bassin.ajouter(r.get("ventes"))
        return r.get("ventes") or []
    return f


VERIF_TARD_H = 30                # 27 oct 2026 : un encan de hit qui finit dans 6 a 30 h est verifie a la fin du tour, s'il reste du budget
HIT_MIN = 25.0                   # 27 oct 2026 : un hit (auto, patch, numerotee /99 et moins) de 25 $ et plus (port compris) vaut une verification


def _hit(cib):
    s = cib.get("serie")
    return bool(cib.get("auto") or cib.get("patch") or (s and int(s) <= 99))


def _prometteuse(a, t, pv, pa, maint, cib=None):
    """Vaut une recherche de ventes ? une seule vente connue et le prix est sous 70 % de celle-ci, ou 3 annonces de la
    meme carte et le prix est sous 60 % de leur mediane. Encan : seulement s'il finit dans 6 h (la mise monte).
    27 oct 2026 (Mathieu : la Pride of a Nation Stutzle /99 a 101 $ « devrait etre dans notre radar ») : un ENCAN de hit
    (auto, patch ou /99 et moins) de 25 $ et plus (port compris) qui finit dans 6 h, meme sans aucune vente connue."""
    import cartes_match
    if a.get("encan"):
        try:
            if datetime.fromisoformat(str(a.get("fin")).replace("Z", "+00:00")) - maint > timedelta(hours=ENCAN_VERIF_H):
                return False
        except ValueError:
            return False
    if len(pv) == 1 and t <= pv[0]["prix"] * RATIO_DEAL:
        return True
    if a.get("encan") and not pv and cib and _hit(cib) and t >= HIT_MIN:
        return True
    return len(pa) >= 3 and t <= (cartes_match.mediane_robuste(pa)[0] or 0) * 0.6


def vendeur_risque(a):
    """Vendeur sans historique ou mal note : le « deal » est trop souvent une arnaque ou une contrefacon."""
    pct, score = a.get("vendeur_pct"), a.get("vendeur_score")
    try:
        return (pct not in (None, "") and float(pct) < 97) or (score not in (None, "") and int(score) < 10)
    except (TypeError, ValueError):
        return False


def _juger(a, r, brut_v, actives, maint, deals, st, ventes_requete=None, comps=None, bassin=None, verif=None):
    """Une annonce : deal ou non (et pourquoi). Les memes regles pour le prix fixe, les encans et les flux."""
    import cartes_match
    t = _total(a)
    if not t or a.get("item_id") in st.setdefault("_vus", set()):
        return
    st["_vus"].add(a.get("item_id"))
    fin = a.get("fin")
    if a.get("encan"):
        try:
            fin_dt = datetime.fromisoformat(str(fin).replace("Z", "+00:00"))
        except ValueError:
            return
        if fin_dt - maint > timedelta(hours=ENCAN_H) or fin_dt < maint:       # encan : seulement ceux qui finissent dans 48 h
            return
    cib = cartes_match.cible_titre(a.get("titre") or "")
    if cib.get("exclu") or not cib.get("joueur"):
        return                                                                  # lot, ou on ne sait pas quel joueur
    if cartes_match.abimee(a.get("titre") or "") or vendeur_risque(a):
        st["ecartees"] = st.get("ecartees", 0) + 1                              # abimee, douteuse, ou vendeur sans historique
        deals.pop(a.get("item_id"), None)
        return
    st["annonces"] = st.get("annonces", 0) + 1
    if a.get("encan"):
        st["encans_fen"] = st.get("encans_fen", 0) + 1
    tout_v = list(brut_v or []) + (bassin.candidats(cib) if bassin else [])
    va = valeur_annonce(a, tout_v, actives, cib=cib)
    if not va and verif:
        pv = memes_ventes(cib, tout_v)
        pa = [_total(x) for x in actives or [] if x.get("item_id") != a.get("item_id")
              and not cartes_match.raisons_refus(cib, x.get("titre") or "")]
        if _prometteuse(a, t, pv, pa, maint, cib):
            nv = verif(cib)
            if nv:
                va = valeur_annonce(a, tout_v + nv, actives, cib=cib)
    if not va and verif and a.get("encan") and t >= HIT_MIN and _hit(cib) and not memes_ventes(cib, tout_v):
        try:
            if datetime.fromisoformat(str(fin).replace("Z", "+00:00")) - maint <= timedelta(hours=VERIF_TARD_H):
                st.setdefault("_tard", []).append((a, r, cib))      # verifie a la fin du tour (budget restant)
        except ValueError:
            pass
    if not va:
        st["sans_ventes"] = st.get("sans_ventes", 0) + 1
        deals.pop(a["item_id"], None)                 # revue : plus un deal (encan dont la mise a monte...)
        return
    med_a, source_a, n_a, ventes_a = va
    if t > med_a * RATIO_DEAL:
        st["trop_cher"] = st.get("trop_cher", 0) + 1
        deals.pop(a["item_id"], None)
        return
    st["deals"] = st.get("deals", 0) + 1
    import sports
    joueur = r.get("joueur") or " ".join(w.capitalize() for w in cib["joueur"].split())
    sport = r.get("sport") or sports.detecter(a.get("titre") or "", defaut="hockey")
    deals[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"), "url": a.get("url"),
                           "valeur": med_a, "ratio": round(t / med_a, 3), "encan": bool(a.get("encan")), "fin": fin,
                           "mises": a.get("mises"), "sport": sport, "joueur": joueur, "q": r.get("q"), "flux": r.get("flux"),
                           "n": n_a, "valeur_source": source_a, "vendues": ventes_a or ventes_requete or [],
                           # 27 oct 2026 : encan - la mise maximale pour que ca reste un deal (70 % de la valeur, port compris)
                           "port": a.get("port_cad"), "mise_max": round(med_a * RATIO_DEAL - (a.get("port_cad") or 0), 2) if a.get("encan") else None,
                           "comps": comps or [], "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION}


def _ventes(q, cache_seul=False):
    """Les ventes SoldComps d'une recherche (3 jours en cache). cache_seul : jamais d'appel (passe des encans)."""
    import cartes_match
    import vendues
    q_v = cartes_match.requete_ebay(cartes_match.cible(q)) or q
    if cache_seul:
        return vendues.en_cache(q_v), None
    r = vendues.rechercher(q_v, fond=True)
    return r.get("ventes") or [], r.get("erreur")


# 27 oct 2026 - licence API eBay (§8.1(c)) : une annonce affichee n'a jamais plus de 6 h de retard sur eBay.
# Un deal (achat immediat OU encan) qui n'a pas ete revu sur eBay depuis 6 h sort de la liste.
FRAICHEUR_EBAY_H = 5             # 5 h + 1 h au plus entre deux tours = jamais plus de 6 h


def _ranger(d, deals, maint):
    limite = (maint - timedelta(hours=FRAICHEUR_EBAY_H)).isoformat()
    garde_ = []
    for x in deals.values():
        if x.get("encan"):
            try:
                if datetime.fromisoformat(str(x.get("fin")).replace("Z", "+00:00")) < maint:
                    continue
            except ValueError:
                continue
        if str(x.get("vu_le") or "") < limite:
            continue
        if not valide(x):
            continue
        garde_.append(x)
    garde_.sort(key=lambda x: x["ratio"])
    return garde_[:800]


def _verifier_tard(st, deals, maint, bassin, verif):
    """27 oct 2026 (Mathieu : la Savoie Draft Day Marks /35 a 50 $, qui finit dans 25 h) : les encans de hits sans ventes
    connues qui finissent dans 6 a 30 h, verifies a la fin du tour avec le budget qui reste, les plus proches de la fin d'abord."""
    for a, r, cib in sorted(st.pop("_tard", []), key=lambda x: str(x[0].get("fin"))):
        avant = st.get("verif_budget", 0)
        nv = verif(cib)
        if st.get("verif_budget", 0) > avant:
            break                                        # budget du jour epuise
        st["_vus"].discard(a.get("item_id"))
        _juger(a, r, nv or [], [], maint, deals, st, bassin=bassin, verif=None)


def _sauver(d, deals, maint, st, **champs):
    garde_ = _ranger(d, deals, maint)
    st.pop("_vus", None)
    st.pop("_tard", None)
    with _verrou:
        d2 = lire()
        d2.update(deals=garde_, **champs)
        if "verif" in d:
            d2["verif"] = d["verif"]
        _diag(d2, **st)
        _ecrire(d2)
    return garde_


def chasser(n=PAR_TOUR, rechercher=None, bassin=None):
    """Prix fixe : n requetes joueur (on reprend la ou on etait), les annonces les plus RECENTES d'abord (les bons prix
    partent vite) ; deals gardes 48 h."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    bassin = bassin if bassin is not None else Bassin()
    d = lire()
    reqs = requetes()
    if not reqs:
        return {"ok": True, "deals": 0}
    i0 = int(d.get("curseur") or 0) % len(reqs)
    lot = (reqs[i0:] + reqs[:i0])[:n]
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    for r in lot:
        try:
            fixes = rechercher(r["q"], categorie="261328", limite=100, fond=True, recentes=True)
        except (RuntimeError, OSError):
            st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
            break
        st["requetes"] = st.get("requetes", 0) + 1
        _c, memes, _e = cartes_match.filtrer(r["q"], fixes)
        # chaque annonce a SA valeur, celle des ventes de la MEME carte (2 au moins), sinon pas de deal
        brut_v, err = _ventes(r["q"])
        if err:
            st["erreurs_ventes"] = st.get("erreurs_ventes", 0) + 1
        bassin.ajouter(brut_v)
        med = cartes_match.mediane_robuste([_total(x) for x in memes])[0] if memes else None
        comps = sorted(({"titre": x["titre"], "total": _total(x), "photo": x.get("photo"), "url": x.get("url")} for x in memes),
                       key=lambda x: abs(x["total"] - (med or 0)))[:8]
        for a in memes:
            _juger(a, r, brut_v, memes, maint, deals, st, comps=comps, bassin=bassin, verif=verif)
    garde_ = _sauver(d, deals, maint, st, curseur=(i0 + len(lot)) % len(reqs), maj=maint.isoformat(timespec="seconds"))
    return {"ok": True, "deals": len(garde_), "nouveaux": st.get("deals", 0), "stats": st}


def encans(n=PAR_TOUR_ENCANS, rechercher=None, bassin=None):
    """26 oct 2026 (Mathieu : « aucune enchere se terminant ? ») : chaque heure, n recherches d'ENCANS (ceux qui finissent
    le plus tot, 48 h et moins) : toute la liste en 3 h. La valeur vient des ventes
    deja connues (le bassin) et, pour un encan prometteur qui finit dans 3 h, d'une recherche ciblee."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    bassin = bassin if bassin is not None else Bassin()
    d = lire()
    reqs = requetes()
    if not reqs:
        return {"ok": True}
    i0 = int(d.get("curseur_e") or 0) % len(reqs)
    lot = (reqs[i0:] + reqs[:i0])[:n]
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    for r in lot:
        try:
            ench = rechercher(r["q"], categorie="261328", limite=100, fond=True, encheres=True)
        except (RuntimeError, OSError):
            st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
            break
        st["requetes_encans"] = st.get("requetes_encans", 0) + 1
        _c, memes_e, _e = cartes_match.filtrer(r["q"], ench)
        if not memes_e:
            continue
        brut_v, _err = _ventes(r["q"], cache_seul=True)
        for a in memes_e:
            _juger(a, r, brut_v or [], [], maint, deals, st, bassin=bassin, verif=verif)
    _verifier_tard(st, deals, maint, bassin, verif)
    garde_ = _sauver(d, deals, maint, st, curseur_e=(i0 + len(lot)) % len(reqs))
    return {"ok": True, "deals": len(garde_), "stats": st}


# 26 oct 2026 (Mathieu : « on doit trouver le maximum ») : en plus des recherches par joueur, des FLUX larges : toutes les
# nouvelles annonces et tous les encans qui finissent de ces familles de cartes, chaque heure (200 annonces par appel).
# Chaque annonce est jugee sur les ventes de SA carte (le bassin), comme les autres.
FLUX = [("young guns", "hockey"), ("young guns canvas", "hockey"), ("young guns exclusives", "hockey"),
        ("upper deck rookie auto", "hockey"), ("rookie patch auto hockey", "hockey"), ("future watch auto", "hockey"),
        ("sp authentic rookie", "hockey"), ("the cup rookie", "hockey"), ("o-pee-chee platinum rookie", "hockey"),
        ("psa 10 rookie hockey", "hockey"), ("upper deck ice rookie", "hockey"), ("artifacts rookie", "hockey"),
        ("black diamond rookie", "hockey"), ("synergy rookie", "hockey"), ("upper deck numbered rookie", "hockey"),
        ("mcdavid", "hockey"), ("bedard", "hockey"),
        ("prizm rookie", None), ("topps chrome rookie", None), ("bowman chrome 1st auto", None)]


# 27 oct 2026 (Mathieu : « pourquoi c'est juste des Young Guns ? ») : les hits des autres produits (autos, patchs,
# numerotees). 5 flux par heure en rotation : chacun revient aux 3 h, l'appel eBay le plus cher reste borne.
FLUX_HITS = [("ud black auto", "hockey"), ("spx auto patch", "hockey"), ("patch auto /99 hockey", "hockey"),
             ("auto patch /49 hockey", "hockey"), ("auto /25 hockey", "hockey"), ("1/1 hockey card", "hockey"),
             ("the cup auto patch", "hockey"), ("sp game used auto", "hockey"), ("premier auto patch", "hockey"),
             ("ice auto patch", "hockey"), ("artifacts auto patch", "hockey"), ("trilogy auto", "hockey"),
             ("ultimate collection auto", "hockey"), ("black diamond auto", "hockey"), ("synergy auto", "hockey")]
HITS_PAR_TOUR = 5


def flux_hits(curseur):
    """Les flux de hits de ce tour, et le curseur du prochain."""
    if os.environ.get("LR_DEALS_FLUX") or not FLUX_HITS:
        return [], 0
    i0 = int(curseur or 0) % len(FLUX_HITS)
    return (FLUX_HITS[i0:] + FLUX_HITS[:i0])[:HITS_PAR_TOUR], (i0 + HITS_PAR_TOUR) % len(FLUX_HITS)


def flux_liste():
    e = os.environ.get("LR_DEALS_FLUX")                 # « young guns;canvas » pour remplacer la liste
    return [(x.strip(), None) for x in e.split(";") if x.strip()] if e else FLUX


def flux(rechercher=None, bassin=None):
    """Chaque flux : les 200 annonces prix fixe les plus recentes + les 200 encans qui finissent le plus tot."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    bassin = bassin if bassin is not None else Bassin()
    d = lire()
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    try:
        pages = max(1, int(os.environ.get("LR_DEALS_PAGES_ENCANS") or PAGES_ENCANS))
    except ValueError:
        pages = PAGES_ENCANS
    limite_fin = (maint + timedelta(hours=ENCAN_H)).isoformat().replace("+00:00", "Z")
    hits, curseur_h = flux_hits(d.get("curseur_h"))
    for q, sport in flux_liste() + hits:
        r = {"q": None, "flux": q, "sport": sport, "joueur": None}
        # prix fixe : les 200 plus recentes ; encans : page apres page (200) tant qu'ils finissent dans 48 h
        for ench, page in [(False, 0)] + [(True, k) for k in range(pages)]:
            try:
                l = rechercher(q, categorie="261328", limite=200, fond=True, encheres=ench, recentes=not ench, flux=True, offset=200 * page)
            except (RuntimeError, OSError):
                st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
                break
            st["requetes_flux"] = st.get("requetes_flux", 0) + 1
            l = [a for a in l if cartes_match.est_carte(a.get("titre") or "")]
            for a in l:
                _juger(a, r, [], [] if ench else l, maint, deals, st, bassin=bassin, verif=verif)
            if ench and (len(l) < 150 or not l or str(l[-1].get("fin") or "9") > limite_fin):
                break                                   # derniere page, ou on depasse 48 h
    _verifier_tard(st, deals, maint, bassin, verif)
    garde_ = _sauver(d, deals, maint, st, curseur_h=curseur_h)
    return {"ok": True, "deals": len(garde_), "stats": st}


REVERIF_PAR_TOUR = 40           # 27 oct 2026 : deals revus directement sur eBay chaque tour (prix, fin, encore en vente)
REVERIF_APRES_H = 1.5


def reverifier(lire_article=None, max_=None):
    """Chaque deal garde, revu sur eBay (Browse getItem) s'il n'a pas ete vu depuis 1 h 30 : prix et port du moment,
    encore en vente, toujours 70 % de sa valeur ou moins. Sinon il sort. Les plus vieux d'abord."""
    import cartes_match
    import ebay_compte
    lire_article = lire_article or (lambda i: ebay_compte.article(i, fond=True))
    try:
        max_ = int(max_ or os.environ.get("LR_DEALS_REVERIF") or REVERIF_PAR_TOUR)
    except ValueError:
        max_ = REVERIF_PAR_TOUR
    d = lire()
    maint = datetime.now(timezone.utc)
    limite = (maint - timedelta(hours=REVERIF_APRES_H)).isoformat(timespec="seconds")
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    for x in sorted(deals.values(), key=lambda x: str(x.get("vu_le") or "")):
        if st.get("reverifies", 0) >= max_:
            break
        if str(x.get("vu_le") or "") >= limite:
            continue
        st["reverifies"] = st.get("reverifies", 0) + 1
        try:
            a = lire_article(x["item_id"])
        except RuntimeError as e:
            if "404" in str(e) or "11001" in str(e):
                deals.pop(x["item_id"], None)          # annonce finie ou retiree
                st["reverif_finies"] = st.get("reverif_finies", 0) + 1
            continue
        except OSError:
            continue
        t = _total(a)
        fini = False
        try:
            fini = bool(a.get("fin")) and datetime.fromisoformat(str(a["fin"]).replace("Z", "+00:00")) < maint
        except ValueError:
            pass
        if fini or not t or cartes_match.abimee(a.get("titre") or "") or t > (x.get("valeur") or 0) * RATIO_DEAL:
            deals.pop(x["item_id"], None)
            st["reverif_retires"] = st.get("reverif_retires", 0) + 1
            continue
        x.update(total=t, ratio=round(t / x["valeur"], 3), mises=a.get("mises", x.get("mises")), fin=a.get("fin") or x.get("fin"),
                 port=a.get("port_cad"), vu_le=maint.isoformat(timespec="seconds"))
        if x.get("encan"):
            x["mise_max"] = round(x["valeur"] * RATIO_DEAL - (a.get("port_cad") or 0), 2)
    garde_ = _sauver(d, deals, maint, st)
    return {"ok": True, "deals": len(garde_), "stats": st}


def chasser_si_besoin():
    """En arriere-plan, au plus une fois par heure, jamais deux a la fois."""
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
            b = Bassin()                                 # une fois par tour : toutes les ventes connues
            try:
                reverifier()                             # d'abord : les deals deja affiches, revus sur eBay
            except Exception as e:
                print("Deals (revue) : " + repr(e), flush=True)
            for f in (chasser, encans, flux):
                try:
                    f(bassin=b)
                except Exception as e:
                    print("Deals : " + repr(e), flush=True)
            with _verrou:
                d = lire()
                d["bassin"] = b.n
                _ecrire(d)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="deals").start()
    return True
