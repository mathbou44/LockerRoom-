"""31 oct 2026 - checklists Upper Deck a plusieurs onglets (Premier, Stature) : seul l'onglet en tableau est lu, les
inscriptions restent le meme joueur, les paralleles de couleur et de patch sont reliees a leur carte de base. Aucun reseau."""
import io
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import openpyxl  # noqa: E402
import checklist_import as ci  # noqa: E402

wb = openpyxl.Workbook()
r = wb.active
r.title = "Base"
for l in [["Base Set"], [], ["150 cards"], ["Parallels"], ["Gold /65"], ["1", "Seth Jarvis,", "Carolina Hurricanes"]]:
    r.append(l)
m = wb.create_sheet("Master Card List")
m.append(["Set Name", "Card", "Description", "Team City", "Team Name", "Rookie", "Auto", "Mem", "Tech", "#'d", "SPs", "Stated Odds"])
L = [("Base Set", "1", "Seth Jarvis", None, None), ("Gold Parallel", "1", "Seth Jarvis", 65, None),
     ("Auto Parallel", "46", "Macklin Celebrini", None, "SP"), ("Auto Parallel", "46", 'Macklin Celebrini "I Like Fishing"', None, None),
     ("Gold Auto Parallel", "46", "Macklin Celebrini", 25, None),
     ("Premier Rookie Auto Jersey", "PRA-RL", "Ryan Leonard", 25, None), ("Premier Rookie Auto Patch Parallel", "PRA-RL", "Ryan Leonard", 15, None),
     ("Jersey Parallel - Rookies", "101", "Gabe Perreault", None, None), ("Shoulder Number Parallel - Rookies", "101", "Gabe Perreault", 3, None)]
for s, n, j, t, sp in L:
    m.append([s, n, j, "Ville", "Equipe", None, None, None, None, t, sp, "Random"])
b = io.BytesIO()
wb.save(b)
res = ci.lire(b.getvalue(), "2025-26-Upper-Deck-Premier-Hockey-Checklist.xlsx", "hockey")
assert res["lignes"] == len(L), res["lignes"]                                     # l'onglet resume n'est pas lu
noms = {s["nom"]: s for s in res["sous_ensembles"]}
assert not any(k in noms for k in ("150 cards", "Gold /65", "Parallels"))
assert noms["Gold Auto Parallel"]["parallele_de"] == "Auto Parallel"
assert noms["Premier Rookie Auto Patch Parallel"]["parallele_de"] == "Premier Rookie Auto Jersey"
assert noms["Shoulder Number Parallel - Rookies"]["parallele_de"] == "Jersey Parallel - Rookies"
ins = [c for c in res["cartes"] if c.get("inscription")]
assert len(ins) == 1 and ins[0]["joueur"] == "Macklin Celebrini" and ins[0]["inscription"] == "I Like Fishing" and ins[0]["sp"] == "SSP"
v = ci.verifier(res)
assert v["ok"] and any("cartes lues" in x for x in v["ok"]), v
assert all(ci.est_bruit(x) for x in ("57 cards", "Gold /65", "1:18 packs", "Platinum 1/1", "Parallels", "Gold /25 or fewer (See list below)"))
assert not any(ci.est_bruit(x) for x in ("Base Set", "Gold Auto Parallel", "Young Guns", "Platinum Parallel - Rookies"))
print("OK test_import_onglets")
