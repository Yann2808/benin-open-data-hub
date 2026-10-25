# Bénin Open Data Hub

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bj-odh.streamlit.app/)
[![refresh](https://github.com/Yann2808/benin-open-data-hub/actions/workflows/refresh.yml/badge.svg)](https://github.com/Yann2808/benin-open-data-hub/actions/workflows/refresh.yml)

**Dashboard en ligne : [bj-odh.streamlit.app](https://bj-odh.streamlit.app/)**

Les grands indicateurs du Bénin, comparés à ses voisins d'Afrique de l'Ouest, et un catalogue des données publiques disponibles sur le pays. Sources ouvertes, pipeline reproductible, rafraîchi chaque semaine.

**Pourquoi.** La Stratégie nationale d'IA et des mégadonnées (SNIAM 2023-2027) et le programme 2026-2033 font de la donnée publique une priorité. Mais les données sur le Bénin sont dispersées entre la World Bank, l'INStaD et data.gouv.bj, dans des formats hétérogènes. Ce hub les rassemble, les documente et les rend lisibles.

## Ce que fait le hub

| Brique | Contenu |
|---|---|
| **Tableau de bord** | 14 indicateurs (démographie, économie, numérique, énergie, éducation, emploi, santé) : dernière valeur, évolution sur 5 ans, rang et position face à la médiane de 6 pays voisins ; définition officielle, unité, année et source dans l'infobulle de chaque chiffre |
| **Fiche pays** | Le même diagnostic pour chacun des 7 pays (rangs, points forts, courbes) et un face-à-face avec le Bénin ; lien partageable (`?pays=Togo`) |
| **Investir au Bénin** | Pour entrepreneurs et investisseurs : taille du marché (avec les pays frontaliers), structure de l'économie, stabilité (croissance, inflation, monnaie face au dollar), crédit, IDE et ouverture commerciale |
| **Comparer** | Séries temporelles du Bénin face à ses pairs, indicateur par indicateur, avec définition et téléchargement CSV complet (7 pays, toutes années, statut de collecte, source) |
| **Open Data for Africa** | Inventaire des 1 107 jeux du portail de la BAD : titres lisibles, thème estimé, producteur, âge des jeux (mis à jour depuis 2024, entre 2020 et 2023, avant 2020) par producteur, recherche et filtres |
| **Catalogue** | Tout ce que le hub connaît : indicateurs, enquêtes de l'INStaD, jeux d'Open Data for Africa (BAD) et de HDX (OCHA), biodiversité (GBIF), fichiers data.gouv.bj déposés et sources seulement référencées (budget, ARCEP, IGN), avec source, période, licence et lien ; export CSV complet et formulaire « Proposer une source » |
| **Accès aux données** | Baromètre : chaque source testée à chaque collecte (joignable, en panne, collecte interdite), taux de disponibilité, dernière réponse réussie ; scores ODIN d'ouverture des statistiques officielles |

## Architecture

```
World Bank API ─┐
INStaD (NADA) ──┤
Open Data       │
 for Africa ────┼─► ingestion/ (Python) ─► DuckDB raw.* ─► dbt (staging → marts + tests) ─► Streamlit
ODIN, GBIF, HDX ┤   retries, snapshots       warehouse/       51 tests de qualité              app/
data.gouv.bj ───┤   baromètre d'accès
 (dépôt manuel) │
toutes sources ─┘   (test HTTP à chaque collecte → raw.source_health, historique cumulé)
```

- **Ingestion** (`ingestion/`) : une source en panne ne bloque pas les autres. Chaque collecte est gardée en JSONL horodaté dans `data/raw/` pour pouvoir rejouer les transformations. Le baromètre (`ingestion/health.py`) teste chaque source déclarée, y compris celles seulement cataloguées.
- **Audit des sources** (`docs/audit_sources.md`) : robots.txt, licence, API et verdict pour chaque source avant toute collecte.
- **Transformations** (`transform/`, dbt-duckdb) : typage, dédoublonnage, dimensions, faits, scorecard, catalogue. Tests : unicité, relations, valeurs acceptées, rangs cohérents, pourcentages entre 0 et 100.
- **Dashboard** (`app/`) : lit DuckDB en local, ou les exports Parquet versionnés une fois hébergé.
- **CI** (`.github/workflows/refresh.yml`) : tests à chaque push, collecte réelle chaque lundi, export Parquet commité.

## Démarrer

```bash
make venv      # crée .venv (les commandes make l'utilisent même s'il n'est pas activé)
make install
make diagnose  # en cas de problème : copie la sortie dans une issue

make demo   # pipeline complet sur données SYNTHÉTIQUES, sans réseau
make run    # pipeline complet sur les vraies sources
make app    # dashboard sur http://localhost:8501
make test   # tests Python + tests dbt
make odfa   # collecte complète d'Open Data for Africa (longue, reprend où elle s'est arrêtée)
make docs   # documentation dbt et lignage
```

Prototype expérimental (non branché sur `make run`) : `python -m ingestion.arcep fichier.pdf` lit un tableau de bord ARCEP déposé à la main et écrit les valeurs, avec leur provenance, dans `data/raw/arcep/` (non versionné). Rien n'est publié tant que l'ARCEP n'a pas donné son accord écrit.

`make demo` sert uniquement à vérifier que tout fonctionne : les valeurs sont générées aléatoirement et le dashboard affiche un bandeau d'avertissement.

**Prérequis** : Python 3.10 à 3.12. Sur un Mac Intel sous macOS 11 ou antérieur, `requirements.txt` fixe automatiquement `pyarrow` en version 17, la dernière publiée précompilée pour ces systèmes. Sans ce garde-fou, pip tente une compilation qui échoue faute de compilateur Rust.

## Ajouter des données

- **Un indicateur ou un pays de comparaison** : `config/sources.yml`, aucune modification de code. Le champ `section` choisit la page : tableau de bord (défaut) ou `investir`.
- **Un fichier de data.gouv.bj** : voir `data/manual/README.md`. Le portail n'autorise pas la collecte automatisée, donc le dépôt est manuel, avec URL et date de téléchargement tracées.
- **Une source seulement référencée** (sans collecte) : `catalog_sources` dans `config/sources.yml`, et une entrée `source_health` pour le baromètre.
- **Proposer une source** : [formulaire d'issue](https://github.com/Yann2808/benin-open-data-hub/issues/new?template=proposer-une-source.yml).

## Méthode

- Pour chaque pays, on prend la dernière valeur publiée. Un pays n'entre dans la comparaison que si sa donnée a moins de 5 ans d'écart avec la plus récente (`comparison_window_years`).
- Le rang n'est calculé que pour les indicateurs au sens clair (plus d'accès à l'électricité = mieux, plus d'inflation = moins bien). Population et urbanisation sont seulement situées par rapport à la médiane.
- Les évolutions des indicateurs en % sont données en points, les autres en % relatif.
- **Inaccessible n'est pas absente** : une source inaccessible ne répond pas au moment du test ; une donnée absente n'est pas publiée par une source qui répond. Le hub ne remplit jamais une case vide.
- Abonnements et personnes ne se mélangent pas : « abonnements pour 100 habitants » (mobile, haut débit fixe) d'un côté, « personnes utilisant Internet, % de la population » de l'autre.
- Chaque valeur porte un statut de collecte (collectée / démo) et la date de publication de sa source ; chaque indicateur, sa définition officielle (telle que publiée, parfois en anglais).

## En ligne

Le dashboard public tourne sur Streamlit Community Cloud : [bj-odh.streamlit.app](https://bj-odh.streamlit.app/). Aucun serveur à maintenir :

1. **Chaque lundi** (ou à la demande : onglet *Actions* → `refresh` → *Run workflow*), GitHub Actions collecte les sources, lance dbt et ses tests, puis commite les marts dans `exports/*.parquet`. Si un test échoue, rien n'est publié et le site garde la version précédente.
2. **Streamlit Community Cloud** surveille la branche `main` : à chaque commit (données ou code), l'app redémarre et lit les exports Parquet.

Sur l'offre gratuite, l'app se met en veille après une période sans visite ; le premier visiteur la réveille en une trentaine de secondes.

## Feuille de route

- [x] v0 : World Bank + catalogue INStaD + dépôt manuel, scorecard, catalogue, CI
- [x] v0.1 : inventaire du portail Open Data for Africa — Bénin (1 107 jeux, avec source, fraîcheur et licence) et dashboard public
- [ ] v0.1 : collecte des valeurs Open Data for Africa (code prêt, `make odfa`) : le téléchargement est aujourd'hui bloqué par la protection anti-robots du portail, en attente d'un accès API
- [ ] v0.2 : premiers jeux de données data.gouv.bj (éducation, santé) et carte par commune
- [ ] v0.2 : indicateurs propres au numérique béninois (ARCEP, ASIN) et à l'agriculture
- [ ] v0.3 : API publique en lecture (exports Parquet + DuckDB-WASM ou FastAPI)
- [x] v0.2 : baromètre de l'accès aux sources, définitions officielles, âge des jeux ODFA, ODIN, GBIF, HDX
- [ ] v1 : fiche « qualité des données » par source (fraîcheur, complétude, trous)

## Licence

Code sous licence MIT. Les données restent sous la licence de leurs producteurs (World Bank : CC BY 4.0 ; ODIN, Open Data Watch : CC BY 4.0 ; GBIF et HDX : licence propre à chaque jeu).

## Méthode de travail

Le projet est développé avec l'aide de [Claude Code](https://claude.com/claude-code) (Anthropic) : les commits concernés portent la mention `Co-Authored-By: Claude`. Les choix de sources, de licences et de méthode restent relus et décidés par l'auteur.
