"""
SLABCOACH - les pepites cachees (5 nov 2026, Mathieu : « trouver les encheres avec de grosses cartes sans visibilite :
erreur de titre, etc. »).

Une annonce dont le nom du joueur est mal ecrit (« Bedrad », « Mcdavd », « Gretsky ») ne sort pas quand les acheteurs
cherchent le joueur : peu de mises, souvent un prix bas. On cherche ces fautes nous-memes, pour les vedettes, puis on
juge l'annonce avec le nom CORRIGE (sa carte et ses ventes, comme les autres deals).

Les fautes generees sont celles qu'on voit vraiment sur eBay : une lettre doublee ou pas (Mathews / Matthews), un son
ecrit autrement (sky / ski, ck / k, ph / f, ie / ei), deux lettres inversees, une voyelle oubliee. On garde les plus
probables et seulement si la faute ne fait pas un autre mot courant.
"""
import re

# dans l'ordre de ce qu'on voit le plus (tch : l'orthographe francaise des noms russes, tres courante au Quebec)
_SONS = [("ch", "tch"), ("zk", "sk"), ("ck", "k"), ("sky", "ski"), ("ski", "sky"), ("ph", "f"), ("ie", "ei"), ("ei", "ie"),
         ("z", "s"), ("y", "i"), ("k", "ck"), ("ov", "off"), ("i", "y"), ("qu", "k"), ("x", "ks")]
_VOY = "aeiouy"
# des fautes qui feraient un mot courant (beaucoup de bruit dans la recherche)
_MOTS = {"price", "power", "hughes", "smith", "wright", "draft", "card", "cards", "auto", "patch", "rookie", "gold", "black", "red"}


def variantes(nom, n=3):
    """« Connor McDavid » -> les n fautes les plus probables du NOM DE FAMILLE (ex. ['mcdavd', 'mcdavidd', 'mcdaivd'])."""
    nf = re.sub(r"[^a-z]", "", str(nom or "").split()[-1].lower()) if str(nom or "").split() else ""
    if len(nf) < 5 or nf in _MOTS:
        return []
    out = []

    def ajouter(v):
        if v and v != nf and len(v) >= 4 and v not in out and v not in _MOTS:
            out.append(v)
    # 1. une lettre doublee ecrite simple (Matthews -> Mathews, MacKinnon -> Mackinon)
    for i in range(1, len(nf)):
        if nf[i] == nf[i - 1]:
            ajouter(nf[:i] + nf[i + 1:])
    # 2. un son ecrit autrement (Gretzky -> Gretsky, Ovechkin -> Ovetchkin, Slafkovsky -> Slafkovski)
    for a, b in _SONS:
        k = nf.find(a, 1)
        if k > 0:
            ajouter(nf[:k] + b + nf[k + len(a):])
    # 3. deux lettres inversees au milieu du nom ; 4. une voyelle oubliee (pas la premiere lettre)
    m = len(nf) // 2
    ajouter(nf[:m] + nf[m + 1] + nf[m] + nf[m + 2:])
    vs = [i for i in range(1, len(nf) - 1) if nf[i] in _VOY]
    if vs:
        i = vs[-1]
        ajouter(nf[:i] + nf[i + 1:])
    # 5. en dernier : une consonne doublee (Makar -> Makkar)
    cons = [i for i in range(1, len(nf) - 1) if nf[i] not in _VOY and nf[i - 1] in _VOY]
    if cons:
        i = cons[len(cons) // 2]
        ajouter(nf[:i] + nf[i] + nf[i:])
    return out[:n]


def corriger(titre, faute, nom):
    """Le titre avec le nom corrige (« 2023 Young Guns Connor Bedrad » -> « ... Connor Bedard »), ou None si la faute
    n'y est pas comme un mot."""
    nf = str(nom or "").split()[-1] if str(nom or "").split() else ""
    if not nf or not faute:
        return None
    t2, k = re.subn(r"(?i)\b" + re.escape(faute) + r"\b", nf, str(titre or ""))
    return t2 if k else None


def requetes(vedettes, par_joueur=2, max_=80):
    """[(faute, nom du joueur)] : les vedettes d'abord, par_joueur fautes chacune."""
    out = []
    for nom in vedettes or []:
        for v in variantes(nom, par_joueur):
            out.append((v, nom))
            if len(out) >= max_:
                return out
    return out
