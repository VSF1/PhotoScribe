"""Tests for the metadata read/write path.

Covers the code that actually touches users' files — keyword normalisation,
existing-metadata parsing, prompt construction, and end-to-end ExifTool
writes across the append/skip/replace matrix. Includes a regression test for
the v1.4.2 numeric-keyword crash ('int' object has no attribute 'lower').

The write tests are light integration tests against a real ExifTool (skipped
if it isn't available); the rest are pure units, some using a stubbed _run.
"""
import os
import sys
import json
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import photoscribe
from photoscribe import (MetadataWriter, OllamaWorker, MetadataWriteWorker,
                         PhotoMetadata, PhotoItem)


HAVE_EXIFTOOL = MetadataWriter.find_exiftool() is not None
needs_exiftool = pytest.mark.skipif(
    not HAVE_EXIFTOOL, reason="ExifTool not available"
)


class FakeResult:
    """Stand-in for subprocess.CompletedProcess."""
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def make_worker(**kw):
    kw.setdefault("photos", [])
    kw.setdefault("model", "m")
    kw.setdefault("prompt", "Describe the photo.")
    kw.setdefault("context", "")
    kw.setdefault("ollama_url", "")
    kw.setdefault("keywords_list", [])
    return OllamaWorker(**kw)


def make_jpeg(path):
    Image.new("RGB", (32, 32), (100, 140, 180)).save(str(path), "JPEG")
    return path


@pytest.fixture(scope="session")
def qapp():
    """A QApplication for tests that instantiate QThread workers."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ── _norm_keywords ────────────────────────────────────────────────

class TestNormKeywords:
    def test_none_and_empty(self):
        assert MetadataWriter._norm_keywords(None) == []
        assert MetadataWriter._norm_keywords([]) == []

    def test_coerces_numeric(self):
        # ExifTool -j returns a purely-numeric keyword (a year) as an int
        assert MetadataWriter._norm_keywords([2025, "beach"]) == ["2025", "beach"]

    def test_drops_blanks_and_none(self):
        assert MetadataWriter._norm_keywords(["a", "", "  ", None, "b"]) == ["a", "b"]

    def test_strips_whitespace(self):
        assert MetadataWriter._norm_keywords(["  sunset  "]) == ["sunset"]


# ── OllamaWorker._clean_keywords ──────────────────────────────────

class TestCleanKeywords:
    def test_numeric_keyword_from_model(self):
        # A model may emit a bare number; must not raise, must stringify
        w = make_worker()
        assert w._clean_keywords(["Sunset", 2025, "beach"]) == ["Sunset", "2025", "beach"]

    def test_drops_blanks_and_none(self):
        w = make_worker()
        assert w._clean_keywords([" ", None, "ocean"]) == ["ocean"]

    def test_case_dedup_keeps_first(self):
        w = make_worker()
        assert w._clean_keywords(["Sunset", "sunset"]) == ["Sunset"]

    def test_snaps_to_vocabulary_spelling(self):
        w = make_worker(keywords_list=["Sunset", "Beach"])
        assert w._clean_keywords(["sunset", "beach"]) == ["Sunset", "Beach"]


# ── read_existing_metadata (stubbed _run) ─────────────────────────

class TestReadExistingMetadata:
    def _stub(self, monkeypatch, entry):
        monkeypatch.setattr(
            photoscribe, "_run",
            lambda *a, **k: FakeResult(stdout=json.dumps([entry]))
        )

    def test_numeric_keyword_regression(self, monkeypatch):
        # v1.4.2: a numeric keyword arrives as a JSON int; must come back as str
        self._stub(monkeypatch, {"Subject": [2025, "beach"]})
        title, caption, kws = MetadataWriter.read_existing_metadata("x.orf.xmp")
        assert kws == ["2025", "beach"]
        assert all(isinstance(k, str) for k in kws)

    def test_single_numeric_keyword(self, monkeypatch):
        # A lone numeric value isn't a list — must still normalise to [str]
        self._stub(monkeypatch, {"Keywords": 2025})
        _, _, kws = MetadataWriter.read_existing_metadata("x.jpg")
        assert kws == ["2025"]

    def test_iptc_xmp_exif_coalesce(self, monkeypatch):
        self._stub(monkeypatch, {"ObjectName": "T", "Description": "C",
                                 "Keywords": ["a", "b"]})
        title, caption, kws = MetadataWriter.read_existing_metadata("x.jpg")
        assert (title, caption, kws) == ("T", "C", ["a", "b"])

    def test_caption_falls_back_to_exif(self, monkeypatch):
        self._stub(monkeypatch, {"ImageDescription": "from exif"})
        _, caption, _ = MetadataWriter.read_existing_metadata("x.jpg")
        assert caption == "from exif"

    def test_empty_when_nonzero_returncode(self, monkeypatch):
        monkeypatch.setattr(photoscribe, "_run",
                            lambda *a, **k: FakeResult(returncode=1))
        assert MetadataWriter.read_existing_metadata("x.jpg") == ("", "", [])


# ── OllamaWorker._build_prompt ────────────────────────────────────

class TestBuildPrompt:
    def test_anti_confabulation_always_present(self, monkeypatch):
        monkeypatch.setattr(MetadataWriter, "read_keywords", lambda f: [])
        w = make_worker(describe_people=False)
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        assert "invent" in prompt.lower()
        assert "general and correct than specific and wrong" in prompt

    def test_named_people_injected(self, monkeypatch):
        monkeypatch.setattr(MetadataWriter, "read_persons", lambda f: ["Andy"])
        monkeypatch.setattr(MetadataWriter, "read_keywords", lambda f: [])
        w = make_worker(describe_people=True)
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        assert "People named in this photo: Andy" in prompt

    def test_existing_tags_injected(self, monkeypatch):
        monkeypatch.setattr(MetadataWriter, "read_persons", lambda f: [])
        monkeypatch.setattr(MetadataWriter, "read_keywords",
                            lambda f: ["Superb Fairywren"])
        w = make_worker(describe_people=False)
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        assert "Superb Fairywren" in prompt

    def test_tags_deduped_against_persons(self, monkeypatch):
        monkeypatch.setattr(MetadataWriter, "read_persons", lambda f: ["Andy"])
        monkeypatch.setattr(MetadataWriter, "read_keywords",
                            lambda f: ["Andy", "beach"])
        w = make_worker(describe_people=True)
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        # "Andy" appears in the people line, not repeated in the subjects line
        assert "already tagged with these subjects: beach" in prompt


# ── End-to-end writes (real ExifTool) ─────────────────────────────

@needs_exiftool
class TestWriteEmbedded:
    def _kw(self, path):
        _, _, kws = MetadataWriter.read_existing_metadata(str(path))
        return kws

    def test_numeric_existing_keyword_append_regression(self, tmp_path):
        # v1.4.2: appending onto a file that already has a numeric keyword
        # used to crash with 'int' object has no attribute 'lower'
        img = make_jpeg(tmp_path / "p.jpg")
        exiftool = MetadataWriter.find_exiftool()
        photoscribe._run([exiftool, "-overwrite_original",
                          "-IPTC:Keywords=2025", "-IPTC:Keywords=beach", str(img)],
                         capture_output=True, text=True)
        meta = PhotoMetadata(title="T", caption="C", keywords=["ocean"])
        ok = MetadataWriter.write_metadata(str(img), meta, backup=False,
                                           append_keywords=True)
        assert ok is True
        kws = [k.lower() for k in self._kw(img)]
        assert "2025" in kws and "beach" in kws and "ocean" in kws

    def test_replace_keywords(self, tmp_path):
        img = make_jpeg(tmp_path / "p.jpg")
        exiftool = MetadataWriter.find_exiftool()
        photoscribe._run([exiftool, "-overwrite_original",
                          "-IPTC:Keywords=old", str(img)],
                         capture_output=True, text=True)
        meta = PhotoMetadata(title="T", caption="C", keywords=["new"])
        MetadataWriter.write_metadata(str(img), meta, backup=False,
                                      append_keywords=False)
        kws = [k.lower() for k in self._kw(img)]
        assert "new" in kws and "old" not in kws

    def test_skip_existing_preserves_title(self, tmp_path):
        img = make_jpeg(tmp_path / "p.jpg")
        exiftool = MetadataWriter.find_exiftool()
        photoscribe._run([exiftool, "-overwrite_original",
                          "-IPTC:ObjectName=Original Title", str(img)],
                         capture_output=True, text=True)
        meta = PhotoMetadata(title="AI Title", caption="C", keywords=[])
        MetadataWriter.write_metadata(str(img), meta, backup=False,
                                      skip_existing=True)
        title, _, _ = MetadataWriter.read_existing_metadata(str(img))
        assert title == "Original Title"


@needs_exiftool
class TestWriteSidecar:
    def test_numeric_existing_keyword_sidecar_regression(self, tmp_path):
        # The reported .ORF case: numeric keyword in the sidecar, append on
        raw = tmp_path / "shot.orf"
        raw.write_bytes(b"\x00" * 64)
        sidecar = tmp_path / "shot.orf.xmp"
        exiftool = MetadataWriter.find_exiftool()
        photoscribe._run([exiftool, "-overwrite_original",
                          "-XMP-dc:Subject=2025", "-XMP-dc:Subject=beach",
                          str(sidecar)], capture_output=True, text=True)
        meta = PhotoMetadata(title="T", caption="C", keywords=["ocean"])
        ok = MetadataWriter._write_sidecar(raw, meta, adobe_naming=False,
                                           append_keywords=True)
        assert ok is True
        _, _, kws = MetadataWriter.read_existing_metadata(str(sidecar))
        low = [k.lower() for k in kws]
        assert "2025" in low and "beach" in low and "ocean" in low


@needs_exiftool
class TestBatchWriteWorker:
    """Drive MetadataWriteWorker.run() (the -stay_open batch path) directly.

    run() executes synchronously here (we call it, not start()), so no event
    loop is needed — we just assert the on-disk result. The `qapp` fixture
    provides a QApplication for QThread/Signal machinery.
    """
    @pytest.fixture(autouse=True)
    def _use_qapp(self, qapp):
        pass

    def _seed(self, path, args):
        make_jpeg(path)
        photoscribe._run(
            [MetadataWriter.find_exiftool(), "-overwrite_original", *args, str(path)],
            capture_output=True, text=True)
        return path

    def _kws(self, path):
        _, _, k = MetadataWriter.read_existing_metadata(str(path))
        return sorted(k)

    def test_replace_clears_old_keywords(self, tmp_path):
        # Regression for the PR #16 fix: replace mode must clear existing
        # keywords, not accumulate them (the += bug left old ones behind).
        f = self._seed(tmp_path / "r.jpg",
                       ["-IPTC:Keywords=old1", "-IPTC:Keywords=old2"])
        MetadataWriteWorker(
            [(str(f), PhotoMetadata(title="T", caption="C",
                                    keywords=["new1", "new2"]))],
            backup=False, append_keywords=False).run()
        assert self._kws(f) == ["new1", "new2"]

    def test_append_preserves_numeric_existing(self, tmp_path):
        f = self._seed(tmp_path / "a.jpg",
                       ["-IPTC:Keywords=2025", "-IPTC:Keywords=beach"])
        MetadataWriteWorker(
            [(str(f), PhotoMetadata(title="T", caption="C",
                                    keywords=["ocean", "beach"]))],
            backup=False, append_keywords=True).run()
        assert self._kws(f) == ["2025", "beach", "ocean"]

    def test_skip_existing_preserves_title(self, tmp_path):
        f = self._seed(tmp_path / "s.jpg", ["-IPTC:ObjectName=Keep Me"])
        MetadataWriteWorker(
            [(str(f), PhotoMetadata(title="AI", caption="C", keywords=["k"]))],
            backup=False, append_keywords=True, skip_existing=True).run()
        title, _, _ = MetadataWriter.read_existing_metadata(str(f))
        assert title == "Keep Me"
