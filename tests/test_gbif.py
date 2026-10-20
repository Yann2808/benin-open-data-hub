from ingestion import gbif


class FakeClient:
    def __init__(self):
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        if url.endswith("/occurrence/search"):
            return {"count": 30, "facets": [{"field": "YEAR", "counts": [{"name": "2019", "count": 20},
                                                                       {"name": "2013", "count": 10}]}]}
        if url.endswith("/dataset"):
            if params["offset"] == 0:
                return {"endOfRecords": False, "results": [{"created": "2019-01-11T15:34:17+00:00"},
                                                           {"created": "2019-05-01T00:00:00+00:00"}]}
            return {"endOfRecords": True, "results": [{"created": "2024-03-02T00:00:00+00:00"}, {"created": None}]}
        raise AssertionError(url)


def test_fetch_all_counts_occurrences_and_datasets_per_year():
    client = FakeClient()
    rows = gbif.fetch_all({"api_base": "https://api.gbif.example/v1/", "country": "BJ"}, client=client)

    occ = {r["year"]: r["value"] for r in rows if r["metric"] == "occurrences"}
    ds = {r["year"]: r["value"] for r in rows if r["metric"] == "jeux publiés"}
    assert occ == {"2013": "10", "2019": "20"}
    assert ds == {"2019": "2", "2024": "1"}  # jeu sans date ignoré, pagination suivie
    assert all(set(r) == set(gbif.COLUMNS) for r in rows)
    assert client.calls[0][1]["country"] == "BJ" and client.calls[0][1]["limit"] == 0
    assert [c[1]["offset"] for c in client.calls[1:]] == [0, 200]  # pages de 200
