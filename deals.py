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
ENCAN_SUIVI_H = 120              # 29 oct 2026 (Mathieu : « deux jours avant les encheres, chez Savage, Remi, CF31, Slab Sharks,
                                 # DC Sports… plusieurs cartes sont supposees sortir dans les deals ») : leurs encans de 5 jours et moins
PAGES_FIXE_SUIVIS = 3
PAGES_SUIVIS = 10                # et jusqu'a 10 pages de 200 encans par groupe de vendeurs (2 000)
ENCAN_H = 48                     # 26 oct 2026 (Mathieu : « tous les deals d'encheres de 48 h et moins ») ; avant : 6 h
ENCAN_VERIF_H = 6                # une recherche de ventes ciblee pour un encan : seulement s'il finit dans 6 h (la mise monte)
PAGES_ENCANS = 3                 # flux d'encans : jusqu'a 3 pages de 200 (les plus proches de la fin d'abord)
PAR_TOUR = 20                    # requetes prix fixe par tour (les plus recentes d'abord) : la liste entiere en 6 h
FRAICHEUR_S = 3600
_verrou = threading.Lock()
_ETAT = {"en_cours": False}


# 29 oct 2026 (Mathieu : « quand je vais voir mes deals a jour ? c'est un probleme de pas savoir, pour l'admin ») :
# l'admin voit ou en est le tour (etape, progression, fin estimee) et quand vient le prochain.
ETAPES = {"revue": (1, "Deals revus sur eBay"), "flux": (2, "Vendeurs suivis et flux"), "encans": (3, "Encans par joueur"),
          "chasser": (4, "Prix fixe par joueur")}


def _progres(etape=None, detail=None):
    if etape:
        _ETAT["etape"] = etape
    _ETAT["detail"] = detail


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "deals_globaux.json")


_VERROU_F = {}


def _prendre_tour():
    """29 oct 2026 (« il ne faut plus que cela arrive ») : un seul chasseur a la fois sur le disque, meme si deux
    processus tournent (mise a jour Render : l'ancien et le nouveau serveur se chevauchent quelques minutes)."""
    try:
        import fcntl
    except ImportError:                       # Windows (PC) : un seul processus
        return True
    try:
        f = open(_chemin() + ".verrou", "a+")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try:
            f.close()
        except Exception:
            pass
        return False
    _VERROU_F["f"] = f
    return True


def _rendre_tour():
    f = _VERROU_F.pop("f", None)
    if f:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()


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
    """31 oct 2026 (Mathieu : « doit faire 1 min que ca load », « Server error ») : le fichier (plusieurs Mo) est reecrit
    aux 30 s pendant un tour ; chaque ecran le relisait alors en entier (lire_vite voyait un fichier change) et le petit
    serveur saturait. Maintenant ce qu'on vient d'ecrire devient tout de suite la copie en memoire : aucune relecture.
    Ecriture compacte (sans espaces) : un fichier plus petit, plus vite ecrit et lu."""
    tmp = _chemin() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, _chemin())
    try:
        st = os.stat(_chemin())
        _LU.update(cle=(st.st_mtime_ns, st.st_size), d=d)
    except OSError:
        pass


_VALIDES = {}
_BANNIS = {"mt": None, "s": set()}


def _bannis():
    # 28 oct 2026 (vitesse) : un seul coup d'oeil au fichier par seconde (avant : un par deal, ~1 900 par ecran)
    if time.time() - _BANNIS.get("vu", 0) < 1.0:
        return _BANNIS["s"]
    _BANNIS["vu"] = time.time()
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
    # 30 oct 2026 (Mathieu : « Stankoven : il y a des comps mais le dashboard ne le montre pas ») : l'encan d'un vendeur
    # suivi, garde sans valeur, prend la valeur que la fenetre vient de trouver (ventes reelles de la meme carte)
    if valeur and any(str(g.get("item_id")) == iid and not g.get("valeur") for g in d.get("suivis") or []):
        with _verrou:
            d = lire()
            for g in d.get("suivis") or []:
                if str(g.get("item_id")) == iid:
                    g.update(valeur=valeur, mise_max=round(valeur * RATIO_DEAL - (g.get("port") or 0), 2))
            _ecrire(d)
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
    while i < len(uniq) or k < len(ved):         # 29 oct : 2 vedettes pour 1 recrue (les flux couvrent deja les recrues)
        mix += ved[k:k + 2]
        k += 2
        mix += uniq[i:i + 1]
        i += 1
    return mix[:260]


# 28 oct 2026 : veterans et legendes de la LNH dont les autos et patchs se vendent bien (noms seulement, rien d'autre)
_VEDETTES_28 = ["Wayne Gretzky", "Mario Lemieux", "Sidney Crosby", "Connor McDavid", "Alex Ovechkin", "Patrick Roy", "Bobby Orr",
            "Jaromir Jagr", "Steve Yzerman", "Joe Sakic", "Nathan MacKinnon", "Auston Matthews", "Cale Makar", "Carey Price",
            "Mark Messier", "Guy Lafleur", "Martin Brodeur", "Nikita Kucherov", "Leon Draisaitl", "Nicklas Lidstrom",
            "Gordie Howe", "Teemu Selanne", "Evgeni Malkin", "Jack Hughes", "Cole Caufield", "Nick Suzuki", "Mike Bossy",
            "Jean Beliveau", "Ray Bourque", "Marc-Andre Fleury"]
# 29 oct 2026 (Mathieu : « des legendes puis des veterans aux deuxieme, troisieme, quatrieme annee ») : plus de legendes,
# les vedettes d'aujourd'hui et les jeunes de 2e a 4e annee (plus des recrues de l'annee : les flux les couvrent deja)
_LEGENDES_29 = ["Maurice Richard", "Bobby Hull", "Brett Hull", "Pavel Bure", "Peter Forsberg", "Ken Dryden", "Dominik Hasek",
                "Eric Lindros", "Paul Kariya", "Phil Esposito", "Luc Robitaille", "Mats Sundin", "Henrik Lundqvist", "Patrick Kane",
                "Jonathan Toews", "Marcel Dionne", "Bryan Trottier", "Denis Savard", "Pierre Turgeon", "Vincent Lecavalier"]
_ETOILES_29 = ["Kirill Kaprizov", "Quinn Hughes", "David Pastrnak", "Jason Robertson", "Mitch Marner", "William Nylander",
               "Igor Shesterkin", "Brady Tkachuk", "Matthew Tkachuk", "Jack Eichel", "Elias Pettersson", "Tim Stutzle"]
_JEUNES_29 = ["Connor Bedard", "Macklin Celebrini", "Matvei Michkov", "Adam Fantilli", "Lane Hutson", "Leo Carlsson",
              "Logan Cooley", "Cutter Gauthier", "Will Smith", "Luke Hughes", "Wyatt Johnston", "Juraj Slafkovsky",
              "Mason McTavish", "Matty Beniers", "Moritz Seider", "Lucas Raymond", "Owen Power", "Shane Wright"]


def _intercaler(*listes):
    out, vus = [], set()
    for k in range(max(len(x) for x in listes)):
        for l in listes:
            if k < len(l) and l[k].lower() not in vus:
                vus.add(l[k].lower())
                out.append(l[k])
    return out


VEDETTES = _intercaler(_VEDETTES_28, _JEUNES_29, _LEGENDES_29, _ETOILES_29)


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


_BASSIN = {"b": None, "le": 0.0}
_verrou_bassin = threading.Lock()
BASSIN_PARTAGE_S = 90 * 60


def bassin_partage(neuf=False):
    """31 oct 2026 (Mathieu : « doit faire 1 min que ca load », « Server error ») : UN seul bassin en memoire pour tout le
    processus. Avant, chaque etape (tour, encans aux 15 min, fin d'encan...) rebatissait le sien : 150 000 ventes relues
    et indexees a chaque fois, parfois deux a la fois, et le petit serveur Render saturait (memoire et calcul).
    neuf=True (debut d'un tour) : rebati ; sinon celui de moins de 90 min sert."""
    with _verrou_bassin:
        b = _BASSIN["b"]
        if neuf or b is None or time.time() - _BASSIN["le"] > BASSIN_PARTAGE_S:
            _BASSIN["b"] = None                          # l'ancien libere avant de batir le nouveau (memoire)
            b = Bassin()
            _BASSIN.update(b=b, le=time.time())
        return b


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
            if self.n % 500 == 0:
                time.sleep(0.004)            # 31 oct 2026 : plus souvent (les ecrans passent entre deux paquets)            # 28 oct 2026 (vitesse) : laisse respirer les requetes des utilisateurs (meme processus)
            tl = cartes_match._norm(v["titre"])     # sans la memoire de norm() : 150 000 titres vus une seule fois
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
                # 31 oct 2026 : les 3 derniers jours seulement (comme dit plus haut), et on arrete une fois plein. Avant, TOUT
                # le cache etait relu (des milliers de lignes apres une grosse soiree) : minutes de calcul, serveur sature
                for (brut,) in c.execute("SELECT ventes FROM cache WHERE le >= ? ORDER BY le DESC", (time.time() - 3 * 86400,)):
                    if self.n >= self.MAX:
                        break
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


def _minuit_mtl():
    """Le prochain minuit a Montreal (le budget SoldComps repart), en ISO."""
    try:
        from zoneinfo import ZoneInfo
        m = datetime.now(ZoneInfo("America/Toronto"))
    except Exception:
        return (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0).isoformat()
    return (m + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _jour_mtl():
    """(jour, heure decimale) a Montreal : le budget de verification suit la journee des acheteurs."""
    try:
        from zoneinfo import ZoneInfo
        m = datetime.now(ZoneInfo("America/Toronto"))
    except Exception:
        m = datetime.now(timezone.utc) - timedelta(hours=4)
    return m.strftime("%Y-%m-%d"), m.hour + m.minute / 60


def _verificateur(d, st, bassin):
    """Une annonce qui a l'air d'un deal mais sans 2 ventes connues de la MEME carte : une recherche SoldComps de CETTE
    carte (budget : LR_DEALS_VERIF_JOUR, 40 par jour par defaut), puis on la juge sur ses vraies ventes."""
    import cartes_match
    import vendues
    try:
        max_ = int(os.environ.get("LR_DEALS_VERIF_JOUR") or VERIF_JOUR)
    except ValueError:
        max_ = VERIF_JOUR
    jour, heure = _jour_mtl()
    v = d.setdefault("verif", {})
    if v.get("jour") != jour:
        v.clear()
        v.update(jour=jour, n=0)
    # 28 oct 2026 (« vraiment tous les deals, pas juste Future Watch et Young Guns ») : le budget du jour (journee de
    # Montreal) est etale : il en reste toujours pour le soir, quand finissent la plupart des encans
    rythme = max_ * min(1.0, (heure + 4) / 24)
    faites = set()

    def f(cib, prio=False):
        q = (cartes_match.requete_ebay(cib) or "").strip()
        if not q or q in faites:
            return None
        # 29 oct 2026 : une carte deja verifiee (ventes en cache, 3 jours) ne coute rien : jamais bloquee par le budget
        # (avant : budget epuise = ses ventes connues ignorees, et le deal disparaissait au tour suivant)
        deja = vendues.en_cache(q)
        if deja is not None:
            faites.add(q)
            st["verifs_cache"] = st.get("verifs_cache", 0) + 1
            bassin.ajouter(deja)
            st["_dern_verif"] = {"q": q, "n": len(deja), "cache": True}
            return deja
        # 29 oct 2026 (Mathieu : « il ne faut plus que cela arrive », SoldComps 706 credits en 3 h) : le budget se compte
        # sur le compteur PERSISTANT de SoldComps (credits reels, partage, survit aux redemarrages et aux mises a jour),
        # plus sur un compteur en memoire qu'un redemarrage effacait
        if prio and prio_ok(heure):                # 30 oct 2026 : la reserve des 4 vendeurs prioritaires
            faites.add(q)
            r = vendues.rechercher(q, fond=True, usage="prio")
            if r.get("erreur"):
                k = _cle_erreur(r["erreur"])
                st[k] = st.get(k, 0) + 1
                return None
            st["prio_verifs"] = st.get("prio_verifs", 0) + 1
            st["_dern_verif"] = {"q": q, "n": len(r.get("ventes") or []), "cache": bool(r.get("cache"))}
            bassin.ajouter(r.get("ventes"))
            return r.get("ventes") or []
        if prio:
            # 31 oct 2026 (Mathieu : « que toutes les cartes des gros vendeurs soient TOUTES analysees avant de passer au
            # reste ») : la reserve est vide -> la carte prend le budget du chasseur, AVANT les autres cartes
            st["prio_budget"] = st.get("prio_budget", 0) + 1
        n_reel = vendues.utilises_aujourdhui("verif")
        if n_reel >= max_ or n_reel >= rythme:
            st["verif_budget"] = st.get("verif_budget", 0) + 1
            return None
        if prio:
            faites.add(q)
            r = vendues.rechercher(q, fond=True, usage="verif")
            if r.get("erreur"):
                k = _cle_erreur(r["erreur"])
                st[k] = st.get(k, 0) + 1
                return None
            if not r.get("cache"):
                v["n"] += 1
            st["prio_debord"] = st.get("prio_debord", 0) + 1
            st["_dern_verif"] = {"q": q, "n": len(r.get("ventes") or []), "cache": bool(r.get("cache"))}
            bassin.ajouter(r.get("ventes"))
            return r.get("ventes") or []
        # 28 oct 2026 : 60 % du budget du jour est garde pour les hits (autos, patchs, /99) : les Young Guns ont deja
        # beaucoup de ventes connues, les hits de veterans et de legendes ont besoin de la verification
        hit = _precieuse(cib)               # 29 oct : une Gretzky OPC PSA 8 compte comme un hit (pas la part des cartes ordinaires)
        if not hit and v.get("n_std", 0) >= max_ * (1 - PART_HITS):
            st["verif_budget"] = st.get("verif_budget", 0) + 1
            return None
        # 29 oct 2026 (Mathieu : « encore juste des callistes de Young Guns et de Future Watch ») : une auto Future Watch
        # est aussi un « hit » et mangeait le budget des hits. Les hits de RECRUES ont au plus 35 % du budget jusqu'a
        # 18 h (Montreal) : la moitie du budget reste aux veterans et aux legendes ; le soir, ce qui reste va a tous
        rec = hit and _recrue(cib)
        if rec and heure < 18 and v.get("n_rh", 0) >= max_ * PART_HITS_RECRUES:
            st["verif_budget_recrues"] = st.get("verif_budget_recrues", 0) + 1
            return None
        faites.add(q)
        r = vendues.rechercher(q, fond=True, usage="verif")
        if r.get("erreur"):
            k = _cle_erreur(r["erreur"])
            st[k] = st.get(k, 0) + 1
            return None
        if not r.get("cache"):
            v["n"] += 1
            if not hit:
                v["n_std"] = v.get("n_std", 0) + 1
            elif rec:
                v["n_rh"] = v.get("n_rh", 0) + 1
        if hit:
            st["hits_verifies"] = st.get("hits_verifies", 0) + 1
            if not rec:
                st["vedettes_verifiees"] = st.get("vedettes_verifiees", 0) + 1
        st["_dern_verif"] = {"q": q, "n": len(r.get("ventes") or []), "cache": bool(r.get("cache"))}
        st["verifs"] = st.get("verifs", 0) + 1
        bassin.ajouter(r.get("ventes"))
        return r.get("ventes") or []
    return f


PART_HITS_RECRUES = 0.35         # 29 oct 2026 : hits de recrues (auto Future Watch, YG patch...) : 35 % du budget avant 18 h
# 30 oct 2026 (Mathieu : « toutes les cartes de Savage n'ont pas de comp ») : une reserve de verifications SoldComps pour les
# 4 vendeurs prioritaires (Savage, Remi, CF31, Slab Sharks), cartes de 10 $ et plus, en plus des 40 du chasseur. Toujours
# sous le plafond total (LR_SOLDCOMPS_JOUR) ; compteur persistant a part (usage « prio »). LR_DEALS_VERIF_PRIO pour changer.
PRIO_VERIF_JOUR = 250
PRIO_MIN = 0.0                   # 31 oct 2026 : TOUTES les cartes des 4 vendeurs (les plus cheres d'abord) ; avant : 10 $ et plus
PRIO_SOIR = 0.20                 # 31 oct 2026 : plus de rythme : 80 % de la reserve tout de suite, 20 % gardes pour apres 16 h
PRIO_SOIR_H = 16


def prio_ok(heure=None):
    """La reserve des 4 vendeurs a encore de la place ? (sans rythme ; 20 % gardes pour le soir, quand les encans finissent)"""
    import vendues
    if heure is None:
        heure = _jour_mtl()[1]
    n_p, m = vendues.utilises_aujourdhui("prio"), prio_max()
    return n_p < m and (heure >= PRIO_SOIR_H or n_p < m * (1 - PRIO_SOIR))


def prio_max():
    try:
        return max(0, int(os.environ.get("LR_DEALS_VERIF_PRIO") or PRIO_VERIF_JOUR))
    except ValueError:
        return PRIO_VERIF_JOUR


def _prio(a):
    return rang_vendeur(a.get("vendeur")) < len(VENDEURS_PRIORITE)


def saison_recrues():
    """L'annee de depart la plus ancienne des recrues « de l'annee » : en oct. 2026, les produits 2025-26 et 2026-27."""
    m = datetime.now()
    return m.year - 1 if m.month >= 7 else m.year - 2


def recrue_recente(texte, rc=False, annee=None):
    """29 oct 2026 (Mathieu : « pas juste des rookies premiere annee ») : une RC de Lemieux 1985 ou une Young Guns de Bedard
    2023-24 n'est plus une « recrue » : ce sont des legendes et des joueurs de 2e a 4e annee. Seulement les recrues de
    l'annee (et les cartes de recrue sans annee)."""
    t = " " + str(texte or "").lower() + " "
    if not (rc or any(m in t for m in (" young guns", " future watch", " rookie", " rc ", " 1st "))):
        return False
    return annee is None or int(annee) >= saison_recrues()


def _recrue(cib):
    """Une carte de recrue de l'annee : pour garder le budget des veterans, des legendes et des jeunes de 2e a 4e annee."""
    return recrue_recente(cib.get("texte"), cib.get("rc"), cib.get("annee"))


_NOMS_VEDETTES = None


def _precieuse(cib):
    """29 oct 2026 : vaut une verification meme sans auto ni patch : un hit, une carte gradee d'avant 2015, une vintage
    (avant 1995) ou une carte d'une vedette (veteran, legende, jeune de 2e a 4e annee)."""
    global _NOMS_VEDETTES
    if _hit(cib):
        return True
    an = cib.get("annee")
    if an and (int(an) < 1995 or (cib.get("grade") and int(an) < 2015)):
        return True
    if _NOMS_VEDETTES is None:
        _NOMS_VEDETTES = {_cle_nom(n) for n in VEDETTES}
    return _cle_nom(cib.get("joueur")) in _NOMS_VEDETTES


def _cle_nom(n):
    """29 oct 2026 : « Alex Ovechkin » (liste) et « Alexander Ovechkin » (titre) sont le meme joueur : initiale + nom."""
    p = str(n or "").lower().replace(".", " ").split()
    return (p[0][:1] + " " + p[-1]) if len(p) > 1 else " ".join(p)


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


JOURNAL_MAX = 200                # 29 oct 2026 : les dernieres verifications SoldComps (admin)


def _noter_journal(st, a, r, cib, dv):
    """29 oct 2026 (Mathieu : « je suis pas capable de voir ce que tu as cherche avec mes credits ») : chaque
    verification SoldComps, sa carte, son prix et le resultat (deal, trop cher, pas assez de ventes)."""
    res, ratio = st.pop("_res", (None, None))
    st.setdefault("_journal", []).append({
        "le": datetime.now(timezone.utc).isoformat(timespec="seconds"), "titre": str(a.get("titre") or "")[:140],
        "total": _total(a), "url": a.get("url"), "encan": bool(a.get("encan")), "q": dv.get("q"), "ventes": dv.get("n", 0),
        "cache": dv.get("cache", False), "res": res or "sans_ventes", "ratio": ratio,
        "genre": "recrue" if _recrue(cib) else ("vedette" if _hit(cib) else "autre"),
        "source": "joueur" if r.get("vedette") else ("vendeur" if r.get("suivi") else ("flux" if r.get("flux") else "joueur"))})


def _juger(a, r, brut_v, actives, maint, deals, st, ventes_requete=None, comps=None, bassin=None, verif=None):
    """Une annonce : deal ou non (et pourquoi). Les memes regles pour le prix fixe, les encans et les flux."""
    st.pop("_dern_verif", None)
    st.pop("_res", None)
    _juger0(a, r, brut_v, actives, maint, deals, st, ventes_requete, comps, bassin, verif)
    dv = st.pop("_dern_verif", None)
    if dv:
        import cartes_match
        _noter_journal(st, a, r, cartes_match.cible_titre(a.get("titre") or ""), dv)


def _juger0(a, r, brut_v, actives, maint, deals, st, ventes_requete=None, comps=None, bassin=None, verif=None):
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
        if fin_dt - maint > timedelta(hours=ENCAN_SUIVI_H if r.get("suivi") else ENCAN_H) or fin_dt < maint:   # 48 h (vendeurs suivis : 5 jours)
            return
    cib = cartes_match.cible_titre(a.get("titre") or "")
    if cib.get("exclu") or not cib.get("joueur"):
        return                                                                  # lot, ou on ne sait pas quel joueur
    if cartes_match.abimee(a.get("titre") or "") or vendeur_risque(a):
        st["ecartees"] = st.get("ecartees", 0) + 1                              # abimee, douteuse, ou vendeur sans historique
        deals.pop(a.get("item_id"), None)
        return
    if r.get("suivi") and not sport_carte(a.get("titre"), cib):
        return                                                                  # 29 oct : vendeurs suivis : pas de soccer, tennis...
    st["annonces"] = st.get("annonces", 0) + 1
    if a.get("encan"):
        st["encans_fen"] = st.get("encans_fen", 0) + 1
    est_hit = _hit(cib)
    if est_hit:
        st["hits_vus"] = st.get("hits_vus", 0) + 1
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
    # 28 oct 2026 (Mathieu : « les deals affichent toujours la meme cochonnerie » ; admin : 7 407 hits vus, 14 verifies) :
    # un hit avec 1 ou 2 ventes connues (pas assez pour une valeur sure) n'etait JAMAIS verifie ; maintenant oui
    peu_ventes = len(memes_ventes(cib, tout_v)) < 3
    if not va and verif and a.get("encan") and t >= HIT_MIN and _precieuse(cib) and peu_ventes and not r.get("suivi"):
        try:
            if datetime.fromisoformat(str(fin).replace("Z", "+00:00")) - maint <= timedelta(hours=VERIF_TARD_H):
                st.setdefault("_tard", []).append((a, r, cib))      # verifie a la fin du tour (budget restant)
        except ValueError:
            pass
    # 29 oct 2026 (Mathieu : « les deals montrent encore juste des Young Guns et des Future Watch ») : un hit a PRIX FIXE
    # (auto, patch, /99) sans vente connue de sa carte etait toujours ecarte. Maintenant il est verifie en fin de tour
    # (apres les encans, avec le budget qui reste) s'il a l'air bas : 25 % sous les memes cartes en vente, ou une
    # vedette (veteran / legende) de 40 $ et plus.
    # 30 oct 2026 (Mathieu : « y'en a encore plein marques Auction ») : un encan a 2 jours de la fin a souvent une mise de
    # 3 $ : c'est la carte qui compte, pas la mise -> tous les encans des 4 vendeurs ; le prix fixe a partir de 10 $
    # 31 oct 2026 (Mathieu : « pour les gros vendeurs, analyse seulement les encheres ; leurs prix fixes ne sont pas des deals,
    # sinon ils sortiront dans nos recherches ») : la reserve ne sert qu'aux ENCANS des 4 vendeurs
    elif not va and verif and r.get("suivi") and peu_ventes and _prio(a) and a.get("encan"):
        st.setdefault("_tard", []).append((a, dict(r, prio=True), cib))     # 30 oct : reserve Savage, Remi, CF31, Slab Sharks
    elif not va and verif and r.get("suivi") and peu_ventes and (t >= HIT_MIN or (a.get("encan") and _precieuse(cib))):
        # 29 oct 2026 : un encan d'un vendeur suivi a 2 jours de la fin a souvent une mise de 5 $ : c'est la carte qui compte
        st.setdefault("_tard", []).append((a, r, cib))           # 29 oct : vendeur suivi, toutes ses cartes de 25 $ et plus
    elif not va and verif and not a.get("encan") and t >= HIT_MIN and _precieuse(cib) and peu_ventes:
        pa2 = [_total(x) for x in actives or [] if x.get("item_id") != a.get("item_id")
               and not cartes_match.raisons_refus(cib, x.get("titre") or "")]
        bas = bool(pa2) and t <= (cartes_match.mediane_robuste(pa2)[0] or 0) * 0.75
        if bas or (r.get("vedette") and t >= 40) or t >= 60:     # 28 oct : tout hit de 60 $ et plus (le budget est plus gros)
            st.setdefault("_tard", []).append((a, r, cib))
    if not va:
        st["_res"] = ("sans_ventes", None)
        st["sans_ventes"] = st.get("sans_ventes", 0) + 1
        deals.pop(a["item_id"], None)                 # revue : plus un deal (encan dont la mise a monte...)
        return
    med_a, source_a, n_a, ventes_a = va
    if t > med_a * RATIO_DEAL:
        st["_res"] = ("pres" if t <= med_a * RATIO_PRES and not a.get("encan") else "trop_cher", round(t / med_a, 3))
        st["trop_cher"] = st.get("trop_cher", 0) + 1
        deals.pop(a["item_id"], None)
        if t <= med_a * RATIO_PRES and not a.get("encan"):      # a surveiller : sous la valeur, pas encore un deal
            st.setdefault("_pres", {})[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"),
                                                         "url": a.get("url"), "valeur": med_a, "ratio": round(t / med_a, 3), "encan": False,
                                                         "joueur": r.get("joueur"), "q": _q_deal(r), "vedette": bool(r.get("vedette")), "flux": r.get("flux"), "n": n_a,
                                                         "vendues": ventes_a or [], "sport": r.get("sport") or "hockey",
                                                         "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION, "palier": "pres"}
        return
    st["_res"] = ("deal", round(t / med_a, 3))
    st["deals"] = st.get("deals", 0) + 1
    if est_hit:
        st["hits_deals"] = st.get("hits_deals", 0) + 1
        if not _recrue(cib):
            st["vedettes_deals"] = st.get("vedettes_deals", 0) + 1
    import sports
    joueur = r.get("joueur") or " ".join(w.capitalize() for w in cib["joueur"].split())
    sport = r.get("sport") or (sport_carte(a.get("titre"), cib) if r.get("suivi") else None) or sports.detecter(a.get("titre") or "", defaut="hockey")
    deals[a["item_id"]] = {"item_id": a["item_id"], "titre": a["titre"], "total": t, "photo": a.get("photo"), "url": a.get("url"),
                           "valeur": med_a, "ratio": round(t / med_a, 3), "encan": bool(a.get("encan")), "fin": fin,
                           "mises": a.get("mises"), "sport": sport, "joueur": joueur, "q": _q_deal(r), "vedette": bool(r.get("vedette")), "flux": r.get("flux"),
                           "n": n_a, "valeur_source": source_a, "vendues": ventes_a or ventes_requete or [],
                           # 27 oct 2026 : encan - la mise maximale pour que ca reste un deal (70 % de la valeur, port compris)
                           "port": a.get("port_cad"), "mise_max": round(med_a * RATIO_DEAL - (a.get("port_cad") or 0), 2) if a.get("encan") else None,
                           "comps": comps or [], "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION,
                           "vendeur": a.get("vendeur")}


SUIVIS_MAX = 400                 # 29 oct 2026 : encans de veterans / legendes des vendeurs suivis gardes pour l'ecran


_HORS_SPORTS = re.compile(r"\b(world cup|fifa|uefa|premier league|serie a|la liga|bundesliga|ligue 1|mls|soccer|futbol|tennis|atp|wta|golf|pga|"
                          r"formula 1|\bf1\b|ufc|mma|wwe|wrestling|boxing|nascar|pok[eé]mon|yu-?gi-?oh|magic the gathering|one piece|lorcana)\b", re.I)
_JOUEURS_HOCKEY = None


def sport_carte(titre, cib=None):
    """29 oct 2026 (Mathieu : « pour les legendes on dirait tout sauf du hockey ») : le sport d'une carte des vendeurs
    suivis, avec une PREUVE : hockey si le titre le dit (set, equipe LNH...) ou si le joueur est un joueur de hockey connu ;
    un autre sport de l'app (NFL, NBA, MLB) s'il gagne nettement. Soccer, tennis, Pokemon... et les cartes sans preuve :
    None (pas montrees)."""
    global _JOUEURS_HOCKEY
    import sports
    t = str(titre or "")
    if _HORS_SPORTS.search(t):
        return None
    sc = sports.scores(t)
    if _JOUEURS_HOCKEY is None:
        try:
            import valeurs
            _JOUEURS_HOCKEY = {str(j).lower() for j in ((valeurs._charger() or {}).get("joueurs") or {})} | {v.lower() for v in VEDETTES}
        except Exception:
            _JOUEURS_HOCKEY = {v.lower() for v in VEDETTES}
    j = str((cib or {}).get("joueur") or "").lower()
    if (j and j in _JOUEURS_HOCKEY) or (sc.get("hockey", 0) >= 2 and sc["hockey"] >= max(sc.values())):
        return "hockey"
    m = max(sc.values())
    gagnants = [k for k, v in sc.items() if v == m]
    return gagnants[0] if m >= 2 and len(gagnants) == 1 else None


def _noter_suivi(st, a, bassin, maint):
    """29 oct 2026 (Mathieu : « je ne vois toujours pas les cartes non rookie » ; « chez Savage, Remi, Slab Sharks… je les
    veux TOUS ») : chaque ENCAN d'un vendeur suivi qui est une carte de veteran, de legende ou de jeune de 2e a 4e annee
    (pas une recrue de l'annee) et qui vaut la peine (hit, gradee, vintage, vedette) est garde pour l'ecran Deals, MEME
    sans valeur verifiee : « Encans de vétérans et légendes ». Sa valeur s'affiche seulement si elle est sure (ventes
    reelles de la meme carte) ; sinon « valeur à vérifier ». Aucun credit SoldComps."""
    import cartes_match
    if not a.get("encan") or not a.get("item_id"):
        return "prix_fixe"
    cib = cartes_match.cible_titre(a.get("titre") or "")
    if cib.get("exclu") or not cib.get("joueur"):
        return "joueur_inconnu"
    # 30 oct 2026 (Mathieu : « on doit voir tous les deals, rookie pas rookie, chez les gros vendeurs surtout ») : les
    # recrues de l'annee sont gardees aussi (classees apres les veterans a l'ecran)
    rec = bool(_recrue(cib))
    if not (_precieuse(cib) or cib.get("rc") or cib.get("yg")):
        return "ordinaire"                           # 29 oct : la recrue d'un veteran (Ovechkin YG 2005) compte aussi
    if cartes_match.abimee(a.get("titre") or "") or vendeur_risque(a):
        return "abimee"
    sport = sport_carte(a.get("titre"), cib)
    if not sport:
        return "pas_hockey"                                      # soccer, tennis, sans preuve : pas dans SlabCoach (hockey d'abord)
    f = a.get("fin")
    fd = None
    try:
        fd = datetime.fromisoformat(str(f).replace("Z", "+00:00"))
    except ValueError:
        return "fin"
    if fd < maint or fd - maint > timedelta(hours=ENCAN_SUIVI_H):
        return "fin"
    t = _total(a)
    an = cib.get("annee")
    if not (_hit(cib) or cib.get("grade") or (an and int(an) < 1995) or t >= 20):
        return "base"                                # une carte de base d'une vedette a 3 $ : pas un encan a montrer
    va = valeur_annonce(a, bassin.candidats(cib) if bassin else [], [], cib=cib)
    st.setdefault("_suivis", {})[str(a["item_id"])] = {
        "item_id": str(a["item_id"]), "titre": a.get("titre"), "total": t, "photo": a.get("photo"), "url": a.get("url"),
        "encan": True, "fin": f, "mises": a.get("mises"), "port": a.get("port_cad"), "vendeur": a.get("vendeur"),
        "valeur": va[0] if va else None, "n": va[2] if va else 0, "vendues": va[3] if va else [],
        "mise_max": round(va[0] * RATIO_DEAL - (a.get("port_cad") or 0), 2) if va else None,
        "sport": sport, "vu_le": maint.isoformat(timespec="seconds"), "v": VERSION, "suivi": True, "recrue": rec}
    return "ok_recrue" if rec else "ok"


def _q_deal(r):
    """29 oct 2026 (Mathieu : « on voit encore juste des Young Guns et des Future Watch ») : une recherche de vedette
    (« Wayne Gretzky auto ») trouve TOUTES les cartes du joueur (patchs, /25, /99...). Le deal gardait cette requete, et
    valide() comparait la carte a « Wayne Gretzky auto » : un patch ou une numerotee etait refuse a la sauvegarde. Tous les
    deals de veterans et de legendes trouves par joueur etaient jetes. Le deal ne garde donc pas la requete d'une vedette
    (comme les flux) : il est juge sur SA carte."""
    return None if r.get("vedette") else r.get("q")


def _cle_erreur(err):
    """29 oct 2026 (Mathieu : « 31 000 refusées ?! ») : le plafond du jour de SlabCoach (aucun appel, aucun credit) n'est pas
    une erreur de SoldComps ; les deux sont comptes a part dans l'admin."""
    return "verif_plafond" if str(err) in ("plafond du jour", "inactif") else "erreurs_ventes"


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


def _verifier_tard(st, deals, maint, bassin, verif, d=None):
    """27 oct 2026 (Mathieu : la Savoie Draft Day Marks /35 a 50 $, qui finit dans 25 h) : les encans de hits sans ventes
    connues qui finissent dans 6 a 30 h, verifies a la fin du tour avec le budget qui reste, les plus proches de la fin d'abord."""
    tard = st.pop("_tard", [])
    # les encans d'abord (le plus proche de la fin), puis les prix fixes (le plus cher d'abord : plus de profit possible)
    # 29 oct 2026 : dans chaque groupe, les veterans et les legendes passent avant les recrues
    # 29 oct 2026 (Mathieu : « on doit passer toutes les cartes de ces vendeurs, ensuite on analyse le reste ») : les vendeurs
    # suivis d'abord (encans puis prix fixe), ensuite le reste
    tard.sort(key=lambda x: (0 if x[1].get("suivi") else 1, 0, 1 if _recrue(x[2]) else 0, 0 if _precieuse(x[2]) else 1, str(x[0].get("fin")), 0)
              if x[0].get("encan") else (0 if x[1].get("suivi") else 1, 1, 1 if _recrue(x[2]) else 0, 0 if _precieuse(x[2]) else 1, "", -(_total(x[0]) or 0)))
    tard.sort(key=lambda x: 0 if x[1].get("prio") else 1)                    # 30 oct : la reserve d'abord (tri stable)
    tard.sort(key=lambda x: (rang_vendeur(x[0].get("vendeur")), 0 if x[0].get("encan") else 1, str(x[0].get("fin") or ""), -(_total(x[0]) or 0))
              if x[1].get("prio") else (9,))
    # 30 oct : dans la reserve, par vendeur (Savage d'abord), les encans qui finissent le plus tot d'abord
    fini = {"prio": False, "std": False}
    for a, r, cib in tard:
        k = "prio" if r.get("prio") else "std"
        if fini[k]:
            continue
        avant = st.get("verif_budget", 0)
        st.pop("_dern_verif", None)
        nv = verif(cib, prio=True) if k == "prio" else verif(cib)
        if st.get("verif_budget", 0) > avant:
            # 31 oct : le budget du chasseur est epuise : les autres cartes s'arretent ; une carte des 4 vendeurs aussi
            # (sa reserve est deja vide, sinon elle n'aurait pas touche au budget du chasseur)
            fini["std"] = True
            if k == "prio":
                fini["prio"] = True
            continue
        if k == "prio" and nv is not None:
            st.setdefault("_prio_cov", {})[str(a.get("item_id"))] = True
        dv = st.pop("_dern_verif", None)
        st["_vus"].discard(a.get("item_id"))
        _juger(a, r, nv or [], [], maint, deals, st, bassin=bassin, verif=None)
        if d is not None:
            _publier(d, deals, maint, st)
        # 30 oct 2026 : l'encan d'un vendeur suivi, deja garde sans valeur, prend la valeur trouvee
        s_ = (st.get("_suivis") or {}).get(str(a.get("item_id")))
        if s_ is not None and not s_.get("valeur"):
            va = valeur_annonce(a, (nv or []) + (bassin.candidats(cib) if bassin else []), [], cib=cib)
            if va:
                s_.update(valeur=va[0], n=va[2], vendues=va[3], mise_max=round(va[0] * RATIO_DEAL - (a.get("port_cad") or 0), 2))
        if dv:
            _noter_journal(st, a, r, cib, dv)


def _noter_couverture(st, maint):
    """31 oct 2026 : combien de cartes des 4 vendeurs ont ete analysees ce tour (valeur trouvee ou ventes cherchees)."""
    cov, vend = st.get("_prio_cov") or {}, st.get("_prio_v") or {}
    par = {}
    for k, ok in cov.items():
        p = par.setdefault(vend.get(k) or "?", [0, 0])
        p[1] += 1
        p[0] += 1 if ok else 0
    st["_couverture"] = {"le": maint.isoformat(timespec="seconds"), "total": len(cov), "faites": sum(1 for v in cov.values() if v),
                         "par_vendeur": par}


def _sauver(d, deals, maint, st, **champs):
    garde_ = _ranger(d, deals, maint)
    st.pop("_vus", None)
    st.pop("_tard", None)
    nouveaux_pres = st.pop("_pres", {})
    nouveaux_retires = st.pop("_retires", [])
    journal = st.pop("_journal", [])
    nouveaux_suivis = st.pop("_suivis", None)
    st.pop("_dern_verif", None)
    st.pop("_res", None)
    couverture = st.pop("_couverture", None)
    st.pop("_prio_cov", None)
    st.pop("_prio_v", None)
    with _verrou:
        d2 = lire()
        if couverture:
            d2["prio_couverture"] = couverture
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
        if journal:
            d2["journal"] = ((d2.get("journal") or []) + journal)[-JOURNAL_MAX:]
        if nouveaux_suivis is not None:                  # 29 oct : les encans de veterans des vendeurs suivis (ce tour-ci)
            vieux = {str(x.get("item_id")): x for x in d2.get("suivis") or [] if encore_ouvert(x, maint)
                     and str(x.get("vu_le") or "") >= (maint - timedelta(hours=FRAICHEUR_EBAY_H)).isoformat()}
            for k, x in nouveaux_suivis.items():
                vieux[str(k)] = _fusion_suivi(vieux.get(str(k)), x)
            # 30 oct 2026 : la limite garde d'abord Savage, Remi, CF31 et Slab Sharks (Slab Sharks a enormement d'encans)
            d2["suivis"] = sorted((x for k, x in vieux.items() if k not in ids and str(k) not in retires),
                                  key=lambda x: (rang_vendeur(x.get("vendeur")), str(x.get("fin"))))[:_env_int("LR_SUIVIS_MAX", SUIVIS_MAX)]
        _diag(d2, **st)
        _ecrire(d2)
    return garde_


PUBLIER_S = 30


def _fusion_suivi(vieux, x):
    """31 oct 2026 : un encan suivi deja valorise (entre deux tours) garde sa valeur, mais prend la mise, le port et la fin
    du moment (avant : la nouvelle mise etait ignoree, ou la valeur effacee a la fin du tour)."""
    if vieux and vieux.get("valeur") and not x.get("valeur"):
        y = dict(x)
        for k in ("valeur", "n", "vendues"):
            y[k] = vieux.get(k)
        y["mise_max"] = round(vieux["valeur"] * RATIO_DEAL - (x.get("port") or 0), 2)
        return y
    return x


def _publier(d, deals, maint, st, force=False):
    """30 oct 2026 (Mathieu : « les deals doivent arriver aussitot qu'ils sont calcules, pas en mega batch aux heures ») :
    pendant un tour, les deals et les encans des gros vendeurs trouves jusqu'ici sont publies (au plus aux 30 s), sans
    attendre la fin de l'etape. La fin de l'etape (_sauver) fait le reste (retraits, journal, statistiques)."""
    if not force and time.time() - st.get("_pub_le", 0) < PUBLIER_S:
        return False
    st["_pub_le"] = time.time()
    garde_ = _ranger(d, deals, maint)
    ns = dict(st.get("_suivis") or {})
    with _verrou:
        d2 = lire()
        retires = {str(k) for k in (d2.get("retires") or {})}
        d2["deals"] = [x for x in garde_ if str(x["item_id"]) not in retires]
        if ns:
            ids = {str(x["item_id"]) for x in d2["deals"]}
            vieux = {str(x.get("item_id")): x for x in d2.get("suivis") or [] if encore_ouvert(x, maint)}
            for k, x in ns.items():
                vieux[str(k)] = _fusion_suivi(vieux.get(str(k)), x)
            d2["suivis"] = sorted((x for k, x in vieux.items() if k not in ids and k not in retires),
                                  key=lambda x: (rang_vendeur(x.get("vendeur")), str(x.get("fin"))))[:_env_int("LR_SUIVIS_MAX", SUIVIS_MAX)]
        _ecrire(d2)
    return True


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


def chasser(n=PAR_TOUR, rechercher=None, bassin=None, vedettes=False):
    """Prix fixe : n requetes joueur (on reprend la ou on etait), les annonces les plus RECENTES d'abord (les bons prix
    partent vite) ; deals gardes 48 h."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    bassin = bassin if bassin is not None else bassin_partage()
    d = lire()
    reqs = requetes()
    cle = "curseur"
    if vedettes:                                         # 29 oct 2026 : admin « Chasser veterans et legendes maintenant »
        reqs, cle = [r for r in reqs if r.get("vedette")], "curseur_v"
    if not reqs:
        return {"ok": True, "deals": 0}
    i0 = int(d.get(cle) or 0) % len(reqs)
    lot = (reqs[i0:] + reqs[:i0])[:n]
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    for i_r, r in enumerate(lot):
        _progres(detail=f"{i_r + 1}/{len(lot)}")
        try:
            fixes = rechercher(r["q"], categorie="261328", limite=100, fond=True, recentes=True)
        except (RuntimeError, OSError):
            st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
            break
        st["requetes"] = st.get("requetes", 0) + 1
        _c, memes, _e = _memes(r, fixes)
        # chaque annonce a SA valeur, celle des ventes de la MEME carte (2 au moins), sinon pas de deal
        # 29 oct 2026 : « Wayne Gretzky auto » melange toutes ses cartes : une recherche SoldComps pour ca ne sert a rien
        # (credits perdus). Les vedettes : ventes en cache seulement ; chaque carte a sa verification ciblee au besoin
        brut_v, err = _ventes(r["q"], cache_seul=bool(r.get("vedette")))
        if err:
            k = _cle_erreur(err)
            st[k] = st.get(k, 0) + 1
        bassin.ajouter(brut_v)
        med = cartes_match.mediane_robuste([_total(x) for x in memes])[0] if memes else None
        comps = sorted(({"titre": x["titre"], "total": _total(x), "photo": x.get("photo"), "url": x.get("url")} for x in memes),
                       key=lambda x: abs(x["total"] - (med or 0)))[:8]
        if r.get("vedette"):
            comps = []                                   # des cartes differentes du meme joueur : pas des comparables
        for a in memes:
            _juger(a, r, brut_v, memes, maint, deals, st, comps=comps, bassin=bassin, verif=verif)
        _publier(d, deals, maint, st)
    _verifier_tard(st, deals, maint, bassin, verif, d)          # 29 oct : les hits a prix fixe des vedettes aussi
    garde_ = _sauver(d, deals, maint, st, **{cle: (i0 + len(lot)) % len(reqs)}, maj=maint.isoformat(timespec="seconds"))
    return {"ok": True, "deals": len(garde_), "nouveaux": st.get("deals", 0), "stats": st}


def encans(n=PAR_TOUR_ENCANS, rechercher=None, bassin=None, vedettes=False):
    """26 oct 2026 (Mathieu : « aucune enchere se terminant ? ») : chaque heure, n recherches d'ENCANS (ceux qui finissent
    le plus tot, 48 h et moins) : toute la liste en 3 h. La valeur vient des ventes
    deja connues (le bassin) et, pour un encan prometteur qui finit dans 3 h, d'une recherche ciblee."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    bassin = bassin if bassin is not None else bassin_partage()
    d = lire()
    reqs = requetes()
    cle = "curseur_e"
    if vedettes:
        reqs, cle = [r for r in reqs if r.get("vedette")], "curseur_ev"
    if not reqs:
        return {"ok": True}
    i0 = int(d.get(cle) or 0) % len(reqs)
    lot = (reqs[i0:] + reqs[:i0])[:n]
    maint = datetime.now(timezone.utc)
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    for i_r, r in enumerate(lot):
        _progres(detail=f"{i_r + 1}/{len(lot)}")
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
        _publier(d, deals, maint, st)
    _verifier_tard(st, deals, maint, bassin, verif, d)
    garde_ = _sauver(d, deals, maint, st, **{cle: (i0 + len(lot)) % len(reqs)})
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
# 29 oct 2026 (Mathieu : « on doit passer toutes les cartes de ces vendeurs et des autres gros vendeurs de cartes de hockey,
# ensuite on analyse le reste ») : pseudos verifies sur eBay le 29 oct. CF31 = « cf31_sports_cards » (pas « cf_31 »).
# Groupe 1 : les specialistes du hockey ; groupe 2 : les mega-vendeurs multi-sports (leurs cartes de hockey seulement).
VENDEURS_DEFAUT = ["savage.cards", "remi-card-trader", "cf31_sports_cards", "slabsharksinc", "wests01",     # hockey
                   "ultsportscards", "rakesecret", "sforget76", "dcsports87", "probstein123"]                 # + mega-vendeurs
# 30 oct 2026 (Mathieu : « toujours passer le scan avec Savage en premier, ensuite Remi, ensuite CF31, Slab Sharks et le
# reste ») : ces 4 vendeurs sont cherches SEULS (chacun ses pages d'encans, jamais noyes dans un groupe), dans cet ordre,
# avant tous les autres ; leurs deals et leurs encans passent aussi devant a l'ecran, dans le meme ordre.
VENDEURS_PRIORITE = ["savage.cards", "remi-card-trader", "cf31_sports_cards", "slabsharksinc"]


def rang_vendeur(v):
    """0 Savage, 1 Remi, 2 CF31, 3 Slab Sharks, 4 les autres vendeurs suivis, 5 le reste."""
    v = str(v or "").lower()
    if v in VENDEURS_PRIORITE:
        return VENDEURS_PRIORITE.index(v)
    return 4 if v and v in {x.lower() for x in vendeurs_suivis()} else 5


def groupes_vendeurs(vs=None):
    """Les recherches de vendeurs, dans l'ordre : chaque prioritaire seul, puis les autres par groupes de 5."""
    vs = list(vs if vs is not None else vendeurs_suivis())
    prio = [v for p in VENDEURS_PRIORITE for v in vs if v.lower() == p]
    autres = [v for v in vs if v.lower() not in VENDEURS_PRIORITE]
    return [[v] for v in prio] + [autres[k:k + VENDEURS_PAR_APPEL] for k in range(0, len(autres), VENDEURS_PAR_APPEL)]
VENDEURS_PAR_APPEL = 5                   # 5 vendeurs par recherche : chaque groupe a ses 10 pages d'encans (2 000)
VENDEURS_V = 2


def vendeurs_suivis():
    e = os.environ.get("LR_DEALS_VENDEURS")
    if e:
        return [x.strip() for x in e.split(";") if x.strip()]
    d = lire_vite()
    v = d.get("vendeurs")
    if not isinstance(v, list):
        return list(VENDEURS_DEFAUT)
    if int(d.get("vendeurs_v") or 0) < VENDEURS_V:
        # 29 oct 2026 : une liste reglee avant : « cf_31 » corrige, et les nouveaux gros vendeurs de hockey ajoutes
        v = ["cf31_sports_cards" if x.lower() == "cf_31" else x for x in v]
        v += [x for x in VENDEURS_DEFAUT if x.lower() not in {y.lower() for y in v}]
        ordre = {x.lower(): i for i, x in enumerate(VENDEURS_DEFAUT)}
        v.sort(key=lambda x: ordre.get(x.lower(), len(ordre)))
    return list(v)


def tester_vendeurs(rechercher=None, maint=None):
    """29 oct 2026 (Mathieu : « Top vendeurs : toujours rien ») : l'admin voit, vendeur par vendeur, ce qu'eBay renvoie
    MAINTENANT (encans et prix fixe de la categorie des cartes) et pourquoi chaque encan est garde ou non. 2 recherches
    eBay par vendeur, aucun credit SoldComps."""
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    maint = maint or datetime.now(timezone.utc)
    out = []
    for v in vendeurs_suivis()[:12]:
        x = {"vendeur": v, "encans": 0, "prix_fixe": 0, "gardes": 0, "raisons": {}, "exemples": [], "erreur": None}
        for ench in (True, False):
            try:
                l = rechercher("", categorie="261328", limite=200, fond=False, encheres=ench, recentes=not ench, flux=True, vendeurs=[v])
            except (RuntimeError, OSError, TypeError) as e:
                x["erreur"] = str(e)[:200]
                break
            x["encans" if ench else "prix_fixe"] = len(l)
            if not ench:
                continue
            st = {}
            for a in l:
                k = (_noter_suivi(st, a, None, maint) or "ok") if cartes_match.est_carte(a.get("titre") or "") else "pas_carte"
                x["raisons"][k] = x["raisons"].get(k, 0) + 1
                if k == "ok":
                    x["gardes"] += 1
                    if len(x["exemples"]) < 3:
                        x["exemples"].append(a.get("titre") or "")
        out.append(x)
    d = lire_vite()
    lim = (maint - timedelta(hours=6)).isoformat()
    return {"ok": True, "vendeurs": out, "suivis_fichier": len(d.get("suivis") or []),
            "suivis_frais": sum(1 for y in d.get("suivis") or [] if str(y.get("vu_le") or "") >= lim),
            "deals_vendeurs": sum(1 for y in d.get("deals") or [] if y.get("flux") == "vendeurs")}


VENDEURS_PERSO_MAX = 3            # 30 oct 2026 : « mes vendeurs a moi » (Pro), par compte
VENDEURS_PERSO_TOTAL = 30         # tous comptes confondus : le budget eBay du chasseur


def regler_vendeurs_perso(compte, liste):
    """Les vendeurs ajoutes par un compte : chasses avec les vendeurs suivis (apres eux). -> la liste gardee."""
    l = []
    for x in liste or []:
        x = re.sub(r"[^A-Za-z0-9._-]", "", str(x).strip().lstrip("@"))[:64].lower()
        if x and x not in l:
            l.append(x)
    l = l[:VENDEURS_PERSO_MAX]
    with _verrou:
        d = lire()
        p = d.get("vendeurs_perso") if isinstance(d.get("vendeurs_perso"), dict) else {}
        if l:
            p[str(compte)] = l
        else:
            p.pop(str(compte), None)
        d["vendeurs_perso"] = p
        _ecrire(d)
    return l


def vendeurs_perso():
    """Les vendeurs ajoutes par les comptes (sans les suivis), les plus demandes d'abord, 30 au plus."""
    p = lire_vite().get("vendeurs_perso") or {}
    suivis = {v.lower() for v in vendeurs_suivis()}
    compte = {}
    for l in p.values():
        for v in l or []:
            if v.lower() not in suivis:
                compte[v.lower()] = compte.get(v.lower(), 0) + 1
    return [v for v, _n in sorted(compte.items(), key=lambda kv: -kv[1])][:VENDEURS_PERSO_TOTAL]


def groupes_chasse():
    """Toutes les recherches de vendeurs d'un tour : les suivis (prioritaires seuls d'abord), puis les vendeurs ajoutes
    par les comptes, en leurs propres groupes de 5."""
    pv = vendeurs_perso()
    return groupes_vendeurs(vendeurs_suivis()) + [pv[k:k + VENDEURS_PAR_APPEL] for k in range(0, len(pv), VENDEURS_PAR_APPEL)]


def regler_vendeurs(liste):
    l = []
    for x in liste or []:
        x = re.sub(r"[^A-Za-z0-9._-]", "", str(x).strip().lstrip("@"))[:64]
        if x and x.lower() not in [y.lower() for y in l]:
            l.append(x)
    with _verrou:
        d = lire()
        d["vendeurs"] = l[:40]
        d["vendeurs_v"] = VENDEURS_V
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
    bassin = bassin if bassin is not None else bassin_partage()
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
    limite_suivi = (maint + timedelta(hours=ENCAN_SUIVI_H)).isoformat().replace("+00:00", "Z")
    grps = groupes_chasse()
    titres_vus = []                                   # 31 oct 2026 : pour apprendre les produits et inserts (produits_appris)
    for i_g, grp in enumerate(grps):
        _progres(detail=f"vendeurs:{i_g + 1}/{len(grps)}")
        rv = {"q": None, "flux": "vendeurs", "sport": None, "joueur": None, "suivi": True}
        # 30 oct 2026 : prix fixe : les 600 plus recentes (3 pages) ; un gros vendeur en met des centaines par jour
        # 31 oct 2026 : le groupe des gros vendeurs : leurs encans seulement (leurs prix fixes passent par les recherches normales)
        fixe_fini = all(rang_vendeur(v) < len(VENDEURS_PRIORITE) for v in grp)
        for ench, page in [(False, k) for k in range(PAGES_FIXE_SUIVIS)] + [(True, j) for j in range(max(pages, PAGES_SUIVIS))]:
            if not ench and fixe_fini:
                continue
            try:
                l = rechercher("", categorie="261328", limite=200, fond=True, encheres=ench, recentes=not ench, flux=True, offset=200 * page, vendeurs=grp)
            except (RuntimeError, OSError, TypeError):
                st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
                st["vendeurs_erreurs"] = st.get("vendeurs_erreurs", 0) + 1
                break
            st["requetes_flux"] = st.get("requetes_flux", 0) + 1
            st["vendeurs_annonces"] = st.get("vendeurs_annonces", 0) + len(l)
            l = [a for a in l if cartes_match.est_carte(a.get("titre") or "")]
            titres_vus.extend(a.get("titre") or "" for a in l)
            for a in l:
                st.pop("_res", None)
                _juger(a, rv, [], [] if ench else l, maint, deals, st, bassin=bassin, verif=verif)
                if _prio(a) and a.get("encan") and st.get("_res"):
                    cov = st.setdefault("_prio_cov", {})
                    cov[str(a.get("item_id"))] = cov.get(str(a.get("item_id"))) or st["_res"][0] != "sans_ventes"
                    st.setdefault("_prio_v", {})[str(a.get("item_id"))] = a.get("vendeur")
                k_s = "suivi_" + (_noter_suivi(st, a, bassin, maint) or "ok")
                st[k_s] = st.get(k_s, 0) + 1
            _publier(d, deals, maint, st)
            if not ench and len(l) < 150:
                fixe_fini = True                       # plus d'autres annonces a prix fixe : on passe aux encans
            if ench and (len(l) < 150 or not l or str(l[-1].get("fin") or "9") > limite_suivi):
                break
    # 31 oct 2026 (Mathieu : « toutes les cartes des gros vendeurs favoris TOUTES analysees avant de passer au reste ») :
    # les cartes de Savage, Remi, CF31 et Slab Sharks sans valeur sont verifiees ICI, avant les flux de hits et de recrues
    # (qui depensent le budget du chasseur) ; la reserve d'abord, puis le budget du chasseur
    tard = st.pop("_tard", [])
    st["_tard"] = [x for x in tard if x[1].get("prio")]
    _progres(detail="gros vendeurs : analyse")
    _verifier_tard(st, deals, maint, bassin, verif, d)
    st["_tard"] = [x for x in tard if not x[1].get("prio")] + st.get("_tard", [])
    _noter_couverture(st, maint)
    # 28 oct 2026 (Mathieu : « les maudits deals sont encore juste des Young Guns ») : les flux larges de recrues (Young
    # Guns, rookies) un tour sur deux seulement ; les appels eBay economises vont aux hits (2 fois plus de flux de hits)
    tour_n = int(d.get("tour_n") or 0)
    recrues = flux_liste() if tour_n % 2 == 0 or os.environ.get("LR_DEALS_FLUX") else []
    tous_f = hits + recrues
    for i_f, (q, sport) in enumerate(tous_f):            # 28 oct : les hits d'abord (le budget de verification va aux hits)
        _progres(detail=f"flux:{i_f + 1}/{len(tous_f)}")
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
            titres_vus.extend(a.get("titre") or "" for a in l)
            for a in l:
                _juger(a, r, [], [] if ench else l, maint, deals, st, bassin=bassin, verif=verif)
            _publier(d, deals, maint, st)
            if ench and (len(l) < 150 or not l or str(l[-1].get("fin") or "9") > limite_fin):
                break                                   # derniere page, ou on depasse 48 h
    _verifier_tard(st, deals, maint, bassin, verif, d)
    try:
        import produits_appris
        st["produits_appris"] = produits_appris.apprendre(titres_vus)
    except Exception as e:
        print("Produits appris : " + repr(e), flush=True)
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


# 31 oct 2026 (Mathieu : « les cartes qui arrivent a la fin, les 2 dernieres heures : rafraichir le prix eBay assez souvent,
# le deal change et peut rapidement devenir un faux deal » ; « se faire retirer du dashboard si ce n'est plus un deal ») :
# aux 5 min, les encans (deals et encans des gros vendeurs) qui finissent dans 2 h sont relus sur eBay, 20 par appel
# (getItems, jamais le cache). Mise du moment au-dessus de 70 % de la valeur -> il sort des deals ; fini -> il sort.
FIN_PROCHE_H = 2
FIN_PROCHE_PAS_S = 300
FIN_PROCHE_APPELS = 8                      # au plus 160 annonces par passe


def fin_proche_si_besoin():
    if _ETAT.get("fin_proche") or time.time() - _ETAT.get("fin_proche_le", 0) < FIN_PROCHE_PAS_S:
        return None
    _ETAT["fin_proche"], _ETAT["fin_proche_le"] = True, time.time()
    try:
        return fin_proche()
    except Exception as e:
        print("Deals (fin proche) : " + repr(e), flush=True)
        return None
    finally:
        _ETAT["fin_proche"] = False


def fin_proche(lire_lot=None, maint=None):
    import ebay_compte
    lire_lot = lire_lot or (lambda ids: ebay_compte.articles_lot(ids, fond=True))
    maint = maint or datetime.now(timezone.utc)
    lim = (maint + timedelta(hours=FIN_PROCHE_H)).isoformat().replace("+00:00", "Z")
    d = lire_vite()
    a_lire = {}
    for x in (d.get("deals") or []) + (d.get("suivis") or []):
        if x.get("encan") and encore_ouvert(x, maint) and str(x.get("fin") or "9") <= lim:
            a_lire.setdefault(str(x["item_id"]), str(x.get("fin")))
    ids = sorted(a_lire, key=lambda i: a_lire[i])[:20 * FIN_PROCHE_APPELS]          # ceux qui finissent le plus tot d'abord
    lus, demandes = {}, set()
    for k in range(0, len(ids), 20):
        lot = ids[k:k + 20]
        try:
            lus.update(lire_lot(lot))
            demandes.update(lot)
        except (RuntimeError, OSError) as e:
            print("Deals (fin proche) : " + repr(e), flush=True)
            break
    if not demandes:
        return {"ok": True, "lus": 0, "sortis": 0}
    vu = maint.isoformat(timespec="seconds")
    sortis = []

    def maj(x):
        """True = garder ; False = sortir (fini, ou plus un deal)."""
        iid = str(x.get("item_id"))
        if iid not in demandes:
            return True
        a = lus.get(iid)
        if a is None:                                  # absent de la reponse : fini ou retire... si la fin est passee
            return encore_ouvert(x, maint)
        t = _total(a)
        if a.get("fin"):
            x["fin"] = a["fin"]
        if not t or not encore_ouvert(x, maint):
            return False
        x.update(total=t, mises=a.get("mises", x.get("mises")), port=a.get("port_cad", x.get("port")), vu_le=vu)
        if x.get("valeur"):
            x["ratio"] = round(t / x["valeur"], 3)
        return True

    with _verrou:
        d2 = lire()
        garde = []
        for x in d2.get("deals") or []:
            ok = maj(x)
            if ok and x.get("valeur") and str(x.get("item_id")) in demandes and (x.get("total") or 0) > x["valeur"] * RATIO_DEAL:
                ok = False                                 # la mise a monte : plus un deal
            (garde if ok else sortis).append(x)
        d2["deals"] = garde
        d2["suivis"] = [x for x in d2.get("suivis") or [] if maj(x)]
        d2["fin_proche"] = {"le": vu, "lus": len(demandes), "sortis": len(sortis)}
        _ecrire(d2)
    _LU["cle"] = None
    return {"ok": True, "lus": len(demandes), "sortis": len(sortis)}


def recharger():
    """28 oct 2026 (Mathieu : « on doit recharger les deals ») : un tour complet tout de suite (admin), sans attendre
    l'heure et sans le rythme du budget eBay (le plafond du jour, lui, tient toujours)."""
    import appels_ebay
    if _ETAT["en_cours"]:
        return {"ok": True, "deja": True}
    if _ETAT.get("tour_demande"):
        return {"ok": True, "deja": True, "attente": True}          # 31 oct 2026 : un seul tour demande a la fois
    appels_ebay.liberer(900)
    if chasser_si_besoin(force=True):
        return {"ok": True, "lance": True}
    _ETAT["tour_demande"] = True                     # 31 oct 2026 : la passe des encans finit, puis le tour part
    if not _ETAT.get("proches"):
        def attendre():
            for _ in range(60):                      # au plus 5 min : un autre processus tient peut-etre le verrou
                time.sleep(5)
                if not _ETAT.get("tour_demande"):
                    return
                if chasser_si_besoin(force=True):
                    _ETAT.pop("tour_demande", None)
                    return
            _ETAT.pop("tour_demande", None)
        threading.Thread(target=attendre, daemon=True, name="deals-attente").start()
    return {"ok": True, "lance": False, "attente": True}


VEDETTES_PAR_CHASSE = 40         # 29 oct 2026 : admin « Chasser veterans maintenant » : 40 recherches prix fixe + 40 encans


def chasser_vedettes():
    """29 oct 2026 (Mathieu : « depuis le debut de la journee je te demande des legendes et des veterans ») : un tour
    seulement pour les veterans, les legendes et les jeunes de 2e a 4e annee, tout de suite (admin). Le budget du jour
    (eBay et SoldComps) tient toujours."""
    import appels_ebay
    with _verrou:
        if _ETAT["en_cours"] or not _prendre_tour():
            return {"ok": True, "deja": True}
        _ETAT["en_cours"] = True
        _ETAT["essai_le"] = time.time()
    appels_ebay.liberer(900)

    def tache():
        _ETAT.update(debut=time.time(), etape="vedettes", detail=None)
        try:
            b = bassin_partage()
            for f in (chasser, encans):
                try:
                    f(VEDETTES_PAR_CHASSE, bassin=b, vedettes=True)
                except Exception as e:
                    print("Deals (vedettes) : " + repr(e), flush=True)
        finally:
            _ETAT.update(en_cours=False, etape=None, detail=None)
            _rendre_tour()
    threading.Thread(target=tache, daemon=True, name="deals-vedettes").start()
    return {"ok": True, "lance": True}


def tour(d=None):
    """Ou en est le chasseur : en cours (etape i/4, progression, depuis, fin estimee) ou le prochain tour."""
    d = d or lire_vite()
    der = d.get("dernier_tour") or {}
    duree = der.get("duree_s") or 1800
    if _ETAT.get("en_cours"):
        deb = _ETAT.get("debut") or _ETAT.get("essai_le") or time.time()
        n, lib = ETAPES.get(_ETAT.get("etape") or "", (1, "Vétérans et légendes"))
        if _ETAT.get("etape") == "vedettes":
            duree = 600
        return {"en_cours": True, "debut": datetime.fromtimestamp(deb, timezone.utc).isoformat(timespec="seconds"),
                "etape": _ETAT.get("etape"), "etape_n": n, "etapes": 1 if _ETAT.get("etape") == "vedettes" else len(ETAPES), "etape_lib": lib, "detail": _ETAT.get("detail"),
                "fin_estimee": datetime.fromtimestamp(max(deb + duree, time.time() + 60), timezone.utc).isoformat(timespec="seconds"),
                "dernier": der or None}
    try:
        m = datetime.fromisoformat(str(d.get("maj"))).timestamp()
    except ValueError:
        m = 0
    base = max(m, _ETAT.get("essai_le", 0))
    prochain = max(base + FRAICHEUR_S, time.time())
    return {"en_cours": False, "prochain": datetime.fromtimestamp(prochain, timezone.utc).isoformat(timespec="seconds"),
            "dernier": der or None, "demande": bool(_ETAT.get("tour_demande")),
            "passe": "proches" if _ETAT.get("proches") else "valo" if _ETAT.get("valo") else None}


def journal(n=80):
    """Les dernieres verifications SoldComps (la plus recente d'abord) et le bilan des 24 dernieres heures."""
    l = list(lire_vite().get("journal") or [])
    lim = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    b = {}
    for x in l:
        if str(x.get("le") or "") < lim:
            continue
        g = b.setdefault(x.get("genre") or "autre", {"verifiees": 0, "deals": 0, "pres": 0, "trop_cher": 0, "sans_ventes": 0})
        g["verifiees"] += 1
        g[x.get("res") if x.get("res") in g else "sans_ventes"] += 1
    return {"lignes": l[::-1][:n], "bilan": b}


def etat():
    """Pour l'admin : ou en est le chasseur (deals affiches, budget eBay et budget de verification du jour)."""
    import appels_ebay
    import vendues
    d = lire_vite()
    try:
        vmax = int(os.environ.get("LR_DEALS_VERIF_JOUR") or VERIF_JOUR)
    except ValueError:
        vmax = VERIF_JOUR
    v = d.get("verif") or {}
    jour = _jour_mtl()[0]
    g = diagnostic(d)
    import cartes_match
    rep = {"young_guns": 0, "recrues": 0, "hits": 0, "veterans": 0}
    for x in d.get("deals") or []:
        if not (valide(x) and encore_ouvert(x)):
            continue
        rep[sorte(x.get("titre"))] += 1
    return {"ok": True, "en_cours": _ETAT["en_cours"], "maj": d.get("maj"), "repartition": rep,
            "hits_24h": {"vus": g.get("hits_vus", 0), "verifies": g.get("hits_verifies", 0), "deals": g.get("hits_deals", 0),
                         "refus_budget": g.get("verif_budget", 0), "erreurs_ventes": g.get("erreurs_ventes", 0), "sans_ventes": g.get("sans_ventes", 0),
                         "plafond": g.get("verif_plafond", 0)},
            "soldcomps": _etat_soldcomps(), "journal": journal(), "tour": tour(d),
            "vendeurs_24h": {"annonces": g.get("vendeurs_annonces", 0), "gardes": g.get("suivi_ok", 0) + g.get("suivi_ok_recrue", 0), "erreurs": g.get("vendeurs_erreurs", 0),
                             "suivis": len(d.get("suivis") or []), "deals": sum(1 for x in d.get("deals") or [] if x.get("flux") == "vendeurs")},
            "vedettes_24h": {"verifiees": g.get("vedettes_verifiees", 0), "deals": g.get("vedettes_deals", 0),
                             "refus_recrues": g.get("verif_budget_recrues", 0)},
            "deals": sum(1 for x in d.get("deals") or [] if valide(x) and encore_ouvert(x)),
            "ebay": utilises_ebay(), "ebay_rythme": round(appels_ebay.rythme("browse")),
            "ebay_plafond": round(appels_ebay.limite("browse") * (1 - appels_ebay.RESERVE_GESTES)),
            "verif": vendues.utilises_aujourdhui("verif"), "verif_max": vmax,
            "prio": vendues.utilises_aujourdhui("prio"), "prio_max": prio_max(), "prio_24h": {"verifs": g.get("prio_verifs", 0), "refus": g.get("prio_budget", 0),
                                                                                         "debord": g.get("prio_debord", 0)},
            "prio_couverture": d.get("prio_couverture")}


_SORTES = {}


def sorte(titre):
    """young_guns | recrues | hits | veterans : pour la repartition (admin) et le melange de l'ecran Deals."""
    r = _SORTES.get(titre)           # 28 oct 2026 (vitesse) : 800 deals a chaque ecran
    if r is None:
        if len(_SORTES) > 20000:
            _SORTES.clear()
        r = _SORTES[titre] = _sorte(titre)
    return r


def _sorte(titre):
    import cartes_match
    t = cartes_match.norm(titre or "")
    c = cartes_match._decoder_memo(titre or "")
    s = c.get("serie")
    if c.get("auto") or c.get("patch") or (s is not None and int(s) <= 99):
        return "hits"
    if not recrue_recente(t, c.get("rc"), c.get("annee")):
        return "veterans"                # 29 oct : legendes (RC vintage) et joueurs de 2e a 4e annee
    if "young guns" in t:
        return "young_guns"
    return "recrues"


_RECRUES = {}


def est_recrue(titre):
    """29 oct 2026 (Mathieu : « encore que des rookies dans tes deals ») : une carte de recrue de l'annee (Young Guns,
    Future Watch, RC, rookie patch...), hit ou pas. Le reste (veterans, legendes, jeunes de 2e a 4e annee) passe devant."""
    r = _RECRUES.get(titre)
    if r is None:
        import cartes_match
        if len(_RECRUES) > 20000:
            _RECRUES.clear()
        c = cartes_match._decoder_memo(titre or "")
        r = _RECRUES[titre] = bool(recrue_recente(cartes_match.norm(titre or ""), c.get("rc"), c.get("annee")))
    return r


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


def _etat_soldcomps():
    import vendues
    try:
        e = vendues.derniere_erreur()
        return {"jour": vendues.utilises_aujourdhui(), "plafond": vendues.plafond_jour(), "fond": int(vendues.plafond_jour() * 0.7),
                "verif": vendues.utilises_aujourdhui("verif"), "prio": vendues.utilises_aujourdhui("prio"), "prio_max": prio_max(),
                "autres_max": int(vendues.plafond_jour() * vendues.PART_AUTRES_FOND),
                "erreur": e.get("erreur") if e and time.time() - e.get("le", 0) < 6 * 3600 else None, "sites": vendues.sites(),
                # 29 oct 2026 : budget du jour atteint -> quand ca repart (le compteur suit le jour du serveur, UTC)
                "epuise": vendues.utilises_aujourdhui() >= int(vendues.plafond_jour() * 0.7),
                "reprise": _minuit_mtl()}
    except Exception as x:
        return {"erreur": repr(x)}


def utilises_ebay():
    import appels_ebay
    return appels_ebay.utilises("browse")


# 30 oct 2026 (Mathieu : « encore » des encans « Auction » chez Savage) : entre deux tours (aux 10 min), les encans des
# 4 vendeurs prioritaires encore sans valeur, ceux qui finissent le plus tot d'abord, sont verifies sur leurs vraies
# ventes avec la reserve (usage « prio », meme plafond et meme rythme que dans le tour) ; jamais pendant un tour.
VALO_PAS_S = 600
VALO_PAR_PASSE = 40


def _env_int(k, d):
    """31 oct 2026 (Mathieu : « on fait une exception aujourd'hui et on roule le maximum ») : reglable dans Render."""
    try:
        return max(1, int(os.environ.get(k) or d))
    except ValueError:
        return d


def valoriser_suivis_si_besoin(attendre=False):
    if _ETAT.get("en_cours") or _ETAT.get("valo") or time.time() - _ETAT.get("valo_le", 0) < _env_int("LR_VALO_PAS_S", VALO_PAS_S):
        return False
    _ETAT["valo"], _ETAT["valo_le"] = True, time.time()

    def tache():
        try:
            valoriser_suivis()
        except Exception as e:
            print("Deals (valeurs des encans suivis) : " + repr(e), flush=True)
        finally:
            _ETAT["valo"] = False
    if attendre:
        tache()
    else:
        threading.Thread(target=tache, daemon=True).start()
    return True


def valoriser_suivis(rechercher=None, n_max=None):
    import cartes_match
    import vendues
    rechercher = rechercher or vendues.rechercher
    d = lire()
    maint = datetime.now(timezone.utc)
    n_max = n_max or _env_int("LR_VALO_PAR_PASSE", VALO_PAR_PASSE)
    a_faire = [x for x in d.get("suivis") or [] if not x.get("valeur") and _prio(x) and encore_ouvert(x)]
    a_faire.sort(key=lambda x: (rang_vendeur(x.get("vendeur")), str(x.get("fin") or "")))
    jour, heure = _jour_mtl()
    trouves, faites, n = {}, set(), 0
    for x in a_faire:
        if n >= n_max:
            break
        cib = cartes_match.cible_titre(x.get("titre") or "")
        q = (cartes_match.requete_ebay(cib) or "").strip()
        if not q or q in faites:
            continue
        faites.add(q)
        v = vendues.en_cache(q)
        if v is None:
            if not prio_ok(heure):
                break                                        # la reserve du jour est atteinte (ou ses 20 % du soir)
            r = rechercher(q, fond=True, usage="prio")
            n += 1
            if r.get("erreur"):
                continue
            v = r.get("ventes") or []
        for y in a_faire:                                    # une recherche sert a toutes les annonces de la meme carte
            if str(y.get("item_id")) in trouves:
                continue
            c2 = cartes_match.cible_titre(y.get("titre") or "")
            if (cartes_match.requete_ebay(c2) or "").strip() != q:
                continue
            va = valeur_annonce(y, v, [], cib=c2)
            if va:
                trouves[str(y.get("item_id"))] = va
    # 31 oct 2026 (Mathieu : « la barre ne bouge pas ») : les encans dont les ventes ont ete cherchees comptent comme analyses
    analyses = [str(y.get("item_id")) for y in a_faire
                if (cartes_match.requete_ebay(cartes_match.cible_titre(y.get("titre") or "")) or "").strip() in faites]
    if trouves or analyses:
        with _verrou:
            d = lire()
            for g in d.get("suivis") or []:
                va = trouves.get(str(g.get("item_id")))
                if va and not g.get("valeur"):
                    g.update(valeur=va[0], n=va[2], vendues=va[3], mise_max=round(va[0] * RATIO_DEAL - (g.get("port") or 0), 2))
            cov = d.get("prio_couverture")
            if cov and analyses:
                deja = set(cov.get("ids_valo") or [])
                nv = [i for i in analyses if i not in deja]
                cov["faites"] = min(cov.get("total") or 0, (cov.get("faites") or 0) + len(nv))
                cov["ids_valo"] = list(deja | set(nv))[-5000:]
                cov["le"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
            _ecrire(d)
    return {"verifies": n, "valeurs": len(trouves), "a_faire": len(a_faire)}


# 31 oct 2026 (Mathieu : « les encheres finissent ce soir ») : entre deux tours, aux 15 min, les encans de Savage, Remi,
# CF31 et Slab Sharks qui finissent dans 6 h sont relus sur eBay (mise du moment, nouveaux encans), juges et publies tout
# de suite ; les nouveaux sans valeur passent ensuite par la reserve « prio ». 1 a 3 recherches eBay par passe (sans cache).
PROCHES_PAS_S = 900
PROCHES_H = 6
PROCHES_PAGES = 3


def proches_si_besoin(attendre=False):
    if _ETAT.get("en_cours") or _ETAT.get("proches") or time.time() - _ETAT.get("proches_le", 0) < PROCHES_PAS_S:
        return False
    _ETAT["proches"], _ETAT["proches_le"] = True, time.time()

    def tache():
        try:
            if _prendre_tour():                      # jamais pendant un tour (meme dans un autre processus)
                try:
                    proches_prio(valoriser=False)
                finally:
                    _rendre_tour()
        except Exception as e:
            print("Deals (encans proches) : " + repr(e), flush=True)
        finally:
            _ETAT["proches"] = False
        # 31 oct 2026 (Mathieu : « le bouton redevient bleu avant que ca finisse ») : la valorisation (longue avec un gros
        # budget) se fait HORS du verrou du tour : « Relancer le chasseur » n'est plus refuse en silence pendant ce temps
        if _ETAT.pop("tour_demande", False):
            chasser_si_besoin(force=True)
        elif not _ETAT.get("en_cours") and not _ETAT.get("valo"):
            _ETAT["valo"], _ETAT["valo_le"] = True, time.time()
            try:
                valoriser_suivis()
            except Exception as e:
                print("Deals (valeurs des encans proches) : " + repr(e), flush=True)
            finally:
                _ETAT["valo"] = False
    if attendre:
        tache()
    else:
        threading.Thread(target=tache, daemon=True, name="deals-proches").start()
    return True


def proches_prio(rechercher=None, bassin=None, maint=None, valoriser=True):
    import cartes_match
    import ebay_compte
    rechercher = rechercher or ebay_compte.rechercher
    d = lire()
    maint = maint or datetime.now(timezone.utc)
    limite = (maint + timedelta(hours=PROCHES_H)).isoformat().replace("+00:00", "Z")
    bassin = bassin if bassin is not None else bassin_partage()
    deals = {x["item_id"]: x for x in d.get("deals") or []}
    st = {}
    verif = _verificateur(d, st, bassin)
    rv = {"q": None, "flux": "vendeurs", "sport": None, "joueur": None, "suivi": True}
    vus = 0
    for page in range(PROCHES_PAGES):
        try:
            l = rechercher("", categorie="261328", limite=200, fond=True, encheres=True, flux=True, offset=200 * page,
                           vendeurs=VENDEURS_PRIORITE, frais=True)
        except (RuntimeError, OSError, TypeError) as e:
            st["erreurs_ebay"] = st.get("erreurs_ebay", 0) + 1
            print("Deals (encans proches) : " + repr(e), flush=True)
            break
        st["requetes_proches"] = st.get("requetes_proches", 0) + 1
        dans = [a for a in l if str(a.get("fin") or "9") <= limite]
        for a in dans:
            if not cartes_match.est_carte(a.get("titre") or ""):
                continue
            vus += 1
            _juger(a, rv, [], [], maint, deals, st, bassin=bassin, verif=verif)
            k_s = "suivi_" + (_noter_suivi(st, a, bassin, maint) or "ok")
            st[k_s] = st.get(k_s, 0) + 1
        if len(l) < 150 or len(dans) < len(l):
            break                                    # plus d'encans, ou on depasse 6 h
    st["proches_vus"] = vus
    if not st.get("requetes_proches"):
        return {"ok": False, "vus": 0, "erreur": "eBay injoignable"}        # rien lu : on n'ecrit rien (pas d'ecrasement)
    _publier(d, deals, maint, st, force=True)
    with _verrou:                                    # le budget de verification utilise (comme a la fin d'un tour)
        d2 = lire()
        if "verif" in d:
            d2["verif"] = d["verif"]
        d2["proches"] = {"le": maint.isoformat(timespec="seconds"), "vus": vus, "requetes": st.get("requetes_proches", 0)}
        if st.get("_journal"):
            d2["journal"] = ((d2.get("journal") or []) + st["_journal"])[-JOURNAL_MAX:]
        _diag(d2, **{k: v for k, v in st.items() if not k.startswith("_") and isinstance(v, (int, float))})
        _ecrire(d2)
    try:
        if valoriser:
            valoriser_suivis()                       # les nouveaux encans sans valeur : la reserve « prio »
    except Exception as e:
        print("Deals (valeurs des encans proches) : " + repr(e), flush=True)
    return {"ok": True, "vus": vus, "stats": {k: v for k, v in st.items() if not k.startswith("_")}}


def chasser_si_besoin(force=False):
    """En arriere-plan, au plus une fois par heure, jamais deux a la fois."""
    d = lire_vite()                  # 28 oct 2026 (vitesse) : appele a chaque ecran Deals / Accueil : lecture en cache
    try:
        age = time.time() - datetime.fromisoformat(str(d.get("maj"))).timestamp()
    except ValueError:
        age = 1e9
    age = min(age, time.time() - _ETAT.get("essai_le", 0))      # 27 oct 2026 (revue) : un tour rate compte aussi
    # une seule fois par demarrage (mise a jour, redemarrage) : peu de deals -> un tour apres 10 min, pas apres 1 h
    # (jamais plus : le quota d'appels eBay du jour)
    peu = not _ETAT.get("rapide") and sum(1 for x in d.get("deals") or [] if valide(x)) < 10
    if age < (600 if peu else FRAICHEUR_S) and not force:
        if not proches_si_besoin():               # 31 oct 2026 : aux 15 min, les encans qui finissent dans 6 h
            valoriser_suivis_si_besoin()         # 30 oct 2026 : entre deux tours, les encans des gros vendeurs sans valeur
        return False
    if _ETAT.get("proches") and not force:
        return False                             # la passe des encans proches finit d'abord (quelques secondes)
    if peu:
        _ETAT["rapide"] = True
    with _verrou:
        if _ETAT["en_cours"]:
            return False
        if not _prendre_tour():
            return False                             # un autre processus chasse deja
        _ETAT["en_cours"] = True
        _ETAT["essai_le"] = time.time()

    def tache():
        debut = time.time()
        _ETAT.update(debut=debut, etape="revue", detail=None)
        try:
            b = bassin_partage(neuf=True)                # une fois par tour : toutes les ventes connues (partage ensuite)
            try:
                reverifier()                             # d'abord : les deals deja affiches, revus sur eBay
            except Exception as e:
                print("Deals (revue) : " + repr(e), flush=True)
            # 28 oct 2026 : les flux d'abord (hits, vendeurs suivis, encans larges) : ce sont eux qui trouvent le plus ;
            # si le rythme du budget eBay coupe le tour, il coupe les recherches par joueur
            for f in (flux, encans, chasser):
                _progres(f.__name__)
                try:
                    f(bassin=b)
                except Exception as e:
                    print("Deals : " + repr(e), flush=True)
            with _verrou:
                d = lire()
                d["bassin"] = b.n
                d["dernier_tour"] = {"debut": datetime.fromtimestamp(debut, timezone.utc).isoformat(timespec="seconds"),
                                     "fin": datetime.now(timezone.utc).isoformat(timespec="seconds"), "duree_s": round(time.time() - debut)}
                _ecrire(d)
        finally:
            _ETAT.update(en_cours=False, etape=None, detail=None)
            _rendre_tour()
    threading.Thread(target=tache, daemon=True, name="deals").start()
    return True
