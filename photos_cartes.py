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

MAX_OCTETS = 4_500_000
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
        nom = secrets.token_hex(8) + ".jpg"
        with open(os.path.join(dossier(), nom), "wb") as f:
            f.write(brut)
        out.append(PREFIXE + nom)
    return out


def supprimer(refs):
    for r in refs or []:
        f = chemin(r)
        if f:
            try:
                os.remove(f)
            except OSError:
                pass
