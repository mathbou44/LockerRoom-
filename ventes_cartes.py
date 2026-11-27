"""SLABCOACH - la CARTE EXACTE de chaque vente, rangee une fois et gardee sur le disque (27 nov 2026).

Mathieu (12 h 38) : « double puis triple verifier les valeurs des graphiques de prise de valeur, pour etre sur que les joueurs
perdent et prennent vraiment de la valeur ; il faut que notre indice et notre base de mesure soient equitables pour tout le
monde : evaluer des pommes avec des pommes et des poires avec des poires » ; (13 h 50) « Go » au correctif.

La verification (archives du 26 nov, 1 555 245 ventes) : le marche d'un joueur, mesure par SORTE de carte (famille + note +
tranche de tirage + saison), melangeait des cartes differentes : la « Young Guns PSA 10 de 2010 » de Bobrovsky recevait une
« 2024 Young Guns Renewed PSA Auto 10 » a 62 $ contre une annee de vraies YG 2010 PSA 10 a 431 $ (-59 % affiche ; -28 % carte
par carte). Desormais chaque vente est rangee dans sa CARTE EXACTE et sa note (a_grader.classer : joueur, sorte, saison, /N,
numero ; raw, PSA 9 ou PSA 10), et une carte n'est comparee qu'a elle-meme.

Ranger 1,5 million de titres prend une dizaine de minutes : chaque titre n'est range qu'UNE fois (sqlite, sur le disque) ; les
jours suivants, seuls les nouveaux titres. Un titre qu'on ne sait pas ranger est garde aussi (sans carte), pour ne pas le relire.
"""
import hashlib
import os
import sqlite3
import threading

REGLE = 1                       # change quand la facon de ranger change : tout est relu une fois
_verrou = threading.Lock()


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "ventes_cartes.sqlite")


def _cx():
    c = sqlite3.connect(_chemin(), timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS t (h TEXT PRIMARY KEY, cle TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    r = c.execute("SELECT v FROM meta WHERE k='regle'").fetchone()
    if not r or r[0] != str(REGLE):
        c.execute("DELETE FROM t")
        c.execute("INSERT OR REPLACE INTO meta VALUES ('regle', ?)", (str(REGLE),))
        c.commit()
    return c


def _h(titre, joueur):
    return hashlib.md5((str(titre or "") + "|" + str(joueur or "").lower()).encode("utf-8", "replace")).hexdigest()[:20]


def ranger(titre, joueur=None):
    """Un titre -> (joueur, recherche, saison, /N, numero, note) ou None ; sans le disque (le calcul seul)."""
    import a_grader
    try:
        r = a_grader.classer(titre, joueur)
    except Exception:
        return None
    if not r:
        return None                     # une autre note (PSA 8, BGS...), un lot, une carte qu'on ne reconnait pas : rien
    return tuple(r[0]) + (r[1],)


def cartes(paires, respirer=None):
    """[(titre, joueur)] -> {(titre, joueur): carte ou None}. Les titres deja ranges viennent du disque ; les autres sont
    ranges puis gardes."""
    paires = list(dict.fromkeys((str(t or ""), str(j or "")) for t, j in paires))
    out, manque = {}, []
    with _verrou:
        c = _cx()
        try:
            for i in range(0, len(paires), 500):
                lot = paires[i:i + 500]
                hs = {_h(t, j): (t, j) for t, j in lot}
                for h, cle in c.execute("SELECT h, cle FROM t WHERE h IN (%s)" % ",".join("?" * len(hs)), list(hs)):
                    out[hs[h]] = tuple(_lire(cle)) if cle else None
                manque += [p for p in lot if p not in out]
        finally:
            c.close()
    neufs = []
    for k, (t, j) in enumerate(manque):
        if respirer and k % 200 == 199:
            respirer(k)
        r = ranger(t, j or None)
        out[(t, j)] = r
        neufs.append((_h(t, j), _ecrire(r) if r else None))
        if len(neufs) >= 5000:
            _garder(neufs)
            neufs = []
    if neufs:
        _garder(neufs)
    return out


def _ecrire(r):
    return "\t".join("" if v is None else str(v) for v in r)


def _lire(s):
    j, q, an, se, num, note = (s.split("\t") + [""] * 6)[:6]
    return (j, q, int(an) if an else None, int(se) if se else None, num or None, note)


def _garder(rows):
    with _verrou:
        c = _cx()
        try:
            c.executemany("INSERT OR REPLACE INTO t VALUES (?, ?)", rows)
            c.commit()
        finally:
            c.close()


def compte():
    try:
        c = _cx()
        try:
            return c.execute("SELECT COUNT(*), SUM(cle IS NOT NULL) FROM t").fetchone()
        finally:
            c.close()
    except sqlite3.Error:
        return (0, 0)
