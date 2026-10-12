"""Collecte complète du portail Open Data for Africa — Bénin (benin.opendataforafrica.org).

Le portail tourne sur la plateforme Knoema. On passe par son API publique,
jamais par le HTML :
  - catalogue : GET /api/1.0/meta/dataset (titre, source, licence, dates)
  - données   : client Python officiel `knoema`, jeu par jeu

Règles de politesse :
  - robots.txt interdit /api/1.0/sdmx : on ne l'utilise jamais ;
  - pause configurable entre deux jeux de données ;
  - reprise sur interruption : chaque jeu est sauvegardé dans
    data/raw/odfa/<id>.parquet et n'est pas recollecté sans --refresh ;
  - un jeu en échec est journalisé et n'arrête pas les autres.

Licences : chaque jeu porte sa licence et ses conditions d'utilisation
(champs licence / terms_url). Les vérifier avant de republier des données
brutes ; les marts publiés ne contiennent que le catalogue.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .common import RAW_DIR, HttpClient, utc_now

log = logging.getLogger("ingestion.odfa")

DATASET_COLUMNS = [
    "dataset_id", "title", "description", "dataset_type", "status", "category",
    "source_id", "source_name", "source_verified", "license", "terms_url",
    "publication_date", "last_updated_on", "next_release_date", "accessed_on",
    "dimensions", "url", "listed_at",
]
OBS_COLUMNS = ["dataset_id", "series_key", "dimensions", "frequency", "date", "value", "fetched_at"]
LOG_COLUMNS = ["dataset_id", "status", "row_count", "error", "fetched_at"]

OUT_DIR = RAW_DIR / "odfa"


# --- Catalogue ------------------------------------------------------------------

def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


def normalize_dataset(item: dict[str, Any], host: str, listed_at: str) -> dict[str, Any]:
    source = item.get("source") or {}
    dims = item.get("dimensions") or []
    dim_names = [(_first(x, "name", "id") if isinstance(x, dict) else str(x)) for x in dims]
    desc = _first(item, "description", "rawDescription")
    ds_id = _first(item, "id", "key")

    def s(v: Any) -> str | None:
        return None if v in (None, "") else str(v)

    return {
        "dataset_id": s(ds_id),
        "title": s(_first(item, "title", "name")),
        "description": s(desc)[:2000] if desc else None,
        "dataset_type": s(item.get("type")),
        "status": s(item.get("status")),
        "category": s(item.get("category")),
        "source_id": s(source.get("id")),
        "source_name": s(_first(source, "localizedName", "name")),
        "source_verified": s(source.get("isVerified")),
        "license": s(_first(item, "licenseTypeName") or _first(source, "licenseTypeName")),
        "terms_url": s(_first(item, "termsOfUseLink") or _first(source, "termsOfUseLink")),
        "publication_date": s(item.get("publicationDate")),
        "last_updated_on": s(item.get("lastUpdatedOn")),
        "next_release_date": s(item.get("nextReleaseDate")),
        "accessed_on": s(item.get("accessedOn")),
        "dimensions": json.dumps([d for d in dim_names if d], ensure_ascii=False),
        "url": f"https://{host}/{ds_id}" if ds_id else None,
        "listed_at": listed_at,
    }


def list_datasets(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient(retries=3)
    host = cfg["host"]
    payload = client.get_json(f"https://{host}/api/1.0/meta/dataset")
    if isinstance(payload, dict):  # certaines versions enveloppent la liste
        payload = payload.get("items") or payload.get("data") or []
    listed_at = utc_now()
    datasets = [normalize_dataset(x, host, listed_at) for x in payload if isinstance(x, dict)]
    datasets = [d for d in datasets if d["dataset_id"]]
    log.info("Open Data for Africa : %s jeux de données au catalogue", len(datasets))
    return datasets


def select_datasets(datasets: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    include = set(cfg.get("include") or [])
    exclude = set(cfg.get("exclude") or [])
    chosen = [d for d in datasets
              if (not include or d["dataset_id"] in include) and d["dataset_id"] not in exclude]
    limit = cfg.get("max_datasets")
    return chosen[: int(limit)] if limit else chosen


# --- Données --------------------------------------------------------------------

def frame_to_long(df: pd.DataFrame, dataset_id: str, fetched_at: str) -> pd.DataFrame:
    """Met le tableau large renvoyé par knoema.get au format long :
    une ligne par série × date. Les dimensions de la série (variables d'un jeu
    à l'autre) sont rangées en JSON pour garder un schéma unique."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OBS_COLUMNS)

    work = df.copy()
    if not isinstance(work.columns, pd.MultiIndex):
        work.columns = pd.MultiIndex.from_arrays([work.columns.astype(str)], names=["series"])
    level_names = [n if n else f"dim_{i}" for i, n in enumerate(work.columns.names)]
    work.columns = work.columns.set_names(level_names)
    work.index = work.index.rename("date")

    long = work.melt(ignore_index=False, value_name="value").reset_index()
    long = long[pd.to_numeric(long["value"], errors="coerce").notna()]
    if long.empty:
        return pd.DataFrame(columns=OBS_COLUMNS)

    freq_col = next((c for c in level_names if c.lower() == "frequency"), None)
    dim_cols = [c for c in level_names if c != freq_col]

    def dims_json(row: pd.Series) -> str:
        return json.dumps({c: str(row[c]) for c in dim_cols}, ensure_ascii=False)

    out = pd.DataFrame({
        "dataset_id": dataset_id,
        "dimensions": long.apply(dims_json, axis=1),
        "frequency": long[freq_col].astype(str) if freq_col else None,
        "date": pd.to_datetime(long["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(long["date"].astype(str)),
        "value": pd.to_numeric(long["value"], errors="coerce").astype(str),
        "fetched_at": fetched_at,
    })
    out["series_key"] = out["dimensions"] + "|" + out["frequency"].fillna("").astype(str)
    return out[OBS_COLUMNS]


def _default_fetcher(cfg: dict[str, Any]) -> Callable[[str], pd.DataFrame]:
    import knoema  # import tardif : seulement si on collecte vraiment

    api = knoema.ApiConfig()
    api.host = cfg["host"]
    app_id, app_secret = os.environ.get("ODFA_APP_ID"), os.environ.get("ODFA_APP_SECRET")
    if app_id and app_secret:  # facultatif : relève les quotas d'appels
        api.app_id, api.app_secret = app_id, app_secret
    return lambda dataset_id: knoema.get(dataset_id)


def fetch_datasets(
    datasets: list[dict[str, Any]],
    cfg: dict[str, Any],
    refresh: bool = False,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
    out_dir: Path = OUT_DIR,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Collecte chaque jeu et écrit data/raw/odfa/<id>.parquet. Renvoie le journal."""
    out_dir.mkdir(parents=True, exist_ok=True)
    fetcher = fetcher or _default_fetcher(cfg)
    pause = float(cfg.get("pause_seconds", 2))
    journal: list[dict[str, Any]] = []
    todo = [d for d in datasets if refresh or not (out_dir / f"{d['dataset_id']}.parquet").exists()]
    skipped = len(datasets) - len(todo)
    if skipped:
        log.info("%s jeux déjà collectés, ignorés (--refresh pour les recollecter)", skipped)

    for i, ds in enumerate(todo, start=1):
        ds_id = ds["dataset_id"]
        fetched_at = utc_now()
        try:
            long = frame_to_long(fetcher(ds_id), ds_id, fetched_at)
            tmp = out_dir / f"{ds_id}.parquet.tmp"
            long.to_parquet(tmp, index=False)
            tmp.replace(out_dir / f"{ds_id}.parquet")  # écriture atomique
            journal.append({"dataset_id": ds_id, "status": "ok", "row_count": str(len(long)),
                            "error": None, "fetched_at": fetched_at})
            log.info("[%s/%s] %s — %s valeurs (%s)", i, len(todo), ds_id, len(long), (ds["title"] or "")[:60])
        except Exception as err:  # noqa: BLE001 — un jeu en échec n'arrête pas la collecte
            journal.append({"dataset_id": ds_id, "status": "échec", "row_count": "0",
                            "error": f"{type(err).__name__}: {err}"[:500], "fetched_at": fetched_at})
            log.warning("[%s/%s] %s en échec : %s", i, len(todo), ds_id, err)
        if i < len(todo):
            sleep(pause)
    return journal


def load_observations(out_dir: Path = OUT_DIR) -> int:
    """(Re)construit raw.odfa_observations à partir de tous les fichiers collectés."""
    import duckdb

    from . import common

    con = duckdb.connect(str(common.WAREHOUSE_PATH))
    try:
        con.execute("create schema if not exists raw")
        files = sorted(out_dir.glob("*.parquet")) if out_dir.exists() else []
        if files:
            pattern = str(out_dir / "*.parquet").replace("'", "''")
            cols = ", ".join(f'cast("{c}" as varchar) as "{c}"' for c in OBS_COLUMNS)
            con.execute(f"create or replace table raw.odfa_observations as "
                        f"select {cols} from read_parquet('{pattern}', union_by_name = true)")
        else:
            col_defs = ", ".join(f'"{c}" varchar' for c in OBS_COLUMNS)
            con.execute(f"create or replace table raw.odfa_observations ({col_defs})")
        return con.execute("select count(*) from raw.odfa_observations").fetchone()[0]
    finally:
        con.close()
