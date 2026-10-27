# 27 oct 2026 - validation de la methode de probabilites des breaks (python tests/valider_probabilites.py 300000)
# Compare : cotes publiees vs taux par boite, et la formule de l'app vs une simulation Monte-Carlo de vraies boites.
# Validation de la methode de probabilites de SlabCoach (breaks) - lecture seule du catalogue
import sys, os, re, math, json, time
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.chdir(RACINE)
import numpy as np
import catalogue, calcul
rng = np.random.default_rng(12345)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
RE_COTE = re.compile(r"\b1\s*:\s*(\d+(?:[ \u202f\u00a0]\d{3})*(?:[\.,]\d+)?)\s*(packs?|paquets?|boxes|bo[iî]tes?|cases?|caisses?)?\s*(hobby|epack|h\b)?", re.I)
RE_DETAIL = re.compile(r"absent|exclusif|blaster|hanger|tin\b|mega|retail|walmart|target|starter", re.I)
rapport = {}
for p in catalogue.liste():
    t0 = time.time()
    prod = catalogue.charger(p["id"]); taux = prod["_taux"]; se = {s["nom"]: s for s in prod["sous_ensembles"]}
    fmt = (prod.get("formats") or [{}])[0]
    paquets = float(fmt.get("paquets") or 0); cpp = float(fmt.get("cartes_par_paquet") or 0)
    r = {"nom": prod["nom"], "cartes_boite": paquets * cpp, "somme_taux": round(sum(taux.values()), 2)}
    # B - cotes publiees vs taux par boite
    ecarts = []
    for n, s in se.items():
        m = RE_COTE.search(str(s.get("cotes") or ""))
        if not m or n not in taux or not paquets:
            continue
        x = float(re.sub(r"[ \u202f\u00a0]", "", m.group(1)).replace(",", "."))
        if RE_DETAIL.search(str(s.get("cotes") or "")[:m.end() + 25]) and not re.search(r"hobby", str(s.get("cotes") or ""), re.I):
            continue
        unite = (m.group(2) or "pack").lower()
        attendu = paquets / x if unite.startswith(("pack", "paquet")) else 1 / x if unite.startswith(("box", "bo")) else 1 / (x * float(fmt.get("boites_par_caisse") or 1))
        if attendu > 0:
            ecarts.append((n, round(taux[n], 4), round(attendu, 4), round(taux[n] / attendu, 3)))
    r["cotes_verifiees"] = len(ecarts)
    r["cotes_ecarts"] = [e for e in ecarts if abs(e[3] - 1) > 0.03][:12]
    r["cotes_identiques"] = sum(1 for e in ecarts if abs(e[3] - 1) <= 0.03)
    # D - Monte-Carlo : chaque boite tire le nombre garanti (partie entiere + Bernoulli de la fraction) de chaque
    # sous-ensemble, chaque exemplaire = une version au hasard selon son tirage ; P(au moins un hit) par joueur
    lignes = [(c, s, n) for c, s, n in catalogue.cartes_attendues(prod, 1) if calcul.categories_carte(c, s)]
    par_se = {}
    for c, s, n in lignes:
        par_se.setdefault(s["nom"], []).append((c, n))
    joueurs = sorted({j.strip() for c, s, n in lignes for j in str(c.get("joueur") or "").split("/") if j.strip()})
    ji = {j: i for i, j in enumerate(joueurs)}
    lam_part = np.zeros(len(joueurs)); lam_plein = np.zeros(len(joueurs))
    vu = np.zeros((N, len(joueurs)), dtype=bool)
    for nom, l in par_se.items():
        t = taux[nom]; ws = np.array([n for _c, n in l]); q = ws / ws.sum()
        js = [[ji[j.strip()] for j in str(c.get("joueur") or "").split("/") if j.strip()] for c, _n in l]
        for k, (c, n) in enumerate(l):
            for j in js[k]:
                lam_plein[j] += n; lam_part[j] += n / len(js[k])
        k_fix = int(math.floor(t)); frac = t - k_fix
        nb = k_fix + (rng.random(N) < frac).astype(int)
        tot = int(nb.sum())
        if tot == 0:
            continue
        tir = rng.choice(len(l), size=tot, p=q)
        boite = np.repeat(np.arange(N), nb)
        for k in range(len(l)):
            sel = boite[tir == k]
            if not len(js[k]):
                continue
            if len(js[k]) == 1:
                vu[sel, js[k][0]] = True
            else:                        # carte a 2 joueurs (ou plus) : elle va a UN des deux, au hasard
                qui = rng.integers(0, len(js[k]), size=len(sel))
                for u, j in enumerate(js[k]):
                    vu[sel[qui == u], j] = True
    p_sim = vu.mean(axis=0)
    p_poisson_plein = 1 - np.exp(-lam_plein)
    p_poisson_part = 1 - np.exp(-lam_part)
    se_sim = np.sqrt(np.maximum(p_sim * (1 - p_sim), 1e-12) / N)
    ok = p_sim > 0.002
    def err(p_ana):
        d = np.abs(p_ana - p_sim)
        rel = np.where(ok, d / np.maximum(p_sim, 1e-9), 0)
        z = np.where(ok, d / se_sim, 0)
        return {"ecart_max_pts": round(100 * float(d.max()), 3), "ecart_rel_max_pct": round(100 * float(rel.max()), 1),
                "ecart_rel_median_pct": round(100 * float(np.median(rel[ok])) if ok.any() else 0, 2),
                "z_max": round(float(z.max()), 1), "joueurs_hors_3sigma": int((z > 3).sum())}
    r["joueurs"] = len(joueurs)
    r["poisson_plein_vs_sim"] = err(p_poisson_plein)
    r["poisson_moitie_carte_double_vs_sim"] = err(p_poisson_part)
    top = np.argsort(-p_sim)[:3]
    r["exemples"] = [(joueurs[i], round(float(p_sim[i]), 4), round(float(p_poisson_plein[i]), 4), round(float(p_poisson_part[i]), 4)) for i in top]
    duo = [j for j in range(len(joueurs)) if abs(lam_plein[j] - lam_part[j]) > 1e-12]
    r["joueurs_avec_cartes_doubles"] = len(duo)
    r["secondes"] = round(time.time() - t0, 1)
    rapport[prod["id"]] = r
    print(json.dumps({prod["id"]: r}, ensure_ascii=False), flush=True)
pass
