"""
SLABCOACH - la liquidite d'une carte, pour le Radar Pro (20 nov 2026).

Mathieu : « si la personne achete une carte, ok, pas trop pire, mais il est pogne avec. Il faut etre sur que ces cartes
soient assez liquides et qu'ils les vendent ; des cartes assez desirees ». Puis : « on peut utiliser le prix en coulisse,
mais l'utilisateur voit juste la lettre ».

Pour chaque annonce, deux signaux tires de nos archives de ventes (base_ventes, la meme carte : meme titre normalise, meme
compagnie, meme note) :
  liq : le nombre de ventes de la carte dans les 60 derniers jours (elle se vend : on n'est pas pogne avec) ;
  med : sa mediane ponderee par la recence (demi-vie 15 j, 90 jours, sans les prix aberrants), pour ne garder que les annonces
        pas plus de 10 % au-dessus de ce que la carte se vend.
Rien de ceci n'est montre : l'utilisateur voit la lettre SlabIQ et l'annonce, jamais une valeur, une mediane ni un compte.

Teste (outils/radar_iq.py, regle choisie sur septembre, jamais sur la periode de test) : un achat « reussi » = la meme carte
se revend ensuite ET a au moins 90 % du prix paye.
  achats du 19 au 29 oct. : hasard 11,7 % ; Radar Pro d'avant (A et A+) 29,8 % ; cette regle 71,0 % (IC 95 % 67,6-74,4) ;
  achats du 1er au 8 nov. : hasard 11,3 % ; cette regle 60,3 % (57,3-63,2).
Sans le prix (liquidite seulement) : 62,4 % et 51,8 %. LR_RADAR_PRIX=0 dans Render enleve le prix de la regle.

L'index (table liquidite de base_ventes.sqlite) se remplit en fond, par paquets, depuis les ventes deja archivees : aucun appel
de plus a SoldComps ni a eBay.
"""
import datetime as dt
import hashlib
import os
import re
import statistics
import threading
import time

NOTE_MIN = 82                       # A- et plus
LIQ_MIN = 5
LIQ_JOURS = 60
RABAIS_MAX = 0.10                   # l'annonce : au plus 10 % au-dessus de la mediane recente
MED_JOURS = 90
DEMI_VIE = 15.0
RAFRAICHIR_S = 1800
PAQUET = 4000
G = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg|csg|gma|isa|ags|mnt)\s*-?\s*(?:gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*)?"
               r"(\d+(?:\.\d)?)\b", re.I)
_V = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False, "pret": set(), "tables": set()}


def _ch():
    import comptes
    return os.path.join(comptes.DONNEES, "base_ventes.sqlite")


def prix_permis():
    return (os.environ.get("LR_RADAR_PRIX") or "1").strip() not in ("0", "non", "false")


def cle(titre):
    """La carte : le titre normalise (validation_iq.cle_carte) + la compagnie + la note (une PSA 10 et une SGC 10 different)."""
    import validation_iq
    g = G.search(titre or "")
    return validation_iq.cle_carte(titre) + ("|" + g.group(1).lower().replace("beckett", "bgs") + "|" + str(float(g.group(2))) if g else "||0.0")


def mediane_recente(hist, jour, dv=DEMI_VIE, jours=MED_JOURS, avant=False):
    """[(le 'AAAA-MM-JJ', prix)] -> la mediane ponderee par la recence a `jour`, sur `jours` jours, sans les prix hors de
    [m/3, 3m] ; None sous 2 ventes. avant=True : seulement les ventes d'AVANT le jour (le banc : l'achat est lui-meme une vente)."""
    d0 = dt.date.fromisoformat(jour)
    h = []
    for le, p in hist:
        a = (d0 - dt.date.fromisoformat(le)).days
        if (a > 0 if avant else a >= 0) and a <= jours:
            h.append((float(p), a))
    if len(h) < 2:
        return None
    m = statistics.median(p for p, _ in h)
    pw = sorted((p, 0.5 ** (a / dv)) for p, a in h if m / 3 <= p <= m * 3)
    tot = sum(w for _, w in pw)
    acc = 0.0
    for p, w in pw:
        acc += w
        if acc >= tot / 2 - 1e-12:
            return p
    return pw[-1][0]


def _cx():
    import base_ventes
    c = base_ventes._cx()
    if _ch() in _ETAT["tables"]:
        return c
    c.execute("CREATE TABLE IF NOT EXISTS liquidite (cle TEXT, le TEXT, prix REAL, h TEXT, PRIMARY KEY (cle, le, prix, h)) WITHOUT ROWID")
    c.execute("CREATE INDEX IF NOT EXISTS liquidite_le ON liquidite (le)")
    c.execute("CREATE TABLE IF NOT EXISTS liquidite_etat (k TEXT PRIMARY KEY, v TEXT)")
    _ETAT["tables"].add(_ch())
    if c.execute("SELECT 1 FROM liquidite_etat WHERE k='rowid'").fetchone():
        _ETAT["pret"].add(_ch())            # un index deja bati (avant un redemarrage) sert tout de suite
    return c


def rafraichir(pause=0.05):
    """Les ventes archivees depuis le dernier passage -> l'index (par paquets, une petite pause entre chacun) ; les ventes de
    plus de 90 jours en sortent."""
    with _V:
        if _ETAT["en_cours"]:
            return 0
        _ETAT["en_cours"] = True
    n = 0
    try:
        d0 = (dt.date.today() - dt.timedelta(days=MED_JOURS + 1)).isoformat()
        c = _cx()
        try:
            r = c.execute("SELECT v FROM liquidite_etat WHERE k='rowid'").fetchone()
            dernier = int(r[0]) if r else 0
            while True:
                rows = c.execute("SELECT rowid, titre, prix, le FROM ventes WHERE rowid > ? ORDER BY rowid LIMIT ?", (dernier, PAQUET)).fetchall()
                if not rows:
                    break
                lignes = []
                for _rid, t, p, le in rows:
                    le = str(le or "")[:10]
                    if t and p and float(p) >= 3 and le >= d0:
                        lignes.append((cle(t), le, round(float(p), 2), hashlib.md5(t.encode("utf-8", "ignore")).hexdigest()[:12]))
                dernier = rows[-1][0]
                c.executemany("INSERT OR IGNORE INTO liquidite VALUES (?,?,?,?)", lignes)
                c.execute("INSERT OR REPLACE INTO liquidite_etat VALUES ('rowid', ?)", (str(dernier),))
                c.commit()
                n += len(lignes)
                if pause:
                    time.sleep(pause)
            c.execute("DELETE FROM liquidite WHERE le < ?", (d0,))
            c.commit()
        finally:
            c.close()
        _ETAT["pret"].add(_ch())
    except Exception as e:
        print("Liquidite (index) : " + repr(e)[:160], flush=True)
    finally:
        _ETAT["le"] = time.time()
        _ETAT["en_cours"] = False
    return n


def _rafraichir_si_besoin():
    if not _ETAT["en_cours"] and time.time() - _ETAT["le"] > RAFRAICHIR_S:
        threading.Thread(target=rafraichir, daemon=True, name="liquidite").start()


def signaux(titres):
    """{titre: (liq, med)} pour des annonces ; None si l'index n'est pas encore pret (l'annonce sera jugee au prochain
    balayage plutot que rejetee)."""
    _rafraichir_si_besoin()
    c = _cx()
    if _ch() not in _ETAT["pret"]:
        c.close()
        return None
    auj = dt.date.today().isoformat()
    l60 = (dt.date.today() - dt.timedelta(days=LIQ_JOURS)).isoformat()
    out = {}
    try:
        for t in titres:
            hist = c.execute("SELECT le, prix FROM liquidite WHERE cle = ?", (cle(t),)).fetchall()
            out[t] = (sum(1 for le, _ in hist if le >= l60), mediane_recente(hist, auj))
    finally:
        c.close()
    return out


def passe(liq, med, total):
    """La regle du Radar Pro sur les signaux d'une annonce (la note SlabIQ se juge a part)."""
    if (liq or 0) < LIQ_MIN:
        return False
    if not prix_permis():
        return True
    return bool(med) and float(total or 0) <= (1 + RABAIS_MAX) * float(med)
