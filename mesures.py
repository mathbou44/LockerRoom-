"""
SLABCOACH - les MESURES de l'examen (3 nov 2026), faites par l'app, pas par l'IA.

Mathieu : « on doit etre meilleur que ca, cherche partout ». Ce qu'on a retenu des methodes publiees (TAG, Ximilar, les
brevets de pre-gradation, l'etude Kiradex sur le centrage, les guides de photo PSA / cardgrade.io) :
  1. CENTRAGE : on mesure de l'arete coupee jusqu'au CADRE IMPRIME (definition PSA), au PIRE point du cote (pas la
     mediane : un cadre penche compte a son pire endroit). Nouveau : un detecteur de PAIRES d'elements imprimes en miroir
     (le meme bord de cadre, la meme fenetre de patch, de chaque cote). Une coupe decentree deplace TOUS les elements
     imprimes du MEME decalage : quand 2 paires ou plus donnent le meme decalage, la mesure est confirmee. Une carte
     dessinee de facon asymetrique (un titre en haut) ne donne pas de paires d'accord : on ne l'invente pas.
  2. COINS et BORDS : le blanchiment est MESURE, en mm2 et en mm (une carte = 63,5 x 88,9 mm) : les pixels pres de
     l'arete nettement plus clairs que la bordure du coin (TAG appelle ca « fray » / « fill »). Et l'ARRONDI d'un coin :
     la surface « mangee » par rapport a un coin carre.
  3. QUALITE DES PHOTOS : resolution (px par mm), nettete (variance du laplacien), reflets (zones brulees), avant de
     juger. Une photo qui ne permet pas de voir n'est pas une « note prudente » : on dit quoi reprendre.
numpy + Pillow. Toutes les fonctions recoivent la carte REDRESSEE (examen.redresser).
"""
import math

try:
    import numpy as np
except ImportError:                        # sans numpy : l'examen marche comme avant (mesures absentes)
    np = None

MM_COURT, MM_LONG = 63.5, 88.9             # format standard d'une carte de sport


def disponible():
    return np is not None


def _arr(carte):
    return np.asarray(carte.convert("RGB"), dtype=np.float32)


# -- 1. centrage par paires en miroir ----------------------------------------------------------------------------------
BANDES = 12


def _lignes(a, cote_px_min, cote_px_max):
    """a : (H, W, 3), lignes VERTICALES. -> [{x, bandes:[...], ext:(rgb), int:(rgb)}] pour les colonnes de cote_px_min a
    cote_px_max depuis la gauche ET depuis la droite (x en px depuis le bord de son cote ; cote 'g' ou 'd')."""
    H, W, _ = a.shape
    h0, h1 = int(H * 0.05), int(H * 0.95)
    bornes = np.linspace(h0, h1, BANDES + 1).astype(int)
    prof = np.stack([a[bornes[i]:bornes[i + 1]].mean(axis=0) for i in range(BANDES)])          # (B, W, 3)
    g = np.zeros((BANDES, W), np.float32)
    g[:, 2:-2] = np.abs(prof[:, 4:] - prof[:, :-4]).sum(axis=2)
    out = []
    for cote in ("g", "d"):
        gg = g if cote == "g" else g[:, ::-1]
        pp = prof if cote == "g" else prof[:, ::-1]
        zone = gg[:, cote_px_min:cote_px_max]
        if zone.size == 0:
            continue
        med = np.median(zone, axis=1, keepdims=True) + 1
        pic = (zone >= 38) & (zone >= 3.0 * med)
        loc = np.zeros_like(pic)
        loc[:, 1:-1] = (zone[:, 1:-1] >= zone[:, :-2]) & (zone[:, 1:-1] >= zone[:, 2:])
        pic &= loc
        # une ligne = un pic dans plusieurs bandes CONSECUTIVES a la meme position (+- 2 px)
        dil = pic.copy()
        for k in (1, 2):
            dil[:, k:] |= pic[:, :-k]
            dil[:, :-k] |= pic[:, k:]
        sup = dil.sum(axis=0)
        xs = [i for i in range(len(sup)) if sup[i] >= 4 and (i == 0 or sup[i] >= sup[i - 1]) and (i + 1 == len(sup) or sup[i] >= sup[i + 1])]
        garde = []
        for i in xs:
            if garde and i - garde[-1] <= 3:
                if sup[i] > sup[garde[-1]]:
                    garde[-1] = i
                continue
            garde.append(i)
        for i in garde:
            bandes = [b for b in range(BANDES) if dil[b, i]]
            # la plus longue suite de bandes consecutives
            run, best, cur = [], [], []
            for b in range(BANDES):
                if b in bandes:
                    cur.append(b)
                    if len(cur) > len(best):
                        best = cur[:]
                else:
                    cur = []
            if len(best) < 4:
                continue
            x = i + cote_px_min
            e = pp[best, max(0, x - 10):max(1, x - 4)].mean(axis=(0, 1))
            n = pp[best, x + 4:x + 10].mean(axis=(0, 1))
            out.append({"cote": cote, "x": int(x), "bandes": best, "ext": e, "int": n, "force": float(zone[best, i].mean())})
    return out


def _pos_bande(a, cote, x, b, tol=4):
    """La position exacte de la ligne dans UNE bande (pour le pire point)."""
    H, W, _ = a.shape
    h0, h1 = int(H * 0.05), int(H * 0.95)
    bornes = np.linspace(h0, h1, BANDES + 1).astype(int)
    p = a[bornes[b]:bornes[b + 1]].mean(axis=0)
    if cote == "d":
        p = p[::-1]
    lo, hi = max(2, x - tol), min(W - 3, x + tol + 1)
    g = np.abs(p[lo + 2:hi + 2] - p[lo - 2:hi - 2]).sum(axis=1)
    return lo + int(np.argmax(g)) if g.size else x


def _dcoul(c1, c2):
    """Distance de couleur qui tolere l'eclairage : la teinte (rgb normalise) compte, la luminosite un peu (une dorure
    brille plus d'un cote que de l'autre sur une photo)."""
    s1, s2 = float(c1.sum()) + 1, float(c2.sum()) + 1
    teinte = float(np.linalg.norm(c1 / s1 - c2 / s2)) * 300
    return teinte + abs(math.log(s1 / s2)) * 40


def _axe(a):
    """Le centrage d'un axe (lignes verticales de a) -> dict ou None."""
    H, W, _ = a.shape
    cand = _lignes(a, max(4, int(W * 0.012)), int(W * 0.46))
    G = [c for c in cand if c["cote"] == "g"]
    D = [c for c in cand if c["cote"] == "d"]
    paires = []
    for l in G:
        for r in D:
            dl, dr = l["x"], r["x"]
            if max(dl, dr) / (dl + dr) > 0.80:
                continue
            sl, sr = set(l["bandes"]), set(r["bandes"])
            iou = len(sl & sr) / len(sl | sr)
            if iou < 0.5:
                continue
            de, di = _dcoul(l["ext"], r["ext"]), _dcoul(l["int"], r["int"])
            ce, cr = _dcoul(l["ext"], l["int"]), _dcoul(r["ext"], r["int"])
            # la meme couleur d'un cote de la ligne (la bordure, le cadre : a l'exterieur OU a l'interieur ; l'autre cote peut
            # etre la photo, differente a gauche et a droite) et un vrai contraste
            m = min(de, di)
            if m > 45 or min(ce, cr) < 25:
                continue
            score = iou + (1 - m / 45) + 0.5 * (1 - min(max(de, di), 110) / 110)
            paires.append({"l": l, "r": r, "dl": dl, "dr": dr, "o": (dl - dr) / 2.0, "score": score,
                           "bandes": sorted(sl & sr)})
    if not paires:
        return None
    # chaque ligne dans une seule paire : les meilleures d'abord
    paires.sort(key=lambda p: -p["score"])
    pris, uniques = set(), []
    for p in paires:
        k1, k2 = ("g", p["l"]["x"]), ("d", p["r"]["x"])
        if k1 in pris or k2 in pris:
            continue
        pris |= {k1, k2}
        uniques.append(p)
    # le consensus : les paires qui donnent le meme decalage (une coupe deplace tout de la meme facon)
    tol = max(4.0, W * 0.006)
    groupes = []
    for p in sorted(uniques, key=lambda p: p["dl"] + p["dr"]):         # les plus a l'exterieur d'abord
        for gp in groupes:
            if abs(gp[0]["o"] - p["o"]) <= tol:
                gp.append(p)
                break
        else:
            groupes.append([p])
    groupes.sort(key=lambda gp: (-len(gp), gp[0]["dl"] + gp[0]["dr"]))
    gp = groupes[0]
    ext = gp[0]                                                         # la paire la plus a l'exterieur du groupe
    # le PIRE point de cette paire, bande par bande (un cadre penche)
    pires = []
    for b in ext["bandes"]:
        xl = _pos_bande(a, "g", ext["dl"], b)
        xr = _pos_bande(a, "d", ext["dr"], b)
        if xl + xr:
            pires.append((max(xl, xr) / (xl + xr), xl, xr))
    pire = max(pires) if pires else (max(ext["dl"], ext["dr"]) / (ext["dl"] + ext["dr"]), ext["dl"], ext["dr"])
    g_ = round(100 * pire[0])
    # une VRAIE bordure (une bande unie entre l'arete et la ligne, des deux cotes) : un decentrage fort y est reel ; un
    # element de design (fenetre, bande de titre) peut etre asymetrique par dessin : au-dessus de 60/40, a verifier
    def unie(cote, x):
        if x < 8:
            return False
        z = a[int(H * 0.3):int(H * 0.7), 3:x - 3] if cote == "g" else a[int(H * 0.3):int(H * 0.7), W - x + 3:W - 3]
        return bool(z.size) and float(z.reshape(-1, 3).std(axis=0).mean()) < 20
    bordure = unie("g", ext["dl"]) and unie("d", ext["dr"])
    autres = [p for gp2 in groupes[1:] for p in gp2]
    fiab = "haute" if len(gp) >= 2 else "moyenne" if g_ <= 60 and not autres else "faible"
    return {"ratio": f"{g_}/{100 - g_}", "a": int(pire[1]), "b": int(pire[2]), "l": ext["dl"] / W, "r": ext["dr"] / W,
            "paires": len(gp), "contredit": len(autres), "fiabilite": fiab, "bordure": bordure,
            "a_verifier": bool(g_ > 60 and not bordure),
            "reperes": [{"a": p["dl"] / W, "b": p["dr"] / W} for p in gp][:4]}


def centrage(carte):
    """-> {"gd": {...} | None, "hb": {...} | None} : ratio au pire point, la paire de reperes (fractions), la fiabilite."""
    if np is None or carte is None:
        return None
    a = _arr(carte)
    gd = _axe(a)
    hb = _axe(np.ascontiguousarray(a.transpose(1, 0, 2)))
    if hb:                                                              # l / r de l'axe transpose = haut / bas
        hb["t"], hb["b_"] = hb.pop("l"), hb.pop("r")
    return {"gd": gd, "hb": hb}


# -- 2. coins et bords : le blanchiment MESURE ---------------------------------------------------------------------------
def _lum(x):
    return x[..., 0] * 0.299 + x[..., 1] * 0.587 + x[..., 2] * 0.114


def _sat(x):
    mx, mn = x.max(axis=-1), x.min(axis=-1)
    return (mx - mn) / (mx + 1)


def usure(carte_marge, marge):
    """carte_marge : la carte redressee AVEC sa marge de fond (examen.redresser(im, q, marge)). -> {"coins": {nom: {...}},
    "bords": {nom: {...}}, "px_mm": float} ; None si pas mesurable. Le blanc compte : plus clair que la bordure de ce
    coin de 45 (luminance) et peu colore, dans les 1,2 mm de l'arete ; le fond autour doit etre plus sombre que le blanc."""
    if np is None or carte_marge is None:
        return None
    a = _arr(carte_marge)
    Hm, Wm, _ = a.shape
    # la carte dans l'image avec marge
    mx, my = int(round(Wm * marge / (1 + 2 * marge))), int(round(Hm * marge / (1 + 2 * marge)))
    c = a[my:Hm - my, mx:Wm - mx]
    H, W, _ = c.shape
    court = min(W, H)
    px_mm = court / MM_COURT
    L, S = _lum(a), _sat(a)
    fond = float(np.median(np.concatenate([L[:max(2, my - 2)].ravel(), L[Hm - max(2, my - 2):].ravel()])))
    k = max(3, int(round(1.2 * px_mm)))                       # la bande de 1,2 mm le long de l'arete
    out = {"px_mm": round(px_mm, 1), "fond_clair": fond > 170, "coins": {}, "bords": {}}
    if fond > 170:                                             # fond blanc : le blanc d'usure ne se distingue pas du fond
        return out
    def blanc(zone_rgb, ref_l):
        l, s = _lum(zone_rgb), _sat(zone_rgb)
        return (l > min(250, ref_l + 45)) & (s < 0.22)
    t = max(k * 3, int(round(4 * px_mm)))                     # un coin : 4 mm x 4 mm
    coins = {"haut-gauche": (my, mx, 1, 1), "haut-droit": (my, Wm - mx - t, 1, -1),
             "bas-droit": (Hm - my - t, Wm - mx - t, -1, -1), "bas-gauche": (Hm - my - t, mx, -1, 1)}
    for nom, (y0, x0, sy, sx) in coins.items():
        z = a[y0:y0 + t, x0:x0 + t]
        if z.shape[0] < t or z.shape[1] < t:
            continue
        # la bordure de reference : l'anneau de 2 a 4 mm du coin
        yy, xx = np.mgrid[0:t, 0:t]
        dy = yy if sy == 1 else (t - 1 - yy)
        dx = xx if sx == 1 else (t - 1 - xx)
        bord = np.minimum(dy, dx)
        ref = z[(bord >= 2 * px_mm) & (bord < 4 * px_mm)]
        if not ref.size:
            continue
        ref_l = float(np.median(_lum(ref)))
        if ref_l > 205:                                       # bordure blanche : le blanchiment n'a pas de contraste
            out["coins"][nom] = {"mesurable": False, "raison": "bordure claire"}
            continue
        m = blanc(z, ref_l) & (bord < k)
        aire = float(m.sum()) / (px_mm ** 2)
        out["coins"][nom] = {"mesurable": True, "blanc_mm2": round(aire, 2), "ref_l": round(ref_l)}
    bords = {"haut": a[my:my + k, mx + t:Wm - mx - t], "bas": a[Hm - my - k:Hm - my, mx + t:Wm - mx - t][::-1],
             "gauche": a[my + t:Hm - my - t, mx:mx + k].transpose(1, 0, 2),
             "droit": a[my + t:Hm - my - t, Wm - mx - k:Wm - mx].transpose(1, 0, 2)[::-1]}
    for nom, z in bords.items():
        if z.size == 0:
            continue
        ref_z = {"haut": a[my + k:my + 3 * k, mx + t:Wm - mx - t], "bas": a[Hm - my - 3 * k:Hm - my - k, mx + t:Wm - mx - t],
                 "gauche": a[my + t:Hm - my - t, mx + k:mx + 3 * k], "droit": a[my + t:Hm - my - t, Wm - mx - 3 * k:Wm - mx - k]}[nom]
        ref_l = float(np.median(_lum(ref_z)))
        if ref_l > 205:
            out["bords"][nom] = {"mesurable": False, "raison": "bordure claire"}
            continue
        m = blanc(z, ref_l)
        col = m.any(axis=0)                                   # une colonne le long de l'arete touchee
        longueur = float(col.sum()) / px_mm
        # les points : suites de colonnes touchees
        pts, prev = 0, False
        for v in col:
            if v and not prev:
                pts += 1
            prev = bool(v)
        out["bords"][nom] = {"mesurable": True, "blanc_mm": round(longueur, 1), "points": pts, "ref_l": round(ref_l)}
    return out


# -- 3. la qualite de la photo ------------------------------------------------------------------------------------------
def qualite(carte, px_mm=None):
    """La carte redressee (+ px_mm : la resolution NATIVE de la photo, la carte redressee est agrandie) -> {px_mm, nettete,
    reflets_pct, reflets: [zones], net: bool, a_reprendre: [messages]}."""
    if np is None or carte is None:
        return None
    a = _arr(carte)
    H, W, _ = a.shape
    px_mm = px_mm or min(W, H) / MM_COURT
    L = _lum(a)
    lap = L[1:-1, 1:-1] * -4 + L[:-2, 1:-1] + L[2:, 1:-1] + L[1:-1, :-2] + L[1:-1, 2:]
    nettete = float(lap.var())
    brule = (L > 248) & (_sat(a) < 0.12)
    pct = float(brule.mean()) * 100
    zones = []
    for nom, (ys, xs) in {"haut-gauche": (slice(0, H // 4), slice(0, W // 4)), "haut-droit": (slice(0, H // 4), slice(3 * W // 4, W)),
                          "bas-gauche": (slice(3 * H // 4, H), slice(0, W // 4)), "bas-droit": (slice(3 * H // 4, H), slice(3 * W // 4, W)),
                          "centre": (slice(H // 4, 3 * H // 4), slice(W // 4, 3 * W // 4))}.items():
        if float(brule[ys, xs].mean()) > 0.02:
            zones.append(nom)
    msgs = []
    if px_mm < 14:
        msgs.append("photo trop petite pour les coins et les bords : approche le téléphone (la carte doit remplir l'écran)")
    if nettete < 40:
        msgs.append("photo floue : tiens le téléphone immobile et touche la carte à l'écran pour faire le focus")
    if zones:
        msgs.append("reflet sur " + ", ".join(zones) + " : incline un peu la carte ou éloigne la lumière (pas de flash direct)")
    return {"px_mm": round(px_mm, 1), "nettete": round(nettete), "reflets_pct": round(pct, 2), "reflets": zones,
            "net": nettete >= 40, "assez_grande": px_mm >= 14, "a_reprendre": msgs}
