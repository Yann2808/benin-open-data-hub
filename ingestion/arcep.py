"""Prototype EXPÉRIMENTAL : extraction des tableaux de bord Internet de l'ARCEP Bénin (PDF).

Statut : non branché sur `make run`, rien n'est chargé dans l'entrepôt ni affiché.
Les mentions légales de l'ARCEP soumettent toute reproduction à un accord écrit
(voir docs/audit_sources.md) : tant qu'il n'est pas obtenu, ce script ne sert
qu'à vérifier, en local, que l'extraction est fiable.

Le PDF est téléchargé À LA MAIN depuis https://arcep.bj/internet/ (pas de collecte
automatique), puis :

    python -m ingestion.arcep chemin/vers/Observatoire_Internet_T1_2026_TaB.pdf

Chaque valeur garde sa provenance (fichier, page, tableau, ligne, période) et le
statut « à vérifier ». Sortie : data/raw/arcep/<fichier>.jsonl (dossier non versionné).
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from .common import RAW_DIR, utc_now

log = logging.getLogger("ingestion.arcep")

COLUMNS = ["source_file", "page", "table", "row_label", "period", "value_raw", "value", "unit",
           "status", "extracted_at"]
PERIOD = re.compile(r"\bT[1-4]_\d{4}\b")
TABLE = re.compile(r"^\s*Tableau\s+\d+\s*:\s*(.+?)\s*$")
END = re.compile(r"^\s*(Source\s*:|Graphique\s+\d+|Tableau\s+\d+)")
# Une cellule : nombre avec espaces de milliers (« 36 475 »), décimal à virgule, pourcentage, ou « - »
CELL = re.compile(r"^(?:-|\d{1,3}(?:[   ]\d{3})*(?:,\d+)?\s*%?|\d+(?:,\d+)?\s*%?)$")


def parse_value(raw: str) -> tuple[float | None, str]:
    """« 36 475 » → (36475, nombre) ; « 0,35% » → (0.35, %) ; « - » → (None, nombre)."""
    raw = raw.strip()
    if raw == "-":
        return None, "nombre"
    unit = "%" if raw.endswith("%") else "nombre"
    num = re.sub(r"[   %]", "", raw).replace(",", ".")
    return float(num), unit


def parse_page_text(text: str, page: int, source_file: str, extracted_at: str) -> tuple[list[dict], list[str]]:
    """Lit les tableaux d'une page (texte en mise en page conservée). Renvoie les valeurs
    et les lignes qui n'ont pas pu être lues (à reprendre à la main)."""
    records: list[dict[str, Any]] = []
    unread: list[str] = []
    table, periods = None, []
    for line in text.splitlines():
        if m := TABLE.match(line):
            table, periods = m.group(1), []
            continue
        if table is None:
            continue
        if not periods:
            periods = PERIOD.findall(line)
            continue
        if END.match(line):
            table, periods = None, []
            continue
        cells = [c for c in re.split(r"\s{2,}", line.strip()) if c]
        if len(cells) < 2:
            # Nombres sans libellé (ligne repliée, colonnes collées) : signalés, jamais devinés
            if cells and re.search(r"\d", cells[0]):
                unread.append(f"page {page}, {table} : {line.strip()}")
            continue
        label, values = cells[0], cells[1:]
        if len(values) != len(periods) or not all(CELL.match(v) for v in values):
            unread.append(f"page {page}, {table} : {line.strip()}")
            continue
        for period, raw in zip(periods, values):
            value, unit = parse_value(raw)
            records.append({
                "source_file": source_file, "page": page, "table": table, "row_label": label,
                "period": period, "value_raw": raw, "value": value, "unit": unit,
                "status": "à vérifier", "extracted_at": extracted_at,
            })
    return records, unread


def extract(pdf_path: Path) -> tuple[list[dict], list[str]]:
    from pypdf import PdfReader  # import tardif : dépendance du seul prototype

    extracted_at = utc_now()
    records, unread = [], []
    for i, page in enumerate(PdfReader(str(pdf_path)).pages, start=1):
        r, u = parse_page_text(page.extract_text(extraction_mode="layout"), i, pdf_path.name, extracted_at)
        records += r
        unread += u
    return records, unread


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(__doc__)
        return 2
    pdf = Path(args[0])
    records, unread = extract(pdf)
    out = RAW_DIR / "arcep" / f"{pdf.stem}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("%s valeurs extraites (statut « à vérifier ») → %s", len(records), out)
    for line in unread:
        log.warning("Ligne non lue, à reprendre à la main : %s", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
