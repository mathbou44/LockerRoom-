"""13 nov 2026 : la sauvegarde de nuit vers Cloudflare R2 (un faux S3 local, moto) : le .zip part, les bases SQLite sont des
copies coherentes, on garde 7 nuits + 8 dimanches, rien ne part sans les cles."""
import os, sys, tempfile, sqlite3, zipfile, io
from datetime import date, timedelta
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import sauvegarde
for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
    os.environ.pop(k, None)
assert not sauvegarde.actif() and sauvegarde.passe_si_besoin() is None
racine = tempfile.mkdtemp()
os.makedirs(os.path.join(racine, "photos")); os.makedirs(os.path.join(racine, "radar_garde"))
open(os.path.join(racine, "photos", "a.jpg"), "wb").write(b"x" * 1000)
open(os.path.join(racine, "radar_garde", "cache.json"), "w").write("{}")
open(os.path.join(racine, "x.tmp"), "w").write("tmp")
db = sqlite3.connect(os.path.join(racine, "ventes.sqlite")); db.execute("CREATE TABLE v(a)"); db.executemany("INSERT INTO v VALUES (?)", [(i,) for i in range(500)]); db.commit()
# une ecriture en cours (transaction ouverte) : la copie reste coherente (les 500 lignes validees)
db.execute("INSERT INTO v VALUES (999)")
# 1. le zip
z = os.path.join(tempfile.mkdtemp(), "s.zip")
n = sauvegarde.faire_zip(z, racine)
noms = zipfile.ZipFile(z).namelist()
assert "photos/a.jpg" in noms and "ventes.sqlite" in noms, noms
assert not any(x.startswith("radar_garde") or x.endswith(".tmp") for x in noms), noms
c = os.path.join(tempfile.mkdtemp(), "v.sqlite"); open(c, "wb").write(zipfile.ZipFile(z).read("ventes.sqlite"))
assert sqlite3.connect(c).execute("SELECT count(*) FROM v").fetchone()[0] == 500
db.rollback(); db.close()
# 2. la garde : 7 nuits + les dimanches de 8 semaines
auj = date(2026, 11, 13)
cles = [sauvegarde.PREFIXE + (auj - timedelta(days=i)).isoformat() + ".zip" for i in range(80)]
g = sauvegarde.a_garder(cles, auj)
assert all(sauvegarde.PREFIXE + (auj - timedelta(days=i)).isoformat() + ".zip" in g for i in range(7))
assert sauvegarde.PREFIXE + "2026-11-01.zip" in g and sauvegarde.PREFIXE + "2026-09-20.zip" in g   # des dimanches
assert sauvegarde.PREFIXE + "2026-11-02.zip" not in g and sauvegarde.PREFIXE + "2026-08-30.zip" not in g
# 3. l'envoi (un faux R2) et le menage
try:
    import boto3
    from moto import mock_aws
except ImportError:
    print('SAUVEGARDE R2 OK (sans moto : envoi non teste)'); sys.exit(0)
with mock_aws():
    cl = boto3.client("s3", region_name="us-east-1")
    cl.create_bucket(Bucket="slabcoach-sauvegardes")
    for k in cles[1:30]:
        cl.put_object(Bucket="slabcoach-sauvegardes", Key=k, Body=b"vieux")
    r = sauvegarde.envoyer(client=cl, bucket="slabcoach-sauvegardes", racine=racine)
    assert r["ok"] and r["taille"] > 0, r
    restantes = [o["Key"] for o in cl.list_objects_v2(Bucket="slabcoach-sauvegardes")["Contents"]]
    assert r["cle"] in restantes and len(restantes) < 30, (r, len(restantes))
    s = sauvegarde.statut()
    assert s["dernier_ok"] and s["derniere_taille"] and not s["actif"], s
print("SAUVEGARDE R2 OK", r["cle"], r["taille"], "gardees", r.get("gardees"), "effacees", r.get("effacees"))
