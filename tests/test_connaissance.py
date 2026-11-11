"""11 nov 2026 : le savoir du guide des annees 90 dans SlabIQ (plancher, jamais baisse)."""
import os, sys, tempfile
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import connaissance, score_slab
R = connaissance.reconnaitre
assert R("1997-98 Skybox Metal Universe Michael Jordan Precious Metal Gems PMG Red /90")["niveau"] == "graal"
assert R("1993 SP Derek Jeter #279 Foil RC PSA 8")["niveau"] == "graal"
assert R("1990-91 Score Martin Brodeur #439 RC Draft Pick")["niveau"] == "cle"
assert R("1996-97 Topps Chrome Kobe Bryant #138 RC")["niveau"] == "chasse"
assert R("1996-97 Topps Chrome Kobe Bryant #138 Refractor RC BGS 9")["niveau"] == "graal"
assert R("1996-97 Upper Deck Game Jersey Mario Lemieux GJ6")["niveau"] == "chasse"
assert R("1998 Playoff Contenders Peyton Manning Rookie Ticket Auto")["niveau"] == "graal"
assert R("2023-24 Upper Deck Young Guns Connor Bedard #201") is None
assert score_slab.plancher(40, R("1993 SP Derek Jeter #279")) == 88
assert score_slab.plancher(95, R("1990-91 Score Martin Brodeur #439")) == 95          # jamais baisse
assert score_slab.plancher(None, R("1993 SP Derek Jeter #279")) is None
s = score_slab.score("1997-98 Metal Universe Michael Jordan Precious Metal Gems /100")
assert (s["score"] is None or s["score"] >= 88) and s["connaissance"]["niveau"] == "graal", s
print("CONNAISSANCE OK")
