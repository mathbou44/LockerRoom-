"""
SLABCOACH - le banc de la TENDANCE d'une carte (20 nov 2026), sur toutes nos ventes.

  python3 outils/banc_tendance.py [ventes_hockey.tsv.gz]

La tendance de l'app (vendues.tendance) : la mediane des J derniers jours contre celle des 2 J jours d'avant. Le banc du serveur
(banc.valider_tendance) demande : la direction annoncee s'est-elle poursuivie les J jours suivants ? Ici, en plus :
  - plusieurs dates de depart (toutes les 2 semaines sur les 6 derniers mois), toutes les cartes qui ont assez de ventes ;
  - le POINT DE COMPARAISON : la direction du marche (si tout baisse, dire « baisse » a raison sans rien savoir). Une tendance
    utile bat la direction du marche de la meme periode ;
  - la direction suivante est mesuree sur les ventes d'APRES la date (jamais vues par la tendance).
"""
import collections
import datetime as dt
import json
import os
import statistics as st
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def mesurer(cartes, J, seuil, departs):
    res = []
    for t0 in departs:
        d0 = dt.date.fromisoformat(t0)
        w1, w3, wf = (d0 - dt.timedelta(days=J)).isoformat(), (d0 - dt.timedelta(days=3 * J)).isoformat(), (d0 + dt.timedelta(days=J)).isoformat()
        paris = []
        for k, l in cartes.items():
            rec = [x["prix"] for x in l if w1 <= x["le"] < t0]
            av = [x["prix"] for x in l if w3 <= x["le"] < w1]
            ap = [x["prix"] for x in l if t0 <= x["le"] < wf]
            if len(rec) < 3 or len(av) < 3 or len(ap) < 3:
                continue
            a, b, c = st.median(av), st.median(rec), st.median(ap)
            pred, reel = (b - a) / a, (c - b) / b
            paris.append((pred, reel))
        if not paris:
            continue
        marche = st.median(r for _p, r in paris)            # la direction du marche (toutes les cartes) cette periode
        for pred, reel in paris:
            if abs(pred) >= seuil and abs(reel) > 1e-9:
                res.append((t0, pred > 0, reel > 0, marche > 0))
    if not res:
        return {"paris": 0}
    juste = sum(p == r for _t, p, r, _m in res) / len(res)
    base = sum(m == r for _t, p, r, m in res) / len(res)    # dire la direction du marche a chaque fois
    hausse = [x for x in res if x[1]]
    baisse = [x for x in res if not x[1]]
    return {"paris": len(res), "justes": round(juste, 3), "marche": round(base, 3), "gain_vs_marche": round(juste - base, 3),
            "hausse_justes": round(sum(r for _t, p, r, _m in hausse) / len(hausse), 3) if hausse else None, "n_hausse": len(hausse),
            "baisse_justes": round(sum(not r for _t, p, r, _m in baisse) / len(baisse), 3) if baisse else None, "n_baisse": len(baisse)}


def lancer(chemin):
    import banc_valeur
    cartes = banc_valeur.charger(chemin)
    fin = max(x["le"] for l in cartes.values() for x in l)
    out = {}
    for J in (14, 21, 30, 45):
        d = dt.date.fromisoformat(fin) - dt.timedelta(days=J)
        departs = [(d - dt.timedelta(days=14 * i)).isoformat() for i in range(13)]
        for seuil in (0.10, 0.15, 0.25):
            r = mesurer(cartes, J, seuil, departs)
            out[f"j{J}_s{int(seuil * 100)}"] = r
            print(f"J={J:2d} seuil={seuil:.0%} : {r}", flush=True)
    json.dump(out, open("/tmp/claude-0/banc_tendance.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lancer(args[0] if args else "/mnt/user-data/uploads/Downloads/ventes_hockey.tsv.gz")
