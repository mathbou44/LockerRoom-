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
marche_joueurs.liste_bas = lambda n=40, **k: [dict(x, taux=None) for x in L["acheter"]][:n]
marche_joueurs.liste_haut = lambda n=40, **k: [{c: v_ for c, v_ in x.items() if c not in ("taux", "mois", "gain")} for x in L["vendre"]][:n]
ETATS = {x["nom"]: dict(x, signal=s) for s, l in L.items() for x in l}
marche_joueurs.etat = lambda nom: ETATS.get(nom)

api = lockerroom.Api()
# 23 nov 2026 : « A vendre » n'est pas prouve au prix reel -> retire de Tendances et de la fiche, pour tous
lockerroom.Api._TEND_IQ.update(v=None, le=0)
r0 = api.tendances_iq()
assert lockerroom.VENTE_PROUVEE is False and not (r0["cats"].get("vendre") or []) and r0["compte"]["vendre"] == 0 and r0["cats"]["acheter"], r0["compte"]
t0 = api.tendance_joueur("Bon Sommet"); l0 = ((t0.get("iq") or t0).get("marche") or {}).get("long") if isinstance(t0, dict) else None
assert l0 is None or "signal" not in l0, l0
# 23 nov 2026 (Mathieu : « on a enleve "at their highest" ?! ») : le FAIT reste : « Au plus haut », le pendant de « Au plus bas »
# (bon joueur actif, A ou B), sans taux, sans delai, sans gain : aucun conseil de vente, et jamais un prix
h0 = r0["cats"]["haut"]
assert [x["nom"] for x in h0] == ["Bon Sommet"] and r0["compte"]["haut"] == 1, ([x["nom"] for x in h0], r0["compte"])       # « Moyen Sommet » est cote C
assert h0[0]["marche"]["haut_depuis_j"] == 350 and h0[0]["marche"]["vs_mediane_pct"] == 62 and not h0[0]["marche"].get("taux") and not h0[0]["marche"].get("gain"), h0[0]["marche"]
lockerroom.VENTE_PROUVEE = True                    # le mecanisme reste pret : le reste du test le rallume
lockerroom.Api._TEND_IQ.update(v=None, le=0)
r = api.tendances_iq()
assert r["ok"], r
a, v = r["cats"]["acheter"], r["cats"]["vendre"]
assert [x["nom"] for x in a] == ["Bon Creux"], [x["nom"] for x in a]            # pas le joueur en creux sur la glace, pas le C, pas l'inconnu
assert [x["nom"] for x in v] == ["Bon Sommet", "Moyen Sommet"], [x["nom"] for x in v]
m = a[0]["marche"]
assert m == {"vs_mediane_pct": -30, "sous_sommet_pct": -40, "mois_pct": -5, "taux": 0.58, "mois": 3, "gain": 24.0, "bas_depuis_j": 300, "haut_depuis_j": 0, "hist_j": 364, "courbe": None}, m
assert a[0]["lettre"][:1] in ("A", "B") and v[0]["marche"]["haut_depuis_j"] == 350
# « au plus bas » : un fait montre a tous, meme filtre « bon joueur » (actif, pas en creux sur la glace, A ou B)
assert [x["nom"] for x in r["cats"]["bas"]] == ["Bon Creux"] and r["compte"]["bas"] == 1 and r["cats"]["bas"][0]["marche"]["bas_depuis_j"] == 300, r["cats"]["bas"]
assert r["compte"]["acheter"] == 1 and r["compte"]["vendre"] == 2 and r["preuve"] == PREUVE
assert not r["cats"].get("haut") and r["compte"]["haut"] == 0, "« A vendre » rallume : la liste de faits « Au plus haut » lui laisse la place"
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
# 23 nov 2026 (Mathieu : « pourquoi juste 10 et 18 ? Un top 25 dans chaque, du plus gros pourcentage au plus petit ; la meme vue en
# Gratuit, avec seulement les 5 du bas debloques ») : 30 bons joueurs au plus bas et 30 au plus haut -> 25 de chaque, le plus gros
# ecart d'abord ; en Gratuit, les 20 premiers gardent leur % et leur courbe, jamais leur nom ; les 5 derniers se lisent
lockerroom.VENTE_PROUVEE = False
for i in range(30):
    for pre in ("Bas", "Haut"):
        NOTES[f"{pre} {i:02d}"] = 80.0
        I[f"{pre} {i:02d}"] = {"actif": True, "indice": 60, "equipe": "MTL", "criteres": {}, "pastilles": []}
marche_joueurs.liste_bas = lambda n=40, **k: [{"nom": f"Bas {i:02d}", "vs_mediane_pct": -(2 + (i * 7) % 31), "sous_sommet_pct": -50, "bas_depuis_j": 40 + i, "haut_depuis_j": 0, "hist_j": 364, "courbe": [1.0, 0.9]} for i in range(30)][:n]
marche_joueurs.liste_haut = lambda n=40, **k: [{"nom": f"Haut {i:02d}", "vs_mediane_pct": 2 + (i * 11) % 37, "sous_sommet_pct": 0, "bas_depuis_j": 0, "haut_depuis_j": 40 + i, "hist_j": 364, "courbe": [0.9, 1.0]} for i in range(30)][:n]
lockerroom.Api._TEND_IQ.update(v=None, le=0)
rp = api.tendances_iq()
pb, ph = [x["marche"]["vs_mediane_pct"] for x in rp["cats"]["bas"]], [x["marche"]["vs_mediane_pct"] for x in rp["cats"]["haut"]]
# 26 nov 2026 (« le top 100 pour les 2 ») : 100 au plus ; ici 30 bons joueurs de chaque cote : les 30 y sont
assert len(pb) == 30 and len(ph) == 30 and lockerroom.Api.TEND_TOP == 100, (len(pb), len(ph))
assert pb == sorted(pb) and pb[0] == -32 and ph == sorted(ph, reverse=True) and ph[0] == 38, (pb[:3], ph[:3])       # le plus gros ecart d'abord
assert all(x.get("nom") and not x.get("verrou") for x in rp["cats"]["bas"] + rp["cats"]["haut"]) and "gratuit" not in rp      # en Pro : tout se lit
rg = api._tendances_gratuit(rp)
for cat_ in ("bas", "haut"):
    Lg = rg["cats"][cat_]
    assert len(Lg) == 30 and all(x.get("verrou") for x in Lg[:25]) and not any(x.get("verrou") for x in Lg[25:]), cat_
    assert all(set(x) == {"verrou", "marche"} and set(x["marche"]) == {"vs_mediane_pct", "courbe"} for x in Lg[:25]), "une ligne verrouillee : son % et sa courbe, jamais le nom"
    assert [x["marche"]["vs_mediane_pct"] for x in Lg] == [x["marche"]["vs_mediane_pct"] for x in rp["cats"][cat_]]     # le meme ordre, les memes %
    assert [x["nom"] for x in Lg[25:]] == [x["nom"] for x in rp["cats"][cat_][25:]]                                     # les 5 du bas : tels quels
assert "Bas 0" not in json.dumps(rg["cats"]["bas"][:25]) and rg["gratuit"] == {"verrous": 50, "libres": 5, "top": 100}
# au-dela de 100 bons joueurs : les 100 plus gros ecarts seulement
lb0, lh0 = marche_joueurs.liste_bas, marche_joueurs.liste_haut
for i in range(30, 130):
    NOTES[f"Bas {i:03d}"] = 80.0
    I[f"Bas {i:03d}"] = {"actif": True, "indice": 60, "equipe": "MTL", "criteres": {}, "pastilles": []}
marche_joueurs.liste_bas = lambda n=40, **k: lb0(n) + [{"nom": f"Bas {i:03d}", "vs_mediane_pct": -(40 + i), "sous_sommet_pct": -50, "bas_depuis_j": 40, "haut_depuis_j": 0, "hist_j": 364, "courbe": [1.0, 0.9]} for i in range(30, 130)][:max(0, n - 30)]
lockerroom.Api._TEND_IQ.update(v=None, le=0)
r100 = api.tendances_iq()["cats"]["bas"]
assert len(r100) == 100 and r100[0]["marche"]["vs_mediane_pct"] == -169 and r100[-1]["marche"]["vs_mediane_pct"] == -70, (len(r100), r100[0]["marche"], r100[-1]["marche"])
marche_joueurs.liste_bas = lb0
lockerroom.Api._TEND_IQ.update(v=None, le=0)
assert rp["cats"]["bas"][0].get("nom"), "la reponse gardee pour tous n'est pas touchee par le Gratuit"
pt = api._tendances_gratuit({**rp, "cats": {**rp["cats"], "bas": rp["cats"]["bas"][:4], "haut": []}})                  # une courte liste : rien de verrouille
assert not any(x.get("verrou") for x in pt["cats"]["bas"]) and pt["gratuit"]["verrous"] == 0
print("OK test_tendances_marche (top 100 au plus : %s ... %s ; %s ... %s ; Gratuit : les 5 derniers lisibles)" % (pb[0], pb[-1], ph[0], ph[-1]))
lockerroom.VENTE_PROUVEE = True
print("OK test_tendances_marche (a acheter : %s ; a vendre : %s ; fiche : %s)" % ([x["nom"] for x in a], [x["nom"] for x in v], "long" if lg is not None else "sans fiche ici"))

# -- le Radar (Mathieu, Caufield : « le genre de joueur qu'on devrait avoir dans le Radar quand on cherche qui acheter ») : les
#    cartes d'un joueur « A acheter » montent, avec son ecart ; pas celles du joueur en creux sur la glace ni du joueur cote C
# 21 nov 2026 (soir) : tant que l'achat n'est pas prouve, rien ne monte dans le Radar ; le mecanisme reste pret
assert lockerroom.ACHAT_PROUVE is False and lockerroom.a_acheter_noms() == {}
lockerroom.ACHAT_PROUVE = True
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
