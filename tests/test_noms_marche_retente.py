"""26 nov 2026 (journal, 15 h 29, juste apres un redemarrage : « Demande (noms du marche) : OperationalError('database is
locked') ») : la base etait occupee une seconde de trop, et la liste des joueurs du marche (les prospects et les legendes que
la LNH ne donne pas : Martone, Hagens, Messier...) restait VIDE pendant 24 heures. Maintenant : on reessaie 2 minutes plus
tard, et en attendant on garde la liste d'avant."""
import os, sys, sqlite3, tempfile, time
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import demande_legale as dl

ch = os.path.join(comptes.DONNEES, "base_ventes.sqlite")
c = sqlite3.connect(ch)
c.execute("CREATE TABLE ventes (cle TEXT PRIMARY KEY, q TEXT, titre TEXT, prix REAL, le TEXT)")
auj = time.strftime("%Y-%m-%d", time.gmtime())
for k in range(15):
    c.execute("INSERT INTO ventes VALUES (?,?,?,?,?)", ("m%d" % k, "porter martone", "2025-26 Upper Deck Porter Martone Young Guns #%d" % k, 20.0, auj))
c.commit(); c.close()

# 1. la base occupee : la liste d'avant reste, et on reessaie dans 2 minutes (pas dans 24 heures)
vrai = sqlite3.connect
def occupee(*a, **k):
    raise sqlite3.OperationalError("database is locked")
dl._MARCHE.update(le=0.0, noms=["Gavin Mckenna"])
sqlite3.connect = occupee
try:
    assert dl._noms_marche() == ["Gavin Mckenna"], "la liste d'avant, pas une liste vide"
    attente = dl._MARCHE["le"] + 86400 - time.time()
    assert 60 <= attente <= 125, "nouvel essai dans 2 minutes : %r" % attente
    assert dl._noms_marche() == ["Gavin Mckenna"], "pas un essai a chaque appel non plus"
finally:
    sqlite3.connect = vrai

# 2. deux minutes plus tard, la base repond : la vraie liste, gardee une journee
dl._MARCHE["le"] = time.time() - 86400 - 1
assert dl._noms_marche() == ["Porter Martone"], dl._MARCHE["noms"]
assert time.time() - dl._MARCHE["le"] < 5
sqlite3.connect = occupee
try:
    assert dl._noms_marche() == ["Porter Martone"], "gardee 24 h : la base n'est meme pas relue"
finally:
    sqlite3.connect = vrai
print("test_noms_marche_retente OK")
