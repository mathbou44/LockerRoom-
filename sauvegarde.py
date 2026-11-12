"""
SLABCOACH - la sauvegarde de nuit hors de Render (13 nov 2026).

Mathieu : « que cette data-la reste a nous toutes les annees a venir » ; il a choisi Cloudflare R2 (10 Go gratuits).
Chaque nuit (entre 3 h et 6 h, heure de Montreal), toutes les donnees du serveur (comptes, inventaires, photos, ventes,
modeles SlabIQ, journal) en un .zip, envoye dans un bucket R2. Les bases SQLite sont copiees par leur API de sauvegarde
(une copie coherente, meme pendant une ecriture). Les caches qui se refont seuls sont laisses de cote.
On garde : les 7 dernieres nuits + un dimanche par semaine pendant 8 semaines (le reste est efface du bucket).

Dans Render (Environment), l'admin met lui-meme :
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET (defaut : slabcoach-sauvegardes).
Sans ces cles : rien ne part (le .zip reste telechargeable a la main dans Admin).
"""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone

PREFIXE = "sauvegardes/slabcoach_"
GARDE_NUITS = 7
GARDE_DIMANCHES = 8
SAUTER = {"radar_garde", "__pycache__", "tmp"}
CACHES = ("cache_vendues.sqlite", ".verrou", ".tmp", ".lock", "-journal", "-wal", "-shm")
_ETAT = {"en_cours": False}
_verrou = threading.Lock()


def _racine():
    import lockerroom
    return lockerroom.DOSSIER


def _statut_chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "sauvegarde_r2.json")


def statut():
    try:
        with open(_statut_chemin(), encoding="utf-8") as f:
            s = json.load(f) or {}
    except (OSError, ValueError):
        s = {}
    return {**s, "actif": actif(), "en_cours": _ETAT["en_cours"], "bucket": os.environ.get("R2_BUCKET") or "slabcoach-sauvegardes"}


def _statut_ecrire(s):
    p = _statut_chemin()
    try:
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
    except OSError:
        pass


def actif():
    return all(os.environ.get(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))


def _fichiers(racine):
    for d, sous, fichiers in os.walk(racine):
        sous[:] = [x for x in sous if x not in SAUTER and not x.startswith(".")]
        for f in fichiers:
            if not f.endswith(CACHES):
                yield os.path.join(d, f)


def taille_donnees(racine=None):
    racine = racine or _racine()
    t = 0
    for ch in _fichiers(racine):
        try:
            t += os.path.getsize(ch)
        except OSError:
            pass
    return t


def faire_zip(dest, racine=None):
    """Toutes les donnees -> dest (.zip). Une base SQLite : sa copie coherente (API de sauvegarde), jamais le fichier vivant."""
    racine = racine or _racine()
    n = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as z:
        for ch in _fichiers(racine):
            if os.path.abspath(ch) == os.path.abspath(dest):
                continue
            nom = os.path.relpath(ch, racine)
            try:
                if ch.endswith((".sqlite", ".sqlite3", ".db")):
                    fd, copie = tempfile.mkstemp(suffix=".sqlite", dir=os.path.dirname(dest))
                    os.close(fd)
                    try:
                        src = sqlite3.connect("file:" + ch + "?mode=ro", uri=True, timeout=30)
                        dst = sqlite3.connect(copie)
                        try:
                            src.backup(dst)
                        finally:
                            dst.close()
                            src.close()
                        z.write(copie, nom)
                    finally:
                        try:
                            os.remove(copie)
                        except OSError:
                            pass
                else:
                    z.write(ch, nom)
                n += 1
            except (OSError, sqlite3.Error):
                pass
            if n % 200 == 0:
                time.sleep(0.01)                          # laisse passer les requetes de l'app (un seul serveur)
    return n


def _client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                        region_name="auto", config=Config(retries={"max_attempts": 5, "mode": "standard"}))


def a_garder(cles, auj=None):
    """Les cles (slabcoach_AAAA-MM-JJ.zip) a garder : les GARDE_NUITS plus recentes + un dimanche par semaine (8 semaines)."""
    auj = auj or datetime.now(timezone.utc).date()
    dates = {}
    for k in cles:
        try:
            dates[k] = datetime.strptime(k[len(PREFIXE):len(PREFIXE) + 10], "%Y-%m-%d").date()
        except ValueError:
            continue
    recentes = sorted(dates, key=lambda k: dates[k], reverse=True)[:GARDE_NUITS]
    lim = auj - timedelta(weeks=GARDE_DIMANCHES)
    dimanches = [k for k in dates if dates[k].weekday() == 6 and dates[k] >= lim]
    return set(recentes) | set(dimanches) | {k for k in cles if k not in dates}


def envoyer(client=None, bucket=None, racine=None):
    """Fait le .zip, l'envoie dans R2, efface les vieilles sauvegardes. -> le statut."""
    t0 = time.time()
    bucket = bucket or os.environ.get("R2_BUCKET") or "slabcoach-sauvegardes"
    racine = racine or _racine()
    s = {"le": datetime.now().isoformat(timespec="seconds"), "ok": False}
    tmpd = tempfile.gettempdir()
    taille = taille_donnees(racine)
    libre = shutil.disk_usage(tmpd).free
    if libre < taille * 1.1 + 200e6:
        s["erreur"] = "Pas assez d'espace temporaire (%d Mo de donnees, %d Mo libres)" % (taille // 1e6, libre // 1e6)
        _statut_ecrire({**statut(), **s, "dernier_essai": s["le"]})
        return s
    fd, z = tempfile.mkstemp(prefix="slabcoach_", suffix=".zip", dir=tmpd)
    os.close(fd)
    try:
        n = faire_zip(z, racine)
        cle = PREFIXE + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".zip"
        client = client or _client()
        client.upload_file(z, bucket, cle)
        s.update(ok=True, cle=cle, fichiers=n, taille=os.path.getsize(z), duree_s=round(time.time() - t0))
        try:
            cles = []
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIXE):
                cles += [o["Key"] for o in page.get("Contents") or []]
            garde = a_garder(cles)
            effacees = [k for k in cles if k not in garde]
            for k in effacees:
                client.delete_object(Bucket=bucket, Key=k)
            s.update(gardees=len(cles) - len(effacees), effacees=len(effacees))
        except Exception as e:
            s["menage_erreur"] = f"{type(e).__name__} : {e}"[:200]
    except Exception as e:
        s["erreur"] = f"{type(e).__name__} : {e}"[:300]
    finally:
        try:
            os.remove(z)
        except OSError:
            pass
    prev = statut()
    _statut_ecrire({k: v for k, v in {**prev, **s, "dernier_essai": s["le"],
                                      "dernier_ok": s["le"] if s["ok"] else prev.get("dernier_ok"),
                                      "derniere_taille": s.get("taille") or prev.get("derniere_taille")}.items()
                    if k not in ("actif", "en_cours", "bucket")})
    return s


def _heure_montreal():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Toronto")).hour
    except Exception:
        return (datetime.now(timezone.utc).hour - 5) % 24


def passe_si_besoin():
    """La boucle du serveur (chaque heure) : une sauvegarde par nuit, entre 3 h et 6 h (Montreal), si les cles sont la."""
    if not actif() or _ETAT["en_cours"] or not (3 <= _heure_montreal() < 6):
        return None
    s = statut()
    try:
        der = datetime.fromisoformat(str(s.get("dernier_essai"))[:19])
    except ValueError:
        der = None
    if der and datetime.now() - der < timedelta(hours=20):
        return None
    return lancer()


def lancer():
    with _verrou:
        if _ETAT["en_cours"]:
            return {"ok": True, "deja": True}
        _ETAT["en_cours"] = True

    def tache():
        try:
            r = envoyer()
            print("Sauvegarde R2 : " + json.dumps({k: r.get(k) for k in ("ok", "cle", "taille", "duree_s", "erreur")}), flush=True)
        except Exception as e:
            print("Sauvegarde R2 : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="sauvegarde-r2").start()
    return {"ok": True, "lance": True}
