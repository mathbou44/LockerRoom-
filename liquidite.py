"""
SLABCOACH - la liquidite d'une carte, pour le Radar Pro (20 nov 2026).

Mathieu : « si la personne achete une carte, ok, pas trop pire, mais il est pogne avec. Il faut etre sur que ces cartes
soient assez liquides et qu'ils les vendent ; des cartes assez desirees ». Puis : « on peut utiliser le prix en coulisse,
mais l'utilisateur voit juste la lettre ».

Pour chaque annonce, deux signaux tires de nos archives de ventes (base_ventes, la meme carte : meme titre normalise, meme
compagnie, meme note) :
  liq : le nombre de ventes de la carte dans les 60 derniers jours (elle se vend : on n'est pas pogne avec) ;
  med : sa mediane ponderee par la recence (demi-vie 15 j, 90 jours, sans les prix aberrants), pour ne garder que les annonces
        qui ne depassent pas ce que la carte se vend (23 nov 2026 ; avant : jusqu'a 10 % au-dessus).
Rien de ceci n'est montre : l'utilisateur voit la lettre SlabIQ et l'annonce, jamais une valeur, une mediane ni un compte.

Teste (outils/radar_iq.py, regle choisie sur septembre, jamais sur la periode de test) : un achat « reussi » = la meme carte
se revend ensuite ET a au moins 90 % du prix paye.
  achats du 19 au 29 oct. : hasard 11,7 % ; Radar Pro d'avant (A et A+) 29,8 % ; cette regle 71,0 % (IC 95 % 67,6-74,4) ;
  achats du 1er au 8 nov. : hasard 11,3 % ; cette regle 60,3 % (57,3-63,2).
Sans le prix (liquidite seulement) : 62,4 % et 51,8 %. LR_RADAR_PRIX=0 dans Render enleve le prix de la regle.

23 nov 2026 (Mathieu : « analyser toutes les avenues pour augmenter le plus le % » ; il choisit « B : 78 % ») : 8 ventes en 60
jours (avant : 5) et jamais au-dessus de ce que la carte se vend (avant : jusqu'a 10 % au-dessus). Pourquoi : les achats a 5-7
ventes reussissaient 3 fois sur 10, ceux a 8 ventes et plus 7 fois sur 10. Aux 5 dates du bulletin, sur les memes ventes :
  avant (5 ventes, +10 %)      : 76, 74, 59, 64, 63 %   (225 cartes differentes a la derniere date)
  8 ventes, +10 %              : 86, 81, 72, 71, 67 %   (130 cartes)
  8 ventes, <= mediane (ICI)   : 90, 88, 80, 82, 78 %   (104 cartes) ; se revend : 90 % (avant 81 %)
  12 ventes, <= mediane        : 97, 92, 84, 84, 81 %   (60 cartes, 16 joueurs : trop mince)
A savoir : le gain de « 8 ventes » vient de la liquidite (la carte se revend plus) ; le gain de « <= mediane » vient du prix paye
(le marche de la carte ne tient pas mieux : l'acheteur ne paie juste jamais trop cher). Moins d'annonces passent : si le Radar
Pro est trop vide, revenir a RABAIS_MAX = 0.10 (« 8 ventes » seul) et refaire les tests du site. Recherche : outils/recherche/avenues/.

23 nov 2026 au soir (Mathieu, devant « garde sa valeur » qui passe de 86 a 80 % sur un export plus gros : « continue a travailler
pour rendre SlabIQ infaillible ») : une carte NEUVE perd sa valeur. Sur 8 275 achats du Radar Pro rejoues d'oct. 2025 a oct. 2026
(27 fenetres : 21 jours d'achats, 30 jours de reventes), par anciennete de la carte (jours depuis sa 1re vente chez nous) :
  moins de 21 jours 30-35 % ; 21 a 45 jours 27-35 % ; 45 a 60 jours 54-79 % ; 60 jours et plus 74-86 %.
Ce sont les sorties (Series 2 en mars, Extended en juin, Series 1 en novembre) : le prix d'une recrue part haut et descend pendant
deux mois. La regle ajoutee : la carte se vendait DEJA il y a deux mois (au moins une vente entre 60 et 90 jours avant). Aucun
nouveau reglage : ce sont les deux durees deja en place (LIQ_JOURS, MED_JOURS). Choisie sur les achats d'oct. 2025 a mars 2026,
jugee sur ceux d'avril a oct. 2026 :
  choix : 70,0 % -> 85,6 % (par carte differente 72 -> 80 %) ; pire fenetre 43 % -> 72 %
  juge  : 72,2 % -> 84,8 % (par carte differente 69 -> 79 %) ; pire fenetre 53 % -> 67 %
Essaye en plus et REJETE (bon sur la periode de choix, rien sur l'autre) : A et plus seulement (90 % puis 84 %), 50 $ et plus.
Pas retenu, trop peu de cartes : 12 ventes, prix a 7 % sous la mediane (+2 a 3 points chacun). Environ une annonce sur trois
ne passe plus (derniere fenetre : 83 cartes differentes au lieu de 125). LR_RADAR_ANCIENNETE=0 dans Render enleve cette regle.
Ce que ca ne regle PAS : meme avec elle, une fenetre sur l'annee tombe a 67 % (mai 2026). Recherche : outils/recherche/garde/.

24 nov 2026 (Mathieu, une Rantanen UD Canvas Young Guns PSA 10 partie a 63 $ en encan : « j'espere qu'on l'avait captee » ; puis
« on doit etre parfait avant Apple ») : la liquidite comptait MAL les ventes, dans les deux sens.
  1. La meme vente etait comptee 2, 3 ou 4 fois : nos archives la gardent une fois par recherche qui l'a trouvee, au prix
     converti a quelques cents pres (36 % des lignes de 30 $ et plus des 90 derniers jours). Maintenant : une vente = le numero
     de l'annonce eBay vendue (id_vente), une seule ligne dans l'index.
  2. La meme carte avait plusieurs cles selon la facon d'ecrire le titre (la Rantanen : 21). Maintenant : cle_base.
« 8 ventes en 60 jours » voulait donc souvent dire 3 ou 4 vraies ventes, et de vraies cartes liquides etaient refusees. La regle
re-choisie sur de vraies ventes (outils/recherche/garde/banc2.py et regles2.py ; choix : oct. 2025 a mars 2026 ; juge : avril
a oct. 2026 ; prix <= mediane, pas une carte neuve) :
  2 ventes : 84,1 % / 86,6 %   174 cartes differentes a la derniere fenetre
  3 ventes : 85,3 % / 88,1 %   148
  4 ventes : 86,9 % / 89,3 %   134
  5 ventes : 87,5 % / 90,3 %   116   <- ICI (LIQ_MIN = 5) ; avant (doublons, ancienne cle, « 8 ventes ») : 85,6 % / 84,8 %, 83 cartes
  6 ventes : 88,3 % / 91,3 %   103
  8 ventes : 88,9 % / 92,2 %    86
Doublons EXACTS (l'export du 24 nov avec la colonne « id » : 1 778 722 lignes pour 1 264 949 annonces vendues ; meme_vente).
« Pas une carte neuve » compte toujours autant : 4 ventes avec les cartes neuves = 69,6 % / 77,8 %. Test officiel refait sur ces
vraies ventes (achats du 9 sept au 15 oct 2026) : 87,1 % gardent leur valeur (638 achats ; avant : 84,6 % sur 454).
Nouvel index : liquidite2.sqlite (l'ancien reste la).

L'index se remplit en fond, par paquets, depuis les ventes deja archivees (base_ventes.sqlite, en lecture seulement) : aucun
appel de plus a SoldComps ni a eBay. 20 nov 2026 (Render : « database is locked ») : l'index a son propre fichier
(liquidite.sqlite, en WAL) : il n'attend jamais apres les longues lectures des archives, et les archives n'attendent pas apres lui.
"""
import datetime as dt
import hashlib
import os
import re
import sqlite3
import statistics
import threading
import time

NOTE_MIN = 82                       # A- et plus
LIQ_MIN = 5                         # 24 nov 2026 : 5 VRAIES ventes en 60 jours (23 nov : 8, comptees avec les doublons)
LIQ_JOURS = 60
RABAIS_MAX = 0.0                    # 23 nov 2026 : l'annonce ne depasse pas la mediane recente (avant : +10 %)
VIEUX_MIN = 1                       # 23 nov 2026 au soir : au moins une vente entre LIQ_JOURS et MED_JOURS jours avant (pas une carte neuve)
MED_JOURS = 90
DEMI_VIE = 15.0
RAFRAICHIR_S = 1800
PAQUET = 4000
G = re.compile(r"\b(psa|bgs|sgc|cgc|tag|ksa|hga|beckett|bccg|csg|gma|isa|ags|mnt)\s*-?\s*(?:gem\s*(?:mint|mt)?\s*|mint\s*|pristine\s*)?"
               r"(\d+(?:\.\d)?)\b", re.I)
_V = threading.Lock()
_ETAT = {"le": 0.0, "en_cours": False, "pret": set(), "tables": set()}


VERSION = 2                         # 24 nov 2026 : la cle sans le bruit d'ecriture ; une vente comptee une seule fois


def _ch():
    import comptes
    return os.path.join(comptes.DONNEES, "liquidite2.sqlite")     # 24 nov 2026 : un nouvel index (liquidite.sqlite : l'ancien)


def prix_permis():
    return (os.environ.get("LR_RADAR_PRIX") or "1").strip() not in ("0", "non", "false")


def anciennete_permise():
    return (os.environ.get("LR_RADAR_ANCIENNETE") or "1").strip() not in ("0", "non", "false")


_RE_SAISON = re.compile(r"^((?:19|20)\d\d)(?:[-/](?:\d\d|\d{4}))?$")
_RE_PONCT = re.compile(r"^[\W_]+$")
_SERIES = frozenset(("series", "serie", "one", "two", "1", "2", "s1", "s2"))
_RE_ITM = re.compile(r"/itm/(?:[^/?]+/)?(\d{9,15})")


def cle_base(titre):
    """La carte, sans la compagnie ni la note : les mots du titre (validation_iq.cle_carte) SANS le bruit d'ecriture.
    24 nov 2026 (Mathieu, une Rantanen Canvas Young Guns PSA 10 partie a 63 $ : « j'espere qu'on l'avait captee ») : la meme
    carte avait 21 cles (« 2015 » ou « 2015-16 », « #C98 » ou « C98 », « Series 1 », « UD » ou « Upper Deck », un tiret seul).
    On n'enleve QUE ce qui ne peut pas confondre deux cartes : la saison garde son annee de debut, le numero perd son diese,
    « Series 1 » part quand le numero est la, « Upper Deck » / « UD » partent, la ponctuation seule part. Essaye et REJETE : une
    cle faite par le decodeur (joueur, annee, numero, paralleles) : deux fois plus de cartes liquides, mais elle confondait une
    « 1st Round Rookies Outburst » a 50 $ avec la Young Guns Outburst a 700 $ (outils/recherche/garde/cle_carte.py)."""
    import validation_iq
    toks = validation_iq.cle_carte(titre).split()
    a_num = any(t.startswith("#") and len(t) > 1 for t in toks)
    out = set()
    for t in toks:
        if _RE_PONCT.match(t):
            continue
        m = _RE_SAISON.match(t)
        if m:
            out.add(m.group(1))
        elif t.startswith("#"):
            t = t.lstrip("#").replace("-", "")
            if t:
                out.add(t)
        elif t == "ud" or (a_num and t in _SERIES):
            continue
        else:
            out.add(t)
    if "upper" in out and "deck" in out:
        out -= {"upper", "deck"}
    return " ".join(sorted(out))


def cle(titre):
    """La carte : cle_base + la compagnie + la note (une PSA 10 et une SGC 10 different)."""
    g = G.search(titre or "")
    return cle_base(titre) + ("|" + g.group(1).lower().replace("beckett", "bgs") + "|" + str(float(g.group(2))) if g else "||0.0")


def meme_vente(deja, le, prix):
    """La ligne (le, prix) est-elle une vente DEJA comptee de la meme annonce ? deja : [(le 'AAAA-MM-JJ', prix)] de cette annonce.
    Oui si a un jour pres (deux sources, deux fuseaux) et a 5 % pres (le taux de change du jour ou on l'a lue). Une annonce a
    plusieurs exemplaires vendus a des jours differents, ou a des prix differents le meme jour (« choisis ta carte »), garde
    chacune de ses ventes. Mesure sur l'export du 24 nov : 1 778 722 lignes pour 1 264 949 annonces ; 1,9 % des annonces ont
    des lignes a plusieurs dates (a un jour pres pour 86 % d'entre elles)."""
    try:
        j = dt.date.fromisoformat(str(le)[:10]).toordinal()
    except ValueError:
        return False
    p = float(prix or 0)
    for le2, p2 in deja:
        try:
            if abs(j - dt.date.fromisoformat(str(le2)[:10]).toordinal()) <= 1 and abs(p - float(p2)) <= 0.05 * max(p, float(p2)):
                return True
        except ValueError:
            continue
    return False


def id_vente(url, titre=None, le=None, prix=None):
    """Une vente = une annonce eBay vendue : son numero (dans le lien). Nos archives la gardent une fois par recherche qui l'a
    trouvee, au prix converti a quelques cents pres : sans ce numero, la meme vente comptait 2, 3 ou 4 fois."""
    m = _RE_ITM.search(str(url or ""))
    return m.group(1) if m else hashlib.md5(f"{titre}|{le}|{prix}".encode("utf-8", "ignore")).hexdigest()[:16]


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
    c = sqlite3.connect(_ch(), timeout=30)
    if _ch() in _ETAT["tables"]:
        return c
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS liquidite (cle TEXT, idv TEXT, le TEXT, prix REAL, PRIMARY KEY (cle, idv, le, prix)) WITHOUT ROWID")
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
        import base_ventes
        if not _ETAT.get("ancien_ote"):                  # 20 nov 2026 : la 1re version de l'index vivait dans base_ventes.sqlite
            try:
                v = base_ventes._cx()
                try:
                    v.execute("DROP TABLE IF EXISTS liquidite")
                    v.execute("DROP TABLE IF EXISTS liquidite_etat")
                    v.commit()
                finally:
                    v.close()
                _ETAT["ancien_ote"] = True
            except Exception as e:
                print("Liquidite (ancien index) : " + repr(e)[:120], flush=True)
        c = _cx()
        try:
            r = c.execute("SELECT v FROM liquidite_etat WHERE k='rowid'").fetchone()
            dernier = int(r[0]) if r else 0
            while True:
                v = base_ventes._cx()                     # une courte lecture par paquet, jamais de transaction ouverte
                try:
                    rows = v.execute("SELECT rowid, titre, prix, le, url FROM ventes WHERE rowid > ? ORDER BY rowid LIMIT ?", (dernier, PAQUET)).fetchall()
                finally:
                    v.close()
                if not rows:
                    break
                lignes, lot = [], {}
                for _rid, t, p, le, u in rows:
                    le = str(le or "")[:10]
                    if t and p and float(p) >= 3 and le >= d0:
                        k, i = cle(t), id_vente(u, t, le, p)
                        if (k, i) not in lot:                    # les ventes deja gardees de cette annonce (l'index, puis ce paquet)
                            lot[(k, i)] = c.execute("SELECT le, prix FROM liquidite WHERE cle = ? AND idv = ?", (k, i)).fetchall()
                        if meme_vente(lot[(k, i)], le, p):       # la meme vente, relue par une autre recherche : une seule ligne
                            continue
                        lot[(k, i)].append((le, float(p)))
                        lignes.append((k, i, le, round(float(p), 2)))
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
    """{titre: (liq, med, vieux)} pour des annonces ; None si l'index n'est pas encore pret (l'annonce sera jugee au prochain
    balayage plutot que rejetee). vieux : les ventes de la carte entre LIQ_JOURS et MED_JOURS jours avant aujourd'hui."""
    _rafraichir_si_besoin()
    c = _cx()
    if _ch() not in _ETAT["pret"]:
        c.close()
        return None
    auj = dt.date.today().isoformat()
    l60 = (dt.date.today() - dt.timedelta(days=LIQ_JOURS)).isoformat()
    l90 = (dt.date.today() - dt.timedelta(days=MED_JOURS)).isoformat()
    out = {}
    try:
        for t in titres:
            hist = c.execute("SELECT le, prix FROM liquidite WHERE cle = ?", (cle(t),)).fetchall()
            out[t] = (sum(1 for le, _ in hist if le >= l60), mediane_recente(hist, auj), sum(1 for le, _ in hist if l90 <= le < l60))
    finally:
        c.close()
    return out


def passe(liq, med, total, vieux=None):
    """La regle du Radar Pro sur les signaux d'une annonce (la note SlabIQ se juge a part). vieux inconnu (None) : refusee
    (on ne montre pas une carte dont on ne sait pas si elle est neuve)."""
    if (liq or 0) < LIQ_MIN:
        return False
    if anciennete_permise() and (vieux or 0) < VIEUX_MIN:
        return False
    if not prix_permis():
        return True
    return bool(med) and float(total or 0) <= (1 + RABAIS_MAX) * float(med)
