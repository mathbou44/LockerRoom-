"""23 nov 2026 (Mathieu, carte O-Pee-Chee Platinum #BA-AK lue « Autographs » : « c'est une blue rainbow. Sert-toi du code BA ») :
le CODE d'une carte dit parfois son parallele quand la carte ne l'ecrit pas (BA = Blue Rainbow). On l'apprend de nos ventes,
par produit ET par saison (RA = Red Rainbow en 2025-26, mais « Rookie Autographs » avant).

    python3 outils/apprendre_codes_variantes.py ventes_hockey.tsv.gz            # montre
    python3 outils/apprendre_codes_variantes.py ventes_hockey.tsv.gz --ecrire   # ecrit codes_variantes.json

Garde seulement ce qui est sur : 20 ventes et 5 cartes differentes dans la saison, chaque mot dans 85 % des titres, et un nom
fait seulement de couleurs et de finis (les noms d'inserts sont imprimes sur la carte : l'IA les lit deja)."""
import collections
import gzip
import json
import os
import re
import sys
from datetime import date

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
import cartes_match as cm  # noqa: E402

RE = re.compile(r"#\s?([A-Za-z]{2,5})-([A-Za-z0-9]{1,5})\b")
COULEURS = set("blue red gold green orange purple violet black emerald silver pink yellow teal white bronze copper".split())
FINIS = set("rainbow prism wave shimmer seismic cosmic pixel matte".split())
N_MIN, CODES_MIN, PART_MIN = 20, 5, 0.85


def saison(titre):
    m = re.search(r"\b(20\d\d)\s?[-/]\s?(\d\d)\b", titre)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"\b(20\d\d)\b", titre)
    return f"{m.group(1)}-{(int(m.group(1)) + 1) % 100:02d}" if m else None


def apprendre(titres):
    G = collections.defaultdict(list)
    for t in titres:
        m = RE.search(t)
        if not m:
            continue
        ps = cm.produits_du_titre(t)
        s = saison(t)
        if len(ps) == 1 and s:
            G[(ps[0], m.group(1).upper(), s)].append((cm.norm(RE.sub(" ", t)), m.group(2).upper()))
    par_code = collections.defaultdict(dict)
    for (prod, pre, s), L in G.items():
        n = len(L)
        if n < N_MIN or len({c for _, c in L}) < CODES_MIN:
            continue
        cpt, pos = collections.Counter(), collections.defaultdict(list)
        for t, _ in L:
            mots = re.findall(r"[a-z]+", t)
            for w in set(mots):
                if w in COULEURS or w in FINIS:
                    cpt[w] += 1
                    pos[w].append(mots.index(w))
        forts = sorted((w for w, k in cpt.items() if k / n >= PART_MIN), key=lambda w: sum(pos[w]) / len(pos[w]))
        if len(forts) >= 2 and any(w in FINIS for w in forts) and any(w in COULEURS for w in forts):
            par_code[(prod, pre, " ".join(forts))][s] = [min(cpt[w] for w in forts), n]
    out = []
    for (prod, pre, var), S in sorted(par_code.items()):
        ok, n = sum(v[0] for v in S.values()), sum(v[1] for v in S.values())
        out.append({"produit": prod, "prefixe": pre, "variante": var.title(), "saisons": dict(sorted(S.items())), "n": n, "part": round(ok / n, 3)})
    return out


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    with gzip.open(argv[1], "rt", encoding="utf-8", errors="replace") as f:
        f.readline()
        titres = [l.split("\t", 1)[0] for l in f]
    codes = apprendre(titres)
    for c in codes:
        print(f"{c['produit']:22s} #{c['prefixe']:5s} -> {c['variante']:16s} {c['part']:.0%} de {c['n']} ventes · saisons {', '.join(c['saisons'])}")
    if "--ecrire" in argv:
        p = os.path.join(ICI, "codes_variantes.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"appris_le": date.today().isoformat(), "ventes": len(titres), "codes": codes}, f, ensure_ascii=False, indent=1)
        print("ecrit", p)


if __name__ == "__main__":
    main(sys.argv)
