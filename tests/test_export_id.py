"""24 nov 2026 (Mathieu, une Rantanen Canvas Young Guns PSA 10 partie a 63 $ : « j'espere qu'on l'avait captee ») : nos archives
gardent une vente une fois par recherche qui l'a trouvee (cle : recherche + lien), au prix converti a quelques cents pres. L'export
des ventes (admin) donne maintenant le numero de l'annonce vendue, pour compter une vente UNE fois ; jamais le lien lui-meme."""
import gzip, io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LR_CALME_DEMARRAGE_S"] = "99999"; os.environ["LR_RECHAUFFER_S"] = "99999"
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import server
import base_ventes
T = "2015 UPPER DECK #C98 MIKKO RANTANEN UD CANVAS YOUNG GUNS RC ROOKIE PSA 10"
# la MEME vente trouvee par deux recherches, a deux taux de change ; une autre vente ; une vente sans lien
base_ventes.noter("rantanen canvas", [{"titre": T, "prix": 92.97, "le": "2026-10-22", "url": "https://www.ebay.com/itm/286123456789?nordt=true"}], sport="hockey")
base_ventes.noter("rantanen young guns psa 10", [{"titre": T, "prix": 92.99, "le": "2026-10-22", "url": "https://www.ebay.ca/itm/mikko-rantanen/286123456789"},
                                                {"titre": T, "prix": 114.38, "le": "2026-11-16", "url": "https://www.ebay.com/itm/286999000111"},
                                                {"titre": "2015-16 Upper Deck Canvas Mikko Rantanen", "prix": 40.0, "le": "2026-11-01"}], sport="hockey")
assert server._id_vente_export("https://www.ebay.com/itm/286123456789?nordt=true") == "286123456789"
assert server._id_vente_export("https://www.ebay.ca/itm/mikko-rantanen/286123456789") == "286123456789"
assert server._id_vente_export(None) == "" and server._id_vente_export("https://exemple.com/x") == ""
server.api._est_admin = lambda reel=False: True
c = server.app.test_client()
r = c.get("/admin/ventes_export.tsv.gz?sport=hockey")
assert r.status_code == 200, r.status_code
L = gzip.GzipFile(fileobj=io.BytesIO(r.data)).read().decode("utf-8").splitlines()
assert L[0] == "titre\tprix\tle\tq\tid", L[0]
lignes = [l.split("\t") for l in L[1:]]
assert len(lignes) == 4 and all(len(l) == 5 for l in lignes), lignes
ids = sorted(l[4] for l in lignes)
assert ids == ["", "286123456789", "286123456789", "286999000111"], ids      # la meme vente : le meme numero, deux fois
assert "ebay" not in "\n".join(L).lower() and "http" not in "\n".join(L)       # jamais un lien dans l'export
print("OK test_export_id")
