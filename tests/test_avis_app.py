"""20 nov 2026 - les notes App Store sur le site : vraies seulement, cachees tant qu'il n'y en a pas assez."""
import os, sys, tempfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ICI)
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
os.environ["LOCKERROOM_TACHES"] = "0"
import avis_app as A

def ent(i, note, texte, titre="Super", auteur="Coll"):
    return {"author": {"name": {"label": auteur}, "uri": {"label": "x"}}, "im:rating": {"label": str(note)}, "id": {"label": str(i)},
            "title": {"label": titre}, "content": {"label": texte, "attributes": {"type": "text"}}, "im:version": {"label": "1.0"},
            "updated": {"label": "2026-12-0%dT10:00:00-07:00" % (i % 9 + 1)}}

flux = {"feed": {"entry": [{"im:name": {"label": "SlabCoach"}}] + [ent(1, 5, "Le Radar m'a trouve une Young Guns a moitie prix, malade."),
        ent(2, 2, "Bof, trop de choses a apprendre au debut de l'app."), ent(3, 4, "Court"),
        ent(4, 4, "<script>alert(1)</script> tres bonne app pour suivre ma collection"), ent(5, 5, "Enfin une app faite pour les collectionneurs d'ici.")]}}
l = A.lire_flux(flux, "ca")
assert len(l) == 5 and l[0]["note"] == 5 and l[0]["auteur"] == "Coll"
d = {"maj": 0, "notes": {"moyenne": 4.6, "nb": 42}, "avis": l}
b = A.bons_avis(d)
assert [a["id"] for a in b] == ["5", "4", "1"], b          # 4-5 etoiles avec un vrai texte, les plus recents d'abord
s = A.html_section(d)
assert "<script>" not in s and "&lt;script&gt;" in s and s.count('class="av-c"') == 6 and 'aria-hidden="true"' in s
assert "4,6" in s and "42 notes" in s
assert A.html_section({"avis": l[:2], "notes": {}}) == ""   # moins de 3 bons commentaires : rien
lg = A.html_bandeau(d, comptes=1234)
assert "4,6" in lg and "42 notes sur l’App Store" in lg and "1 200+" in lg and "1,200+" in lg
assert A.html_bandeau({"notes": {"moyenne": 5.0, "nb": 2}}, comptes=10) == ""   # trop peu : on ne montre rien
assert A.lire_lookup({"resultCount": 1, "results": [{"averageUserRating": 4.71, "userRatingCount": 9}]}) == {"moyenne": 4.71, "nb": 9}
assert A.lire_lookup({"resultCount": 0, "results": []})["nb"] == 0
# la page : rien d'affiche ni de {{...}} oublie quand il n'y a pas encore de notes
p = A.injecter("<head></head>{{AVIS_LIGNE}}|{{AVIS_SECTION}}", "{{AVIS_LIGNE}}")
assert p == "<head></head>|", p
print("OK test_avis_app")
