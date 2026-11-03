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
            eb = pp[best, max(0, x - 10):max(1, x - 4)].mean(axis=1)              # (bandes, 3)
            nb = pp[best, x + 4:x + 10].mean(axis=1)
            # 3 nov 2026 (pratique : damier orange de la Suzuki) : un MOTIF repete (damier, rayures) fait des lignes partout,
            # en miroir, avec le meme decalage. Un vrai cadre a au moins un cote UNI tout le long de la ligne
            if nb.size == 0 or min(float(eb.std(axis=0).mean()), float(nb.std(axis=0).mean())) > 20:
                continue
            e, n = eb.mean(axis=0), nb.mean(axis=0)
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


def _claire(zone):
    """Une bordure claire ou grise (blanc, argent, gris pale) : le blanchiment ne s'y voit pas sur une photo."""
    z = zone.reshape(-1, 3)
    l, s = float(np.median(_lum(z))), float(np.median(_sat(z)))
    return l > 150 and (s < 0.30 or l > 205)


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
    # 3 nov 2026 (pratique sur 12 vraies photos : holo, foil, presentoir) : une bordure qui BRILLE (holo, foil, reflets
    # du presentoir) a des points clairs partout, pas seulement a l'arete : ce n'est pas du blanchiment. On compare la
    # bande de l'arete (0 a 0,6 mm) a une bande interieure (1,5 a 3 mm) : brillante a l'interieur -> pas mesurable
    e_ = max(2, int(round(0.6 * px_mm)))
    i0, i1 = int(round(1.5 * px_mm)), int(round(3 * px_mm))
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
        if _claire(ref):                                      # bordure claire : le blanchiment n'a pas de contraste
            out["coins"][nom] = {"mesurable": False, "raison": "bordure claire"}
            continue
        # le contour doit tomber sur la vraie arete : juste dehors (le fond) doit trancher avec la bordure, des 2 cotes
        e2 = max(2, int(0.6 * px_mm))
        yh = (y0 - e2, y0) if sy == 1 else (y0 + t, y0 + t + e2)
        xh = (x0 - e2, x0) if sx == 1 else (x0 + t, x0 + t + e2)
        dehors_h = a[max(0, yh[0]):max(0, yh[1]), x0:x0 + t]
        dehors_v = a[y0:y0 + t, max(0, xh[0]):max(0, xh[1])]
        if not dehors_h.size or not dehors_v.size or min(abs(float(np.median(_lum(dehors_h))) - ref_l),
                                                         abs(float(np.median(_lum(dehors_v))) - ref_l)) < 25:
            out["coins"][nom] = {"mesurable": False, "raison": "contour incertain"}
            continue
        interieur = blanc(z, ref_l) & (bord >= i0) & (bord < i1)
        if float(interieur.mean() if interieur.size else 0) * t * t / max(1, ((bord >= i0) & (bord < i1)).sum()) > 0.015:
            out["coins"][nom] = {"mesurable": False, "raison": "bordure brillante"}
            continue
        # l'arete coupee accroche la lumiere (1 ou 2 px de liseré clair, sur toutes les cartes) : on ne la compte pas
        m = blanc(z, ref_l) & (bord < k) & (bord >= max(2, int(round(0.15 * px_mm))))
        aire = float(m.sum()) / (px_mm ** 2)
        out["coins"][nom] = {"mesurable": True, "blanc_mm2": round(aire, 2), "ref_l": round(ref_l)}
    # un presentoir transparent devant le bas de la carte : des reflets clairs juste SOUS l'arete du bas (dans le fond)
    sous = L[Hm - my + 2:Hm - 2, mx:Wm - mx]
    presentoir = bool(sous.size) and float((sous > fond + 45).mean()) > 0.04
    if presentoir:
        out["presentoir"] = True
        for nom in ("bas-gauche", "bas-droit"):
            if (out["coins"].get(nom) or {}).get("mesurable"):
                out["coins"][nom] = {"mesurable": False, "raison": "presentoir"}
    bords = {"haut": a[my:my + k, mx + t:Wm - mx - t], "bas": a[Hm - my - k:Hm - my, mx + t:Wm - mx - t][::-1],
             "gauche": a[my + t:Hm - my - t, mx:mx + k].transpose(1, 0, 2),
             "droit": a[my + t:Hm - my - t, Wm - mx - k:Wm - mx].transpose(1, 0, 2)[::-1]}
    for nom, z in bords.items():
        if z.size == 0:
            continue
        if nom == "bas" and presentoir:
            out["bords"][nom] = {"mesurable": False, "raison": "presentoir"}
            continue
        ref_z = {"haut": a[my + k:my + 3 * k, mx + t:Wm - mx - t], "bas": a[Hm - my - 3 * k:Hm - my - k, mx + t:Wm - mx - t],
                 "gauche": a[my + t:Hm - my - t, mx + k:mx + 3 * k], "droit": a[my + t:Hm - my - t, Wm - mx - 3 * k:Wm - mx - k]}[nom]
        ref_l = float(np.median(_lum(ref_z)))
        if _claire(ref_z):
            out["bords"][nom] = {"mesurable": False, "raison": "bordure claire"}
            continue
        zi = {"haut": a[my + i0:my + i1, mx + t:Wm - mx - t], "bas": a[Hm - my - i1:Hm - my - i0, mx + t:Wm - mx - t],
              "gauche": a[my + t:Hm - my - t, mx + i0:mx + i1], "droit": a[my + t:Hm - my - t, Wm - mx - i1:Wm - mx - i0]}[nom]
        if zi.size and float(blanc(zi, ref_l).mean()) > 0.015:
            out["bords"][nom] = {"mesurable": False, "raison": "bordure brillante"}
            continue
        m = blanc(z[:e_], ref_l)
        # une colonne est touchee si le blanc entre d'au moins 0,25 mm (le liseré de l'arete, 1-2 px, ne compte pas)
        col = m.sum(axis=0) >= max(3, int(round(0.25 * px_mm)))
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
    brule = (a.min(axis=2) >= 250)                            # brule : les 3 couleurs au maximum
    pct = float(brule.mean()) * 100
    zones = []
    for nom, (ys, xs) in {"haut-gauche": (slice(0, H // 4), slice(0, W // 4)), "haut-droit": (slice(0, H // 4), slice(3 * W // 4, W)),
                          "bas-gauche": (slice(3 * H // 4, H), slice(0, W // 4)), "bas-droit": (slice(3 * H // 4, H), slice(3 * W // 4, W)),
                          "centre": (slice(H // 4, 3 * H // 4), slice(W // 4, 3 * W // 4))}.items():
        # un reflet tranche sur sa zone ; un fond blanc imprime (bordure blanche) n'est pas un reflet
        if float(brule[ys, xs].mean()) > 0.02 and float(np.median(L[ys, xs])) < 215:
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


# -- 4. trouver la carte dans la photo (sans contour du telephone) ------------------------------------------------------
def trouver_carte(im):
    """La carte sur un fond (tapis, presentoir) : chaque rangee est comparee a son propre fond (les 4 % de gauche et de
    droite, que la carte ne touche pas) ; la carte = les colonnes et les rangees ou plus de la moitie des pixels
    tranchent. Un presentoir transparent (etroit) ne compte pas. -> quad 0..1000 (haut-gauche, sens horaire) ou None."""
    if np is None or im is None:
        return None
    k = 900 / max(im.size)
    p = im.convert("RGB").resize((max(1, int(im.size[0] * k)), max(1, int(im.size[1] * k))))
    a = _arr(p)
    H, W, _ = a.shape
    b = max(4, int(W * 0.04))
    fond = np.median(np.concatenate([a[:, :b], a[:, -b:]], axis=1), axis=1)            # (H, 3) : le fond de chaque rangee
    d = np.abs(a - fond[:, None, :]).sum(axis=2)
    m = d > 60
    cols = m.mean(axis=0)
    rows = m.mean(axis=1)
    def bornes(v, seuil):
        idx = np.where(v > seuil)[0]
        if idx.size < 10:
            return None
        # la plus longue suite (la carte), pas une tache isolee
        coupes = np.where(np.diff(idx) > 3)[0]
        debuts = np.concatenate([[0], coupes + 1])
        fins = np.concatenate([coupes, [idx.size - 1]])
        j = int(np.argmax(fins - debuts))
        return int(idx[debuts[j]]), int(idx[fins[j]])
    bx = bornes(cols, 0.35)
    if not bx:
        return None
    by = bornes(m[:, bx[0]:bx[1] + 1].mean(axis=1), 0.6)
    if not by:
        return None
    x0, x1 = bx
    y0, y1 = by
    if (x1 - x0) < W * 0.15:
        return None
    # le bas (ou le haut) peut se confondre avec le fond (carte grise sur un fond gris, presentoir devant) : le format
    # d'une carte (88,9 x 63,5 mm) donne deux bas possibles ; on garde la ligne horizontale la plus franche
    L = _lum(a)
    lc = L[:, x0 + (x1 - x0) // 6:x1 - (x1 - x0) // 6].mean(axis=1)
    g = np.zeros(H)
    g[2:-2] = np.abs(lc[4:] - lc[:-4])
    w = x1 - x0
    # le haut et le bas = la PAIRE de lignes horizontales franches dont l'ecart a le format d'une carte (debout ou couchee)
    pics = [i for i in range(3, H - 3) if g[i] >= g[i - 1] and g[i] >= g[i + 1] and g[i] > 6]
    pics = sorted(pics, key=lambda i: -g[i])[:40]
    meilleur, sc = None, -1.0
    for k in (MM_LONG / MM_COURT, MM_COURT / MM_LONG):
        h = w * k
        for yt in pics:
            yb_cand = [yb for yb in pics if abs((yb - yt) - h) <= 0.035 * h]
            if not yb_cand:
                continue
            yb = max(yb_cand, key=lambda i: g[i])
            v = g[yt] + g[yb] + (8 if abs(yt - y0) < H * 0.02 else 0) + (8 if abs(yb - y1) < H * 0.02 else 0)
            if v > sc:
                meilleur, sc = (yt, yb), v
    if meilleur:
        y0, y1 = meilleur
    if (y1 - y0) < H * 0.15:
        return None
    f = lambda x, n: max(0, min(1000, round(x / n * 1000)))
    return [[f(x0, W), f(y0, H)], [f(x1 + 1, W), f(y0, H)], [f(x1 + 1, W), f(y1 + 1, H)], [f(x0, W), f(y1 + 1, H)]]


def bordure_unie(carte, axe, a, b):
    """La bande entre l'arete et la ligne retenue est-elle une vraie bordure (unie) des deux cotes ? a, b en fraction.
    Un decentrage fort mesure sur autre chose qu'une bordure peut etre le DESSIN de la carte (un logo plus haut)."""
    if np is None or carte is None or a is None or b is None:
        return False
    x = _arr(carte)
    if axe == "hb":
        x = x.transpose(1, 0, 2)
    H, W, _ = x.shape
    la, lb = int(a * W), int(b * W)
    if la < 8 or lb < 8:
        return False
    z1, z2 = x[int(H * .3):int(H * .7), 3:la - 3], x[int(H * .3):int(H * .7), W - lb + 3:W - 3]
    return bool(z1.size and z2.size) and float(z1.reshape(-1, 3).std(axis=0).mean()) < 20 and float(z2.reshape(-1, 3).std(axis=0).mean()) < 20


# -- 5. la SILHOUETTE : coins arrondis et encoches, mesures sur la forme (toutes couleurs de bordure) ---------------------
# 3 nov 2026 (Mathieu : « continue de rendre l'analyseur meilleur ») : le blanchiment par la couleur ne marche pas sur les
# bordures claires, argent ou holo. La FORME de la carte, elle, se lit sur n'importe quelle bordure tant que le fond tranche
# (tapis fonce) : l'arete de chaque cote est suivie pixel par pixel, une droite est ajustee (robuste) ; un creux sous la
# droite = une encoche ou une ebrechure (profondeur et longueur en mm). Un coin = la surface qui manque par rapport au coin
# carre que dessinent les deux droites (mm2) ; on compare aussi les 4 coins entre eux (un coin use est plus rond que les
# autres, quelle que soit la coupe d'usine).
def _arete(prof_l, ref_bord, ref_fond):
    """Un profil de luminance perpendiculaire a l'arete (du fond vers la carte) -> position sous-pixel du passage a mi-chemin."""
    mi = (ref_bord + ref_fond) / 2.0
    s = 1.0 if ref_bord > ref_fond else -1.0
    v = (prof_l - mi) * s
    idx = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
    if not idx.size:
        return None
    i = int(idx[0])
    d = v[i + 1] - v[i]
    return i + (-v[i] / d if d else 0.5)


def silhouette(carte_marge, marge):
    """-> {"px_mm", "cotes": {nom: {"mesurable", "encoches": [{pos_mm, profondeur_mm, longueur_mm}], "rugosite_mm"}},
    "coins": {nom: {"mesurable", "manque_mm2", "relatif"}}} ; None si pas mesurable.
    La carte se distingue du fond par sa COULEUR (distance au fond), pas seulement par sa luminosite : un vert fonce pres
    d'un coin n'est pas du fond noir. Un echantillon dont le fond n'est pas le fond (presentoir transparent devant la carte,
    reflet) est ecarte."""
    if np is None or carte_marge is None:
        return None
    a = _arr(carte_marge)
    Hm, Wm, _ = a.shape
    mx, my = int(round(Wm * marge / (1 + 2 * marge))), int(round(Hm * marge / (1 + 2 * marge)))
    W, H = Wm - 2 * mx, Hm - 2 * my
    px_mm = min(W, H) / MM_COURT
    r = max(4, int(round(0.9 * px_mm)))
    out = {"px_mm": round(px_mm, 1), "cotes": {}, "coins": {},
           "dims_mm": {"haut": round(W / px_mm, 1), "bas": round(W / px_mm, 1), "gauche": round(H / px_mm, 1), "droit": round(H / px_mm, 1)}}
    # le fond est lu LOCALEMENT, sur chaque profil (l'eclairage du tapis varie le long d'un cote)
    def bande(nom):
        if nom == "haut":
            return a[max(0, my - r):my + r, mx:Wm - mx].transpose(1, 0, 2), my - max(0, my - r)
        if nom == "bas":
            return a[Hm - my - r:min(Hm, Hm - my + r), mx:Wm - mx][::-1].transpose(1, 0, 2), min(Hm, Hm - my + r) - (Hm - my)
        if nom == "gauche":
            return a[my:Hm - my, max(0, mx - r):mx + r], mx - max(0, mx - r)
        return a[my:Hm - my, Wm - mx - r:min(Wm, Wm - mx + r)][:, ::-1], min(Wm, Wm - mx + r) - (Wm - mx)
    PR, BG = {}, {}
    for nom in ("haut", "droit", "bas", "gauche"):
        B, x0 = bande(nom)
        if B.shape[1] < 6:
            continue
        ext = B[:, :max(2, x0 - r // 2)]
        bg = np.median(ext, axis=1)                                   # (n, 3) : le fond de chaque profil
        PR[nom] = (np.sqrt(((B - bg[:, None, :]) ** 2).sum(axis=2)), x0, ext.std(axis=1).mean(axis=1))
        BG[nom] = bg
    # un presentoir transparent sous la carte : des reflets clairs juste sous l'arete du bas
    Lm = _lum(a)
    sous = Lm[min(Hm - 2, Hm - my + r):Hm - 1, mx:Wm - mx]
    fond_bas = float(np.median(Lm[:max(2, my - r), mx:Wm - mx])) if my - r > 2 else float(np.median(sous)) if sous.size else 0.0
    presentoir = bool(sous.size) and float((sous > fond_bas + 45).mean()) > 0.04
    out["presentoir"] = presentoir
    lignes = {}
    for nom in ("haut", "droit", "bas", "gauche"):
        if nom not in PR:
            continue
        P, x0, et = PR[nom]
        if P.shape[0] < 50:
            continue
        carte = float(np.median(P[:, min(P.shape[1] - 2, x0 + r // 2):]))
        if carte < 35:
            out["cotes"][nom] = {"mesurable": False, "raison": "fond qui ne tranche pas"}
            continue
        n = P.shape[0]
        # le fond est bien du fond : uni (pas les aretes d'un presentoir transparent, pas un reflet), et la carte tranche
        # sur ce fond a cet endroit ; on ecarte aussi 1,5 mm autour de chaque echantillon douteux
        cloc = np.median(P[:, min(P.shape[1] - 2, x0 + r // 2):], axis=1)
        propre = (et < max(8.0, float(np.median(et)) * 2.5)) & (cloc > 45)
        dil = max(1, int(round(1.5 * px_mm)))
        mauvais = ~propre
        for dd in range(1, dil + 1):
            mauvais[dd:] |= ~propre[:-dd]
            mauvais[:-dd] |= ~propre[dd:]
        propre = ~mauvais
        if presentoir and nom in ("gauche", "droit"):
            propre[int(0.65 * len(propre)):] = False            # le presentoir cache le bas des cotes
        if presentoir and nom == "bas":
            out["cotes"][nom] = {"mesurable": False, "raison": "presentoir devant l'arete"}
            continue
        y = np.full(n, np.nan)
        for k in range(n):
            if propre[k]:
                v = _arete(P[k], float(cloc[k]), 0.0)            # le milieu entre CE fond et CETTE carte (une zone foncee de la carte)
                if v is not None and v < P.shape[1] - 2:
                    y[k] = v
        t = np.arange(n, dtype=float)
        ok = ~np.isnan(y)
        m = ok & (t > 0.06 * n) & (t < 0.94 * n)
        if m.sum() < 0.5 * n:
            out["cotes"][nom] = {"mesurable": False, "raison": "presentoir ou reflet devant l'arete" if propre.mean() < 0.7 else "arete mal lue"}
            continue
        tt_, yy = t[m], y[m]
        for _ in range(3):
            A = np.vstack([tt_, np.ones_like(tt_)]).T
            k_, b_ = np.linalg.lstsq(A, yy, rcond=None)[0]
            res = yy - (k_ * tt_ + b_)
            s_ = np.median(np.abs(res)) * 1.4826 + 0.3
            g = np.abs(res) < 3 * s_
            if g.all():
                break
            tt_, yy = tt_[g], yy[g]
        lignes[nom] = (k_, b_, n)
        res_all = y - (k_ * t + b_)
        rug = float(np.nanmedian(np.abs(res_all[m]))) / px_mm
        seuil, lmin = 0.12 * px_mm, max(3, int(round(0.25 * px_mm)))
        creux = (np.nan_to_num(res_all, nan=0.0) > seuil) & m & (np.nan_to_num(res_all, nan=0.0) < 0.75 * r)
        enc, i = [], 0
        while i < n:
            if creux[i]:
                j = i
                while j + 1 < n and creux[j + 1]:
                    j += 1
                if j - i + 1 >= lmin:
                    enc.append({"pos_mm": round((i + j) / 2 / px_mm, 1), "profondeur_mm": round(float(np.nanmax(res_all[i:j + 1])) / px_mm, 2),
                                "longueur_mm": round((j - i + 1) / px_mm, 1)})
                i = j + 1
            else:
                i += 1
        out["cotes"][nom] = {"mesurable": True, "encoches": sorted(enc, key=lambda e: -e["profondeur_mm"])[:6], "rugosite_mm": round(rug, 3),
                             "lu_pct": round(100 * float(m.sum()) / max(1, int(((t > 0.06 * n) & (t < 0.94 * n)).sum())))}
    def droite_img(nom):
        k_, b_, n = lignes[nom]
        if nom == "haut":
            return lambda tt: (mx + tt, max(0, my - r) + (k_ * tt + b_))
        if nom == "bas":
            return lambda tt: (mx + tt, min(Hm, Hm - my + r) - (k_ * tt + b_))
        if nom == "gauche":
            return lambda tt: (max(0, mx - r) + (k_ * tt + b_), my + tt)
        return lambda tt: (min(Wm, Wm - mx + r) - (k_ * tt + b_), my + tt)
    def inter(nom1, nom2):
        f1, f2 = droite_img(nom1), droite_img(nom2)
        p1, p2 = np.array(f1(0.0)), np.array(f1(float(lignes[nom1][2])))
        p3, p4 = np.array(f2(0.0)), np.array(f2(float(lignes[nom2][2])))
        d1, d2 = p2 - p1, p4 - p3
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:
            return None
        u = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
        return p1 + u * d1
    paires = {"haut-gauche": ("haut", "gauche"), "haut-droit": ("haut", "droit"), "bas-droit": ("bas", "droit"), "bas-gauche": ("bas", "gauche")}
    s = int(round(2.5 * px_mm))
    manques = {}
    for nom, (c1, c2) in paires.items():
        if presentoir and nom.startswith("bas"):
            out["coins"][nom] = {"mesurable": False, "raison": "presentoir"}
            continue
        if c1 not in lignes or c2 not in lignes:
            out["coins"][nom] = {"mesurable": False, "raison": "aretes pas lues"}
            continue
        p = inter(c1, c2)
        if p is None:
            continue
        cx, cy = p
        sx = 1 if "gauche" in nom else -1
        sy = 1 if "haut" in nom else -1
        x0, x1 = (int(round(cx)), int(round(cx)) + s) if sx == 1 else (int(round(cx)) - s, int(round(cx)))
        y0, y1 = (int(round(cy)), int(round(cy)) + s) if sy == 1 else (int(round(cy)) - s, int(round(cy)))
        if x0 < 0 or y0 < 0 or x1 > Wm or y1 > Hm:
            continue
        # le fond du coin : la zone juste dehors, en diagonale (au-dela de la pointe)
        gx0, gx1 = (max(0, x0 - s), x0) if sx == 1 else (x1, min(Wm, x1 + s))
        gy0, gy1 = (max(0, y0 - s), y0) if sy == 1 else (y1, min(Hm, y1 + s))
        gz = a[gy0:gy1, gx0:gx1].reshape(-1, 3)
        if gz.size < 30:
            continue
        bgc = np.median(gz, axis=0)
        d = np.sqrt(((a[y0:y1, x0:x1] - bgc[None, None, :]) ** 2).sum(axis=2))
        ref = float(np.median(d[d > 35])) if (d > 35).any() else 0.0
        if ref < 35:
            out["coins"][nom] = {"mesurable": False, "raison": "fond qui ne tranche pas"}
            continue
        carte_px = d > min(30.0, ref / 2)
        manque = (d.size - int(carte_px.sum())) / (px_mm ** 2)
        manques[nom] = manque
        out["coins"][nom] = {"mesurable": True, "manque_mm2": round(manque, 2)}
    if len(manques) >= 3:
        med = float(np.median(list(manques.values())))
        for nom, v in manques.items():
            out["coins"][nom]["relatif"] = round(v - med, 2)
    return out


# -- 6. la SURFACE : relief en lumiere rasante, et difference entre deux eclairages ----------------------------------------
# 3 nov 2026 (recherche : inspection de surfaces brillantes a deux sources de lumiere, brevet US 11 169 095 ; lumiere
# rasante 5 a 15 degres des guides de pre-gradation) : sur une surface lisse, les deux eclairages donnent la meme image ;
# une rayure ou une bosse incline localement la surface et renvoie la lumiere d'un cote seulement : la DIFFERENCE des
# deux photos les fait ressortir, l'impression (identique dans les deux) s'efface. Une seule photo rasante : on enleve
# l'eclairage lent (passe-haut) et on renforce le contraste local.
def _carte_plate(im, cote=1400):
    import examen
    q = trouver_carte(im)
    if not q:
        return None
    q = examen.affiner_quad(im, q, 0.03)
    c = examen.redresser(im, q)
    return c.resize((cote, int(round(cote * c.size[1] / c.size[0])))) if c is not None and c.size[0] >= c.size[1] else (
        c.resize((int(round(cote * c.size[0] / c.size[1])), cote)) if c is not None else None)


def _passe_haut(g, rayon=18):
    from PIL import Image, ImageFilter
    im = Image.fromarray(np.clip(g, 0, 255).astype("uint8"))
    flou = np.asarray(im.filter(ImageFilter.GaussianBlur(rayon)), dtype=np.float32)
    return g - flou


def _vers_image(v, gain=4.0):
    from PIL import Image
    return Image.fromarray(np.clip(128 + gain * v, 0, 255).astype("uint8"))


def relief(im):
    """Une photo en lumiere rasante -> l'image du relief (la carte a plat, passe-haut, contraste x4) ou None."""
    if np is None:
        return None
    c = _carte_plate(im)
    if c is None:
        return None
    g = _lum(_arr(c))
    return _vers_image(_passe_haut(g), 2.5)


def difference_eclairages(im1, im2):
    """Deux photos, la lampe de chaque cote -> l'image de leur difference (le relief), la part de surface qui change, ou None."""
    if np is None:
        return None
    c1, c2 = _carte_plate(im1), _carte_plate(im2)
    if c1 is None or c2 is None:
        return None
    if c1.size != c2.size:
        c2 = c2.resize(c1.size)
    g1, g2 = _passe_haut(_lum(_arr(c1))), _passe_haut(_lum(_arr(c2)))
    # meme niveau de contraste avant de soustraire (l'exposition change d'une photo a l'autre)
    g1 /= (np.std(g1) + 1e-6)
    g2 /= (np.std(g2) + 1e-6)
    d = g1 - g2
    fort = float((np.abs(d) > 3.5).mean()) * 100
    return {"image": _vers_image(d * 18, 1.0), "pct_relief": round(fort, 2)}
