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


# ── OllamaWorker._parse_response (tolerant JSON) ──────────────────

class TestParseResponse:
    def w(self):
        return OllamaWorker(photos=[], model="m", prompt="p", context="",
                            ollama_url="", keywords_list=[])

    def test_clean_json(self):
        d = self.w()._parse_response(
            '{"title":"A","caption":"B","keywords":["x","y"]}')
        assert d == {"title": "A", "caption": "B", "keywords": ["x", "y"]}

    def test_fenced_block(self):
        d = self.w()._parse_response(
            '```json\n{"title":"A","caption":"B","keywords":["x"]}\n```')
        assert d["title"] == "A"

    def test_reasoning_preamble_with_stray_brace(self):
        # A 'thinking' dump with a stray {brace} before the real object
        txt = ('Let me think. The image {shows} gulls.\nJSON:\n'
               '{"title":"Gulls","caption":"On a beach.","keywords":["gulls"]}\n'
               'Hope that helps!')
        d = self.w()._parse_response(txt)
        assert d["title"] == "Gulls" and d["keywords"] == ["gulls"]

    def test_trailing_commas(self):
        d = self.w()._parse_response(
            '{"title":"A","caption":"B","keywords":["x","y",],}')
        assert d["keywords"] == ["x", "y"]

    def test_single_quoted_dict(self):
        d = self.w()._parse_response(
            "{'title':'A','caption':'B','keywords':['x']}")
        assert d["title"] == "A"

    def test_smart_quotes(self):
        d = self.w()._parse_response(
            '{“title”:“A”,“caption”:“B”,'
            '“keywords”:[“x”]}')
        assert d["title"] == "A"

    def test_line_comments(self):
        d = self.w()._parse_response(
            '{\n"title":"A", // note\n"caption":"B",\n"keywords":["x"]\n}')
        assert d["caption"] == "B"

    def test_unquoted_keyword_array(self):
        d = self.w()._parse_response(
            '{"title":"A","caption":"B","keywords":[gulls, beach]}')
        assert d["keywords"] == ["gulls", "beach"]

    def test_brackets_in_caption_not_mangled(self):
        # Valid JSON with brackets inside a string must parse untouched — the
        # aggressive bare-array repair must not run when strict parse succeeds.
        d = self.w()._parse_response(
            '{"title":"A","caption":"Shot [at dusk] here","keywords":["x"]}')
        assert d["caption"] == "Shot [at dusk] here"

    def test_unrecoverable_returns_none(self):
        assert self.w()._parse_response("total gibberish, no json") is None
        assert self.w()._parse_response("") is None


# ── Structured output on the backend calls (mocked network) ───────

class _Resp:
    def __init__(self, status=200, text="", payload=None):
        self.status_code = status
        self.text = text
        self._payload = payload or {"choices": [{"message": {"content": "{}"}}],
                                    "message": {"content": "{}"}}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class TestStructuredOutput:
    def _worker(self, backend):
        return OllamaWorker(photos=[], model="m", prompt="p", context="",
                            ollama_url="http://x", keywords_list=[],
                            backend=backend)

    def test_openai_requests_json_schema(self, monkeypatch):
        seen = []
        monkeypatch.setattr(photoscribe.requests, "post",
                            lambda url, json=None, timeout=None: (seen.append(json), _Resp())[1])
        self._worker("openai")._call_openai("imgb64", "prompt")
        rf = seen[0].get("response_format")
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["schema"]["required"] == ["title", "caption", "keywords"]

    def test_openai_falls_back_when_unsupported(self, monkeypatch):
        seen = []

        def post(url, json=None, timeout=None):
            seen.append(json)
            if "response_format" in json:
                return _Resp(status=400, text="'response_format.type' must be json_schema")
            return _Resp()
        monkeypatch.setattr(photoscribe.requests, "post", post)
        self._worker("openai")._call_openai("img", "p")
        assert len(seen) == 2 and "response_format" not in seen[1]

    def test_ollama_requests_format_schema(self, monkeypatch):
        seen = []
        monkeypatch.setattr(photoscribe.requests, "post",
                            lambda url, json=None, timeout=None: (seen.append(json), _Resp())[1])
        self._worker("ollama")._call_ollama("img", "p")
        fmt = seen[0].get("format")
        assert isinstance(fmt, dict) and fmt["required"] == ["title", "caption", "keywords"]

    def test_ollama_falls_back_to_json_then_plain(self, monkeypatch):
        seen = []

        def post(url, json=None, timeout=None):
            seen.append(json.get("format"))
            # reject the schema (dict) with 400, accept "json"
            if isinstance(json.get("format"), dict):
                return _Resp(status=400)
            return _Resp()
        monkeypatch.setattr(photoscribe.requests, "post", post)
        self._worker("ollama")._call_ollama("img", "p")
        assert seen[0] and isinstance(seen[0], dict)   # first: schema
        assert seen[1] == "json"                       # fallback: plain json mode


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

    def test_location_asserted_as_ground_truth(self, monkeypatch):
        # v1.5.4: when a Location is supplied, the prompt must forbid the model
        # naming a different place (the "Spain photo captioned Thailand" bug).
        monkeypatch.setattr(MetadataWriter, "read_persons", lambda f: [])
        monkeypatch.setattr(MetadataWriter, "read_keywords", lambda f: [])
        w = make_worker(describe_people=False,
                        context="Location: Comillas, Cantabria, Spain")
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        assert "Comillas, Cantabria, Spain" in prompt
        assert "ground truth" in prompt.lower()
        assert "never name a different" in prompt.lower()

    def test_no_ground_truth_line_without_context(self, monkeypatch):
        monkeypatch.setattr(MetadataWriter, "read_persons", lambda f: [])
        monkeypatch.setattr(MetadataWriter, "read_keywords", lambda f: [])
        w = make_worker(describe_people=False, context="")
        photo = PhotoItem(filepath="x.jpg", filename="x.jpg")
        prompt = w._build_prompt(photo)
        assert "ground truth" not in prompt.lower()


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


# ── UTF-8 accented keywords (v1.5.4) ──────────────────────────────

@needs_exiftool
class TestAccentedKeywords:
    """Accented keywords used to be written as Latin-1 and shown as "?" in
    Lightroom. v1.5.4 marks the IPTC block UTF-8 (CodedCharacterSet=UTF8)."""

    def _ccs(self, path):
        exiftool = MetadataWriter.find_exiftool()
        r = photoscribe._run([exiftool, "-s3", "-IPTC:CodedCharacterSet", str(path)],
                             capture_output=True, text=True)
        return r.stdout.strip()

    def test_single_write_preserves_accents(self, tmp_path):
        img = make_jpeg(tmp_path / "a.jpg")
        meta = PhotoMetadata(title="T", caption="C",
                             keywords=["Château de Chenonceau", "Provençe", "Nîmes"])
        MetadataWriter.write_metadata(str(img), meta, backup=False)
        _, _, kws = MetadataWriter.read_existing_metadata(str(img))
        assert "Château de Chenonceau" in kws
        assert "Nîmes" in kws
        assert self._ccs(img) == "UTF8"

    def test_batch_write_preserves_accents(self, tmp_path):
        img = make_jpeg(tmp_path / "b.jpg")
        meta = PhotoMetadata(title="Café", caption="C",
                             keywords=["Château de Chenonceau", "Loire Valley"])
        n, errs = MetadataWriter.write_metadata_batch(
            [(str(img), meta)], backup=False, append_keywords=False)
        assert n == 1 and not errs
        _, _, kws = MetadataWriter.read_existing_metadata(str(img))
        assert "Château de Chenonceau" in kws
        assert self._ccs(img) == "UTF8"


# ── GPS + location from XMP sidecars (v1.5.4) ─────────────────────

@needs_exiftool
class TestSidecarLocation:
    """RAW files geotagged in Lightroom / Geotag Photos Pro keep GPS and the
    resolved City/State/Country in a .xmp sidecar, not baked into the raw.
    v1.5.4 reads the sidecar so the location reaches the prompt."""

    def _make_raw_with_sidecar(self, tmp_path, adobe_naming=False):
        raw = tmp_path / "DSCF1234.RAF"
        raw.write_bytes(b"\x00" * 32)  # dummy raw exiftool can't read
        sidecar = (raw.with_suffix(".xmp") if adobe_naming
                   else Path(str(raw) + ".xmp"))
        exiftool = MetadataWriter.find_exiftool()
        photoscribe._run([exiftool, "-overwrite_original",
                          "-XMP:GPSLatitude=43.383686",
                          "-XMP:GPSLongitude=-4.292961",
                          "-XMP-photoshop:City=Comillas",
                          "-XMP-photoshop:State=Cantabria",
                          "-XMP-photoshop:Country=Spain",
                          str(sidecar)], capture_output=True, text=True)
        return raw

    def test_gps_read_from_sidecar(self, tmp_path):
        raw = self._make_raw_with_sidecar(tmp_path)
        coords = photoscribe.read_gps_coordinates(str(raw))
        assert coords is not None
        assert abs(coords[0] - 43.383686) < 1e-4
        assert abs(coords[1] - (-4.292961)) < 1e-4

    def test_location_fields_read_from_sidecar(self, tmp_path):
        raw = self._make_raw_with_sidecar(tmp_path)
        loc = photoscribe.read_location_fields(str(raw))
        assert loc is not None
        assert "Comillas" in loc and "Spain" in loc
        # City before Country in the assembled string
        assert loc.index("Comillas") < loc.index("Spain")

    def test_location_fields_adobe_naming(self, tmp_path):
        raw = self._make_raw_with_sidecar(tmp_path, adobe_naming=True)
        loc = photoscribe.read_location_fields(str(raw))
        assert loc and "Comillas" in loc

    def test_no_sidecar_returns_none(self, tmp_path):
        raw = tmp_path / "bare.RAF"
        raw.write_bytes(b"\x00" * 32)
        assert photoscribe.read_gps_coordinates(str(raw)) is None
        assert photoscribe.read_location_fields(str(raw)) is None
