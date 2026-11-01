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
except ImportError:                       # serveur sans Pillow : l'examen marche comme avant (photos entieres seulement)
    Image = None

COTE_ENVOI = 1568                         # la plus grande image utile pour le modele
COTE_REDRESSE = 1400                      # le grand cote de la carte redressee
COIN = 0.16                               # un zoom de coin : 16 % du petit cote (avec la marge de fond)
BORD = 0.09                               # un zoom de bord : la bande de 9 % le long du bord (avec la marge de fond)


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


def redresser(im, quad, marge=0.0):
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
    k = min(1.6, COTE_REDRESSE / max(larg, haut))     # jamais plus de 1,6 x (on n'invente pas de detail)
    W, H = max(50, int(larg * k)), max(50, int(haut * k))
    # Image.QUAD : coins source dans l'ordre haut-gauche, bas-gauche, bas-droit, haut-droit
    data = (q[0][0], q[0][1], q[3][0], q[3][1], q[2][0], q[2][1], q[1][0], q[1][1])
    return im.transform((W, H), Image.QUAD, data, Image.BICUBIC)


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
    T = 480
    out = Image.new("RGB", (2 * T + 6, 2 * T + 6), (40, 40, 40))
    pos = {"haut-gauche": (0, 0), "haut-droit": (W - c, 0), "bas-gauche": (0, H - c), "bas-droit": (W - c, H - c)}
    for i, (nom, (x, y)) in enumerate(pos.items()):
        z = carte.crop((x, y, x + c, y + c)).resize((T, T), Image.LANCZOS)
        out.paste(_etiquette(z, f"{face} - coin {nom}"), ((i % 2) * (T + 6), (i // 2) * (T + 6)))
    return out


def mosaique_bords(carte, face):
    """Les 4 bords en bandes (le haut et le bas tels quels, la gauche et la droite tournees a l'horizontale)."""
    W, H = carte.size
    e = max(8, int(min(W, H) * BORD))
    L = 1400
    bandes = [("bord haut", carte.crop((0, 0, W, e))), ("bord bas", carte.crop((0, H - e, W, H))),
              ("bord gauche", carte.crop((0, 0, e, H)).rotate(-90, expand=True)), ("bord droit", carte.crop((W - e, 0, W, H)).rotate(90, expand=True))]
    hs = []
    for nom, b in bandes:
        k = L / b.size[0]
        hs.append((nom, b.resize((L, max(20, int(b.size[1] * k))), Image.LANCZOS)))
    out = Image.new("RGB", (L, sum(b.size[1] for _n, b in hs) + 6 * 3), (40, 40, 40))
    y = 0
    for nom, b in hs:
        out.paste(_etiquette(b, f"{face} - {nom}"), (0, y))
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


def _cote(carte, cote):
    """La largeur de la bordure d'un cote, mesuree sur 3 segments du bord (elle doit etre droite). -> px ou None."""
    W, H = carte.size
    long = W if cote in ("gauche", "droite") else H
    mini, maxi = max(3, int(long * 0.012)), int(long * 0.24)
    pos = []
    for seg in ((0.22, 0.40), (0.41, 0.59), (0.60, 0.78)):
        if cote == "gauche":
            p = _profil(carte, "x", 0, maxi + 3, seg)
        elif cote == "droite":
            p = list(reversed(_profil(carte, "x", W - maxi - 3, W, seg)))
        elif cote == "haut":
            p = _profil(carte, "y", 0, maxi + 3, seg)
        else:
            p = list(reversed(_profil(carte, "y", H - maxi - 3, H, seg)))
        x, force, rel = _bordure(p, mini, maxi)
        if x is None or force < 45 or rel < 3.5:
            return None
        pos.append(x)
    if max(pos) - min(pos) > max(3, long * 0.012):       # pas une ligne droite : un motif de l'image, pas une bordure
        return None
    return sorted(pos)[1]


def _ratio(a, b):
    t = a + b
    if not t:
        return None
    g = round(100 * max(a, b) / t)
    return f"{g}/{100 - g}"


def centrage_detail(carte):
    """1er nov 2026 (Mathieu : « une grille pour montrer comment le centering a ete evalue ») : les 4 bordures trouvees, en
    fraction de la largeur / hauteur de la carte redressee (None = pas trouvee), et les ratios."""
    if carte is None:
        return None
    W, H = carte.size
    l, r, t, b = _cote(carte, "gauche"), _cote(carte, "droite"), _cote(carte, "haut"), _cote(carte, "bas")
    okx, oky = bool(l and r and l + r < 0.4 * W), bool(t and b and t + b < 0.4 * H)
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
_PSA_DEVANT = ((55, 10), (60, 9), (65, 8), (70, 7), (80, 6), (85, 5), (90, 4))
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


def preparer(photos_octets, quads=None, rasante=None):
    """photos_octets : [devant, dos?] (octets) ; quads : [quad_devant, quad_dos] en 0..1000 ; rasante : octets ou None.
    -> {"images": [(libelle, octets_jpeg)], "centrage": {...}, "note_centrage": n|None, "zooms": bool}"""
    quads = list(quads or [])
    images, cent, cartes = [], {}, []
    for j, b in enumerate(photos_octets[:2]):
        face = "devant" if j == 0 else "dos"
        im = ouvrir(b)
        images.append((f"Photo {j} : le {face} (photo entiere).", jpeg(im)))
        q = quads[j] if j < len(quads) and quads[j] else None
        c = redresser(im, q) if q else None                 # exacte : pour le centrage
        z = redresser(im, q, 0.03) if q else None           # avec un peu de fond : pour voir l'arete des coins et des bords
        cartes.append(c)
        if z is not None:
            images.append((f"Zooms des 4 coins du {face} (pleine resolution, carte redressee ; le fond autour montre l'arete).",
                           jpeg(mosaique_coins(z, face), 1100)))
            images.append((f"Zooms des 4 bords du {face} (le fond autour montre l'arete).", jpeg(mosaique_bords(z, face), 1400)))
        if c is not None:
            m = centrage(c)
            if m:
                cent[face] = m
    if rasante:
        images.append(("Photo en lumiere rasante (inclinee) : pour les rayures, les plis et les bosses de surface.", jpeg(ouvrir(rasante))))
    return {"images": images, "centrage": cent or None, "note_centrage": note_centrage(cent.get("devant"), cent.get("dos")) if cent else None,
            "zooms": any(c is not None for c in cartes)}


def data_url_octets(p):
    s = str(p or "")
    if s.startswith("data:"):
        s = s.split(",", 1)[1]
    return base64.b64decode(s)
