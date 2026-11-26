"""20 nov 2026 (Mathieu : « valide l'info ; change-la partout pour que ce soit coherent : site, app, ordi ») : LES chiffres
publics de SlabIQ, une seule source : ui/slabiq_tests.json (ecrit par outils/tests_site.py, sur des ventes jamais vues).
Le site (outils/site_iq.py) et la fenetre SlabIQ de l'app (Api.slabiq_chiffres) les ecrivent avec les MEMES arrondis, toujours
vers le bas : jamais plus que la mesure. Des comptes et des pourcentages : jamais un prix."""
import json
import os

CHEMIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "slabiq_tests.json")


def lire(chemin=None):
    try:
        with open(chemin or CHEMIN, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def ventes_k(R):
    """416 934 -> « 415 k+ » (par tranches de 5 000, vers le bas)."""
    return f"{int(R['ventes_total'] // 5000 * 5)} k+"


def fois(R):
    """Les cartes A et A+ contre les E (la regle du Radar Pro) : 9,2 -> 9."""
    return int(R["x_ahaut_e"] + 1e-9)


def accord(R):
    """(texte fr, texte en, avant) : 80,2 % -> « 80 % » ; a moins d'un point sous un chiffre rond : « ≈ 80 % »."""
    a = R["accord"] * 100
    rond = round(a / 5) * 5
    if 0 < rond - a < 1:
        return f"≈ {rond} %", f"≈ {rond}%", round(R["accord_avant"] * 100)
    return f"{round(a)} %", f"{round(a)}%", round(R["accord_avant"] * 100)


def pro(R):
    """(Radar Pro, seul) en % entiers. Le Radar Pro vers le bas ; « seul » au plus proche (la moitie vers le haut), comme
    revendue() et comme le bulletin : jamais plus d'ecart que la mesure. 23 nov 2026 au soir : « seul » mesure a 9,6 % s'ecrivait
    « 9 % » dans le comparatif et « 10 % » dans le bulletin de la meme page ; avant, 11,1 % donnait 11 partout."""
    return int(R["pro"]["reussi"] * 100 + 1e-9), int(R["hasard"]["reussi"] * 100 + 0.5)


def revendue(R):
    """23 nov 2026 (le comparatif « seul ou avec SlabCoach ») : (Radar Pro, seul) en % entiers : la meme carte s'est revendue
    ensuite. Le Radar Pro vers le bas, le point de comparaison au plus proche (la moitie vers le haut) : jamais plus d'ecart
    que la mesure."""
    return int(R["pro"]["revendue"] * 100 + 1e-9), int(R["hasard"]["revendue"] * 100 + 0.5)


CHEMIN_BULLETIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "slabiq_bulletin.json")


def fois_seul(R, bulletin=None):
    """26 nov 2026 (Mathieu : « on est combien de fois meilleur avec SlabCoach ? on doit etre vraiment simple ») : combien de fois
    plus souvent une carte du Radar Pro garde sa valeur qu'une carte achetee seul. -> (N entier, bas, haut) : N = le PIRE des
    tests (le test du site et chaque date du bulletin), arrondi vers le bas : « N fois » est donc vrai a CHAQUE test ; bas et
    haut : l'etendue, a une decimale vers le bas. Le 26 nov : 6,0 a 7,3 -> « 6× » (le test du jour seul dirait 7)."""
    if bulletin is None:
        bulletin = lire(CHEMIN_BULLETIN)
    L = [(x.get("pro") or {}, x.get("hasard") or {}) for x in (bulletin or {}).get("lignes") or []]
    cp, ch = R.get("pro") or {}, R.get("hasard") or {}
    if not any(p.get("n") == cp.get("n") and p.get("reussi") == cp.get("reussi") for p, _h in L):      # la derniere ligne du bulletin EST le test du site
        L.append((cp, ch))
    r = [p["reussi"] / h["reussi"] for p, h in L if p.get("n") and p.get("reussi") and h.get("reussi")]
    bas, haut = min(r), max(r)
    return int(bas + 1e-9), int(bas * 10 + 1e-9) / 10, int(haut * 10 + 1e-9) / 10, len(r)


def publics(chemin=None):
    """Pour l'app : les memes textes que le site. {} si la mesure n'est pas la."""
    R = lire(chemin)
    try:
        a_fr, a_en, av = accord(R)
        p, h = pro(R)
        rv, rvh = revendue(R)
        return {"le": R["le"], "ventes": ventes_k(R), "fois": fois(R), "accord_fr": a_fr, "accord_en": a_en, "accord_avant": av,
                "pro": p, "hasard": h, "revendue": rv, "revendue_seul": rvh, "joueurs": int(R.get("joueurs") or 0),
                "fois_seul": fois_seul(R)[0]}
    except (KeyError, TypeError, ValueError):
        return {}
