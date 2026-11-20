import json,re,sys
BRUIT = r"[\s\d.,:;·•\-–—+−~≈%$/()#×?!…»«'’\"|\[\]]"
def core(p):
    s = p
    while True:
        t = re.sub(r'^(?:\{\}|' + BRUIT + r')+', '', s)
        t = re.sub(r'(?:\{\}|' + BRUIT + r')+$', '', t)
        if t == s: break
        s = t
    return s
if __name__ == '__main__':
    for f in sys.argv[1:]:
        L = json.load(open(f))
        C = sorted({core(x) for x in L if len(re.sub(r'[^A-Za-zÀ-ÿ]', '', core(x).replace('{}',''))) >= 1})
        json.dump(C, open(f.replace('_frag', '_cores'), 'w'), ensure_ascii=False, indent=0)
        print(f, len(L), '->', len(C))
