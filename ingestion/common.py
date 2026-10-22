"""Outils partagés : chemins, config, client HTTP avec retries, chargement DuckDB."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.yml"
RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE_PATH = ROOT / "warehouse" / "benin.duckdb"

log = logging.getLogger("ingestion")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ClientError(RuntimeError):
    """Erreur 4xx définitive (adresse inexistante, accès refusé) : inutile de réessayer."""

    def __init__(self, status: int, url: str):
        super().__init__(f"{status} sur {url}")
        self.status = status


class HttpClient:
    """Client GET JSON avec retries exponentiels sur les erreurs passagères
    (5xx, 429, timeouts, coupures). Les 4xx sont définitifs : pas de retry."""

    def __init__(self, retries: int = 4, backoff: float = 2.0, timeout: int = 120):
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "benin-open-data-hub/0.1 (+https://github.com/Yann2808)"
        self.session.headers["Accept"] = "application/json"

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self._send("GET", url, params=params)

    def post_json(self, url: str, body: Any = None) -> Any:
        """POST d'un corps JSON (certaines API de lecture, comme ODIN, passent par POST)."""
        return self._send("POST", url, json=body)

    def _send(self, method: str, url: str, params: dict[str, Any] | None = None, json: Any = None) -> Any:
        last_err: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if method == "GET":
                    resp = self.session.get(url, params=params, timeout=self.timeout)
                else:
                    resp = self.session.post(url, json=json, timeout=self.timeout)
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise ClientError(resp.status_code, resp.url)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise requests.HTTPError(f"{resp.status_code} sur {resp.url}")
                return resp.json()
            except (requests.RequestException, ValueError) as err:
                last_err = err
                if attempt == self.retries:
                    break
                wait = self.backoff ** attempt
                log.warning("Échec %s/%s (%s) — nouvel essai dans %.0fs", attempt, self.retries, err, wait)
                time.sleep(wait)
        raise RuntimeError(f"Impossible de récupérer {url} : {last_err}") from last_err


def write_snapshot(source: str, records: list[dict[str, Any]]) -> Path:
    """Garde une copie brute horodatée (JSONL) : on peut toujours rejouer
    les transformations sans rappeler l'API."""
    folder = RAW_DIR / source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def ensure_raw_table(table: str, columns: list[str]) -> None:
    """Crée raw.<table> vide si elle n'existe pas, sans toucher aux données
    existantes. Utilisé quand une source est en panne : on garde la dernière
    collecte réussie et dbt peut toujours tourner."""
    import duckdb  # import tardif : le diagnostic doit marcher même sans duckdb

    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        con.execute("create schema if not exists raw")
        col_defs = ", ".join(f'"{c}" varchar' for c in columns)
        con.execute(f"create table if not exists raw.{table} ({col_defs})")
    finally:
        con.close()


def upsert_raw_table(table: str, records: list[dict[str, Any]], columns: list[str], key: str) -> int:
    """Remplace dans raw.<table> les lignes dont la clé est présente dans records,
    et garde les autres (ex. journal de collecte cumulé d'une exécution à l'autre)."""
    import duckdb

    ensure_raw_table(table, columns)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        keys = [r[key] for r in records]
        if keys:
            con.execute(f'delete from raw.{table} where "{key}" in (select unnest(?))', [keys])
            placeholders = ", ".join("?" for _ in columns)
            con.executemany(f"insert into raw.{table} values ({placeholders})",
                            [tuple(r.get(c) for c in columns) for r in records])
        return con.execute(f"select count(*) from raw.{table}").fetchone()[0]
    finally:
        con.close()


def drop_demo_rows(table: str, column: str, marker: str) -> int:
    """Supprime de raw.<table> les lignes de démo (valeur de `column` commençant
    par `marker`). Appelé avant une collecte réelle : si la source échoue ensuite,
    « la dernière collecte conservée » ne doit jamais être celle de `make demo`."""
    import duckdb

    if not WAREHOUSE_PATH.exists():
        return 0
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        found = con.execute(
            "select count(*) from information_schema.tables where table_schema = 'raw' and table_name = ?",
            [table],
        ).fetchone()[0]
        if not found:
            return 0
        n = con.execute(f'select count(*) from raw.{table} where starts_with("{column}", ?)', [marker]).fetchone()[0]
        if n:
            con.execute(f'delete from raw.{table} where starts_with("{column}", ?)', [marker])
        return n
    finally:
        con.close()


def load_raw_table(table: str, records: Iterable[dict[str, Any]], columns: list[str]) -> int:
    """Remplace raw.<table> par les enregistrements fournis (colonnes explicites,
    pour que le schéma ne dépende pas de ce que renvoie l'API un jour donné)."""
    rows = [tuple(rec.get(c) for c in columns) for rec in records]
    import duckdb  # import tardif : le diagnostic doit marcher même sans duckdb

    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        con.execute("create schema if not exists raw")
        col_defs = ", ".join(f'"{c}" varchar' for c in columns)
        con.execute(f"create or replace table raw.{table} ({col_defs})")
        if rows:
            placeholders = ", ".join("?" for _ in columns)
            con.executemany(f"insert into raw.{table} values ({placeholders})", rows)
        return len(rows)
    finally:
        con.close()
