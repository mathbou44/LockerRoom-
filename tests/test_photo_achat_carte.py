"""21 nov 2026 (Mathieu : « la photo doit etre importee directement aussi ») : une carte ajoutee toute seule depuis un achat eBay
recoit la photo de l'achat des qu'elle est connue ; jamais par-dessus une photo deja la ; jamais sur une carte faite a la main."""
import os, sys, tempfile
d = tempfile.mkdtemp(); os.environ["LOCKERROOM_DONNEES"] = d
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lockerroom
api = lockerroom.Api()
a = api.carte_sauver({"titre": "2025-26 Artifacts Rookie Orange Porter Martone /149", "statut": "En stock", "source": "achat eBay"})["id"]
b = api.carte_sauver({"titre": "2025-26 Upper Deck Young Guns Ivan Demidov", "statut": "En stock", "source": "achat eBay", "photo": "https://i.ebayimg.com/deja.jpg"})["id"]
m = api.carte_sauver({"titre": "2024-25 SP Authentic Macklin Celebrini", "statut": "En stock"})["id"]
c = api._db()
try:
    api._achats_table(c)
    for iid, cid in (("111111111111", a), ("222222222222", b), ("333333333333", m)):
        c.execute("INSERT INTO achats_ebay (item_id, n, titre, cout, date, carte_id) VALUES (?,?,?,?,?,?)", (iid, 0, "x", 39.0, "2026-11-01", cid))
    c.commit()
    assert lockerroom.Api._photo_achat_vers_carte(c) == 0, "pas de photo connue : rien ne bouge"
    c.execute("UPDATE achats_ebay SET photo='https://i.ebayimg.com/neuve.jpg'"); c.commit()
    assert lockerroom.Api._photo_achat_vers_carte(c, "111111111111") == 1; c.commit()
    assert lockerroom.Api._photo_achat_vers_carte(c) == 0; c.commit()
    ph = {r[0]: r[1] for r in c.execute("SELECT id, photo FROM cartes")}
    assert ph[a] == "https://i.ebayimg.com/neuve.jpg" and ph[b] == "https://i.ebayimg.com/deja.jpg" and not ph[m], ph
    c.execute("UPDATE achats_ebay SET photo='-' WHERE item_id='111111111111'"); c.execute("UPDATE cartes SET photo='' WHERE id=?", (a,)); c.commit()
    assert lockerroom.Api._photo_achat_vers_carte(c) == 0, "« - » (eBay n'a pas de photo) n'est jamais copie"
finally:
    c.close()
import inspect
assert "photo_item(item_id)" in inspect.getsource(lockerroom.Api.achat_vers_inventaire)
print("OK test_photo_achat_carte")
