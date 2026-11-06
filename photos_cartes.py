"""
SLABCOACH - photos des cartes gardees dans l'inventaire (27 oct 2026, Mathieu : « apres l'annonce, ca lui demande s'il
veut juste la laisser dans son inventaire ou la publier sur eBay »).

Une carte gardee « pour plus tard » garde ses photos (la photo studio, faite dans le telephone) sur NOTRE serveur, dans
le dossier du compte : elles ne sont visibles que par ce compte (/mes-photos/<nom>, connexion requise) et partent chez
eBay seulement le jour ou le vendeur publie. Supprimer la carte (ou le compte) supprime ses photos.
"""
import base64
import os
import re
import secrets

import comptes

MAX_OCTETS = 8_000_000                  # 5 nov 2026 : les originales de la camera native HD (jusqu'a 5000 px)
MAX_PHOTOS = 12
PREFIXE = "/mes-photos/"
_NOM = re.compile(r"[a-f0-9]{16}\.jpg")


def dossier():
    d = os.path.join(comptes.dossier() or comptes.DONNEES, "photos_cartes")
    os.makedirs(d, exist_ok=True)
    return d


def chemin(ref):
    """« /mes-photos/0a1b...jpg » -> fichier du compte courant, ou None."""
    nom = str(ref or "").rsplit("/", 1)[-1]
    if not _NOM.fullmatch(nom):
        return None
    f = os.path.join(dossier(), nom)
    return f if os.path.isfile(f) else None


MAX_PIXELS = 40_000_000                 # 3 nov 2026 (revue de securite) : 8000 x 5000 au plus (une photo de 48 Mpx passe)
QUOTA_MO = float(os.environ.get("LR_PHOTOS_QUOTA_MO") or 1500)     # par compte (un abus ne remplit pas le disque partage)


def _taille_ok(brut):
    """Les dimensions lues dans l'en-tete, sans decoder l'image (une petite image geante = une bombe)."""
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(brut)) as im:
            w, h = im.size
    except ImportError:
        return
    except Exception:
        return                          # pas une image lisible : rien a decoder plus tard non plus (pas de bombe)
    if w * h > MAX_PIXELS or max(w, h) > 12000:
        raise ValueError("Photo trop grande : reprends-la")


def _quota_ok(n):
    d = dossier()
    try:
        tot = sum(e.stat().st_size for e in os.scandir(d) if e.is_file())
    except OSError:
        return
    if tot + n > QUOTA_MO * 1e6:
        raise ValueError("Espace photos plein : supprime des cartes ou d’anciennes photos")


def sauver(photos):
    """Liste de photos (data URL, URL https d'eBay ou /mes-photos/ deja gardee) -> liste de references."""
    out = []
    for p in (photos or [])[:MAX_PHOTOS]:
        p = str(p or "")
        if p.startswith("https://") or (p.startswith(PREFIXE) and chemin(p)):
            out.append(p)
            continue
        m = re.match(r"data:image/(?:jpeg|jpg|png|webp);base64,(.+)$", p, re.S)
        if not m:
            continue
        try:
            brut = base64.b64decode(m.group(1), validate=False)
        except (ValueError, TypeError):
            continue
        if len(brut) < 2000 or len(brut) > MAX_OCTETS:
            raise ValueError("Photo trop lourde ou illisible : reprends-la")
        if not (brut[:3] == b"\xff\xd8\xff" or brut[:8] == b"\x89PNG\r\n\x1a\n" or (brut[:4] == b"RIFF" and brut[8:12] == b"WEBP")):
            raise ValueError("Format de photo non pris en charge")
        _taille_ok(brut)
        _quota_ok(len(brut))
        nom = secrets.token_hex(8) + ".jpg"
        with open(os.path.join(dossier(), nom), "wb") as f:
            f.write(brut)
        out.append(PREFIXE + nom)
    return out


DISQUE_MIN_MO = float(os.environ.get("LR_PHOTOS_DISQUE_MIN_MO") or 350)


def disque_libre_mo():
    import shutil
    try:
        return shutil.disk_usage(dossier()).free / 1e6
    except OSError:
        return 0.0


def garder_hd():
    """7 nov 2026 (Mathieu : « on devrait pouvoir cliquer sur la photo, zoomer et voir tous les defauts en 48 Mpx ») : les
    photos de la carte (devant, dos) restent en pleine resolution, tant que le disque du serveur a de la place
    (DISQUE_MIN_MO) ; sous ce seuil, elles sont allegees comme avant (2400 px) pour ne jamais remplir le disque."""
    return disque_libre_mo() >= DISQUE_MIN_MO


def alleger(fichiers, cote=2400, qualite=85, min_octets=1_300_000):
    """5 nov 2026 (Mathieu : « une fois la photo evaluee, on peut reduire la qualite pour prendre moins de place ») : une
    photo deja examinee (les zooms en pleine resolution ont ete faits) est gardee en 2400 px, JPEG 85 (~0,6-1 Mo au lieu
    de 5-6 Mo). Meme nom de fichier (les references restent bonnes) ; les contours 0..1000 ne changent pas (meme cadrage).
    fichiers : les CHEMINS (resolus par l'appelant : dossier() depend du compte courant). -> octets gagnes"""
    try:
        from PIL import Image
    except ImportError:
        return 0
    gagne = 0
    for f in fichiers or []:
        try:
            if not f or not os.path.isfile(f) or os.path.getsize(f) < min_octets:
                continue
            avant = os.path.getsize(f)
            with Image.open(f) as im:
                o = (im.getexif() or {}).get(0x0112, 1)
                if o not in (None, 1):          # une orientation EXIF : on n'y touche pas (les contours seraient tournes)
                    continue
                im = im.convert("RGB")
                k = min(1.0, cote / max(im.size))
                if k < 1.0:
                    im = im.resize((max(1, round(im.size[0] * k)), max(1, round(im.size[1] * k))), Image.LANCZOS)
                tmp = f + ".allege"
                im.save(tmp, "JPEG", quality=qualite, optimize=True)
            if os.path.getsize(tmp) < avant:
                os.replace(tmp, f)
                gagne += avant - os.path.getsize(f)
            else:
                os.remove(tmp)
        except Exception as e:
            print("Photo allegee : " + repr(e), flush=True)
            try:
                os.remove(f + ".allege")
            except OSError:
                pass
    return gagne


def supprimer(refs):
    for r in refs or []:
        f = chemin(r)
        if f:
            try:
                os.remove(f)
            except OSError:
                pass
