import duckdb
import pytest
import requests

from ingestion import common, health


class FakeResponse:
    def __init__(self, status):
        self.status_code = status
        self.closed = False

    def close(self):
        self.closed = True


def fake_get(responses):
    """Renvoie la réponse (ou lève l'exception) prévue pour chaque URL."""
    def get(url, **kwargs):
        assert kwargs["stream"] is True  # le corps n'est jamais téléchargé
        result = responses[url]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)
    return get


ENTRIES = [
    {"source": "API ok", "url": "https://ok.example/api", "official_api": True, "license": "CC BY 4.0"},
    {"source": "Site en panne", "url": "https://down.example/", "collection_policy": "catalogue seulement"},
    {"source": "Portail interdit", "url": "https://forbidden.example/robots.txt", "collection_policy": "interdite"},
    {"source": "Cloudflare", "url": "https://cf.example/api"},
]
RESPONSES = {
    "https://ok.example/api": 200,
    "https://down.example/": requests.ConnectionError("Name or service not known"),
    "https://forbidden.example/robots.txt": 200,
    "https://cf.example/api": 403,
}


def test_check_all_records_status_errors_and_metadata():
    rows = health.check_all(ENTRIES, get=fake_get(RESPONSES))
    by_source = {r["source"]: r for r in rows}

    assert all(set(r) == set(health.COLUMNS) for r in rows)
    assert len({r["tested_at"] for r in rows}) == 1  # un même horodatage par exécution
    ok = by_source["API ok"]
    assert ok["http_status"] == "200" and ok["error_message"] is None
    assert ok["official_api"] == "true" and ok["license"] == "CC BY 4.0"
    assert ok["collection_policy"] == "autorisée"  # politique par défaut
    down = by_source["Site en panne"]
    assert down["http_status"] is None and "ConnectionError" in down["error_message"]
    assert by_source["Cloudflare"]["error_message"] == "HTTP 403"
    assert by_source["Portail interdit"]["collection_policy"] == "interdite"
    assert by_source["Site en panne"]["official_api"] == "false"


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError, match="collection_policy"):
        health.check_all([{"source": "x", "url": "https://x", "collection_policy": "peut-être"}],
                         get=fake_get({"https://x": 200}))


def test_history_is_appended_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "WAREHOUSE_PATH", tmp_path / "wh.duckdb")
    get = fake_get(RESPONSES)
    assert health.append_history(health.check_all(ENTRIES, get=get), tmp_path / "absent.parquet") == 4
    assert health.append_history(health.check_all(ENTRIES, get=get), tmp_path / "absent.parquet") == 8


def test_history_is_reloaded_from_export_on_fresh_warehouse(tmp_path, monkeypatch):
    # Première exécution, puis export de l'historique (comme en CI)
    monkeypatch.setattr(common, "WAREHOUSE_PATH", tmp_path / "first.duckdb")
    health.append_history(health.check_all(ENTRIES, get=fake_get(RESPONSES)), tmp_path / "absent.parquet")
    export = tmp_path / "source_health.parquet"
    con = duckdb.connect(str(tmp_path / "first.duckdb"))
    con.execute(f"copy raw.source_health to '{export}' (format parquet)")
    con.close()

    # Entrepôt neuf : l'historique exporté est rechargé avant d'ajouter les nouveaux tests
    monkeypatch.setattr(common, "WAREHOUSE_PATH", tmp_path / "fresh.duckdb")
    assert health.append_history(health.check_all(ENTRIES, get=fake_get(RESPONSES)), export) == 8
    # Table déjà remplie : pas de second rechargement (pas de doublons)
    assert health.append_history([], export) == 8


def test_config_declares_every_project_source():
    entries = common.load_config()["source_health"]
    names = {e["source"] for e in entries}
    assert {"World Bank (API WDI)", "INStaD (catalogue NADA)", "data.gouv.bj"} <= names
    assert all(e.get("collection_policy", "autorisée") in health.POLICIES for e in entries)
    # Collecte interdite : seul /robots.txt est testé
    assert all(e["url"].endswith("/robots.txt") for e in entries if e.get("collection_policy") == "interdite")
