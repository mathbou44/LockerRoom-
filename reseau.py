"""20 nov 2026 (Aikido « Potential user input in HTTP request may allow SSRF attack ») : toutes les requetes sortantes du serveur
passent ici. Une adresse qui mene a l'interieur (le serveur lui-meme, le reseau prive de Render, l'adresse des metadonnees d'un
nuage, 169.254.x.x) est refusee, meme si un nom de domaine y pointe (DNS) ; seuls http et https sont permis. Les appels vers
l'exterieur (eBay, LNH, Wikipedia...) passent sans changement."""
import ipaddress
import os
import socket
import urllib.parse
import urllib.request

_LOCAL_OK = os.environ.get("LOCKERROOM_RESEAU_LOCAL") == "1"      # les tests seulement


class AdresseRefusee(ValueError):
    pass


def verifier(url):
    u = urllib.parse.urlsplit(str(url or ""))
    if u.scheme not in ("http", "https"):
        raise AdresseRefusee("Protocole refusé : " + (u.scheme or "?"))
    hote = (u.hostname or "").strip().lower()
    if not hote:
        raise AdresseRefusee("Adresse sans hôte")
    if _LOCAL_OK:
        return
    try:
        ips = {a[4][0] for a in socket.getaddrinfo(hote, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError, OSError):
        return                                   # introuvable : urlopen echouera de lui-meme
    for ip in ips:
        a = ipaddress.ip_address(ip.split("%")[0])
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified:
            raise AdresseRefusee("Adresse interne refusée : " + hote)


def ouvrir(req, *a, **k):
    """urllib.request.urlopen, apres verification de l'adresse (une Request ou une URL)."""
    verifier(req.full_url if isinstance(req, urllib.request.Request) else req)
    return urllib.request.urlopen(req, *a, **k)


def chemin_sur(base, nom):
    """20 nov 2026 (Aikido « Potential file inclusion attack via reading file ») : un fichier de donnees reste DANS son dossier :
    pas de chemin absolu, pas de « .. » ; sinon ValueError."""
    base = os.path.realpath(base)
    p = os.path.realpath(os.path.join(base, str(nom or "")))
    if os.path.isabs(str(nom or "")) or not (p == base or p.startswith(base + os.sep)):
        raise ValueError("Chemin refusé : " + str(nom)[:80])
    return p
