"""24 nov 2026 (Mathieu, une Rantanen UD Canvas Young Guns PSA 10 partie a 63 $ : « j'espere qu'on l'avait captee » ; puis « on doit
etre parfait avant Apple »). Nos archives gardent une vente une fois par recherche qui l'a trouvee, au prix converti a quelques
cents pres : 36 % des lignes de 30 $ et plus des 90 derniers jours etaient des doublons. Le test publie sur le site compte
maintenant UNE vente par numero d'annonce (la colonne « id » de l'export) et refuse d'ecrire le site sans elle."""
import gzip, os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI); sys.path.insert(0, os.path.join(ICI, "outils"))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_TESTS_TRAV"] = tempfile.mkdtemp()
import tests_site
T = "2015 UPPER DECK #C98 MIKKO RANTANEN UD CANVAS YOUNG GUNS RC ROOKIE PSA 10"
T2 = "Upper Deck 2015-16 UD Canvas Young Guns Mikko Rantanen RC #C98 PSA 10"


def fichier(lignes, entete="titre\tprix\tle\tq\tid"):
    p = os.path.join(tempfile.mkdtemp(), "v.tsv.gz")
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(entete + "\n" + "\n".join("\t".join(str(x) for x in l) for l in lignes) + "\n")
    return p


# 1. avec la colonne « id » : la meme annonce vendue (3 recherches, 3 prix a quelques cents, un jour d'ecart) = UNE vente
L = [(T, 92.97, "2026-10-22", "rantanen canvas", "286123456789"), (T, 92.99, "2026-10-22", "rantanen psa 10", "286123456789"),
     (T, 95.80, "2026-10-23", "rantanen young guns", "286123456789"),            # relue 3 semaines plus tard, a un autre taux (3 %)
     (T2, 114.38, "2026-11-16", "rantanen canvas", "286999000111"),
     (T, 70.0, "2026-10-30", "rantanen canvas", ""), (T, 70.0, "2026-10-30", "rantanen psa 10", "")]     # sans numero : le trio exact
r = tests_site.charger(fichier(L))
assert tests_site.DOUBLONS[0] == "exacts" and len(r) == 3, (tests_site.DOUBLONS, r)
assert sorted(x[1] for x in r) == [70.0, 92.97, 114.38]
# 2. un vieil export sans « id » : doublons ESTIMES (meme titre, a 1 jour pres, prix a 1 % pres) ; l'ecart de 3 % reste
r2 = tests_site.charger(fichier([l[:4] for l in L], "titre\tprix\tle\tq"))
assert tests_site.DOUBLONS[0] == "estimes" and sorted(x[1] for x in r2) == [70.0, 92.97, 95.8, 114.38], r2
# 3. le site ne s'ecrit pas avec des doublons estimes ; et la cle de carte du test est celle de l'app
src = open(os.path.join(ICI, "outils", "tests_site.py"), encoding="utf-8").read()
assert 'if DOUBLONS[0] != "exacts":' in src and "raise SystemExit" in src and "liquidite.cle_base(t)" in src
import liquidite
assert liquidite.cle_base(T) == liquidite.cle_base(T2) and liquidite.LIQ_MIN == 5 and liquidite.VERSION == 2
print("OK test_ventes_une_fois")
