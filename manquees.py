"""
SLABCOACH - les aubaines manquees (25 nov 2026, Mathieu : « on aurait du capter cette carte-la » ; « on ne devrait jamais
manquer ce genre de deal-la » ; « la meilleure chose pour capter le plus de cartes possible a l'avenir »).

La mesure, sans aucun credit ni appel eBay :
  1. le REGISTRE : chaque annonce que le chasseur juge laisse une ligne : quand il l'a vue la premiere fois, a combien
     d'heures de la fin, et ce qu'il en a conclu (deal, trop chere, sans valeur, ecartee, hors fenetre). Aucun contenu
     d'eBay n'est garde : la cle est une EMPREINTE a sens unique du numero de l'annonce ; le reste est a nous (l'heure ou
     nous l'avons vue, notre verdict, notre valeur). 21 jours.
  2. chaque nuit : dans NOS ventes (base_ventes : SoldComps, TheCardAPI), chaque carte vendue au prix max de la regle du
     chasseur ou moins (30 % de profit apres les frais, valeur = les ventes de la meme carte AVANT cette vente, 30 $ et
     plus). C'est une aubaine. Le registre dit si elle a ete montree avant la fin, et sinon pourquoi.
Limites, dites telles quelles a l'ecran : le port de la vente n'est pas connu (une aubaine « sans le port ») ; seules les
ventes que nous avons recues comptent ; rien avant la mise en service du registre.
"""
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

GARDER_J = 21                    # une ligne du registre (un encan dure 10 jours ; ses ventes nous arrivent jusqu'a 10 jours apres)
JOURS_REVUS = 10                 # chaque nuit : les ventes des 10 derniers jours (elles arrivent avec du retard)
JOURS_RAPPORT = 45
VALEUR_MIN = 30.0                # comme le chasseur : rien savoir des cartes sous 30 $
MAX_VENTES = 60000               # lignes de ventes lues par calcul (les plus recentes d'abord)
BUDGET_S = 420                   # un calcul ne prend jamais plus de 7 minutes au serveur
EXEMPLES = 80
ENTRE_CALCULS_S = 12 * 3600
TARD_H = 1.0                     # montree a moins d'une heure de la fin : « trop tard pour miser »
# le verdict garde est le plus FORT jamais vu (un encan vu hors fenetre lundi, puis juge mardi)
RANGS = {"deal": 6, "photo": 5, "trop_cher": 4, "pres": 4, "comps_vieilles": 3, "sans_ventes": 3, "ecartee": 2, "joueur": 2,
         "sport": 2, "fenetre": 1, "autre": 0}
# ce que l'ecran montre : 5 raisons, pas 11
GROUPES = {"deal": "montree", "trop_cher": "trop_cher", "pres": "trop_cher", "sans_ventes": "sans_valeur",
           "comps_vieilles": "sans_valeur", "photo": "ecartee", "ecartee": "ecartee", "joueur": "ecartee", "sport": "ecartee",
           "fenetre": "fenetre", "autre": "ecartee"}
_RE_NUM = re.compile(r"(?<!\d)(\d{9,15})(?!\d)")
_RE_ITM = re.compile(r"/itm/(?:[^/?#]*/)?(\d{9,15})")
_verrou = threading.Lock()
_TAMPON = []
_ETAT = {"purge": 0.0, "pret": set()}


def empreinte(item_id):
    """L'empreinte a sens unique d'un numero d'annonce (ou None)."""
    m = _RE_NUM.search(str(item_id or ""))
    return hashlib.sha256(("slabcoach|vu|" + m.group(1)).encode()).hexdigest()[:24] if m else None


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "chasse_vus.sqlite")


def _chemin_rapport():
    import comptes
    return os.path.join(comptes.DONNEES, "aubaines_manquees.json")


def _cx():
    ch = _chemin()
    c = sqlite3.connect(ch, timeout=30)
    if ch not in _ETAT["pret"] or not os.path.getsize(ch):
        c.execute("CREATE TABLE IF NOT EXISTS vus (h TEXT PRIMARY KEY, vu INTEGER, maj INTEGER, avant_h REAL, res TEXT, rg INTEGER, "
                  "deal INTEGER, deal_h REAL, enc INTEGER, val REAL)")
        c.execute("CREATE INDEX IF NOT EXISTS vus_vu ON vus (vu)")
        c.commit()
        _ETAT["pret"].add(ch)
    return c


def noter(a, res, maint=None, valeur=None):
    """Le chasseur vient de juger l'annonce « a » : une ligne au registre (en memoire ; ecrite par paquets, voir vider)."""
    h = empreinte(a.get("item_id"))
    if not h:
        return
    maint = maint or datetime.now(timezone.utc)
    avant = None
    if a.get("fin"):
        try:
            avant = round((datetime.fromisoformat(str(a["fin"]).replace("Z", "+00:00")) - maint).total_seconds() / 3600, 2)
        except ValueError:
            avant = None
    res = res if res in RANGS else "autre"
    try:
        val = round(float(valeur), 2) if valeur else None
    except (TypeError, ValueError):
        val = None
    with _verrou:
        _TAMPON.append((h, int(maint.timestamp()), avant, res, RANGS[res], 1 if res == "deal" else 0, 1 if a.get("encan") else 0, val))
        plein = len(_TAMPON) >= 400
    if plein:
        vider()


def vider():
    """Ecrit le tampon. Une fois par heure : retire les lignes de plus de GARDER_J jours."""
    with _verrou:
        lot = list(_TAMPON)
        del _TAMPON[:]
    purge = time.time() - _ETAT["purge"] > 3600
    if not lot and not purge:
        return 0
    try:
        c = _cx()
        try:
            c.executemany(
                "INSERT INTO vus (h, vu, maj, avant_h, res, rg, deal, deal_h, enc, val) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(h) DO UPDATE SET maj = excluded.maj, "
                "res = CASE WHEN excluded.rg >= rg THEN excluded.res ELSE res END, rg = MAX(rg, excluded.rg), "
                "deal_h = CASE WHEN deal = 0 AND excluded.deal = 1 THEN excluded.avant_h ELSE deal_h END, "
                "deal = MAX(deal, excluded.deal), val = COALESCE(excluded.val, val)",
                [(h, t, t, av, res, rg, dl, av if dl else None, enc, val) for h, t, av, res, rg, dl, enc, val in lot])
            if purge:
                c.execute("DELETE FROM vus WHERE vu < ?", (int(time.time()) - GARDER_J * 86400,))
                _ETAT["purge"] = time.time()
            c.commit()
        finally:
            c.close()
    except sqlite3.Error as e:
        print("Manquees (registre) : " + repr(e)[:200], flush=True)
        return 0
    return len(lot)


def _registre(hs):
    """{empreinte: ligne} pour ces empreintes, et l'heure de la toute premiere ligne du registre (ou None)."""
    out, debut = {}, None
    try:
        c = _cx()
        try:
            debut = c.execute("SELECT MIN(vu) FROM vus").fetchone()[0]
            hs = list(hs)
            for i in range(0, len(hs), 500):
                p = hs[i:i + 500]
                for h, vu, avant, res, deal, deal_h, enc, val in c.execute(
                        "SELECT h, vu, avant_h, res, deal, deal_h, enc, val FROM vus WHERE h IN (%s)" % ",".join("?" * len(p)), p):
                    out[h] = {"vu": vu, "avant_h": avant, "res": res, "deal": bool(deal), "deal_h": deal_h, "enc": bool(enc), "val": val}
        finally:
            c.close()
    except sqlite3.Error as e:
        print("Manquees (lecture) : " + repr(e)[:200], flush=True)
    return out, debut


def _num(url, cle=None):
    m = _RE_ITM.search(str(url or "")) or _RE_ITM.search(str(cle or "")) or _RE_NUM.search(str(cle or ""))
    return m.group(1) if m else None


def _cle_carte(cib):
    return json.dumps([cib.get(k) if not isinstance(cib.get(k), (set, tuple)) else sorted(cib[k]) for k in sorted(cib)],
                      sort_keys=True, default=str)


def aubaine(vente, bassin, memo=None):
    """(valeur, prix max) si cette vente est une aubaine selon la regle du chasseur, sinon None. La valeur vient des ventes de
    la MEME carte des jours d'avant."""
    import cartes_match
    import deals
    titre, jour = vente.get("titre") or "", str(vente.get("le") or "")[:10]
    try:
        prix = float(vente.get("prix") or 0)
    except (TypeError, ValueError):
        return None
    if prix <= 0 or not titre or not jour:
        return None
    cib = cartes_match.cible_titre(titre)
    if cib.get("exclu") or not cib.get("joueur") or cartes_match.abimee(titre):
        return None
    try:                                                 # comme le chasseur : seulement un sport qu'il sert (hockey d'abord)
        import sports
        sp = deals.sport_carte(titre, cib)
        if not sp or not sports.sert("deals", sp):
            return None
    except Exception:
        return None
    memo = memo if memo is not None else {}
    k = _cle_carte(cib)
    if k not in memo:
        memo[k] = deals.memes_ventes(cib, bassin.candidats(cib))
    num = vente.get("num")
    # les ventes des jours d'AVANT seulement : ce que le chasseur pouvait savoir avant la fin (jamais la vente elle-meme, ni
    # celles du meme jour)
    pv = [v for v in memo[k] if str(v.get("le") or "")[:10] < jour and not (num and _num(v.get("url")) == num)]
    val, _g = deals.valeur_sure(pv, titre)
    if not val or val < VALEUR_MIN:
        return None
    pm = deals.prix_max(val)
    return (round(val, 2), round(pm, 2)) if prix <= pm else None


def lire_ventes(depuis, max_=MAX_VENTES):
    """Nos ventes depuis ce jour (une ligne par annonce : la meme vente revient sous plusieurs recherches)."""
    import base_ventes
    out, vus = [], set()
    try:
        c = base_ventes._cx()
        try:
            for titre, prix, le, url, cle in c.execute("SELECT titre, prix, le, url, cle FROM ventes WHERE le >= ? ORDER BY le DESC LIMIT ?",
                                                       (depuis, int(max_))):
                num = _num(url, cle)
                if not num or num in vus:
                    continue
                vus.add(num)
                out.append({"titre": titre, "prix": prix, "le": le, "url": url, "num": num})
        finally:
            c.close()
    except sqlite3.Error as e:
        print("Manquees (ventes) : " + repr(e)[:200], flush=True)
    return out


def calculer(bassin=None, maint=None, ventes=None, jours=JOURS_REVUS, budget_s=BUDGET_S):
    """Le rapport : par jour, les aubaines de nos ventes, celles montrees avant la fin, et la raison des autres."""
    import deals
    maint = maint or datetime.now(timezone.utc)
    vider()
    auj = maint.strftime("%Y-%m-%d")
    d0 = (maint - timedelta(days=jours)).strftime("%Y-%m-%d")
    ventes = lire_ventes(d0) if ventes is None else [dict(v, num=v.get("num") or _num(v.get("url"), v.get("id"))) for v in ventes]
    ventes = [v for v in ventes if d0 <= str(v.get("le") or "")[:10] < auj and v.get("num")]
    reg, debut = _registre({empreinte(v["num"]) for v in ventes})
    if not debut:
        return _ecrire_rapport({"le": maint.isoformat(timespec="seconds"), "depuis": None, "jours": {}, "exemples": []}, garder=True)
    # le premier jour ENTIER du registre : une vente d'avant ne peut pas avoir ete vue
    j_debut = (datetime.fromtimestamp(debut, timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    bassin = bassin if bassin is not None else deals.bassin_partage()
    memo, par_jour, ex, t0, coupe = {}, {}, [], time.time(), False
    for i, v in enumerate(sorted(ventes, key=lambda v: str(v["le"]), reverse=True)):
        jour = str(v["le"])[:10]
        if jour < j_debut:
            continue
        if time.time() - t0 > budget_s:
            coupe = True
            break
        if i % 25 == 24:
            time.sleep(0.01)                             # le serveur sert les ecrans entre deux paquets
        j = par_jour.setdefault(jour, {"ventes": 0, "aubaines": 0, "montrees": 0, "tard": 0, "raisons": {}})
        j["ventes"] += 1
        try:
            a = aubaine(v, bassin, memo)
        except Exception as e:
            print("Manquees (valeur) : " + repr(e)[:200], flush=True)
            a = None
        if not a:
            continue
        val, pm = a
        j["aubaines"] += 1
        r = reg.get(empreinte(v["num"]))
        raison = GROUPES.get(r["res"], "ecartee") if r else "jamais_vue"
        if r and r["deal"]:
            raison = "montree"
        if raison == "montree":
            j["montrees"] += 1
            if r.get("deal_h") is not None and r["deal_h"] < TARD_H:
                j["tard"] += 1
            continue
        j["raisons"][raison] = j["raisons"].get(raison, 0) + 1
        ex.append({"titre": str(v["titre"])[:140], "prix": round(float(v["prix"]), 2), "valeur": val, "max": pm, "jour": jour, "raison": raison,
                   "vu_h": r.get("avant_h") if r else None, "encan": r.get("enc") if r else None, "notre_valeur": r.get("val") if r else None})
    ex.sort(key=lambda x: x["prix"] - x["max"])            # le plus loin sous le prix max d'abord
    rap = {"le": maint.isoformat(timespec="seconds"), "depuis": j_debut, "jours": par_jour, "exemples": ex[:EXEMPLES], "coupe": coupe,
           "revus": sorted(par_jour)}
    return _ecrire_rapport(rap)


def _ecrire_rapport(rap, garder=False):
    """Les jours recalcules remplacent les leurs ; les jours plus vieux restent (JOURS_RAPPORT)."""
    vieux = lire()
    jours = dict(vieux.get("jours") or {})
    jours.update(rap.get("jours") or {})
    lim = (datetime.now(timezone.utc) - timedelta(days=JOURS_RAPPORT)).strftime("%Y-%m-%d")
    rap = {**rap, "jours": {k: v for k, v in jours.items() if k >= lim}}
    if garder and vieux.get("exemples"):
        rap["exemples"] = vieux["exemples"]
    ch = _chemin_rapport()
    try:
        with open(ch + ".tmp", "w", encoding="utf-8") as f:
            json.dump(rap, f, ensure_ascii=False)
        os.replace(ch + ".tmp", ch)
    except OSError as e:
        print("Manquees (rapport) : " + repr(e)[:200], flush=True)
    return rap


def lire():
    try:
        with open(_chemin_rapport(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def calculer_si_besoin(bassin=None):
    """Appele a la fin de chaque tour du chasseur : le rapport se refait aux 12 heures."""
    try:
        age = time.time() - os.path.getmtime(_chemin_rapport())
    except OSError:
        age = None
    if age is not None and age < ENTRE_CALCULS_S:
        vider()
        return None
    return calculer(bassin=bassin)


def resume(rap=None, jours=7, maint=None):
    """Pour l'ecran : hier, les `jours` derniers jours, les raisons, les exemples."""
    rap = rap if rap is not None else lire()
    maint = maint or datetime.now(timezone.utc)
    js = rap.get("jours") or {}
    lim = (maint - timedelta(days=jours)).strftime("%Y-%m-%d")

    def somme(cles):
        t = {"ventes": 0, "aubaines": 0, "montrees": 0, "tard": 0, "raisons": {}}
        for k in cles:
            x = js[k]
            for c in ("ventes", "aubaines", "montrees", "tard"):
                t[c] += int(x.get(c) or 0)
            for r, n in (x.get("raisons") or {}).items():
                t["raisons"][r] = t["raisons"].get(r, 0) + n
        t["part"] = round(t["montrees"] / t["aubaines"], 3) if t["aubaines"] else None
        return t
    recents = sorted(k for k in js if k >= lim)
    return {"le": rap.get("le"), "depuis": rap.get("depuis"), "coupe": bool(rap.get("coupe")),
            "periode": {**somme(recents), "jours": len(recents)},
            "par_jour": [{"jour": k, **somme([k])} for k in sorted(js, reverse=True)[:14]],
            "exemples": rap.get("exemples") or []}
