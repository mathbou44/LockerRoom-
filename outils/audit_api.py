"""24 nov 2026 (Mathieu : « repasse chaque fonction et calcul ; un audit intense avant le release »).

Chaque fonction de l'API, appelee comme l'app le fait (POST /api/<nom>, corps JSON), SANS reseau, par :
  - un compte GRATUIT (le compte demo, rempli) ;
  - personne (aucune session).
Pour chaque fonction : sans argument, avec des arguments plausibles (devines d'apres leur nom), puis avec des arguments tordus
(None, vide, texte geant, negatif, dictionnaire, liste). On releve :
  1. les ERREURS 500 (une exception non prevue : l'ecran dirait « Erreur du serveur ») ;
  2. les fonctions d'ADMIN qui repondent a un compte ordinaire ;
  3. les champs reserves (valeurs tirees des ventes eBay) qui sortent pour un compte ordinaire ;
  4. les fonctions qui repondent sans session ;
  5. les appels lents (1 s et plus, sans reseau).

    python3 outils/audit_api.py            -> le resume a l'ecran, le detail dans /tmp/audit_api.json
"""
import inspect
import json
import os
import socket
import sys
import tempfile
import time
import traceback

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.chdir(ICI)
os.environ.update(LOCKERROOM_DONNEES=tempfile.mkdtemp(prefix="audit_api_"), LOCKERROOM_MULTI="1", LOCKERROOM_DEMO_CODE="audit-local",
                  LOCKERROOM_TACHES="0", LR_CALME_DEMARRAGE_S="99999", LR_RECHAUFFER_S="99999", LOCKERROOM_SECRET="audit-local-secret")


def _hors_ligne(*a, **k):
    raise OSError("audit : hors ligne")


socket.socket.connect = _hors_ligne                      # aucun appel dehors : tout ce qui sort echoue tout de suite
socket.create_connection = _hors_ligne

import server      # noqa: E402
import comptes     # noqa: E402
import admin       # noqa: E402
from lockerroom import Api  # noqa: E402

server._premiere_synchro = lambda cid: None
server._rythme_ok = lambda nom: True
ERREURS = []
_vrai_noter = admin.noter_erreur


def _noter(quoi, e):
    try:
        f = traceback.extract_tb(e.__traceback__)[-1] if getattr(e, "__traceback__", None) else None
        ERREURS.append((quoi, type(e).__name__, str(e)[:160], f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" if f else ""))
    except Exception:
        pass


admin.noter_erreur = _noter
IOS = {"User-Agent": "Mozilla/5.0 (iPhone) LockerRoomiOS", "Origin": "http://localhost"}
c = server.app.test_client()
r = c.post("/demo", data={"code": "audit-local"}, headers=IOS)
assert r.status_code == 302, r.status_code
anonyme = server.app.test_client()

# ce qu'on n'appelle pas dans la tournee : efface le compte (teste a part) ou n'a de sens que sur le serveur
SAUTER = {"compte_supprimer"}
# un champ de ce nom dans la reponse d'un compte ordinaire = une valeur tiree des ventes (licence eBay : admin et Platine)
RESERVES = ("admin_vendu", "mediane", "comps", "ventes_recentes", "valeur_marche", "prix_suggere", "mise_max", "achat_max")
PLAUSIBLE = {"q": "Connor Bedard Young Guns", "titre": "2023-24 Upper Deck Young Guns Connor Bedard #451", "nom": "Connor Bedard", "joueur": "Connor Bedard",
             "prix": 25, "prix_max": 50, "montant": 10, "cout": 5, "n": 3, "jours": 30, "url": "https://www.ebay.ca/itm/123456789012", "item_id": "123456789012",
             "iid": "123456789012", "cid": "abcdefgh12", "pid": "2023-24-upper-deck-series-1", "sport": "hockey", "langue": "fr", "code": "12345678",
             "frais": False, "note": 10, "compagnie": "PSA", "texte": "bonjour", "raison": "essai", "etat": "fait", "v": "pro", "mode": "equipes"}
TORDUS = [("None", None), ("vide", ""), ("geant", "x" * 6000), ("negatif", -1), ("enorme", 10 ** 15), ("dict", {"a": 1}), ("liste", [1, "a", None]),
          ("html", "<script>alert(1)</script>"), ("sql", "' OR 1=1 --"), ("chemin", "../../etc/passwd"), ("bool", True)]


def deviner(nom_param):
    k = nom_param.lower()
    if k in PLAUSIBLE:
        return PLAUSIBLE[k]
    if k.endswith("_id") or k in ("id", "carte_id", "bid", "aid", "sid", "vid", "tid"):
        return 1
    if "prix" in k or "montant" in k or "valeur" in k or "cout" in k:
        return 20
    if "date" in k or k in ("le", "depuis"):
        return "2026-11-01"
    if k.startswith("nouv") or k in ("d", "donnees", "carte", "f", "filtres", "profil", "reglages", "c", "p", "champs"):
        return {}
    if k.endswith("s") or k in ("ids", "liste", "lot", "photos", "items"):
        return []
    return "essai"


def appeler(client, nom, args):
    t0 = time.time()
    n0 = len(ERREURS)
    try:
        r = client.post("/api/" + nom, data=json.dumps(args), headers={"Content-Type": "application/json"})
        code, corps = r.status_code, r.get_json(silent=True)
    except Exception as e:                                # le client de test laisse passer une exception hors du dispatcher
        code, corps = 599, {"erreur": repr(e)[:200]}
    return {"code": code, "s": round(time.time() - t0, 2), "corps": corps, "exc": ERREURS[n0:]}


def cles(o, prof=0, vu=None):
    vu = set() if vu is None else vu
    if prof > 6:
        return vu
    if isinstance(o, dict):
        for k, v in o.items():
            vu.add(str(k))
            cles(v, prof + 1, vu)
    elif isinstance(o, list):
        for v in o[:40]:
            cles(v, prof + 1, vu)
    return vu


def valeurs(o, cle, prof=0, out=None):
    """Les valeurs NON VIDES rangees sous cette cle, a tout niveau (un champ present mais vide, faux ou nul ne dit rien)."""
    out = [] if out is None else out
    if prof > 6:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            if k == cle and v not in (None, False, 0, "", [], {}):
                out.append(v)
            valeurs(v, cle, prof + 1, out)
    elif isinstance(o, list):
        for v in o[:40]:
            valeurs(v, cle, prof + 1, out)
    return out


methodes = sorted((n, f) for n, f in inspect.getmembers(Api, predicate=inspect.isfunction) if not n.startswith("_") and n not in SAUTER)
rapport = {"e500": [], "admin_ouvert": [], "reserves": [], "sans_session": [], "lents": [], "n_appels": 0, "n_methodes": len(methodes)}
t_debut = time.time()
for nom, f in methodes:
    params = [p for p in inspect.signature(f).parameters.values() if p.name != "self" and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)]
    essais = [("sans", [])]
    if params:
        essais.append(("plausible", [deviner(p.name) for p in params]))
        for nom_t, v in TORDUS:
            essais.append((nom_t, [v for _ in params]))
        if len(params) > 1:                               # un seul argument tordu, les autres plausibles
            for i, p in enumerate(params[:4]):
                for nom_t, v in (("None", None), ("dict", {"a": 1}), ("geant", "x" * 6000)):
                    a = [deviner(q.name) for q in params]
                    a[i] = v
                    essais.append((f"{p.name}={nom_t}", a))
        essais.append(("trop", [deviner(p.name) for p in params] + ["en trop", 2, None]))
    else:
        essais.append(("trop", ["en trop"]))
    for etiq, args in essais:
        res = appeler(c, nom, args)
        rapport["n_appels"] += 1
        if res["code"] >= 500:
            rapport["e500"].append({"f": nom, "args": etiq, "exc": res["exc"][-1][1:] if res["exc"] else [str((res["corps"] or {}).get("erreur"))[:120]]})
        if res["s"] >= 1.0:
            rapport["lents"].append({"f": nom, "args": etiq, "s": res["s"]})
        corps = res["corps"]
        if res["code"] == 200 and etiq in ("sans", "plausible"):
            ok = not (isinstance(corps, dict) and (corps.get("erreur") or corps.get("ok") is False))
            if nom.startswith("admin_") and ok:
                rapport["admin_ouvert"].append({"f": nom, "args": etiq, "apercu": json.dumps(corps, default=str)[:200]})
            fuite = sorted(k for k in RESERVES if valeurs(corps, k))
            if fuite:
                rapport["reserves"].append({"f": nom, "args": etiq, "champs": fuite})
    ra = appeler(anonyme, nom, [])
    rapport["n_appels"] += 1
    if ra["code"] == 200 and not (isinstance(ra["corps"], dict) and ra["corps"].get("erreur")):
        rapport["sans_session"].append({"f": nom, "apercu": json.dumps(ra["corps"], default=str)[:160]})
    elif ra["code"] >= 500:
        rapport["e500"].append({"f": nom, "args": "sans session", "exc": ra["exc"][-1][1:] if ra["exc"] else []})

rapport["duree_s"] = round(time.time() - t_debut, 1)
with open("/tmp/audit_api.json", "w", encoding="utf-8") as fh:
    json.dump(rapport, fh, ensure_ascii=False, indent=1, default=str)
par_f = {}
for e in rapport["e500"]:
    par_f.setdefault(e["f"], []).append(e)
print(f"{rapport['n_methodes']} fonctions, {rapport['n_appels']} appels, {rapport['duree_s']} s")
print(f"ERREURS 500 : {len(rapport['e500'])} appels dans {len(par_f)} fonctions")
for nom, l in sorted(par_f.items()):
    causes = sorted({" | ".join(str(x) for x in e["exc"]) for e in l})
    print(f"  {nom} ({len(l)} : {', '.join(sorted({e['args'] for e in l})[:6])}) -> {causes[0][:170]}" + (f"  (+{len(causes) - 1} autres causes)" if len(causes) > 1 else ""))
print(f"ADMIN ouvert a un compte ordinaire : {len(rapport['admin_ouvert'])}")
for e in rapport["admin_ouvert"]:
    print("  ", e["f"], e["args"], e["apercu"][:140])
print(f"Champs reserves vus par un compte ordinaire : {len(rapport['reserves'])}")
for e in rapport["reserves"]:
    print("  ", e["f"], e["args"], e["champs"])
print(f"Repondent sans session : {len(rapport['sans_session'])}")
for e in rapport["sans_session"]:
    print("  ", e["f"], e["apercu"][:120])
print(f"Lents (1 s et plus) : {len(rapport['lents'])}")
for e in sorted(rapport["lents"], key=lambda x: -x["s"])[:12]:
    print("  ", e["f"], e["args"], e["s"], "s")

# --test : les regles qui ne doivent JAMAIS casser (tests/test_audit_api.py)
if "--test" in sys.argv:
    arite = [e for e in rapport["e500"] if e["exc"] and e["exc"][0] == "TypeError" and "positional argument" in str(e["exc"][1]) and "_appel_partage" in str(e["exc"][2])]
    normaux = [e for e in rapport["e500"] if e["args"] in ("sans", "sans session")]
    assert not rapport["admin_ouvert"], rapport["admin_ouvert"][:3]
    assert not rapport["sans_session"], rapport["sans_session"][:3]
    assert not rapport["reserves"], rapport["reserves"][:3]
    assert not arite, arite[:3]
    assert not normaux, normaux[:3]
    assert rapport["n_methodes"] >= 300, rapport["n_methodes"]
    print("AUDIT API OK")
