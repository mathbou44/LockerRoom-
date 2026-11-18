"""9 nov 2026 (Aikido : « user input in HTTP request may allow SSRF ») : les telechargements vers une adresse qui ne vient
pas du code (liens d'un flux RSS, pages d'eBay) passent par ici : https seulement, jamais une adresse interne (reseau prive,
boucle locale, metadonnees du nuage), redirections verifiees aussi, taille plafonnee."""
import ipaddress
import socket
import urllib.parse
import urllib.request


class AdresseRefusee(ValueError):
    pass


def _hote_public(hote):
    try:
        infos = socket.getaddrinfo(hote, 443, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise AdresseRefusee(f"hote introuvable : {hote}") from e
    for i in infos:
        ip = ipaddress.ip_address(i[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise AdresseRefusee(f"adresse interne refusee : {hote}")


def verifier(url, hotes=None):
    """hotes : suffixes permis (ex. ("ebay.ca", "ebay.com")) ; None = tout hote PUBLIC en https."""
    u = urllib.parse.urlsplit(str(url or ""))
    hote = (u.hostname or "").lower()
    if u.scheme != "https" or not hote:
        raise AdresseRefusee("https seulement")
    if hotes and not any(hote == h or hote.endswith("." + h) for h in hotes):
        raise AdresseRefusee(f"hote non permis : {hote}")
    _hote_public(hote)
    return url


class _Redir(urllib.request.HTTPRedirectHandler):
    def __init__(self, hotes):
        self.hotes = hotes

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        verifier(newurl, self.hotes)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def lire(url, hotes=None, headers=None, timeout=15, max_octets=3_000_000):
    verifier(url, hotes)
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.build_opener(_Redir(hotes)).open(req, timeout=timeout) as r:
        return r.read(max_octets)


class _Head(urllib.request.Request):
    def get_method(self):
        return "HEAD"


def suivre(url, hotes=None, timeout=8):
    """18 nov 2026 (Aikido, SSRF) : l'adresse FINALE d'un lien court colle par l'utilisateur (ebay.us/...) : chaque saut est
    verifie (https, hote public, permis) ; aucune adresse interne n'est jamais touchee."""
    verifier(url, hotes)
    req = _Head(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.build_opener(_Redir(hotes)).open(req, timeout=timeout) as r:
        fin = r.geturl()
    verifier(fin, hotes)
    return fin
