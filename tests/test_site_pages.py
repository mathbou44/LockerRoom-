"""16 nov 2026 : le site (accueil, tarifs, qui nous sommes) s'affiche en francais et en anglais, sans gabarit oublie,
et l'app iPhone ne voit jamais la page des prix du site (regles d'Apple)."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("LOCKERROOM_DONNEES", tempfile.mkdtemp())
os.environ["LR_CALME_DEMARRAGE_S"] = "99999"
os.environ["LR_RECHAUFFER_S"] = "99999"
import server  # noqa: E402

for page in ("accueil", "tarifs", "apropos"):
    for l in ("fr", "en"):
        with server.app.test_request_context(f"/?lang={l}"):
            h = server._page_vitrine(page).get_data(as_text=True)
        assert "{{" not in h, (page, l, re.findall(r"\{\{\w+\}\}", h))
        assert f'<html lang="{l}">' in h
        assert h.count('<span class="fr">') == h.count('<span class="en">'), (page, h.count('<span class="fr">'), h.count('<span class="en">'))
        assert 'class="lien actif' in h if page != "accueil" else True
c = server.app.test_client()
for chemin in ("/tarifs", "/pricing", "/a-propos", "/about"):
    r = c.get(chemin)
    assert r.status_code == 200 and b"SlabCoach" in r.data, chemin
    r = c.get(chemin, headers={"User-Agent": "Mozilla/5.0 LockerRoomiOS"})
    assert r.status_code == 302, chemin
print("SITE OK")
