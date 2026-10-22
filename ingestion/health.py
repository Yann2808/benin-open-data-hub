"""Baromètre de l'accès aux données : chaque source du projet est testée à chaque
exécution, y compris celles qui sont seulement cataloguées.

But : distinguer une source **inaccessible** (le serveur ne répond pas, refuse
l'accès, est en maintenance) d'une donnée **absente** (la source répond mais ne
publie rien pour le Bénin). Un test = une requête GET légère sur l'adresse
déclarée dans config/sources.yml (section `source_health`), sans retry : on
mesure ce que voit un utilisateur à cet instant.

Pour une source dont le robots.txt interdit la collecte automatisée, on ne teste
que /robots.txt, toujours autorisé : on sait si le site répond sans le collecter.

raw.source_health est enrichie à chaque exécution, jamais écrasée. En CI, où
l'entrepôt repart de zéro, l'historique est rechargé depuis
exports/source_health.parquet (commité avec les autres exports).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

import requests

from . import common
from .common import ROOT, ensure_raw_table, utc_now

log = logging.getLogger("ingestion.health")

COLUMNS = [
    "source", "url_tested", "http_status", "response_time_ms", "official_api",
    "license", "collection_policy", "tested_at", "error_message",
]
# Politique de collecte déclarée pour chaque source (voir docs/audit_sources.md)
POLICIES = ("autorisée", "catalogue seulement", "interdite")
HISTORY_EXPORT = ROOT / "exports" / "source_health.parquet"
USER_AGENT = "benin-open-data-hub/0.1 (+https://github.com/Yann2808)"


def probe(url: str, timeout: float = 30, get: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Une requête GET, sans retry. Le corps n'est pas téléchargé (stream) :
    seuls le code HTTP et le temps de réponse comptent."""
    get = get or requests.get
    start = time.monotonic()
    try:
        resp = get(url, timeout=timeout, stream=True, allow_redirects=True,
                   headers={"User-Agent": USER_AGENT})
        elapsed = time.monotonic() - start
        status = resp.status_code
        resp.close()
        error = None if status < 400 else f"HTTP {status}"
        return {"http_status": str(status), "response_time_ms": str(round(elapsed * 1000)), "error_message": error}
    except requests.RequestException as err:
        elapsed = time.monotonic() - start
        return {"http_status": None, "response_time_ms": str(round(elapsed * 1000)),
                "error_message": f"{type(err).__name__} : {str(err)[:300]}"}


def check_all(entries: list[dict[str, Any]], get: Callable[..., Any] | None = None) -> list[dict[str, Any]]:
    """Teste chaque source déclarée et renvoie une ligne par test."""
    tested_at = utc_now()
    rows = []
    for e in entries:
        policy = e.get("collection_policy", "autorisée")
        if policy not in POLICIES:
            raise ValueError(f"{e['source']} : collection_policy inconnue {policy!r} (attendu : {POLICIES})")
        result = probe(e["url"], get=get)
        rows.append({
            "source": e["source"],
            "url_tested": e["url"],
            "official_api": str(bool(e.get("official_api", False))).lower(),
            "license": e.get("license"),
            "collection_policy": policy,
            "tested_at": tested_at,
            **result,
        })
        log.info("%s : %s en %s ms%s", e["source"], result["http_status"] or "pas de réponse",
                 result["response_time_ms"], f" ({result['error_message']})" if result["error_message"] else "")
    return rows


def append_history(rows: list[dict[str, Any]], history_export: Path = HISTORY_EXPORT) -> int:
    """Ajoute les tests à raw.source_health sans rien effacer. Si la table est
    vide (entrepôt neuf, en CI) et qu'un historique exporté existe, il est
    rechargé d'abord. Renvoie le nombre total de lignes."""
    import duckdb

    ensure_raw_table("source_health", COLUMNS)
    con = duckdb.connect(str(common.WAREHOUSE_PATH))
    try:
        if con.execute("select count(*) from raw.source_health").fetchone()[0] == 0 and history_export.exists():
            cols = ", ".join(f'cast("{c}" as varchar)' for c in COLUMNS)
            con.execute(f"insert into raw.source_health select {cols} from read_parquet(?)", [str(history_export)])
            log.info("Historique du baromètre rechargé depuis %s", history_export.name)
        if rows:
            placeholders = ", ".join("?" for _ in COLUMNS)
            con.executemany(f"insert into raw.source_health values ({placeholders})",
                            [tuple(r.get(c) for c in COLUMNS) for r in rows])
        return con.execute("select count(*) from raw.source_health").fetchone()[0]
    finally:
        con.close()
