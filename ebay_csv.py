"""
LOCKERROOM - fichiers eBay sans API (repris de Hall of Cardz) :

  - lire_annonces() : rapport Seller Hub > Reports > « All active listings ».
  - lire_ventes()   : rapport Seller Hub > Reports > « Orders ».
  - fichier_brouillons() : fichier d'import « Draft » (Seller Hub > Reports >
    Upload) pour la categorie Trading Card Singles (261328), avec les
    « item specifics » deja remplis. Le vendeur complete et publie ses
    brouillons dans eBay : rien n'est publie par l'app.
"""
import csv
import io
import re

CATEGORY_ID = 261328
CONDITION_GRADEE = 2750
CONDITION_NON_GRADEE = 4000
# 30 oct 2026 (« Grade (27502) is a required field » pour une PSA 6) : tables completes d'eBay, categorie 261328
# (developer.ebay.com, « Condition Descriptor IDs for Trading Cards »). Avant, les notes s'arretaient a 7.
GRADEURS = {
    "PSA": "Professional Sports Authenticator (PSA) - (ID: 275010)",
    "BCCG": "Beckett Collectors Club Grading (BCCG) - (ID: 275011)",
    "BVG": "Beckett Vintage Grading (BVG) - (ID: 275012)",
    "BGS": "Beckett Grading Services (BGS) - (ID: 275013)",
    "CSG": "Certified Sports Guaranty (CSG) - (ID: 275014)",
    "CGC": "Certified Guaranty Company (CGC) - (ID: 275015)",
    "SGC": "Sportscard Guaranty Corporation (SGC) - (ID: 275016)",
    "KSA": "K Sportscard Authentication (KSA) - (ID: 275017)",
    "GMA": "Gem Mint Authentication (GMA) - (ID: 275018)",
    "HGA": "Hybrid Grading Approach (HGA) - (ID: 275019)",
    "ISA": "International Sports Authentication (ISA) - (ID: 2750110)",
    "GSG": "Gold Standard Grading (GSG) - (ID: 2750112)",
    "PGS": "Platin Grading Service (PGS) - (ID: 2750113)",
    "MNT": "MNT Grading (MNT) - (ID: 2750114)",
    "TAG": "Technical Authentication & Grading (TAG) - (ID: 2750115)",
    "RARE": "Rare Edition (Rare) - (ID: 2750116)",
    "RCG": "Revolution Card Grading (RCG) - (ID: 2750117)",
    "CGA": "Card Grading Australia (CGA) - (ID: 2750120)",
}
GRADEUR_AUTRE = "Other - (ID: 2750123)"
BECKETT = "BGS"                                            # « Beckett 9.5 » = BGS
_NOTES_ID = {"10": 275020, "9.5": 275021, "9": 275022, "8.5": 275023, "8": 275024, "7.5": 275025, "7": 275026,
             "6.5": 275027, "6": 275028, "5.5": 275029, "5": 2750210, "4.5": 2750211, "4": 2750212, "3.5": 2750213,
             "3": 2750214, "2.5": 2750215, "2": 2750216, "1.5": 2750217, "1": 2750218, "Authentic": 2750219}
NOTES = {k: f"{k} - (ID: {v})" for k, v in _NOTES_ID.items()}
_RE_GRADE = re.compile(r"\b([A-Za-z]{2,7})(?![A-Za-z])\s*(?:GEM\s*(?:MINT|MT)\s*|MINT\s*|NM-?MT\s*\+?\s*)?"
                       r"(10|[1-9](?:\.[05])?|AUTH(?:ENTIC)?)\b", re.I)


def lire_grade(g):
    """« PSA 6 », « psa6 », « BGS 9.5 », « Beckett 9.5 », « PSA 6.0 », « PSA Authentic » -> ("PSA", "6") ; sinon None.
    Le graduateur inconnu -> « AUTRE » (eBay accepte « Other »)."""
    m = _RE_GRADE.search(str(g or ""))
    if not m:
        return None
    qui = m.group(1).upper()
    if qui in ("RAW", "UNGRADED"):
        return None
    if qui == "BECKETT":
        qui = BECKETT
    n = m.group(2).upper()
    if n.startswith("A"):
        n = "Authentic"
    else:
        n = ("%g" % float(n))
    if n not in _NOTES_ID:
        return None
    return (qui if qui in GRADEURS else "AUTRE"), n


def id_gradeur(qui):
    return re.search(r"ID: (\d+)", GRADEURS.get(qui) or GRADEUR_AUTRE).group(1)


def id_note(n):
    return str(_NOTES_ID[n]) if n in _NOTES_ID else None


ETAT_NM = "Near Mint or Better - (ID: 400010)"
COLONNES_DRAFT = [
    "Action(SiteID=Canada|Country=CA|Currency=CAD|Version=1193|CC=UTF-8)",
    "Custom label (SKU)", "Category ID", "Title", "UPC", "Price", "Quantity",
    "Item photo URL", "Condition ID", "Description", "Format",
    "CD:Professional Grader - (ID: 27501)", "CD:Grade - (ID: 27502)",
    "CDA:Certification Number - (ID: 27503)", "CD:Card Condition - (ID: 40001)",
    "C:Sport", "C:Player/Athlete", "C:Manufacturer", "C:Season",
    "C:Parallel/Variety", "C:Set", "C:Team", "C:League", "C:Autographed",
    "C:Card Number", "C:Type", "C:Country of Origin",
]


def _num(texte):
    if texte in (None, ""):
        return None
    t = re.sub(r"[^\d.,-]", "", str(texte)).replace(",", ".")
    if t.count(".") > 1:
        t = t.replace(".", "", t.count(".") - 1)
    try:
        return float(t)
    except ValueError:
        return None


def _lignes(contenu, marqueur):
    """Texte CSV -> DictReader qui commence a la ligne d'en-tete contenant `marqueur`."""
    if isinstance(contenu, bytes):
        contenu = contenu.decode("utf-8-sig", errors="replace")
    lignes = contenu.splitlines(keepends=True)
    i = next((k for k, l in enumerate(lignes) if marqueur.lower() in l.lower()), None)
    if i is None:
        return None
    return csv.DictReader(io.StringIO("".join(lignes[i:])))


def _v(row, *noms):
    bas = {str(k).strip().lower(): v for k, v in row.items() if k}
    for n in noms:
        v = bas.get(n.lower())
        if v not in (None, ""):
            return str(v).strip()
    return ""


_MOIS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def date_iso(texte):
    """« Oct-15-26 », « Oct-15-26 21:00:01 PDT », « Oct 15, 2026 », « 2026-10-15 » -> « 2026-10-15 »."""
    t = str(texte or "").strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"([A-Za-z]{3})[a-z]*[-\s.]+(\d{1,2}),?[-\s]+(\d{2,4})", t)
    if m and m.group(1).lower() in _MOIS:
        an = int(m.group(3))
        an = an + 2000 if an < 100 else an
        return f"{an}-{_MOIS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)          # 10/15/2026 (mois/jour, format US)
    if m:
        an = int(m.group(3))
        an = an + 2000 if an < 100 else an
        return f"{an}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return ""


def lire_annonces(contenu):
    r = _lignes(contenu, "Item number")
    if r is None:
        raise ValueError("Ce n'est pas un rapport d'annonces eBay (colonne « Item number » absente).")
    out = []
    for row in r:
        item = _v(row, "Item number")
        variation = _v(row, "Variation details")
        if not item or ";" in variation:
            continue
        out.append({"item_number": item, "titre": _v(row, "Title"), "sku": _v(row, "Custom label (SKU)"),
                    "prix": _num(_v(row, "Current price", "Start price")), "variation": variation,
                    "debut": date_iso(_v(row, "Start date")) or None,
                    "watchers": int(_num(_v(row, "Watchers")) or 0) if _v(row, "Watchers") else None})
    return out


def lire_ventes(contenu):
    r = _lignes(contenu, "Transaction ID")
    if r is None:
        raise ValueError("Ce n'est pas un rapport de ventes eBay (colonne « Transaction ID » absente).")
    out = []
    for row in r:
        txn, item = _v(row, "Transaction ID"), _v(row, "Item Number")
        if not txn or not item:
            continue
        out.append({"transaction_id": txn, "item_number": item, "titre": _v(row, "Item Title"),
                    "prix": _num(_v(row, "Sold For")), "port_charge": _num(_v(row, "Shipping And Handling")),
                    "total": _num(_v(row, "Total Price")), "date": date_iso(_v(row, "Sale Date", "Paid On Date")),
                    "acheteur": _v(row, "Buyer Username")})
    return out


def titre_annonce(c):
    """Annee, marque, set, parallele, JOUEUR, tirage, auto, gradation, #numero (80 caracteres)."""
    p = [c.get("annee"), c.get("marque"), c.get("set_nom"), c.get("parallele"), str(c.get("joueur") or "").upper(),
         f"/{c['tirage']}" if c.get("tirage") else None, "Auto" if c.get("auto") else None,
         c.get("grade") if c.get("grade") and str(c.get("grade")).lower() != "raw" else None,
         f"#{c['numero']}" if c.get("numero") else None]
    return re.sub(r"\s+", " ", " ".join(str(x) for x in p if x)).strip()[:80]


def fichier_brouillons(cartes, description=""):
    """Texte CSV pret pour Seller Hub > Reports > Upload (action Draft)."""
    sortie = io.StringIO()
    w = csv.writer(sortie)
    w.writerow(["#INFO", "Version=0.0.2", "Template= eBay-draft-listings-template_ENCA"])
    w.writerow(["#INFO Action and Category ID are required fields."])
    w.writerow(["#INFO After uploading from Seller Hub Reports, complete your drafts here: https://www.ebay.ca/sh/lst/drafts"])
    w.writerow(["#INFO"])
    w.writerow(COLONNES_DRAFT)
    for c in cartes:
        m = lire_grade(c.get("grade"))
        ligne = {k: "" for k in COLONNES_DRAFT}
        ligne[COLONNES_DRAFT[0]] = "Draft"
        ligne["Custom label (SKU)"] = c.get("sku") or f"LR-{c.get('id')}"
        ligne["Category ID"] = CATEGORY_ID
        ligne["Title"] = c.get("titre") or titre_annonce(c)
        ligne["Price"] = c.get("prix_demande") or ""
        ligne["Quantity"] = 1
        ligne["Condition ID"] = CONDITION_GRADEE if m else CONDITION_NON_GRADEE
        ligne["Description"] = description
        ligne["Format"] = "FixedPrice"
        if m:
            ligne["CD:Professional Grader - (ID: 27501)"] = GRADEURS.get(m[0]) or GRADEUR_AUTRE
            ligne["CD:Grade - (ID: 27502)"] = NOTES[m[1]]
            ligne["CDA:Certification Number - (ID: 27503)"] = str(c.get("cert") or "").strip()[:30]
        else:
            ligne["CD:Card Condition - (ID: 40001)"] = ETAT_NM
        import sports                               # 23 oct 2026 - NHL, NFL, NBA, MLB
        asp = sports.aspects_ebay(c.get("sport") or sports.detecter(c.get("titre"), c.get("equipe"), defaut="hockey"))
        ligne["C:Sport"] = asp["Sport"]
        ligne["C:Player/Athlete"] = c.get("joueur") or ""
        ligne["C:Manufacturer"] = c.get("marque") or ""
        ligne["C:Season"] = c.get("annee") or ""
        ligne["C:Parallel/Variety"] = c.get("parallele") or ""
        ligne["C:Set"] = c.get("set_nom") or ""
        ligne["C:Team"] = c.get("equipe") or ""
        ligne["C:League"] = asp["League"]
        ligne["C:Autographed"] = "Yes" if c.get("auto") else "No"
        ligne["C:Card Number"] = c.get("numero") or ""
        ligne["C:Type"] = "Sports Trading Card"
        ligne["C:Country of Origin"] = "United States"
        w.writerow([ligne[k] for k in COLONNES_DRAFT])
    return sortie.getvalue()
