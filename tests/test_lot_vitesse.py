"""23 nov 2026 (Mathieu, lot de 4 cartes : « c'est quand meme long ce processus » ; « incapable de supprimer une carte a partir
de ce stade »). Journal du serveur : 1 min 50 s pour 4 cartes, puis 10,0 s pour ouvrir la mise en vente et 6,6 s pour
reverifier les dos.
- la mise en vente ne lit que les cartes a programmer (plus tout l'inventaire) ;
- la 2e verification des dos (11 nov) reste telle quelle ;
- 3 cartes a la fois, et chaque carte ecrit ses temps dans le journal (on corrige ce qui est mesure) ;
- a l'etape des prix, « Retirer » sort une carte du lot."""
import json, os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ.setdefault("LR_CALME_DEMARRAGE_S", "99999"); os.environ.setdefault("LR_RECHAUFFER_S", "99999")
import lockerroom
api = lockerroom.Api()

# 1. les cartes a programmer : les memes qu'avant, mais triees par la base
c = api._db()
for i, (statut, item) in enumerate([("En stock", None), ("Vendue", None), ("Listée", "405000000001"), ("En stock", "405000000002"), ("En stock", ""), ("En stock", None)]):
    c.execute("INSERT INTO cartes (titre, joueur, statut, item_number, photo, photos, prix_demande) VALUES (?,?,?,?,?,?,?)",
              (f"2024-25 Upper Deck Series 1 Young Guns Joueur {i} #20{i} RC", f"Joueur {i}", statut, item, "a.jpg", json.dumps(["a.jpg", "b.jpg"]), 30.0))
c.commit(); c.close()
tout = [x["id"] for x in api.inventaire_liste({}) if not (x.get("statut") in ("Vendue", "Listée") or x.get("item_number"))]
lus = []
vraie = api.inventaire_liste
api.inventaire_liste = lambda f=None: (lus.append(dict(f or {})), vraie(f))[1]
r = api.serie_candidates()
api.inventaire_liste = vraie
assert sorted(x["id"] for x in r["cartes"]) == sorted(tout) and len(tout) == 3, (r["cartes"], tout)
assert lus == [{"a_programmer": True}], lus
assert len(vraie({"a_programmer": True})) == 3 and len(vraie({})) == 6

# 2. le filet du 11 nov reste entier : la lecture d'un lot ne remplit jamais le cache de paires_verifier a sa place
#    (essaye le 23 nov pour gagner 6,6 s, retire : c'est la 2e verification qui a ete demandee apres 3 annonces au mauvais dos)
assert "_paires_noter" not in open(os.path.join(ICI, "lockerroom.py"), encoding="utf-8").read()

# 3. le lot : 3 a la fois, les temps au journal, la paire notee seulement si la lecture l'a confirmee
src = open(os.path.join(ICI, "lockerroom.py"), encoding="utf-8").read()
assert lockerroom.Api.LOT_PARALLELE == 3
assert 'print(f"Lot : carte lue en ' in src and 'print(f"Preparer lent : ' in src

# 4. l'ecran : « Retirer » a l'etape des prix, sans supprimer la carte de l'inventaire
app = open(os.path.join(ICI, "source", "src_app.html"), encoding="utf-8").read()
assert "data-prt=\"${x.id}\">${tt('Retirer', 'Remove')}" in app
i = app.index("$$('[data-prt]')"); bloc = app[i:i + 520]
assert "PG.choisis.delete(x_.id)" in bloc and "if (!PG.choisis.size) PG.etape = 1" in bloc and "carte_supprimer" not in bloc
assert "elle reste dans ton inventaire" in bloc
print("OK test_lot_vitesse")
