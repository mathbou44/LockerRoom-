"""
SLABCOACH - le nombre de couleurs d'une patch (13 nov 2026).

Mathieu (une Gauthier Signature Swatches /49, patch 2 couleurs ; des 4 couleurs vendues pres de 300 $) : « une 2 couleurs
vaut a peu pres 60 % d'une 4 couleurs ; une 1 couleur vaut beaucoup moins qu'une 3 couleurs ; on doit en tenir compte
quand on met un montant ». Le BAREME (par rapport a une 4 couleurs) :
  1 couleur 35 % · 2 couleurs 60 % · 3 couleurs 80 % · 4 couleurs 100 % · 5 et plus / logo / tag / nameplate 115 %.
Le nombre vient du titre quand le vendeur l'ecrit (« 3 color patch », « tri-color », « logo patch »), sinon de la PHOTO
(l'IA compte les couleurs de tissu dans la fenetre ; une seule lecture par photo, gardee). Chaque vente comparable est
ramenee a la patch de la carte : prix x bareme(carte) / bareme(vente). Une vente dont on ne sait rien reste telle quelle.
"""
import hashlib
import json
import os
import re
import statistics
import threading

BAREME = {1: 0.35, 2: 0.60, 3: 0.80, 4: 1.00, 5: 1.15}
MAX_PHOTOS = 16
APPELS_JOUR = int(os.environ.get("LR_PATCHS_JOUR") or 400)     # lectures IA par jour au plus (le chasseur et les fiches)
_verrou = threading.Lock()
_JOUR = {"j": None, "n": 0}


def _budget_ok():
    from datetime import date
    j = date.today().isoformat()
    with _verrou:
        if _JOUR["j"] != j:
            _JOUR.update(j=j, n=0)
        if _JOUR["n"] >= APPELS_JOUR:
            return False
        _JOUR["n"] += 1
        return True

_RE_PATCH = re.compile(r"\b(patch(es)?|swatch(es)?|rpa|laundry tag|nameplate|logo patch|jumbo patch|tag patch|"
                       r"sigswatches|sigpatches)\b", re.I)
_MOTS_N = {"one": 1, "single": 1, "two": 2, "dual": 2, "double": 2, "three": 3, "tri": 3, "triple": 3, "four": 4, "quad": 4,
           "five": 5, "six": 6}
_RE_N = re.compile(r"\b(\d|one|single|two|dual|double|three|tri|triple|four|quad|five|six)\s*-?\s*(colou?rs?|clrs?|clr|cl|tone)\b", re.I)
_RE_PREMIUM = re.compile(r"\b(logo|laundry\s*tag|tag|nameplate|name\s*plate|letter|number\s*patch|nhl\s*shield|shield|"
                         r"captain'?s?\s*c|\bc\s*patch|button|eyelet|piping|stripe\s*logo)\b", re.I)


def est_patch(titre):
    return bool(_RE_PATCH.search(str(titre or "")))


def du_titre(titre):
    """Le nombre de couleurs ecrit dans un titre (« 3 color », « tri-color », « logo/tag » -> 5), sinon None."""
    t = str(titre or "")
    if _RE_PREMIUM.search(t) and est_patch(t):
        return 5
    m = _RE_N.search(t)
    if not m:
        return None
    w = m.group(1).lower()
    n = int(w) if w.isdigit() else _MOTS_N.get(w)
    return max(1, min(5, n)) if n else None


def facteur(n_carte, n_vente):
    if not n_carte or not n_vente:
        return 1.0
    return BAREME[max(1, min(5, int(n_carte)))] / BAREME[max(1, min(5, int(n_vente)))]


# -- la photo -----------------------------------------------------------------------------------------------------
OUTIL = {
    "name": "patchs",
    "description": "Le nombre de couleurs de tissu dans la fenetre de patch de chaque carte.",
    "input_schema": {"type": "object", "properties": {"cartes": {"type": "array", "items": {"type": "object", "properties": {
        "k": {"type": "integer", "description": "Le numero de l'image (1, 2, 3...)"},
        "couleurs": {"type": "integer", "description": "Couleurs de TISSU differentes dans la fenetre (1 a 6). 0 si aucune patch visible."},
        "special": {"type": "boolean", "description": "true si la patch montre un logo, une etiquette (tag), une lettre / un chiffre de chandail, un nameplate"},
        "certitude": {"type": "string", "enum": ["sure", "probable", "incertaine"]}},
        "required": ["k", "couleurs", "certitude"]}}}, "required": ["cartes"]},
}
SYSTEME = """Tu regardes des photos de cartes de hockey avec une piece de chandail (patch, swatch). Pour CHAQUE image, compte
les couleurs de TISSU differentes visibles dans la fenetre de la patch : une bande de couleur, une couture d'une autre couleur
de tissu, un morceau de logo comptent ; le carton imprime autour, l'autographe a l'encre et les reflets du slab ne comptent pas.
Des nuances du meme tissu (ombre, pli) = une seule couleur. Si la photo est floue ou la fenetre cachee : certitude « incertaine ».
Reponds avec l'outil « patchs », une entree par image, dans l'ordre."""


def _chemin_cache():
    import comptes
    return os.path.join(comptes.DONNEES, "patchs_cache.json")


def _cache():
    try:
        with open(_chemin_cache(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _cle(url):
    return hashlib.sha1(str(url).encode()).hexdigest()[:20]


def _net(url, t=500):
    u = str(url or "")
    return re.sub(r"/s-l\d+(\.(?:jpg|jpeg|png|webp))", rf"/s-l{t}\1", u.replace("/thumbs/images/", "/images/"))


def compter(urls):
    """{url: n (1 a 5) ou None} : le cache d'abord, puis une seule lecture IA pour les photos jamais vues."""
    urls = [u for u in dict.fromkeys(str(u) for u in urls or [] if u and str(u).startswith("http"))]
    c = _cache()
    out = {u: c[_cle(u)] for u in urls if _cle(u) in c}
    neuves = [u for u in urls if u not in out][:MAX_PHOTOS]
    if neuves and _budget_ok():
        try:
            import vision
            if not vision.disponible():
                raise RuntimeError("vision indisponible")
            contenu = []
            for k, u in enumerate(neuves):
                contenu.append({"type": "text", "text": f"Image {k + 1} :"})
                contenu.append({"type": "image", "source": {"type": "url", "url": _net(u)}})
            contenu.append({"type": "text", "text": f"Compte les couleurs de la patch de ces {len(neuves)} cartes."})
            r = vision._appeler({"model": vision.MODELE, "max_tokens": 120 + 40 * len(neuves), "system": SYSTEME, "tools": [OUTIL],
                                 "tool_choice": {"type": "tool", "name": "patchs"},
                                 "messages": [{"role": "user", "content": contenu}]}, timeout=90)
            try:
                vision._noter_serveur(r.get("usage") or {})
            except Exception:
                pass
            fiche = next((b.get("input") for b in r.get("content") or [] if b.get("type") == "tool_use"), None) or {}
            lu = {}
            for x in fiche.get("cartes") or []:
                try:
                    k = int(x.get("k")) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= k < len(neuves):
                    n = int(x.get("couleurs") or 0)
                    if x.get("certitude") == "incertaine" or n <= 0:
                        lu[neuves[k]] = None
                    else:
                        lu[neuves[k]] = 5 if x.get("special") else max(1, min(5, n))
            with _verrou:
                c = _cache()
                for u in neuves:
                    c[_cle(u)] = lu.get(u)
                    out[u] = lu.get(u)
                if len(c) > 40000:
                    c = dict(list(c.items())[-30000:])
                p = _chemin_cache()
                with open(p + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(c, f)
                os.replace(p + ".tmp", p)
        except Exception as e:
            print("Patchs (photos) : " + repr(e)[:200], flush=True)
    return out


def ajuster(titre, photo, ventes, photos=True):
    """La carte (titre, photo) et ses ventes [{prix, titre, photo}] -> (ratio a appliquer a la valeur, n de la carte,
    ventes annotees) ; ratio 1.0 si la carte n'est pas une patch ou si on ne sait rien. Le ratio = mediane des prix
    ramenes a la patch de la carte / mediane des prix bruts (la valeur garde sa propre facon d'etre calculee)."""
    if not est_patch(titre) or not ventes:
        return 1.0, None, ventes
    n_c = du_titre(titre)
    lus = {}
    if photos:
        urls = ([photo] if n_c is None and photo else []) + [v.get("photo") for v in ventes if v.get("photo") and du_titre(v.get("titre")) is None]
        lus = compter(urls) if urls else {}
    if n_c is None and photo:
        n_c = lus.get(str(photo))
    out, brut, adj = [], [], []
    for v in ventes:
        n_v = du_titre(v.get("titre"))
        if n_v is None and v.get("photo"):
            n_v = lus.get(str(v.get("photo")))
        p = v.get("prix") or v.get("total")
        f = facteur(n_c, n_v)
        out.append(dict(v, couleurs=n_v, prix_patch=round(p * f, 2) if p else None))
        if p:
            brut.append(p)
            adj.append(p * f)
    if not n_c or not brut:
        return 1.0, n_c, out
    r = statistics.median(adj) / statistics.median(brut)
    return round(max(0.3, min(2.0, r)), 3), n_c, out
