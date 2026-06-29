# Changelog

All notable changes to PhotoScribe are recorded here. Dates are ISO (YYYY-MM-DD).

## [1.3.3] — 2026-06-28

### Added
- **The keyword vocabulary now persists** between sessions — paste it once and it's there next launch.

### Changed
- **Larger photo preview** in the Results tab (roughly double), so it's actually useful for reviewing before writing.
- **Clear All** now also deletes the folder's saved-progress file, so repeated test runs start clean without hunting down a hidden file.

## [1.3.2] — 2026-06-28

### Fixed
- **RAW files: skip-existing (and append-keywords) now work for XMP sidecars.** The sidecar writer ignored both options and always overwrote, so existing captions on RAW files (e.g. from Photo Mechanic) were replaced even with "skip if already present" turned on. It now reads the existing sidecar and honours skip/append like the embedded path. Follow-up to 1.3.1, which only covered embedded JPEG/TIFF metadata.

## [1.3.1] — 2026-06-24

### Fixed
- **"Skip title/caption if file already has them" no longer overwrites existing captions.** The check only looked at the IPTC caption field; captions stored in XMP (`dc:description`) or EXIF — as Photo Mechanic and Lightroom write them — went undetected and were overwritten. It now coalesces title, caption, and keywords across IPTC, XMP, and EXIF.

## [1.3.0] — 2026-06-24

A big feature release, with substantial community contributions from
[@bridgew99](https://github.com/bridgew99) (performance, context detection, UI/UX).

### Added
- **Folder context detection** — parses dated folder names (e.g. `20250315 - Berry NSW`, ISO and dot-separated variants), walking up the tree, to pre-fill Location and Date/Time (empty fields only).
- **Folder Presets tab** — rules to auto-apply a prompt preset or keyword list based on folder name.
- **Editable prompt presets** — Save As / Update / Delete; custom presets persist, built-ins can be overridden.
- **CSV import** — load metadata from a previously exported (or spreadsheet-edited) CSV; matches by filepath then filename and reports unmatched rows.
- **Photo preview** in the Results tab, and **double-click** a photo to jump to its result.
- **Model recommender** — detects GPU/RAM and suggests the best Gemma model (LM Studio name or Ollama pull).
- **Describe people** option — describe positions/roles/actions, never names.
- **Auto-deduplicate keywords** — removes plural/case near-duplicates.
- **EXIF date fallback** when no folder date is detected.
- **GPS reverse-geocode** (opt-in, off by default, one-time consent) — place-name lookup via OpenStreetMap; reads the image and co-located XMP sidecar.
- **Progress resume** — interrupted batches (and manual edits) restore on reload.
- **Batch timing** — per-photo seconds in the log plus a batch summary in the status bar.

### Changed
- **Much faster** large-folder handling: no thumbnail generation at load, pipelined image pre-encoding, single-row table updates, threaded metadata writing with a progress bar.
- Options laid out in two columns; window sizes to the screen and centres on launch.

## [1.2.4] — 2026-06-22

### Added
- **DxO PhotoLab support** for RAW XMP sidecars. PhotoLab uses the same `photo.xmp` convention as Adobe/Lightroom, so the sidecar naming option is now labelled **"Adobe / Lightroom / PhotoLab"**. Title, description, and keywords round-trip into PhotoLab (with its *"Synchronize metadata with XMP sidecars"* preference enabled). No write-logic change — purely confirmation + labelling.

## [1.2.3] — 2026-06-22

### Fixed
- Keywords now **match an existing keyword vocabulary's spelling**. Generated keywords are snapped (case-insensitively) to the exact term from your keyword list, and case-insensitive duplicates are dropped. Stops Lightroom and other DAMs importing `sunset` as a new keyword separate from your existing `Sunset`.

## [1.2.2] — 2026-06-22

First cross-platform release: macOS **and** Windows.

### Added
- **Windows installer** (`PhotoScribe-Setup.exe`), built by GitHub Actions on every `v*` tag and attached to the release automatically. ExifTool is bundled, so Windows users have nothing else to install.
- New custom app icon across both platforms.

### Changed
- Reworked `MetadataWriter.find_exiftool()` so a frozen build looks for ExifTool **next to the app executable** first (where it now ships), then `_MEIPASS`, then PATH / known locations.
- Carried HEIC/HEIF support through to the Windows build.

## [1.2.1] — 2026-06-22

Reliability release for RAW/DNG handling and error reporting.

### Added
- **HEIC / HEIF support** via `pillow-heif` (iPhone photos). Added to supported formats, the file dialog, and the drop-zone label; libheif is bundled in the app.

### Changed
- RAW files (incl. DNG) are now decoded from their **embedded preview JPEG** first, falling back to a full LibRaw decode only when there's no usable preview. Fixes phone/HDR/Lightroom-converted DNGs that decoded dark or blank and made the model return nothing. Also faster.

### Fixed
- An empty or non-JSON model response now triggers **one automatic retry** and, if it still fails, a plain-English message — instead of the cryptic `JSON parse error: Expecting value: line 1 column 1 (char 0)`.

## [1.2] — 2026-06-22

### Added
- **XMP sidecar support** for RAW files, with a selectable naming convention:
  - Adobe / Lightroom — `photo.xmp` (extension replaced)
  - Darktable / DigiKam — `photo.cr2.xmp` (extension kept)
  Title, caption, and keywords are written to the correct `XMP-dc` fields.
- **Keyword density** control (Fewer / Standard / More keywords) — no technical token settings exposed.

### Fixed
- LM Studio "thinking" models occasionally returning empty responses, by improving how JSON is extracted (and falling back to `reasoning_content`).

## [1.1] — 2026-06-07
- Windows build pipeline scaffolding and cross-platform ExifTool detection (the pipeline itself was first made to actually work in 1.2.2 — see notes below).

## [1.0.0]
- Initial release: local AI photo metadata generation (LM Studio / Ollama), IPTC + embedded XMP writing via ExifTool, batch context, prompts/presets, keyword vocabulary, CSV export.

---

## Build & infrastructure notes

Engineering details worth remembering, especially for the Windows pipeline.

### macOS build
- `./build_app.sh` produces a signed + notarized `dist/PhotoScribe.dmg` and `.app`.
- The app icon is the committed `PhotoScribe.icns` (regenerated from `icon.png`); `build_app.sh` only falls back to generating one from `logo.png` if `PhotoScribe.icns` is absent.
- `logo.png` is the gold footer signature shown in-app — **not** the icon. Don't repurpose it.

### Windows build (`.github/workflows/build-windows.yml`)
Hard-won fixes:

1. **ExifTool download.** exiftool.org no longer self-hosts the Windows zip — it's on SourceForge. `fetch-exiftool.ps1` reads the current version from `https://exiftool.org/ver.txt` and downloads `exiftool-<ver>_64.zip` from SourceForge. SourceForge serves the real file only to non-browser user agents, so the script sends a `curl/8.4.0` UA (a browser-like UA gets an HTML interstitial instead).

2. **`exiftool_files` layout.** Modern ExifTool is not a single exe — it's `exiftool(-k).exe` (a launcher, renamed to `exiftool.exe`) plus an `exiftool_files\` folder with the Perl runtime. Bundling this **through** PyInstaller breaks Perl's `@INC` (`Can't locate strict.pm`). Fix: do **not** put ExifTool in the spec `datas`; instead copy `exiftool.exe` + `exiftool_files\` into `dist\PhotoScribe\` (next to the exe) as a post-build step, and have `find_exiftool()` look there.

3. **CI release upload.** The workflow needs `permissions: contents: write` or `gh release upload` fails with `HTTP 403: Resource not accessible by integration`.

4. **Triggers.** Builds on `v*` tags and manual `workflow_dispatch`. Manual runs upload the installer as a downloadable artifact; tag runs also attach it to the matching release. Installer version comes from the tag (falls back to `0.0.0` on non-tag runs).

Local Windows build (Python 3.10–3.13):
```
pip install -r requirements.txt "pyinstaller>=6.0"
powershell -ExecutionPolicy Bypass -File fetch-exiftool.ps1
pyinstaller PhotoScribe-Windows.spec --noconfirm --clean
Copy-Item exiftool.exe dist\PhotoScribe\ -Force
Copy-Item exiftool_files dist\PhotoScribe\exiftool_files -Recurse -Force
& "<path>\ISCC.exe" /DMyAppVersion=<version> installer.iss
```
