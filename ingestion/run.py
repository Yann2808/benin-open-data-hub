"""Point d'entrée de l'ingestion.

    python -m ingestion.run              # collecte réelle (World Bank + INStaD + fichiers manuels)
    python -m ingestion.run --offline    # charge les jeux de test (démo sans réseau)
    python -m ingestion.run --only worldbank
    python -m ingestion.run --only health   # baromètre de l'accès aux sources seulement
    python -m ingestion.run --only odfa  # collecte complète d'Open Data for Africa (longue, reprend où elle s'est arrêtée)
    python -m ingestion.run --only odfa --refresh   # recollecte aussi les jeux déjà présents

Sans --only odfa, seul le catalogue Open Data for Africa est rafraîchi (rapide) ;
les données déjà collectées sont rechargées depuis data/raw/odfa/.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import gbif, hdx, health, manual, nada, odfa, odin, worldbank
from .common import ROOT, drop_demo_rows, ensure_raw_table, load_config, load_raw_table, upsert_raw_table, write_snapshot

FIXTURES = ROOT / "tests" / "fixtures"
# Marqueurs des données synthétiques de `make demo` (voir tests/fixtures/make_fixtures.py)
DEMO_MARKERS = {
    "wb_observations": ("source_last_updated", "DEMO-SYNTHETIQUE"),
    "nada_studies": ("idno", "DEMO-"),
}
SOURCES = ("worldbank", "nada", "manual", "odfa", "odin", "gbif", "hdx", "health")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bénin Open Data Hub — ingestion")
    parser.add_argument("--offline", action="store_true", help="utiliser les fixtures de test au lieu des API")
    parser.add_argument("--only", choices=SOURCES, action="append", help="limiter à certaines sources")
    parser.add_argument("--refresh", action="store_true", help="odfa : recollecter aussi les jeux déjà présents")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    log = logging.getLogger("ingestion")

    cfg = load_config()
    selected = args.only or list(SOURCES)
    failures: list[str] = []

    # Toutes les tables brutes existent toujours, même pour une source non
    # sélectionnée ou en panne : dbt peut tourner quel que soit le scénario.
    ensure_raw_table("wb_observations", worldbank.COLUMNS)
    ensure_raw_table("nada_studies", nada.COLUMNS)
    ensure_raw_table("manual_registry", manual.REGISTRY_COLUMNS)
    ensure_raw_table("odfa_datasets", odfa.DATASET_COLUMNS)
    ensure_raw_table("odfa_fetch_log", odfa.LOG_COLUMNS)
    ensure_raw_table("source_health", health.COLUMNS)
    ensure_raw_table("wb_indicator_meta", worldbank.META_COLUMNS)
    ensure_raw_table("odin_scores", odin.COLUMNS)
    ensure_raw_table("gbif_yearly", gbif.COLUMNS)
    ensure_raw_table("hdx_datasets", hdx.COLUMNS)

    # Collecte réelle : on retire d'abord les restes d'un `make demo`, pour que
    # « dernière collecte conservée » ne mélange jamais démo et vraies données.
    if not args.offline:
        for table, (column, marker) in DEMO_MARKERS.items():
            n = drop_demo_rows(table, column, marker)
            if n:
                log.info("raw.%s : %s lignes de démo supprimées", table, n)

    # Le catalogue des indicateurs vient de la config : toujours rechargé.
    load_raw_table("wb_indicator_catalog", worldbank.indicator_catalog(cfg["worldbank"]), worldbank.CATALOG_COLUMNS)

    if "worldbank" in selected:
        try:
            records = _offline("worldbank") if args.offline else worldbank.fetch_all(cfg["worldbank"])
            if not args.offline:
                write_snapshot("worldbank", records)
            n = load_raw_table("wb_observations", records, worldbank.COLUMNS)
            log.info("raw.wb_observations : %s lignes", n)
        except Exception as err:  # une source en panne ne bloque pas les autres
            log.error("World Bank en échec : %s — dernière collecte conservée", err)
            ensure_raw_table("wb_observations", worldbank.COLUMNS)
            failures.append("worldbank")

    # Définitions officielles des indicateurs : jamais en démo (on n'invente pas de
    # définition), et un échec garde les précédentes sans bloquer la collecte.
    if "worldbank" in selected and not args.offline:
        try:
            n = load_raw_table("wb_indicator_meta", worldbank.fetch_metadata(cfg["worldbank"]), worldbank.META_COLUMNS)
            log.info("raw.wb_indicator_meta : %s lignes", n)
        except Exception as err:  # noqa: BLE001
            log.warning("Définitions World Bank indisponibles : %s — précédentes conservées", err)

    if "nada" in selected:
        try:
            records = _offline("nada") if args.offline else nada.fetch_all(cfg["nada"])
            if not args.offline:
                write_snapshot("nada", records)
            n = load_raw_table("nada_studies", records, nada.COLUMNS)
            log.info("raw.nada_studies : %s lignes", n)
        except Exception as err:
            # Source optionnelle : signalée, mais n'arrête pas le pipeline.
            log.warning("Catalogue INStaD indisponible : %s — dernière collecte conservée. "
                        "Lance `make diagnose` pour le détail.", err)
            ensure_raw_table("nada_studies", nada.COLUMNS)

    if "manual" in selected:
        entries = manual.load_all(cfg["manual"])
        load_raw_table("manual_registry", entries, manual.REGISTRY_COLUMNS)

    if "odfa" in selected and not args.offline:
        _run_odfa(cfg["odfa"], collect_data=bool(args.only and "odfa" in args.only), refresh=args.refresh, log=log)
    if not args.offline:
        log.info("raw.odfa_observations : %s lignes", odfa.load_observations())
    else:
        odfa.load_observations(FIXTURES / "odfa_empty")  # table vide en démo

    # Sources optionnelles ajoutées après l'audit du 2026-10-20 (docs/audit_sources.md) :
    # jamais en démo (on n'invente pas de valeurs), un échec garde la dernière collecte.
    if "odin" in selected and not args.offline:
        try:
            countries = [cfg["worldbank"]["focus_country"], *cfg["worldbank"]["peer_countries"]]
            n = load_raw_table("odin_scores", odin.fetch_all(cfg["odin"], countries), odin.COLUMNS)
            log.info("raw.odin_scores : %s lignes", n)
        except Exception as err:  # noqa: BLE001
            log.warning("ODIN indisponible : %s — dernière collecte conservée", err)

    if "gbif" in selected and not args.offline:
        try:
            n = load_raw_table("gbif_yearly", gbif.fetch_all(cfg["gbif"]), gbif.COLUMNS)
            log.info("raw.gbif_yearly : %s lignes", n)
        except Exception as err:  # noqa: BLE001
            log.warning("GBIF indisponible : %s — dernière collecte conservée", err)

    if "hdx" in selected and not args.offline:
        try:
            n = load_raw_table("hdx_datasets", hdx.fetch_all(cfg["hdx"]), hdx.COLUMNS)
            log.info("raw.hdx_datasets : %s lignes", n)
        except Exception as err:  # noqa: BLE001
            log.warning("HDX indisponible : %s — dernière collecte conservée", err)

    # Baromètre de l'accès aux données : jamais en démo (pas de réseau), jamais bloquant.
    if "health" in selected and not args.offline:
        try:
            n = health.append_history(health.check_all(cfg.get("source_health") or []))
            log.info("raw.source_health : %s tests au total", n)
        except Exception as err:  # noqa: BLE001
            log.warning("Baromètre de l'accès aux données en échec : %s", err)

    # Seule la World Bank est indispensable : sans elle, le dashboard serait vide.
    if failures:
        log.error("Source indispensable en échec : %s", ", ".join(failures))
        return 1
    return 0


def _run_odfa(cfg: dict, collect_data: bool, refresh: bool, log: logging.Logger) -> None:
    """Source optionnelle : une panne est signalée sans arrêter le pipeline."""
    try:
        datasets = odfa.list_datasets(cfg)
        load_raw_table("odfa_datasets", datasets, odfa.DATASET_COLUMNS)
    except Exception as err:  # noqa: BLE001
        log.warning("Catalogue Open Data for Africa indisponible : %s — dernière collecte conservée", err)
        return
    if not collect_data:
        log.info("Catalogue Open Data for Africa à jour. Collecte des données : make odfa")
        return
    journal = odfa.fetch_datasets(odfa.select_datasets(datasets, cfg), cfg, refresh=refresh)
    upsert_raw_table("odfa_fetch_log", journal, odfa.LOG_COLUMNS, key="dataset_id")
    ok = sum(j["status"] == "ok" for j in journal)
    log.info("Open Data for Africa : %s jeux collectés, %s en échec", ok, len(journal) - ok)


def _offline(source: str) -> list[dict]:
    path = FIXTURES / f"{source}_normalized.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
