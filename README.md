# Bénin Open Data Hub

Les grands indicateurs du Bénin, comparés à ses voisins d'Afrique de l'Ouest, et un catalogue des données publiques disponibles sur le pays. Sources ouvertes, pipeline reproductible, rafraîchi chaque semaine.

**Pourquoi.** La Stratégie nationale d'IA et des mégadonnées (SNIAM 2023-2027) et le programme 2026-2033 font de la donnée publique une priorité. Mais les données sur le Bénin sont dispersées entre la World Bank, l'INStaD et data.gouv.bj, dans des formats hétérogènes. Ce hub les rassemble, les documente et les rend lisibles.

## Ce que fait le hub

| Brique | Contenu |
|---|---|
| **Tableau de bord** | 12 indicateurs (démographie, économie, numérique, énergie, éducation, emploi, santé) : dernière valeur, évolution sur 5 ans, rang et position face à la médiane de 6 pays voisins |
| **Comparer** | Séries temporelles du Bénin face à ses pairs, indicateur par indicateur |
| **Catalogue** | Tout ce que le hub connaît : indicateurs, enquêtes de l'INStaD, jeux du portail Open Data for Africa (BAD), fichiers data.gouv.bj déposés, avec source, période, licence et lien |

## Architecture

```
World Bank API ─┐
INStaD (NADA) ──┼─► ingestion/ (Python) ─► DuckDB raw.* ─► dbt (staging → marts + tests) ─► Streamlit
Open Data       │   retries, snapshots       warehouse/       38 tests de qualité              app/
 for Africa ─────┤   JSONL / Parquet
data.gouv.bj ───┘
 (dépôt manuel)
```

- **Ingestion** (`ingestion/`) : une source en panne ne bloque pas les autres. Chaque collecte est gardée en JSONL horodaté dans `data/raw/` pour pouvoir rejouer les transformations.
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

`make demo` sert uniquement à vérifier que tout fonctionne : les valeurs sont générées aléatoirement et le dashboard affiche un bandeau d'avertissement.

**Prérequis** : Python 3.10 à 3.12. Sur un Mac Intel sous macOS 11 ou antérieur, `requirements.txt` fixe automatiquement `pyarrow` en version 17, la dernière publiée précompilée pour ces systèmes. Sans ce garde-fou, pip tente une compilation qui échoue faute de compilateur Rust.

## Ajouter des données

- **Un indicateur ou un pays de comparaison** : `config/sources.yml`, aucune modification de code.
- **Un fichier de data.gouv.bj** : voir `data/manual/README.md`. Le portail n'autorise pas la collecte automatisée, donc le dépôt est manuel, avec URL et date de téléchargement tracées.

## Méthode

- Pour chaque pays, on prend la dernière valeur publiée. Un pays n'entre dans la comparaison que si sa donnée a moins de 5 ans d'écart avec la plus récente (`comparison_window_years`).
- Le rang n'est calculé que pour les indicateurs au sens clair (plus d'accès à l'électricité = mieux, plus d'inflation = moins bien). Population et urbanisation sont seulement situées par rapport à la médiane.
- Les évolutions des indicateurs en % sont données en points, les autres en % relatif.

## Mettre en ligne

1. Pousser le dépôt sur GitHub (public).
2. Lancer le workflow `refresh` à la main une première fois : il produit `exports/*.parquet`.
3. Déployer `app/streamlit_app.py` sur Streamlit Community Cloud (gratuit), qui lit ces exports.

## Feuille de route

- [x] v0 : World Bank + catalogue INStaD + dépôt manuel, scorecard, catalogue, CI
- [x] v0.1 : collecte complète du portail Open Data for Africa — Bénin (API Knoema), inventaire avec fraîcheur et licences
- [ ] v0.2 : premiers jeux de données data.gouv.bj (éducation, santé) et carte par commune
- [ ] v0.2 : indicateurs propres au numérique béninois (ARCEP, ASIN) et à l'agriculture
- [ ] v0.3 : API publique en lecture (exports Parquet + DuckDB-WASM ou FastAPI)
- [ ] v1 : fiche « qualité des données » par source (fraîcheur, complétude, trous)

## Licence

Code sous licence MIT. Les données restent sous la licence de leurs producteurs (World Bank : CC BY 4.0).
