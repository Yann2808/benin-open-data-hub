"""Point d'entrée de l'ingestion.

    python -m ingestion.run              # collecte réelle (World Bank + INStaD + fichiers manuels)
    python -m ingestion.run --offline    # charge les jeux de test (démo sans réseau)
    python -m ingestion.run --only worldbank
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import manual, nada, worldbank
from .common import ROOT, ensure_raw_table, load_config, load_raw_table, write_snapshot

FIXTURES = ROOT / "tests" / "fixtures"
SOURCES = ("worldbank", "nada", "manual")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bénin Open Data Hub — ingestion")
    parser.add_argument("--offline", action="store_true", help="utiliser les fixtures de test au lieu des API")
    parser.add_argument("--only", choices=SOURCES, action="append", help="limiter à certaines sources")
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

    # Seule la World Bank est indispensable : sans elle, le dashboard serait vide.
    if failures:
        log.error("Source indispensable en échec : %s", ", ".join(failures))
        return 1
    return 0


def _offline(source: str) -> list[dict]:
    path = FIXTURES / f"{source}_normalized.json"
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
