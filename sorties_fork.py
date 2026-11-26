"""26 nov 2026 — le worker ne doit jamais heriter d'une sortie verrouillee.

Ce qui s'est passe (15 h 23, juste apres un push ; courriel de Render « HTTP health check failed (timed out after
5 seconds) ») : sur Render, gunicorn precharge l'app dans le processus MAITRE, ou roulent les fils de fond ; le worker qui
repond aux clients en est une copie (fork). Si, a l'instant precis du fork, un fil du maitre est en train d'ecrire sur la
sortie standard (un print(..., flush=True) : le gardien des piles s'annonce justement a ce moment-la), le worker herite du
verrou interne de sys.stdout a l'etat « pris », par un fil qui n'existe pas chez lui : personne ne le relachera jamais.

Dans le worker, chaque fil qui ecrit ensuite sur la sortie reste bloque pour toujours. Or gunicorn ecrit une ligne d'acces
apres CHAQUE requete (verification de sante comprise) : les 32 fils tombent un par un (chacun sert une requete, puis reste
pris sur sa ligne d'acces), le serveur ne repond plus, Render le redemarre au bout d'une minute. Signature dans le journal :
« RuntimeError: reentrant call inside <_io.BufferedWriter name='<stdout>'> » dans les premieres secondes (le seul fil qui
a herite de l'identite du fil fautif), puis plus AUCUNE ligne d'acces. Vu 1 fois sur 13 demarrages.

Le remede : dans l'enfant, tout de suite apres le fork, des sorties NEUVES sur les memes descripteurs (1 et 2), donc avec
des verrous neufs, et les journaux de logging (gunicorn y ecrit) pointes dessus. Les anciennes ne sont jamais touchees
(les vider attendrait le meme verrou) ni liberees (leur finalisation voudrait les vider).
"""
import atexit
import io
import logging
import os
import sys

_GARDEES = []                                    # les anciennes sorties, gardees en vie pour toujours (voir plus haut)
_ETAT = {"installe": False, "refaites": 0, "fin": None}


def _fermer_les_anciennes():
    """A la fin du processus : les anciennes sorties sont marquees fermees SANS etre videes (on ferme l'objet du descripteur,
    pas le descripteur : closefd est faux pour les sorties standard). Python ne tentera donc pas de les vider en les liberant
    (il attendrait le verrou herite, puis s'arreterait sur une erreur fatale)."""
    for vieux in list(_GARDEES):
        try:
            brut = vieux.buffer.raw
            if getattr(brut, "closefd", True) is False:
                brut.close()
        except Exception:
            pass


def _journaux():
    """Tous les handlers de logging vivants (ceux de gunicorn compris)."""
    vus, out = set(), []
    for ref in list(getattr(logging, "_handlerList", None) or ()):
        h = ref() if callable(ref) else ref
        if h is not None and id(h) not in vus:
            vus.add(id(h))
            out.append(h)
    noms = [logging.getLogger()] + [x for x in list(logging.Logger.manager.loggerDict.values()) if isinstance(x, logging.Logger)]
    for lg in noms:
        for h in list(getattr(lg, "handlers", None) or ()):
            if id(h) not in vus:
                vus.add(id(h))
                out.append(h)
    return out


def refaire():
    """Des sorties neuves pour CE processus. Appelee dans l'enfant apres chaque fork ; ne leve jamais."""
    for nom, fd in (("stdout", 1), ("stderr", 2)):
        try:
            vieux = getattr(sys, nom, None)
            if not isinstance(vieux, io.TextIOWrapper) or not isinstance(vieux.buffer, io.BufferedWriter):
                continue                         # sans tampon (python -u) ou sortie remplacee : pas de verrou a heriter
            if vieux.fileno() != fd:
                continue
            neuf = io.TextIOWrapper(io.BufferedWriter(io.FileIO(fd, "w", closefd=False)),
                                    encoding=vieux.encoding or "utf-8", errors=vieux.errors or "backslashreplace",
                                    line_buffering=bool(vieux.line_buffering), write_through=bool(vieux.write_through))
        except Exception:
            continue
        _GARDEES.append(vieux)
        setattr(sys, nom, neuf)
        if getattr(sys, "__" + nom + "__", None) is vieux:
            setattr(sys, "__" + nom + "__", neuf)
        try:
            for h in _journaux():
                if getattr(h, "stream", None) is vieux:
                    h.stream = neuf              # pas setStream() : elle viderait l'ancienne sortie (le verrou)
        except Exception:
            pass
    _ETAT["refaites"] += 1
    if _ETAT["fin"] != os.getpid():
        _ETAT["fin"] = os.getpid()
        try:
            atexit.register(_fermer_les_anciennes)
        except Exception:
            pass


def installer():
    """A appeler une fois, au chargement, dans le processus qui va etre copie (le maitre de gunicorn)."""
    if _ETAT["installe"] or not hasattr(os, "register_at_fork"):
        return False
    os.register_at_fork(after_in_child=refaire)
    _ETAT["installe"] = True
    return True
