import pytest

from runestone.agent import tools as agent_tools
from runestone.agent.tools import WordPrioritisationItem


class FakeDDGS:
    """Fake DDGS class for testing news search functionality."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def news(self, query, max_results, timelimit, region):
        return []


def test_word_prioritisation_item_validation():
    """Test unicode escape decoding validation in WordPrioritisationItem."""

    # Test case 1: Double escaped unicode
    item = WordPrioritisationItem(
        word_phrase="f\\u00f6rs\\u00f6ka", translation="try", example_phrase="Kan du f\\u00f6rs\\u00f6ka?"
    )
    assert item.word_phrase == "försöka"
    assert item.example_phrase == "Kan du försöka?"

    # Test case 2: Normal string
    item = WordPrioritisationItem(word_phrase="försöka", translation="try", example_phrase="Kan du försöka?")
    assert item.word_phrase == "försöka"

    # Test case 3: JSON escaped style mixing (should be handled if it contains \u)
    # Note: if the string passed to Pydantic *is* "abc", it remains "abc".
    # If it is "a\\u0062c", it becomes "abc".
    item = WordPrioritisationItem(word_phrase="a\\u0062c", translation="x", example_phrase="y")
    assert item.word_phrase == "abc"


def test_field_descriptions():
    """Test that the translation field description has been updated."""
    fields = WordPrioritisationItem.model_fields
    translation_desc = fields["translation"].description
    assert "concise" in translation_desc.lower()
    assert "translation of the word_phrase" in translation_desc.lower()


@pytest.mark.anyio
async def test_search_news_with_dates_formats_results(monkeypatch):
    class FakeDDGSWithResults(FakeDDGS):
        def news(self, query, max_results, timelimit, region):
            return [
                {
                    "title": "Svensk ekonomi växer",
                    "body": "Tillväxten ökade under kvartalet.",
                    "url": "https://example.com/ekonomi",
                    "date": "2025-11-20T10:30:00+00:00",
                },
                {
                    "title": "Ny utbildningsreform",
                    "body": "Regeringen presenterade nya förslag.",
                    "url": "https://example.se/utbildning",
                    "date": "2025-11-21T09:00:00+00:00",
                },
            ]

    monkeypatch.setattr(agent_tools, "DDGS", FakeDDGSWithResults)

    output = await agent_tools.search_news_with_dates.ainvoke({"query": "ekonomi", "k": 2, "timelimit": "w"})

    assert output["query"] == "ekonomi"
    assert output["timelimit"] == "w"
    assert output["region"] == "se-sv"
    assert output["swedish_only"] is False
    assert output["results"][0]["title"] == "Svensk ekonomi växer"
    assert output["results"][1]["title"] == "Ny utbildningsreform"
    assert output["results"][0]["url"] == "https://example.com/ekonomi"
    assert output["results"][1]["url"] == "https://example.se/utbildning"


@pytest.mark.anyio
async def test_search_news_with_dates_swedish_only_filters(monkeypatch):
    class FakeDDGSSwedishOnly(FakeDDGS):
        def news(self, query, max_results, timelimit, region):
            return [
                {
                    "title": "Global marknad",
                    "body": "Internationella trender.",
                    "url": "https://example.com/market",
                    "date": "2025-11-22T08:00:00+00:00",
                },
                {
                    "title": "Svenska nyheter",
                    "body": "Lokala uppdateringar.",
                    "url": "https://news.example.se/sverige",
                    "date": "2025-11-22T12:00:00+00:00",
                },
            ]

    monkeypatch.setattr(agent_tools, "DDGS", FakeDDGSSwedishOnly)

    output = await agent_tools.search_news_with_dates.ainvoke({"query": "nyheter", "swedish_only": True})

    assert len(output["results"]) == 1
    assert output["results"][0]["title"] == "Svenska nyheter"


@pytest.mark.anyio
async def test_search_news_with_dates_no_results_after_filter(monkeypatch):
    class FakeDDGSNoSwedish(FakeDDGS):
        def news(self, query, max_results, timelimit, region):
            return [
                {
                    "title": "Global market",
                    "body": "International trends.",
                    "url": "https://example.com/market",
                    "date": "2025-11-22T08:00:00+00:00",
                }
            ]

    monkeypatch.setattr(agent_tools, "DDGS", FakeDDGSNoSwedish)

    output = await agent_tools.search_news_with_dates.ainvoke({"query": "marknad", "swedish_only": True})

    assert output["results"] == []


@pytest.mark.anyio
async def test_search_news_with_dates_clamps_k(monkeypatch):
    class FakeDDGSClampsK(FakeDDGS):
        def news(self, query, max_results, timelimit, region):
            assert max_results == 10
            return []

    monkeypatch.setattr(agent_tools, "DDGS", FakeDDGSClampsK)

    output = await agent_tools.search_news_with_dates.ainvoke({"query": "ekonomi", "k": 999})

    assert output["results"] == []
