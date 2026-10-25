# Bénin Open Data Hub — contexte pour Claude Code

Projet data personnel de Yann : indicateurs publics du Bénin comparés à 6 voisins
(TGO, NGA, BFA, NER, CIV, SEN) + catalogue des données disponibles sur le pays.
Objectif : projet vitrine « data product », contribution à l'écosystème data/IA béninois
(SNIAM 2023-2027, programme 2026-2033). Répondre en français.

## Architecture
- `ingestion/` (Python) → DuckDB `warehouse/benin.duckdb`, schéma `raw.*` (tout en varchar)
  - `worldbank.py` : API World Bank v2, 25 indicateurs × 7 pays × 2000-2025. **Source indispensable.**
    Définitions officielles via `/v2/fr/indicator` (repli sur l'anglais si la traduction est vide) → `raw.wb_indicator_meta`.
  - `nada.py` : catalogue INStaD (nada.instad.bj). **Source optionnelle** : un échec ne bloque pas le pipeline.
  - `odfa.py` : portail Open Data for Africa — Bénin (Knoema, BAD) via son API. `make run` rafraîchit le catalogue,
    `make odfa` collecte tous les jeux (reprise : `data/raw/odfa/<id>.parquet`, `--refresh` pour tout recollecter).
    robots.txt interdit `/api/1.0/sdmx` : ne jamais l'appeler. Licence de chaque jeu dans `mart_odfa_datasets`.
    Le téléchargement des valeurs renvoie 403 (Cloudflare « Just a moment ») : **ne pas contourner** la protection ;
    voie légitime = identifiants API (`ODFA_APP_ID` / `ODFA_APP_SECRET`, lus par le code) ou contact du portail.
  - `manual.py` : fichiers data.gouv.bj déposés à la main dans `data/manual/` et déclarés dans `config/sources.yml`
    (data.gouv.bj interdit la collecte automatisée dans son robots.txt : ne jamais scraper).
  - `health.py` : baromètre de l'accès aux sources (section `source_health` de la config) : un GET sans retry par
    source à chaque collecte → `raw.source_health`, cumulé, jamais écrasé ; rechargé depuis `exports/source_health.parquet`
    sur un entrepôt neuf (CI). Collecte interdite : seul `/robots.txt` est testé.
  - `odin.py` (scores ODIN, CC BY 4.0, API JSON du site non documentée), `gbif.py` (agrégats annuels, api.gbif.org),
    `hdx.py` (catalogue CKAN, groupe `ben`) : **sources optionnelles**, jamais en démo. Voir `docs/audit_sources.md`.
  - `arcep.py` : **prototype expérimental**, non branché sur `make run` : lit un PDF ARCEP déposé à la main →
    `data/raw/arcep/` (non versionné). Mentions légales ARCEP : reproduction interdite sans accord écrit → rien n'est publié.
  - `catalog_sources` (config) : sources auditées seulement référencées (budget DGB, ARCEP, IGN) → `raw.catalog_sources`.
  - `common.py` : HttpClient (`get_json` / `post_json`, retries sur 5xx/429/timeouts, pas sur 4xx), snapshots JSONL dans `data/raw/`,
    `drop_demo_rows` : une collecte réelle (`run.py` sans `--offline`) purge d'abord les lignes de démo.
- `transform/` (dbt-duckdb) : staging (vues) → marts (tables) : dim_country, dim_indicator,
  fct_indicator_values (avec `collection_status` collectée/démo), mart_latest_values, mart_benin_scorecard,
  mart_data_catalog (types : indicateur, enquête, fichier déposé, jeu de données, source référencée), mart_odfa_datasets,
  mart_source_availability, mart_odin_scores, mart_gbif_yearly. 51 tests dbt, 52 tests pytest (dont un test de fumée
  de l'app avec `AppTest`).
- `app/streamlit_app.py` : 8 pages `st.navigation` (menu en haut, replié dans un menu latéral sur téléphone ; adresses `/fiche-pays`, `/investir`, etc.) : Tableau de bord, Fiche pays, Investir au Bénin, Comparer, Open Data for Africa,
  Catalogue, Accès aux données, Méthode. Une fonction `page_*` par page, routeur en fin de fichier ; le test de fumée les ouvre toutes. Définition, unité, année et source à côté de chaque chiffre (`definition_md`,
  `source_line`). Abonnements (« pour 100 habitants ») et personnes (« % de la population ») jamais confondus :
  `tests/test_labels.py` le vérifie. Investir : marché (zones Bénin / + frontaliers / + reste du hub), structure de l'économie,
  stabilité sur 10 ans (moyenne et écart-type croissance/inflation, monnaie base 100 en 2015), crédit, IDE, ouverture.
  Pas de Doing Business (arrêté en 2021) ; gouvernance WGI prévue (autre base de l'API World Bank, source 3).
  Fiche pays : `country_profile()` refait en pandas le calcul de `mart_benin_scorecard` pour n'importe quel pays
  (à garder aligné avec le SQL) ; sélecteur lié à l'URL (`?pays=Togo`, libellé du pays).
  `app/odfa_catalog.py` : titres ODFA lisibles depuis les slugs, thème estimé par mots-clés, famille de producteur,
  âge des jeux (`update_period`, `age_table`).
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

## État au 2026-10-21
- ⏳ Branche `nightly/2026-10-21` (mission de nuit) : baromètre d'accès, définitions, âge ODFA, audit des sources,
  ODIN, GBIF, HDX, exports CSV, modèle d'issue. PR ouverte, à relire ; voir `RAPPORT_NUIT.md`.
- ❌ data.gouv.bj : le domaine ne résout plus en DNS au 2026-10-20.
- ✅ Dépôt public https://github.com/Yann2808/benin-open-data-hub (PR #1 mergée : ODFA + refonte du dashboard).
- ✅ Onglet « Investir au Bénin » en ligne (PR #5 ; la PR #4 visait la mauvaise branche). Refresh du 2026-10-19 :
  23 indicateurs (12 tableau de bord + 11 investir), 4 105 valeurs dans les exports.
- ✅ Dashboard public : https://bj-odh.streamlit.app/ (Streamlit Community Cloud, branche `main`,
  fichier `app/streamlit_app.py`, visibilité publique). Redéploiement automatique à chaque commit sur `main`.
- ✅ Collecte World Bank réelle OK (jusqu'à 2025), dbt OK.
- ✅ Catalogue ODFA : 1 107 jeux inventoriés ; ❌ valeurs non collectées (403 Cloudflare, voir plus haut).
- ❌ INStaD (nada.instad.bj) : tout le site en maintenance (404/503) au 2026-10-12. Source optionnelle, on attend.

## Prochaines étapes
0. Relire et fusionner la PR de la nuit ; décisions en attente dans `RAPPORT_NUIT.md` (ARCEP, budget, R&D).
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
