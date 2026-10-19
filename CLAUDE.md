# Bénin Open Data Hub — contexte pour Claude Code

Projet data personnel de Yann : indicateurs publics du Bénin comparés à 6 voisins
(TGO, NGA, BFA, NER, CIV, SEN) + catalogue des données disponibles sur le pays.
Objectif : projet vitrine « data product », contribution à l'écosystème data/IA béninois
(SNIAM 2023-2027, programme 2026-2033). Répondre en français.

## Architecture
- `ingestion/` (Python) → DuckDB `warehouse/benin.duckdb`, schéma `raw.*` (tout en varchar)
  - `worldbank.py` : API World Bank v2, 12 indicateurs × 7 pays × 2000-2025. **Source indispensable.**
  - `nada.py` : catalogue INStaD (nada.instad.bj). **Source optionnelle** : un échec ne bloque pas le pipeline.
  - `odfa.py` : portail Open Data for Africa — Bénin (Knoema, BAD) via son API. `make run` rafraîchit le catalogue,
    `make odfa` collecte tous les jeux (reprise : `data/raw/odfa/<id>.parquet`, `--refresh` pour tout recollecter).
    robots.txt interdit `/api/1.0/sdmx` : ne jamais l'appeler. Licence de chaque jeu dans `mart_odfa_datasets`.
    Le téléchargement des valeurs renvoie 403 (Cloudflare « Just a moment ») : **ne pas contourner** la protection ;
    voie légitime = identifiants API (`ODFA_APP_ID` / `ODFA_APP_SECRET`, lus par le code) ou contact du portail.
  - `manual.py` : fichiers data.gouv.bj déposés à la main dans `data/manual/` et déclarés dans `config/sources.yml`
    (data.gouv.bj interdit la collecte automatisée dans son robots.txt : ne jamais scraper).
  - `common.py` : HttpClient (retries sur 5xx/429/timeouts, pas sur 4xx), snapshots JSONL dans `data/raw/`,
    `drop_demo_rows` : une collecte réelle (`run.py` sans `--offline`) purge d'abord les lignes de démo.
- `transform/` (dbt-duckdb) : staging (vues) → marts (tables) : dim_country, dim_indicator,
  fct_indicator_values, mart_latest_values, mart_benin_scorecard, mart_data_catalog, mart_odfa_datasets. 38 tests.
- `app/streamlit_app.py` : 7 onglets (Tableau de bord, Fiche pays, Investir au Bénin, Comparer, Open Data for Africa,
  Catalogue, Méthode). Investir : marché (zones Bénin / + frontaliers / + reste du hub), structure de l'économie,
  stabilité sur 10 ans (moyenne et écart-type croissance/inflation, monnaie base 100 en 2015), crédit, IDE, ouverture.
  Pas de Doing Business (arrêté en 2021) ; gouvernance WGI prévue (autre base de l'API World Bank, source 3).
  Fiche pays : `country_profile()` refait en pandas le calcul de `mart_benin_scorecard` pour n'importe quel pays
  (à garder aligné avec le SQL) ; sélecteur lié à l'URL (`?pays=Togo`, libellé du pays).
  `app/odfa_catalog.py` : titres ODFA lisibles depuis les slugs, thème estimé par mots-clés, famille de producteur.
  Lit DuckDB en local, ou `exports/*.parquet` une fois hébergé. Streamlit ≥ 1.50 (metrics avec sparklines, badges).
  `query()` est en `@st.cache_data(ttl=3600)` : après un commit d'exports, l'app en ligne garde les anciennes
  données jusqu'à 1 h (redéployer le code ne vide pas ce cache). Pour forcer : « Reboot app » sur share.streamlit.io.
  Thème dans `.streamlit/config.toml` (vert Bénin `#0F7B4B`, Inter / Space Grotesk, clair imposé).
  Couleurs des pays attribuées par code ISO, jamais par rang : le Bénin en vert, chaque voisin sa couleur.
- `.github/workflows/refresh.yml` : tests à chaque push et PR ; collecte réelle chaque lundi 05:17 UTC
  (ou `workflow_dispatch`), dbt build, export Parquet commité sur `main` par `github-actions[bot]`.
- `.devcontainer/` : config Codespaces générée par Streamlit Cloud (lance l'app sur le port 8501).
- Skill Claude Code `developing-with-streamlit` : lien symbolique local (ignoré par Git), recréé par `streamlit skills`.
- Ajouter un indicateur ou un pays : uniquement `config/sources.yml`. Champ `section` : « tableau de bord » (défaut)
  ou « investir » → colonne `dim_indicator.section`. Le tableau de bord et la fiche pays ne montrent que la première.

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

## État au 2026-10-19
- ✅ Dépôt public https://github.com/Yann2808/benin-open-data-hub (PR #1 mergée : ODFA + refonte du dashboard).
- ✅ Onglet « Investir au Bénin » en ligne (PR #5 ; la PR #4 visait la mauvaise branche). Refresh du 2026-10-19 :
  23 indicateurs (12 tableau de bord + 11 investir), 4 105 valeurs dans les exports.
- ✅ Dashboard public : https://bj-odh.streamlit.app/ (Streamlit Community Cloud, branche `main`,
  fichier `app/streamlit_app.py`, visibilité publique). Redéploiement automatique à chaque commit sur `main`.
- ✅ Collecte World Bank réelle OK (jusqu'à 2025), dbt OK.
- ✅ Catalogue ODFA : 1 107 jeux inventoriés ; ❌ valeurs non collectées (403 Cloudflare, voir plus haut).
- ❌ INStaD (nada.instad.bj) : tout le site en maintenance (404/503) au 2026-10-12. Source optionnelle, on attend.

## Prochaines étapes
1. Cache de l'app : ajouter la date de modification de `exports/*.parquet` à la clé de `query()`, pour que
   chaque refresh soit visible tout de suite.
2. Accès API ODFA (identifiants) pour collecter les valeurs ; humaniser les titres des jeux (slugs).
3. Revérifier l'API INStaD quand le site sera revenu (`make diagnose`).
4. v0.2 : premiers jeux data.gouv.bj (éducation, santé), carte par commune.

## Conventions
- Code et commentaires en français, noms de variables en anglais.
- Toute nouvelle source : colonnes explicites dans raw, un modèle stg, des tests dbt, une entrée au catalogue.
- Ne jamais présenter les données de démo (`make demo`, marquées `DEMO-SYNTHETIQUE`) comme réelles.
- Git : travailler sur une branche, PR vers `main` (merger = mettre en ligne). Puller `main` avant de commencer,
  le bot y commite les exports chaque lundi. Ne jamais commiter `.streamlit/secrets.toml`.
- PR : toujours `gh pr create --base main`, jamais vers une autre branche de feature. Si une branche dépend d'une
  autre, la rebaser sur `main` une fois la première mergée. Avant de merger, vérifier la cible
  (`gh pr view --json baseRefName`) : la PR #4 a été mergée dans une branche morte et n'est jamais arrivée en ligne.
- Nouveaux indicateurs dans `config/sources.yml` : après le merge, lancer `gh workflow run refresh.yml`, sinon les
  exports en ligne ne les contiennent qu'au lundi suivant.
- Usage de Claude transparent : trailer `Co-Authored-By: Claude` dans les commits, mention dans le README
  (section « Méthode de travail ») ; pas de ligne « 🤖 Generated with Claude Code » dans les PR.
