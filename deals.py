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
import re
import statistics
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

RATIO_DEAL = 0.70
RATIO_PRES = 0.85                # 27 oct 2026 : « a surveiller » = 70 a 85 % de la valeur (jamais affiche comme un deal)
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


_LU = {"cle": None, "d": {}}


def lire_vite():
    """28 oct 2026 (Mathieu : « c'est tres lent de changer de page ») : LECTURE SEULE (ne pas modifier le resultat).
    Le fichier des deals (plusieurs Mo) n'est relu que s'il a change : l'ecran Deals le lisait 4 fois par appel."""
    try:
        st = os.stat(_chemin())
    except OSError:
        return {}
    cle = (st.st_mtime_ns, st.st_size)
    if _LU["cle"] != cle:
        _LU.update(cle=cle, d=lire())
    return _LU["d"]


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
        d = lire_vite()
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
        retirer = not valeur or (gain is not None and gain <= 1) or (total and total > valeur * RATIO_DEAL and not x.get("encan"))
        if not retirer:
            for g in l:
                if str(g.get("item_id")) == iid:
                    g.update(valeur=valeur, ratio=round(total / valeur, 3) if total else g.get("ratio"))
                    if g.get("encan"):          # 27 oct 2026 (revue) : la mise max suit la nouvelle valeur
                        g["mise_max"] = round(valeur * RATIO_DEAL - (g.get("port") or 0), 2)
                        if g["mise_max"] <= (g.get("total") or 0) - (g.get("port") or 0):
                            retirer = True
        if retirer:
            d["deals"] = [g for g in l if str(g.get("item_id")) != iid]
            _noter_retires(d, [iid])            # un tour de chasse deja commence ne le remettra pas
        _ecrire(d)
    return True


RETIRES_JOURS = 7


def _noter_retires(d, ids):
    """27 oct 2026 (revue) : annonces retirees (vendues, corrigees, plus un deal) : elles ne reviennent ni dans la liste,
    ni dans « a surveiller », ni dans la liste de secours."""
    maint = datetime.now(timezone.utc)
    r = {k: v for k, v in (d.get("retires") or {}).items() if str(v) >= (maint - timedelta(days=RETIRES_JOURS)).isoformat()}
    for i in ids:
        r[str(i)] = maint.isoformat(timespec="seconds")
    d["retires"] = r
    return r


def bannir(item_id):
    """26 oct 2026 - « pas un deal » signale par l'admin : retire pour tout le monde."""
    with _verrou:
        d = lire()
        d["bannis"] = (list(d.get("bannis") or []) + [str(item_id)])[-3000:]
        d["deals"] = [x for x in d.get("deals") or [] if str(x.get("item_id")) != str(item_id)]
        _ecrire(d)
    return {"ok": True}


def _rejuger(x):
    """27 oct 2026 (Mathieu : « les users doivent TOUJOURS voir quelque chose ») : un deal d'une version d'avant n'est
    plus efface d'un coup ; il est rejuge avec les regles d'aujourd'hui sur ses ventes gardees. S'il passe, il reste."""
    import cartes_match
    if cartes_match.abimee(x.get("titre") or ""):
        return False
    m, _pv = valeur_sure([v for v in x.get("vendues") or [] if v.get("prix")], x.get("titre") or "")
    if not m or not x.get("total") or x["total"] > m * RATIO_DEAL:
        return False
    x.update(valeur=m, ratio=round(x["total"] / m, 3), v=VERSION)
    if x.get("encan"):
        x["mise_max"] = round(m * RATIO_DEAL - (x.get("port") or 0), 2)
    return True


def valide(x):
    """La carte passe-t-elle les regles ACTUELLES du filtre ? (une ancienne version est rejugee, pas effacee)."""
    import cartes_match
    if str(x.get("item_id")) in _bannis():
        return False
    if int(x.get("v") or 0) < VERSION and not _rejuger(x):
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
    uniq = uniq[:110]
    # 28 oct 2026 (Mathieu : « les deals sont presque juste des Future Watch et des Young Guns ; ou sont les auto patch de
    # veterans ou de legendes ? ») : les veterans et les legendes aussi, en autos et en patchs, intercales avec les recrues
    # (1 pour 1) : le meme nombre de recherches par heure, mieux reparties
    ved = []
    for j in VEDETTES:
        for genre in ("auto", "patch"):
            q = f"{j} {genre}"
            if q.lower() not in vus:
                vus.add(q.lower())
                ved.append({"q": q, "joueur": j, "sport": "hockey", "poids": float(dem.get(j) or 1.0), "vedette": True})
    mix, i, k = [], 0, 0
    while i < len(uniq) or k < len(ved):         # 28 oct (« encore que des rookies ») : 1 vedette, 1 recrue, vedettes d'abord
        if k < len(ved):
            mix.append(ved[k])
            k += 1
        mix += uniq[i:i + 1]
        i += 1
    return mix[:200]


# 28 oct 2026 : veterans et legendes de la LNH dont les autos et patchs se vendent bien (noms seulement, rien d'autre)
VEDETTES = ["Wayne Gretzky", "Mario Lemieux", "Sidney Crosby", "Connor McDavid", "Alex Ovechkin", "Patrick Roy", "Bobby Orr",
            "Jaromir Jagr", "Steve Yzerman", "Joe Sakic", "Nathan MacKinnon", "Auston Matthews", "Cale Makar", "Carey Price",
            "Mark Messier", "Guy Lafleur", "Martin Brodeur", "Nikita Kucherov", "Leon Draisaitl", "Nicklas Lidstrom",
            "Gordie Howe", "Teemu Selanne", "Evgeni Malkin", "Jack Hughes", "Cole Caufield", "Nick Suzuki", "Mike Bossy",
            "Jean Beliveau", "Ray Bourque", "Marc-Andre Fleury"]


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
JOURS_MAX = 90                   # 27 oct 2026 : comme le dit la page Support (« les 90 derniers jours »)
JOURS_MAX_HITS = 180


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
    # 27 oct 2026 (revue) : jamais des ventes trop vieilles : 90 jours, 180 pour un hit (numerotee /99 ou moins, auto,
    # patch : ca se vend moins souvent)
    jm = JOURS_MAX
    if titre_annonce:
        dc = cartes_match.decoder(titre_annonce)
        if dc.get("auto") or dc.get("patch") or (dc.get("serie") and dc["serie"] <= 99):
            jm = JOURS_MAX_HITS
    pv = [v for v in pv if _jours(v) <= jm]
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
_RE_GRADE_V = _re.compile(r" (psa|bgs|sgc|cgc|beckett|csg|gma|isa|ags|mnt|tag|ksa|hga) ?\d")
VERIF_JOUR = 40                  # recherches SoldComps ciblees par jour pour confirmer une annonce prometteuse
PART_HITS = 0.85                 # 28 oct 2026 : la part gardee pour les hits (0,6 -> 0,85 : « encore juste des Young Guns » ; les YG ont deja leurs ventes connues)


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
        # 28 oct 2026 : 60 % du budget du jour est garde pour les hits (autos, patchs, /99) : les Young Guns ont deja
        # beaucoup de ventes connues, les hits de veterans et de legendes ont besoin de la verification
        hit = _hit(cib)
        if not hit and v.get("n_std", 0) >= max_ * (1 - PART_HITS):
            st["verif_budget"] = st.get("verif_budget", 0) + 1
            return None
        faites.add(q)
        r = vendues.rechercher(q, fond=True)
        if r.get("erreur"):
            st["erreurs_ventes"] = st.get("erreurs_ventes", 0) + 1
            return None
        if not r.get("cache"):
            v["n"] += 1
            if not hit:
                v["n_std"] = v.get("n_std", 0) + 1
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
    # 29 oct 2026 (Mathieu : « les deals montrent encore juste des Young Guns et des Future Watch ») : un hit a PRIX FIXE
    # (auto, patch, /99) sans vente connue de sa carte etait toujours ecarte. Maintenant il est verifie en fin de tour
    # (apres les encans, avec le budget qui reste) s'il a l'air bas : 25 % sous les memes cartes en vente, ou une
    # vedette (veteran / legende) de 40 $ et plus.
    elif not va and verif and r.get("suivi") and t >= HIT_MIN and not memes_ventes(cib, tout_v):
        st.setdefault("_tard", []).append((a, r, cib))           # 29 oct : vendeur suivi, toutes ses cartes de 25 $ et plus
    elif not va and verif and not a.get("encan") and t >= HIT_MIN and _hit(cib) and not memes_ventes(cib, tout_v):
        pa2 = [_total(x) for x in actives or [] if x.get("item_id") != a.get("item_id")
               and not cartes_match.raisons_refus(cib, x.get("titre") or "")]
        bas = bool(pa2) and t <= (cartes_match.mediane_robuste(pa2)[0] or 0) * 0.75
        if bas or (r.get("vedette") and t >= 40):
            st.setdefault("_tard", []).append((a, r, cib))
    if not va:
        st["sans_ventes"] = st.get("sans_ventes", 0) + 1
        deals.pop(a["item_id"], None)                 # revue : plus un deal (encan dont la mise a monte...)
        return
    med_a, source_a, n_a, ventes_a = va
    if t > med_a * RATIO_DEAL:
        st["trop_cher"] = st.get("trop_cher", 0) + 1
        deals.pop(a["item_id"], None)
        if t <= med_a * RATIO_PRES and not a.get("encan"):      # a surveiller : sous la valeur, pas encore un deal
            st.setdefault("_pres", {})[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"),
                                                         "url": a.get("url"), "valeur": med_a, "ratio": round(t / med_a, 3), "encan": False,
                                                         "joueur": r.get("joueur"), "q": r.get("q"), "flux": r.get("flux"), "n": n_a,
                                                         "vendues": ventes_a or [], "sport": r.get("sport") or "hockey",
                                                         "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION, "palier": "pres"}
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


def encore_ouvert(x, maint=None):
    """Un encan dont la fin est passee n'est plus un deal."""
    if not x.get("encan"):
        return True
    try:
        return datetime.fromisoformat(str(x.get("fin")).replace("Z", "+00:00")) > (maint or datetime.now(timezone.utc))
    except ValueError:
        return False


def _verifier_tard(st, deals, maint, bassin, verif):
    """27 oct 2026 (Mathieu : la Savoie Draft Day Marks /35 a 50 $, qui finit dans 25 h) : les encans de hits sans ventes
    connues qui finissent dans 6 a 30 h, verifies a la fin du tour avec le budget qui reste, les plus proches de la fin d'abord."""
    tard = st.pop("_tard", [])
    # les encans d'abord (le plus proche de la fin), puis les prix fixes (le plus cher d'abord : plus de profit possible)
    tard.sort(key=lambda x: (0, 0 if x[1].get("suivi") else 1, str(x[0].get("fin")), 0) if x[0].get("encan") else (1, 0 if x[1].get("suivi") else 1, "", -(_total(x[0]) or 0)))
    for a, r, cib in tard:
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
    nouveaux_pres = st.pop("_pres", {})
    nouveaux_retires = st.pop("_retires", [])
    with _verrou:
        d2 = lire()
        retires = _noter_retires(d2, nouveaux_retires)
        garde_ = [x for x in garde_ if str(x["item_id"]) not in retires]
        ids = {x["item_id"] for x in garde_}
        pres = {x["item_id"]: x for x in d2.get("pres") or []}
        pres.update(nouveaux_pres)
        lim = (maint - timedelta(hours=FRAICHEUR_EBAY_H)).isoformat()
        pres_l = sorted((x for k, x in pres.items() if k not in ids and str(k) not in retires and str(x.get("vu_le") or "") >= lim),
                        key=lambda x: x["ratio"])[:300]
        d2.update(deals=garde_, pres=pres_l, **champs)
        if len(garde_) >= 5:                              # la derniere bonne liste, en secours
            d2["secours"] = {"le": maint.isoformat(timespec="seconds"), "deals": garde_[:120]}
        elif d2.get("secours"):                           # 27 oct 2026 (revue) : le secours perd ses annonces finies / retirees
            d2["secours"]["deals"] = [x for x in d2["secours"].get("deals") or [] if str(x.get("item_id")) not in retires and encore_ouvert(x, maint)]
        if "verif" in d:
            d2["verif"] = d["verif"]
        _diag(d2, **st)
        _ecrire(d2)
    return garde_


def _memes(r, annonces):
    """Les annonces a juger pour une requete. Recrue : la carte exacte de la requete. Vedette (« Gretzky auto ») : toutes
    les cartes de ce joueur (autos, patchs, numerotees...) ; chacune est jugee sur les ventes de SA carte, comme les flux."""
    import cartes_match
    if not r.get("vedette"):
        return cartes_match.filtrer(r["q"], annonces)
    nom = cartes_match.norm(r.get("joueur") or "") if hasattr(cartes_match, "norm") else str(r.get("joueur") or "").lower()
    der = nom.split()[-1] if nom else ""
    l = [a for a in annonces if der and der in (a.get("titre") or "").lower() and cartes_match.est_carte(a.get("titre") or "")]
    return None, l, []


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
        _c, memes, _e = _memes(r, fixes)
        # chaque annonce a SA valeur, celle des ventes de la MEME carte (2 au moins), sinon pas de deal
        brut_v, err = _ventes(r["q"])
        if err:
            st["erreurs_ventes"] = st.get("erreurs_ventes", 0) + 1
        bassin.ajouter(brut_v)
        med = cartes_match.mediane_robuste([_total(x) for x in memes])[0] if memes else None
        comps = sorted(({"titre": x["titre"], "total": _total(x), "photo": x.get("photo"), "url": x.get("url")} for x in memes),
                       key=lambda x: abs(x["total"] - (med or 0)))[:8]
        if r.get("vedette"):
            comps = []                                   # des cartes differentes du meme joueur : pas des comparables
        for a in memes:
            _juger(a, r, brut_v, memes, maint, deals, st, comps=comps, bassin=bassin, verif=verif)
    _verifier_tard(st, deals, maint, bassin, verif)          # 29 oct : les hits a prix fixe des vedettes aussi
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
        _c, memes_e, _e = _memes(r, ench)
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
             ("ultimate collection auto", "hockey"), ("black diamond auto", "hockey"), ("synergy auto", "hockey"),
             # 28 oct 2026 (Mathieu : « ou sont les cartes auto patch de veterans ou de legendes ? »)
             ("legends auto hockey", "hockey"), ("legends patch hockey", "hockey"), ("veteran auto patch hockey", "hockey"),
             ("game used auto patch hockey", "hockey"), ("sp legendary signatures", "hockey"), ("ud legends auto", "hockey"),
             ("signature moments auto", "hockey"), ("the cup legends", "hockey"), ("sp signature edition auto", "hockey"),
             ("leaf auto hockey", "hockey"), ("tag patch hockey", "hockey"), ("letter patch hockey", "hockey"),
             ("gretzky auto", "hockey"), ("lemieux auto", "hockey"), ("crosby auto", "hockey"), ("ovechkin auto", "hockey"),
             ("patrick roy auto", "hockey"), ("mcdavid auto patch", "hockey")]
HITS_PAR_TOUR = 16               # 28 oct (soir) : 16 par heure : tous les flux de hits en ~2 h


def flux_hits(curseur):
    """Les flux de hits de ce tour, et le curseur du prochain."""
    if os.environ.get("LR_DEALS_FLUX") or not FLUX_HITS:
        return [], 0
    i0 = int(curseur or 0) % len(FLUX_HITS)
    return (FLUX_HITS[i0:] + FLUX_HITS[:i0])[:HITS_PAR_TOUR], (i0 + HITS_PAR_TOUR) % len(FLUX_HITS)


# 29 oct 2026 (Mathieu : « au moins une centaine de deals autres que des Young Guns en encheres, comme chez savage, remi,
# cf_31, dc sports 87, slab shark et d'autres particuliers. Je les veux TOUS ») : des vendeurs suivis. Chaque heure : leurs
# encans qui finissent dans 48 h (toutes cartes, pas seulement des recrues) et leurs nouvelles annonces a prix fixe.
# La liste se regle dans la console admin (pseudos eBay exacts) ou avec LR_DEALS_VENDEURS (« a;b;c »).
VENDEURS_DEFAUT = ["savage.cards", "remi-card-trader", "slabsharksinc", "dcsports87", "cf_31"]   # 29 oct : savage.cards et remi-card-trader confirmes par Mathieu
VENDEURS_PAR_APPEL = 10                  # la Browse API accepte plusieurs vendeurs dans un meme filtre


def vendeurs_suivis():
    e = os.environ.get("LR_DEALS_VENDEURS")
    if e:
        return [x.strip() for x in e.split(";") if x.strip()]
    v = lire().get("vendeurs")
    return list(v) if isinstance(v, list) else list(VENDEURS_DEFAUT)


def regler_vendeurs(liste):
    l = []
    for x in liste or []:
        x = re.sub(r"[^A-Za-z0-9._-]", "", str(x).strip().lstrip("@"))[:64]
        if x and x.lower() not in [y.lower() for y in l]:
            l.append(x)
    with _verrou:
        d = lire()
        d["vendeurs"] = l[:40]
        _ecrire(d)
    return l[:40]


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
    # 29 oct : les vendeurs suivis d'abord (leurs encans et leurs nouvelles annonces), par groupes de 10 vendeurs par appel
    vs = vendeurs_suivis()
    for k in range(0, len(vs), VENDEURS_PAR_APPEL):
        grp = vs[k:k + VENDEURS_PAR_APPEL]
        rv = {"q": None, "flux": "vendeurs", "sport": None, "joueur": None, "suivi": True}
        for ench, page in [(False, 0)] + [(True, j) for j in range(pages)]:
            try:
                l = rechercher("", categorie="261328", limite=200, fond=True, encheres=ench, recentes=not ench, flux=True, offset=200 * page, vendeurs=grp)
            except (RuntimeError, OSError, TypeError):
                st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
                break
            st["requetes_flux"] = st.get("requetes_flux", 0) + 1
            st["vendeurs_annonces"] = st.get("vendeurs_annonces", 0) + len(l)
            l = [a for a in l if cartes_match.est_carte(a.get("titre") or "")]
            for a in l:
                _juger(a, rv, [], [] if ench else l, maint, deals, st, bassin=bassin, verif=verif)
            if ench and (len(l) < 150 or not l or str(l[-1].get("fin") or "9") > limite_fin):
                break
    # 28 oct 2026 (Mathieu : « les maudits deals sont encore juste des Young Guns ») : les flux larges de recrues (Young
    # Guns, rookies) un tour sur deux seulement ; les appels eBay economises vont aux hits (2 fois plus de flux de hits)
    tour_n = int(d.get("tour_n") or 0)
    recrues = flux_liste() if tour_n % 2 == 0 or os.environ.get("LR_DEALS_FLUX") else []
    for q, sport in hits + recrues:                     # 28 oct : les hits d'abord (le budget de verification va aux hits)
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
    garde_ = _sauver(d, deals, maint, st, curseur_h=curseur_h, tour_n=tour_n + 1)
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
                st.setdefault("_retires", []).append(x["item_id"])
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
            st.setdefault("_retires", []).append(x["item_id"])
            st["reverif_retires"] = st.get("reverif_retires", 0) + 1
            continue
        x.update(total=t, ratio=round(t / x["valeur"], 3), mises=a.get("mises", x.get("mises")), fin=a.get("fin") or x.get("fin"),
                 port=a.get("port_cad"), vu_le=maint.isoformat(timespec="seconds"))
        if x.get("encan"):
            x["mise_max"] = round(x["valeur"] * RATIO_DEAL - (a.get("port_cad") or 0), 2)
    garde_ = _sauver(d, deals, maint, st)
    return {"ok": True, "deals": len(garde_), "stats": st}


def recharger():
    """28 oct 2026 (Mathieu : « on doit recharger les deals ») : un tour complet tout de suite (admin), sans attendre
    l'heure et sans le rythme du budget eBay (le plafond du jour, lui, tient toujours)."""
    import appels_ebay
    if _ETAT["en_cours"]:
        return {"ok": True, "deja": True}
    appels_ebay.liberer(900)
    return {"ok": True, "lance": bool(chasser_si_besoin(force=True))}


def etat():
    """Pour l'admin : ou en est le chasseur (deals affiches, budget eBay et budget de verification du jour)."""
    import appels_ebay
    d = lire()
    try:
        vmax = int(os.environ.get("LR_DEALS_VERIF_JOUR") or VERIF_JOUR)
    except ValueError:
        vmax = VERIF_JOUR
    v = d.get("verif") or {}
    jour = datetime.now().strftime("%Y-%m-%d")
    import cartes_match
    rep = {"young_guns": 0, "recrues": 0, "hits": 0, "veterans": 0}
    for x in d.get("deals") or []:
        if not (valide(x) and encore_ouvert(x)):
            continue
        rep[sorte(x.get("titre"))] += 1
    return {"ok": True, "en_cours": _ETAT["en_cours"], "maj": d.get("maj"), "repartition": rep,
            "deals": sum(1 for x in d.get("deals") or [] if valide(x) and encore_ouvert(x)),
            "ebay": utilises_ebay(), "ebay_rythme": round(appels_ebay.rythme("browse")),
            "ebay_plafond": round(appels_ebay.limite("browse") * (1 - appels_ebay.RESERVE_GESTES)),
            "verif": v.get("n", 0) if v.get("jour") == jour else 0, "verif_max": vmax}


def sorte(titre):
    """young_guns | recrues | hits | veterans : pour la repartition (admin) et le melange de l'ecran Deals."""
    import cartes_match
    t = cartes_match.norm(titre or "")
    c = cartes_match.decoder(titre or "")
    s = c.get("serie")
    if c.get("auto") or c.get("patch") or (s is not None and int(s) <= 99):
        return "hits"
    if "young guns" in t:
        return "young_guns"
    if c.get("rc") or "rookie" in t or "future watch" in t:
        return "recrues"
    return "veterans"


def melanger(lst, ratio=2):
    """28 oct 2026 (« encore juste des Young Guns ») : l'ecran Deals par defaut alterne : 2 deals d'autres cartes (hits,
    veterans, legendes, autres recrues) pour 1 Young Guns, dans leur ordre ; les Young Guns restants a la fin."""
    yg, autres = [], []
    for x in lst:
        (yg if sorte(x.get("titre")) == "young_guns" else autres).append(x)
    out, i, j = [], 0, 0
    while i < len(autres) or j < len(yg):
        for _ in range(ratio):
            if i < len(autres):
                out.append(autres[i]); i += 1
        if j < len(yg):
            out.append(yg[j]); j += 1
    return out


def utilises_ebay():
    import appels_ebay
    return appels_ebay.utilises("browse")


def chasser_si_besoin(force=False):
    """En arriere-plan, au plus une fois par heure, jamais deux a la fois."""
    d = lire()
    try:
        age = time.time() - datetime.fromisoformat(str(d.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    age = min(age, time.time() - _ETAT.get("essai_le", 0))      # 27 oct 2026 (revue) : un tour rate compte aussi
    # une seule fois par demarrage (mise a jour, redemarrage) : peu de deals -> un tour apres 10 min, pas apres 1 h
    # (jamais plus : le quota d'appels eBay du jour)
    peu = not _ETAT.get("rapide") and sum(1 for x in d.get("deals") or [] if valide(x)) < 10
    if age < (600 if peu else FRAICHEUR_S) and not force:
        return False
    if peu:
        _ETAT["rapide"] = True
    with _verrou:
        if _ETAT["en_cours"]:
            return False
        _ETAT["en_cours"] = True
        _ETAT["essai_le"] = time.time()

    def tache():
        try:
            b = Bassin()                                 # une fois par tour : toutes les ventes connues
            try:
                reverifier()                             # d'abord : les deals deja affiches, revus sur eBay
            except Exception as e:
                print("Deals (revue) : " + repr(e), flush=True)
            # 28 oct 2026 : les flux d'abord (hits, vendeurs suivis, encans larges) : ce sont eux qui trouvent le plus ;
            # si le rythme du budget eBay coupe le tour, il coupe les recherches par joueur
            for f in (flux, encans, chasser):
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
