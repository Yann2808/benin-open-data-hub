# Audit des sources — 2026-10-20

Avant d'écrire un collecteur, on vérifie pour chaque source : le `robots.txt`, les conditions
d'utilisation et la licence, l'existence d'une API officielle, le format, la couverture du
Bénin et la date de la donnée la plus récente. Règle du projet : si la collecte automatique est
interdite ou ambiguë, on ne collecte pas, on référence seulement la source au catalogue.

Toutes les vérifications ont été faites le 2026-10-20 (soir, heure de Paris), avec une requête
unique par adresse et l'en-tête `User-Agent: benin-open-data-hub/0.1`.

## Synthèse

| Source | API officielle | Licence | robots.txt | Donnée la plus récente | Verdict |
|---|---|---|---|---|---|
| Banque mondiale — 3 indicateurs « socle numérique » | oui (API v2) | CC BY 4.0 | autorisé | 2024 (publié le 2026-10-08) | **intégrable** (2 sur 3) |
| ODIN — Open Data Inventory | API JSON du site, non documentée publiquement | CC BY 4.0 (mention sur le site) | pas de restriction | édition 2024 (mise à jour 21/07/2025) | **intégrable** |
| GBIF — biodiversité, Bénin | oui (api.gbif.org, documentée) | par jeu (CC0, CC BY, CC BY-NC) | autorisé | 2026 | **intégrable** |
| HDX — données humanitaires, Bénin | oui (CKAN, documentée) | par jeu (CC BY majoritaire) | `/robots.txt` renvoie un défi anti-robot (202) ; API accessible | 2026-10-20 | **intégrable** (catalogue) |
| Données budgétaires (DGB) | API interne du site, non documentée | non précisée | autorisé (`Disallow:` vide) | 2025-09-11 | **à cataloguer seulement** |
| ARCEP Bénin — Internet | non (PDF) | reproduction interdite sans accord écrit | autorisé (`Crawl-delay: 10`) | T1 2026 (publié en mai 2026) | **à cataloguer seulement** ; prototype local, expérimental |
| IGN Bénin — base de données spatiales | non (ni WMS ni WFS) | non précisée | autorisé (`/wp-admin/` exclu) | 2024 | **à cataloguer seulement** |

## Détail par source

### Banque mondiale — indicateurs du socle numérique
- **URL** : https://donnees.banquemondiale.org/pays/benin (site) ; collecte par l'API déjà utilisée,
  `https://api.worldbank.org/v2`. Pas de doublon : on ajoute seulement des codes dans `config/sources.yml`.
- **robots.txt** : `donnees.banquemondiale.org` → `Allow: /`. L'API n'a pas de robots.txt (404 JSON).
- **Licence** : CC BY 4.0 (conditions de la World Bank Open Data).
- **Vérification des codes** (7 pays, 2000-2025) :
  | Code | Nom officiel (FR) | Bénin | Dernière valeur Bénin |
  |---|---|---|---|
  | `IT.NET.BBND.P2` | Abonnements aux services d'accès haut débit sur ligne fixe (pour 100 habitants) | 23 valeurs | 2024 |
  | `SE.TER.ENRR` | Inscriptions à l'école, enseignement supérieur (% brut) | 23 valeurs | 2022 |
  | `GB.XPD.RSDV.GD.ZS` | Dépenses en recherche et développement (% du PIB) | **aucune valeur** | — |
- **Verdict** : intégrable pour `IT.NET.BBND.P2` et `SE.TER.ENRR`. `GB.XPD.RSDV.GD.ZS` n'est **pas
  ajouté** : la World Bank ne publie aucune valeur pour le Bénin (seuls le Burkina Faso, le Togo, le
  Nigeria, le Sénégal et la Côte d'Ivoire en ont, souvent anciennes). Décision à prendre (voir rapport).

### ODIN — Open Data Inventory (Open Data Watch)
- **URL** : https://odin.opendatawatch.com/country-profiles/BEN?year=2024
- **robots.txt** : aucun (l'adresse renvoie la page de l'application) : pas de restriction déclarée.
- **Licence** : « Licensed under a Creative Commons Attribution 4.0 license » (pied de page du site).
  Citation : Open Data Watch, Open Data Inventory.
- **API** : l'application publique interroge une API JSON (`https://odin-aim.akroninc.net/api/api/client/`),
  la même qui alimente la page « Download data ». Elle n'est pas documentée publiquement, mais elle est
  publique, sans authentification, et sert des données sous CC BY 4.0. Points d'accès utilisés :
  `GetLiveYears`, `GetCountries`, `GetCountryScore/{année}/{pays}`.
- **Format** : JSON. **Couverture** : Bénin et les 6 pays de comparaison, éditions 2015, 2016, 2017,
  2018, 2020, 2022, 2024.
- **Donnée la plus récente** : édition 2024 (dernière mise à jour annoncée : 21 juillet 2025).
- **Verdict** : intégrable, à faible fréquence (49 requêtes par semaine, une pause entre chaque).
  À signaler : API non documentée, susceptible de changer ; prévenir Open Data Watch serait courtois.
  La méthodologie a évolué entre éditions : les comparaisons dans le temps sont indicatives.

### GBIF — biodiversité (Bénin)
- **URL** : http://www.gbifbenin.org/page/consult/acces-aux-donnees-et-metadonnees (site du nœud
  national). Collecte par l'API publique mondiale `https://api.gbif.org/v1`, pays `BJ`, plutôt que par le site.
- **robots.txt** : `api.gbif.org` n'interdit que `/v1/image/unsafe`. Le site du nœud (`gbifbenin.org`)
  n'est joignable qu'en HTTP (HTTPS : connexion réinitialisée).
- **Licence** : chaque jeu porte sa licence (CC0, CC BY 4.0 ou CC BY-NC 4.0) ; accord d'utilisation
  des données GBIF (citation). L'API est documentée (https://techdocs.gbif.org).
- **Format** : JSON. **Couverture** : 1 189 979 occurrences situées au Bénin ; 242 jeux publiés par des
  organismes béninois.
- **Verdict** : intégrable. On ne collecte que des agrégats : occurrences par année d'observation
  (facette `year`) et jeux publiés par année d'enregistrement (`created`).

### HDX — Humanitarian Data Exchange (Bénin)
- **URL** : https://data.humdata.org/group/ben ; API CKAN `https://data.humdata.org/api/3/action/package_search?fq=groups:ben`.
- **robots.txt** : la page renvoie un défi anti-robot (HTTP 202, corps vide) ; l'API documentée répond
  normalement (200, JSON). On n'utilise que l'API, jamais les pages.
- **Licence** : par jeu ; pour les 203 jeux du Bénin : CC BY (103), CC BY-IGO (36), « Other » (27),
  ODbL (14), CC0 (13), CC BY-SA (7). Conditions HDX : réutilisation selon la licence de chaque jeu.
- **Format** : JSON (métadonnées), fichiers variés. **Couverture** : 203 jeux, dont 108 modifiés en 2026.
- **Verdict** : intégrable au **catalogue** (titre, organisation, licence, dates, lien). Les fichiers
  eux-mêmes ne sont pas collectés.

### Données budgétaires — Direction générale du Budget
- **URL** : https://opendata.budgetbenin.bj/ (« Base de données financière de la DGB »).
- **Plateforme** : application Angular ; données servies par une API interne,
  `https://backdata.budgetbenin.bj/public/api` (ex. `/agregats` : 113 agrégats, dernière mise à jour
  2025-09-11). Aucune documentation publique.
- **robots.txt** : le domaine principal n'en a pas (renvoie la page de l'application) ; `backdata` :
  `Disallow:` vide (tout autorisé).
- **Licence** : aucune licence ni condition de réutilisation affichée.
- **Verdict** : **à cataloguer seulement**. API non documentée et licence absente : cas ambigu.
  Question à poser à la DGB : licence de réutilisation, API officielle documentée.

### ARCEP Bénin — Observatoire de l'Internet
- **URL** : https://arcep.bj/internet/ ; tableaux de bord trimestriels en PDF, de 2016 au T1 2026
  (`Observatoire_Internet_T1_2026_TaB.pdf`, publié en mai 2026).
- **robots.txt** : `User-agent: * / Crawl-delay: 10`, aucune exclusion.
- **Conditions** : les mentions légales (https://arcep.bj/mentions-legales/) indiquent que « toute
  reproduction, distribution, modification, adaptation, retransmission ou publication, même partielle »
  du contenu du site est « strictement interdite sans l'accord exprès écrit de l'ARCEP BENIN ».
- **API** : aucune. **Format** : PDF (texte extractible, tableaux réguliers).
- **Verdict** : **à cataloguer seulement** tant que l'ARCEP n'a pas donné son accord écrit.
  Un prototype d'extraction (`ingestion/arcep.py`, marqué expérimental) lit un PDF **déposé à la
  main** et écrit les valeurs, avec leur provenance (fichier, page, période), dans `data/raw/arcep/`,
  dossier non versionné. Rien n'est publié ni affiché.

### IGN Bénin — base de données spatiales des unités administratives
- **URL** : https://ign.bj/webmap/ (« Réalisation : IGN, 2024 » ; départements, communes,
  arrondissements, villages).
- **robots.txt** : seul `/wp-admin/` est exclu.
- **Services** : aucun service WMS/WFS trouvé (`/geoserver/...` → 404). La carte Leaflet charge des
  fichiers GeoJSON statiques (limites, routes, pistes, stations) et des fonds ArcGIS / OpenStreetMap.
- **Licence** : non précisée.
- **Verdict** : **à cataloguer seulement**, aucune collecte de couches. Question à poser à l'IGN :
  licence des limites administratives et existence d'un service WFS.

## Sources déjà présentes (rappel)

| Source | Statut |
|---|---|
| World Bank (API WDI) | collecte réelle, CC BY 4.0 |
| INStaD (NADA) | API absente au 2026-10-20 (404 sur toutes les adresses connues) |
| Open Data for Africa (Knoema) | catalogue via l'API ; valeurs bloquées par Cloudflare (403), non contourné |
| data.gouv.bj | collecte interdite (robots.txt) ; **le domaine ne résout plus en DNS au 2026-10-20** |
