"""18 nov 2026 (Mathieu : « la cote de la Pro s'auto-regule avec les comps, sans que le client voie le background ») :
l'audit Pro baisse d'un cran un joueur dont les annonces Pro sont souvent a 3x leurs comps, et le lui rend ensuite ;
jamais un joueur de l'expert ; une sorte devient une question ; rien n'est montre au client (seulement la lettre)."""
import os, sys, tempfile, json, time
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comptes
comptes.DONNEES = os.environ["LOCKERROOM_DONNEES"]
import audit_pro as ap
import bareme_iq as bq
import slabiq_expert as e
D = os.environ["LOCKERROOM_DONNEES"]
os.makedirs(os.path.join(D, "radar_garde"), exist_ok=True)
J = "Joueur Mince"                                   # inconnu de l'expert
ann = [{"item_id": f"a{i}", "titre": f"2024-25 Upper Deck Young Guns {J} #{200 + i}", "total": 30.0, "score": 80, "joueur": J} for i in range(6)]
ann += [{"item_id": "e1", "titre": "2024-25 Upper Deck Young Guns Connor McDavid", "total": 900.0, "score": 95, "joueur": "Connor McDavid"} for _ in range(1)]
ann += [{"item_id": f"x{i}", "titre": f"2024-25 Upper Deck Young Guns {J} #{300 + i}", "total": 30.0, "score": 80, "joueur": J, "encan": True} for i in range(3)]
json.dump({"le": time.time(), "r": {"ok": True, "pour_toi": [{"joueur": J, "annonces": ann}]}}, open(os.path.join(D, "radar_garde", "c1.json"), "w"))
assert len(ap.annonces_pro(D)) == 10                 # prix fixe et encans
comps = lambda t: {"mediane": 3.0, "nb": 8}           # la meme carte se vend 3 $
d = e.lire(); d["cotes_auto"] = {J: "B"}; e.ecrire(d); bq._AUTO["t"] = 0.0     # sa cote marche : B
avant = bq.note_joueur(J)[1]
assert avant == "B"
r = ap.iterer(D, comps, digne=lambda x: True)
assert r["verifiees"] == 7 and r["surpayees"] == 7 and r["corrigees"] == 1
apres = bq.note_joueur(J)[1]
assert apres == "B-", (avant, apres)                                      # un cran, pas plus
assert bq.note_joueur("Connor McDavid")[1:] == ("A+", "expert")          # l'expert : jamais touche
# la semaine suivante, ses annonces redeviennent normales : il reprend sa cote
d = e.lire(); d["cotes_auto"] = {J: "B"}; e.ecrire(d); bq._AUTO["t"] = 0.0     # (la validation de la semaine la remet)
r2 = ap.iterer(D, lambda t: {"mediane": 28.0, "nb": 8}, digne=lambda x: True)
assert r2["retours"] and bq.note_joueur(J)[1] == avant
# une sorte souvent surpayee : une question pour l'expert (pas un changement seul)
d = e.lire(); d["questions_marche"] = []; e.ecrire(d)
rap = ap.auditer([{"titre": f"2024-25 Upper Deck Canvas Joueur{i} Nom{i}", "total": 40.0} for i in range(12)], lambda t: {"mediane": 4.0, "nb": 5})
cotes, b, rt, Q = ap.decider(rap, e.lire())
assert all(q["type"] == "sorte" and q.get("audit") for q in Q)
assert not os.path.exists(os.path.join(D, "ne_pas_creer"))
# 18 nov 2026 (2e version) : le prix FINAL des encans montres en Pro, contre les comps de la meme carte
import datetime as dt
fini = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).isoformat()
K = "Joueur Encan"
d = e.lire(); d["cotes_auto"] = {K: "B"}; d["cotes_audit"] = {}; e.ecrire(d); bq._AUTO["t"] = bq._AUDIT["t"] = 0.0
enc = [{"item_id": f"v1|1234567890{i}|0", "titre": f"2024-25 Upper Deck Young Guns {K} #2{i}", "total": 20.0, "encan": True, "fin": fini, "joueur": K}
       for i in range(5)]
def comps_enc(prix_final):
    def f(t):
        i = t.split("#2")[-1]
        v = [{"titre": t, "prix": p, "url": f"https://www.ebay.com/itm/9{j}{i}0000000"} for j, p in enumerate((40.0, 42.0, 38.0))]
        v.append({"titre": t, "prix": prix_final, "url": f"https://www.ebay.com/itm/1234567890{i}"})
        return {"mediane": 40.0, "nb": 4, "ventes": v}
    return f
rap = ap.auditer(enc, comps_enc(15.0))                 # finis a 15 $ pour des comps a 40 $ : moins de la moitie
assert rap["encans_finis"] == 5 and rap["encans"][K] == [5, 5, 0], rap["encans"]
cotes, ch, rt, Q = ap.decider(rap, e.lire())
assert cotes.get(K) == "B-" and ch, (cotes, ch)        # un cran de moins
rap = ap.auditer(enc, comps_enc(70.0))                 # finis a 70 $ : 1,75x les comps
cotes, ch, rt, Q = ap.decider(rap, dict(e.lire(), cotes_audit={}))
assert cotes.get(K) == "B+", cotes                     # un cran de plus (les deux sens)
# signaux contraires : une question dans « SlabIQ demande », pas un changement seul
rap = ap.auditer(enc, comps_enc(70.0))
rap["joueurs"][K] = [5, 5]                             # et ses annonces a prix fixe surpayees
cotes, ch, rt, Q = ap.decider(rap, dict(e.lire(), cotes_audit={}))
assert K not in cotes and any(q["nom"] == K and q["type"] == "joueur" for q in Q)
# un encan pas encore fini ne compte pas
assert ap.auditer([dict(enc[0], fin=(dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).isoformat())], comps_enc(15.0))["encans_finis"] == 0
# la reponse de l'expert s'applique tout de suite, meme a un joueur de la liste de depart (Crosby)
e.coter("Sidney Crosby", "B+"); bq._APPRIS["t"] = 0.0
assert bq.note_joueur("Sidney Crosby")[1:] == ("B+", "expert")
print("AUDIT PRO OK")
