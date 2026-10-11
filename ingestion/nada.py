"""Ingestion du catalogue de microdonnées de l'INStaD (plateforme NADA).

On ne récupère que les métadonnées publiques du catalogue : quelles enquêtes
existent, sur quelles années, par qui. C'est la base d'un « catalogue des
données du Bénin » consultable dans le dashboard.

L'adresse de l'API change selon la version de NADA et la configuration du
serveur (réécriture d'URL avec ou sans index.php). On essaie donc plusieurs
adresses connues et on garde la première qui renvoie un catalogue.
`make diagnose` affiche le résultat de chaque essai.
"""
from __future__ import annotations

import logging
from typing import Any

from .common import ClientError, HttpClient, utc_now

log = logging.getLogger("ingestion.nada")

COLUMNS = [
    "study_id", "idno", "title", "nation", "year_start", "year_end",
    "repository", "data_access_type", "created", "changed", "url", "ingested_at",
]

# (chemin de l'API de recherche, paramètre taille, paramètre page) par ordre de probabilité
CANDIDATES = [
    ("/index.php/api/catalog/search", "ps", "page"),
    ("/api/catalog/search", "ps", "page"),
    ("/index.php/api/catalog", "ps", "page"),
    ("/api/catalog", "ps", "page"),
    ("/index.php/api/catalog/search", "limit", "page"),
]


def parse_rows(payload: Any) -> tuple[int, list[dict[str, Any]]]:
    if isinstance(payload, list):
        return len(payload), payload
    result = payload.get("result", payload) if isinstance(payload, dict) else {}
    rows = result.get("rows") or result.get("data") or []
    total = int(result.get("total") or result.get("found") or len(rows))
    return total, rows


def looks_like_catalog(payload: Any) -> bool:
    _, rows = parse_rows(payload)
    return bool(rows) and isinstance(rows[0], dict) and ("idno" in rows[0] or "title" in rows[0])


def normalize(row: dict[str, Any], site_root: str, ingested_at: str) -> dict[str, Any]:
    study_id = row.get("id") or row.get("sid")

    def s(key: str) -> str | None:
        val = row.get(key)
        return None if val in (None, "") else str(val)

    return {
        "study_id": None if study_id is None else str(study_id),
        "idno": s("idno"),
        "title": s("title"),
        "nation": s("nation"),
        "year_start": s("year_start"),
        "year_end": s("year_end"),
        "repository": s("repositoryid"),
        "data_access_type": s("data_access_type") or s("form_model"),
        "created": s("created"),
        "changed": s("changed"),
        "url": f"{site_root}/index.php/catalog/{study_id}" if study_id is not None else None,
        "ingested_at": ingested_at,
    }


def probe(client: HttpClient, site_root: str) -> list[tuple[str, str]]:
    """Essaie chaque adresse candidate et renvoie (adresse, verdict). Sert au diagnostic."""
    report = []
    for path, size_key, page_key in CANDIDATES:
        url = f"{site_root}{path}"
        try:
            payload = client.get_json(url, {size_key: 2, page_key: 1})
            verdict = "OK, catalogue trouvé" if looks_like_catalog(payload) else f"JSON inattendu : {str(payload)[:120]}"
        except ClientError as err:
            verdict = f"HTTP {err.status}"
        except Exception as err:  # noqa: BLE001 — on rapporte tout
            verdict = f"échec : {err}"[:200]
        report.append((f"{url}?{size_key}=2&{page_key}=1", verdict))
    return report


def _find_endpoint(client: HttpClient, site_root: str, size: int) -> tuple[str, str, str, Any]:
    tried = []
    for path, size_key, page_key in CANDIDATES:
        url = f"{site_root}{path}"
        try:
            payload = client.get_json(url, {size_key: size, page_key: 1})
        except ClientError as err:
            tried.append(f"{path} → HTTP {err.status}")
            continue
        except Exception as err:  # coupure réseau sur une adresse : on tente la suivante
            tried.append(f"{path} → {type(err).__name__}")
            continue
        if looks_like_catalog(payload):
            log.info("API NADA trouvée : %s", url)
            return url, size_key, page_key, payload
        tried.append(f"{path} → réponse sans catalogue")
    raise RuntimeError("aucune adresse d'API NADA ne répond : " + " ; ".join(tried))


def fetch_all(cfg: dict[str, Any], client: HttpClient | None = None) -> list[dict[str, Any]]:
    client = client or HttpClient(retries=2)
    site_root = cfg["site_root"].rstrip("/")
    size = int(cfg.get("page_size", 100))
    ingested_at = utc_now()

    url, size_key, page_key, payload = _find_endpoint(client, site_root, size)
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        total, rows = parse_rows(payload)
        out.extend(normalize(r, site_root, ingested_at) for r in rows)
        if not rows or len(out) >= total or len(rows) < size:
            break
        page += 1
        payload = client.get_json(url, {size_key: size, page_key: page})
    log.info("NADA INStaD : %s études", len(out))
    return out
