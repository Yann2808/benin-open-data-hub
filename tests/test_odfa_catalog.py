import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import odfa_catalog as oc  # noqa: E402


def test_humanize_title_restores_survey_and_elisions():
    assert oc.humanize_title("eds-prévalence-et-traitement-de-l-ira") == "EDS — Prévalence et traitement de l'ira"
    assert oc.humanize_title("ehcvm-indicateurs-de-l-emploi") == "EHCVM — Indicateurs de l'emploi"
    assert oc.humanize_title("mines-performance-du-secteur") == "Mines performance du secteur"
    assert oc.humanize_title("eri-esi-secteur-informel") == "ERI-ESI — Secteur informel"
    assert oc.humanize_title("statistiques-agricoles-benin") == "Statistiques agricoles Bénin"
    assert oc.humanize_title("") == ""


def test_humanize_title_marks_truncated_slugs():
    slug = "rge-" + "a" * 96
    assert len(slug) == oc.SLUG_MAX
    assert oc.humanize_title(slug).endswith("…")


def test_estimate_theme_prefers_survey_over_keywords():
    # « inscription » pointerait vers Éducation : l'enquête RGE l'emporte
    assert oc.estimate_theme("rge-inscription-au-registre-du-commerce", "INSAE") == "Entreprises et commerce"
    assert oc.estimate_theme("agvsa-securite-alimentaire", "INSAE") == "Agriculture et alimentation"
    # mots-clés courts en mots entiers : « eau » ne doit pas matcher « niveau »
    assert oc.estimate_theme("niveau-de-vie", "Ministère en charge du commerce") == "Entreprises et commerce"
    assert oc.estimate_theme("approvisionnement-en-eau", "SONEB") == "Infrastructures et énergie"
    assert oc.estimate_theme("sans-indice", "") == oc.OTHER_THEME


def test_producer_family_and_freshness():
    assert oc.producer_family("INSAE_Enquête Emploi du Temps") == "INStaD"
    assert oc.producer_family("Ministère en charge de la santé") == "Ministères"
    assert oc.producer_family("National Institute of Statistics of Rwanda") == "International"
    assert oc.producer_family("Port Autonome de Cotonou") == "Agences publiques"
    assert oc.freshness_bucket(100) == "moins d'un an"
    assert oc.freshness_bucket(800) == "1 à 3 ans"
    assert oc.freshness_bucket(2000) == "plus de 3 ans"
    assert oc.freshness_bucket(None) == "inconnue"


def test_enrich_adds_columns_without_touching_source():
    raw = pd.DataFrame({"title": ["eds-mortalite"], "source_name": ["INSAE"], "days_since_update": [10]})
    out = oc.enrich(raw)
    assert list(raw.columns) == ["title", "source_name", "days_since_update"]
    assert out.loc[0, ["title_fr", "survey", "theme", "producer", "freshness"]].tolist() == [
        "EDS — Mortalite", "EDS", "Santé", "INStaD", "moins d'un an"]


def test_update_period_buckets_by_year_of_last_update():
    assert oc.update_period(pd.Timestamp("2024-01-01")) == "depuis 2024"
    assert oc.update_period(pd.Timestamp("2023-12-31 23:00")) == "2020 à 2023"
    assert oc.update_period(pd.Timestamp("2020-01-01")) == "2020 à 2023"
    assert oc.update_period(pd.Timestamp("2019-12-31")) == "avant 2020"
    assert oc.update_period(None) == "date inconnue"
    assert oc.update_period(pd.NaT) == "date inconnue"


def test_age_table_counts_per_producer_with_total():
    df = pd.DataFrame({
        "producer": ["INStaD", "INStaD", "Ministères", "INStaD"],
        "last_updated_on": pd.to_datetime(["2025-03-01", "2018-06-01", "2021-01-01", "2024-02-02"]),
    })
    table = oc.age_table(df, "producer")
    assert list(table.columns) == ["depuis 2024", "2020 à 2023", "avant 2020", "total"]  # pas de « date inconnue » vide
    assert table.loc["INStaD"].tolist() == [2, 0, 1, 3]
    assert table.loc["Ministères"].tolist() == [0, 1, 0, 1]
    assert table.index[0] == "INStaD"  # trié par total décroissant
