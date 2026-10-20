"""Chargement des fichiers téléchargés à la main (data.gouv.bj, rapports PDF
convertis, etc.).

data.gouv.bj n'autorise pas la collecte automatisée : on respecte cette règle.
Chaque fichier est déclaré dans config/sources.yml avec son URL d'origine et
sa date de téléchargement, ce qui garde la traçabilité.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import duckdb

from .common import ROOT, WAREHOUSE_PATH, utc_now

log = logging.getLogger("ingestion.manual")

SAFE_TABLE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
REGISTRY_COLUMNS = ["table_name", "file", "source_url", "producer", "downloaded_on", "row_count", "loaded_at"]


def load_all(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    folder = ROOT / cfg["folder"]
    entries: list[dict[str, Any]] = []
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        con.execute("create schema if not exists raw")
        for ds in cfg.get("datasets") or []:
            table = ds["table"]
            if not SAFE_TABLE.match(table):
                raise ValueError(f"Nom de table invalide : {table!r} (minuscules, chiffres, _)")
            path = (folder / ds["file"]).resolve()
            if folder.resolve() not in path.parents:
                raise ValueError(f"Fichier hors de {folder} : {ds['file']}")
            if not path.exists():
                log.warning("Fichier déclaré mais absent : %s", path.name)
                continue
            reader = _reader(path)
            con.execute(f"create or replace table raw.{table} as select * from {reader}(?)", [str(path)])
            count = con.execute(f"select count(*) from raw.{table}").fetchone()[0]
            log.info("Manuel %s → raw.%s (%s lignes)", path.name, table, count)
            entries.append({
                "table_name": table,
                "file": ds["file"],
                "source_url": ds.get("source_url"),
                "producer": ds.get("producer"),
                "downloaded_on": str(ds.get("downloaded_on") or ""),
                "row_count": str(count),
                "loaded_at": utc_now(),
            })
    finally:
        con.close()
    return entries


def _reader(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "read_csv_auto"
    if suffix == ".parquet":
        return "read_parquet"
    if suffix in (".json", ".jsonl"):
        return "read_json_auto"
    raise ValueError(f"Format non géré : {path.name} (csv, parquet, json). Convertis les .xlsx en .csv.")


# --- Sources seulement cataloguées (config `catalog_sources`) ------------------------------
CATALOG_COLUMNS = ["title", "producer", "topic", "url", "access", "status"]


def catalog_sources(cfg: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Sources référencées sans collecte : une ligne par source, statut « référencée » par défaut."""
    return [{**{c: s.get(c) for c in CATALOG_COLUMNS}, "status": s.get("status", "référencée")} for s in cfg or []]
