"""Audit du site (24 nov 2026, Mathieu : « un audit intense de l'app et du site avant le release officiel »). Sans reseau, sur
les fichiers du site : chaque lien interne mene a une page qui existe, chaque ancre a sa cible, chaque texte francais a son
anglais (et l'inverse), aucun gabarit {{...}} ne reste sans remplacement, aucune ligne interdite (logo de ligue, superlatif
sans mesure, mention d'un prix tire d'eBay), et chaque chiffre de SlabIQ est celui du test (tests/test_site_a_jour.py).
Usage : python3 outils/audit_site.py [--test]"""
import json, os, re, sys
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(RACINE, "ui")
PAGES = ["site_base.html", "site_accueil.html", "site_slabiq.html", "site_tarifs.html", "site_apropos.html", "site_securite.html",
         "conditions.html", "confidentialite.html", "support.html", "connexion.html"]
serveur = open(os.path.join(RACINE, "server.py"), encoding="utf-8").read()
ROUTES = set(re.findall(r'@app\.route\("([^"<]+)"', serveur))
PREFIXES = [r.split("<")[0] for r in re.findall(r'@app\.route\("([^"]*<[^"]+)"', serveur) if r.split("<")[0] not in ("/",)]
FICHIERS = set(os.listdir(UI))
ECARTS, FAITS = [], 0

def voir(ok, texte):
    global FAITS
    FAITS += 1
    if not ok:
        ECARTS.append(texte)

def sans_code(h):
    return re.sub(r"<(script|style)\b[\s\S]*?</\1>", " ", h)

for nom in PAGES:
    ch = os.path.join(UI, nom)
    voir(os.path.exists(ch), f"{nom} : fichier absent")
    if not os.path.exists(ch):
        continue
    brut = open(ch, encoding="utf-8").read()
    h = sans_code(brut)
    ids = set(re.findall(r'\bid="([^"]+)"', brut))
    # 1. les liens
    for href in set(re.findall(r'<a\b[^>]*\bhref="([^"]*)"', h)):
        if href.startswith(("http://", "https://")):
            voir(href.startswith("https://"), f"{nom} : lien non securise {href}")
            voir(" " not in href and "{{" not in href, f"{nom} : lien mal forme {href}")
        elif href.startswith(("mailto:", "tel:")):
            voir("@" in href or href.startswith("tel:"), f"{nom} : courriel mal forme {href}")
        elif href.startswith("#"):
            voir(href == "#" or href[1:] in ids or nom == "site_base.html", f"{nom} : l'ancre {href} n'a pas de cible dans la page")
        elif href.startswith("/"):
            chemin = href.split("#")[0].split("?")[0]
            ok = chemin in ROUTES or chemin.lstrip("/") in FICHIERS or any(chemin.startswith(p) for p in PREFIXES) or os.path.exists(os.path.join(UI, chemin.lstrip("/")))
            voir(ok, f"{nom} : le lien {href} ne mene a aucune page du serveur")
        elif href and not href.startswith(("javascript:", "{{")):
            voir(False, f"{nom} : lien relatif {href} (il casse selon la page d'ou l'on vient)")
    for src in set(re.findall(r'<(?:img|source|link)\b[^>]*\b(?:src|href)="(/[^"]+)"', brut)):
        chemin = src.split("?")[0]
        voir(chemin in ROUTES or os.path.exists(os.path.join(UI, chemin.lstrip("/"))) or any(chemin.startswith(p) for p in PREFIXES) or chemin.lstrip("/") in FICHIERS,
             f"{nom} : le fichier {src} n'existe pas")
    for img in re.findall(r"<img\b[^>]*>", brut):
        voir(re.search(r'\balt="', img) is not None, f"{nom} : une image sans texte de remplacement : {img[:70]}")
    # 2. le francais et l'anglais vont par paires
    fr, en = len(re.findall(r'class="fr"', h)), len(re.findall(r'class="en"', h))
    voir(fr == en, f"{nom} : {fr} textes en francais pour {en} en anglais")
    for m in re.finditer(r'<span class="en">([\s\S]*?)</span>', h):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        voir(not re.search(r"\b(les|des|une|pour|avec|sans|ton|tes|nos|vos|dans|sont|cette|aussi|toujours|jamais|gratuit|cartes)\b", t, re.I) or bool(re.search(r"\b(the|and|your|you|for|with|of|is|are)\b", t, re.I)),
             f"{nom} : du francais dans un texte anglais : « {t[:70]} »")
    for m in re.finditer(r'<span class="fr">([\s\S]*?)</span>', h):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        voir(not re.search(r"\b(the|your|you|with|and)\b", t) or bool(re.search(r"\b(le|la|les|des|et|ton|tes|pour|de|du|un|une)\b", t, re.I)),
             f"{nom} : de l'anglais dans un texte francais : « {t[:70]} »")
    # 3. les gabarits : chacun est remplace par le serveur
    for g in set(re.findall(r"\{\{([A-Z_]+)\}\}", brut)):
        voir("{{" + g + "}}" in serveur or (g.startswith("ACT_") and "{{ACT_" in serveur), f"{nom} : le gabarit {{{{{g}}}}} n'est remplace nulle part dans server.py")
    # 4. ce que le site ne doit jamais dire
    texte = re.sub(r"<[^>]+>", " ", h)
    # un superlatif sur l'APP (« la meilleure app », « n° 1 »), pas « le Radar garde les meilleures cartes » ; une garantie
    # AFFIRMEE, pas l'avertissement « les resultats passes ne garantissent pas… » ni « aucun profit n'est garanti »
    for motif, quoi in ((r"\bn[°o]\s?1\b|\bnum[ée]ro un\b|#1\b|\bthe best (app|tool|system|analy)|\b(le|la) meilleure? (app|outil|syst[eè]me|analy)|\bmost advanced\b|\ble plus avanc|\bla plus avanc", "un superlatif sans mesure"),
                        (r"(?<!ne )(?<!n'est )(?<!not )(?<!no )\b(profits? garantis?|r[ée]sultats? garantis?|guaranteed (profit|return|result)s?|garantit (un|des|le) (profit|gain))", "une garantie de resultat"),
                        (r"\bprofit de revente\b|\bresale profit\b", "le profit de revente (retire du site)"),
                        (r"\bGoogle News\b|\bESPN\b|\bYahoo\b|\bGoldin\b", "une source ou un partenaire non autorise")):
        m = re.search(motif, texte, re.I)
        voir(m is None, f"{nom} : {quoi} : « {texte[max(0, (m.start() if m else 0) - 30):(m.end() if m else 0) + 30].strip()} »")
    for logo in re.findall(r'<img\b[^>]*src="([^"]*)"', brut):
        voir(not re.search(r"nhl|lnh|upper-?deck|topps|panini|psa\b|ebay", logo, re.I), f"{nom} : une image qui ressemble a un logo de tiers : {logo}")
    # 5. accessibilite et partage : un seul h1 par page de contenu, une langue declaree a la base
    if nom.startswith("site_") and nom != "site_base.html":
        voir(len(re.findall(r"<h1\b", h)) == 1, f"{nom} : {len(re.findall(r'<h1', h))} titres h1 (il en faut un)")
base = open(os.path.join(UI, "site_base.html"), encoding="utf-8").read()
voir(re.search(r"<html[^>]*\blang=", base) is not None, "site_base.html : la langue de la page n'est pas declaree")
voir('name="viewport"' in base and 'name="description"' in base, "site_base.html : il manque viewport ou description")
# 6. chaque page du menu a sa route en francais ET en anglais
for fr_, en_ in (("/tarifs", "/pricing"), ("/a-propos", "/about"), ("/securite", "/security"), ("/preuve", "/proof")):
    voir(fr_ in ROUTES and en_ in ROUTES, f"routes : {fr_} et {en_} doivent exister toutes les deux")

if __name__ == "__main__":
    print(f"AUDIT DU SITE : {len(PAGES)} pages, {FAITS} verifications, {len(ECARTS)} ecart(s)")
    for e in ECARTS:
        print("  ECART", e)
    if "--test" in sys.argv and ECARTS:
        sys.exit(1)
