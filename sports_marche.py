"""
SLABCOACH - quel sport ajouter apres le hockey ? (13 nov 2026, admin)

Mathieu : « il va falloir commencer a integrer les autres sports ; prendre le 2e sport le plus vendu au Canada ; fie-toi
aux ventes ; on scalera quand on sera plus gros ».

Aucune source publique ne donne les ventes de cartes PAR SPORT AU CANADA. On les estime avec ce que le serveur peut lire :
  1. LES VENTES (le coeur) : TheCardAPI (ventes eBay reelles, gratuit) : les 100 dernieres ventes de chaque sport -> combien
     de ventes par heure (le rythme). Si l'API donne un total, on le garde aussi.
  2. LA PART DU CANADA : eBay Browse (gratuit) : le nombre d'annonces de cartes de chaque sport chez les vendeurs situes au
     Canada, contre le meme nombre dans le monde -> l'indice Canada du sport (1,0 = comme ailleurs ; 2,0 = deux fois plus
     present au Canada).
  3. NOS VENDEURS CANADIENS (Savage, Remi, CF31, Slab Sharks) : combien de cartes de chaque sport ils ont en vente.
Ventes estimees au Canada = part des ventes x indice Canada (remis sur 100 %). Le verdict : le sport non-hockey en tete.
Cout : ~500 lignes TheCardAPI (sur 5 000 gratuites par jour) et 15 appels Browse. Aucun credit CompSniper.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

# sport -> (mot des ventes, valeur de l'aspect « Sport » d'eBay)
SPORTS = {"hockey": ("hockey", "Ice Hockey"), "basketball": ("basketball", "Basketball"), "baseball": ("baseball", "Baseball"),
          "football": ("football", "Football"), "soccer": ("soccer", "Soccer")}
NOMS = {"hockey": "Hockey", "basketball": "Basketball", "baseball": "Baseball", "football": "Football", "soccer": "Soccer"}
CAT_CARTES = "261328"                # eBay : Sports Trading Card Singles


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "sports_marche.json")


def lire():
    try:
        with open(_chemin(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _date(v):
    s = str(v or "").replace("Z", "+00:00")
    for f in (lambda x: datetime.fromisoformat(x), lambda x: datetime.strptime(x[:10], "%Y-%m-%d")):
        try:
            return f(s).timestamp()
        except ValueError:
            continue
    return None


def _total(d):
    for src in (d, (d or {}).get("meta") or {}, (d or {}).get("pagination") or {}):
        if isinstance(src, dict):
            for k in ("total", "total_count", "totalCount", "count_total"):
                try:
                    v = int(src.get(k))
                    if v > 0:
                        return v
                except (TypeError, ValueError):
                    continue
    return None


def rythme_ventes(lignes):
    """Les ventes (TheCardAPI) -> ventes par heure, d'apres l'ecart entre la plus recente et la plus ancienne. None si les
    dates n'ont pas d'heure (toutes le meme jour) : alors on compte par jour."""
    ts = sorted(t for t in (_date(x.get("sale_date")) for x in lignes if isinstance(x, dict)) if t)
    if len(ts) < 10:
        return None
    ecart_h = (ts[-1] - ts[0]) / 3600
    if ecart_h < 0.5:                       # 100 ventes en moins de 30 min (ou dates sans heure) : au moins 200/h
        return round(len(ts) / 0.5, 1)
    return round((len(ts) - 1) / ecart_h, 2)


def _ventes(mot):
    import thecardapi
    if not thecardapi.actif():
        return {"erreur": "TheCardAPI inactif"}
    if not thecardapi._budget_ok("etude", 100):
        return {"erreur": "plafond du jour TheCardAPI"}
    try:
        d = thecardapi._appel({"q": mot, "limit": 100}, 20)
    except Exception as e:
        return {"erreur": "TheCardAPI : " + type(e).__name__}
    lignes = [x for x in (d or {}).get("data") or [] if isinstance(x, dict)]
    thecardapi._compter(len(lignes), "etude")
    pays = {}
    for x in lignes:                         # le pays du vendeur, si l'API le donne (on apprend le schema en meme temps)
        for k in ("seller_country", "item_country", "country", "location", "item_location", "seller_location"):
            v = x.get(k)
            if v:
                k2 = "CA" if ("canada" in str(v).lower() or str(v).upper().strip() in ("CA", "CAN")) else "autre"
                pays[k2] = pays.get(k2, 0) + 1
                break
    return {"n": len(lignes), "par_heure": rythme_ventes(lignes), "total": _total(d), "pays": pays or None,
            "champs": sorted(lignes[0].keys())[:30] if lignes else None}


def _annonces(aspect, filtre=None, pays="CA"):
    """Le nombre d'annonces actives (le « total » de la Browse API) de cartes d'un sport. Une requete de 1 resultat."""
    import appels_ebay
    import ebay_compte
    appels_ebay.exiger("browse", True)
    p = {"limit": 1, "category_ids": CAT_CARTES, "aspect_filter": f"categoryId:{CAT_CARTES},Sport:{{{aspect}}}"}
    if filtre:
        p["filter"] = filtre
    adresse = ebay_compte.url("recherche") + "?" + urllib.parse.urlencode(p, quote_via=urllib.parse.quote)
    req = urllib.request.Request(adresse, headers={"Authorization": "Bearer " + ebay_compte.jeton_application(), "Accept": "application/json",
                                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_" + pays})
    appels_ebay.compter("browse")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int((json.loads(r.read()) or {}).get("total") or 0)


def combiner(m):
    """Les mesures brutes -> la part estimee de chaque sport au Canada et le verdict. Calcul pur (teste)."""
    S = list(m)
    v = {s: (m[s].get("ventes") or {}).get("par_heure") for s in S}
    if not all(v.get(s) for s in S):
        v = {s: (m[s].get("ventes") or {}).get("total") for s in S}
    ok_v = all(v.get(s) for s in S)
    ca = {s: m[s].get("annonces_ca") or 0 for s in S}
    mo = {s: m[s].get("annonces_monde") or 0 for s in S}
    sca, smo = sum(ca.values()), sum(mo.values())
    indice = {s: round((ca[s] / sca) / (mo[s] / smo), 2) if sca and smo and mo[s] and ca[s] else None for s in S}
    out = {}
    if ok_v:
        sv = sum(v.values())
        brut = {s: (v[s] / sv) * (indice[s] if indice[s] is not None else 1.0) for s in S}
        sb = sum(brut.values()) or 1
        for s in S:
            out[s] = {"part_ventes": round(100 * v[s] / sv, 1), "indice_ca": indice[s], "part_canada": round(100 * brut[s] / sb, 1)}
    elif sca:                                 # pas de ventes lisibles : les annonces au Canada seulement (a defaut)
        for s in S:
            out[s] = {"part_ventes": None, "indice_ca": indice[s], "part_canada": round(100 * ca[s] / sca, 1)}
    for s in S:
        out.setdefault(s, {})
        out[s].update(annonces_ca=ca[s] or None, annonces_monde=mo[s] or None, chez_nos_vendeurs=m[s].get("chez_nos_vendeurs"),
                      ventes_heure=(m[s].get("ventes") or {}).get("par_heure"))
    cl = sorted([s for s in S if s != "hockey" and out[s].get("part_canada") is not None], key=lambda s: -out[s]["part_canada"])
    return {"sports": out, "classement": cl, "verdict": cl[0] if cl else None, "base": "ventes" if ok_v else "annonces"}


def mesurer():
    import deals
    m = {}
    for s, (mot, aspect) in SPORTS.items():
        e = {"ventes": _ventes(mot)}
        try:
            e["annonces_ca"] = _annonces(aspect, "itemLocationCountry:CA", "CA")
            e["annonces_monde"] = _annonces(aspect, None, "US")
            e["chez_nos_vendeurs"] = _annonces(aspect, "sellers:{" + "|".join(deals.VENDEURS_PRIORITE) + "}", "CA")
        except Exception as ex:
            e["erreur_ebay"] = str(ex)[:160]
        m[s] = e
        time.sleep(0.3)
    r = combiner(m)
    r.update(le=datetime.now().isoformat(timespec="seconds"), brut=m)
    try:
        p = _chemin()
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
    except OSError:
        pass
    return r
