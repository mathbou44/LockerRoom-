"""
SLABCOACH - la chance de gagner un encan a sa mise max (5 nov 2026, Mathieu : « je perds mon temps a miser sur des cartes
qui montent en fou a la derniere seconde ; il faut l'integrer subtilement, pas trop d'info »).

Chaque encan suivi par le chasseur (sa valeur, sa mise max, le vendeur, la fin) est garde. Une fois fini, son prix final
est retrouve dans nos ventes reelles (base_ventes : l'adresse /itm/<numero> de la vente). On mesure alors, par genre
d'encan, combien de fois il a fini SOUS la mise max :
  genre = groupe du vendeur (gros vendeurs suivis / maisons a volume / petits vendeurs / autres) x recrue ou non x gamme
  de valeur (moins de 50 $, 50 a 200 $, plus de 200 $).
Lissage de Laplace ((gagnes + 1) / (n + 2)) ; un genre avec moins de 15 encans prend son groupe de vendeur, puis tous.
A l'ecran : rien de plus sur les tuiles. Un encan dont le genre finit presque toujours au-dessus de la mise max (moins de
12 %, 15 encans et plus) n'est plus montre ; la fiche dit en une ligne la chance de ce genre d'encan.
"""
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

N_MIN = 15
CACHER_SOUS = 0.12
GARDER_J = 45
MAX_ARCHIVE = 30000
_verrou = threading.Lock()
_MEM = {"mtime": None, "v": None}


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "encans_archive.json")


def _lire():
    ch = _chemin()
    try:
        mt = os.path.getmtime(ch)
    except OSError:
        return {"encans": {}, "stats": {}}
    if _MEM["v"] is not None and _MEM["mtime"] == mt:
        return _MEM["v"]
    try:
        with open(ch, encoding="utf-8") as f:
            v = json.load(f)
    except (OSError, ValueError):
        v = {"encans": {}, "stats": {}}
    _MEM.update(mtime=mt, v=v)
    return v


def _ecrire(v):
    ch = _chemin()
    tmp = ch + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False)
    os.replace(tmp, ch)
    _MEM.update(mtime=None, v=None)


def groupe(x):
    """Le groupe du vendeur : les gros vendeurs suivis, les maisons a volume, les petits vendeurs, les autres."""
    import deals
    v = str(x.get("vendeur") or "").lower()
    if v in [s.lower() for s in deals.VENDEURS_PRIORITE]:
        return "suivis"
    sc = x.get("vendeur_score") or 0
    if v in [s.lower() for s in deals.VENDEURS_DERNIER] or sc >= deals.GROS_VENDEUR:
        return "volume"
    if sc and sc < deals.PETIT_VENDEUR:
        return "petits"
    return "autres"


def _gamme(v):
    v = v or 0
    return "moins50" if v < 50 else "50a200" if v <= 200 else "plus200"


def genre(x):
    return f"{groupe(x)}|{'rc' if x.get('recrue') else 'v'}|{_gamme(x.get('valeur'))}"


def archiver(encans_):
    """Les encans suivis (avec valeur et mise max) gardes pour plus tard (leur prix final)."""
    l = [x for x in encans_ or [] if x.get("encan") and x.get("valeur") and x.get("mise_max") is not None and x.get("item_id") and x.get("fin")]
    if not l:
        return 0
    with _verrou:
        a = _lire()
        e = dict(a.get("encans") or {})
        for x in l:
            k = str(x["item_id"])
            vieux = e.get(k) or {}
            e[k] = {"fin": str(x["fin"]), "mise_max": float(x["mise_max"]), "valeur": float(x["valeur"]), "port": x.get("port"),
                    "vendeur": x.get("vendeur"), "vendeur_score": x.get("vendeur_score"), "recrue": bool(x.get("recrue")),
                    **{c: vieux[c] for c in ("final", "cherche") if c in vieux}}
        if len(e) > MAX_ARCHIVE:
            for k in sorted(e, key=lambda k: e[k]["fin"])[:len(e) - MAX_ARCHIVE]:
                e.pop(k, None)
        a = {**a, "encans": e}
        _ecrire(a)
    return len(l)


_RE_ITM = re.compile(r"/itm/(?:[^/?#]*/)?(\d{9,15})")


def resoudre(maint=None):
    """Les encans finis depuis 2 h et plus : leur prix final dans nos ventes reelles. Puis les statistiques par genre."""
    import comptes
    maint = maint or datetime.now(timezone.utc)
    with _verrou:
        a = _lire()
        e = dict(a.get("encans") or {})
    lim = (maint - timedelta(hours=2)).isoformat()
    vieux = (maint - timedelta(days=GARDER_J)).isoformat()
    a_trouver = {k: x for k, x in e.items() if "final" not in x and vieux <= x["fin"].replace("Z", "+00:00") <= lim}
    finals = {}
    if a_trouver:
        d0 = min(x["fin"] for x in a_trouver.values())[:10]
        try:
            c = sqlite3.connect(os.path.join(comptes.DONNEES, "base_ventes.sqlite"), timeout=30)
            try:
                for url, cle, prix in c.execute("SELECT url, cle, prix FROM ventes WHERE le >= ?", (d0,)):
                    m = _RE_ITM.search(str(url or "")) or _RE_ITM.search(str(cle or ""))
                    if m and m.group(1) in a_trouver:
                        finals[m.group(1)] = float(prix)
            finally:
                c.close()
        except sqlite3.Error:
            pass
    stats = {}
    with _verrou:
        a = _lire()
        e = dict(a.get("encans") or {})
        for k, p in finals.items():
            if k in e:
                e[k] = {**e[k], "final": p}
        for k in [k for k, x in e.items() if x["fin"].replace("Z", "+00:00") < vieux]:
            e.pop(k, None)                               # trop vieux : retire (trouve ou pas)
        for x in e.values():
            if "final" not in x:
                continue
            gagne = x["final"] <= x["mise_max"] + 0.5        # la vente finale (sans port) contre la mise max
            g = genre(x)
            for cle in (g, g.split("|")[0], "tous"):
                s = stats.setdefault(cle, [0, 0])
                s[0] += 1 if gagne else 0
                s[1] += 1
        a = {**a, "encans": e, "stats": stats, "le": maint.isoformat(timespec="seconds")}
        _ecrire(a)
    return {"trouves": len(finals), "suivis": len(e), "genres": len(stats)}


def chance(x):
    """(p, n, niveau) : la chance qu'un encan de ce genre finisse sous sa mise max, ou None (pas assez d'encans connus).
    niveau : « genre », « vendeur » (son groupe de vendeur) ou « tous »."""
    st = (_lire().get("stats") or {})
    g = genre(x)
    for cle, niv in ((g, "genre"), (g.split("|")[0], "vendeur"), ("tous", "tous")):
        s = st.get(cle)
        if s and s[1] >= N_MIN:
            return round((s[0] + 1) / (s[1] + 2), 3), s[1], niv
    return None


def a_cacher(x, c=None):
    """Cache seulement sur le genre de l'encan ou son groupe de vendeur (jamais sur la moyenne de tous les encans)."""
    c = c or chance(x)
    return bool(c and c[2] != "tous" and c[0] < CACHER_SOUS)
