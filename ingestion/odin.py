"""Ingestion des scores ODIN (Open Data Inventory, Open Data Watch).

ODIN mesure l'ouverture et la couverture des statistiques officielles publiées
par chaque pays (score de 0 à 100). Licence : CC BY 4.0 (Open Data Watch).

On interroge l'API JSON qui alimente le site public (odin.opendatawatch.com) :
elle n'est pas documentée publiquement mais ne demande aucune authentification
(voir docs/audit_sources.md). Faible fréquence : une requête par pays et par
édition, avec une pause entre deux. Source optionnelle : un échec ne bloque
jamais le pipeline.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .common import HttpClient, utc_now

log = logging.getLogger("ingestion.odin")

COLUMNS = [
    "country_iso3", "edition_year", "overall_score", "coverage_score", "openness_score",
    "rank_world", "n_countries_ranked", "ingested_at",
]


def _s(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def normalize_score(payload: dict[str, Any], iso3: str, year: int, ingested_at: str) -> dict[str, Any] | None:
    """Une ligne par pays × édition ; None si ODIN n'a pas évalué le pays cette année-là."""
    if payload.get("countryTotalPerc") in (None, ""):
        return None
    return {
        "country_iso3": iso3,
        "edition_year": str(year),
        "overall_score": _s(payload.get("countryTotalPerc")),
        "coverage_score": _s(payload.get("coverageScore")),
        "openness_score": _s(payload.get("opennessScore")),
        "rank_world": _s(payload.get("rankWorldTotal")),
        "n_countries_ranked": _s(payload.get("totalCountries")),
        "ingested_at": ingested_at,
    }


def fetch_all(cfg: dict[str, Any], countries: list[str], client: HttpClient | None = None,
              sleep: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
    client = client or HttpClient()
    base = cfg["api_base"].rstrip("/")
    editions = [(y["useId"], int(y["year"])) for y in client.get_json(f"{base}/GetLiveYears") if y.get("isLive")]
    ids = {c["countryCode"]: c["countryId"] for c in client.get_json(f"{base}/GetCountries")}
    missing = [iso for iso in countries if iso not in ids]
    if missing:
        log.warning("ODIN : pays inconnus %s", ", ".join(missing))
    ingested_at = utc_now()
    out = []
    for iso in countries:
        if iso not in ids:
            continue
        for use_id, year in editions:
            # Corps vide : pondération par défaut d'ODIN
            row = normalize_score(client.post_json(f"{base}/GetCountryScore/{use_id}/{ids[iso]}", {}),
                                  iso, year, ingested_at)
            if row:
                out.append(row)
            sleep(cfg.get("pause_seconds", 1))
    log.info("ODIN : %s scores (%s pays × %s éditions)", len(out), len(countries), len(editions))
    return out
