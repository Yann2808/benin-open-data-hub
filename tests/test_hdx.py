from ingestion import hdx


class FakeClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        return {"success": True, "result": self.pages.pop(0)}


PKG = {"id": "a1", "name": "benin-population", "title": "Benin - Population", "license_title": "CC BY",
       "organization": {"title": "UNFPA"}, "dataset_date": "[2020-01-01T00:00:00 TO 2020-12-31T23:59:59]",
       "last_modified": "2026-01-02T10:00:00", "num_resources": 3}


def test_fetch_all_paginates_and_normalizes():
    pages = [{"count": 3, "results": [PKG, {**PKG, "id": "a2", "name": "b2"}]},
             {"count": 3, "results": [{**PKG, "id": "a3", "name": "b3", "organization": None, "last_modified": None,
                                       "metadata_modified": "2025-05-05T00:00:00"}]}]
    client = FakeClient(pages)
    rows = hdx.fetch_all({"site": "https://hdx.example/", "group": "ben", "page_size": 2}, client=client)

    assert [c[1]["start"] for c in client.calls] == [0, 2]
    assert client.calls[0][0] == "https://hdx.example/api/3/action/package_search"
    assert client.calls[0][1]["fq"] == "groups:ben"
    assert len(rows) == 3 and set(rows[0]) == set(hdx.COLUMNS)
    assert rows[0]["url"] == "https://hdx.example/dataset/benin-population"
    assert rows[0]["organization"] == "UNFPA" and rows[0]["license"] == "CC BY" and rows[0]["num_resources"] == "3"
    assert rows[2]["organization"] is None
    assert rows[2]["last_modified"] == "2025-05-05T00:00:00"  # repli sur metadata_modified
