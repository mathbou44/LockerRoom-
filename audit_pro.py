"""18 nov 2026 (Mathieu : « que la cote de la Pro s'auto-regule avec les comps, sans que le client voie le background ; on ne
montre jamais de prix ») : l'AUDIT PRO, chaque jour, cote serveur, admin seulement.
18 nov 2026 (2e version, Mathieu : « pas juste les prix fixes : le prix final des encheres aussi ; toujours iterer ; les
questions et incoherences dans nos questions, et mes reponses s'appliquent directement dans l'app ») :
- un ENCAN montre en Pro et fini : son prix final contre les comps de la meme carte (sa vente retrouvee par son numero) ;
  les encans d'un joueur qui finissent souvent a moins de la moitie des comps -> un cran de moins ; souvent a 1,5x et plus
  -> un cran de plus (les deux sens) ;
- des signaux contraires (annonces surpayees mais encans forts), ou un joueur de l'expert dont les encans s'effondrent :
  une QUESTION dans « SlabIQ demande » (la reponse devient sa cote tout de suite, dans l'app).

1. On reprend les annonces a prix fixe que les Radars Pro ont montrees (les Radars gardes sur le disque, 7 derniers jours).
2. Pour chacune, les ventes deja connues de la MEME carte (cache et archives : aucun appel) : son prix est-il 3x ses comps ?
3. Un JOUEUR dont les annonces Pro sont souvent surpayees (>= 4 annonces et >= 40 %) perd un cran de cote ; quand ses
   annonces redeviennent normales (< 15 %), il le reprend. Le client ne voit que la lettre, jamais un prix ni une comparaison.
4. Une SORTE de carte souvent surpayee devient une question pour l'expert (les sortes viennent de l'expert).
Les joueurs cotes par l'expert ne sont jamais touches (leur valeur est hors marche).
"""
import glob
import json
import os
import statistics
import time
from datetime import datetime

SEUIL = 3.0              # une annonce a 3x ses comps (ou plus) est « surpayee »
COMPS_MIN = 3
N_JOUEUR = 4
PART_JOUEUR = 0.40
PART_RETOUR = 0.15
N_SORTE = 10
PART_SORTE = 0.30
N_ENCANS = 4             # encans finis d'un joueur, au moins
PART_BAS = 0.50          # part des encans finis a moins de la moitie des comps
PART_HAUT = 0.50         # part des encans finis a 1,5x les comps ou plus
BAS, HAUT = 0.5, 1.5
EXPERT_N, EXPERT_PART = 6, 0.70     # un joueur de l'expert : seulement une question, et seulement si c'est net
JOURS = 7
ORDRE = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "E"]
_ETAT = {"en_cours": False}


def _sections(r):
    for k in ("pour_toi", "decouvrir", "chauds", "creux", "chasses", "types", "vendeurs", "cibles"):
        for g in (r.get(k) or []):
            if isinstance(g, dict):
                for x in g.get("annonces") or []:
                    yield x
                    for y in x.get("autres") or []:
                        yield y
    for x in (r.get("petits") or []) + (r.get("deals") or []):
        if isinstance(x, dict):
            yield x


def annonces_pro(dossier, jours=JOURS):
    """Les annonces (prix fixe et encans) que les Radars ont montrees ces derniers jours (une fois chacune)."""
    lim = time.time() - jours * 86400
    vus, out = set(), []
    for f in glob.glob(os.path.join(dossier, "radar_garde", "*.json")):
        try:
            if os.path.getmtime(f) < lim:
                continue
            r = (json.load(open(f, encoding="utf-8")) or {}).get("r") or {}
        except Exception:
            continue
        for x in _sections(r):
            iid = str(x.get("item_id") or "")
            if not iid or iid in vus or not x.get("titre") or not x.get("total"):
                continue
            vus.add(iid)
            out.append(x)
    return out


def auditer(items, comps, digne=None):
    """items : annonces (titre, total, score, joueur) ; comps(titre) -> {mediane, nb} ; digne(x) -> visible en Pro ?
    -> le rapport (rien n'est ecrit ici)."""
    import bareme_iq as bq
    import cartes_match
    par_j, par_s, ex, verifiees, lettres_s = {}, {}, [], 0, {}
    enc_j, enc_n, maint = {}, 0, time.time()
    for x in items:
        if digne and not digne(x):
            continue
        t = str(x.get("titre") or "")
        try:
            vc = comps(t) or {}
        except Exception:
            vc = {}
        if x.get("encan"):
            r = _encan_fini(x, vc, maint)
            if r is None:
                continue
            enc_n += 1
            nom = x.get("joueur") or cartes_match.joueur_du_titre(t) or ""
            nom = " ".join(w.capitalize() for w in str(nom).split())
            if nom:
                a = enc_j.setdefault(nom, [0, 0, 0])
                a[0] += 1
                a[1] += r < BAS
                a[2] += r >= HAUT
            continue
        med, nb = vc.get("mediane"), int(vc.get("nb") or 0)
        if not med or nb < COMPS_MIN:
            continue
        verifiees += 1
        sur = float(x["total"]) >= SEUIL * float(med)
        nom = x.get("joueur") or cartes_match.joueur_du_titre(t) or ""
        nom = " ".join(w.capitalize() for w in str(nom).split())
        so, ra = bq.sorte(t)
        lettres_s[ra] = so
        for D, k in ((par_j, nom), (par_s, ra)):
            if k:
                a = D.setdefault(k, [0, 0])
                a[0] += 1
                a[1] += sur
        if sur and len(ex) < 30:
            ex.append({"titre": t[:90], "joueur": nom, "sorte": ra, "ratio": round(float(x["total"]) / float(med), 1)})
    sur_tot = sum(v[1] for v in par_j.values()) if par_j else sum(v[1] for v in par_s.values())
    return {"le": datetime.now().isoformat(timespec="seconds"), "annonces": len(items), "verifiees": verifiees, "surpayees": sur_tot,
            "part": round(sur_tot / verifiees, 3) if verifiees else None,
            "joueurs": {k: v for k, v in par_j.items()}, "sortes": {k: v for k, v in par_s.items()}, "lettres_s": lettres_s, "exemples": ex,
            "encans_finis": enc_n, "encans": enc_j}


def _num(x):
    import re
    m = re.search(r"(\d{9,15})", str(x.get("item_id") or "")) or re.search(r"/itm/(?:[^/?]+/)?(\d{9,15})", str(x.get("url") or ""))
    return m.group(1) if m else None


def _encan_fini(x, vc, maint):
    """Un encan montre en Pro et fini : son prix final / la mediane des AUTRES ventes de la meme carte, ou None."""
    try:
        fin = datetime.fromisoformat(str(x.get("fin")).replace("Z", "+00:00")).timestamp() if x.get("fin") else None
    except ValueError:
        fin = None
    if not fin or fin > maint:
        return None
    n = _num(x)
    if not n:
        return None
    ventes = vc.get("ventes") or []
    final = next((float(v["prix"]) for v in ventes if v.get("prix") and n in str(v.get("url") or "")), None)
    autres = [float(v["prix"]) for v in ventes if v.get("prix") and n not in str(v.get("url") or "")]
    if not final or len(autres) < COMPS_MIN:
        return None
    return final / statistics.median(autres)


def decider(rapport, d):
    """Les corrections : (cotes_audit, changements, retours, questions). Un cran au plus, dans un sens ou dans l'autre ;
    des signaux contraires, ou un joueur de l'expert : une question."""
    import bareme_iq as bq
    import validation_iq
    cotes = dict(d.get("cotes_audit") or {})
    experts = {k.lower() for k in bq.JOUEURS_EXPERT} | {k.lower() for k in (d.get("cotes") or {})}
    J, E = rapport.get("joueurs") or {}, rapport.get("encans") or {}
    changes, retours, Q = [], [], []
    for nom in set(J) | set(E):
        if not nom:
            continue
        n_f, s_f = (J.get(nom) or [0, 0])[:2]
        n_e, bas, haut = (E.get(nom) or [0, 0, 0])[:3]
        bas_f = n_f >= N_JOUEUR and s_f / n_f >= PART_JOUEUR            # ses annonces Pro sont souvent surpayees
        bas_e = n_e >= N_ENCANS and bas / n_e >= PART_BAS                # ses encans finissent souvent sous la moitie des comps
        haut_e = n_e >= N_ENCANS and haut / n_e >= PART_HAUT             # ses encans finissent souvent a 1,5x et plus
        preuve = f"{s_f}/{n_f} annonces surpayées · {bas}/{n_e} encans à moins de la moitié des comps · {haut}/{n_e} à 1,5× et plus"
        preuve_en = f"{s_f}/{n_f} listings overpriced · {bas}/{n_e} auctions under half the comps · {haut}/{n_e} at 1.5× or more"
        if nom.lower() in experts:
            if n_e >= EXPERT_N and (bas / n_e >= EXPERT_PART or haut / n_e >= EXPERT_PART):
                l = bq.note_joueur(nom)[1]
                Q.append({"type": "joueur", "nom": nom, "lettre": l, "audit": True, "confirmer": True, "n": n_e,
                          "raison": f"Audit Pro : tu l'as coté {l}, mais ses encans finissent loin de ses comps ({preuve})",
                          "raison_en": f"Pro audit: you rated him {l}, but his auctions close far from his comps ({preuve_en})"})
            continue
        sans = _sans_audit(nom)
        if not sans or sans not in ORDRE:
            continue
        i = ORDRE.index(sans)
        if (bas_f or bas_e) and haut_e:
            Q.append({"type": "joueur", "nom": nom, "lettre": sans, "audit": True, "urgent": True, "n": n_f + n_e,
                      "raison": f"Audit Pro : signaux contraires ({preuve}). Quelle est sa vraie lettre ?",
                      "raison_en": f"Pro audit: mixed signals ({preuve_en}). What is his real letter?"})
            continue
        cible = ORDRE[min(len(ORDRE) - 1, i + 1)] if (bas_f or bas_e) else ORDRE[max(0, i - 1)] if haut_e else None
        if cible and cible != sans:
            if cotes.get(nom) != cible:
                cotes[nom] = cible
                changes.append({"nom": nom, "de": sans, "a": cible, "preuve": preuve})
        elif nom in cotes and n_f + n_e >= N_JOUEUR:
            retours.append({"nom": nom, "a": cotes.pop(nom)})
    tranchees = set(d.get("sortes") or {}) | getattr(validation_iq, "SORTES_TRANCHEES", set())
    for ra, (n, s) in (rapport.get("sortes") or {}).items():
        if n >= N_SORTE and s / n >= PART_SORTE and ra not in tranchees and ra not in ("base", "lot_checklist"):
            lib = validation_iq.LIBELLES.get(ra, (ra, ra))
            Q.append({"type": "sorte", "nom": ra, "lettre": (rapport.get("lettres_s") or {}).get(ra),
                      "n": n, "urgent": True, "audit": True,
                      "raison": f"Audit Pro : {s} annonces « {lib[0]} » sur {n} montrées en Pro étaient à 3 fois leurs comps ou plus",
                      "raison_en": f"Pro audit: {s} of {n} “{lib[1]}” listings shown in Pro were 3x their comps or more"})
    return cotes, changes, retours, Q


def _sans_audit(nom):
    """La lettre du joueur SANS la correction de l'audit (pour ne baisser que d'un cran a la fois)."""
    import bareme_iq as bq
    try:
        import indice_joueurs
        c = ((indice_joueurs.indice(nom) or {}).get("criteres")) or {}
    except Exception:
        c = {}
    try:
        return bq._note_joueur0(nom, c, recrue=float(c.get("recrue") or 0) >= 90)[1]
    except Exception:
        return None


def iterer(dossier, comps, digne=None):
    import bareme_iq as bq
    import slabiq_expert
    items = annonces_pro(dossier)
    rap = auditer(items, comps, digne)
    d = slabiq_expert.lire()
    cotes, changes, retours, Q = decider(rap, d)
    d["cotes_audit"] = cotes
    rap.update(baisses=changes, retours=retours, corrigees=len(cotes), questions=len(Q))
    rap["joueurs"] = sorted(([k, v[0], v[1]] for k, v in rap["joueurs"].items() if v[1]), key=lambda z: -z[2])[:40]
    rap.pop("lettres_s", None)
    rap["encans"] = sorted(([k, v[0], v[1], v[2]] for k, v in rap["encans"].items()), key=lambda z: -z[1])[:40]
    rap["sortes"] = sorted(([k, v[0], v[1]] for k, v in rap["sortes"].items() if v[1]), key=lambda z: -z[2])[:20]
    d["audit_pro"] = rap
    h = d.setdefault("audit_hist", [])
    h.append({"le": rap["le"], "verifiees": rap["verifiees"], "encans_finis": rap["encans_finis"], "part": rap["part"],
              "changes": len(changes), "retours": len(retours), "questions": len(Q)})
    d["audit_hist"] = h[-60:]
    if Q:
        deja = {(q.get("type"), str(q.get("nom")).lower()) for q in d.get("questions_marche") or []}
        d["questions_marche"] = [q for q in Q if (q["type"], str(q["nom"]).lower()) not in deja] + (d.get("questions_marche") or [])
    slabiq_expert.ecrire(d)
    bq._AUDIT["t"] = 0.0
    return rap


def passe_si_besoin(dossier, comps, digne=None, forcer=False):
    """Chaque jour (la boucle du serveur), en arriere-plan : aucun appel (cache et archives), on peut iterer souvent."""
    import threading
    import slabiq_expert
    h = (slabiq_expert.lire().get("audit_hist") or [{}])[-1]
    try:
        if not forcer and h and (datetime.now() - datetime.fromisoformat(h.get("le"))).total_seconds() < 20 * 3600:
            return None
    except (TypeError, ValueError):
        pass
    if _ETAT["en_cours"]:
        return None
    _ETAT["en_cours"] = True

    def tache():
        try:
            r = iterer(dossier, comps, digne)
            print("Audit Pro : %s annonces verifiees, %s surpayees, %s joueurs corriges"
                  % (r.get("verifiees"), r.get("surpayees"), r.get("corrigees")), flush=True)
        except Exception as e:
            print("Audit Pro : " + repr(e)[:200], flush=True)
        finally:
            _ETAT["en_cours"] = False
    threading.Thread(target=tache, daemon=True, name="audit-pro").start()
    return True
