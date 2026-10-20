"""Ingestion du catalogue HDX (Humanitarian Data Exchange, OCHA) pour le Bénin,
via l'API CKAN documentée (`package_search`, groupe `ben`).

On ne collecte que les métadonnées des jeux (titre, organisation, licence,
dates, lien) pour le catalogue unifié : les fichiers ne sont pas téléchargés.
Les pages du site renvoient un défi anti-robot : on ne les appelle jamais.
Source optionnelle.
"""
from __future__ import annotations

import logging
from typing import Any

from .common import HttpClient, utc_now

log = logging.getLogger("ingestion.hdx")

COLUMNS = [
    "dataset_id", "name", "title", "organization", "license", "dataset_date",
    "last_modified", "num_resources", "url", "ingested_at",
]


def normalize(pkg: dict[str, Any], site: str, ingested_at: str) -> dict[str, Any]:
    org = pkg.get("organization") or {}
    return {
        "dataset_id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "organization": org.get("title") if isinstance(org, dict) else str(org),
        "license": pkg.get("license_title"),
        "dataset_date": pkg.get("dataset_date"),
        "last_modified": pkg.get("last_modified") or pkg.get("metadata_modified"),
        "num_resources": None if pkg.get("num_resources") is None else str(pkg["num_resources"]),
        "url": f"{site}/dataset/{pkg['name']}" if pkg.get("name") else None,
        "ingested_at": ingested_at,
    }


def fetch_all(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient()
    site = cfg["site"].rstrip("/")
    ingested_at = utc_now()
    rows, start, page = [], 0, int(cfg.get("page_size", 500))
    while True:
        result = client.get_json(f"{site}/api/3/action/package_search",
                                 {"fq": f"groups:{cfg['group']}", "rows": page, "start": start})["result"]
        batch = result.get("results", [])
        rows.extend(normalize(p, site, ingested_at) for p in batch)
        start += len(batch)
        if not batch or start >= int(result.get("count", 0)):
            break
    log.info("HDX : %s jeux de données (groupe %s)", len(rows), cfg["group"])
    return rows
