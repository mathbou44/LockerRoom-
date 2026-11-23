import pickle
from radar import prep, regle, bilan
W = [("27 sept", "2026-08-23", "2026-09-10", "2026-09-27"), ("11 oct", "2026-09-09", "2026-09-26", "2026-10-11"),
     ("25 oct", "2026-09-25", "2026-10-10", "2026-10-25"), ("8 nov", "2026-10-08", "2026-10-23", "2026-11-08"),
     ("22 nov", "2026-10-15", "2026-10-29", "2026-11-22")]
P = {w[0]: prep(*w[1:]) for w in W}
pickle.dump(P, open("P5.pkl", "wb"))
C = [("actuelle 82/5/+10 %", 82, 5, .10), ("liq 8", 82, 8, .10), ("liq 8, +5 %", 82, 8, .05), ("liq 8, <= mediane", 82, 8, 0.0),
     ("liq 12", 82, 12, .10), ("liq 12, <= mediane", 82, 12, 0.0), ("liq 5, <= mediane", 82, 5, 0.0), ("liq 8 sans prix", 82, 8, None), ("liq 5 sans prix", 82, 5, None)]
print(f"{'':22}" + "".join(f"{w[0]:>22}" for w in W))
print(f"{'hasard':22}" + "".join(f"{bilan(P[w[0]])['ok']*100:10.1f} (n={bilan(P[w[0]])['n']:5})  " for w in W))
for nom, note, liq, rab in C:
    ligne, rv, nt = "", "", ""
    for w in W:
        b = bilan([x for x in P[w[0]] if regle(x, note, liq, rab)])
        ligne += f"{b['ok']*100:10.1f} (n={b['n']:5})  "
        rv += f"{b['rev']*100:10.1f}            "
        nt += f"{b['net']*100:10.1f}            "
    print(f"{nom:22}" + ligne)
    print(f"{'   se revend':22}" + rv)
    print(f"{'   net apres frais':22}" + nt)
