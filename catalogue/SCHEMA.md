# Format d'un produit du catalogue LockerRoom (un fichier JSON par produit)

Fichier : /tmp/lr/catalogue_src/<id>.json   (id en minuscules, ex. 2025-26-ud-series-1)

```json
{
  "id": "2025-26-ud-series-1",
  "nom": "2025-26 Upper Deck Series 1",
  "saison": "2025-26",
  "marque": "Upper Deck",
  "sortie": "2025-11-05",                      // date de sortie (AAAA-MM-JJ, ou AAAA-MM si seul le mois est connu)
  "formats": [
    {"format": "Boîte hobby", "paquets": 12, "cartes_par_paquet": 12, "boites_par_caisse": 12}
  ],
  "sous_ensembles": [
    // UNE entree par sous-ensemble (base, recrues, inserts, autos, memorabilia, paralleles numerotees...)
    {"nom": "Young Guns", "groupe": "recrue", "nb_cartes": 50, "tirage": null,
     "parallele_de": null, "par_boite": 6, "cotes": "6 par boîte hobby"},
    {"nom": "Young Guns Exclusives", "groupe": "recrue", "nb_cartes": 50, "tirage": 100,
     "parallele_de": "Young Guns", "par_boite": null, "cotes": "/100"}
  ],
  "groupes_boite": [
    // lignes de la composition de boite qui melangent plusieurs sous-ensembles
    {"libelle": "Clear Cut Parallels, UD Canvas Black and White or Encore Blue", "par_boite": 1,
     "sous_ensembles": ["Clear Cut", "UD Canvas Black and White", "Encore Blue"]}
  ],
  "cartes": [
    // SEULEMENT les sous-ensembles qui ont leur propre liste (parallele_de == null)
    {"numero": "201", "joueur": "Artyom Levshunov", "equipe": "CHI", "sous_ensemble": "Young Guns",
     "recrue": true, "auto": false, "memo": false, "tirage": null}
  ],
  "notes": ["ce qui manque ou reste incertain"],
  "sources": ["https://..."]
}
```

Regles
- `groupe` : "base" | "recrue" | "insert" | "auto" | "memo" (relique/patch) | "auto_memo" | "numerotee" (insert numerote sans auto).
- `par_boite` : nombre attendu PAR BOITE HOBBY, tire de la composition officielle de la boite
  ("Young Guns: 6"). Si seules des cotes par paquet existent ("1:144 packs"), calcule
  par_boite = paquets_par_boite / 144 (arrondi a 4 decimales) et garde le texte dans `cotes`.
  Inconnu -> null (ne JAMAIS inventer).
- `tirage` : le numerotage (/100 -> 100), sinon null.
- `equipe` : code LNH a 3 lettres parmi : ANA BOS BUF CGY CAR CHI COL CBJ DAL DET EDM FLA LAK MIN
  MTL NSH NJD NYI NYR OTT PHI PIT SJS SEA STL TBL TOR UTA VAN VGK WSH WPG. Carte a deux equipes :
  "MTL/CHI". Retraite/legende : l'equipe imprimee sur la carte. Utah = UTA.
- Carte a deux joueurs : "Ivan Demidov / Artyom Levshunov".
- Joueurs ecrits comme sur la checklist (accents compris), sans "RC".
- Donnees factuelles seulement : numero, joueur, equipe, sous-ensemble. Aucune description recopiee.
- Rien d'invente : une liste introuvable -> l'omettre et l'ecrire dans `notes`.
- Valider le JSON (python3 -c "import json; json.load(open(...))") avant de terminer.
