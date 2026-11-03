"""
SLABCOACH - l'assistant de gradation : est-ce que ca vaut la peine, et quel service (3 nov 2026).

Mathieu (devant le simple formulaire « Send for grading ») : « on peut juste faire ca pour assister l'utilisateur pour
grader avec PSA ? C'est pas assez ». Ce que l'assistant calcule pour UNE carte :
  1. les chances de chaque note PSA, d'apres la fourchette de l'examen de l'etat (jamais une promesse) ;
  2. ce que vaut la carte a chaque note : les VRAIES ventes de la meme carte gradee (lockerroom.valeur_gradee) ;
  3. le cout : le niveau de service que la valeur declaree impose (la valeur APRES gradation), le port aller-retour ;
  4. le gain attendu = valeur esperee gradee - valeur raw, apres les frais de vente des deux cotes, moins le cout ;
     la note minimum pour etre rentable ; un verdict.
Les tarifs PSA changent souvent (les niveaux Value ont ete suspendus puis rouverts en 2026) : la table est datee, a
confirmer sur psacard.com, et Render peut la remplacer sans deployer (LR_PSA_TARIFS, JSON).
"""
import json
import os
from datetime import datetime, timedelta

# (nom, prix US$, valeur declaree max US$, delai en jours ouvrables min, max) - releve du 3 nov 2026 (cardgrade.io, mise a
# jour du 29 oct 2026 : Value rouvert ; allvintagecards.com, 6 sept 2026). A confirmer sur psacard.com avant d'envoyer.
TARIFS_PSA = [
    ("Value", 39.99, 500, 90, 100),
    ("Regular", 79.99, 1500, 70, 80),
    ("Express", 149.00, 2500, 20, 30),
    ("Super Express", 349.00, 5000, 10, 15),
    ("Walk-Through", 599.00, 10000, 7, 10),
]
TARIFS_DATE = "2026-11-03"
PORT_CAD = 45.0                  # Canada -> PSA (suivi, assure) et retour, pour UN colis (estime ; depend du transporteur)


def tarifs():
    try:
        t = json.loads(os.environ.get("LR_PSA_TARIFS") or "null")
        if isinstance(t, list) and t and all(len(x) == 5 for x in t):
            return [tuple(x) for x in t], os.environ.get("LR_PSA_TARIFS_DATE") or TARIFS_DATE
    except ValueError:
        pass
    return TARIFS_PSA, TARIFS_DATE


def service(valeur_usd):
    """Le niveau le moins cher qui couvre la valeur declaree (US$)."""
    t, _d = tarifs()
    for x in t:
        if valeur_usd <= x[2]:
            return {"nom": x[0], "prix_usd": x[1], "max_usd": x[2], "jours": [x[3], x[4]]}
    x = t[-1]
    return {"nom": x[0], "prix_usd": x[1], "max_usd": x[2], "jours": [x[3], x[4]], "au_dela": True}


def jours_ouvrables(debut, n):
    d = debut
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def probas(bas, haut):
    """La fourchette de l'examen -> {note: chance}. Une fourchette serree : surtout la note du haut ; une large : partagee.
    Toujours un peu de chance d'un cran de moins (ce qu'une photo ne montre pas)."""
    if haut is None:
        return {}
    h = 10 if haut >= 9.75 else int(haut)
    b = h if bas is None else (10 if bas >= 9.75 else int(bas))
    b = min(b, h)
    p = {}
    if b == h:
        p[h] = 0.60
        p[h - 1] = 0.25 if h < 10 else 0.30
        if h < 10:
            p[h + 1] = 0.15
        else:
            p[h - 2] = 0.10
    else:
        p[h], p[b] = 0.45, 0.40
        p[b - 1] = 0.15
        for g in range(b + 1, h):                    # une fourchette de plus d'un cran : les notes entre partagent
            p[g] = 0.15
        s = sum(p.values())
        p = {g: v / s for g, v in p.items()}
    return {g: round(v, 3) for g, v in p.items() if 1 <= g <= 10}


def calculer(valeur_raw, valeurs_note, bas, haut, taux_usd, frais_pct=0.1325, frais_fixe=0.40, n_cartes=1, port_cad=None):
    """valeurs_note : {note: {"valeur": CAD, "n": ventes}}. -> le detail et le verdict."""
    pr = probas(bas, haut)
    connues = {g: v for g, v in valeurs_note.items() if v and v.get("valeur")}
    if not pr:
        return {"ok": True, "verdict": "examiner", "probas": {}}
    h = max(pr)
    haut_val = (connues.get(h) or {}).get("valeur") or max([v["valeur"] for v in connues.values()] or [0])
    sv = service((haut_val or valeur_raw or 0) / taux_usd)
    port = (PORT_CAD if port_cad is None else port_cad) / max(1, n_cartes)
    cout = round(sv["prix_usd"] * taux_usd + port, 2)
    net = lambda v: v * (1 - frais_pct) - frais_fixe
    couverte = sum(p for g, p in pr.items() if g in connues)
    lignes = [{"note": g, "chance": p, "valeur": (connues.get(g) or {}).get("valeur"), "n": (connues.get(g) or {}).get("n", 0)}
              for g, p in sorted(pr.items(), reverse=True)]
    out = {"ok": True, "probas": pr, "lignes": lignes, "service": sv, "cout": cout, "port": round(port, 2),
           "frais_usd_cad": taux_usd, "tarifs_date": tarifs()[1]}
    if couverte < 0.6 or h not in connues:
        out.update(verdict="pas_assez", couverte=round(couverte, 2))
        return out
    ev = sum(p * connues[g]["valeur"] for g, p in pr.items() if g in connues) / couverte
    out["valeur_esperee"] = round(ev, 2)
    if valeur_raw:
        gain = net(ev) - net(valeur_raw) - cout
        out["gain"] = round(gain, 2)
        seuil = None
        for g in sorted(connues):
            if net(connues[g]["valeur"]) - net(valeur_raw) - cout > 0:
                seuil = g
                break
        out["seuil"] = seuil
        out["verdict"] = "oui" if gain > max(15.0, 0.10 * cout) else "non" if gain < 0 else "juste"
        if out["verdict"] != "oui" and seuil == 10 and pr.get(10):
            out["verdict"] = "pari_10"                 # rentable seulement en 10
    else:
        out["verdict"] = "sans_raw"
    jmax = sv["jours"][1]
    out["retour_prevu"] = jours_ouvrables(datetime.now(), jmax + 5).strftime("%Y-%m-%d")   # + l'envoi et le retour
    return out
