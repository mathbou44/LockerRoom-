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
# 9 nov 2026 (Mathieu : pregradecards.com, « 12 surface flaws that kill your card's grade ») : 6 sortes de plus et des
# valeurs revues d'apres leurs ecarts typiques (une micro-rayure vue seulement au zoom : -0,5 ; un micro-creux : -0,5 a -1 ;
# une empreinte : -0,5 a -1 ; un point d'encre : -0,5 ; une perte de lustre : -1 a -2 ; une bosse : -0,5 a -2 ; un
# decollement du foil : -1 a -4 ; une decoloration : -1 a -3). Le pli et la marque d'ecriture gardent la severite de PSA.
SURFACE = {
    "ligne d'impression": (10, 9, 8),                  # PSA 10 tolere un leger defaut d'impression ; PSA 9 : un defaut mineur
    "trace de rouleau": (10, 9, 9),                    # lignes regulieres d'usine, tres faibles (roller marks)
    "point d'encre": (9, 9, 8),                        # petit point d'encre d'usine (print dot)
    "micro-creux": (9, 9, 8),                          # petit creux / trou d'epingle dans le vernis (pitting)
    "tache": (9, 8, 6),
    "empreinte": (9, 8, 6),
    "rayure": (9, 7, 5),                               # une micro-rayure vue seulement en lumiere rasante : -0,5
    "perte de lustre": (9, 8, 7),
    "cire": (9, 8, 7),                                 # tache de cire (vieux paquets)
    "bosse": (8, 7, 6),
    "decoloration": (8, 8, 7),                         # jaunissement, couleurs ternies
    "decollement": (8, 7, 6),                          # le foil ou le chrome qui se souleve, bulle
    # 3 nov 2026 (Will Smith YG #701, PSA 6 : un « 8 » ecrit sur une feuille posee dessus, enfonce pres de la tete) : une
    # MARQUE D'ECRITURE (chiffre, lettre, trait creuse dans le carton) ; PSA la paie cher, meme vue seulement en rasante
    "marque d'ecriture": (6, 6, 5),
    "pli": (5, 4, 3),
    "autre": (9, 8, 6),
}
# 9 nov 2026 (la Dickinson : « la tache brune est une vraie tache ») : PSA 10 = « aucune tache, de quelque sorte que ce soit » ;
# PSA 9 tolere « une tres legere tache de cire au DOS ». Une tache au dos est donc un cran moins grave qu'au devant (jamais 10).
SURFACE_DOS = {"tache": (9, 9, 8), "cire": (9, 9, 8)}
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
        # PSA 8 : 1 ou 2 coins ; 7 : quelques coins. 9 nov 2026 (Mathieu, la Willander : 3 coins du dos touches -> « 7,5 a 8 ») : 3 coins = 7,5
        return 8.0 if n["effilochage_leger"] <= 2 else 7.5 if n["effilochage_leger"] == 3 else 7.0 if n["effilochage_leger"] <= 4 else 6.0
    if n["point_blanc"]:
        return 9.0 if n["point_blanc"] == 1 else 8.5 if n["point_blanc"] <= 3 else 8.0
    return 10.0


def note_bords(etats):
    if not etats:
        return 10.0
    pire = min(ETATS_BORD[e][0] for e in etats)
    touches = sum(1 for e in etats if ETATS_BORD[e][0] < 10)
    # 9 nov 2026 (Mathieu, la Hutson Red Prism : quelques points blancs sur UN bord, le reste parfait -> « PSA 9 ») : de fins
    # points blancs sur un seul bord : 9 ; sur deux bords : 8,5 ; au-dela, ou de l'usure, le tableau
    fins = [e for e in etats if ETATS_BORD[e][0] < 10]
    if fins and all(e in ("point_blanc", "quelques_points") for e in fins) and len(fins) <= 2:
        return 9.0 if len(fins) == 1 else 8.5
    if pire >= 8 and touches >= 4:                     # usure repetee sur plusieurs aretes : un demi-point de plus
        return psa(pire - 0.5)
    if pire == 9 and touches >= 2:
        return 8.5
    return float(pire)


def note_surface(items):
    """items : [(type, visibilite)]. -> sous-note."""
    if not items:
        return 10.0
    def val(it):
        t, v = it[0], it[1]
        dos = len(it) > 2 and it[2] == 1
        tab = SURFACE_DOS.get(t) if dos and t in SURFACE_DOS else SURFACE.get(t, SURFACE["autre"])
        return tab[VISIBILITES.index(v) if v in VISIBILITES else 1]
    notes = [val(it) for it in items]
    items = [(it[0], it[1]) for it in items]
    pire = min(notes)
    rayures = sum(1 for t, v in items if t == "rayure" and v != "rasante")
    if rayures >= 2:                                   # plusieurs rayures vues sans lumiere rasante : 7 (5 si visibles a l'oeil)
        pire = min(pire, 5 if any(t == "rayure" and v == "visible" for t, v in items) else 7)
    elif sum(1 for t, v in items if t in ("rayure", "micro-creux") and v == "rasante") >= 3:
        pire = min(pire, 8)                            # plusieurs marques fines : -1 a -1,5
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


# 9 nov 2026 (Mathieu : les criteres de TAG, captures de taggrading.com) : la note TAG estimee avec les MEMES observations.
# TAG 10 Gem Mint (950-989) : devant centre a ~55/45, dos ~70/30 ; 4 coins nets (petits artefacts visibles seulement en haute
#   resolution ; une ou deux legeres touches au dos) ; une arete peut montrer un leger fil ; surface tres belle (un tout petit
#   defaut : micro-creux, rayure qui ne traverse pas le vernis, legere ligne d'impression ; le dos peut en avoir plus).
# TAG 9 Mint (900-949) : devant ~60/40, dos ~90/10 ; coins nets et carres, jusqu'a deux tres legeres touches visibles au
#   devant, plusieurs au dos ; usure legere visible sur un ou deux bords ; 2-3 petits creux et/ou une rayure plus longue sans
#   traverser le vernis, legere ligne d'impression ; au dos, une petite rayure qui traverse le vernis.
# TAG 10 Pristine (990-1000) : devant ~51/49, dos ~54,5/45,5 ; coins et aretes pratiquement parfaits (aucune usure visible,
#   presque rien meme en haute resolution) ; surface sans aucun defaut visible a l'oeil. Annonce SEULEMENT si le centrage
#   des deux faces est mesure (sans mesure, on ne peut pas tenir 51/49).
TAG_NIVEAUX = {"P": ("Pristine", "990–1000"), 10: ("Gem Mint", "950–989"), 9: ("Mint", "900–949")}
_TAG_CENTRAGE = {"P": (51, 54.5), 10: (55, 70), 9: (60, 90)}
_PIRE_COIN_TAG = {"net": 0, "point_blanc": 1, "effilochage_leger": 2, "effilochage": 3, "arrondi_leger": 4, "arrondi": 5, "plie": 6}


def _pct(ratio):
    try:
        return float(str(ratio).replace(",", ".").split("/")[0])
    except (TypeError, ValueError):
        return None


def tag(coins, bords, surface, centrage_devant=(), centrage_dos=()):
    """coins / bords : [(face 0|1, etat)] ; surface : [(face, type, visibilite)] ; centrage_* : ratios « 58/42 » mesures.
    -> {note: 10|9|None (8 ou moins), libelle, score, raisons: [ce qui empeche le cran du dessus]}"""
    dev = [p for p in (_pct(r) for r in centrage_devant or ()) if p]
    dos = [p for p in (_pct(r) for r in centrage_dos or ()) if p]

    fr = lambda v: (str(int(v)) if float(v).is_integer() else str(v).replace(".", ","))

    def bloque(n):
        r = []
        cd, cb = _TAG_CENTRAGE[n]
        nom = "Pristine" if n == "P" else str(n)
        if dev and max(dev) > cd:
            r.append(f"centrage du devant {fr(max(dev))}/{fr(100 - max(dev))} (TAG {nom} : {fr(cd)}/{fr(100 - cd)} au plus)")
        if dos and max(dos) > cb:
            r.append(f"centrage du dos {fr(max(dos))}/{fr(100 - max(dos))} (TAG {nom} : {fr(cb)}/{fr(100 - cb)} au plus)")
        if n == "P":
            if not dev or not dos:
                r.append("centrage des deux faces pas mesuré (Pristine : 51/49)")
            if any(e != "net" for _, e in coins):
                r.append("un coin pas parfait (Pristine : aucun)")
            if any(e not in ("net", "point_blanc") for _, e in bords) or sum(1 for _, e in bords if e == "point_blanc") > 1:
                r.append("arête pas parfaite (Pristine : presque rien)")
            if surface:
                r.append("un défaut de surface (Pristine : aucun visible)")
            return r
        cf = [e for f, e in coins if f == 0]
        cr = [e for f, e in coins if f == 1]
        if n == 10:
            if any(_PIRE_COIN_TAG.get(e, 6) > 1 for e in cf):
                r.append("un coin du devant touché (TAG 10 : 4 coins nets)")
            if sum(1 for e in cr if _PIRE_COIN_TAG.get(e, 6) == 2) > 2 or any(_PIRE_COIN_TAG.get(e, 6) > 2 for e in cr):
                r.append("coins du dos trop touchés (TAG 10 : une ou deux légères touches)")
        else:
            if sum(1 for e in cf if _PIRE_COIN_TAG.get(e, 6) >= 2) > 2 or any(_PIRE_COIN_TAG.get(e, 6) > 2 for e in cf):
                r.append("coins du devant trop touchés (TAG 9 : deux très légères touches au plus)")
            if any(_PIRE_COIN_TAG.get(e, 6) > 3 for e in cr):
                r.append("un coin du dos arrondi ou plié")
        bt = [e for f, e in bords if e != "net"]
        if n == 10:
            if any(e not in ("point_blanc", "quelques_points") for e in bt) or sum(1 for e in bt if e == "quelques_points") > 1:
                r.append("usure de bord (TAG 10 : un léger fil au plus)")
        else:
            if any(e in ("encoche", "ebrechures", "usure") for e in bt) or sum(1 for e in bt if e in ("quelques_points", "usure_legere")) > 2:
                r.append("usure sur plus de deux bords ou encoche (TAG 9 : légère, sur un ou deux bords)")
        sf = [(t, v) for f, t, v in surface if f == 0]
        sb = [(t, v) for f, t, v in surface if f == 1]
        graves = ("pli", "bosse", "marque d'ecriture", "perte de lustre", "decollement", "decoloration", "cire")
        if any(t in graves for t, _ in sf + sb):
            r.append("pli, bosse ou marque dans le carton")
        if n == 10:
            if len(sf) > 1 or any(v == "visible" for _, v in sf):
                r.append("plus d’un petit défaut de surface au devant (TAG 10 : un tout petit au plus)")
            if any(t == "rayure" and v == "visible" for t, v in sb):
                r.append("rayure visible au dos")
        else:
            if sum(1 for t, _ in sf if t == "rayure") > 1 or any(t == "rayure" and v == "visible" for t, v in sf) or len(sf) > 3:
                r.append("trop de défauts de surface au devant (TAG 9 : 2-3 petits ou une rayure légère)")
        return r
    for n in ("P", 10, 9):
        if not bloque(n):
            lib, sc = TAG_NIVEAUX[n]
            return {"note": 10 if n == "P" else n, "pristine": n == "P", "libelle": lib, "score": sc,
                    "raisons": bloque(10) if n == 9 else bloque("P")[:2] if n == 10 else [], "centrage_mesure": bool(dev or dos)}
    return {"note": None, "libelle": "8 ou moins", "score": "< 900", "raisons": bloque(9)[:3], "centrage_mesure": bool(dev or dos)}
