"""
SLABCOACH - « ce que tu as manque depuis ta derniere visite » (12 nov 2026).

Mathieu : « monsieur, madame tout le monde, un papa, un grand-pere, quelqu'un qui travaille, qui n'a pas le temps de suivre
le marche. Quand il ouvre l'app : bonjour, voici les nouvelles que tu as manquees depuis ta derniere visite. » En mots
simples, seulement ce qui touche SES cartes : ses joueurs (echange, honneur, blessure, gros changement de l'Indice SlabIQ),
la valeur de sa collection, ses ventes, ses alertes. Jamais un prix de vente d'eBay (licence) : la valeur de SA collection
est celle que l'app lui montre deja.

L'historique de l'Indice (indice_hist.json) : une ligne par jour {nom: [indice, equipe, en_feu]}, 45 jours.
"""
import json
import os
import threading
from datetime import date, datetime, timedelta

HIST_JOURS = 45
PAUSE_H = 6            # une « nouvelle visite » : 6 h sans ouvrir l'app (une nuit, une journee de travail)
ECART_INDICE = 6.0     # un changement d'Indice qui vaut la peine d'etre dit
MAX_JOUEURS = 6
_verrou = threading.Lock()
_CACHE = {"mt": None, "d": None}

EVS = {  # type d'evenement -> (mot, ton) ; le sens vient de indice_joueurs.TYPES_EVENEMENTS
    "temple": ("Temple de la renommée", "or"), "honneur": ("Honoré", "or"), "trophee": ("Trophée", "or"),
    "exploit": ("Exploit", "vert"), "rappel": ("Rappelé", "vert"), "contrat": ("Contrat", ""),
    "echange": ("Échangé", "or"), "blessure": ("Blessé", "rouge"), "negatif": ("Mauvaise nouvelle", "rouge")}
EVS_EN = {"temple": "Hall of Fame", "honneur": "Honoured", "trophee": "Award", "exploit": "Milestone", "rappel": "Called up",
          "contrat": "Contract", "echange": "Traded", "blessure": "Injured", "negatif": "Bad news"}


# -- l'historique de l'Indice ------------------------------------------------------------------------------------------
def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "indice_hist.json")


def hist_lire():
    p = _chemin()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _CACHE["mt"] != mt:
        try:
            with open(p, encoding="utf-8") as f:
                _CACHE["d"] = json.load(f) or {}
            _CACHE["mt"] = mt
        except (OSError, ValueError):
            return {}
    return _CACHE["d"] or {}


def hist_noter(I, jour=None):
    """La photo du jour de l'Indice (la derniere passe du jour remplace la precedente) ; 45 jours gardes."""
    jour = (jour or date.today()).isoformat()
    ligne = {nom: [v.get("indice"), v.get("equipe") or None, 1 if "en_feu" in (v.get("pastilles") or []) else 0]
             for nom, v in (I or {}).items() if v.get("indice") is not None}
    with _verrou:
        h = dict(hist_lire())
        h[jour] = ligne
        lim = (date.fromisoformat(jour) - timedelta(days=HIST_JOURS)).isoformat()
        h = {k: v for k, v in h.items() if k >= lim}
        p = _chemin()
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(p + ".tmp", p)
        _CACHE["mt"], _CACHE["d"] = os.path.getmtime(p), h
    return len(ligne)


def avant(nom, jour):
    """[indice, equipe, en_feu] du joueur au dernier jour <= jour (ou None)."""
    h = hist_lire()
    for k in sorted((k for k in h if k <= jour), reverse=True):
        v = h[k].get(nom)
        if v:
            return v
    return None


# -- les joueurs ---------------------------------------------------------------------------------------------------------
def joueurs(noms, depuis, en=False, I=None, marche=None):
    """Ce qui a change pour ces joueurs depuis la date ISO « depuis » : echange, evenement, Indice. -> [items] du plus
    important au moins important."""
    import indice_joueurs
    if I is None:
        I = indice_joueurs.lire().get("indice") or {}
    if marche is None:
        try:
            import demande_legale
            marche = demande_legale.marche_equipe
        except Exception:
            marche = None
    jour = str(depuis)[:10]
    out = []
    for nom, n_cartes in noms:
        v = I.get(nom) or indice_joueurs.indice(nom)
        if not v:
            continue
        a = avant(nom, jour)
        it = {"joueur": nom, "cartes": n_cartes, "indice": v.get("indice")}
        poids = 0.0
        # 1. un echange (l'equipe du jour contre celle de la derniere visite)
        if a and a[1] and v.get("equipe") and a[1] != v.get("equipe"):
            it.update(sorte="echange", de=a[1], vers=v["equipe"])
            try:
                m0, m1 = (marche(a[1]), marche(v["equipe"])) if marche else (None, None)
            except Exception:
                m0 = m1 = None
            if m0 is not None and m1 is not None and abs(m1 - m0) >= 10:
                it["marche"] = "plus" if m1 > m0 else "moins"
            poids = 100
        # 2. un evenement depuis la visite (Temple, honneur, trophee, blessure...)
        evs = [e for e in v.get("evenements") or [] if str(e.get("date") or "")[:10] >= jour]
        if evs and not it.get("sorte"):
            e = max(evs, key=lambda e: abs({"temple": 30, "honneur": 25, "trophee": 20, "negatif": 18, "exploit": 15, "blessure": 15,
                                              "rappel": 12, "contrat": 6, "echange": 3}.get(e.get("type"), 1)))
            it.update(sorte="evenement", type=e.get("type"), sens=e.get("sens"), titre=e.get("titre"), lien=e.get("lien"))
            poids = 80 if e.get("type") in ("temple", "honneur", "trophee", "blessure", "negatif") else 50
        # 3. l'Indice SlabIQ qui a bouge
        if a and a[0] is not None and v.get("indice") is not None:
            d = round(v["indice"] - a[0], 1)
            if abs(d) >= ECART_INDICE:
                it["ecart"] = d
                if not it.get("sorte"):
                    it["sorte"] = "monte" if d > 0 else "baisse"
                    poids = 30 + abs(d)
        # 4. en feu maintenant (et pas a la derniere visite)
        if "en_feu" in (v.get("pastilles") or []) and not (a and a[2]):
            it["feu"] = True
            if not it.get("sorte"):
                it["sorte"] = "feu"
                poids = 40
            w = v.get("semaine") or {}
            if w.get("mj"):
                it["semaine"] = {"pts": w.get("pts"), "mj": w.get("mj")}
        if it.get("sorte"):
            it["poids"] = poids + min(10, n_cartes)
            out.append(it)
    out.sort(key=lambda x: -x["poids"])
    return out[:MAX_JOUEURS]


def phrase(it, en=False):
    """Un item joueur -> (titre, detail, ton) en mots simples."""
    j, s = it["joueur"], it["sorte"]
    if s == "echange":
        t = (f"{j} : traded {it['de']} → {it['vers']}" if en else f"{j} a changé d'équipe : {it['de']} → {it['vers']}")
        if it.get("marche") == "moins":
            d = "A smaller card market: his cards often dip for a while" if en else "Un plus petit marché de cartes : ses cartes baissent souvent pour un temps"
        elif it.get("marche") == "plus":
            d = "A bigger card market: good news for his cards" if en else "Un plus gros marché de cartes : une bonne nouvelle pour ses cartes"
        else:
            d = "Check your cards' value" if en else "Vérifie la valeur de tes cartes"
        return t, d, "or"
    if s == "evenement":
        mot, ton = EVS.get(it.get("type"), ("Nouvelle", ""))
        if en:
            mot = EVS_EN.get(it.get("type"), "News")
        return f"{j} · {mot}", (it.get("titre") or "")[:140], ton or ("vert" if (it.get("sens") or 0) > 0 else "rouge")
    if s in ("monte", "baisse"):
        d = it["ecart"]
        if en:
            return (f"{j} {'is rising' if d > 0 else 'is falling'}", f"SlabIQ index {'+' if d > 0 else ''}{d:g} since your last visit", "vert" if d > 0 else "rouge")
        return (f"{j} {'monte' if d > 0 else 'baisse'}", f"Indice SlabIQ {'+' if d > 0 else ''}{d:g} depuis ta dernière visite".replace(".", ","), "vert" if d > 0 else "rouge")
    if s == "feu":
        w = it.get("semaine") or {}
        if en:
            return f"{j} is on fire", (f"{w.get('pts')} points in {w.get('mj')} games" if w.get("mj") else "Great week"), "or"
        return f"{j} est en feu", (f"{w.get('pts')} points en {w.get('mj')} matchs" if w.get("mj") else "Une grosse semaine"), "or"
    return j, "", ""


# -- la visite -----------------------------------------------------------------------------------------------------------
def heures_depuis(iso, maintenant=None):
    try:
        return ((maintenant or datetime.now()) - datetime.fromisoformat(str(iso)[:19])).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def rouler_visite(r, maintenant=None):
    """Les reglages (visite_le, visite_prec) -> (depuis, nouvelle_visite, a_ecrire). Une nouvelle visite = PAUSE_H heures sans
    ouvrir l'app ; « depuis » = le debut de la visite d'avant (on garde le meme resume toute la visite)."""
    maintenant = maintenant or datetime.now()
    now = maintenant.isoformat(timespec="seconds")
    der = r.get("visite_le") or ""
    h = heures_depuis(der, maintenant) if der else None
    if h is None:
        return None, False, {"visite_le": now}                # 1re fois : rien a dire (le tour de l'app s'en occupe)
    if h >= PAUSE_H:
        return der, True, {"visite_le": now, "visite_prec": der}
    return r.get("visite_prec") or None, False, {"visite_le": now}


def valeur_noter(hist, valeur, nb, jour=None):
    """{AAAA-MM-JJ: [valeur, nb]} : une photo par jour de la valeur de la collection, 60 jours."""
    jour = (jour or date.today()).isoformat()
    h = dict(hist or {})
    h[jour] = [round(valeur, 2), nb]
    for k in sorted(h)[:-60]:
        h.pop(k, None)
    return h


def valeur_avant(hist, depuis):
    j = str(depuis or "")[:10]
    ks = [k for k in sorted(hist or {}) if k <= j]
    return (hist[ks[-1]] if ks else None)
