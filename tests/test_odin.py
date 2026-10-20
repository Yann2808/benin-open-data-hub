from ingestion import odin


class FakeClient:
    def __init__(self, scores):
        self.scores = scores  # {(use_id, country_id): payload}
        self.posts = []

    def get_json(self, url, params=None):
        if url.endswith("/GetLiveYears"):
            return [{"useId": 8, "year": 2022, "isLive": True}, {"useId": 9, "year": 2024, "isLive": True},
                    {"useId": 10, "year": 2026, "isLive": False}]
        if url.endswith("/GetCountries"):
            return [{"countryCode": "BEN", "countryId": 42}, {"countryCode": "TGO", "countryId": 58}]
        raise AssertionError(url)

    def post_json(self, url, body=None):
        self.posts.append((url, body))
        use_id, country_id = map(int, url.rsplit("/", 2)[-2:])
        return self.scores.get((use_id, country_id), {"countryTotalPerc": None, "countryName": "?"})


CFG = {"api_base": "https://odin.example/api/client/", "pause_seconds": 0}


def test_fetch_all_one_row_per_country_and_live_edition():
    scores = {
        (9, 42): {"countryTotalPerc": "60.5", "coverageScore": "50.0", "opennessScore": "70.1",
                  "rankWorldTotal": "80", "totalCountries": "190"},
        (8, 42): {"countryTotalPerc": "55", "coverageScore": "45", "opennessScore": "65",
                  "rankWorldTotal": "90", "totalCountries": "190"},
    }
    client = FakeClient(scores)
    rows = odin.fetch_all(CFG, ["BEN", "TGO", "XXX"], client=client, sleep=lambda s: None)

    # Éditions non publiées (isLive false) ignorées ; pays inconnu ignoré
    assert len(client.posts) == 4
    assert client.posts[0] == ("https://odin.example/api/client/GetCountryScore/8/42", {})
    # Togo non évalué dans ce jeu de test : aucune ligne inventée
    assert [(r["country_iso3"], r["edition_year"]) for r in rows] == [("BEN", "2022"), ("BEN", "2024")]
    latest = rows[1]
    assert set(latest) == set(odin.COLUMNS)
    assert latest["overall_score"] == "60.5" and latest["openness_score"] == "70.1"
    assert latest["rank_world"] == "80" and latest["n_countries_ranked"] == "190"


def test_normalize_score_returns_none_without_score():
    assert odin.normalize_score({"countryTotalPerc": None}, "BEN", 2024, "t") is None
    assert odin.normalize_score({"countryTotalPerc": ""}, "BEN", 2024, "t") is None
