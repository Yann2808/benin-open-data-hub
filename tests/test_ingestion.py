import json
from pathlib import Path

import duckdb
import pytest

from ingestion import common, manual, nada, worldbank

FIX = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeClient:
    """Rejoue des réponses enregistrées dans l'ordre et garde les paramètres reçus."""

    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        return self.payloads.pop(0)


WB_CFG = {
    "base_url": "https://api.worldbank.org/v2", "focus_country": "BEN", "peer_countries": ["TGO"],
    "start_year": 2020, "end_year": 2025,
    "indicators": [{"code": "SP.POP.TOTL", "label": "Population", "theme": "Démographie", "unit": "hab", "higher_is_better": None}],
}


def test_worldbank_paginates_and_normalizes():
    client = FakeClient(fixture("wb_page1.json"), fixture("wb_page2.json"))
    rows = worldbank.fetch_indicator(client, WB_CFG, "SP.POP.TOTL")

    assert len(rows) == 3
    assert [c[1]["page"] for c in client.calls] == [1, 2]
    assert client.calls[0][0].endswith("/country/BEN;TGO/indicator/SP.POP.TOTL")
    assert client.calls[0][1]["date"] == "2020:2025"
    first = rows[0]
    assert first["country_iso3"] == "BEN" and first["year"] == "2024" and first["value"] == "14000000"
    assert first["source_last_updated"] == "2026-07-01"
    assert rows[1]["value"] is None  # valeur manquante conservée en NULL, pas en "None"
    assert set(first) == set(worldbank.COLUMNS)


def test_worldbank_api_error_is_raised():
    with pytest.raises(ValueError, match="Erreur API World Bank"):
        worldbank.parse_page(fixture("wb_error.json"))


def test_indicator_catalog_keeps_null_direction():
    cat = worldbank.indicator_catalog(WB_CFG)
    assert cat[0]["higher_is_better"] is None
    cfg = {**WB_CFG, "indicators": [{**WB_CFG["indicators"][0], "higher_is_better": False}]}
    assert worldbank.indicator_catalog(cfg)[0]["higher_is_better"] == "false"


def test_indicator_catalog_section_defaults_to_dashboard():
    assert worldbank.indicator_catalog(WB_CFG)[0]["section"] == worldbank.DEFAULT_SECTION
    cfg = {**WB_CFG, "indicators": [{**WB_CFG["indicators"][0], "section": "investir"}]}
    assert worldbank.indicator_catalog(cfg)[0]["section"] == "investir"


def test_config_sections_are_known():
    import yaml
    cfg = yaml.safe_load((FIX.parents[1] / "config" / "sources.yml").read_text(encoding="utf-8"))
    sections = {i.get("section", worldbank.DEFAULT_SECTION) for i in cfg["worldbank"]["indicators"]}
    assert sections <= set(worldbank.SECTIONS)


NADA_CFG = {"site_root": "https://nada.instad.bj", "page_size": 100}


def test_nada_parses_and_tolerates_missing_fields():
    client = FakeClient(fixture("nada_search.json"))
    rows = nada.fetch_all(NADA_CFG, client)

    assert len(rows) == 2
    assert client.calls[0][0] == "https://nada.instad.bj/index.php/api/catalog/search"
    assert rows[0]["idno"] == "BEN-INS-EMB-2024-V1.0"
    assert rows[0]["url"] == "https://nada.instad.bj/index.php/catalog/65"
    assert rows[1]["year_start"] is None and rows[1]["year_end"] is None
    assert rows[1]["data_access_type"] == "public"  # repli sur form_model
    assert set(rows[0]) == set(nada.COLUMNS)


class EndpointClient(FakeClient):
    """Simule un serveur où seules certaines adresses existent (404 ailleurs)."""

    def __init__(self, routes):
        super().__init__()
        self.routes = routes

    def get_json(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if url not in self.routes:
            raise common.ClientError(404, url)
        return self.routes[url]


def test_nada_falls_back_to_next_endpoint_on_404():
    client = EndpointClient({"https://nada.instad.bj/api/catalog/search": fixture("nada_search.json")})
    rows = nada.fetch_all(NADA_CFG, client)
    assert len(rows) == 2
    assert [c[0] for c in client.calls] == [
        "https://nada.instad.bj/index.php/api/catalog/search",
        "https://nada.instad.bj/api/catalog/search",
    ]


def test_nada_reports_every_endpoint_when_none_works():
    client = EndpointClient({"https://nada.instad.bj/api/catalog": {"status": "ok", "rows": []}})
    with pytest.raises(RuntimeError, match="aucune adresse") as exc:
        nada.fetch_all(NADA_CFG, client)
    assert "HTTP 404" in str(exc.value) and "sans catalogue" in str(exc.value)


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload, self.url = status, payload, "https://x"

    def json(self):
        return self._payload


def test_http_client_does_not_retry_client_errors(monkeypatch):
    calls = []
    client = common.HttpClient(retries=4, backoff=0)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: calls.append(1) or FakeResponse(404))
    with pytest.raises(common.ClientError):
        client.get_json("https://x")
    assert len(calls) == 1


def test_http_client_retries_server_errors(monkeypatch):
    responses = iter([FakeResponse(503), FakeResponse(200, {"ok": True})])
    client = common.HttpClient(retries=4, backoff=0)
    monkeypatch.setattr(client.session, "get", lambda *a, **k: next(responses))
    assert client.get_json("https://x") == {"ok": True}


@pytest.fixture
def tmp_warehouse(tmp_path, monkeypatch):
    wh = tmp_path / "wh.duckdb"
    monkeypatch.setattr(common, "WAREHOUSE_PATH", wh)
    monkeypatch.setattr(manual, "WAREHOUSE_PATH", wh)
    monkeypatch.setattr(manual, "ROOT", tmp_path)
    return wh


def test_load_raw_table_replaces_content(tmp_warehouse):
    common.load_raw_table("t", [{"a": "1", "b": None}], ["a", "b"])
    common.load_raw_table("t", [{"a": "2"}, {"a": "3"}], ["a", "b"])
    con = duckdb.connect(str(tmp_warehouse))
    assert con.execute("select a from raw.t order by a").fetchall() == [("2",), ("3",)]


def test_drop_demo_rows_keeps_real_rows(tmp_warehouse):
    common.load_raw_table("nada_studies", [{"idno": "DEMO-001"}, {"idno": "BEN-2018-EDS"}, {"idno": None}],
                          ["idno"])
    assert common.drop_demo_rows("nada_studies", "idno", "DEMO-") == 1
    con = duckdb.connect(str(tmp_warehouse))
    assert con.execute("select idno from raw.nada_studies order by idno").fetchall() == [("BEN-2018-EDS",), (None,)]


def test_drop_demo_rows_without_table_is_noop(tmp_warehouse):
    assert common.drop_demo_rows("absente", "idno", "DEMO-") == 0


def test_manual_loads_declared_csv(tmp_warehouse, tmp_path):
    (tmp_path / "manual").mkdir()
    (tmp_path / "manual" / "ecoles.csv").write_text("commune,effectif\nCotonou,120\nParakou,80\n", encoding="utf-8")
    cfg = {"folder": "manual", "datasets": [
        {"file": "ecoles.csv", "table": "datagouvbj_ecoles", "source_url": "https://data.gouv.bj/x", "downloaded_on": "2026-10-11"},
        {"file": "absent.csv", "table": "datagouvbj_absent"},
    ]}
    entries = manual.load_all(cfg)
    assert [e["table_name"] for e in entries] == ["datagouvbj_ecoles"]
    assert entries[0]["row_count"] == "2"


@pytest.mark.parametrize("table,file", [("Bad-Name", "x.csv"), ("ok_table", "../evil.csv")])
def test_manual_rejects_unsafe_input(tmp_warehouse, tmp_path, table, file):
    (tmp_path / "manual").mkdir(exist_ok=True)
    with pytest.raises(ValueError):
        manual.load_all({"folder": "manual", "datasets": [{"file": file, "table": table}]})
