"""Génère les jeux de démo utilisés par `python -m ingestion.run --offline`.

ATTENTION : ces valeurs sont SYNTHÉTIQUES (marche aléatoire déterministe).
Elles servent uniquement à tester le pipeline et le dashboard sans réseau.
Elles sont marquées source_last_updated = "DEMO-SYNTHETIQUE" et le dashboard
affiche un bandeau d'avertissement quand il les détecte.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

HERE = Path(__file__).parent
CFG = yaml.safe_load((HERE.parents[1] / "config" / "sources.yml").read_text(encoding="utf-8"))
WB = CFG["worldbank"]

COUNTRY_NAMES = {
    "BEN": "Benin", "TGO": "Togo", "NGA": "Nigeria", "BFA": "Burkina Faso",
    "NER": "Niger", "CIV": "Cote d'Ivoire", "SEN": "Senegal",
}
# (valeur de départ approximative, dérive annuelle, bruit)
SHAPES = {
    "SP.POP.TOTL": (6.9e6, 0.028, 0.002),
    "SP.URB.TOTL.IN.ZS": (38, 0.012, 0.004),
    "SP.DYN.LE00.IN": (53, 0.006, 0.003),
    "NY.GDP.MKTP.CD": (3.5e9, 0.06, 0.05),
    "NY.GDP.PCAP.CD": (520, 0.035, 0.05),
    "NY.GDP.MKTP.KD.ZG": (4.5, 0.0, 0.35),
    "FP.CPI.TOTL.ZG": (3.0, 0.0, 0.6),
    "IT.NET.USER.ZS": (0.3, 0.17, 0.05),
    "IT.CEL.SETS.P2": (2.0, 0.16, 0.05),
    "EG.ELC.ACCS.ZS": (22, 0.03, 0.02),
    "SE.PRM.ENRR": (85, 0.012, 0.02),
    "SL.UEM.TOTL.ZS": (2.5, 0.0, 0.08),
}
ADDITIVE = {"NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS"}
CAPPED = {"SP.URB.TOTL.IN.ZS", "IT.NET.USER.ZS", "EG.ELC.ACCS.ZS"}


def worldbank() -> list[dict]:
    rng = random.Random(2808)
    out = []
    names = {i["code"]: i["label"] for i in WB["indicators"]}
    for code, (start, drift, noise) in SHAPES.items():
        for iso in [WB["focus_country"], *WB["peer_countries"]]:
            value = start * rng.uniform(0.6, 1.6)
            for year in range(WB["start_year"], WB["end_year"] + 1):
                if code in ADDITIVE:
                    value = max(0.1, start * rng.uniform(0.4, 1.6) + rng.gauss(0, noise * start))
                else:
                    value *= 1 + drift + rng.gauss(0, noise)
                    if code in CAPPED:
                        value = min(value, 99.0)
                # dernières années parfois manquantes, comme dans la vraie API
                missing = year >= WB["end_year"] - 1 and rng.random() < 0.5
                out.append({
                    "indicator_code": code,
                    "indicator_name": names[code],
                    "country_iso3": iso,
                    "country_name": COUNTRY_NAMES[iso],
                    "year": str(year),
                    "value": None if missing else f"{value:.4f}",
                    "unit": None,
                    "obs_status": None,
                    "source_last_updated": "DEMO-SYNTHETIQUE",
                    "ingested_at": "2026-10-11T00:00:00+00:00",
                })
    return out


def nada() -> list[dict]:
    themes = [
        ("Enquête démographique et de santé", 2017, 2018),
        ("Enquête harmonisée sur les conditions de vie des ménages", 2018, 2019),
        ("Enquête sur la migration", 2024, 2024),
        ("Recensement général des entreprises", 2020, 2021),
        ("Enquête emploi et secteur informel", 2022, 2022),
    ]
    return [
        {
            "study_id": str(i),
            "idno": f"DEMO-{i:03d}",
            "title": f"[DÉMO] {title}",
            "nation": "Bénin",
            "year_start": str(y0),
            "year_end": str(y1),
            "repository": "central",
            "data_access_type": "licensed",
            "created": "2025-01-01",
            "changed": "2025-01-01",
            "url": None,
            "ingested_at": "2026-10-11T00:00:00+00:00",
        }
        for i, (title, y0, y1) in enumerate(themes, start=1)
    ]


if __name__ == "__main__":
    (HERE / "worldbank_normalized.json").write_text(json.dumps(worldbank(), ensure_ascii=False, indent=0), encoding="utf-8")
    (HERE / "nada_normalized.json").write_text(json.dumps(nada(), ensure_ascii=False, indent=1), encoding="utf-8")
    print("Fixtures de démo générées.")
