"""Ingestion d'agrégats GBIF (biodiversité) pour le Bénin, via l'API publique
documentée https://api.gbif.org/v1 (pas le site du nœud national).

On ne collecte que des comptages annuels, jamais les occurrences elles-mêmes :
  - occurrences : observations situées au Bénin (pays BJ), par année d'observation ;
  - jeux publiés : jeux de données enregistrés par des organismes béninois, par
    année d'enregistrement sur GBIF.
Chaque jeu GBIF porte sa licence (CC0, CC BY, CC BY-NC). Source optionnelle.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from .common import HttpClient, utc_now

log = logging.getLogger("ingestion.gbif")

COLUMNS = ["metric", "year", "value", "ingested_at"]
METRICS = ("occurrences", "jeux publiés")


def occurrences_by_year(client: HttpClient, base: str, country: str) -> Counter:
    payload = client.get_json(f"{base}/occurrence/search",
                              {"country": country, "facet": "year", "facetLimit": 1000, "limit": 0})
    facets = payload.get("facets") or [{}]
    return Counter({int(c["name"]): int(c["count"]) for c in facets[0].get("counts", [])})


def datasets_by_year(client: HttpClient, base: str, country: str, page_size: int = 200) -> Counter:
    years: Counter = Counter()
    offset = 0
    while True:
        payload = client.get_json(f"{base}/dataset", {"country": country, "limit": page_size, "offset": offset})
        for ds in payload.get("results", []):
            if ds.get("created"):
                years[int(ds["created"][:4])] += 1
        if payload.get("endOfRecords", True) or not payload.get("results"):
            return years
        offset += page_size


def fetch_all(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient()
    base, country = cfg["api_base"].rstrip("/"), cfg["country"]
    ingested_at = utc_now()
    rows = []
    for metric, counts in (("occurrences", occurrences_by_year(client, base, country)),
                           ("jeux publiés", datasets_by_year(client, base, country))):
        rows.extend({"metric": metric, "year": str(y), "value": str(n), "ingested_at": ingested_at}
                    for y, n in sorted(counts.items()))
    log.info("GBIF : %s lignes (occurrences et jeux publiés par année)", len(rows))
    return rows
