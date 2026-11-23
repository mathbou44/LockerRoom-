# SIGNAL PAR JOUEUR, version 1 (recherche, pas dans l'app). Une regle par CAS : on reconnait d'abord le cas du joueur
# (recrue de l'annee, jeune, veteran), puis l'evenement du jour (gros match, tour du chapeau, sequence en feu, panne, nouvelle
# sans performance). Entrees : seulement ce qui est public le soir meme (matchs de la LNH, vues Wikipedia, annee de la carte recrue).
# AUCUN prix n'entre dans le declencheur. Les chiffres attendus viennent de rejoue.py (meme carte, avant et apres).
import datetime as dt

def saison(d):
    y = dt.date.fromordinal(d)
    return y.year - (y.month < 8)

def cas_joueur(annee_recrue, d):
    """recrue = ses cartes recrues sont de cette saison ; jeune = 1 ou 2 saisons apres ; veteran sinon (ou inconnu)."""
    if not annee_recrue: return 'veteran'
    a = saison(d) - annee_recrue
    return 'recrue' if a <= 0 else 'jeune' if a <= 2 else 'veteran'

def evenements(G, i, cas):
    """G = [(jour, points, buts)] en ordre ; i = le match du jour. Renvoie les evenements declenches par CE match."""
    pts = [g[1] for g in G]; p, b = G[i][1], G[i][2]; ev = []
    if cas == 'recrue':
        if i < 3: return ev
        if b >= 3: ev.append('chapeau')
        if p >= 3 or b >= 2: ev.append('gros')
        if i >= 5 and sum(pts[i - 2:i + 1]) >= 5 and sum(pts[i - 3:i]) < 5: ev.append('feu')
        if i >= 8 and sum(pts[i - 3:i + 1]) == 0 and sum(pts[i - 4:i]) > 0 and sum(pts[:i - 3]) / (i - 3) >= 0.4: ev.append('panne')
        return ev
    if i < 40: return ev
    base = sum(pts[i - 40:i]) / 40
    if b >= 3: ev.append('chapeau')
    if p >= 3 or b >= 2: ev.append('gros')
    if sum(pts[i - 4:i + 1]) >= 5 * (base + 0.6) and sum(pts[i - 5:i]) < 5 * (base + 0.6): ev.append('feu')
    if base >= 0.5 and sum(pts[i - 3:i + 1]) == 0 and sum(pts[i - 4:i]) > 0: ev.append('panne')
    return ev

# le tableau de decision : (cas, evenement) -> (signal, raison courte). Le premier evenement de la liste qui s'applique gagne.
ORDRE = ['panne', 'chapeau', 'gros', 'feu', 'pic']
REGLES = {
    ('recrue', 'panne'): ('VENDS', 'Recrue en panne : 4 matchs sans point'),
    ('recrue', 'chapeau'): ('NEUTRE', 'Recrue, gros match : hausse d\'un jour'),
    ('recrue', 'gros'): ('NEUTRE', 'Recrue, gros match : hausse d\'un jour'),
    ('recrue', 'feu'): ('NEUTRE', 'Recrue en feu : hausse courte'),
    ('recrue', 'pic'): ('NEUTRE', 'Recrue dans les nouvelles'),
    ('jeune', 'panne'): ('ATTENDS', 'En panne : 4 matchs sans point'), ('veteran', 'panne'): ('ATTENDS', 'En panne : 4 matchs sans point'),
    ('jeune', 'chapeau'): ('ACHETE', 'Tour du chapeau ce soir'), ('veteran', 'chapeau'): ('ACHETE', 'Tour du chapeau ce soir'),
    ('jeune', 'gros'): ('ACHETE', 'Gros match ce soir'), ('veteran', 'gros'): ('ACHETE', 'Gros match ce soir'),
    ('jeune', 'feu'): ('ACHETE', 'Sequence en feu qui commence'), ('veteran', 'feu'): ('ACHETE', 'Sequence en feu qui commence'),
    ('jeune', 'pic'): ('VENDS', 'Dans les nouvelles, sans gros match : la hausse s\'efface'), ('veteran', 'pic'): ('VENDS', 'Dans les nouvelles, sans gros match : la hausse s\'efface'),
}
def signal(cas, evs):
    """-> (signal, raison, evenement). Sans evenement : la recrue de l'annee est ATTENDS (ses cartes baissent jusqu'a ~12 mois), les autres NEUTRE."""
    for e in ORDRE:
        if e in evs: return (*REGLES[(cas, e)], e)
    return ('ATTENDS', 'Carte de l\'annee : elle baisse encore', None) if cas == 'recrue' else ('NEUTRE', '', None)
