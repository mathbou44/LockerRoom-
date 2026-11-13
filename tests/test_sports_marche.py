"""13 nov 2026 : le 2e sport au Canada, d'apres les ventes (calcul pur)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sports_marche as SM

L = [{"sale_date": f"2026-11-13T12:{m:02d}:00Z"} for m in range(0, 50)] + [{"sale_date": "2026-11-13T10:00:00Z"}]
assert 17 < SM.rythme_ventes(L) < 19, SM.rythme_ventes(L)                  # 51 ventes en 2 h 49 : ~17,8/h
assert SM.rythme_ventes([{"sale_date": "2026-11-13"}] * 40) == 80.0         # dates sans heure : borne basse
assert SM.rythme_ventes([{"sale_date": "x"}] * 40) is None
m = {"hockey": {"ventes": {"par_heure": 20}, "annonces_ca": 50000, "annonces_monde": 200000, "chez_nos_vendeurs": 9000},
     "basketball": {"ventes": {"par_heure": 100}, "annonces_ca": 15000, "annonces_monde": 1000000, "chez_nos_vendeurs": 300},
     "baseball": {"ventes": {"par_heure": 110}, "annonces_ca": 12000, "annonces_monde": 1200000, "chez_nos_vendeurs": 200},
     "football": {"ventes": {"par_heure": 90}, "annonces_ca": 6000, "annonces_monde": 900000, "chez_nos_vendeurs": 100},
     "soccer": {"ventes": {"par_heure": 30}, "annonces_ca": 2000, "annonces_monde": 300000, "chez_nos_vendeurs": 50}}
r = SM.combiner(m)
assert r["base"] == "ventes" and r["verdict"] == "basketball", r       # baseball vend plus dans le monde, mais moins au Canada
assert r["sports"]["hockey"]["part_canada"] > r["sports"]["basketball"]["part_canada"]
assert abs(sum(e["part_canada"] for e in r["sports"].values()) - 100) < 0.6
m2 = {k: dict(v, ventes={"erreur": "x"}) for k, v in m.items()}
r2 = SM.combiner(m2)
assert r2["base"] == "annonces" and r2["verdict"] == "basketball"
print("OK test_sports_marche")
