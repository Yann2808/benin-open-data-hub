"""Ingestion des indicateurs World Bank (API v2, sans clé).

Doc : https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
Format de réponse : [métadonnées de pagination, [observations...]]
"""
from __future__ import annotations

import logging
from typing import Any

from .common import HttpClient, utc_now

log = logging.getLogger("ingestion.worldbank")

COLUMNS = [
    "indicator_code", "indicator_name", "country_iso3", "country_name",
    "year", "value", "unit", "obs_status", "source_last_updated", "ingested_at",
]


def parse_page(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Sépare métadonnées et observations. L'API renvoie un objet 'message'
    (au lieu d'une liste) quand un indicateur n'existe pas."""
    if not isinstance(payload, list) or len(payload) < 2:
        if isinstance(payload, list) and payload and "message" in payload[0]:
            raise ValueError(f"Erreur API World Bank : {payload[0]['message']}")
        return {}, []
    meta, data = payload[0], payload[1] or []
    return meta, data


def normalize(obs: dict[str, Any], last_updated: str | None, ingested_at: str) -> dict[str, Any]:
    return {
        "indicator_code": obs["indicator"]["id"],
        "indicator_name": obs["indicator"]["value"],
        "country_iso3": obs.get("countryiso3code") or obs["country"]["id"],
        "country_name": obs["country"]["value"],
        "year": obs["date"],
        "value": None if obs.get("value") is None else str(obs["value"]),
        "unit": obs.get("unit") or None,
        "obs_status": obs.get("obs_status") or None,
        "source_last_updated": last_updated,
        "ingested_at": ingested_at,
    }


def fetch_indicator(client: HttpClient, cfg: dict[str, Any], code: str) -> list[dict[str, Any]]:
    countries = ";".join([cfg["focus_country"], *cfg["peer_countries"]])
    url = f"{cfg['base_url']}/country/{countries}/indicator/{code}"
    params = {"format": "json", "per_page": 1000, "date": f"{cfg['start_year']}:{cfg['end_year']}", "page": 1}
    ingested_at = utc_now()
    out: list[dict[str, Any]] = []
    while True:
        meta, data = parse_page(client.get_json(url, params))
        last_updated = meta.get("lastupdated")
        out.extend(normalize(o, last_updated, ingested_at) for o in data)
        if not meta or params["page"] >= int(meta.get("pages", 1)):
            break
        params["page"] += 1
    log.info("World Bank %s : %s observations", code, len(out))
    return out


def fetch_all(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient()
    records: list[dict[str, Any]] = []
    for ind in cfg["indicators"]:
        records.extend(fetch_indicator(client, cfg, ind["code"]))
    return records


# Où l'indicateur s'affiche : tableau de bord général, ou onglet « Investir au Bénin »
DEFAULT_SECTION = "tableau de bord"
SECTIONS = (DEFAULT_SECTION, "investir")


def indicator_catalog(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Métadonnées métier des indicateurs (libellé FR, thème, sens de lecture)."""
    return [
        {
            "indicator_code": i["code"],
            "label_fr": i["label"],
            "theme": i["theme"],
            "unit_fr": i["unit"],
            "higher_is_better": None if i.get("higher_is_better") is None else str(i["higher_is_better"]).lower(),
            "section": i.get("section", DEFAULT_SECTION),
        }
        for i in cfg["indicators"]
    ]


CATALOG_COLUMNS = ["indicator_code", "label_fr", "theme", "unit_fr", "higher_is_better", "section"]


# --- Métadonnées des indicateurs (définition officielle, organisme producteur) ----------
# Endpoint en français (/v2/fr/indicator) : nom et organisme traduits par la World Bank ;
# la définition (sourceNote) reste souvent en anglais, on la garde telle que publiée.
META_COLUMNS = ["indicator_code", "name_source", "definition", "source_organization", "ingested_at"]


def normalize_meta(item: dict[str, Any], ingested_at: str) -> dict[str, Any]:
    def s(key: str) -> str | None:
        val = item.get(key)
        return val.strip() if isinstance(val, str) and val.strip() else None

    return {
        "indicator_code": item["id"],
        "name_source": s("name"),
        "definition": s("sourceNote"),
        "source_organization": s("sourceOrganization"),
        "ingested_at": ingested_at,
    }


def fetch_metadata(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient()
    ingested_at = utc_now()
    out = []
    for ind in cfg["indicators"]:
        _, data = parse_page(client.get_json(f"{cfg['base_url']}/fr/indicator/{ind['code']}", {"format": "json"}))
        out.extend(normalize_meta(item, ingested_at) for item in data)
    log.info("World Bank : métadonnées de %s indicateurs", len(out))
    return out
