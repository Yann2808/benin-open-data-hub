# Bénin Open Data Hub — contexte pour Claude Code

Projet data personnel de Yann : indicateurs publics du Bénin comparés à 6 voisins
(TGO, NGA, BFA, NER, CIV, SEN) + catalogue des données disponibles sur le pays.
Objectif : projet vitrine « data product », contribution à l'écosystème data/IA béninois
(SNIAM 2023-2027, programme 2026-2033). Répondre en français.

## Architecture
- `ingestion/` (Python) → DuckDB `warehouse/benin.duckdb`, schéma `raw.*` (tout en varchar)
  - `worldbank.py` : API World Bank v2, 12 indicateurs × 7 pays × 2000-2025. **Source indispensable.**
  - `nada.py` : catalogue INStaD (nada.instad.bj). **Source optionnelle** : un échec ne bloque pas le pipeline.
  - `manual.py` : fichiers data.gouv.bj déposés à la main dans `data/manual/` et déclarés dans `config/sources.yml`
    (data.gouv.bj interdit la collecte automatisée dans son robots.txt : ne jamais scraper).
  - `common.py` : HttpClient (retries sur 5xx/429/timeouts, pas sur 4xx), snapshots JSONL dans `data/raw/`.
- `transform/` (dbt-duckdb) : staging (vues) → marts (tables) : dim_country, dim_indicator,
  fct_indicator_values, mart_latest_values, mart_benin_scorecard, mart_data_catalog. 32 tests.
- `app/streamlit_app.py` : 4 onglets (Tableau de bord, Comparer, Catalogue, Méthode).
  Lit DuckDB en local, ou `exports/*.parquet` une fois hébergé.
- `.github/workflows/refresh.yml` : tests à chaque push, collecte réelle chaque lundi, export Parquet commité.
- Ajouter un indicateur ou un pays : uniquement `config/sources.yml`.

## Commandes
`make venv` · `make install` · `make demo` (données synthétiques) · `make run` · `make transform` ·
`make app` · `make test` · `make diagnose`. Le Makefile utilise `.venv/` même non activé.

## Environnement de Yann (important)
- MacBook Pro **Intel x86_64**, macOS ancien (≤ 11). Conda installé avec `(base)` actif par défaut.
- **Toujours travailler dans `.venv`** (Python 3.12, créé depuis le Python de conda), jamais dans conda base :
  dbt lancé depuis conda base a été tué (`Killed: 9`).
- `pyarrow` doit rester **< 18** sur ce Mac (plus de wheels macOS < 12 ensuite → compilation Rust qui échoue).
  Déjà géré par un marqueur dans `requirements.txt` ; installer avec `pip install --prefer-binary`.
- Le Python système (`python3` de macOS) est trop ancien : ne pas l'utiliser.

## État au 2026-10-11
- ✅ Collecte World Bank réelle OK (2 184 lignes), dbt OK, dashboard OK sur vraies données.
- ❌ API INStaD : `/index.php/api/catalog/search` renvoie 404. `nada.py` essaie maintenant 5 adresses ;
  si aucune ne marche, analyser la sortie de `make diagnose` (section API INStaD) pour trouver la bonne.
- Pas encore de dépôt Git ni de GitHub.

## Prochaines étapes
1. Trouver l'API INStaD qui marche (ou basculer sur l'export du catalogue).
2. `git init`, premier commit, dépôt public GitHub `Yann2808/benin-open-data-hub`.
3. Lancer le workflow `refresh` une fois pour produire `exports/*.parquet`, puis déployer sur Streamlit Community Cloud.
4. v0.1 : premiers jeux data.gouv.bj (éducation, santé), carte par commune.

## Conventions
- Code et commentaires en français, noms de variables en anglais.
- Toute nouvelle source : colonnes explicites dans raw, un modèle stg, des tests dbt, une entrée au catalogue.
- Ne jamais présenter les données de démo (`make demo`, marquées `DEMO-SYNTHETIQUE`) comme réelles.
