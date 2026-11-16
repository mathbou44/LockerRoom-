"""
SLABCOACH - la preuve en direct, a l'epreuve des contestations (16 nov 2026).

Mathieu : « on doit etre bullet proof si jamais on se fait challenger ».

Un test sur le passe peut toujours etre soupconne (« vous avez choisi la regle apres coup »). Ici, chaque jour, AVANT de
connaitre la suite, SlabCoach fige ce qu'il dit :
  - le MARCHE : chaque Young Guns de base suivie (raw et PSA 10) a son prix du jour (mediane des 14 derniers jours),
    avec le moment de SlabIQ (creux, flambee, sortie...), ses points, le score SlabIQ complet de la carte et l'indice du
    joueur. C'est l'acheteur « sans SlabCoach » (il achete au prix du marche) et la base pour tester le score complet ;
  - le RADAR : chaque deal montre ce jour-la (prix, valeur, rabais, score SlabIQ, moment, verdict).

Rien ne peut etre change apres coup :
  1. le fichier du jour est ecrit une seule fois (JSON canonique : cles triees, sans espaces), jamais reecrit ;
  2. son empreinte SHA-256 est enchainee a celle de la veille (changer un vieux jour casse toute la chaine) ;
  3. l'empreinte est horodatee chez OpenTimestamps (ancree dans la chaine Bitcoin) : une preuve independante, verifiable
     par n'importe qui avec l'outil « ots », que le fichier existait a cette date ;
  4. la page publique /preuve montre les empreintes le jour meme ; les fichiers eux-memes 30 jours plus tard (les deals
     sont finis : on ne donne pas le Radar du jour gratuitement).

Puis, 30, 60 et 90 jours plus tard, le resultat se calcule avec les vraies ventes de la meme carte : sans SlabCoach (tout
le marche) contre avec SlabCoach (bon moment et au moins 10 % sous la valeur), et le score SlabIQ par tranches.
"""
import gzip
import hashlib
import json
import os
import threading
import urllib.request
from datetime import date, datetime, timedelta

_verrou = threading.Lock()
DELAI_PUBLIC_J = 30
HORIZONS = (30, 60, 90)
BON = ("creux", "creux_fort")
RABAIS_MIN = 10
OTS_CALENDRIERS = ("https://a.pool.opentimestamps.org", "https://b.pool.opentimestamps.org")
OTS_ENTETE = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94\x01\x08"   # en-tete .ots, v1, sha256


def dossier():
    import comptes
    d = os.path.join(comptes.DONNEES, "preuve")
    os.makedirs(d, exist_ok=True)
    return d


def _chaine_chemin():
    return os.path.join(dossier(), "chaine.json")


def chaine():
    try:
        with open(_chaine_chemin(), encoding="utf-8") as f:
            return json.load(f) or []
    except (OSError, ValueError):
        return []


def canonique(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


# -- ce que SlabCoach dit aujourd'hui ----------------------------------------------------------------------------------
def _marche(jour):
    import moment_yg
    L = moment_yg._lignes_banque()
    V = moment_yg.ventes_par_joueur(L)
    d0 = jour.toordinal()
    lignes = []
    for j, gg in V.items():
        e = moment_yg.etat(j) or {}
        for g, l in gg.items():
            px = sorted(p for o, p in l if d0 - 14 <= o < d0)
            if len(px) < 3:
                continue
            med = px[len(px) // 2] if len(px) % 2 else (px[len(px) // 2 - 1] + px[len(px) // 2]) / 2
            lignes.append({"t": "m", "j": j, "g": g, "prix": round(med, 2), "n14": len(px), "etat": e.get("etat") or "inconnu",
                           "points": moment_yg.points_de(j) if e else None})
    # le score SlabIQ complet de la carte (le meme moteur que l'app) et l'indice du joueur
    try:
        import score_slab
        items = [{"titre": f"Upper Deck Young Guns {x['j']} Rookie" + (" PSA 10" if x["g"] == "psa10" else ""), "joueur": x["j"]} for x in lignes]
        score_slab.annoter_lot(items)
        for x, it in zip(lignes, items):
            x["iq"] = it.get("score")
    except Exception as e:
        print("Preuve (score) : " + repr(e)[:160], flush=True)
    try:
        import indice_joueurs
        for x in lignes:
            ij = indice_joueurs.indice(x["j"]) or {}
            x["indice"] = ij.get("indice")
    except Exception:
        pass
    return lignes


def _radar():
    import deals
    import moment_yg
    d = deals.lire_vite() or {}
    L = [dict(x) for x in (d.get("deals") or [])[:400] if isinstance(x, dict) and x.get("item_id")]
    try:
        import score_slab
        score_slab.annoter_lot([x for x in L if x.get("score") is None])
    except Exception as e:
        print("Preuve (score radar) : " + repr(e)[:160], flush=True)
    out = []
    for x in L:
        if not x.get("moment") and x.get("joueur"):
            try:
                moment_yg.annoter(x)
            except Exception:
                pass
        m = x.get("moment") or {}
        total, port = x.get("total"), x.get("port") or 0
        rab = x.get("rabais")
        if rab is None and x.get("ratio"):
            rab = round(100 * (1 - float(x["ratio"])))
        elif rab is None and total and x.get("valeur"):
            rab = round(100 * (1 - float(total) / float(x["valeur"])))
        out.append({"t": "r", "id": str(x["item_id"]), "titre": str(x.get("titre") or "")[:200], "j": x.get("joueur"),
                    "g": moment_yg.classer(x.get("titre"), x.get("joueur")) if x.get("joueur") else None,
                    "prix": round(float(total) - float(port), 2) if total else None, "total": total, "valeur": x.get("valeur"),
                    "rabais": rab, "encan": bool(x.get("encan")), "fin": x.get("fin"), "iq": x.get("score"),
                    "etat": m.get("etat"), "verdict": (m.get("verdict") or {}).get("cle"), "vendeur": x.get("vendeur")})
    return out


def figer(aujourd=None, forcer_contenu=None):
    """Fige la journee (une seule fois). -> l'entree de la chaine, ou None si deja fait."""
    jour = aujourd or date.today()
    nom = jour.isoformat()
    with _verrou:
        ch = chaine()
        if any(e["jour"] == nom for e in ch):
            return None
        contenu = forcer_contenu if forcer_contenu is not None else {"jour": nom, "marche": _marche(jour), "radar": _radar()}
        corps = canonique({"version": 1, "fige_le": datetime.now().isoformat(timespec="seconds"), **contenu})
        h = hashlib.sha256(corps).hexdigest()
        prec = ch[-1]["chaine"] if ch else "0" * 64
        maillon = hashlib.sha256((prec + nom + h).encode()).hexdigest()
        chemin = os.path.join(dossier(), nom + ".json.gz")
        if os.path.exists(chemin):                       # jamais reecrit
            return None
        with open(chemin, "wb") as f:
            f.write(gzip.compress(corps, mtime=0))
        e = {"jour": nom, "sha256": h, "chaine": maillon, "n_marche": len(contenu.get("marche") or []),
             "n_radar": len(contenu.get("radar") or []), "ots": None}
        ch.append(e)
        tmp = _chaine_chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(ch, f, indent=1)
        os.replace(tmp, _chaine_chemin())
    horodater_en_attente()
    return e


# -- l'horodatage independant (OpenTimestamps) -------------------------------------------------------------------------
def _ots(h_hex):
    if os.environ.get("LR_OTS") == "0":
        return None
    dig = bytes.fromhex(h_hex)
    for cal in OTS_CALENDRIERS:
        try:
            req = urllib.request.Request(cal + "/digest", data=dig, method="POST",
                                         headers={"User-Agent": "SlabCoach", "Accept": "application/vnd.opentimestamps.v1"})
            with urllib.request.urlopen(req, timeout=15) as r:
                rep = r.read()
            if rep:
                return OTS_ENTETE + dig + rep
        except Exception as e:
            print(f"Preuve (OpenTimestamps {cal}) : " + repr(e)[:120], flush=True)
    return None


def horodater_en_attente():
    """Les jours pas encore horodates (panne reseau) le sont au prochain passage."""
    ch = chaine()
    change = False
    for e in ch:
        if e.get("ots"):
            continue
        b = _ots(e["sha256"])
        if b:
            with open(os.path.join(dossier(), e["jour"] + ".ots"), "wb") as f:
                f.write(b)
            e["ots"] = datetime.now().isoformat(timespec="minutes")
            change = True
    if change:
        with _verrou:
            cur = chaine()
            faits = {e["jour"]: e["ots"] for e in ch if e.get("ots")}
            for e in cur:
                if not e.get("ots") and faits.get(e["jour"]):
                    e["ots"] = faits[e["jour"]]
            tmp = _chaine_chemin() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cur, f, indent=1)
            os.replace(tmp, _chaine_chemin())


def lire_jour(nom):
    with open(os.path.join(dossier(), nom + ".json.gz"), "rb") as f:
        return gzip.decompress(f.read())


def verifier():
    """Recalcule chaque empreinte et toute la chaine. -> {ok, jours, erreurs}."""
    prec, err = "0" * 64, []
    ch = chaine()
    for e in ch:
        try:
            h = hashlib.sha256(lire_jour(e["jour"])).hexdigest()
        except OSError:
            err.append(e["jour"] + " : fichier absent")
            continue
        if h != e["sha256"]:
            err.append(e["jour"] + " : contenu modifie")
        m = hashlib.sha256((prec + e["jour"] + e["sha256"]).encode()).hexdigest()
        if m != e["chaine"]:
            err.append(e["jour"] + " : chaine brisee")
        prec = e["chaine"]
    return {"ok": not err, "jours": len(ch), "erreurs": err}


# -- le resultat, quand le temps a passe -------------------------------------------------------------------------------
def resultats(aujourd=None):
    """Pour chaque jour fige et chaque horizon ecoule : la valeur de la carte plus tard (mediane des vraies ventes de la meme
    carte, +/- 14 jours) contre le prix du jour. Sans SlabCoach = tout le marche ; avec = le Radar (bon moment et au moins
    10 % sous la valeur) ; et le score SlabIQ complet par tranches."""
    import moment_yg
    auj = (aujourd or date.today()).toordinal()
    V = moment_yg.ventes_par_joueur(moment_yg._lignes_banque())

    def plus_tard(j, g, d0, h):
        l = (V.get(j) or {}).get(g) or []
        px = sorted(p for o, p in l if d0 + h - 14 <= o <= d0 + h + 14)
        if len(px) < 3:
            return None
        return px[len(px) // 2] if len(px) % 2 else (px[len(px) // 2 - 1] + px[len(px) // 2]) / 2

    acc = {h: {"sans": [], "avec": [], "radar": [], "iq_haut": [], "iq_bas": []} for h in HORIZONS}
    jours = []
    for e in chaine():
        d0 = date.fromisoformat(e["jour"]).toordinal()
        if auj - d0 < min(HORIZONS):
            continue
        try:
            doc = json.loads(lire_jour(e["jour"]))
        except (OSError, ValueError):
            continue
        jours.append(e["jour"])
        for h in HORIZONS:
            if auj - d0 < h + 14:
                continue
            for x in doc.get("marche") or []:
                v = plus_tard(x["j"], x["g"], d0, h)
                if not v or not x.get("prix"):
                    continue
                c = 100 * (v / x["prix"] - 1)
                acc[h]["sans"].append(c)
                iq = x.get("iq")
                if iq is not None and iq >= 70:
                    acc[h]["iq_haut"].append(c)
                elif iq is not None and iq < 50:
                    acc[h]["iq_bas"].append(c)
            for x in doc.get("radar") or []:
                if not x.get("g") or not x.get("prix") or not x.get("j"):
                    continue
                v = plus_tard(x["j"], x["g"], d0, h)
                if not v:
                    continue
                c = 100 * (v / x["prix"] - 1)
                acc[h]["radar"].append(c)
                if x.get("etat") in BON and (x.get("rabais") or 0) >= RABAIS_MIN:
                    acc[h]["avec"].append(c)

    def res(l):
        if not l:
            return None
        s = sorted(l)
        med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
        return {"n": len(l), "mediane_pct": round(med, 1), "vaut_plus_pct": round(100 * sum(1 for x in l if x > 0) / len(l))}
    return {"ok": True, "jours_evalues": jours, "par_horizon": {str(h): {k: res(v) for k, v in acc[h].items()} for h in HORIZONS},
            "regle": {"avec": f"bon moment (creux) et au moins {RABAIS_MIN} % sous la valeur", "sans": "toutes les Young Guns au prix du marche"}}


def statut():
    ch = chaine()
    return {"jours": len(ch), "premier": ch[0]["jour"] if ch else None, "dernier": ch[-1] if ch else None,
            "horodates": sum(1 for e in ch if e.get("ots")), "public_apres_j": DELAI_PUBLIC_J}


def tour(aujourd=None):
    """Le passage quotidien : figer aujourd'hui, horodater ce qui attend, garder le resultat a jour."""
    out = {}
    e = figer(aujourd)
    if e:
        out["fige"] = {k: e[k] for k in ("jour", "n_marche", "n_radar", "sha256")}
    else:
        horodater_en_attente()
    try:
        r = resultats(aujourd)
        with open(os.path.join(dossier(), "resultats.json"), "w", encoding="utf-8") as f:
            json.dump({**r, "le": datetime.now().isoformat(timespec="minutes")}, f, ensure_ascii=False)
    except Exception as ex:
        out["resultats_erreur"] = repr(ex)[:160]
    return out


def resultats_garde():
    try:
        with open(os.path.join(dossier(), "resultats.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def public():
    """Ce que tout le monde peut voir : la chaine (empreintes le jour meme) ; les fichiers apres 30 jours."""
    lim = (date.today() - timedelta(days=DELAI_PUBLIC_J)).isoformat()
    return {"chaine": [{**e, "fichier": e["jour"] <= lim} for e in chaine()], "public_apres_j": DELAI_PUBLIC_J,
            "resultats": resultats_garde(), "verification": verifier()}
