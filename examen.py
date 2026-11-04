"""
SLABCOACH - l'examen de l'etat d'une carte, prepare pour l'IA (1er nov 2026).

Mathieu : « on doit ameliorer notre analyseur IA ; je veux qu'on soit PARFAIT ».
Ce qui rend un pre-gradeur bon n'est pas un « meilleur modele », c'est ce qu'on lui montre et ce qu'on mesure soi-meme :
  1. la carte REDRESSEE (ses 4 coins, trouves dans le telephone) puis des ZOOMS en pleine resolution : les 4 coins et les
     4 bords de chaque face, en mosaiques etiquetees. Un coin blanchi de 6 pixels dans la photo entiere devient visible ;
  2. le CENTRAGE MESURE par l'app (les bordures imprimees, de chaque cote) quand la carte a des bordures ; sinon on le dit ;
  3. l'IA recoit la mesure et les zooms ; ses sous-notes sont rendues coherentes par des regles (vision._nettoyer_etat).
Aucune dependance lourde : Pillow seulement.
"""
import base64
import io

try:
    from PIL import Image, ImageDraw, ImageOps
    # 3 nov 2026 (revue de securite) : une « bombe » (petit fichier, image geante) est refusee au lieu de remplir la memoire
    import warnings as _w
    Image.MAX_IMAGE_PIXELS = 40_000_000
    _w.simplefilter("error", Image.DecompressionBombWarning)
except ImportError:                       # serveur sans Pillow : l'examen marche comme avant (photos entieres seulement)
    Image = None

COTE_ENVOI = 1568                         # la plus grande image utile pour le modele
COTE_REDRESSE = 1400                      # le grand cote de la carte redressee
COIN = 0.13                               # un zoom de coin : 13 % du petit cote (avec la marge de fond) ; 2 nov : plus serre
BORD = 0.075                              # un zoom de bord : la bande de 7,5 % le long du bord (avec la marge de fond)
COTE_ZOOM = 3600                          # 2 nov 2026 : les zooms sortent de la photo en PLEINE resolution (avant : 1400 px)


def disponible():
    return Image is not None


def ouvrir(octets):
    im = Image.open(io.BytesIO(octets))
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def jpeg(im, cote=COTE_ENVOI, qualite=88):
    im = im.copy()
    im.thumbnail((cote, cote), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=qualite, optimize=True)
    return b.getvalue()


def _quad_px(quad, w, h):
    """quad en 0..1000 (haut-gauche, haut-droit, bas-droit, bas-gauche) -> pixels."""
    try:
        q = [(max(0.0, min(1000.0, float(x))) / 1000 * w, max(0.0, min(1000.0, float(y))) / 1000 * h) for x, y in quad][:4]
    except (TypeError, ValueError):
        return None
    if len(q) != 4:
        return None
    larg = ((q[1][0] - q[0][0]) ** 2 + (q[1][1] - q[0][1]) ** 2) ** .5
    haut = ((q[3][0] - q[0][0]) ** 2 + (q[3][1] - q[0][1]) ** 2) ** .5
    if larg < 0.15 * w or haut < 0.15 * h:
        return None
    return q


# 2 nov 2026 (Mathieu : « ameliorer la detection des rebords ») : les 4 aretes de la carte, ajustees sur la photo pleine
# resolution. Pour chaque cote : 40 points, le saut de luminosite le plus franc perpendiculairement au cote (+/- 4 % de la
# carte), une droite ajustee par moindres carres en ecartant les points aberrants (3 passes, ecart > 2,5 x l'ecart median),
# puis les coins = intersections des droites voisines. Methode classique (points d'arete + ajustement robuste de droites).
def _droite(pts):
    """Moindres carres totaux -> (cx, cy, dx, dy) (un point et la direction) ou None."""
    n = len(pts)
    if n < 2:
        return None
    cx, cy = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    import math
    a = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return cx, cy, math.cos(a), math.sin(a)


def _dist(d, p):
    cx, cy, dx, dy = d
    return abs((p[0] - cx) * dy - (p[1] - cy) * dx)


def _inter(d1, d2):
    x1, y1, a1, b1 = d1
    x2, y2, a2, b2 = d2
    det = a1 * (-b2) - b1 * (-a2)
    if abs(det) < 1e-9:
        return None
    t = ((x2 - x1) * (-b2) - (y2 - y1) * (-a2)) / det
    return x1 + a1 * t, y1 + b1 * t


def affiner_quad(im, quad, recherche=0.04):
    """quad (0..1000) -> quad ajuste (0..1000), ou le meme si les aretes ne sont pas assez franches."""
    import math
    W0, H0 = im.size
    q = _quad_px(quad, W0, H0)
    if not q:
        return quad
    k = min(1.0, 1100 / max(W0, H0))
    g = im.convert("L").resize((max(8, int(W0 * k)), max(8, int(H0 * k))), Image.BILINEAR)
    W, H = g.size
    px = g.load()
    q = [(x * k, y * k) for x, y in q]
    cote = max(math.dist(q[0], q[1]), math.dist(q[1], q[2]))
    R = max(4, int(cote * recherche))
    ctr = (sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4)

    def lum(x, y):
        xi, yi = int(x), int(y)
        if xi < 0 or yi < 0 or xi >= W or yi >= H:
            return None
        return px[xi, yi]

    lignes = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        L = math.dist(a, b) or 1
        tx, ty = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        nx, ny = -ty, tx                                   # normale ; orientee vers l'exterieur de la carte
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if (m[0] - ctr[0]) * nx + (m[1] - ctr[1]) * ny < 0:
            nx, ny = -nx, -ny
        pts = []
        for j in range(40):
            t = 0.1 + 0.8 * j / 39
            ox, oy = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            prof = []
            for s_ in range(-R, R + 1):
                v = lum(ox + nx * s_, oy + ny * s_)
                prof.append(v)
            best, bs = None, 0
            for s_ in range(2, len(prof) - 2):
                v1, v2 = prof[s_ - 2], prof[s_ + 2]
                if v1 is None or v2 is None:
                    continue
                gr = abs(v2 - v1)
                if gr > bs:
                    bs, best = gr, s_ - R
            if best is not None and bs >= 18:
                pts.append((ox + nx * best, oy + ny * best))
        if len(pts) < 12:
            return quad
        d = _droite(pts)
        for _ in range(3):
            ds = sorted(_dist(d, p) for p in pts)
            seuil = max(1.0, 2.5 * ds[len(ds) // 2])
            gard = [p for p in pts if _dist(d, p) <= seuil]
            if len(gard) < 12:
                return quad
            d = _droite(gard)
        if len(gard) < 0.5 * len(pts):
            return quad
        lignes.append(d)
    coins = []
    for i in range(4):
        c = _inter(lignes[(i + 3) % 4], lignes[i])
        if c is None or math.dist(c, q[i]) > 2.5 * R:
            return quad                                     # un coin trop loin du depart : on garde le depart
        coins.append(c)
    return [[max(0, min(1000, round(x / W * 1000))), max(0, min(1000, round(y / H * 1000)))] for x, y in coins]


def redresser(im, quad, marge=0.0, cote=None):
    """La carte seule, a plat (transformation du quadrilatere en rectangle). marge : la part de fond gardee autour (les
    zooms de coins et de bords doivent montrer l'ARETE de la carte, donc un peu de fond). -> image ou None."""
    q = _quad_px(quad, *im.size)
    if not q:
        return None
    if marge:
        cx, cy = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
        q = [(cx + (x - cx) * (1 + 2 * marge), cy + (y - cy) * (1 + 2 * marge)) for x, y in q]
    larg = (((q[1][0] - q[0][0]) ** 2 + (q[1][1] - q[0][1]) ** 2) ** .5 + ((q[2][0] - q[3][0]) ** 2 + (q[2][1] - q[3][1]) ** 2) ** .5) / 2
    haut = (((q[3][0] - q[0][0]) ** 2 + (q[3][1] - q[0][1]) ** 2) ** .5 + ((q[2][0] - q[1][0]) ** 2 + (q[2][1] - q[1][1]) ** 2) ** .5) / 2
    # cote=None : 1400 px (le centrage) ; les zooms : la pleine resolution de la photo (jamais agrandie : pas de detail invente)
    k = min(1.6, COTE_REDRESSE / max(larg, haut)) if cote is None else min(1.0, cote / max(larg, haut))
    W, H = max(50, int(larg * k)), max(50, int(haut * k))
    # Image.QUAD : coins source dans l'ordre haut-gauche, bas-gauche, bas-droit, haut-droit
    data = (q[0][0], q[0][1], q[3][0], q[3][1], q[2][0], q[2][1], q[1][0], q[1][1])
    return im.transform((W, H), Image.QUAD, data, Image.BICUBIC)


def regle(carte, face):
    """2 nov 2026 (Mathieu : « on doit voir le centrage et tes points de repere : ecriture, bord de la patch ») : la carte
    redressee entouree d'une regle 0-1000 (gauche->droite en haut, haut->bas a gauche) : l'IA y lit la position exacte des
    reperes du centrage (bordure, cadre, fenetre de patch, texte). Les memes coordonnees que la grille de l'ecran."""
    W, H = carte.size
    M = 46
    out = Image.new("RGB", (W + 2 * M, H + 2 * M), (24, 24, 28))
    out.paste(carte, (M, M))
    d = ImageDraw.Draw(out)
    for k in range(0, 1001, 25):
        x, y = M + k / 1000 * (W - 1), M + k / 1000 * (H - 1)
        L = 16 if k % 100 == 0 else 9 if k % 50 == 0 else 5
        for yy in (M - L, M + H):
            d.line([(x, yy), (x, yy + L)], fill=(255, 220, 90), width=2 if k % 100 == 0 else 1)
        for xx in (M - L, M + W):
            d.line([(xx, y), (xx + L, y)], fill=(255, 220, 90), width=2 if k % 100 == 0 else 1)
        if k % 100 == 0:
            d.text((x - 10, 4), str(k), fill=(255, 255, 255))
            d.text((4, y - 6), str(k), fill=(255, 255, 255))
    d.text((M, H + M + 18), f"{face} - carte redressee, regle 0-1000", fill=(255, 255, 255))
    return out


def _etiquette(im, texte):
    d = ImageDraw.Draw(im)
    w = 8 + 7 * len(texte)
    d.rectangle([0, 0, w, 18], fill=(0, 0, 0))
    d.text((4, 3), texte, fill=(255, 255, 255))
    return im


def mosaique_coins(carte, face):
    """Les 4 coins (20 % du petit cote, agrandis a 480 px) en 2 x 2, etiquetes."""
    W, H = carte.size
    c = int(min(W, H) * COIN)
    T = 640
    out = Image.new("RGB", (2 * T + 6, 2 * T + 6), (40, 40, 40))
    pos = {"haut-gauche": (0, 0), "haut-droit": (W - c, 0), "bas-gauche": (0, H - c), "bas-droit": (W - c, H - c)}
    for i, (nom, (x, y)) in enumerate(pos.items()):
        z = carte.crop((x, y, x + c, y + c)).resize((T, T), Image.LANCZOS)
        out.paste(_etiquette(z, f"{face} - coin {nom}"), ((i % 2) * (T + 6), (i // 2) * (T + 6)))
    return out


def mosaique_bords(carte, face, paire=("haut", "bas")):
    """2 nov 2026 : deux bords opposes, chacun coupe en deux moities (plus de grossissement), en bandes etiquetees. Les bords
    gauche et droit sont tournes a l'horizontale."""
    W, H = carte.size
    e = max(8, int(min(W, H) * BORD))
    L = 1500
    bandes = []
    for nom in paire:
        if nom == "haut":
            b = carte.crop((0, 0, W, e))
        elif nom == "bas":
            b = carte.crop((0, H - e, W, H))
        elif nom == "gauche":
            b = carte.crop((0, 0, e, H)).rotate(-90, expand=True)
        else:
            b = carte.crop((W - e, 0, W, H)).rotate(90, expand=True)
        bw = b.size[0]
        m = bw // 2
        for lib, x0, x1 in (("1re moitie", 0, m + e // 2), ("2e moitie", m - e // 2, bw)):
            bandes.append((f"{face} - bord {nom}, {lib}", b.crop((x0, 0, x1, b.size[1]))))
    hs = []
    for nom, b in bandes:
        k = L / b.size[0]
        hs.append((nom, b.resize((L, max(20, int(b.size[1] * k))), Image.LANCZOS)))
    out = Image.new("RGB", (L, sum(b.size[1] for _n, b in hs) + 6 * (len(hs) - 1)), (40, 40, 40))
    y = 0
    for nom, b in hs:
        out.paste(_etiquette(b, nom), (0, y))
        y += b.size[1] + 6
    return out


# -- le centrage mesure -------------------------------------------------------------------------------------------------
def _profil(carte, axe, de, a, bande=(0.25, 0.75)):
    """Le profil moyen des couleurs perpendiculaire a un bord : colonnes (axe 'x') de `de` a `a`, moyennees sur la bande
    du milieu des lignes (et inversement). -> liste de (r, g, b)."""
    W, H = carte.size
    if axe == "x":
        z = carte.crop((de, int(H * bande[0]), a, int(H * bande[1]))).resize((a - de, 1), Image.BOX)
        return [z.getpixel((i, 0)) for i in range(a - de)]
    z = carte.crop((int(W * bande[0]), de, int(W * bande[1]), a)).resize((1, a - de), Image.BOX)
    return [z.getpixel((0, i)) for i in range(a - de)]


def _bordure(profil, mini, maxi):
    """La position de la ligne bordure -> image la plus franche entre mini et maxi (pixels depuis le bord), et sa force."""
    g = [0.0] * len(profil)
    for i in range(2, len(profil) - 2):
        g[i] = sum(abs(profil[i + 2][c] - profil[i - 2][c]) for c in range(3))
    zone = g[mini:maxi]
    if not zone:
        return None, 0, 0
    pic = max(range(len(zone)), key=lambda i: zone[i]) + mini
    fond = sorted(zone)[len(zone) // 2] or 1
    return pic, g[pic], g[pic] / fond


def _candidats(profil, mini, maxi):
    """Les lignes franches d'un profil (maxima locaux du gradient, force >= 45 et >= 3,5 x le gradient median)."""
    g = [0.0] * len(profil)
    for i in range(2, len(profil) - 2):
        g[i] = sum(abs(profil[i + 2][c] - profil[i - 2][c]) for c in range(3))
    zone = g[mini:maxi]
    if not zone:
        return []
    fond = sorted(zone)[len(zone) // 2] or 1
    out = []
    for i in range(max(mini, 1), min(maxi, len(g) - 1)):
        if g[i] >= 45 and g[i] / fond >= 3.5 and g[i] >= g[i - 1] and g[i] >= g[i + 1]:
            if out and i - out[-1] <= 2:
                if g[i] > g[out[-1]]:
                    out[-1] = i
                continue
            out.append(i)
    return out


def _cote(carte, cote):
    """La largeur de la bordure d'un cote : 2 nov 2026 - la ligne imprimee la plus a l'EXTERIEUR qui est droite sur les 3
    segments du bord (avant : la plus forte, souvent une fenetre de patch ou un cadre interieur). -> px ou None."""
    W, H = carte.size
    long = W if cote in ("gauche", "droite") else H
    mini, maxi = max(3, int(long * 0.012)), int(long * 0.24)
    tol = max(3, long * 0.012)
    segs = []
    for seg in ((0.22, 0.40), (0.41, 0.59), (0.60, 0.78)):
        if cote == "gauche":
            p = _profil(carte, "x", 0, maxi + 3, seg)
        elif cote == "droite":
            p = list(reversed(_profil(carte, "x", W - maxi - 3, W, seg)))
        elif cote == "haut":
            p = _profil(carte, "y", 0, maxi + 3, seg)
        else:
            p = list(reversed(_profil(carte, "y", H - maxi - 3, H, seg)))
        segs.append(_candidats(p, mini, maxi))
    if not all(segs):
        return None
    for x in segs[0]:
        trio = [x]
        for autres in segs[1:]:
            proche = [y for y in autres if abs(y - x) <= tol]
            if not proche:
                break
            trio.append(min(proche, key=lambda y: abs(y - x)))
        if len(trio) == 3:
            return sorted(trio)[1]
    return None


def _couleur(carte, cote, px):
    """La couleur moyenne de la bordure (entre l'arete et la ligne trouvee), au milieu du cote."""
    W, H = carte.size
    px = max(2, int(px))
    box = {"gauche": (0, int(H * .3), px, int(H * .7)), "droite": (W - px, int(H * .3), W, int(H * .7)),
           "haut": (int(W * .3), 0, int(W * .7), px), "bas": (int(W * .3), H - px, int(W * .7), H)}[cote]
    return carte.crop(box).resize((1, 1), Image.BOX).getpixel((0, 0))


def _ratio(a, b):
    t = a + b
    if not t:
        return None
    g = round(100 * max(a, b) / t)
    return f"{g}/{100 - g}"


def _grad(profil):
    g = [0.0] * len(profil)
    for i in range(2, len(profil) - 2):
        g[i] = sum(abs(profil[i + 2][c] - profil[i - 2][c]) for c in range(3))
    return g


def _droit(carte, cote, x, tol):
    """La ligne a x px du bord est-elle droite (presente sur les 3 segments du cote) ?"""
    W, H = carte.size
    long = W if cote in ("gauche", "droite") else H
    maxi = int(long * 0.26)
    rates = 0
    for seg in ((0.16, 0.30), (0.33, 0.47), (0.53, 0.67), (0.70, 0.84)):     # tout le long du cote (un texte, une arche : non)
        if cote == "gauche":
            p = _profil(carte, "x", 0, maxi + 3, seg)
        elif cote == "droite":
            p = list(reversed(_profil(carte, "x", W - maxi - 3, W, seg)))
        elif cote == "haut":
            p = _profil(carte, "y", 0, maxi + 3, seg)
        else:
            p = list(reversed(_profil(carte, "y", H - maxi - 3, H, seg)))
        if not any(abs(c - x) <= tol for c in _candidats(p, max(2, int(x - tol - 2)), min(len(p) - 2, int(x + tol + 3)))):
            rates += 1
    return rates <= 1                                         # droite sur au moins 3 des 4 segments


def _axe(carte, c1, c2):
    """2 nov 2026 (Mathieu : « ameliorer la detection ») : le centrage d'un axe par SYMETRIE. Le profil d'un cote et celui
    du cote oppose (lu de l'arete vers l'interieur) sont aligns par correlation croisee normalisee : le meme element
    imprime (la bordure, ou le cadre d'une carte sans bordure) est trouve des deux cotes. On garde l'element commun le plus
    a l'exterieur, s'il est droit des deux cotes. -> (px c1, px c2) ou None."""
    import math
    W, H = carte.size
    long = W if c1 == "gauche" else H
    mini, maxi = max(3, int(long * 0.012)), int(long * 0.26)
    if c1 == "gauche":
        p1, p2 = _profil(carte, "x", 0, maxi + 3), list(reversed(_profil(carte, "x", W - maxi - 3, W)))
    else:
        p1, p2 = _profil(carte, "y", 0, maxi + 3), list(reversed(_profil(carte, "y", H - maxi - 3, H)))
    g1, g2 = _grad(p1), _grad(p2)
    D = int(long * 0.08)
    best, bd = -1.0, 0
    for d in range(-D, D + 1):
        xs = [(g1[i], g2[i + d]) for i in range(mini, maxi) if mini <= i + d < maxi]
        if len(xs) < 10:
            continue
        a = [u for u, _v in xs]
        b = [v for _u, v in xs]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        num = sum((u - ma) * (v - mb) for u, v in xs)
        den = math.sqrt(sum((u - ma) ** 2 for u in a) * sum((v - mb) ** 2 for v in b)) or 1
        if num / den > best:
            best, bd = num / den, d
    if best < 0.5:
        return None
    prod = [(g1[i] * g2[i + bd], i) for i in range(mini, maxi) if mini <= i + bd < maxi and g1[i] >= 45 and g2[i + bd] >= 45]
    if not prod:
        return None
    top = max(v for v, _i in prod)
    tol = max(3, long * 0.012)
    for v, i in sorted(prod, key=lambda x: x[1]):            # le plus a l'exterieur d'abord
        if v >= 0.35 * top and _droit(carte, c1, i, tol) and _droit(carte, c2, i + bd, tol):
            return i, i + bd
    return None


def centrage_detail(carte):
    """1er nov 2026 (Mathieu : « une grille pour montrer comment le centering a ete evalue ») : les 4 bordures trouvees, en
    fraction de la largeur / hauteur de la carte redressee (None = pas trouvee), et les ratios. 2 nov 2026 : par symetrie
    (_axe), ce qui marche aussi pour les cartes sans bordure (le cadre interieur sert de repere)."""
    if carte is None:
        return None
    W, H = carte.size
    x, y = _axe(carte, "gauche", "droite"), _axe(carte, "haut", "bas")
    l, r = x if x else (None, None)
    t, b = y if y else (None, None)
    okx, oky = bool(x and l + r < 0.5 * W), bool(y and t + b < 0.5 * H)
    return {"l": round(l / W, 4) if okx else None, "r": round(r / W, 4) if okx else None, "t": round(t / H, 4) if oky else None,
            "b": round(b / H, 4) if oky else None, "gd": _ratio(l, r) if okx else None, "hb": _ratio(t, b) if oky else None}


def ratios(l, r, t, b):
    """Des bordures en fraction -> {"gd", "hb"} (pour l'ajustement a la main)."""
    return {"gd": _ratio(l, r) if l is not None and r is not None and l + r > 0 else None,
            "hb": _ratio(t, b) if t is not None and b is not None and t + b > 0 else None}


def centrage(carte):
    """-> {"gd": "55/45", "hb": "52/48"} (le plus grand cote d'abord), une valeur None si la bordure n'est pas mesurable."""
    d = centrage_detail(carte)
    if not d:
        return None
    out = {"gd": d["gd"], "hb": d["hb"]}
    return out if (out["gd"] or out["hb"]) else None


# Tolerances de centrage publiees par PSA (devant / dos) -> la plus haute note permise par le centrage
# 2 nov 2026 (Mathieu : « on ne comprend pas ou tu as pris tes references pour le centering ») : les normes officielles PSA
# (psacard.com, Card Grading Standards) : le grade le plus haut que permet le centrage. Devant : 10 = environ 55/45 a
# 60/40 ; 9 = 60/40 a 65/35 ; 8 = 65/35 a 70/30 ; 7 = 70/30 a 75/25 ; 6 = 80/20 ; 5 et 4 = 85/15 ; 3 a 1 = 90/10.
# Dos : 10 = 75/25 ; 9 a 1 = 90/10. (Avant : un cran trop severe, 10 jusqu'a 55/45 seulement.)
_PSA_DEVANT = ((60, 10), (65, 9), (70, 8), (75, 7), (80, 6), (85, 5), (90, 3))
_PSA_DOS = ((75, 10), (90, 9))


def note_centrage(devant, dos=None):
    def pire(c):
        vs = [int(x.split("/")[0]) for x in ((c or {}).get("gd"), (c or {}).get("hb")) if x]
        return max(vs) if vs else None
    n = None
    p = pire(devant)
    if p is not None:
        n = next((v for lim, v in _PSA_DEVANT if p <= lim), 3)
    p = pire(dos)
    if p is not None:
        nd = next((v for lim, v in _PSA_DOS if p <= lim), 8)
        n = min(n, nd) if n is not None else None
    return n


def preparer(photos_octets, quads=None, rasante=None, rasante2=None, gros_plans=None):
    """photos_octets : [devant, dos?] (octets) ; quads : [quad_devant, quad_dos] en 0..1000 ; rasante : octets ou None.
    -> {"images": [(libelle, octets_jpeg)], "centrage": {...}, "note_centrage": n|None, "zooms": bool}"""
    quads = list(quads or [])
    images, cent, cartes, mes, verif = [], {}, [], {}, {}
    utilises = []                                          # 3 nov 2026 (revue) : le contour vraiment utilise, rendu a l'appelant
    for j, b in enumerate(photos_octets[:2]):
        face = "devant" if j == 0 else "dos"
        im = ouvrir(b)
        images.append((f"Photo {j} : le {face} (photo entiere).", jpeg(im)))
        q = quads[j] if j < len(quads) and quads[j] else None
        if not q:                                           # 3 nov 2026 : pas de contour du telephone -> l'app trouve la carte
            try:
                import mesures
                q0 = mesures.trouver_carte(im)
                q = affiner_quad(im, q0, 0.03) if q0 else None
            except Exception as e:
                print("Examen (carte trouvee) : " + repr(e), flush=True)
                q = None
        utilises.append(q)
        c = redresser(im, q) if q else None                 # exacte : pour le centrage
        z = redresser(im, q, 0.03, COTE_ZOOM) if q else None   # pleine resolution, un peu de fond : l'arete des coins et des bords
        cartes.append(c)
        if z is not None:
            images.append((f"Zooms des 4 coins du {face} (pleine resolution, carte redressee ; le fond autour montre l'arete).",
                           jpeg(mosaique_coins(z, face), 1290, 90)))
            images.append((f"Zooms des bords haut et bas du {face}, chacun en deux moities (le fond autour montre l'arete).",
                           jpeg(mosaique_bords(z, face, ("haut", "bas")), 1568, 90)))
            images.append((f"Zooms des bords gauche et droit du {face} (tournes a l'horizontale), chacun en deux moities.",
                           jpeg(mosaique_bords(z, face, ("gauche", "droite")), 1568, 90)))
        if c is not None:
            images.append((f"Le {face} redresse, avec une REGLE 0-1000 tout autour (pour les reperes du centrage : lis les positions sur la regle).",
                           jpeg(regle(c, face), 1568, 90)))
            m = centrage(c) or {}
            # 3 nov 2026 (Mathieu : « on doit etre meilleur que tout ce qui existe ») : les mesures de l'app (mesures.py) : le
            # centrage par paires d'elements imprimes en miroir complete la symetrie ; le blanchiment des coins et des bords
            # en mm ; la qualite de la photo (resolution native, nettete, reflets)
            mz = _mesurer(im, q, c, z)
            if mz:
                mes[face] = mz
                cp = mz.get("centrage") or {}
                for ax in ("gd", "hb"):
                    x = cp.get(ax)
                    if x and ((not m.get(ax) and x.get("fiabilite") in ("haute", "moyenne")) or (x.get("fiabilite") == "haute" and not x.get("a_verifier"))):
                        m[ax] = x["ratio"]
                        if x.get("a_verifier"):
                            verif.setdefault(face, []).append(ax)
                # la symetrie : un fort decentrage sans bordure unie -> a verifier (le bas de la fourchette seulement)
                try:
                    import mesures
                    det = centrage_detail(c) or {}
                    for ax, k1, k2 in (("gd", "l", "r"), ("hb", "t", "b")):
                        if m.get(ax) and m.get(ax) == det.get(ax) and int(str(m[ax]).split("/")[0]) > 60 \
                                and not mesures.bordure_unie(c, ax, det.get(k1), det.get(k2)) and ax not in verif.get(face, []):
                            verif.setdefault(face, []).append(ax)
                except Exception as e:
                    print("Examen (bordure) : " + repr(e), flush=True)
            if m.get("gd") or m.get("hb"):
                cent[face] = {"gd": m.get("gd"), "hb": m.get("hb")}
    # 3 nov 2026 (Mathieu : « une IA d'analyse parfaite ») : les GROS PLANS des coins, pris expres de tout pres. Une photo
    # entiere donne ~16 px/mm ; un coin se juge a 40 px/mm et plus (le blanchiment fait 0,1 mm). Envoyes en pleine
    # resolution (1568 px) : le modele juge chaque coin d'abord sur son gros plan.
    gp_info = []
    for g in (gros_plans or [])[:8]:
        try:
            im = ouvrir(g["octets"])
        except Exception as e:
            print("Examen (gros plan) : " + repr(e), flush=True)
            continue
        try:
            import mesures
            q = mesures.nettete_gros_plan(im)
        except Exception:
            q = None
        face, coin = g.get("face") or "devant", g.get("coin") or "?"
        gp_info.append({"face": face, "coin": coin, **(q or {})})
        images.append((f"GROS PLAN du coin {coin} du {face.upper()} (photo rapprochee prise expres, bien plus nette que les zooms ; "
                       f"tenue droite, ce coin vers le {coin}). Juge ce coin D'ABORD ici : la pointe, les 2 aretes, le blanc."
                       + (" Cette photo est un peu floue : confirme avec le zoom." if q and not q.get("net") else ""), jpeg(im, 1568, 90)))
    if rasante:
        images.append(("Photo en lumiere rasante (inclinee) : pour les rayures, les plis et les bosses de surface.", jpeg(ouvrir(rasante))))
        # 3 nov 2026 : le relief, calcule par l'app (l'impression s'efface, les rayures et les bosses ressortent)
        try:
            import mesures
            if rasante2:
                images.append(("Photo en lumiere rasante, la lampe de l'AUTRE cote.", jpeg(ouvrir(rasante2))))
                d = mesures.difference_eclairages(ouvrir(rasante), ouvrir(rasante2))
                if d:
                    images.append(("DIFFERENCE entre les deux eclairages, calculee par l'app (la carte a plat) : l'impression s'efface ; ce qui "
                                   "reste en clair ou en fonce est du RELIEF (rayure, bosse, pli, empreinte). Une ligne fine = rayure ; une tache "
                                   "ronde = bosse ou empreinte ; une ligne nette sur toute la carte = pli. Le contour de la carte et les reflets "
                                   "du vernis holo peuvent aussi ressortir : ne les compte pas.", jpeg(d["image"], 1568, 88)))
            else:
                rl = mesures.relief(ouvrir(rasante))
                if rl is not None:
                    images.append(("RELIEF de la photo rasante, calcule par l'app (eclairage lent enleve, contraste local x4) : les rayures et les "
                                   "bosses ressortent en lignes ou taches claires / foncees ; les motifs imprimes restent aussi, compare avec la photo.",
                                   jpeg(rl, 1568, 88)))
        except Exception as e:
            print("Examen (relief) : " + repr(e), flush=True)
    # la note du centrage : les axes « a verifier » (un decentrage fort mesure sur un element de design, peut-etre dessine
    # ainsi) n'abaissent que le BAS de la fourchette
    sur = {f: {ax: v for ax, v in d.items() if ax not in verif.get(f, [])} for f, d in cent.items()}
    n_haut = note_centrage(sur.get("devant"), sur.get("dos")) if cent else None
    n_bas = note_centrage(cent.get("devant"), cent.get("dos")) if cent else None
    return {"images": images, "centrage": cent or None, "note_centrage": n_haut if n_haut is not None else (n_bas if not verif else None),
            "note_centrage_bas": n_bas, "centrage_verifier": verif, "mesures": mes, "zooms": any(c is not None for c in cartes),
            "gros_plans": gp_info, "quads": utilises}


def _mesurer(im, q, c, z):
    """Les mesures de mesures.py pour une face (jamais d'exception : une mesure ratee n'empeche pas l'examen)."""
    try:
        import mesures
        if not mesures.disponible():
            return None
        px = _quad_px(q, *im.size) if q else None
        natif = None
        if px:
            cotes = [((px[i][0] - px[(i + 1) % 4][0]) ** 2 + (px[i][1] - px[(i + 1) % 4][1]) ** 2) ** 0.5 for i in range(4)]
            natif = min((cotes[0] + cotes[2]) / 2, (cotes[1] + cotes[3]) / 2) / mesures.MM_COURT
        return {"centrage": mesures.centrage(c), "usure": mesures.usure(z, 0.03) if z is not None else None,
                "silhouette": mesures.silhouette(z, 0.03) if z is not None else None, "qualite": mesures.qualite(c, natif)}
    except Exception as e:
        print("Examen (mesures) : " + repr(e), flush=True)
        return None


def data_url_octets(p):
    s = str(p or "")
    if s.startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)
