"""9 nov 2026 (Mathieu : « beaucoup de gens vont televerser leurs cartes scannees via l'ordi » ; un scan = plusieurs cartes) :
une page de numeriseur -> une image par carte.

Le fond du scan (le couvercle blanc, ou noir) est lu sur le pourtour de la page ; une carte = une tache qui tranche avec
ce fond et qui a la taille et les proportions d'une carte (63,5 x 88,9 mm, ou couchee ; un slab est plus long). Chaque
carte est recadree avec une petite marge de fond tout autour : la suite (lecture, coins, photo studio) la traite comme
une photo ordinaire. Sans scipy : les taches sont etiquetees sur une version reduite (800 px), en Python pur.
"""
import base64
import io

from PIL import Image, ImageFilter, ImageOps

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

COTE_ANALYSE = 800            # 2 mm d'espace entre deux cartes = ~4 px ici : elles restent separees
MAX_CARTES = 24


def _fond(a):
    """La couleur du fond : la mediane du pourtour (3 % de chaque bord)."""
    h, w = a.shape[:2]
    m = max(2, int(min(h, w) * 0.03))
    bord = np.concatenate([a[:m].reshape(-1, 3), a[-m:].reshape(-1, 3), a[:, :m].reshape(-1, 3), a[:, -m:].reshape(-1, 3)])
    med = np.median(bord, axis=0)
    # le bruit du fond : la mediane des ecarts (des cartes peuvent toucher le bord de la page : pas le 90e centile)
    return med, np.percentile(np.sqrt(((bord - med) ** 2).sum(axis=1)), 50)


def _taches(masque):
    """Composantes connexes (4 voisins) d'un masque booleen -> liste de (n_pixels, x0, y0, x1, y1)."""
    h, w = masque.shape
    vu = np.zeros_like(masque, dtype=bool)
    out = []
    pts = np.argwhere(masque)
    for y, x in pts:
        if vu[y, x]:
            continue
        pile = [(y, x)]
        vu[y, x] = True
        n, x0, y0, x1, y1 = 0, x, y, x, y
        while pile:
            cy, cx = pile.pop()
            n += 1
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and masque[ny, nx] and not vu[ny, nx]:
                    vu[ny, nx] = True
                    pile.append((ny, nx))
        out.append((n, x0, y0, x1, y1))
    return out


def _separer(m, x0, y0, x1, y1, prof=0):
    """Deux cartes presque collees forment une seule tache : on la coupe la ou une rangee (ou une colonne) entiere est
    presque toute du fond (l'espace de 1-2 mm entre deux cartes d'une grille), recursivement."""
    if prof > 6:
        return [(x0, y0, x1, y1)]
    z = m[y0:y1 + 1, x0:x1 + 1]
    for axe in (0, 1):                                    # 0 : rangees (coupe horizontale), 1 : colonnes
        dens = z.mean(axis=1 - axe)
        n = dens.size
        lo, hi = int(n * 0.12), int(n * 0.88)             # jamais tout pres du bord de la tache
        creux = [i for i in range(lo, hi) if dens[i] < 0.35]
        if creux:
            # le creux le plus profond ; ses voisins de part et d'autre doivent etre de la carte
            i = min(creux, key=lambda j: dens[j])
            if dens[:i].max() > 0.6 and dens[i + 1:].max() > 0.6:
                if axe == 0:
                    return _separer(m, x0, y0, x1, y0 + i - 1, prof + 1) + _separer(m, x0, y0 + i + 1, x1, y1, prof + 1)
                return _separer(m, x0, y0, x0 + i - 1, y1, prof + 1) + _separer(m, x0 + i + 1, y0, x1, y1, prof + 1)
    # resserrer la boite sur la carte (les rangees et colonnes vides du bord)
    ys = np.where(z.mean(axis=1) > 0.2)[0]
    xs = np.where(z.mean(axis=0) > 0.2)[0]
    if not ys.size or not xs.size:
        return []
    return [(x0 + int(xs[0]), y0 + int(ys[0]), x0 + int(xs[-1]), y0 + int(ys[-1]))]


def decouper(im):
    """im (PIL) -> liste de {"image": PIL, "boite": (x0, y0, x1, y1) en px, "centre": (cx, cy) en 0..1}, lue de gauche a
    droite puis de haut en bas (par rangees). Une seule carte trouvee -> une liste d'un element."""
    if np is None:
        return []
    im = ImageOps.exif_transpose(im).convert("RGB")
    W, H = im.size
    k = COTE_ANALYSE / max(W, H)
    pt = im.resize((max(1, round(W * k)), max(1, round(H * k))), Image.BOX)
    a = np.asarray(pt, dtype=float)
    f, bruit = _fond(a)
    dist = np.sqrt(((a - f) ** 2).sum(axis=2))
    seuil = max(28.0, float(bruit) * 3 + 10)
    brut = dist > seuil
    # ouverture : les poussieres et les fils disparaissent (pas de fermeture : elle collerait deux cartes voisines)
    mi = Image.fromarray((brut * 255).astype("uint8")).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    m = np.asarray(mi) > 127
    h, w = m.shape
    aire_page = h * w
    boites = []
    for n, x0, y0, x1, y1 in _taches(m):
        if n >= aire_page * 0.008:
            boites += _separer(brut, x0, y0, x1, y1)
    # une carte a cadre blanc donne 2 taches (le tour colore et l'image du centre) : la boite incluse dans une autre part
    def dedans(a_, b_):
        ix = max(0, min(a_[2], b_[2]) - max(a_[0], b_[0]) + 1)
        iy = max(0, min(a_[3], b_[3]) - max(a_[1], b_[1]) + 1)
        return ix * iy >= 0.8 * (a_[2] - a_[0] + 1) * (a_[3] - a_[1] + 1)
    boites.sort(key=lambda b_: (b_[2] - b_[0]) * (b_[3] - b_[1]), reverse=True)
    garde = []
    for b_ in boites:
        if not any(dedans(b_, g) for g in garde):
            garde.append(b_)
    cartes = []
    for x0, y0, x1, y1 in garde:
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        if bw * bh < aire_page * 0.008 or bw < 12 or bh < 12:           # poussiere, texte, ombre
            continue
        r = max(bw, bh) / min(bw, bh)
        if not 1.15 <= r <= 2.1:                                          # carte 1,40 (penchee : moins) ; slab ~1,7
            continue
        if brut[y0:y1 + 1, x0:x1 + 1].mean() < 0.45:                     # une tache creuse ou en L : pas une carte
            continue
        mx, my = max(2, int(bw * 0.06)), max(2, int(bh * 0.06))        # un peu de fond autour (les coins se lisent)
        X0, Y0 = max(0, int((x0 - mx) / k)), max(0, int((y0 - my) / k))
        X1, Y1 = min(W, int((x1 + 1 + mx) / k)), min(H, int((y1 + 1 + my) / k))
        cartes.append({"image": im.crop((X0, Y0, X1, Y1)), "boite": (X0, Y0, X1, Y1),
                       "centre": (round((X0 + X1) / 2 / W, 4), round((Y0 + Y1) / 2 / H, 4))})
    if not cartes:
        return []
    # l'ordre de lecture : par rangees (une carte de haut), puis de gauche a droite
    hc = np.median([c["boite"][3] - c["boite"][1] for c in cartes]) / H
    cartes.sort(key=lambda c: (round(c["centre"][1] / max(hc * 0.6, 1e-3)), c["centre"][0]))
    return cartes[:MAX_CARTES]


def jpeg_data_url(im, cote=3000, qualite=90):
    im = im.copy()
    im.thumbnail((cote, cote), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=qualite, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def apparier(devants, dos):
    """Un scan des devants puis un scan des dos (chaque carte retournee SUR PLACE) : le dos d'une carte est au meme endroit
    de la page que son devant (ou en miroir, si on a retourne la page entiere) -> la meilleure des deux lectures.
    -> liste d'index de dos (ou None) pour chaque devant."""
    if not devants or not dos:
        return [None] * len(devants)

    def cout(miroir):
        pris, paires, total = set(), [], 0.0
        for d in devants:
            cx = 1 - d["centre"][0] if miroir else d["centre"][0]
            best, bd = None, 9.0
            for j, b in enumerate(dos):
                if j in pris:
                    continue
                e = (cx - b["centre"][0]) ** 2 + (d["centre"][1] - b["centre"][1]) ** 2
                if e < bd:
                    best, bd = j, e
            if best is not None and bd < 0.02:                            # a moins de ~14 % de la page
                pris.add(best)
                paires.append(best)
                total += bd
            else:
                paires.append(None)
                total += 0.05
        return total, paires
    return min(cout(False), cout(True), key=lambda x: x[0])[1]
