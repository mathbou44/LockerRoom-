"""
SLABCOACH - le bareme de l'examen d'etat (2 nov 2026).

Mathieu : « les baremes doivent etre etablis pour que toutes les cartes soient evaluees selon les memes criteres et la meme
severite ». L'IA ne donne plus de note : elle DECRIT ce qu'elle voit, coin par coin, bord par bord, et chaque marque de
surface, avec des etats fixes (les memes mots pour toutes les cartes). Cette table transforme ces observations en sous-notes
et en note, toujours de la meme facon. Les seuils suivent les normes officielles de PSA (psacard.com, Card Grading
Standards) ; l'ecran montre cette meme table (« Le bareme »).

Regles :
  - coins et bords : les 8 du devant et du dos comptent (PSA juge les deux faces) ;
  - une observation « incertaine » abaisse le BAS de la fourchette seulement ; « probable » et « sure » comptent partout ;
  - la note globale = la pire sous-note ; deux categories a 9 : 8,5 (PSA 9 = « un seul defaut mineur ») ; jamais 9,5
    (PSA n'en a pas) ;
  - le centrage : les tolerances PSA (examen.note_centrage), mesure par l'app, sinon estime.
"""

ETATS_COIN = {
    "net": (10, "pointe nette et carree"),
    "point_blanc": (9, "un tout petit point blanc a la pointe, visible seulement au zoom"),
    "effilochage_leger": (8, "leger effilochage (blanchiment) a la pointe, vu de pres"),
    "effilochage": (7, "effilochage net, visible sans zoom"),
    "arrondi_leger": (5, "pointe tres legerement arrondie"),
    "arrondi": (4, "coin arrondi"),
    "plie": (3, "coin plie ou ecrase"),
}
ETATS_BORD = {
    "net": (10, "arete nette et continue"),
    "point_blanc": (9, "un seul tout petit point blanc"),
    "quelques_points": (8, "quelques petits points blancs, vus de pres"),
    "usure_legere": (7, "legere usure le long de l'arete, vue de pres"),
    "encoche": (6, "tres legere encoche (notching)"),
    "ebrechures": (5, "petites ebrechures (chipping)"),
    "usure": (4, "usure nette ou entaille"),
}
# surface : (rasante / zoom seulement, visible de pres, visible a l'oeil)
SURFACE = {
    "ligne d'impression": (10, 9, 8),                  # PSA 10 tolere un leger defaut d'impression ; PSA 9 : un defaut mineur
    "tache": (9, 8, 6),
    "empreinte": (9, 8, 6),
    "rayure": (8, 6, 5),
    "perte de lustre": (7, 6, 5),
    "bosse": (7, 6, 5),
    "pli": (5, 4, 3),
    "autre": (9, 8, 6),
}
VISIBILITES = ("rasante", "de_pres", "visible")
CERTITUDES = ("sure", "probable", "incertaine")
COINS = ("haut-gauche", "haut-droit", "bas-droit", "bas-gauche")
BORDS = ("haut", "droit", "bas", "gauche")
_ECHELLE = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 10]


def psa(v):
    """Une note sur l'echelle PSA (pas de 9,5 : 9,5 -> 9)."""
    v = max(1.0, min(10.0, float(v)))
    return max(x for x in _ECHELLE if x <= v + 1e-9)


def note_coins(etats):
    """etats : liste des etats des coins vus (jusqu'a 8). -> sous-note."""
    n = {k: sum(1 for e in etats if e == k) for k in ETATS_COIN}
    if n["plie"]:
        return 3.0
    if n["arrondi"]:
        return 4.0
    if n["arrondi_leger"]:
        return 5.0 if n["arrondi_leger"] == 1 else 4.5
    if n["effilochage"]:
        return 7.0 if n["effilochage"] == 1 else 6.0          # PSA 6 : effilochage progressif a plusieurs coins
    if n["effilochage_leger"]:
        return 8.0 if n["effilochage_leger"] <= 2 else 7.0 if n["effilochage_leger"] <= 4 else 6.0   # PSA 8 : 1 ou 2 coins ; 7 : quelques coins
    if n["point_blanc"]:
        return 9.0 if n["point_blanc"] == 1 else 8.5 if n["point_blanc"] <= 3 else 8.0
    return 10.0


def note_bords(etats):
    if not etats:
        return 10.0
    pire = min(ETATS_BORD[e][0] for e in etats)
    touches = sum(1 for e in etats if ETATS_BORD[e][0] < 10)
    if pire >= 8 and touches >= 4:                     # usure repetee sur plusieurs aretes : un demi-point de plus
        return psa(pire - 0.5)
    if pire == 9 and touches >= 2:
        return 8.5
    return float(pire)


def note_surface(items):
    """items : [(type, visibilite)]. -> sous-note."""
    if not items:
        return 10.0
    notes = [SURFACE.get(t, SURFACE["autre"])[VISIBILITES.index(v) if v in VISIBILITES else 1] for t, v in items]
    pire = min(notes)
    rayures = sum(1 for t, v in items if t == "rayure" and v != "rasante")
    if rayures >= 2:                                   # PSA 5 : plusieurs rayures legeres
        pire = min(pire, 5)
    elif sum(1 for x in notes if x <= 9) >= 2 and pire == 9:
        pire = 8.5
    return psa(pire)


def globale(sous):
    """sous : {categorie: note} (None ignore). La pire ; deux categories a ce niveau (>= 8) : un demi-point de moins."""
    vs = [v for v in sous.values() if v is not None]
    if not vs:
        return None
    p = min(vs)
    if p == 9 and sum(1 for v in vs if v == p) >= 2:    # PSA 9 = « un seul defaut mineur » : deux -> 8,5
        p -= 0.5
    return psa(p)


def table():
    """Le bareme, pour l'ecran (le meme que les calculs)."""
    return {"coins": {k: v for k, v in ETATS_COIN.items()}, "bords": {k: v for k, v in ETATS_BORD.items()},
            "surface": {k: dict(zip(VISIBILITES, v)) for k, v in SURFACE.items()}}
