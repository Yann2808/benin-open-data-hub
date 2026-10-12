import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from ingestion import common, odfa

FIX = Path(__file__).parent / "fixtures"
CFG = {"host": "benin.opendataforafrica.org", "pause_seconds": 0}


class FakeClient:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get_json(self, url, params=None):
        self.calls.append(url)
        return self.payload


def knoema_like_frame():
    """Reproduit la forme renvoyée par knoema.get : index de dates, colonnes
    MultiIndex nommées par dimension, avec la fréquence en dernier niveau."""
    cols = pd.MultiIndex.from_tuples(
        [("Alibori", "Maïs", "A"), ("Borgou", "Maïs", "A")],
        names=["Département", "Culture", "Frequency"],
    )
    idx = pd.DatetimeIndex(["2025-01-01", "2026-01-01"], name="Date")
    return pd.DataFrame([[100.0, 200.0], [110.0, np.nan]], index=idx, columns=cols)


def test_list_datasets_normalizes_catalog():
    payload = json.loads((FIX / "odfa_meta_dataset.json").read_text(encoding="utf-8"))
    client = FakeClient(payload)
    rows = odfa.list_datasets(CFG, client)

    assert client.calls == ["https://benin.opendataforafrica.org/api/1.0/meta/dataset"]
    assert [r["dataset_id"] for r in rows] == ["vtklyze", "agri2026"]  # l'entrée sans id est ignorée
    sdg, agri = rows
    assert sdg["license"] == "Public Domain"          # repli sur la licence de la source
    assert sdg["terms_url"] == "https://unstats.un.org/terms"
    assert sdg["source_verified"] == "True"
    assert agri["license"] == "Open"
    assert json.loads(agri["dimensions"]) == ["Département", "Culture"]
    assert agri["url"] == "https://benin.opendataforafrica.org/agri2026"
    assert set(sdg) == set(odfa.DATASET_COLUMNS)


def test_select_datasets_include_exclude_limit():
    ds = [{"dataset_id": i} for i in "abcd"]
    assert [d["dataset_id"] for d in odfa.select_datasets(ds, {"exclude": ["b"], "max_datasets": 2})] == ["a", "c"]
    assert [d["dataset_id"] for d in odfa.select_datasets(ds, {"include": ["d"]})] == ["d"]


def test_frame_to_long_keeps_dimensions_and_drops_missing():
    long = odfa.frame_to_long(knoema_like_frame(), "agri2026", "2026-10-11T00:00:00+00:00")

    assert list(long.columns) == odfa.OBS_COLUMNS
    assert len(long) == 3  # la valeur manquante de Borgou 2026 est écartée
    first = long.iloc[0]
    assert json.loads(first["dimensions"]) == {"Département": "Alibori", "Culture": "Maïs"}
    assert first["frequency"] == "A" and first["date"] == "2025-01-01" and float(first["value"]) == 100.0
    assert long["series_key"].nunique() == 2


def test_frame_to_long_handles_simple_columns_and_empty():
    df = pd.DataFrame({"Taux": [1.5]}, index=pd.DatetimeIndex(["2024-01-01"]))
    long = odfa.frame_to_long(df, "x", "t")
    assert json.loads(long.iloc[0]["dimensions"]) == {"series": "Taux"}
    assert odfa.frame_to_long(pd.DataFrame(), "x", "t").empty


def test_fetch_is_resumable_and_isolates_failures(tmp_path):
    datasets = [{"dataset_id": i, "title": i} for i in ("ok1", "boom", "ok2")]
    calls = []

    def fetcher(ds_id):
        calls.append(ds_id)
        if ds_id == "boom":
            raise RuntimeError("quota dépassé")
        return knoema_like_frame()

    journal = odfa.fetch_datasets(datasets, CFG, fetcher=fetcher, out_dir=tmp_path, sleep=lambda s: None)
    assert [j["status"] for j in journal] == ["ok", "échec", "ok"]
    assert "quota dépassé" in journal[1]["error"]
    assert sorted(p.name for p in tmp_path.glob("*.parquet")) == ["ok1.parquet", "ok2.parquet"]

    # Relance : seuls les jeux absents sont recollectés
    calls.clear()
    odfa.fetch_datasets(datasets, CFG, fetcher=fetcher, out_dir=tmp_path, sleep=lambda s: None)
    assert calls == ["boom"]
    # --refresh : tout est recollecté
    calls.clear()
    odfa.fetch_datasets(datasets, CFG, refresh=True, fetcher=fetcher, out_dir=tmp_path, sleep=lambda s: None)
    assert calls == ["ok1", "boom", "ok2"]


def test_load_observations_unions_files(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WAREHOUSE_PATH", tmp_path / "wh.duckdb")
    out = tmp_path / "odfa"
    assert odfa.load_observations(out) == 0  # dossier absent : table vide créée
    odfa.fetch_datasets([{"dataset_id": "a", "title": "a"}, {"dataset_id": "b", "title": "b"}], CFG,
                        fetcher=lambda _: knoema_like_frame(), out_dir=out, sleep=lambda s: None)
    assert odfa.load_observations(out) == 6
    con = duckdb.connect(str(tmp_path / "wh.duckdb"))
    assert con.execute("select count(distinct dataset_id) from raw.odfa_observations").fetchone()[0] == 2


def test_upsert_keeps_previous_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WAREHOUSE_PATH", tmp_path / "wh.duckdb")
    cols = odfa.LOG_COLUMNS
    common.upsert_raw_table("log", [{"dataset_id": "a", "status": "échec"}, {"dataset_id": "b", "status": "ok"}], cols, "dataset_id")
    common.upsert_raw_table("log", [{"dataset_id": "a", "status": "ok"}], cols, "dataset_id")
    con = duckdb.connect(str(tmp_path / "wh.duckdb"))
    assert con.execute("select dataset_id, status from raw.log order by 1").fetchall() == [("a", "ok"), ("b", "ok")]
