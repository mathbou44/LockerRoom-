"""
SLABCOACH - l'alerte de valeur d'une carte de la collection (29 oct 2026, Mathieu : « quand tu cliques sur la carte dans la
collection, mettre une alarme pour quand la carte prend de la valeur ou descend, pour que l'utilisateur sache quoi faire
avec sa carte sans toujours regarder ; refresh aux semaines dans son inventaire automatiquement. Je te laisse choisir »).

Choix : une cloche par carte (un tap dans sa fiche). Chaque semaine, sa valeur est refaite avec les ventes reelles de la
MEME carte (jamais les prix demandes) et mise a jour dans la collection. Si elle bouge de 15 % ou plus depuis la derniere
reference : une alerte (« +18 % : vaut 1 750 $ »), puis la nouvelle valeur devient la reference.
"""
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS suivi_valeur (carte_id INTEGER PRIMARY KEY, actif INTEGER DEFAULT 1, reference REAL, derniere REAL,
  verifie_le TEXT, cree_le TEXT);
"""
SEUIL = 0.15                    # 15 % de hausse ou de baisse
JOURS = 7                       # une verification par semaine par carte
PAR_HEURE = 12                  # au plus 12 cartes par heure et par compte (le budget SoldComps)


def _cx(api):
    c = api._db()
    c.executescript(SCHEMA)
    return c


def _titre(carte):
    import cartes_match
    import ebay_csv
    t = carte.get("titre") or ebay_csv.titre_annonce(carte) or ""
    if carte.get("auto") and not cartes_match.decoder(t)["auto"]:
        t += " auto"
    return t


def valeur_actuelle(carte, fond=True):
    """La valeur de la carte selon ses ventes reelles sures (None si pas assez de ventes)."""
    import deals
    import vendues
    t = _titre(carte)
    if len(t) < 6:
        return None
    vs = [v for v in (vendues.memes_annonce(t, fond=fond).get("ventes") or []) if v.get("prix")]
    return round(deals.valeur_sure(vs, t)[0], 2) if len(vs) >= 2 and deals.valeur_sure(vs, t)[0] else None


def etat(api, cid):
    c = _cx(api)
    try:
        r = c.execute("SELECT * FROM suivi_valeur WHERE carte_id=?", (int(cid),)).fetchone()
    finally:
        c.close()
    if not r or not r["actif"]:
        return {"ok": True, "actif": False}
    d = dict(r)
    var = round(100 * (d["derniere"] / d["reference"] - 1)) if d.get("derniere") and d.get("reference") else None
    return {"ok": True, "actif": True, "reference": d.get("reference"), "derniere": d.get("derniere"), "verifie_le": d.get("verifie_le"),
            "variation": var, "seuil": int(SEUIL * 100)}


def regler(api, cid, actif):
    carte = api.carte_lire(cid)
    if not carte:
        return {"ok": False, "erreur": "Carte introuvable"}
    c = _cx(api)
    try:
        if actif:
            v = carte.get("valeur")
            c.execute("INSERT INTO suivi_valeur (carte_id, actif, reference, derniere, verifie_le, cree_le) VALUES (?,1,?,?,NULL,?) "
                      "ON CONFLICT(carte_id) DO UPDATE SET actif=1", (int(cid), v, v, datetime.now().isoformat(timespec="seconds")))
        else:
            c.execute("UPDATE suivi_valeur SET actif=0 WHERE carte_id=?", (int(cid),))
        c.commit()
    finally:
        c.close()
    return etat(api, cid)


def ids(api):
    c = _cx(api)
    try:
        return [r[0] for r in c.execute("SELECT carte_id FROM suivi_valeur WHERE actif=1")]
    finally:
        c.close()


def verifier(api, maint=None, valeur=None):
    """Chaque heure (boucle du serveur) : les cartes suivies pas verifiees depuis 7 jours (12 au plus). -> alertes envoyees."""
    import alarmes
    maint = maint or datetime.now()
    valeur = valeur or valeur_actuelle
    lim = (maint - timedelta(days=JOURS)).isoformat(timespec="seconds")
    c = _cx(api)
    try:
        lst = [dict(r) for r in c.execute("SELECT * FROM suivi_valeur WHERE actif=1 AND (verifie_le IS NULL OR verifie_le < ?) "
                                          "ORDER BY verifie_le IS NOT NULL, verifie_le LIMIT ?", (lim, PAR_HEURE))]
    finally:
        c.close()
    if not lst:
        return 0
    etat_a = alarmes._lire()
    n = 0
    for s in lst:
        carte = api.carte_lire(s["carte_id"])
        if not carte or carte.get("statut") == "Vendue":
            _maj(api, s["carte_id"], actif=0)
            continue
        try:
            v = valeur(carte)
        except Exception as e:
            print("Suivi valeur : " + repr(e), flush=True)
            continue                                 # (budget du jour, reseau) : on reessaie l'heure suivante
        champs = {"verifie_le": maint.isoformat(timespec="seconds")}
        if v:
            champs["derniere"] = v
            ref = s.get("reference")
            if not ref:
                champs["reference"] = v
            elif abs(v / ref - 1) >= SEUIL:
                pct = round(100 * (v / ref - 1))
                nom = carte.get("joueur") or alarmes.cartes_match_titre(carte)
                haut = pct > 0
                if alarmes._notifier(api, etat_a, f"valeur:{s['carte_id']}:{maint.strftime('%Y-%m-%d')}",
                                     f"{'📈' if haut else '📉'} {nom} {'+' if haut else '−'}{abs(pct)} % : vaut {v:.0f} $",
                                     f"Était {ref:.0f} $ · ventes réelles de la semaine. "
                                     + ("Bon moment pour la vendre ?" if haut else "Garde-la ou vends-la : à toi de voir."),
                                     "#inventaire", v, carte.get("photo"), maint=None):
                    n += 1
                champs["reference"] = v
            try:                                     # la collection se met a jour toute seule (seulement la valeur)
                cx = api._db()
                try:
                    cx.execute("UPDATE cartes SET valeur=? WHERE id=?", (v, s["carte_id"]))
                    cx.commit()
                finally:
                    cx.close()
            except Exception as e:
                print("Suivi valeur (collection) : " + repr(e), flush=True)
        _maj(api, s["carte_id"], **champs)
    alarmes._ecrire(etat_a)
    return n


def _maj(api, cid, **champs):
    if not champs:
        return
    c = _cx(api)
    try:
        c.execute("UPDATE suivi_valeur SET " + ", ".join(f"{k}=?" for k in champs) + " WHERE carte_id=?", (*champs.values(), int(cid)))
        c.commit()
    finally:
        c.close()
