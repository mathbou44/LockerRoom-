"""21 nov 2026 (Mathieu : « bons joueurs, marche qui diminue, pas parce qu'ils produisent moins ») : dans Tendances, « a acheter »
garde seulement un joueur cote A ou B qui n'est PAS en creux sur la glace ; « a vendre » garde tout joueur suivi ; chaque joueur
porte son ecart, « au plus bas depuis », son taux mesure ; la preuve sort telle quelle ; jamais un prix, seulement des %."""
import json, os, sys, tempfile
d = tempfile.mkdtemp(); os.environ["LOCKERROOM_DONNEES"] = d
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lockerroom, indice_joueurs, bareme_iq, marche_joueurs

NOTES = {"Bon Creux": 82.0, "Bon Glace Froide": 84.0, "Moyen Creux": 55.0, "Bon Sommet": 80.0, "Moyen Sommet": 50.0, "Legende Retraitee": 95.0}
I = {n: {"actif": True, "indice": 60, "equipe": "MTL", "criteres": {}, "pastilles": (["en_creux"] if n == "Bon Glace Froide" else [])} for n in NOTES}
I["Legende Retraitee"]["actif"] = False            # 21 nov 2026 (Gordie Howe dans « À acheter ») : « il joue bien » = un joueur ACTIF
indice_joueurs.lire = lambda: {"indice": I, "le": "2026-11-21T10:00:00"}
vrai_note = bareme_iq.note_joueur
bareme_iq.note_joueur = lambda nom, c=None, **k: (NOTES[nom], bareme_iq.lettre_joueur(NOTES[nom]), "test") if nom in NOTES else vrai_note(nom, c, **k)
assert bareme_iq.lettre_joueur(82.0)[:1] in ("A", "B") and bareme_iq.lettre_joueur(55.0)[:1] not in ("A", "B"), (bareme_iq.lettre_joueur(82.0), bareme_iq.lettre_joueur(55.0))
L = {"acheter": [{"nom": "Bon Creux", "vs_mediane_pct": -30, "sous_sommet_pct": -40, "mois_pct": -5, "taux": 0.58, "mois": 3, "gain": 24.0, "bas_depuis_j": 300, "haut_depuis_j": 0, "hist_j": 364, "n": 40},
                 {"nom": "Bon Glace Froide", "vs_mediane_pct": -28, "sous_sommet_pct": -35, "mois_pct": -5, "taux": 0.58, "bas_depuis_j": 90, "haut_depuis_j": 0, "hist_j": 364, "n": 40},
                 {"nom": "Moyen Creux", "vs_mediane_pct": -25, "sous_sommet_pct": -30, "mois_pct": -5, "taux": 0.54, "bas_depuis_j": 60, "haut_depuis_j": 0, "hist_j": 364, "n": 40},
                 {"nom": "Legende Retraitee", "vs_mediane_pct": -34, "sous_sommet_pct": -40, "mois_pct": -5, "taux": 0.65, "bas_depuis_j": 60, "haut_depuis_j": 0, "hist_j": 364, "n": 40},
                 {"nom": "Pas Suivi", "vs_mediane_pct": -25, "sous_sommet_pct": -30, "mois_pct": -5, "taux": 0.54, "bas_depuis_j": 60, "haut_depuis_j": 0, "hist_j": 364, "n": 40}],
     "vendre": [{"nom": "Bon Sommet", "vs_mediane_pct": 62, "sous_sommet_pct": 40, "mois_pct": 30, "taux": 0.94, "bas_depuis_j": 0, "haut_depuis_j": 350, "hist_j": 350, "n": 30},
                {"nom": "Moyen Sommet", "vs_mediane_pct": 35, "sous_sommet_pct": 12, "mois_pct": 20, "taux": 0.76, "bas_depuis_j": 0, "haut_depuis_j": 120, "hist_j": 300, "n": 30}]}
PREUVE = {"achat": {"taux": 0.58, "base": 0.35, "n": 89, "joueurs": 28, "essais": [{"regle": ["mediane", 0.2], "n": 89, "joueurs": 28, "taux": 0.58, "borne": 0.48, "gain_med": 13.9}], "du": "2026-03-15", "au": "2026-09-06"}}
marche_joueurs.liste = lambda signal, n=40: L[signal][:n]
marche_joueurs.preuve = lambda: PREUVE
ETATS = {x["nom"]: dict(x, signal=s) for s, l in L.items() for x in l}
marche_joueurs.etat = lambda nom: ETATS.get(nom)

api = lockerroom.Api()
lockerroom.Api._TEND_IQ.update(v=None, le=0)
r = api.tendances_iq()
assert r["ok"], r
a, v = r["cats"]["acheter"], r["cats"]["vendre"]
assert [x["nom"] for x in a] == ["Bon Creux"], [x["nom"] for x in a]            # pas le joueur en creux sur la glace, pas le C, pas l'inconnu
assert [x["nom"] for x in v] == ["Bon Sommet", "Moyen Sommet"], [x["nom"] for x in v]
m = a[0]["marche"]
assert m == {"vs_mediane_pct": -30, "sous_sommet_pct": -40, "mois_pct": -5, "taux": 0.58, "mois": 3, "gain": 24.0, "bas_depuis_j": 300, "haut_depuis_j": 0, "hist_j": 364}, m
assert a[0]["lettre"][:1] in ("A", "B") and v[0]["marche"]["haut_depuis_j"] == 350
assert r["compte"]["acheter"] == 1 and r["compte"]["vendre"] == 2 and r["preuve"] == PREUVE
# jamais un prix : aucune cle de prix dans ce qui sort pour ces listes
assert not any(k in json.dumps(a + v) for k in ('"prix"', '"mediane"', '"moyenne"', '"niveau"')), "des ecarts en %, jamais un prix"

# la fiche du joueur : son marche sur 12 mois ; le signal « acheter » suit la meme regle (pas en creux sur la glace, A ou B)
t = api.tendance_joueur("Bon Creux")
lg = ((t.get("iq") or t).get("marche") or {}).get("long") if isinstance(t, dict) else None
if lg is not None:
    assert lg["vs_mediane_pct"] == -30 and lg["bas_depuis_j"] == 300 and lg.get("signal") == "acheter" and lg.get("taux") == 0.58 and lg.get("mois") == 3, lg
    t2 = api.tendance_joueur("Bon Glace Froide"); l2 = ((t2.get("iq") or t2).get("marche") or {}).get("long") or {}
    assert l2.get("vs_mediane_pct") == -28 and "signal" not in l2, l2
    t3 = api.tendance_joueur("Bon Sommet"); l3 = ((t3.get("iq") or t3).get("marche") or {}).get("long") or {}
    assert l3.get("signal") == "vendre", l3
print("OK test_tendances_marche (a acheter : %s ; a vendre : %s ; fiche : %s)" % ([x["nom"] for x in a], [x["nom"] for x in v], "long" if lg is not None else "sans fiche ici"))

# -- le Radar (Mathieu, Caufield : « le genre de joueur qu'on devrait avoir dans le Radar quand on cherche qui acheter ») : les
#    cartes d'un joueur « A acheter » montent, avec son ecart ; pas celles du joueur en creux sur la glace ni du joueur cote C
lockerroom._ACH_RADAR.update(le=0.0, v={})
N = lockerroom.a_acheter_noms()
assert N == {"bon creux": -30}, N
import marche_cles
marche_cles.bas = lambda nom: None
A = [{"titre": "2020-21 Upper Deck Young Guns Bon Creux #201", "joueur": "Bon Creux", "prix": 50.0},
     {"titre": "2020-21 Upper Deck Young Guns Bon Glace Froide #202", "joueur": "Bon Glace Froide", "prix": 50.0},
     {"titre": "2020-21 Upper Deck Young Guns Moyen Creux #203", "joueur": "Moyen Creux", "prix": 50.0}]
lockerroom.Api._pour_moi(A, {})
assert A[0].get("marche_bas") == -30 and A[0]["pour_moi_pts"] >= lockerroom.Api.MARCHE_BAS_PTS, A[0]
assert "marche_bas" not in A[1] and "marche_bas" not in A[2], (A[1], A[2])
# « Tu en as N » : les joueurs que le compte a en main (En stock ou Listee), pour mettre SES joueurs d'abord dans « A vendre »
api.carte_sauver({"titre": "2020-21 Upper Deck Young Guns Bon Sommet #201", "joueur": "Bon Sommet", "statut": "En stock"})
api.carte_sauver({"titre": "2021-22 SP Authentic Bon Sommet Future Watch", "joueur": "Bon Sommet", "statut": "En stock"})
api.carte_sauver({"titre": "2019-20 O-Pee-Chee Moyen Sommet", "joueur": "Moyen Sommet", "statut": "Vendue"})
jm = api.joueurs_en_main()
assert jm["ok"] and jm["joueurs"].get("bon sommet") == 2 and "moyen sommet" not in jm["joueurs"], jm
print("OK test_tendances_marche (Radar : la carte d'un joueur a acheter monte, ecart %s %%)" % A[0]["marche_bas"])
