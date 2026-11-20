"""20 nov 2026 (blindage avant le lancement) : deux comptes en ligne (MULTI), Alice et Bob. Chacun ne voit que ses donnees,
partout : TOUTES les fonctions de l'app (celles qui servent les ecrans) sont appelees pour chacun, et aucune reponse ne
contient une donnee de l'autre. Un travail sans compte est REFUSE (il retombait sur la base racine, celle de l'admin) ;
un fil lance pendant une requete garde son compte ; les taches de fond du serveur font un tour sans aucun refus. Reseau coupe."""
import os, sys, tempfile, time, socket, threading, json
D = tempfile.mkdtemp()
os.environ.update(LOCKERROOM_DONNEES=D, LOCKERROOM_MULTI="1", LR_CALME_DEMARRAGE_S="0", LR_RECHAUFFER_S="0",
                  LR_RECHAUFFER_BREAKS_S="0", LOCKERROOM_TACHES="0")
os.environ.pop("LR_GARDE_COMPTE", None)
os.environ.pop("LOCKERROOM_CODE", None)


def _coupe(*a, **k):
    raise OSError("reseau coupe (test)")


socket.create_connection = _coupe
socket.socket.connect = _coupe
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_exit = os._exit
os._exit = lambda *a: (_ for _ in ()).throw(RuntimeError("exit refuse (test)"))
import comptes, server, lockerroom, ebay_compte                     # noqa: E402
assert comptes.MULTI and comptes.GARDE == "refuser"
server._rythme_ok = lambda n: True
api = server.api

A, _ = comptes.trouver_ou_creer("ebay-alice", "alice", "production")
B, _ = comptes.trouver_ou_creer("ebay-bob", "bob", "production")
MARQUE = {A: "ALICEZQX", B: "BOBZQW"}

# 1. sans compte : refuse (avant : la base racine)
try:
    api.carte_sauver({"titre": "orpheline", "statut": "En stock"})
    raise AssertionError("une ecriture sans compte doit etre refusee")
except comptes.SansCompte:
    pass
assert not os.path.exists(os.path.join(D, "lockerroom.db")), "la base racine ne doit pas etre creee"
with comptes.systeme():                                  # le travail du serveur, dit tel quel : permis
    api.reglages_lire()
comptes.REFUSES.clear()

# 2. les donnees de chacun
for cid, m in MARQUE.items():
    with comptes.utiliser(cid):
        api.reglages_sauver({"nom_boutique": "Boutique " + m})
        api.carte_sauver({"titre": f"2023-24 Upper Deck Young Guns Connor Bedard #201 {m}", "statut": "En stock", "cout": 100,
                          "emplacement": "Collection"})
        v = api.carte_sauver({"titre": f"2024-25 Upper Deck Young Guns Macklin Celebrini #201 {m}", "statut": "Vendue"})
        c = api._db(); c.execute("UPDATE cartes SET prix_vendu=150, frais=20, vendu_le='2026-11-01', canal='eBay' WHERE id=?", (v["id"],)); c.commit(); c.close()
        api.couts_depuis_achats([{"item_id": "77" + m, "titre": f"2025-26 Upper Deck Young Guns Ivan Demidov #451 {m}", "quantite": 1,
                                  "cout_total": 60.0, "devise": "CAD", "date": "2026-11-02"}])
        c = api._db(); c.execute("UPDATE achats_ebay SET photo='-'"); c.commit(); c.close()
        try:
            api.client_sauver({"nom": "Client " + m, "courriel": m.lower() + "@exemple.test"})
        except Exception:
            pass

# 3. un fil lance pendant une requete garde son compte (comptes.fil) ; un threading.Thread nu ne l'a pas : refuse, rien ecrit
with comptes.utiliser(A):
    t = comptes.fil(api.carte_sauver, {"titre": "Fil " + MARQUE[A], "statut": "En stock"}); t.join(10)
    err = []

    def nu():
        try:
            api.carte_sauver({"titre": "Fil nu", "statut": "En stock"})
        except comptes.SansCompte as e:
            err.append(e)
    t3 = threading.Thread(target=nu); t3.start(); t3.join(10)
    assert err, "un fil sans compte doit etre refuse"
    c = api._db(); n_fil = c.execute("SELECT COUNT(*) FROM cartes WHERE titre=?", ("Fil " + MARQUE[A],)).fetchone()[0]; c.close()
    assert n_fil == 1, "le fil garde le compte d'Alice"
import sqlite3                                            # noqa: E402
_r = sqlite3.connect(os.path.join(D, "lockerroom.db"))
assert _r.execute("SELECT COUNT(*) FROM cartes").fetchone()[0] == 0, "rien dans la base racine"
_r.close()
comptes.REFUSES.clear()

# 4. toutes les fonctions de l'app, pour chacun, par le vrai serveur (session, /api/<nom>)
cl = server.app.test_client()
H = {"Origin": "http://localhost"}
SAUTER = ("redemarr", "supprimer_compte", "compte_supprimer", "deconnect", "effacer")
noms = sorted(n for n in dir(lockerroom.Api) if not n.startswith("_") and callable(getattr(lockerroom.Api, n))
              and not any(x in n for x in SAUTER) and n not in server._INTERNES)
from concurrent.futures import ThreadPoolExecutor, TimeoutError as TE   # noqa: E402
ex = ThreadPoolExecutor(max_workers=4)


def balayer(cid):
    with cl.session_transaction() as s:
        s.clear(); s["compte"] = cid; s["sid"] = "s-" + cid
    autre = [m for c, m in MARQUE.items() if c != cid][0]
    fuites, vus, ok = [], {}, 0
    for n in noms:
        f = ex.submit(lambda n=n: cl.post("/api/" + n, json=[], headers=H))
        try:
            r = f.result(timeout=20)
        except TE:
            continue
        t = r.get_data(as_text=True)
        ok += r.status_code == 200
        if autre in t or autre.lower() in t:
            fuites.append(n)
        if MARQUE[cid] in t:
            vus[n] = 1
    return fuites, vus, ok


for cid in (A, B):
    fuites, vus, ok = balayer(cid)
    assert ok > 120, ("le serveur doit repondre", ok)
    assert not fuites, (cid, "voit les donnees de l'autre compte dans", fuites)
    assert len(vus) >= 8 and "inventaire_liste" in vus, (cid, sorted(vus))      # ses propres donnees : bien la
    print(cid[:6], ok, "fonctions repondent,", len(vus), "montrent ses donnees, aucune celles de l'autre")
time.sleep(6)                                            # les fils lances par ces appels (photos, lots...)

# 5. sans session : rien
with cl.session_transaction() as s:
    s.clear()
r = cl.post("/api/inventaire_liste", json=[], headers=H)
assert r.status_code == 401 and MARQUE[A] not in r.get_data(as_text=True)

# 6. les taches de fond du serveur : un tour chacune, aucun refus (et les comptes restent separes)
ebay_compte.statut = lambda *a, **k: {"connecte": True, "cles_ok": True}
reel = time.sleep


class _Fin(Exception):
    pass


def _sommeil(n):
    th = threading.current_thread()
    if th.name.startswith("boucle") and n >= 30:
        th._n = getattr(th, "_n", 0) + 1
        if th._n >= 2:
            raise _Fin()
        return
    reel(min(n, 0.05))


server.time.sleep = _sommeil
fils = []
for nom in ("_ebay_auto", "_watch_boucle", "_valeurs_auto", "_revalider_deals", "_rechauffer", "_reprendre_banque_yg", "_moment_yg_boucle"):
    def _run(f=getattr(server, nom)):
        try:
            f()
        except _Fin:
            pass
    th = threading.Thread(target=_run, name="boucle" + nom, daemon=True); th.start(); fils.append(th)
for th in fils:
    th.join(300)
assert not [th.name for th in fils if th.is_alive()]
reel(4)
assert not comptes.REFUSES, [(q, f, p.strip().splitlines()[-6:]) for _, q, f, p in comptes.REFUSES[:3]]

# 7. a la fin : chaque base ne contient que son compte ; la racine n'a rien recu
for cid, m in MARQUE.items():
    autre = [x for c, x in MARQUE.items() if c != cid][0]
    for f in os.listdir(comptes.dossier(cid)):
        if f.endswith(".db"):
            c = sqlite3.connect(os.path.join(comptes.dossier(cid), f))
            dump = "\n".join(c.iterdump()); c.close()
            assert autre not in dump, (cid, f)
            assert m in dump
assert not any(m in open(os.path.join(D, f), errors="ignore").read() for f in os.listdir(D)
               if os.path.isfile(os.path.join(D, f)) and f.endswith((".db", ".json")) for m in MARQUE.values()), "la racine a recu des donnees"
print("OK test_isolation_comptes", len(noms), "fonctions x 2 comptes")
sys.stdout.flush()
_exit(0)
