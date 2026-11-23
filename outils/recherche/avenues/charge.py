import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))); import cache_recherche as cr   # 23 nov 2026 : plus de pickle (Aikido)
import gzip, json, collections
d = json.load(gzip.open("/tmp/claude-0/ts/A_maintenant.json.gz", "rt", encoding="utf-8"))
A = d["A"]
print(len(A), d["info"])
print(A[0])
js = sorted(a["j"] for a in A)
print(js[0], js[-1])
c = collections.Counter(a["ra"] for a in A)
print(c.most_common(30))
c = collections.Counter(a["fin"] for a in A)
print(c.most_common())
cr.sauver(A, "A.json.gz")
