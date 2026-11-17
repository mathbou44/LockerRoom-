"""
SLABCOACH - la validation du bareme SlabIQ, lettre par lettre, avec sa boucle de correction (17 nov 2026).

Mathieu : « trouve une methode de validation ultra precise avec boucle de correction pour chaque note de notre bareme » ;
« l'algo doit trouver un moyen de valider sa cote et, s'il n'est pas sur, m'ecrire ».

LA VERITE = LE MARCHE, mesure sur les ventes reelles (base_ventes, 365 jours ; aucun prix n'est montre au public) :
  1. LA SORTE (Young Guns, RPA, numerotee...) : sa PRIME = le prix de la carte / le prix median des cartes du MEME joueur
     (on compare des Hutson a des Hutson : la popularite du joueur ne fausse rien). Les sortes classees par prime, puis
     associees aux lettres dans les memes proportions que le bareme (quantiles) : la lettre « du marche ».
  2. LE JOUEUR : sa VALEUR = le prix de ses cartes / le prix median de la MEME sorte chez tous les joueurs (une YG de lui
     contre une YG typique). Les joueurs classes, associes aux lettres dans les memes proportions : sa lettre « du marche ».
  3. LA LETTRE FINALE : coupe dans le temps. Les cartes vues dans les premiers 60 % de la periode recoivent leur lettre ;
     dans les 40 % suivants, on compte leurs reventes. Les lettres doivent descendre en ordre (A+ se revend plus que A...) :
     chaque inversion est signalee, et l'accord global est une correlation de rangs (Spearman).
  STABILITE : chaque mesure est refaite sur les deux moities de la periode ; un ecart ne compte que s'il est le meme dans
     les deux (pas un hasard d'une semaine).

LA BOUCLE (chaque semaine) :
  - ecart de 2 crans et plus, stable, assez de ventes (sorte : 60 ; joueur : 25) -> correction AUTOMATIQUE (cotes_auto),
    jamais sur une cote donnee par l'expert ;
  - ecart de 1 cran stable, ou 2 crans pas encore stable ou avec peu de ventes -> une QUESTION a l'expert (« SlabIQ te
    demande ») ; sa reponse devient la cote pour de bon ;
  - une cote de l'expert que le marche contredit de 2 crans, stable -> une question de confirmation (jamais changee seule).
  Chaque passe garde son accord (par lettre et global) : on voit si le bareme s'ameliore.
"""
import json
import math
import os
import re
import statistics
import threading
import time
from datetime import datetime, timedelta

ORDRE = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "E"]
N_SORTE_AUTO, N_SORTE_Q = 60, 25
N_JOUEUR_AUTO, N_JOUEUR_Q = 25, 10
_ETAT = {"en_cours": False}
_verrou = threading.Lock()


def crans(a, b):
    """Le nombre de crans entre deux lettres (positif : b est plus haut que a)."""
    try:
        return ORDRE.index(a) - ORDRE.index(b)
    except ValueError:
        return 0


def _quantiles_vers_lettres(valeurs, lettres_actuelles):
    """valeurs {cle: mesure} et lettres_actuelles {cle: lettre} -> {cle: lettre du marche} : les cles classees par la mesure
    recoivent les lettres dans les MEMES proportions que les lettres actuelles (la mesure decide l'ordre, le bareme la forme)."""
    cles = sorted(valeurs, key=lambda k: -valeurs[k])
    dist = sorted((lettres_actuelles[k] for k in cles if lettres_actuelles.get(k) in ORDRE), key=ORDRE.index)
    if not cles or not dist:
        return {}
    return {k: dist[min(len(dist) - 1, int(i * len(dist) / len(cles)))] for i, k in enumerate(cles)}


def _spearman(xs, ys):
    def rangs(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    a, b = rangs(xs), rangs(ys)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return round(num / den, 3) if den else None


_RE_GRADE = re.compile(r"\b(?:psa|bgs|sgc|cgc|ksa|tag|beckett)\s*(?:gem\s*(?:mint|mt)?\s*)?\d+(?:\.\d)?\b|\bgem\s*mint\b|\bpop\s*\d+\b")


def cle_carte(titre):
    """L'identite d'une carte (pour compter ses reventes) : le titre normalise sans la note, sans le numero de serie
    (12/99 -> /99), sans les mots de vente."""
    import cartes_match
    t = cartes_match.norm(titre or "")
    t = _RE_GRADE.sub(" ", t)
    t = re.sub(r"\b\d+\s*/\s*(\d+)\b", r"/\1", t)
    t = re.sub(r"\b(?:rc|rookie|card|cards|nm|mint|mt|hot|read|look|wow|ssp|sp|lot|new|free|shipping|invest)\b", " ", t)
    return " ".join(sorted(set(t.split())))


_EQ = {"r": None}
# les mots qui ne sont QUE du hockey (« Score », « Prestige », « MVP » existent aussi au football)
_RE_HOCKEY_SUR = re.compile(r"\b(?:hockey|nhl|lnh|young guns?|o-pee-chee|opc|the cup|upper deck|parkhurst|tim hortons|sp authentic"
                            r"|future watch|ice premieres|sp game used|chl|ahl|ohl|whl|qmjhl|iihf|team canada|stanley cup)\b", re.I)


def _equipe_lnh(t):
    if _EQ["r"] is None:
        import cartes_match
        try:
            import sports
            mots = set(cartes_match.SURNOMS_EQUIPES)
            for v in (sports.SPORTS.get("hockey") or {}).get("equipes", {}).values():
                nom = v[0] if isinstance(v, (list, tuple)) else str(v)
                mots |= {nom.lower(), nom.split()[-1].lower()}
            mots = sorted(mots, key=len, reverse=True)
            _EQ["r"] = re.compile(r"\b(?:" + "|".join(re.escape(m) for m in mots if len(m) >= 4) + r")\b", re.I)
        except Exception:
            _EQ["r"] = re.compile(r"(?!x)x")
    return _EQ["r"].search(t or "")


LIBELLES = {"yg": ("Young Guns", "Young Guns"), "yg_variante": ("Young Guns parallèles", "Young Guns parallels"),
            "yg10": ("Young Guns gradée 10", "Graded 10 Young Guns"), "cup_rpa": ("The Cup RPA", "The Cup RPA"),
            "premier_rpa": ("Premier RPA", "Premier RPA"), "fw_auto": ("Future Watch Auto", "Future Watch Auto"),
            "rc_auto": ("Recrue autographe", "Rookie autograph"), "rc_vintage": ("Recrue vintage", "Vintage rookie"),
            "insert_a": ("Inserts vedettes (Clear Cut, Manga…)", "Star inserts (Clear Cut, Manga…)"), "ice_premieres": ("Ice Premieres", "Ice Premieres"),
            "opc_plat_auto": ("OPC Platinum auto", "OPC Platinum auto"), "bd_gems": ("Black Diamond auto", "Black Diamond auto"),
            "dazzlers": ("Dazzlers", "Dazzlers"), "auto": ("Auto", "Auto"), "patch": ("Patch", "Patch"), "ssp": ("SSP", "SSP"),
            "sp": ("SP / variation", "SP / variation"), "base": ("Base", "Base"), "yg_renewed": ("Young Guns Renewed", "Young Guns Renewed"),
            "insert_retro": ("Retro Young Guns d’un vétéran", "Veteran Retro Young Guns"), "numerotee": ("Numérotée", "Numbered"),
            "fluorescence": ("Fluorescence", "Fluorescence"), "case_hit": ("Case hit", "Case hit")}


def ventes(jours=365, chemin=None, max_n=60000):
    """[(titre, prix, jour)] des ventes de hockey connues (les plus recentes d'abord, au plus max_n)."""
    import sqlite3
    import comptes
    import score_slab
    ch = chemin or os.path.join(comptes.DONNEES, "base_ventes.sqlite")
    if not os.path.exists(ch):
        return []
    c = sqlite3.connect(ch)
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(ventes)")}
        jour = "le" if "le" in cols else "jour"
        lim = (datetime.now() - timedelta(days=jours)).strftime("%Y-%m-%d")
        rows = c.execute(f"SELECT titre, prix, substr({jour},1,10) FROM ventes WHERE prix >= 3 AND substr({jour},1,10) >= ? "
                         f"ORDER BY {jour} DESC LIMIT ?", (lim, int(max_n * 1.3))).fetchall()
    finally:
        c.close()
    out = []
    for t, p, j in rows:
        # la validation ne garde que du hockey SUR (Cam Ward le gardien et Cam Ward le quart-arriere ont le meme nom)
        if t and p and not score_slab.sport_autre(t) and (_RE_HOCKEY_SUR.search(t) or _equipe_lnh(t)):
            out.append((t, float(p), j))
        if len(out) >= max_n:
            break
    return out


def _annoter(rows):
    """Chaque vente : sa sorte (lettre, raison), son joueur, la lettre du joueur, la lettre finale, sa cle."""
    import bareme_iq as bq
    import cartes_match
    import indice_joueurs
    try:
        I = (indice_joueurs.lire() or {}).get("indice") or {}
    except Exception:
        I = {}
    Il = {k.lower(): v for k, v in I.items()}
    memo_j = {}
    out = []
    for t, p, j in rows:
        so, ra = bq.sorte(t)
        if ra == "lot_checklist":
            continue
        nom = cartes_match.joueur_du_titre(t)
        if not nom:
            continue
        nom = " ".join(w.capitalize() for w in nom.split())
        if nom not in memo_j:
            try:
                v = indice_joueurs.indice(nom) or Il.get(nom.lower()) or {}
            except Exception:
                v = Il.get(nom.lower()) or {}
            c = v.get("criteres") or {}
            # un nom que SlabIQ ne connait nulle part (« Wild Card », « Tusky ») ne sert pas a juger les joueurs
            connu = bool(v) or bq._legende(nom) or nom in bq.JOUEURS_EXPERT or bq._alias_expert(nom)
            memo_j[nom] = (*bq.note_joueur(nom, c, recrue=float(c.get("recrue") or 0) >= 90), bool(connu))
        nj, lj, src, connu = memo_j[nom]
        fin = bq.lettre(bq.note_finale(bq.NOTE[so], nj))
        k = cle_carte(t)
        out.append({"t": t, "p": p, "j": j, "so": so, "ra": ra, "nom": nom, "lj": lj, "src": src, "fin": fin, "connu": connu, "k": k})
    return out


def _mesures_sortes(A):
    """{raison: (prime mediane, n)} : prix / prix median du meme joueur."""
    par_j = {}
    for x in A:
        par_j.setdefault(x["nom"], []).append(x["p"])
    med_j = {k: statistics.median(v) for k, v in par_j.items() if len(v) >= 4}
    par_r = {}
    for x in A:
        m = med_j.get(x["nom"])
        if m:
            par_r.setdefault(x["ra"], []).append(x["p"] / m)
    # la LIQUIDITE : combien de fois la meme carte se vend (ventes / cartes differentes), relative a la moyenne : une Young
    # Guns raw se vend moins cher qu'une RPA, mais se revend sans cesse ; « recherchee » = les deux
    cles = {}
    for x in A:
        cles.setdefault(x["ra"], {}).setdefault(x.get("k") or cle_carte(x["t"]), 0)
        cles[x["ra"]][x.get("k") or cle_carte(x["t"])] += 1
    liq = {r: sum(v.values()) / len(v) for r, v in cles.items() if v}
    liq_moy = statistics.median(liq.values()) if liq else 1.0
    return {r: (math.sqrt(statistics.median(v) * (liq.get(r, liq_moy) / liq_moy)), len(v)) for r, v in par_r.items()}


def _mesures_joueurs(A):
    """{joueur: (valeur mediane, n)} : prix / prix median de la meme sorte chez tous les joueurs."""
    par_r = {}
    for x in A:
        par_r.setdefault(x["ra"], []).append(x["p"])
    med_r = {k: statistics.median(v) for k, v in par_r.items() if len(v) >= 10}
    par_j = {}
    for x in A:
        m = med_r.get(x["ra"])
        if m and x.get("connu"):
            par_j.setdefault(x["nom"], []).append(x["p"] / m)
    return {j: (statistics.median(v), len(v)) for j, v in par_j.items()}


def _lettres_finales(A):
    """La coupe dans le temps : les reventes (40 % de la fin) des cartes vues au debut (60 %), par lettre finale."""
    if len(A) < 200:
        return {}, None
    jours = sorted(x["j"] for x in A if x["j"])
    coupe = jours[int(len(jours) * 0.6)]
    avant, apres = {}, {}
    for x in A:
        k = x.get("k") or cle_carte(x["t"])
        if (x["j"] or "") < coupe:
            avant.setdefault(k, x["fin"])
        else:
            apres[k] = apres.get(k, 0) + 1
    par_l = {}
    for k, l in avant.items():
        par_l.setdefault(l, []).append(apres.get(k, 0))
    res = {l: {"cartes": len(v), "reventes": round(sum(v) / len(v), 3)} for l, v in par_l.items() if len(v) >= 30}
    ls = [l for l in ORDRE if l in res]
    rho = _spearman([-ORDRE.index(l) for l in ls], [res[l]["reventes"] for l in ls]) if len(ls) >= 3 else None
    return res, rho


def mesurer(rows):
    """La mesure complete, sur toute la periode et sur ses deux moities (la stabilite)."""
    A = _annoter(rows)
    A.sort(key=lambda x: x["j"] or "")
    h1, h2 = A[:len(A) // 2], A[len(A) // 2:]
    import bareme_iq as bq
    # -- les sortes
    S, S1, S2 = _mesures_sortes(A), _mesures_sortes(h1), _mesures_sortes(h2)
    lettre_r = {}
    for x in A:
        lettre_r.setdefault(x["ra"], x["so"])                  # la lettre de la sorte (une raison = une lettre, sauf numerotee)
    gardees = {r: v[0] for r, v in S.items() if v[1] >= N_SORTE_Q}
    mk, mk1, mk2 = (_quantiles_vers_lettres({r: M[r][0] for r in gardees if r in M}, lettre_r) for M in (S, S1, S2))
    sortes = []
    for r in gardees:
        l, lm = lettre_r.get(r), mk.get(r)
        if not lm or not l:
            continue
        e = crans(l, lm)
        e1, e2 = crans(l, mk1.get(r, l)), crans(l, mk2.get(r, l))
        sortes.append({"raison": r, "lettre": l, "marche": lm, "crans": e, "stable": e != 0 and (e1 * e > 0 and e2 * e > 0),
                       "prime": round(S[r][0], 2), "n": S[r][1]})
    # -- les joueurs
    J, J1, J2 = _mesures_joueurs(A), _mesures_joueurs(h1), _mesures_joueurs(h2)
    lettre_j, src_j = {}, {}
    for x in A:
        lettre_j.setdefault(x["nom"], x["lj"])
        src_j.setdefault(x["nom"], x["src"])
    gj = {j: v[0] for j, v in J.items() if v[1] >= N_JOUEUR_Q}
    mj, mj1, mj2 = (_quantiles_vers_lettres({j: M[j][0] for j in gj if j in M and M[j][1] >= 4}, lettre_j) for M in (J, J1, J2))
    joueurs = []
    for j in gj:
        l, lm = lettre_j.get(j), mj.get(j)
        if not lm or not l:
            continue
        e = crans(l, lm)
        e1, e2 = (crans(l, M.get(j)) if M.get(j) else 0 for M in (mj1, mj2))
        joueurs.append({"nom": j, "lettre": l, "marche": lm, "crans": e, "stable": e != 0 and e1 * e > 0 and e2 * e > 0,
                        "valeur": round(J[j][0], 2), "n": J[j][1], "source": src_j.get(j)})
    # -- les lettres finales (la coupe dans le temps)
    fin, rho = _lettres_finales(A)
    ls = [l for l in ORDRE if l in fin]
    inversions = [[a, b] for a, b in zip(ls, ls[1:]) if fin[b]["reventes"] > fin[a]["reventes"] * 1.05]
    # l'accord par lettre : la part des joueurs et des sortes de cette lettre que le marche met a moins d'un cran
    acc = {}
    for x in joueurs + sortes:
        a = acc.setdefault(x["lettre"], [0, 0])
        a[1] += 1
        a[0] += abs(x["crans"]) <= 1
    return {"le": datetime.now().isoformat(timespec="seconds"), "ventes": len(A), "sortes": sortes, "joueurs": joueurs,
            "lettres": fin, "rho": rho, "inversions": inversions,
            "accord": {l: round(a[0] / a[1], 3) for l, a in acc.items() if a[1]},
            "accord_global": round(sum(a[0] for a in acc.values()) / max(1, sum(a[1] for a in acc.values())), 3)}


def decider(m):
    """La boucle de correction : (corrections automatiques, questions) a partir d'une mesure."""
    import bareme_iq as bq
    import slabiq_expert
    d = slabiq_expert.lire()
    cotes_exp = {k.lower() for k in (d.get("cotes") or {})} | {k.lower() for k in bq.JOUEURS_EXPERT}
    auto_j, auto_s, Q = {}, {}, []
    for x in m.get("joueurs") or []:
        if not x["crans"]:
            continue
        expert = x["nom"].lower() in cotes_exp or x["source"] == "expert"
        fort = abs(x["crans"]) >= 2 and x["stable"] and x["n"] >= N_JOUEUR_AUTO
        if fort and not expert:
            auto_j[x["nom"]] = x["marche"]
        elif expert and abs(x["crans"]) >= 2 and x["stable"]:
            Q.append({"type": "joueur", "nom": x["nom"], "lettre": x["lettre"], "marche": x["marche"], "n": x["n"], "confirmer": True,
                      "raison": f"Tu l'as coté {x['lettre']}, mais ses cartes se vendent comme un {x['marche']} ({x['n']} ventes)",
                      "raison_en": f"You rated him {x['lettre']}, but his cards sell like a {x['marche']} ({x['n']} sales)"})
        elif not expert and (abs(x["crans"]) >= 2 or x["stable"]):
            Q.append({"type": "joueur", "nom": x["nom"], "lettre": x["lettre"], "marche": x["marche"], "n": x["n"],
                      "raison": f"SlabIQ dit {x['lettre']}, ses ventes disent {x['marche']} ({x['n']} ventes)",
                      "raison_en": f"SlabIQ says {x['lettre']}, his sales say {x['marche']} ({x['n']} sales)"})
    sortes_exp = set((d.get("sortes") or {}))
    for x in m.get("sortes") or []:
        if not x["crans"] or x["raison"] == "numerotee":
            continue                                # la numerotee a ses propres paliers (/10, /50, /199)
        if abs(x["crans"]) >= 2 and x["stable"] and x["n"] >= N_SORTE_AUTO and x["raison"] not in sortes_exp:
            Q.append({"type": "sorte", "nom": x["raison"], "lettre": x["lettre"], "marche": x["marche"], "n": x["n"], "urgent": True,
                      "raison": f"La sorte « {LIBELLES.get(x['raison'], (x['raison'],))[0]} » est notée {x['lettre']}, mais elle se vend comme une {x['marche']} (prime ×{x['prime']}, {x['n']} ventes)",
                      "raison_en": f"The card type “{LIBELLES.get(x['raison'], (0, x['raison']))[1]}” is rated {x['lettre']}, but sells like a {x['marche']} (premium ×{x['prime']}, {x['n']} sales)"})
        elif x["stable"] and x["raison"] not in sortes_exp:
            Q.append({"type": "sorte", "nom": x["raison"], "lettre": x["lettre"], "marche": x["marche"], "n": x["n"],
                      "raison": f"La sorte « {LIBELLES.get(x['raison'], (x['raison'],))[0]} » : notée {x['lettre']}, le marché dit {x['marche']} ({x['n']} ventes)",
                      "raison_en": f"Card type “{LIBELLES.get(x['raison'], (0, x['raison']))[1]}”: rated {x['lettre']}, the market says {x['marche']} ({x['n']} sales)"})
    # les sortes ne changent jamais seules (le bareme vient de l'expert) : une question, la plus urgente d'abord
    Q.sort(key=lambda q: (not q.get("urgent"), not q.get("confirmer"), -(q.get("n") or 0)))
    return auto_j, auto_s, Q


def iterer(rows=None):
    """Une passe : mesurer, decider, garder (cotes_auto, questions, historique de l'accord)."""
    import slabiq_expert
    rows = rows if rows is not None else ventes()
    if len(rows) < 500:
        d = slabiq_expert.lire()                     # on reessaie dans une semaine (pas a chaque tour de la boucle)
        d.setdefault("validation_hist", []).append({"le": datetime.now().isoformat(timespec="seconds"), "ok": False, "ventes": len(rows)})
        slabiq_expert.ecrire(d)
        return {"ok": False, "raison": "peu de ventes", "n": len(rows)}
    m = mesurer(rows)
    auto_j, _, Q = decider(m)
    d = slabiq_expert.lire()
    d["cotes_auto"] = auto_j
    d["validation"] = {k: m[k] for k in ("le", "ventes", "lettres", "rho", "inversions", "accord", "accord_global")}
    d["validation"]["sortes"] = sorted(m["sortes"], key=lambda x: -abs(x["crans"]))[:40]
    d["validation"]["auto"] = len(auto_j)
    d["questions_marche"] = Q[:200]
    h = d.setdefault("validation_hist", [])
    h.append({"le": m["le"], "accord": m["accord_global"], "rho": m["rho"], "inversions": len(m["inversions"]), "auto": len(auto_j), "questions": len(Q)})
    d["validation_hist"] = h[-60:]
    slabiq_expert.ecrire(d)
    try:
        import bareme_iq
        bareme_iq._APPRIS["t"] = 0.0
    except Exception:
        pass
    return {"ok": True, "ventes": m["ventes"], "accord": m["accord_global"], "rho": m["rho"], "inversions": m["inversions"],
            "auto": len(auto_j), "questions": len(Q)}


def passe_si_besoin():
    """Une fois par semaine (la boucle du serveur), en arriere-plan."""
    import slabiq_expert
    h = (slabiq_expert.lire().get("validation_hist") or [{}])[-1]
    try:
        if h and (datetime.now() - datetime.fromisoformat(h.get("le"))).days < 7:
            return None
    except (TypeError, ValueError):
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            print("Validation SlabIQ : %s" % json.dumps(iterer(), ensure_ascii=False)[:400], flush=True)
        except Exception as ex:
            print("Validation SlabIQ : " + repr(ex), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="validation-iq").start()
    return True
