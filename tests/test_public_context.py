from intelligence_os.public_context import (
    PUBLIC_CONTEXT_CAPABILITIES,
    WikidataClient,
    WorldBankClient,
)
from intelligence_os.sources import get_source


def test_high_value_public_sources_registered():
    expected = {
        "gdelt",
        "world-bank",
        "eurostat",
        "oecd",
        "wikidata",
        "common-crawl",
        "openstreetmap",
        "openaddresses",
    }
    assert all(get_source(source_id) is not None for source_id in expected)
    assert expected.issubset({row["source_id"] for row in PUBLIC_CONTEXT_CAPABILITIES})


def test_world_bank_normalises_response(monkeypatch):
    def fake_get_json(url, *, params=None, timeout=20.0):
        assert "/country/GBR/indicator/NY.GDP.MKTP.CD" in url
        assert params["format"] == "json"
        return [{"page": 1}, [{"date": "2025", "value": 1.0}]]

    monkeypatch.setattr("intelligence_os.public_context._get_json", fake_get_json)
    result = WorldBankClient().indicator("GBR", "NY.GDP.MKTP.CD")
    assert result["metadata"]["page"] == 1
    assert result["observations"][0]["date"] == "2025"


def test_wikidata_search_returns_entities(monkeypatch):
    def fake_get_json(url, *, params=None, timeout=20.0):
        assert params["action"] == "wbsearchentities"
        return {"search": [{"id": "Q1", "label": "Example"}]}

    monkeypatch.setattr("intelligence_os.public_context._get_json", fake_get_json)
    result = WikidataClient().search("Example")
    assert result == [{"id": "Q1", "label": "Example"}]
