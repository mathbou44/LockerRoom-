"""25 nov 2026 (Mathieu : « on aurait du capter cette carte-la » ; « on ne devrait jamais manquer ce genre de deal-la ») : le
registre des annonces jugees et le rapport des aubaines manquees (manquees.py). Aucun credit, aucun contenu d'eBay garde."""
import os, sys, tempfile, json, sqlite3
from datetime import datetime, timedelta, timezone
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
RAC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAC)
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import deals, manquees

M = datetime.now(timezone.utc)
jr = lambda n: (M - timedelta(days=n)).strftime("%Y-%m-%d")
T = "2025-26 Upper Deck SP Authentic Limited Auto Material Patch Mikhail Sergachev /100"
num = lambda i: str(198720521000 + i)
# la meme carte : 6 ventes autour de 70 $ avant, puis 5 ventes d'hier a 32 $ (cinq annonces differentes)
avant = [{"titre": T, "prix": p, "le": jr(20 + i), "url": "https://www.ebay.ca/itm/" + num(100 + i)} for i, p in enumerate((72, 68, 70, 69, 71, 70))]
hier = [{"titre": T, "prix": 32.0, "le": jr(1), "url": "https://www.ebay.ca/itm/" + num(i)} for i in range(5)]
cher = {"titre": T, "prix": 66.0, "le": jr(1), "url": "https://www.ebay.ca/itm/" + num(50)}
b = deals.Bassin(charger=False)
b.ajouter(avant + hier + [cher])

# 1. l'empreinte : a sens unique, la meme pour « v1|123|0 », le numero et l'adresse ; rien d'eBay dans la base
assert manquees.empreinte(num(1)) == manquees.empreinte("v1|" + num(1) + "|0") and manquees.empreinte("abc") is None
assert num(1) not in manquees.empreinte(num(1)) and len(manquees.empreinte(num(1))) == 24

# 2. une aubaine : la valeur vient des ventes d'AVANT, sans la vente elle-meme
a = manquees.aubaine(dict(hier[0], num=num(0)), b)
assert a and 60 <= a[0] <= 75 and a[1] == round(deals.prix_max(a[0]), 2) and 32.0 <= a[1], a
assert manquees.aubaine(dict(cher, num=num(50)), b) is None                       # 66 $ : au-dessus du prix max
assert manquees.aubaine({"titre": "Lot of 50 hockey cards", "prix": 5, "le": jr(1), "num": "1"}, b) is None

# 3. sans registre : rien n'est mesure (une vente d'avant le registre ne peut pas avoir ete vue)
r0 = manquees.calculer(bassin=b, ventes=hier + [cher], maint=M)
assert r0["depuis"] is None and not r0["jours"], r0

# 4. le registre : le verdict le plus fort reste ; « deal » ne s'efface jamais ; l'heure du 1er deal est gardee
il_y_a = lambda j, h=0: M - timedelta(days=j, hours=h)
fin = lambda j, h: (il_y_a(j) + timedelta(hours=h)).isoformat().replace("+00:00", "Z")
an = lambda i, h=5.0, j=3: {"item_id": num(i), "fin": fin(j, h), "encan": True}
manquees.noter(an(0), "fenetre", il_y_a(3))                                        # vue trop tot, puis jugee : un deal
manquees.noter(an(0), "deal", il_y_a(3) + timedelta(hours=3), valeur=70)           # 2 h avant la fin
manquees.noter(an(0), "trop_cher", il_y_a(3) + timedelta(hours=4))                 # la mise a monte : reste « montree »
manquees.noter(an(1), "sans_ventes", il_y_a(3))
manquees.noter(an(1), "fenetre", il_y_a(3) + timedelta(hours=1))                   # un verdict plus faible ne remplace pas
manquees.noter(an(2), "trop_cher", il_y_a(3), valeur=69.5)
manquees.noter(an(3, 0.4), "deal", il_y_a(3))                                      # montree 24 minutes avant la fin
assert manquees.vider() == 7
reg, debut = manquees._registre({manquees.empreinte(num(i)) for i in range(6)})
assert len(reg) == 4 and debut == int(il_y_a(3).timestamp())
r_0 = reg[manquees.empreinte(num(0))]
assert r_0["deal"] and r_0["res"] == "deal" and r_0["deal_h"] == 2.0 and r_0["avant_h"] == 5.0 and r_0["val"] == 70, r_0
assert reg[manquees.empreinte(num(1))]["res"] == "sans_ventes" and reg[manquees.empreinte(num(2))]["val"] == 69.5
c = sqlite3.connect(manquees._chemin())
assert not [x for x in c.execute("SELECT * FROM vus") if any(num(i) in str(x) for i in range(6))]      # aucun numero d'annonce
c.close()

# 5. le rapport : 5 aubaines hier ; 2 montrees (dont 1 trop tard) ; les 3 autres : sans valeur, trop chere, jamais vue
r = manquees.calculer(bassin=b, ventes=hier + [cher], maint=M)
j = r["jours"][jr(1)]
assert j["ventes"] == 6 and j["aubaines"] == 5 and j["montrees"] == 2 and j["tard"] == 1, j
assert j["raisons"] == {"sans_valeur": 1, "trop_cher": 1, "jamais_vue": 1}, j
assert len(r["exemples"]) == 3 and {x["raison"] for x in r["exemples"]} == {"sans_valeur", "trop_cher", "jamais_vue"}
assert all(x["prix"] == 32.0 and x["valeur"] == a[0] and "itm" not in json.dumps(x) for x in r["exemples"]), r["exemples"]
s = manquees.resume(maint=M)
assert s["periode"]["aubaines"] == 5 and s["periode"]["montrees"] == 2 and s["periode"]["part"] == 0.4 and s["periode"]["jours"] == 1, s["periode"]
assert s["par_jour"][0]["jour"] == jr(1) and s["depuis"] == jr(2)
# une vente d'AVANT le premier jour entier du registre n'est pas comptee ; ni celle d'aujourd'hui (journee incomplete)
r2 = manquees.calculer(bassin=b, ventes=[dict(hier[0], le=jr(5)), dict(hier[1], le=jr(0))], maint=M)
assert jr(5) not in r2["jours"] and jr(0) not in r2["jours"] and r2["jours"][jr(1)]["aubaines"] == 5       # les jours deja mesures restent
# aux 12 heures seulement
assert manquees.calculer_si_besoin(b) is None

# 6. le chasseur ecrit au registre a chaque annonce jugee (deal, trop chere, sans valeur, hors fenetre), sans appel de plus
st, dl = {}, {}
bon = {"item_id": num(60), "titre": T, "prix_cad": 20.0, "port_cad": 0.0, "encan": True, "mises": 4, "fin": (M + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
       "vendeur": "petit_vendeur", "vendeur_score": 900, "photo": None, "url": "u"}
loin = dict(bon, item_id=num(61), fin=(M + timedelta(days=4)).isoformat().replace("+00:00", "Z"))
lot = dict(bon, item_id=num(62), titre="Lot of 40 hockey cards mixed")
for x in (bon, loin, lot):
    deals._juger(x, {"q": None, "flux": "petits vendeurs", "sport": "hockey", "joueur": None}, [], [], M, dl, st, bassin=b, verif=None)
manquees.vider()
reg2, _d = manquees._registre({manquees.empreinte(num(i)) for i in (60, 61, 62)})
assert reg2[manquees.empreinte(num(61))]["res"] == "fenetre" and reg2[manquees.empreinte(num(62))]["res"] == "joueur", reg2
assert reg2[manquees.empreinte(num(60))]["res"] in ("deal", "photo", "trop_cher", "sans_ventes", "comps_vieilles"), reg2
assert "_sortie" not in st

# 7. le grand format n'est pas la carte (1er essai sur nos ventes : une Schaefer Young Guns « Oversized » comptee comme une aubaine)
import cartes_match as cm
reg_, ov = "2025-26 Upper Deck Series 2 Young Guns Matthew Schaefer #451 RC", "2025-26 Upper Deck Series 2 - Young Guns Matthew Schaefer #451 Oversized (RC)"
assert cm.raisons_refus(cm.cible_titre(reg_), ov) and cm.raisons_refus(cm.cible_titre(ov), reg_)
assert not cm.raisons_refus(cm.cible_titre(ov), "Upper Deck 2025-26 Young Guns #451 Matthew Schaefer over-size") and not cm.raisons_refus(cm.cible_titre(reg_), reg_)

assert cm.abimee("Upper Deck 24-25 Series 1 Young Guns #229 Lane Hutson RC READ DESCRIPTION") and cm.abimee("Bedard YG see desc") and not cm.abimee(reg_)
# un autre sport dans nos ventes de hockey n'est pas une aubaine du chasseur
assert manquees.aubaine({"titre": "1990 Upper Deck Ken Griffey Jr #156 Graded 9 Seattle Mariners", "prix": 5, "le": jr(1), "num": "9"}, b) is None

# 8. l'ecran et l'API : admin seulement
app = open(os.path.join(RAC, "source", "src_app.html"), encoding="utf-8").read()
api = open(os.path.join(RAC, "lockerroom.py"), encoding="utf-8").read()
assert "async function feuilleManquees()" in app and "() => feuilleManquees()]" in app and "API.aubaines_manquees()" in app
i = api.index("def aubaines_manquees(self)")
assert "self._est_admin()" in api[i:i + 600]
dl_ = open(os.path.join(RAC, "deals.py"), encoding="utf-8").read()
assert "manquees.calculer_si_besoin(b)" in dl_ and "manquees.vider()" in dl_
print("AUBAINES MANQUEES OK", j, s["periode"]["part"])
