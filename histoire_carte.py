"""
SLABCOACH - l'histoire d'une carte (13 nov 2026).

Mathieu : « quand tu cliques sur le score, il faudrait qu'on voie la carte en soi : y a-t-il quelque chose de special
associe a cette carte-la avec ce joueur-la ? Surtout pour les cartes des annees 90, debut 2000, que le monde connait
moins. Pourquoi cette carte-la est interessante. »

Une carte (annee + joueur + produit / insert / parallele, sans le numero de serie ni le grade) -> 2 ou 3 phrases simples :
ce qui la rend speciale (le produit a l'epoque, l'insert, sa rarete annoncee par le fabricant, le moment de la carriere
du joueur). Ecrites par Claude APRES une recherche web (Wikipedia, sites du hobby), avec leurs sources (titre + lien).
Gardee pour toujours (une carte ne change pas d'histoire) : une seule recherche par carte, pour tous les comptes.
Jamais de prix, jamais de population PSA/BGS (regle SlabCoach), jamais un fait invente : rien de special -> on le dit.
Budget : LR_HISTOIRE_JOUR recherches neuves par jour (40).
"""
import json
import os
import re
import threading
import time
from datetime import date

VERSION = 1
_verrou = threading.Lock()
_EN_COURS = {}
_CACHE = {"mt": None, "d": None}

SYSTEME = """Tu es un historien des cartes de hockey (et des autres sports) pour l'app SlabCoach. On te donne UNE carte.
Cherche sur le web (Wikipedia, Cardboard Connection, PSA Card Facts / articles, Beckett articles, blogues de collectionneurs)
ce qui la rend speciale, puis ecris pour un collectionneur ordinaire (un papa, un enfant de 12 ans doit comprendre) :
- 2 ou 3 phrases courtes au total : le produit ou l'insert a l'epoque (nouveau, premier du genre, rarete ANNONCEE par le
  fabricant, design celebre), et/ou le moment de la carriere du joueur (sa recrue, sa saison record, un trophee cette annee-la).
- Seulement des faits trouves dans tes recherches ou tres connus. Si tu n'es pas sur : ne le dis pas.
- Si rien de special : dis simplement que c'est une carte courante de ce produit, en une phrase.
- JAMAIS de prix, de valeur, de ventes, ni de nombre de cartes gradees (population PSA/BGS/SGC). Pas de conseil d'achat.
Reponds a la fin avec UNIQUEMENT ce JSON (rien apres) :
<json>{"speciale": true|false, "fr": "...", "en": "...", "sources": [{"titre": "...", "url": "https://..."}]}</json>
(2 sources au plus, celles qui appuient vraiment le texte.)"""


def _chemin():
    import comptes
    return os.path.join(comptes.DONNEES, "histoire_cartes.json")


def _lire():
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
            return _CACHE["d"] or {}
    return _CACHE["d"] or {}


def _ecrire(d):
    p = _chemin()
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(p + ".tmp", p)
    _CACHE["mt"], _CACHE["d"] = os.path.getmtime(p), d


def identite(titre, joueur=None):
    """La carte, sans ce qui ne change pas son histoire (numero de serie, grade, etat) : la cle du cache + sa description."""
    import cartes_match
    c = cartes_match.cible_titre(titre or "")
    j = (joueur or c.get("joueur") or "").strip().lower()
    if not j:
        return None, None
    an = c.get("annee")
    mots = sorted(set(c.get("marques") or set()) | set(c.get("produits") or set()) | set(c.get("ident") or set())
                  | set(c.get("paralleles") or set()))
    attrs = [k for k in ("rc", "auto", "patch", "inscr") if c.get(k)]
    if c.get("serie"):
        attrs.append("/" + str(c["serie"]))                  # le tirage annonce fait partie de l'histoire (/25, /100)
    cle = "|".join([str(an or ""), j, " ".join(mots), " ".join(attrs)])
    # la description envoyee au modele : le titre nettoye (sans grade, sans numero de copie)
    desc = re.sub(r"\b(psa|bgs|sgc|tag|cgc|beckett)\s*\d+(\.\d)?\b", " ", str(titre or ""), flags=re.I)
    desc = re.sub(r"\b\d{1,4}\s*/\s*(\d{1,4})\b", r"/\1", desc)
    return cle, " ".join(desc.split())[:200]


def budget_jour():
    try:
        return max(0, int(os.environ.get("LR_HISTOIRE_JOUR") or 40))
    except ValueError:
        return 40


def lire(titre, joueur=None):
    """L'histoire deja connue (ou None) ; jamais d'appel."""
    cle, _d = identite(titre, joueur)
    return _lire().get(cle) if cle else None


def _analyser(rep):
    texte = "".join(b.get("text") or "" for b in (rep or {}).get("content") or [] if b.get("type") == "text")
    m = re.search(r"<json>\s*(\{.*\})\s*</json>", texte, re.S) or re.search(r"(\{[^{}]*\"fr\".*\})", texte, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except ValueError:
        return None
    fr, en = str(d.get("fr") or "").strip(), str(d.get("en") or "").strip()
    if not fr:
        return None
    # garde-fous : pas de prix ni de population, meme si le modele en glisse un
    interdit = re.compile(r"(\$|€|\bprix\b|\bvaleur\b|\bvendu|\bpopulation\b|\bpop\b|\bprice\b|\bsold\b|\bworth\b)", re.I)
    fr = " ".join(p for p in re.split(r"(?<=[.!?])\s+", fr) if not interdit.search(p))
    en = " ".join(p for p in re.split(r"(?<=[.!?])\s+", en) if not interdit.search(p))
    if not fr:
        return None
    src = []
    for s in (d.get("sources") or [])[:2]:
        u = str((s or {}).get("url") or "")
        if u.startswith("https://") and "google." not in u:
            src.append({"titre": str(s.get("titre") or u)[:120], "url": u[:400]})
    return {"speciale": bool(d.get("speciale")), "fr": fr[:600], "en": (en or fr)[:600], "sources": src}


def generer(titre, joueur=None, appeler=None):
    """L'histoire de la carte : du cache, sinon UNE recherche (budget du jour). -> {fr, en, sources, speciale} ou {erreur}."""
    cle, desc = identite(titre, joueur)
    if not cle:
        return {"erreur": "carte inconnue"}
    d = _lire()
    if cle in d:
        return d[cle]
    with _verrou:
        ev = _EN_COURS.get(cle)
        if ev is None:
            ev = _EN_COURS[cle] = threading.Event()
            moi = True
        else:
            moi = False
    if not moi:                                      # deja cherchee par quelqu'un d'autre : on attend son resultat
        ev.wait(60)
        return _lire().get(cle) or {"erreur": "pas encore"}
    try:
        jour = date.today().isoformat()
        cpt = d.get("_compteur") or {}
        if cpt.get("jour") == jour and cpt.get("n", 0) >= budget_jour():
            return {"erreur": "budget"}
        if appeler is None:
            import vision
            if not vision._cle():
                return {"erreur": "inactif"}
            appeler = lambda corps: vision._appeler(corps, timeout=90)
        corps = {"model": os.environ.get("LR_HISTOIRE_MODELE") or __import__("vision").MODELE, "max_tokens": 1200, "system": SYSTEME,
                 "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                 "messages": [{"role": "user", "content": f"La carte : {desc}\nLe joueur : {joueur or ''}\nRaconte ce qui la rend speciale."}]}
        t0 = time.time()
        try:
            rep = appeler(corps)
            # la recherche web peut demander une pause (« pause_turn ») : on relance avec ce qui est deja fait (2 fois au plus)
            for _ in range(2):
                if (rep or {}).get("stop_reason") != "pause_turn":
                    break
                corps = dict(corps, messages=corps["messages"] + [{"role": "assistant", "content": rep.get("content") or []}])
                rep = appeler(corps)
        except Exception as e:
            print("Histoire de carte : " + repr(e)[:200], flush=True)
            return {"erreur": "indisponible"}
        h = _analyser(rep)
        with _verrou:
            d = dict(_lire())
            c2 = d.get("_compteur") or {}
            d["_compteur"] = {"jour": jour, "n": (c2.get("n", 0) if c2.get("jour") == jour else 0) + 1}
            if h:
                h.update(le=jour, v=VERSION, s=round(time.time() - t0, 1))
                d[cle] = h
            _ecrire(d)
        return h or {"erreur": "rien"}
    finally:
        with _verrou:
            _EN_COURS.pop(cle, None)
        ev.set()
