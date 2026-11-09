"""9 nov 2026 (Mathieu : « assure-toi que l'app fetch automatiquement tous les updates eBay niveaux financiers ou legaux,
comme les tarifs, pour toujours etre a jour. A tous les jours en back end »).

Une fois par jour, en fond (boucle horaire du serveur) :
  1. eBay Canada, « Seller updates » (la page officielle des changements : frais, politiques, lois) : chaque nouvelle entree
     est gardee ; une entree financiere ou legale est signalee a l'admin (notification + console Admin).
  2. Frais d'importation vers le Canada : la valeur par defaut (annonce pas encore relue) suit ce qu'eBay facture VRAIMENT
     sur les annonces relues ces 14 derniers jours (importCharges de Browse), au lieu d'un chiffre fige.
  3. Douanes vers les Etats-Unis (acheteur americain) : quelques annonces canadiennes relues avec un acheteur aux
     Etats-Unis ; si eBay y donne ses frais d'importation, l'estimation suit.
Les frais de vente eBay de chaque compte suivent ses VRAIES ventes (Api.frais_calibrer, frais d'eBay de chaque commande).
Rien n'est achete ni modifie chez eBay ; lecture seulement."""
import html as _html
import json
import os
import re
import statistics
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

SOURCES = [
    {"id": "ca", "nom": "eBay Canada", "url": "https://www.ebay.ca/sellercentre/resources/seller-updates/timeline"},
]
FIN = re.compile(r"fee|frais|tax|import|dut(y|ies)|tariff|tarif|douan|customs|payout|payment|paiement|pricing|final value|"
                 r"per-order|promoted|ad rate|currency|devise|refund|rembours", re.I)
LEGAL = re.compile(r"law|loi|legal|l[ée]gal|regulat|r[èe]glement|polic|politique|agreement|entente|terms|conditions|return|"
                   r"retour|protection|feedback|[ée]valuation|authentic|greenwash|privacy|confidentialit", re.I)
_VERROU = threading.Lock()
_ETAT = {"le": 0.0}
JOUR_S = 23 * 3600


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "veille_ebay.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _ecrire(d):
    p = _chemin()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)


def _telecharger(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SlabCoach)", "Accept-Language": "en-CA,fr-CA;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(3_000_000).decode("utf-8", "ignore")


def entrees(page, base="https://www.ebay.ca"):
    """Les entrees d'une page « Seller updates » : [{url, titre}] (liens vers les nouvelles officielles)."""
    out, vus = [], set()
    for href, txt in re.findall(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', page or "", re.S | re.I):
        href = _html.unescape(href).strip()
        if href.startswith("/"):
            href = base + href
        if not re.search(r"/sellercentre/(news|resources/seller-updates)/[^/]+", href) or href.rstrip("/").endswith("/timeline"):
            continue
        t = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", txt))).strip()
        if not t or len(t) > 160 or href in vus:
            continue
        vus.add(href)
        out.append({"url": href, "titre": t})
    return out


def sorte(titre):
    t = titre or ""
    return "frais" if FIN.search(t) else "legal" if LEGAL.search(t) else "autre"


def taux_cartes(page):
    """Le taux des frais de vente des cartes a collectionner (sans boutique) cite dans une nouvelle, s'il y est : 13.25 -> 13.25."""
    txt = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", page or "")))
    m = re.search(r"(?:Sports )?Trading Cards[^%]{0,120}?(\d{1,2}(?:\.\d{1,2})?)\s?%", txt, re.I)
    try:
        v = float(m.group(1)) if m else None
    except ValueError:
        v = None
    return v if v is not None and 5 <= v <= 25 else None


def _verifier_sources(d, alerter=None, lire_page=_telecharger):
    nouv = []
    for s in SOURCES:
        etat = d.setdefault("sources", {}).setdefault(s["id"], {"vus": []})
        try:
            lst = entrees(lire_page(s["url"]))
        except Exception as e:
            etat["erreur"] = str(e)[:160]
            etat["erreur_le"] = datetime.now().isoformat(timespec="seconds")
            continue
        if not lst:                                 # page changee (plus aucun lien reconnu) : on le dit, sans fausse alerte
            etat["erreur"] = "aucune entrée reconnue (page changée ?)"
            etat["erreur_le"] = datetime.now().isoformat(timespec="seconds")
            continue
        etat.pop("erreur", None)
        vus = set(etat.get("vus") or [])
        premiere = not etat.get("init")
        for e in lst:
            if e["url"] in vus:
                continue
            vus.add(e["url"])
            if premiere:
                continue                            # le premier passage apprend la page (pas 30 alertes d'un coup)
            n = {"le": datetime.now().isoformat(timespec="seconds"), "source": s["nom"], "titre": e["titre"], "url": e["url"],
                 "sorte": sorte(e["titre"])}
            if n["sorte"] == "frais":
                try:
                    n["taux_cartes"] = taux_cartes(lire_page(e["url"].split("#")[0]))
                except Exception:
                    pass
            nouv.append(n)
        etat.update(vus=sorted(vus)[-600:], init=True, le=datetime.now().isoformat(timespec="seconds"))
    if nouv:
        d["nouveautes"] = (nouv + (d.get("nouveautes") or []))[:60]
        imp = [n for n in nouv if n["sorte"] in ("frais", "legal")]
        if imp and alerter:
            t = imp[0]["titre"] + (f" (+{len(imp) - 1})" if len(imp) > 1 else "")
            try:
                alerter("SlabCoach · changement eBay", ("Frais : " if imp[0]["sorte"] == "frais" else "Règles : ") + t)
            except Exception as e:
                print("Veille eBay (alerte) : " + repr(e), flush=True)
    return nouv


def _p(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(q * (len(vals) - 1) + 0.5))]


def calibrer_import(d, annonces=None):
    """Frais d'importation vers le Canada : le 60e centile de ce qu'eBay facture (import / (prix + port)) sur les annonces
    hors Canada relues ces 14 jours, + la TPS/TVH percue a part ; 15 annonces au moins, sinon rien ne change."""
    import deals
    if annonces is None:
        g = deals.lire()
        annonces = [x for k in ("deals", "suivis", "pres", "retires") for x in (g.get(k) or []) if isinstance(x, dict)]
    lim = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    r, vus = [], set()
    for x in annonces:
        if not x.get("import_lu") or not deals.etranger(x, "CA") or x.get("item_id") in vus:
            continue
        if str(x.get("vu_le") or x.get("import_le") or "9") < lim:
            continue
        base = float(x.get("prix_cad") or 0) + float(x.get("port_cad") or 0)
        if base <= 5:
            continue
        vus.add(x.get("item_id"))
        r.append(float(x.get("import_cad") or 0) / base)
    d["import_n"] = len(r)
    if len(r) >= 15:
        v = round(min(0.80, max(0.15, _p(r, 0.60) + deals.TAXE_IMPORT)), 4)
        d["import_defaut"] = v
        d["import_le"] = datetime.now().isoformat(timespec="seconds")
    return d.get("import_defaut")


def calibrer_import_us(d, annonces=None, lire_article=None, n_max=8):
    """Douanes pour un acheteur aux Etats-Unis : quelques annonces canadiennes relues avec un acheteur americain (8 appels
    Browse par jour au plus). Si eBay y donne ses frais d'importation (5 au moins), l'estimation IMPORT_US les suit."""
    import deals
    import ebay_compte
    lire_article = lire_article or (lambda i: ebay_compte.article(i, fond=True, frais=True, pays="US"))
    if annonces is None:
        g = deals.lire()
        annonces = [x for x in (g.get("deals") or []) if isinstance(x, dict)]
    cands = [x for x in annonces if str(x.get("lieu") or "").upper() == "CA" and not x.get("encan") and x.get("item_id")][:n_max]
    obs = []
    for x in cands:
        try:
            a = lire_article(x["item_id"])
        except Exception:
            continue
        if not a or not a.get("import_lu"):
            continue
        base = float(a.get("prix_cad") or 0) + float(a.get("port_cad") or 0)
        if base > 5:
            obs.append(float(a.get("import_cad") or 0) / base)
    d["import_us_n"] = len(obs)
    if len(obs) >= 5 and any(o > 0 for o in obs):
        d["import_us"] = round(min(0.60, max(0.0, statistics.median(obs))), 4)
        d["import_us_le"] = datetime.now().isoformat(timespec="seconds")
    return d.get("import_us")


def appliquer(d=None):
    """Les valeurs apprises remplacent les chiffres figes (sauf si Render les impose : LR_IMPORT_DEFAUT, LR_IMPORT_US)."""
    import deals
    d = lire() if d is None else d
    if d.get("import_defaut") and not os.environ.get("LR_IMPORT_DEFAUT"):
        deals.IMPORT_DEFAUT = float(d["import_defaut"])
    if d.get("import_us") is not None and not os.environ.get("LR_IMPORT_US"):
        deals.IMPORT_US = float(d["import_us"])


def rafraichir(alerter=None, lire_page=_telecharger, us=True):
    with _VERROU:
        d = lire()
        nouv = _verifier_sources(d, alerter, lire_page)
        for nom, f in (("import", calibrer_import), ("import_us", calibrer_import_us if us else None)):
            if not f:
                continue
            try:
                f(d)
            except Exception as e:
                d.setdefault("erreurs", {})[nom] = str(e)[:160]
        d["le"] = datetime.now().isoformat(timespec="seconds")
        _ecrire(d)
        appliquer(d)
        return {"ok": True, "nouveautes": len(nouv), "import_defaut": d.get("import_defaut"), "import_us": d.get("import_us")}


def rafraichir_si_besoin(alerter=None):
    """Boucle horaire du serveur : une fois par jour (23 h)."""
    if os.environ.get("LR_VEILLE_EBAY", "1") == "0":
        return None
    if time.time() - _ETAT["le"] < JOUR_S:
        return None
    try:
        der = datetime.fromisoformat(lire().get("le") or "2000-01-01").timestamp()
    except ValueError:
        der = 0
    _ETAT["le"] = time.time()
    if time.time() - der < JOUR_S:                     # deja fait aujourd'hui (redemarrage du serveur)
        appliquer()
        return None
    try:
        return rafraichir(alerter)
    except Exception as e:
        print("Veille eBay : " + repr(e), flush=True)
        return None


def resume():
    """Pour la console Admin."""
    import deals
    d = lire()
    return {"le": d.get("le"), "nouveautes": (d.get("nouveautes") or [])[:12],
            "sources": {k: {"le": v.get("le"), "erreur": v.get("erreur"), "n": len(v.get("vus") or [])} for k, v in (d.get("sources") or {}).items()},
            "import_defaut": round(deals.IMPORT_DEFAUT * 100, 1), "import_n": d.get("import_n"), "import_le": d.get("import_le"),
            "import_us": round(deals.IMPORT_US * 100, 1), "import_us_n": d.get("import_us_n"), "import_us_le": d.get("import_us_le")}
