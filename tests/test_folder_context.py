"""Tests for folder context detection module."""
import sys
import os
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from photoscribe import parse_folder_name, detect_folder_context, detect_batch_folder_context, FolderContext


class TestParseFolderName:
    """Test parse_folder_name() with all 4 patterns."""

    def test_pattern1_yyyymmdd_dash(self):
        """Pattern: YYYYMMDD - Description"""
        result = parse_folder_name("20230415 - South Africa Trip")
        assert result is not None
        date_str, description = result
        assert "15" in date_str
        assert "April" in date_str
        assert "2023" in date_str
        assert description == "South Africa Trip"

    def test_pattern1_yyyymmdd_emdash(self):
        """Pattern: YYYYMMDD\u2014Description (em dash)"""
        result = parse_folder_name("20230415\u2014Johannesburg")
        assert result is not None
        date_str, description = result
        assert "April" in date_str
        assert description == "Johannesburg"

    def test_pattern1_yyyymmdd_endash(self):
        """Pattern: YYYYMMDD\u2013Description (en dash)"""
        result = parse_folder_name("20230415\u2013Cape Town")
        assert result is not None
        date_str, description = result
        assert description == "Cape Town"

    def test_pattern2_yyyy_mm_dd_dash(self):
        """Pattern: YYYY-MM-DD - Description"""
        result = parse_folder_name("2023-04-15 - London Trip")
        assert result is not None
        date_str, description = result
        assert "15" in date_str
        assert "April" in date_str
        assert "2023" in date_str
        assert description == "London Trip"

    def test_pattern2_yyyy_dot_mm_dot_dd_dash(self):
        """Pattern: YYYY.MM.DD - Description"""
        result = parse_folder_name("2023.04.15 - Berlin")
        assert result is not None
        date_str, description = result
        assert "April" in date_str
        assert description == "Berlin"

    def test_pattern3_yyyymmdd_space(self):
        """Pattern: YYYYMMDD Description (space only)"""
        result = parse_folder_name("20230415 Sydney Harbour")
        assert result is not None
        date_str, description = result
        assert "April" in date_str
        assert description == "Sydney Harbour"

    def test_pattern4_yyyy_mm_dd_space(self):
        """Pattern: YYYY-MM-DD Description (space only)"""
        result = parse_folder_name("2023-04-15 Berry Show")
        assert result is not None
        date_str, description = result
        assert "April" in date_str
        assert description == "Berry Show"

    def test_pattern4_yyyy_dot_mm_dot_dd_space(self):
        """Pattern: YYYY.MM.DD Description"""
        result = parse_folder_name("2023.12.25 Christmas Day")
        assert result is not None
        date_str, description = result
        assert "December" in date_str
        assert "25" in date_str
        assert description == "Christmas Day"

    def test_invalid_date_month_13(self):
        """Invalid dates should return None (month 13)."""
        result = parse_folder_name("20231315 - Invalid Date")
        assert result is None

    def test_invalid_date_day_32(self):
        """Invalid dates should return None (day 32)."""
        result = parse_folder_name("20230432 - Invalid Day")
        assert result is None

    def test_invalid_date_feb_30(self):
        """Invalid dates should return None (Feb 30)."""
        result = parse_folder_name("20230230 - Invalid Feb")
        assert result is None

    def test_no_match_plain_folder(self):
        """Plain folder names should return None."""
        result = parse_folder_name("My Photos")
        assert result is None

    def test_no_match_partial_date(self):
        """Partial date patterns should not match."""
        result = parse_folder_name("202304 - Incomplete")
        assert result is None

    def test_whitespace_handling(self):
        """Leading/trailing whitespace should be stripped."""
        result = parse_folder_name("  20230415 - Trimmed  ")
        assert result is not None
        _, description = result
        assert description == "Trimmed"


class TestDetectFolderContext:
    """Test detect_folder_context() with filesystem paths."""

    def test_direct_parent_match(self):
        """When the immediate parent folder matches, return its context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "20230415 - Beach Day")
            os.makedirs(folder)
            filepath = os.path.join(folder, "IMG_001.jpg")
            Path(filepath).touch()

            ctx = detect_folder_context(filepath)
            assert ctx is not None
            assert "April" in ctx.date_str
            assert ctx.location == "Beach Day"
            assert ctx.raw_folder == "20230415 - Beach Day"
            assert ctx.subfolder == ""

    def test_subfolder_walk_up(self):
        """When the file is in a subfolder, walk up to find context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "20230415 - Beach Day", "Exports")
            os.makedirs(folder)
            filepath = os.path.join(folder, "IMG_001.jpg")
            Path(filepath).touch()

            ctx = detect_folder_context(filepath)
            assert ctx is not None
            assert ctx.location == "Beach Day"
            assert ctx.subfolder == "Exports"

    def test_nested_date_folders_deepest_wins(self):
        """When multiple ancestor folders have dates, the deepest (closest) wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outer = os.path.join(tmpdir, "20230101 - New Year")
            inner = os.path.join(outer, "20230415 - Beach Day")
            os.makedirs(inner)
            filepath = os.path.join(inner, "IMG_001.jpg")
            Path(filepath).touch()

            ctx = detect_folder_context(filepath)
            assert ctx is not None
            assert ctx.location == "Beach Day"
            assert "April" in ctx.date_str

    def test_no_match(self):
        """When no matching folder is found, return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "My Photos", "Random")
            os.makedirs(folder)
            filepath = os.path.join(folder, "IMG_001.jpg")
            Path(filepath).touch()

            ctx = detect_folder_context(filepath)
            assert ctx is None

    def test_max_levels_respected(self):
        """Stop searching after max_levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create deeply nested structure where match is beyond max_levels
            folder = os.path.join(tmpdir, "20230415 - Deep", "a", "b", "c", "d", "e", "f")
            os.makedirs(folder)
            filepath = os.path.join(folder, "IMG_001.jpg")
            Path(filepath).touch()

            # With max_levels=3, should NOT find the match that is 6 levels up
            ctx = detect_folder_context(filepath, max_levels=3)
            assert ctx is None

    def test_walk_up_multiple_subfolders(self):
        """Subfolder trail should be recorded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "20230415 - Beach Day", "Day1", "RAW")
            os.makedirs(folder)
            filepath = os.path.join(folder, "IMG_001.jpg")
            Path(filepath).touch()

            ctx = detect_folder_context(filepath)
            assert ctx is not None
            assert ctx.subfolder == "Day1 / RAW"


class TestDetectBatchFolderContext:
    """Test detect_batch_folder_context() with mixed contexts."""

    def test_single_context(self):
        """All files from same folder context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "20230415 - Beach Day")
            os.makedirs(folder)
            files = []
            for i in range(5):
                fp = os.path.join(folder, f"IMG_{i:03d}.jpg")
                Path(fp).touch()
                files.append(fp)

            ctx = detect_batch_folder_context(files)
            assert ctx is not None
            assert ctx.location == "Beach Day"

    def test_mixed_contexts_majority_wins(self):
        """When files come from different contexts, the most common wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder1 = os.path.join(tmpdir, "20230415 - Beach Day")
            folder2 = os.path.join(tmpdir, "20230601 - Mountain Hike")
            os.makedirs(folder1)
            os.makedirs(folder2)

            files = []
            # 3 files from Beach Day
            for i in range(3):
                fp = os.path.join(folder1, f"IMG_{i:03d}.jpg")
                Path(fp).touch()
                files.append(fp)
            # 1 file from Mountain Hike
            fp = os.path.join(folder2, "IMG_100.jpg")
            Path(fp).touch()
            files.append(fp)

            ctx = detect_batch_folder_context(files)
            assert ctx is not None
            assert ctx.location == "Beach Day"

    def test_no_matching_files(self):
        """Return None when no files have matching folder context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = os.path.join(tmpdir, "Random Folder")
            os.makedirs(folder)
            files = []
            for i in range(3):
                fp = os.path.join(folder, f"IMG_{i:03d}.jpg")
                Path(fp).touch()
                files.append(fp)

            ctx = detect_batch_folder_context(files)
            assert ctx is None

    def test_empty_list(self):
        """Return None for an empty file list."""
        ctx = detect_batch_folder_context([])
        assert ctx is None
