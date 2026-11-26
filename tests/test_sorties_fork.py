"""26 nov 2026 (courriel de Render apres un push : « HTTP health check failed (timed out after 5 seconds) ») : le worker de
gunicorn est une copie (fork) du processus maitre. Si un fil du maitre ecrit sur la sortie standard a l'instant du fork, la
copie herite du verrou de la sortie a l'etat « pris » : chez elle, chaque fil qui ecrit (la ligne d'acces de chaque requete)
reste bloque pour toujours, et le serveur ne repond plus. On refait l'accident ici, pour vrai : SANS le remede l'enfant
reste bloque, AVEC le remede il ecrit normalement (print et logging)."""
import os, sys, subprocess, tempfile, threading, time
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
import sorties_fork

if not hasattr(os, "fork"):
    print("test_sorties_fork : pas de fork sur ce systeme (Windows) : rien a verifier")
    sys.exit(0)

SCENARIO = r'''
import logging, os, sys, threading, time
sys.path.insert(0, %(racine)r)
import sorties_fork
AVEC, DOS = %(avec)r, %(dos)r
if AVEC:
    assert sorties_fork.installer() is True and sorties_fork.installer() is False, "installe une seule fois"
jr = logging.getLogger("gunicorn.access.essai")
jr.setLevel(logging.INFO); jr.propagate = False
jr.addHandler(logging.StreamHandler(sys.stdout))           # comme gunicorn : la ligne d'acces de chaque requete


def bavard():                                              # un fil du « maitre » pris DANS une ecriture : le tuyau est plein
    sys.stdout.write("x" * 400000)
    sys.stdout.flush()


threading.Thread(target=bavard, daemon=True).start()
time.sleep(1.0)
pid = os.fork()
if pid == 0:
    res = {"print": False, "journal": False}

    def ecrire():
        print("ENFANT-PRINT", flush=True)
        res["print"] = True
        jr.info("ENFANT-JOURNAL")
        res["journal"] = True

    f = threading.Thread(target=ecrire, daemon=True)
    f.start(); f.join(8)
    with open(os.path.join(DOS, "enfant"), "w") as g:
        g.write("%%s %%s %%s" %% (res["print"], res["journal"], sorties_fork._ETAT["refaites"]))
    if AVEC:
        sys.exit(0)                                        # une vraie fin de processus, comme un worker qu'on arrete
    os._exit(0)
open(os.path.join(DOS, "fourche"), "w").close()            # le test peut maintenant vider le tuyau
_, st = os.waitpid(pid, 0)
with open(os.path.join(DOS, "fin"), "w") as g:
    g.write("%%s" %% (os.WEXITSTATUS(st) if os.WIFEXITED(st) else "signal %%s" %% os.WTERMSIG(st)))
os._exit(0)
'''


ENV = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}       # comme sur Render : une sortie AVEC tampon


def jouer(avec):
    dos = tempfile.mkdtemp()
    p = subprocess.Popen([sys.executable, "-W", "ignore", "-c", SCENARIO % {"racine": RACINE, "avec": avec, "dos": dos}],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
    t0 = time.time()
    while not os.path.exists(os.path.join(dos, "fourche")) and time.time() - t0 < 30:
        time.sleep(0.05)
    assert os.path.exists(os.path.join(dos, "fourche")), "le scenario n'a pas fourche : " + p.stderr.read().decode()[-400:]
    lu = {"out": b""}

    def vider():
        lu["out"] = p.stdout.read()

    v = threading.Thread(target=vider, daemon=True)
    v.start()
    try:
        p.wait(timeout=40)
    except subprocess.TimeoutExpired:
        p.kill()
        raise AssertionError("le scenario ne finit pas")
    v.join(10)
    with open(os.path.join(dos, "enfant")) as g:
        a, b, n = g.read().split()
    with open(os.path.join(dos, "fin")) as g:
        FIN[avec] = g.read()
    ERR[avec] = p.stderr.read().decode("utf-8", "replace")
    return a == "True", b == "True", int(n), lu["out"].decode("utf-8", "replace")


FIN, ERR = {}, {}


# ---- 1. l'accident existe : sans le remede, l'enfant n'arrive plus a ecrire (c'est ce que le serveur a vecu)
p_, j_, n_, _ = jouer(False)
assert (p_, j_, n_) == (False, False, 0), "sans le remede, l'enfant devait rester bloque sur la sortie : %r" % ((p_, j_, n_),)

# ---- 2. avec le remede : l'enfant ecrit, par print ET par logging, et ca sort bien sur la vraie sortie
p_, j_, n_, sortie = jouer(True)
assert p_ and j_, "avec le remede, l'enfant doit ecrire sans attendre : %r" % ((p_, j_),)
assert n_ == 1, "les sorties sont refaites une fois, dans l'enfant"
assert "ENFANT-PRINT" in sortie and "ENFANT-JOURNAL" in sortie, sortie[-300:]
assert sortie.count("x") >= 400000, "le maitre, lui, finit son ecriture normalement"
assert FIN[True] == "0" and "Fatal" not in ERR[True], "l'enfant s'arrete proprement : %r %s" % (FIN[True], ERR[True][-300:])
assert "reentrant call inside" in ERR[False] or FIN[False] == "0", "la signature de l'accident, la meme que dans le journal de Render"

# ---- 3. refaire() garde le meme descripteur et les memes reglages, et ne touche pas aux anciennes sorties
TROIS = r'''
import io, logging, sys
sys.path.insert(0, %(racine)r)
import sorties_fork
avant, avant_err = sys.stdout, sys.stderr
assert isinstance(avant.buffer, io.BufferedWriter), "le test doit rouler avec une sortie a tampon"
enc, lb, lb_err = avant.encoding, avant.line_buffering, avant_err.line_buffering
h = logging.StreamHandler(avant)
logging.getLogger("essai.sorties").addHandler(h)
ailleurs = logging.StreamHandler(io.StringIO())
logging.getLogger("essai.sorties").addHandler(ailleurs)
flux = ailleurs.stream
sorties_fork.refaire()
assert sys.stdout is not avant and sys.stdout.fileno() == 1 and sys.stderr is not avant_err and sys.stderr.fileno() == 2
assert sys.stdout.encoding == enc and sys.stdout.line_buffering == lb and sys.stderr.line_buffering == lb_err
assert h.stream is sys.stdout, "les journaux suivent la sortie neuve"
assert ailleurs.stream is flux, "un journal qui ecrit ailleurs n'est pas touche"
assert avant in sorties_fork._GARDEES and not avant.closed, "l'ancienne sortie n'est ni fermee ni liberee"
assert sys.__stdout__ is sys.stdout and sys.__stderr__ is sys.stderr
sorties_fork._fermer_les_anciennes()                       # a la fin du processus : marquees fermees, sans etre videes
assert avant.closed and avant_err.closed and not sys.stdout.closed
import os
os.write(1, b"")                                            # le descripteur, lui, reste ouvert
print("TROIS-OK", flush=True)
'''
r = subprocess.run([sys.executable, "-c", TROIS % {"racine": RACINE}], capture_output=True, env=ENV, timeout=60)
assert b"TROIS-OK" in r.stdout, (r.stdout + r.stderr).decode("utf-8", "replace")[-600:]

# ---- 4. le serveur l'installe au chargement, avant de lancer le moindre fil
src = open(os.path.join(RACINE, "server.py"), encoding="utf-8").read()
assert "sorties_fork.installer()" in src
assert src.index("sorties_fork.installer()") < src.index("def _prendre_verrou"), "installe tout en haut du serveur"

print("test_sorties_fork OK")
