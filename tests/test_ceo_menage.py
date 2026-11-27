"""23 nov 2026 au soir (Mathieu : « 86 taches c'est bcp trop, fais-en toi-meme et regarde si toutes a jour ou importantes ») :
le menage de la liste admin. Ce qui est fait, decide ou depasse se ferme avec sa raison ; les petites taches d'un meme sujet
deviennent une seule tache dont la note garde chaque point. Rien ne disparait sans trace."""
import os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LOCKERROOM_DONNEES"] = tempfile.mkdtemp()
import ceo
c = ceo._semer({"semis": [], "taches": []})
T = {t["id"]: t for t in c["taches"]}
ouv = [t for t in c["taches"] if t["etat"] != "fait"]
claude = [t for t in ouv if re.match(r"\s*claude\b", t["titre"], re.I)]
# 1. la liste tient sur un ecran : 87 ouvertes avant, 25 apres (18 a lui, 7 a Claude)
assert len(ouv) <= 26 and len(ouv) - len(claude) <= 18 and len(claude) <= 8, (len(ouv), len(claude))
# 2. Apple reste en tete, tel quel, avec ses dates
assert [T[i]["etat"] for i in ("ap_accord", "ap_build", "ap_soumettre")] == ["a_faire", "fait", "fait"]      # 26 nov : le build est lance, l'envoi redecoupe (apple_26nov)
ids_ = [t["id"] for t in ceo.taches(c)]
assert ids_[0] == "ap_accord" and {"ap2_testflight", "ap2_small", "ap2_soumettre"} <= set(ids_[:9]), ids_[:9]      # 26 nov : Apple reste en haut, par date
# 3. chaque tache fermee par le menage a sa raison, et celle qui la remplace existe et est ouverte
M = ceo.CLOS["clos_menage_23nov"]
titres_ouverts = " | ".join(t["titre"] for t in ouv)
for tid, raison in M.items():
    assert tid in T and T[tid]["etat"] == "fait" and raison in T[tid]["note"], tid
    m = re.match(r"Regroupée le 23 nov dans « (.+?) »", raison)
    if m:
        assert m.group(1) in titres_ouverts, (tid, m.group(1))
# 4. une tache regroupee garde chaque point dans sa note
N = lambda i: T[i]["note"]
assert all(x in N("g_stripe") for x in ("vérification d'identité", "prix annuel", "paiement"))
assert all(x in N("g_cell") for x in ("nouveau compte", "lot de 4 cartes", "Radar Pro", "Consignation", "recadrage", "défi", "Program of Excellence"))
assert all(x in N("g_cloudflare") for x in ("proxied", "Pare-feu", "Verrouiller Render", "DMARC", "Bot Fight Mode"))
assert all(x in N("g_comptes") for x in ("2FA", "GitHub", "2e vérification"))
assert all(x in N("g_papiers") for x in ("Loi 25", "plan", "Alertes"))
assert all(x in N("g_decisions") for x in ("séries", "Gratuit", "offre du jour", "mot de fondateur", "5 dates", "web le 1er décembre", "PC est fermé", "baseball", "YG Renewed",
                                           "non-cartes", "vitrine", "courbe du hobby", "App Store Connect"))
assert all(x in N("g_plan6") for x in ("Whiteboard", "18 janvier", "15 février", "Mai", "créateurs"))
# 5. ce que Mathieu a deja coche ou rouvert n'est jamais retouche (une seule passe)
T["g_cell"]["etat"] = "fait"; T["sr_2fa"]["etat"] = "a_faire"
n = len(c["taches"]); c = ceo._semer(c); T2 = {t["id"]: t for t in c["taches"]}
assert len(c["taches"]) == n and T2["g_cell"]["etat"] == "fait" and T2["sr_2fa"]["etat"] == "a_faire"
# 6. sur SA liste d'avant (deja semee, des taches cochees a la main) : le menage passe une fois, sans rien doubler
avant = ceo._semer({"semis": ["menage_23nov", "clos_menage_23nov", "auto_23nov", "clos_auto_23nov", "apple_26nov", "clos_apple_26nov"], "taches": []})          # sa liste, telle qu'elle etait a 20 h
assert not any(t["id"].startswith("g_") for t in avant["taches"]) and sum(t["etat"] != "fait" for t in avant["taches"]) == 87
avant["semis"] = [x for x in avant["semis"] if "menage" not in x]
next(t for t in avant["taches"] if t["id"] == "sr_github")["etat"] = "fait"           # il l'avait deja fait
apres = ceo._semer(avant)
A = {t["id"]: t for t in apres["taches"]}
assert len(A) == len(apres["taches"]) and A["g_comptes"]["etat"] == "a_faire" and A["sr_2fa"]["etat"] == "fait" and "Regroupée" in A["sr_2fa"]["note"]
assert "Regroupée" not in (A["sr_github"]["note"] or ""), "une tache deja faite garde sa note"
print("OK test_ceo_menage (%d ouvertes : %d a lui, %d a Claude)" % (len(ouv), len(ouv) - len(claude), len(claude)))
# 7. 23 nov, 21 h 55 (Mathieu : « je veux pas cliquer, tout doit se faire auto ») : sa tache de telechargement se ferme avec sa
#    raison, l'automatisation du test du site devient une tache de Claude ; la liste ne grossit pas
assert T["r_donnees"]["etat"] == "fait" and "rien à télécharger" in T["r_donnees"]["note"]
assert T["g_c_auto"]["etat"] == "a_faire" and re.match(r"Claude\b", T["g_c_auto"]["titre"]) and "Garde-fou" in T["g_c_auto"]["note"]
