# SlabCoach - 21 nov 2026 (Mathieu : « sur le cell, je suis incapable de creer le fichier Excel ou PDF » pour la consignation)
#
# Dans l'app iPhone, la page ne peut ni telecharger un fichier ni imprimer. Le serveur fabrique donc le fichier (un vrai .xlsx,
# ou la liste a imprimer) et le garde 20 minutes derriere un lien impossible a deviner (32 caracteres au hasard) ; l'app ouvre
# ce lien dans Safari, ou iOS sait l'enregistrer, le partager et l'imprimer. Rien n'est ecrit sur le disque ; au plus 60
# fichiers en memoire, le plus vieux sort.
import html
import io
import secrets
import threading
import time

DUREE_S = 20 * 60
MAXI = 60
_F = {}
_V = threading.Lock()


def garder(nom, type_mime, octets):
    j = secrets.token_hex(16)
    with _V:
        m = time.time()
        for k in [k for k, v in _F.items() if m - v[0] > DUREE_S]:
            _F.pop(k, None)
        while len(_F) >= MAXI:
            _F.pop(min(_F, key=lambda k: _F[k][0]), None)
        _F[j] = (m, str(nom)[:80], type_mime, bytes(octets))
    return j


def lire(jeton):
    with _V:
        v = _F.get(str(jeton or ""))
    if not v or time.time() - v[0] > DUREE_S:
        return None
    return {"nom": v[1], "type": v[2], "octets": v[3]}


def _t(l, n=160):
    return " ".join(str(l or "").split())[:n]


def _sur(v):
    """Du texte seulement : une valeur qui commence par = + - @ ne devient jamais une formule (une case vide reste vide)."""
    v = str(v or "")
    return "'" + v if v[:1] and v[:1] in "=+-@" else v


def _lignes(lignes):
    out = []
    for i, x in enumerate([x for x in (lignes or []) if isinstance(x, dict)][:500]):
        ph = str(x.get("photo") or "")
        out.append({"no": i + 1, **{k: _t(x.get(k)) for k in ("joueur", "annee", "marque", "set", "numero", "parallele", "tirage", "grade", "extras")},
                    "titre": _t(x.get("titre"), 240), "photo": ph if ph.startswith("https://") and len(ph) < 600 else ""})
    return out


def consig_xlsx(lignes, maison, jour, en=False):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
    L = _lignes(lignes)
    T = (["No.", "Player", "Season", "Brand", "Set", "Card #", "Parallel", "Serial", "Grade", "RC / Auto / Patch", "Full title", "Minimum price (optional)"] if en
         else ["N°", "Joueur", "Saison", "Marque", "Set", "N° de carte", "Parallèle", "Numérotée", "Gradation", "RC / Auto / Patch", "Titre complet", "Prix minimum (optionnel)"])
    wb = Workbook()
    ws = wb.active
    ws.title = "Consignment" if en else "Consignation"
    ws.append([f"{'Consignment' if en else 'Consignation'} · {_t(maison, 60)} · {jour} · {len(L)} {'cards' if en else 'cartes'}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(T)
    for c in ws[2]:
        c.font = Font(bold=True)
    for x in L:      # (du texte seulement : une valeur qui commence par = + - @ ne devient jamais une formule)
        ws.append([x["no"]] + [_sur(v) for v in (x["joueur"], x["annee"], x["marque"], x["set"], x["numero"], x["parallele"],
                                                 x["tirage"], x["grade"], x["extras"], x["titre"])] + [""])
    for i, w in enumerate((5, 24, 10, 16, 26, 11, 20, 11, 12, 16, 60, 22), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def consig_html(lignes, maison, jour, photos=True, en=False):
    L, e = _lignes(lignes), html.escape
    t = (lambda fr, an: an if en else fr)
    rangs = "".join(
        f'<tr><td class="n">{x["no"]}</td>' + (f'<td class="ph">{("<img src=" + chr(34) + e(x["photo"], True) + chr(34) + " alt=" + chr(34) + chr(34) + ">") if x["photo"] else ""}</td>' if photos else "")
        + f'<td><b>{e(x["joueur"] or x["titre"])}</b><br><span>{e(" · ".join(v for v in (x["annee"], x["set"] or x["marque"], x["numero"], x["parallele"], x["tirage"], x["extras"]) if v))}</span>'
        + (f'<br><small>{e(x["titre"])}</small>' if x["joueur"] and x["titre"] else "") + f'</td><td>{e(x["grade"])}</td><td class="px"></td></tr>' for x in L)
    return ("<!doctype html><html lang=\"" + t("fr", "en") + "\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{e(t('Consignation', 'Consignment'))} {e(_t(maison, 60))}</title><style>"
            "body{font:12px -apple-system,Helvetica,Arial,sans-serif;margin:24px;color:#111;background:#fff} h1{font-size:18px;margin:0 0 2px} p{margin:0 0 14px;color:#555}"
            ".aide{padding:10px 12px;border-radius:10px;background:#eef;color:#224;font-size:13px} @media print{.aide{display:none}}"
            "table{border-collapse:collapse;width:100%} th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#666;border-bottom:2px solid #111;padding:6px}"
            "td{padding:6px;border-bottom:1px solid #ddd;vertical-align:middle} td.n{width:22px;color:#888} td.ph{width:46px} td.ph img{width:40px;height:56px;object-fit:contain;border-radius:3px;background:#f2f2f2}"
            "td span{color:#222} td small{color:#777} td.px{width:90px;border-bottom:1px solid #999} .sig{display:flex;gap:28px;margin-top:26px} .sig div{flex:1;border-top:1px solid #111;padding-top:4px;color:#555;font-size:11px}"
            "@page{margin:14mm}</style></head><body>"
            f"<p class=\"aide\">{e(t('Pour imprimer ou enregistrer en PDF : touche Partager, puis Imprimer.', 'To print or save as PDF: tap Share, then Print.'))}</p>"
            f"<h1>{e(t('Consignation', 'Consignment'))}{' · ' + e(_t(maison, 60)) if maison else ''}</h1><p>{e(jour)} · {len(L)} {t('cartes', 'cards')} · {e(t('dans l’ordre du colis', 'in package order'))}</p>"
            f"<table><thead><tr><th></th>{'<th></th>' if photos else ''}<th>{t('Carte', 'Card')}</th><th>{t('Gradation', 'Grade')}</th><th>{t('Prix minimum', 'Minimum')}</th></tr></thead><tbody>{rangs}</tbody></table>"
            f"<div class=\"sig\"><div>{t('Nom', 'Name')}</div><div>{e(t('Courriel / téléphone', 'Email / phone'))}</div><div>{t('Signature', 'Signature')}</div></div></body></html>").encode("utf-8")


def break_xlsx(lignes, produit, mode, resume=None, en=False):
    """21 nov 2026 (Mathieu : « une option d'extraire un fichier Excel avec les prix pour les personnes qui runnent un break ») :
    une ligne par place (equipe, joueur ou division), son prix, ses vedettes, et deux colonnes a remplir (acheteur, paye)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
    L = []
    for x in [x for x in (lignes or []) if isinstance(x, dict)][:800]:
        try:
            prix = round(float(x.get("prix") or 0), 2)
        except (TypeError, ValueError):
            prix = 0
        L.append((_t(x.get("nom"), 80), prix, _t(x.get("vedettes"), 160)))
    quoi = {"equipes": ("Team", "Équipe"), "joueurs": ("Player", "Joueur"), "divisions": ("Division", "Division")}.get(str(mode), ("Spot", "Place"))[0 if en else 1]
    wb = Workbook()
    ws = wb.active
    ws.title = "Break"
    ws.append([f"{_t(produit, 80)} · {len(L)} {'spots' if en else 'places'}" + (f" · {_t(resume, 120)}" if resume else "")])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append(["No.", quoi, "Price" if en else "Prix", "Key players" if en else "Vedettes", "Buyer" if en else "Acheteur", "Paid" if en else "Payé"] if en
              else ["N°", quoi, "Prix", "Vedettes", "Acheteur", "Payé"])
    for c in ws[2]:
        c.font = Font(bold=True)
    for i, (nom, prix, ved) in enumerate(L, 1):      # (du texte seulement : jamais une formule)
        ws.append([i, _sur(nom), prix, _sur(ved), "", ""])
    n = len(L)
    ws.append([])
    ws.append(["", "Total", f"=SUM(C3:C{n + 2})" if n else 0])
    ws.cell(row=n + 4, column=2).font = Font(bold=True)
    ws.cell(row=n + 4, column=3).font = Font(bold=True)
    for r in range(3, n + 5):
        ws.cell(row=r, column=3).number_format = '#,##0 "$"'
    for i, w in enumerate((5, 30, 12, 44, 24, 10), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A3"
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()
