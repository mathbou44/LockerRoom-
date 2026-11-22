"""
SLABCOACH - a acheter, a vendre : le marche de chaque joueur contre son propre passe (21 nov 2026).

Mathieu : « le marche de Caufield a enormement diminue et il joue bien ; le hype de sa saison de 50 buts a disparu ; c'est le
genre de joueur qu'on devrait avoir quand on cherche qui acheter. On doit detecter ce genre de baisse et capter tous les
joueurs dans la meme situation (bons joueurs, marche qui diminue, pas parce qu'ils produisent moins : le projecteur n'est
plus sur eux). Fais des baremes, change-les, ajuste les variables. Toujours sortir la liste des joueurs a acheter (creux) et
a vendre (sommet temporaire : tous les sommets finissent par retomber). Seulement les bonnes variables. »

1. LE NIVEAU d'un joueur, par tranches de 30 jours : chaque vente de ses cartes (nos archives) est comparee a la mediane de
   SA sorte de carte (marche_cles.sorte : famille + note + tirage) sur l'annee ; le niveau d'une tranche = la mediane de ces
   rapports (une sorte = une voix). On mesure le joueur, jamais une carte.
2. DEUX REPERES tires de ses 11 tranches d'avant : son SOMMET (la 2e plus haute : un mois fou ne fait pas un sommet) et sa
   MEDIANE (son niveau habituel).
3. LES VARIABLES, essayees sur 909 semaines-joueurs (95 joueurs, mai a septembre 2026, suite connue 46 a 74 jours apres) :
   - A ACHETER : un joueur ETABLI (120 matchs LNH et plus) a 20 % sous son sommet : son marche est 5 % plus haut deux mois
     apres dans 50 % des cas, contre 36 % au hasard ; a 10 % sous sa mediane : 53 %.
   - Une RECRUE dans le meme creux : 38 % contre 33 % (mediane -1 %) : son creux continue (le hype d'une sortie qui retombe).
     Les recrues ne sont donc JAMAIS dans « a acheter ».
   - Attendre que le prix se stabilise n'aide pas : 39 % ; pendant que ca baisse encore : 51 %.
   - A VENDRE : 30 % au-dessus de sa mediane ET a son plus haut : plus bas deux mois apres dans 76 % des cas, contre 47 % au
     hasard. Un joueur etabli : 82 % a +30 %, 88 % a +50 %, 94 % a +60 % (36 cas : peu).
   - L'achat ne monte pas a 90 % : 58 a 64 % remontent de 5 % et plus (71 % ne rebaissent pas). On affiche le taux MESURE de
     chaque signal, jamais plus.
4. LA VERIFICATION, refaite a chaque passe avec toutes les ventes accumulees : chaque seuil est rejoue sur le passe et on garde,
   de chaque cote, celui dont la borne basse (Wilson) bat le plus le hasard. Si aucun ne bat le hasard, la liste ne sort pas.
5. « IL JOUE BIEN » ne se rejoue pas sur le passe (on n'a pas l'historique de la forme) : c'est un filtre du jour, applique a
   l'affichage (pas en creux sur la glace, pas de mauvaise nouvelle).
6. « AU PLUS BAS DEPUIS N JOURS » (Mathieu : « comme sur Amazon : le prix le plus bas depuis X jours ») : le niveau du joueur,
   recalcule chaque semaine sur un an ; depuis combien de jours n'a-t-il pas ete aussi bas (ou aussi haut) ? Quand c'est le
   plus bas de tout ce qu'on a, on le dit (« de notre historique »).
7. LA BANQUE DE RAISONS (Mathieu : « enregistrer tous les declencheurs, nouvelles et stats, qui pourraient faire baisser sa
   valeur ; pour tous les joueurs ; on pourra ensuite associer d'avance un phenomene a une baisse, ou confirmer la baisse ») :
   a chaque passe, chaque signal (acheter / vendre) est garde dans un journal avec son niveau, son etat sur la glace et les
   nouvelles des 90 jours d'avant (mouvements.journal : blessure, echange, mauvaise nouvelle, honneur...). Deux ans gardes.
Le public voit des ecarts en %, jamais un prix.
"""
import bisect
import json
import math
import os
import statistics
import threading
import time
from datetime import date, datetime

VERSION = 6
PAS = 30                 # jours d'une tranche
N_TRANCHES = 11          # tranches d'avant (l'annee)
H0, H1 = 46, 74          # « deux mois apres »
N_SORTE_AN = 6           # ventes d'une sorte dans l'annee pour avoir sa mediane
N_SORTE_T = 2            # ventes d'une sorte dans une tranche
N_SORTES = 2             # sortes dans une tranche
N_T_MIN = 6              # ventes dans la tranche du jour
N_HIST = 3               # tranches connues avant
MATCHS_ETABLI = 120      # matchs LNH en carriere
BOUGE = 0.05             # « remonte » / « rebaisse » : 5 %
TOL_DEPUIS = 0.02                 # « au plus bas en N jours » : un niveau plus bas de moins de 2 % ne compte pas (le bruit)
SEMAINES = 26            # semaines rejouees
N_TEST_MIN = 30
ACHATS = (("sommet", 0.15), ("sommet", 0.20), ("sommet", 0.25), ("sommet", 0.30), ("mediane", 0.10), ("mediane", 0.15), ("mediane", 0.20),
          ("mediane", 0.25), ("mediane", 0.30), ("mediane", 0.35))
# 21 nov 2026 (Mathieu : « on fait pas mieux que 70 % pour l'achat ? » ; « le voir sur des plus grands time frames ») : un creux
# profond met plus de 2 mois a remonter. Mesure : -25 % sous sa normale -> 56 % a 2 mois, 72 % a 3 mois ; -30 % -> 62 % puis 80 %.
# Chaque bareme d'achat est donc verifie a 2, 3 et 4 mois ; le joueur porte le meilleur bareme qu'il remplit, AVEC son delai.
HORIZONS = ((2, 46, 74), (3, 76, 104), (4, 106, 134))
# 21 nov 2026 (Mathieu : « il faut donner une vraie plus-value, c'est primordial » ; « continue jusqu'a ce que le signal d'acheter
# soit efficace ») : « remonte de 5 % » ne paie pas les frais. Un signal d'achat est maintenant juge comme un VRAI PARI :
#   - un seul pari par joueur et par creux (le premier signal, puis rien pendant 10 semaines) : 10 semaines du meme creux ne
#     font pas 10 preuves ;
#   - gagnant = on revend plus cher qu'on a paye APRES les frais (eBay ~13 % + l'envoi : 15 %) ;
#   - le bareme est garde s'il a assez de paris, s'il gagne plus souvent que d'acheter n'importe quel joueur etabli (borne
#     prudente), si son taux PRUDENT (voir POIDS_PRUDENT) atteint 45 %, ET si son gain net median est d'au moins 5 %.
# Mesure le 21 nov (3-4 mois) : acheter n'importe qui : 22-25 % de gagnants, -17 % net ; creux de -20 % : ~45 %, ~0 % net ;
# -25 % : ~55 %, +0 a +8 % ; -30 % et plus : 65-73 %, +1 a +12 % net (15 paris, 12 joueurs).
FRAIS = 0.15
ESPACE_PARI_J = 70
N_PARIS_MIN = 12
# 21 nov 2026 (recherche : surapprentissage des backtests, Bailey et Lopez de Prado ; « haircut » de Harvey et Liu ; Bayes
# empirique, Efron et Morris) : quand on essaie 30 baremes sur 15 paris, le meilleur a toujours l'air trop beau. Le taux MONTRE
# est donc le taux PRUDENT : (gagnes + hasard x 10) / (paris + 10), comme si on avait deja vu 10 paris au taux du hasard.
# 11 gagnes sur 15 = 73 % brut -> 54 % prudent. C'est lui qui decide si un bareme est garde et combien de barres on montre.
POIDS_PRUDENT = 10
TAUX_MIN_ACHAT = 0.45          # « efficace » : un taux prudent d'au moins 45 % (le hasard est a 21-25 %)...
GAIN_NET_MIN = 5.0             # ... et le gain net median vaut la peine (5 % et plus) ; -20 % a 4 mois (51 %, +1 %) ne passe pas
VENTES = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60)
_ETAT = {"mt": None, "d": None, "en_cours": False, "vu": 0.0}
_verrou = threading.Lock()


def _fen(l, a, b):
    """Les prix de l (trie par jour) dont le jour est dans ]a, b]."""
    return [p for _, p in l[bisect.bisect_right(l, (a, 1e18)):bisect.bisect_right(l, (b, 1e18))]]


def _niveau(sj, ref, a, b):
    r, n = [], 0
    for k, m in ref.items():
        f = _fen(sj[k], a, b)
        if len(f) >= N_SORTE_T:
            r.append(statistics.median(f) / m)
            n += len(f)
    return (statistics.median(r), n) if len(r) >= N_SORTES and n >= N_T_MIN else (None, n)


def point(sj, jour, suite=False):
    """{niveau, n, sommet, mediane, prec, apres?} du joueur au jour (ordinal), ou None (pas assez de ventes)."""
    ref = {}
    for k, l in sj.items():
        f = _fen(l, jour - 365, jour)
        if len(f) >= N_SORTE_AN:
            ref[k] = statistics.median(f)
    if len(ref) < N_SORTES:
        return None
    niv, n = _niveau(sj, ref, jour - PAS, jour)
    if niv is None:
        return None
    hist = [_niveau(sj, ref, jour - (i + 1) * PAS, jour - i * PAS)[0] for i in range(1, N_TRANCHES + 1)]
    h = sorted((x for x in hist if x is not None), reverse=True)
    if len(h) < N_HIST:
        return None
    out = {"niveau": niv, "n": n, "sommet": h[1] if len(h) >= 4 else h[0], "mediane": statistics.median(h), "prec": hist[0]}
    if suite:
        h0, h1 = suite if isinstance(suite, tuple) else (H0, H1)
        out["apres"] = _niveau(sj, ref, jour + h0, jour + h1)[0]
    return out


def _depuis(sj, jour, niveau, semaines=52):
    """{bas_depuis_j, haut_depuis_j, hist_j} : le niveau d'aujourd'hui est le plus bas / le plus haut des N derniers jours (pas de
    7 jours, un an). bas_depuis_j == hist_j : le plus bas de tout notre historique."""
    ref = {}
    for k, l in sj.items():
        f = _fen(l, jour - 365, jour)
        if len(f) >= N_SORTE_AN:
            ref[k] = statistics.median(f)
    pts = []
    for i in range(1, semaines + 1):
        v = _niveau(sj, ref, jour - 7 * i - PAS, jour - 7 * i)[0]
        if v is not None:
            pts.append((7 * i, v))
    if len(pts) < 6:
        return {}
    hist = pts[-1][0]
    # comme « le prix le plus bas en 30 jours » : aucun niveau des N derniers jours n'etait plus bas qu'aujourd'hui (a 2 % pres,
    # le bruit) ; un joueur pose au fond de son creux depuis un mois reste « au plus bas en 12 mois »
    bas = next((j - 7 for j, v in pts if v < niveau * (1 - TOL_DEPUIS)), hist)
    haut = next((j - 7 for j, v in pts if v > niveau * (1 + TOL_DEPUIS)), hist)
    return {"bas_depuis_j": bas, "haut_depuis_j": haut, "hist_j": hist}


def _chemin_signaux():
    import comptes
    return os.path.join(comptes.DONNEES, "marche_signaux.json")


def signaux():
    try:
        with open(_chemin_signaux(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def _noter_signaux(etats, jour):
    """La banque de raisons : {joueur: [{le, signal, sous_sommet_pct, vs_mediane_pct, glace, raisons: [{date, type, titre}]}]} ;
    un joueur dont le signal continue n'est pas renote chaque jour (une ligne par semaine au plus)."""
    try:
        import mouvements
        J = mouvements.journal()
    except Exception:
        J = {}
    try:
        import indice_joueurs
        I = (indice_joueurs.lire() or {}).get("indice") or {}
    except Exception:
        I = {}
    d0 = (date.fromisoformat(jour).toordinal() - 90)
    lim = date.fromordinal(date.fromisoformat(jour).toordinal() - 730).isoformat()
    with _verrou:
        B = signaux()
        for nom, e in etats.items():
            if not e.get("signal"):
                continue
            l = B.setdefault(nom, [])
            if l and l[-1].get("signal") == e["signal"] and date.fromisoformat(l[-1]["le"]).toordinal() > date.fromisoformat(jour).toordinal() - 7:
                continue
            v = I.get(nom) or {}
            cx = v.get("creux") or {}
            rs = [{"date": x.get("date"), "type": x.get("type"), "titre": str(x.get("titre") or "")[:120]}
                  for x in (J.get(nom) or []) if str(x.get("date") or "") >= date.fromordinal(d0).isoformat()][-8:]
            l.append({"le": jour, "signal": e["signal"], "sous_sommet_pct": e.get("sous_sommet_pct"), "vs_mediane_pct": e.get("vs_mediane_pct"),
                      "glace": {"pastilles": [k for k in (v.get("pastilles") or []) if k in ("en_feu", "en_creux", "rebond", "en_hausse")],
                                "creux": cx.get("etat"), "ecart_pct": cx.get("ecart_pct")}, "raisons": rs})
            B[nom] = [x for x in l if x["le"] >= lim][-120:]
        tmp = _chemin_signaux() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(B, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, _chemin_signaux())


def signal_achat(x, regle):
    quoi, s = regle
    return x["niveau"] <= x[quoi] * (1 - s)


def signal_vente(x, s):
    return x["niveau"] >= x["mediane"] * (1 + s) and x["niveau"] >= max(x["sommet"], x["prec"] or 0)


def wilson(k, n, z=1.96):
    if not n:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


def points_passes(S, fin, semaines=SEMAINES, h0=None, h1=None):
    out = []
    h0, h1 = (H0, H1) if h0 is None else (h0, h1)
    for jour in range(fin - h1, fin - h1 - 7 * semaines, -7):
        for j, sj in S.items():
            x = point(sj, jour, suite=(h0, h1))
            if x and x.get("apres") is not None:
                x["j"] = j
                x["jour"] = jour
                out.append(x)
    return out


def verifier(P, etablis):
    """-> {achat: {regle, taux, borne, n, base, gain_med, actif, essais}, vente: {...}} ; les achats : joueurs etablis seulement."""
    monte = lambda x: x["apres"] >= x["niveau"] * (1 + BOUGE)
    baisse = lambda x: x["apres"] <= x["niveau"] * (1 - BOUGE)

    def cote(Q, regles, sig, f, nom):
        base = (sum(1 for x in Q if f(x)) / len(Q)) if Q else None
        essais, best = [], None
        for r in regles:
            l = [x for x in Q if sig(x, r)]
            k = sum(1 for x in l if f(x))
            e = {"regle": list(r) if isinstance(r, tuple) else r, "n": len(l), "joueurs": len({x["j"] for x in l}),
                 "taux": round(k / len(l), 3) if l else None, "borne": round(wilson(k, len(l)), 3),
                 "gain_med": round(statistics.median([x["apres"] / x["niveau"] - 1 for x in l]) * 100, 1) if l else None}
            essais.append(e)
            if len(l) >= N_TEST_MIN and base is not None and e["borne"] > base and (best is None or e["borne"] > best["borne"]):
                best = e
        jj = [x["jour"] for x in Q if x.get("jour")]
        out = {"base": round(base, 3) if base is not None else None, "base_n": len(Q), "essais": essais, "actif": best is not None,
               "du": date.fromordinal(min(jj)).isoformat() if jj else None, "au": date.fromordinal(max(jj)).isoformat() if jj else None,
               "apres_j": [H0, H1], "bouge": BOUGE, "n_min": N_TEST_MIN}
        if best:
            out.update({k: best[k] for k in ("regle", "taux", "borne", "n", "joueurs", "gain_med")})
        return out
    E = [x for x in P if x["j"] in etablis]
    # les ventes : les joueurs etablis a part (leur sommet retombe plus surement : 82 % a +30 %, 88 % a +50 %)
    return {"achat": cote(E, ACHATS, signal_achat, monte, "achat"), "vente": cote(P, VENTES, signal_vente, baisse, "vente"),
            "vente_etablis": cote(E, VENTES, signal_vente, baisse, "vente")}


def paris(l):
    """Un pari par joueur et par creux : le premier signal, puis rien pendant ESPACE_PARI_J jours."""
    out, vu = [], {}
    for x in sorted(l, key=lambda x: x["jour"]):
        if x["jour"] - vu.get(x["j"], -10 ** 9) >= ESPACE_PARI_J:
            out.append(x)
            vu[x["j"]] = x["jour"]
    return out


def verifier_achat(P, etablis, mois):
    """Les baremes d'achat juges comme des paris, apres les frais -> {base, base_n, essais: [{regle, mois, n, joueurs, taux, borne,
    gain_med, base, ok}], du, au}. taux = la part des paris gagnants apres les frais ; gain_med = le gain net median (%)."""
    net = lambda x: (x["apres"] / x["niveau"]) * (1 - FRAIS) - 1
    E = [x for x in P if x["j"] in etablis]
    base = (sum(1 for x in E if net(x) > 0) / len(E)) if E else None
    essais = []
    for r in ACHATS:
        l = paris([x for x in E if signal_achat(x, r)])
        k = sum(1 for x in l if net(x) > 0)
        e = {"regle": list(r), "mois": mois, "n": len(l), "gagnes": k, "joueurs": len({x["j"] for x in l}), "taux_brut": round(k / len(l), 3) if l else None,
             "taux": round((k + (base or 0) * POIDS_PRUDENT) / (len(l) + POIDS_PRUDENT), 3) if l else None,
             "borne": round(wilson(k, len(l)), 3), "gain_med": round(statistics.median([net(x) for x in l]) * 100, 1) if l else None,
             "base": round(base, 3) if base is not None else None}
        e["ok"] = bool(len(l) >= N_PARIS_MIN and base is not None and e["borne"] > base and e["taux"] >= TAUX_MIN_ACHAT
                       and (e["gain_med"] or 0) >= GAIN_NET_MIN)
        essais.append(e)
    jj = [x["jour"] for x in E if x.get("jour")]
    return {"base": round(base, 3) if base is not None else None, "base_n": len(E), "essais": essais,
            "du": date.fromordinal(min(jj)).isoformat() if jj else None, "au": date.fromordinal(max(jj)).isoformat() if jj else None}


def _etablis(base):
    out = set()
    for nom, v in (base or {}).items():
        try:
            if int((((v or {}).get("nhl") or {}).get("carriere") or {}).get("gamesPlayed") or 0) >= MATCHS_ETABLI:
                out.add(_titre(nom))
        except (TypeError, ValueError):
            pass
    return out


def _titre(n):
    import marche_cles
    return marche_cles._titre(n)


def calculer(ventes=None, base=None, aujourd=None):
    import marche_cles
    aujourd = aujourd or date.today()
    if base is None:
        import demande_legale
        base = (demande_legale.lire() or {}).get("joueurs") or {}
    if ventes is None:
        import base_ventes
        ventes = base_ventes.ventes_titres(365 + PAS + H1 + 7 * SEMAINES)
    noms = {_titre(n) for n in base}                     # seulement les joueurs connus (jamais « Wild Card », « Complete Your »)
    etab = _etablis(base)
    S = marche_cles.series(ventes, noms)
    fin = aujourd.toordinal()
    V = verifier(points_passes(S, fin), etab)
    # les achats : des paris, apres les frais, a 2, 3 et 4 mois ; chaque essai dit son delai et SON hasard
    P2 = points_passes(S, fin)
    a = verifier_achat(P2, etab, HORIZONS[0][0])
    for mois, h0, h1 in HORIZONS[1:]:
        b = verifier_achat(points_passes(S, fin, h0=h0, h1=h1), etab, mois)
        a["essais"] += b["essais"]
        if b.get("du") and (not a.get("du") or b["du"] < a["du"]):
            a["du"] = b["du"]
    bons = [t for t in a["essais"] if t["ok"]]
    a.update(actif=bool(bons), essayes=len(a["essais"]), n_min=N_PARIS_MIN, frais=FRAIS, bouge=BOUGE)
    if bons:
        m = max(bons, key=lambda t: t["borne"])
        a.update({k: m[k] for k in ("regle", "taux", "borne", "n", "joueurs", "gain_med", "mois")})
    V["achat"] = a
    etats = {}
    for nom, sj in S.items():
        x = point(sj, fin)
        if not x:
            continue
        e = {"niveau": round(x["niveau"], 3), "n": x["n"], "sous_sommet_pct": round((x["niveau"] / x["sommet"] - 1) * 100),
             "vs_mediane_pct": round((x["niveau"] / x["mediane"] - 1) * 100), "etabli": nom in etab,
             "mois_pct": round((x["niveau"] / x["prec"] - 1) * 100) if x["prec"] else None}
        a = V["achat"]
        # toute regle qui bat le hasard compte ; la meilleure que le joueur remplit dit la force du signal (son taux mesure)
        if nom in etab and a.get("base") is not None:
            ok = [t for t in a["essais"] if t.get("ok") and signal_achat(x, tuple(t["regle"]))]
            if ok:
                m = max(ok, key=lambda t: t["borne"])
                e.update(signal="acheter", taux=m["taux"], regle=m["regle"], mois=m.get("mois"), gain=m.get("gain_med"))
        # a vendre : un joueur etabli est juge sur les etablis (leur sommet retombe plus surement) ; sans bareme valable la
        # (trop peu de cas), sur tous les joueurs
        for v in ([V.get("vente_etablis") or {}] if nom in etab else []) + [V["vente"]]:
            if "signal" in e or v.get("base") is None:
                continue
            ok = [t for t in v["essais"] if t["n"] >= N_TEST_MIN and t["borne"] > v["base"] and signal_vente(x, t["regle"])]
            if ok:
                m = max(ok, key=lambda t: t["borne"])
                e.update(signal="vendre", taux=m["taux"], regle=m["regle"])
                break
        e.update(_depuis(sj, fin, x["niveau"]))
        etats[nom] = e
    try:
        _noter_signaux(etats, aujourd.isoformat())
    except Exception as ex:
        print("Marche des joueurs (banque de raisons) : " + repr(ex)[:160], flush=True)
    return {"v": VERSION, "le": datetime.now().isoformat(timespec="seconds"), "jour": aujourd.isoformat(), "verif": V, "etats": etats}


# -- le fichier -----------------------------------------------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "marche_joueurs.json")


def lire():
    p = _chemin()
    m_ = time.monotonic()
    if _ETAT["d"] is not None and m_ - _ETAT["vu"] < 5:
        return _ETAT["d"]
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    _ETAT["vu"] = m_
    if _ETAT["d"] is None or _ETAT["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                d_ = json.load(f)
            _ETAT["d"] = d_ if d_.get("v") == VERSION else {}
            _ETAT["mt"] = mt
        except (OSError, ValueError):
            return {}
    return _ETAT["d"]


def ecrire(d):
    with _verrou:
        tmp = _chemin() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, _chemin())
    _ETAT["vu"] = 0.0


def passe():
    d = calculer()
    ecrire(d)
    return d


def passe_si_besoin():
    """Une fois par jour : les etats ET la verification, avec toutes les ventes accumulees."""
    try:
        if time.time() - os.path.getmtime(_chemin()) < 20 * 3600 and lire().get("v") == VERSION:
            return None
    except OSError:
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            t0 = time.time()
            d = passe()
            a, v = (d.get("verif") or {}).get("achat") or {}, (d.get("verif") or {}).get("vente") or {}
            E = d.get("etats") or {}
            print("Marche des joueurs : %d joueurs en %d s · acheter %d (actif %s, %s, %s vs hasard %s, n %s) · vendre %d (actif %s, +%s, %s vs %s, n %s)" % (
                len(E), time.time() - t0, sum(1 for e in E.values() if e.get("signal") == "acheter"), a.get("actif"), a.get("regle"), a.get("taux"), a.get("base"), a.get("n"),
                sum(1 for e in E.values() if e.get("signal") == "vendre"), v.get("actif"), v.get("regle"), v.get("taux"), v.get("base"), v.get("n")), flush=True)
        except Exception as e:
            print("Marche des joueurs : " + repr(e), flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="marche-joueurs").start()
    return True


# -- les lectures ---------------------------------------------------------------------------------------------------------
def etat(nom):
    return (lire().get("etats") or {}).get(_titre(nom))


def liste(signal, n=40):
    """[{nom, sous_sommet_pct, vs_mediane_pct, mois_pct}] : « acheter » (le plus loin de son sommet d'abord) ou « vendre »."""
    E = lire().get("etats") or {}
    l = [{"nom": k, **{c: e.get(c) for c in ("sous_sommet_pct", "vs_mediane_pct", "mois_pct", "n", "taux", "mois", "gain", "bas_depuis_j", "haut_depuis_j", "hist_j")}}
         for k, e in E.items() if e.get("signal") == signal]
    # le signal le plus sur d'abord (son taux mesure), puis le plus loin de son niveau habituel
    l.sort(key=(lambda x: (-(x["taux"] or 0), x["vs_mediane_pct"])) if signal == "acheter" else (lambda x: (-(x["taux"] or 0), -x["vs_mediane_pct"])))
    return l[:n]


def preuve():
    """Ce que la verification a mesure, pour le dire tel quel : {achat: {taux, base, n, gain_med, regle}, vente: {...}} (actifs seulement)."""
    V = lire().get("verif") or {}
    return {k: {c: V[k].get(c) for c in ("taux", "borne", "base", "n", "joueurs", "gain_med", "regle", "base_n", "essais", "essayes", "mois", "du", "au", "apres_j", "bouge", "n_min", "frais")}
            for k in ("achat", "vente", "vente_etablis") if (V.get(k) or {}).get("actif")}


def statut():
    d = lire()
    E = d.get("etats") or {}
    return {"le": d.get("le"), "joueurs": len(E), "acheter": sum(1 for e in E.values() if e.get("signal") == "acheter"),
            "vendre": sum(1 for e in E.values() if e.get("signal") == "vendre"), "verif": d.get("verif")}
