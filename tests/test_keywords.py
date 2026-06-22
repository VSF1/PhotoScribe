"""Tests for keyword deduplication."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from photoscribe import deduplicate_keywords


class TestDeduplicateKeywords:
    def test_empty_list(self):
        assert deduplicate_keywords([]) == []

    def test_no_duplicates(self):
        result = deduplicate_keywords(["sunset", "beach", "ocean"])
        assert result == ["sunset", "beach", "ocean"]

    def test_plural_s(self):
        result = deduplicate_keywords(["sunset", "sunsets"])
        assert result == ["sunset"]

    def test_plural_es(self):
        result = deduplicate_keywords(["beach", "beaches"])
        assert result == ["beach"]

    def test_plural_ies(self):
        result = deduplicate_keywords(["berry", "berries"])
        assert result == ["berry"]

    def test_case_variants(self):
        result = deduplicate_keywords(["Sunset", "sunset"])
        assert result == ["Sunset"]

    def test_preserves_order(self):
        result = deduplicate_keywords(["ocean", "waves", "oceans", "beach"])
        assert result == ["ocean", "waves", "beach"]

    def test_keeps_first_occurrence(self):
        result = deduplicate_keywords(["Trees", "trees", "tree"])
        assert result == ["Trees"]

    def test_short_words_not_affected(self):
        # "ss" ending shouldn't be stripped
        result = deduplicate_keywords(["grass", "glass"])
        assert "grass" in result
        assert "glass" in result

    def test_mixed_real_keywords(self):
        keywords = ["landscape", "landscapes", "Mountain", "mountain",
                    "sunset", "golden hour", "tree", "trees"]
        result = deduplicate_keywords(keywords)
        assert "landscape" in result
        assert "landscapes" not in result
        assert "Mountain" in result
        assert "mountain" not in result
        assert "tree" in result
        assert "trees" not in result
        assert "golden hour" in result
