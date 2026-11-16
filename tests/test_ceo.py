"""16 nov 2026 : le tableau de bord du CEO : reserve a l'admin, aucun secret renvoye, ce que Mathieu remplit est verifie."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["STRIPE_CLE_SECRETE"] = "sk_test_SECRET_A_NE_JAMAIS_MONTRER"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-SECRET2"
import lockerroom  # noqa: E402

a = lockerroom.Api()
a._est_admin = lambda: False
assert a.admin_ceo()["ok"] is False and a.admin_ceo_sauver({})["ok"] is False
a._est_admin = lambda: True
r = a.admin_ceo()
assert r["ok"], r
txt = json.dumps(r)
assert "SECRET" not in txt and "sk_test" not in txt and "sk-ant" not in txt
sv = {s["cle"]: s for s in r["services"]}
assert sv["stripe"]["configure"] is True and sv["anthropic"]["configure"] is True and sv["r2"]["configure"] is False
# ce que Mathieu remplit : verifie (liste blanche, nombres, dates)
x = a.admin_ceo_sauver({"services": {"render": {"montant": "25,50", "devise": "USD", "periode": "mois", "plan": "Starter"},
                                     "inconnu": {"montant": 5}, "apple": {"montant": "abc"}},
                        "obligations": {"acomptes": {"fait_le": "2026-11-16", "prochaine": "pas une date"}},
                        "entreprise": {"statut": "Travailleur autonome", "hack": "x"}, "notes": "ok"})
assert x["ok"]
c = x["config"]
assert c["services"]["render"]["montant"] == 25.5 and "inconnu" not in c["services"] and c["services"]["apple"]["montant"] is None
assert c["obligations"]["acomptes"]["fait_le"] == "2026-11-16" and c["obligations"]["acomptes"]["prochaine"] is None
assert "hack" not in c["entreprise"]
r = a.admin_ceo()
assert r["couts"]["fixe_mois"] > 25.5            # Render 25,50 $ US converti + Apple 99 $ US / 12
assert any(o["cle"] == "acomptes" and o["prochaine"] for o in r["obligations"])
print("CEO OK")
