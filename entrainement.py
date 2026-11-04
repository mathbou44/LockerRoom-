"""
SLABCOACH - la banque d'entrainement de l'analyseur d'etat (3 nov 2026).

Mathieu : « on doit developper une IA d'analyse de carte parfaite ; va tout chercher pour entrainer notre IA ».
Aucune base publique ne donne ce qu'il faut (photos brutes AVANT le gradage + la vraie note + les sous-notes) : les
images PSA sont interdites (licence), les jeux publics sont des slabs basse resolution sans licence claire. La seule
source fiable, c'est NOUS : chaque carte examinee dans SlabCoach puis revenue du gradage.

Seulement si l'utilisateur a dit OUI (reglage « ia_entrainement_ok », non par defaut) :
  - a la revenue du gradage : les photos d'examen (devant, dos, rasantes, gros plans des coins), les mesures de l'app,
    les observations de l'IA, la note estimee, la VRAIE note et les sous-notes (TAG, BGS) si donnees ;
  - quand il confirme / rejette un defaut (✓ / ✕) : le meme examen, avec ses avis (des defauts etiquetes).
Sans nom, sans pseudo, sans prix : la carte (annee, set, joueur, variante) et un identifiant opaque du compte (HMAC avec
un sel du serveur), qui sert seulement a TOUT effacer quand il retire son OUI ou supprime son compte.
L'admin exporte un zip (dataset.jsonl + photos) pour entrainer un detecteur (YOLO / RF-DETR) ou faire un banc d'essai.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import zipfile
from datetime import datetime

_verrou = threading.RLock()          # 3 nov 2026 (revue) : la copie des photos et le journal sous le meme verrou que le retrait
MAX_MO = float(os.environ.get("LR_ENTRAINEMENT_MAX_MO") or 4000)     # la banque ne depasse jamais ca
LIBRE_MIN_MO = 800                                                  # ni ne remplit le disque
SOUS = ("centrage", "coins", "bords", "surface")


def dossier():
    import comptes
    d = os.path.join(comptes.DONNEES, "entrainement")
    os.makedirs(os.path.join(d, "photos"), exist_ok=True)
    return d


def _journal():
    return os.path.join(dossier(), "exemples.jsonl")


def _sel():
    f = os.path.join(dossier(), ".sel")
    try:
        with open(f, "rb") as x:
            s = x.read()
        if len(s) >= 16:
            return s
    except OSError:
        pass
    s = secrets.token_bytes(32)
    with open(f, "wb") as x:
        x.write(s)
    return s


def compte_h(cid):
    """L'identifiant opaque d'un compte (rien ne permet de remonter au compte sans la base des comptes ET le sel)."""
    return hmac.new(_sel(), str(cid or "local").encode(), hashlib.sha256).hexdigest()[:20]


def _compte_courant():
    import comptes
    return compte_h(comptes.courant() if comptes.MULTI else "local")


def _taille_mo():
    t = 0
    for racine, _d, fs in os.walk(dossier()):
        for f in fs:
            try:
                t += os.path.getsize(os.path.join(racine, f))
            except OSError:
                pass
    return t / 1e6


def _place_ok():
    try:
        libre = shutil.disk_usage(dossier()).free / 1e6
    except OSError:
        libre = 1e9
    return libre > LIBRE_MIN_MO and _taille_mo() < MAX_MO


def _copier(ref):
    """Une photo du compte (/mes-photos/...) -> copiee dans la banque sous son empreinte (une seule copie). -> nom|None"""
    import photos_cartes
    f = photos_cartes.chemin(ref)
    if not f:
        return None
    with open(f, "rb") as x:
        b = x.read()
    nom = hashlib.sha256(b).hexdigest()[:24] + ".jpg"
    cible = os.path.join(dossier(), "photos", nom)
    if not os.path.isfile(cible):
        tmp = cible + ".tmp"
        with open(tmp, "wb") as x:
            x.write(b)
        os.replace(tmp, cible)
    return nom


def _num(v, lo=1.0, hi=10.0):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if lo <= x <= hi else None


def sous_notes(d):
    """{centrage, coins, bords, surface} (1 a 10, demis) ; le reste ignore."""
    d = d or {}
    out = {k: _num(d.get(k)) for k in SOUS}
    return {k: v for k, v in out.items() if v is not None} or None


def _carte(carte):
    c = carte or {}
    return {k: c.get(k) for k in ("annee", "marque", "set_nom", "numero", "joueur", "parallele", "tirage", "relique", "auto", "sport") if c.get(k) not in (None, "")}


def _examen(e):
    """Ce qu'on garde de l'examen : estimations, observations, mesures, avis. Pas de texte libre long."""
    garde = ("notes", "note_min", "note_max", "centrage_gd", "centrage_hb", "centrage_dos", "coins", "bords", "surface", "defauts",
             "mesures", "quads", "centrage_reperes", "avis", "evaluable", "surface_jugeable", "centrage_algo", "modele")
    return {k: e.get(k) for k in garde if e.get(k) is not None}


def _photos(e):
    """Les photos de l'examen -> {devant, dos, rasante, rasante2, gros_plans: [{face, coin, f}]} (noms dans la banque)."""
    ph = e.get("photos") or []
    out = {}
    dev = _copier(ph[0]) if ph else None          # 3 nov 2026 (revue) : le devant d'abord ; sans lui, rien n'est copie
    if not dev:
        return out
    out["devant"] = dev
    for k, r in (("dos", ph[1] if len(ph) > 1 else None),
                 ("rasante", e.get("rasante")), ("rasante2", e.get("rasante2"))):
        n = _copier(r) if r else None
        if n:
            out[k] = n
    gp = []
    for g in e.get("gros_plans") or []:
        n = _copier(g.get("ref")) if g.get("ref") else None
        if n:
            gp.append({"face": g.get("face"), "coin": g.get("coin"), "f": n})
    if gp:
        out["gros_plans"] = gp
    return out


def _ecrire(rec):
    with _verrou:
        with open(_journal(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ajouter(carte, etat, retour=None, raison="retour"):
    """Une carte examinee revient du gradage (retour = {grade, compagnie, sous_notes, cert, lien}) ou l'utilisateur donne
    son avis sur un defaut (raison = 'avis'). L'appelant a deja verifie le OUI. -> {ok, id} | {ok: False, raison}"""
    try:
        e = json.loads(etat or "null") if isinstance(etat, str) else etat
    except ValueError:
        e = None
    if not e or not e.get("photos"):
        return {"ok": False, "raison": "pas d'examen avec photos"}
    if not _place_ok():
        return {"ok": False, "raison": "banque pleine"}
    with _verrou:
        return _ajouter(carte, e, retour, raison)


def _ajouter(carte, e, retour, raison):
    photos = _photos(e)
    if not photos.get("devant"):
        return {"ok": False, "raison": "photos introuvables"}
    rec = {"id": photos["devant"][:16], "le": datetime.now().strftime("%Y-%m-%d %H:%M"), "raison": raison, "compte": _compte_courant(),
           "carte": _carte(carte), "examen": _examen(e), "examen_le": str((carte or {}).get("etat_le") or "")[:16], "photos": photos}
    if retour:
        import etat_verite
        rec["verite"] = {"compagnie": str(retour.get("compagnie") or "")[:10], "grade": str(retour.get("grade") or "")[:20],
                         "note": etat_verite.note_de(retour.get("grade")), "sous_notes": sous_notes(retour.get("sous_notes")),
                         "cert": re.sub(r"[^A-Za-z0-9-]", "", str(retour.get("cert") or ""))[:20] or None,
                         "lien": str(retour.get("lien") or "")[:300] if str(retour.get("lien") or "").startswith("https://") else None}
    _ecrire(rec)
    return {"ok": True, "id": rec["id"]}


def _copier_octets(b):
    nom = hashlib.sha256(b).hexdigest()[:24] + ".jpg"
    cible = os.path.join(dossier(), "photos", nom)
    if not os.path.isfile(cible):
        with open(cible + ".tmp", "wb") as x:
            x.write(b)
        os.replace(cible + ".tmp", cible)
    return nom


def ajouter_reference(d):
    with _verrou:                                 # 3 nov 2026 (revue) : pas de menage des photos pendant la copie
        return _ajouter_reference(d)


def _ajouter_reference(d):
    """3 nov 2026 (Mathieu, ses slabs : « PSA 6 a cause de la surface : un 8 grave pres de la tete ») : une carte GRADEE
    ajoutee par l'admin, avec ce qu'on sait de sa note (le defaut connu). Le banc d'essai : on y mesure l'analyseur.
    d = {photos: [data URL devant, dos], compagnie, grade, sous_notes, cert, carte: {...}, defauts: [{zone, type, texte}],
    slab: bool}. -> {ok, id}"""
    import base64 as _b64
    import etat_verite
    def un(p):
        m = re.match(r"data:image/(?:jpeg|jpg|png|webp);base64,(.+)$", str(p or ""), re.S)
        if m:
            b = _b64.b64decode(m.group(1))
            if 2000 < len(b) < 8_000_000:
                return _copier_octets(b)
        return None
    ph = [n for n in (un(p) for p in (d.get("photos") or [])[:2]) if n]
    autres = {k: un(d.get(k)) for k in ("rasante", "rasante2") if d.get(k)}
    gp = [{"face": g.get("face"), "coin": g.get("coin"), "f": un(g.get("photo"))} for g in (d.get("gros_plans") or [])[:8] if isinstance(g, dict)]
    gp = [g for g in gp if g["f"]]
    if not ph:
        return {"ok": False, "erreur": "Ajoute au moins la photo du devant"}
    note = etat_verite.note_de(d.get("grade"))
    if note is None:
        return {"ok": False, "erreur": "Écris la note (ex. PSA 9)"}
    if not _place_ok():
        return {"ok": False, "erreur": "Banque pleine"}
    import bareme
    defauts = []
    for x in (d.get("defauts") or [])[:6]:
        t = re.sub(r"\s+", " ", str(x.get("texte") or "")).strip()[:200]
        typ = x.get("type") if x.get("type") in bareme.SURFACE or x.get("type") in ("blanchiment", "coin mou", "entaille", "ebrechure", "decentrage") else "autre"
        if t or x.get("zone"):
            defauts.append({"zone": str(x.get("zone") or "")[:30], "type": typ, "face": "dos" if x.get("face") == "dos" else "devant", "texte": t})
    rec = {"id": ph[0][:16], "le": datetime.now().strftime("%Y-%m-%d %H:%M"), "raison": "reference", "compte": "reference",
           "carte": {k: str(v)[:80] for k, v in (d.get("carte") or {}).items() if k in ("titre", "annee", "marque", "set_nom", "numero", "joueur", "parallele") and v},
           "photos": {"devant": ph[0], **({"dos": ph[1]} if len(ph) > 1 else {}), **{k: v for k, v in autres.items() if v}, **({"gros_plans": gp} if gp else {})},
           "slab": bool(d.get("slab", True)),
           "verite": {"compagnie": str(d.get("compagnie") or "PSA")[:10], "grade": str(d.get("grade"))[:20], "note": note,
                      "sous_notes": sous_notes(d.get("sous_notes")), "cert": re.sub(r"[^A-Za-z0-9-]", "", str(d.get("cert") or ""))[:20] or None,
                      "defauts_connus": defauts}}
    _ecrire(rec)
    return {"ok": True, "id": rec["id"]}


def _lire():
    try:
        with open(_journal(), encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]
    except (OSError, ValueError):
        return []


def exemples():
    """Les lignes regroupees par examen (la derniere gagne ; la verite et les avis gardes)."""
    par = {}
    for r in _lire():
        a = par.get(r["id"])
        if a and a.get("verite") and not r.get("verite"):
            r = dict(r, verite=a["verite"])
        par[r["id"]] = r
    return list(par.values())


def retirer_compte(cid=None, h=None):
    """Le OUI retire ou le compte supprime : ses exemples et les photos qui ne servent plus a personne. -> n retires"""
    h = h or compte_h(cid)
    with _verrou:
        lignes = _lire()
        garder = [r for r in lignes if r.get("compte") != h]
        n = len({r["id"] for r in lignes}) - len({r["id"] for r in garder})
        if len(garder) != len(lignes):
            tmp = _journal() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for r in garder:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.replace(tmp, _journal())
        # 3 nov 2026 (revue) : le menage des photos orphelines se fait toujours (meme sans ligne a retirer)
        utiles = set()
        for r in garder:
            p = r.get("photos") or {}
            utiles |= {v for k, v in p.items() if k != "gros_plans" and v} | {g["f"] for g in p.get("gros_plans") or []}
        dp = os.path.join(dossier(), "photos")
        for f in os.listdir(dp):
            if f not in utiles:
                try:
                    os.remove(os.path.join(dp, f))
                except OSError:
                    pass
    return n


def retirer_moi():
    import comptes
    return retirer_compte(comptes.courant() if comptes.MULTI else "local")


def stats():
    l = exemples()
    v = [r for r in l if (r.get("verite") or {}).get("note") is not None]
    ecarts = []
    for r in v:
        lo, hi = (r.get("examen") or {}).get("note_min"), (r.get("examen") or {}).get("note_max")
        if lo is not None:
            n = r["verite"]["note"]
            ecarts.append(0 if lo <= n <= (hi if hi is not None else lo) else (n - hi if n > (hi or lo) else n - lo))
    return {"exemples": len(l), "avec_note": len(v), "references": sum(1 for r in l if r.get("raison") == "reference"), "avec_sous_notes": sum(1 for r in v if r["verite"].get("sous_notes")),
            "avec_gros_plans": sum(1 for r in l if (r.get("photos") or {}).get("gros_plans")),
            "avec_avis": sum(1 for r in l if (r.get("examen") or {}).get("avis")),
            "comptes": len({r.get("compte") for r in l}), "dans_fourchette": sum(1 for x in ecarts if x == 0), "mo": round(_taille_mo(), 1),
            "max_mo": MAX_MO, "compagnies": {c: sum(1 for r in v if r["verite"]["compagnie"] == c) for c in sorted({r["verite"]["compagnie"] for r in v})}}


LISEZMOI = """Banque d'entrainement SlabCoach (exportee le {le})

dataset.jsonl : un examen par ligne.
  carte       : annee, set, joueur, variante (aucun renseignement sur la personne)
  examen      : ce que SlabCoach a estime (notes, fourchette, coins/bords/surface vus par l'IA, defauts avec position 0..1000
                dans la photo entiere de leur face, mesures de l'app : centrage par paires, blanchiment en mm2, silhouette,
                qualite de la photo ; quads = les 4 coins de la carte dans chaque photo, 0..1000, haut-gauche puis sens horaire ;
                avis = {{index du defaut: true (confirme) | false (rejete)}})
  verite      : la vraie note de la compagnie (et les sous-notes si l'utilisateur les a donnees ; cert / lien TAG DIG ;
                defauts_connus : la raison de la note quand on la connait, ex. « marque d'ecriture, un 8, pres de la tete »)
  raison      : retour (revenue du gradage), avis (defaut confirme / rejete), reference (carte gradee ajoutee par l'admin,
                souvent photographiee dans son slab : bonne pour la note, pas pour les coins au pixel pres)
  photos      : noms des fichiers dans photos/ (devant, dos, rasante, rasante2, gros_plans [{{face, coin, f}}])
Consentement : chaque exemple vient d'un compte qui a dit OUI (Reglages › Entrainement de l'IA). Il est retire de la
banque quand la personne retire son OUI ou supprime son compte : ne garde pas de copie de cet export plus de 90 jours.
"""


def exporter():
    """-> (chemin d'un zip temporaire, nom). Pour l'admin seulement (verifie par l'appelant). Ecrit sur le disque (la banque
    peut peser des Go) ; l'appelant l'efface apres l'envoi."""
    import tempfile
    l = exemples()
    fd, ch_zip = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    with zipfile.ZipFile(ch_zip, "w", zipfile.ZIP_STORED) as z:
        z.writestr("LISEZMOI.txt", LISEZMOI.format(le=datetime.now().strftime("%Y-%m-%d")))
        z.writestr("dataset.jsonl", "".join(json.dumps({k: v for k, v in r.items() if k != "compte"}, ensure_ascii=False) + "\n" for r in l))
        vus = set()
        for r in l:
            p = r.get("photos") or {}
            for f in [v for k, v in p.items() if k != "gros_plans" and v] + [g["f"] for g in p.get("gros_plans") or []]:
                ch = os.path.join(dossier(), "photos", f)
                if f not in vus and os.path.isfile(ch):
                    vus.add(f)
                    z.write(ch, "photos/" + f)
    return ch_zip, f"slabcoach-entrainement-{datetime.now().strftime('%Y%m%d')}.zip"
