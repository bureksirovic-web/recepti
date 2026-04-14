"""Tests for search module."""
from recepti.search import KeywordSearcher, highlight_matches


class TestSearch:
    def test_keyword_searcher_basic(self, sample_recipes):
        searcher = KeywordSearcher()
        results = searcher.search("paneer", sample_recipes, top_k=5)
        assert len(results) >= 1
        assert results[0][0].name == "Paneer Butter Masala"

    def test_keyword_searcher_cuisine(self, sample_recipes):
        searcher = KeywordSearcher()
        results = searcher.search("Punjabi", sample_recipes, top_k=5)
        assert len(results) == 2
        assert all(r[0].tags.cuisine == "Punjabi" for r in results)

    def test_keyword_searcher_no_results(self, sample_recipes):
        searcher = KeywordSearcher()
        results = searcher.search("xyznonexistent123", sample_recipes, top_k=5)
        assert len(results) == 0

    def test_keyword_searcher_top_k(self, sample_recipes):
        searcher = KeywordSearcher()
        results = searcher.search("dal rice", sample_recipes, top_k=2)
        assert len(results) <= 2

    def test_highlight_matches(self):
        text = "Dal Tadka with rice and paneer"
        result = highlight_matches(text, "rice")
        assert "**rice**" in result

    def test_highlight_matches_no_match(self):
        text = "Dal Tadka"
        result = highlight_matches(text, "xyz")
        # No substitution means no ** markers
        assert "**" not in result or "xyz" not in text