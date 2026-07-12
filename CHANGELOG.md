# Changelog

All notable changes to PhotoScribe are recorded here. Dates are ISO (YYYY-MM-DD).

## [1.6.0.2] — 2026-07-12

### Added
- **New prompt presets.** Added several new built-in presets for different photography genres: Portrait, Studio Portrait, Lifestyle, Fashion, Boudoir, Sports, and Wedding.

### Changed
- **Model download UI.** The model download progress bar no longer disappears automatically. A close button has been added to allow users to dismiss the status message manually.

### Fixed
- **Application stability.** Fixed several crashes, including an initialization error on startup and an error when dragging and dropping photos.
- **Linux packaging.** Corrected the installation path for RPM packages to prevent deeply nested directories. The build script has also been improved to correctly parse version numbers and report the final package path.

## [1.6.0.1] — 2026-07-12

### Added
- **Modular AI Prompts ("Skills").** The logic for constructing the AI prompt is now loaded from external text files in a `prompt_skills/` directory. This makes the AI's behavior much more flexible and easier for users to customize without altering the source code. The skills are organized into `context` and `instructions` subdirectories.

### Changed
- **Centralized UI Styling.** The application's visual styles, previously managed in a large inline block within `photoscribe.py`, have been moved to dedicated `style.qss` (dark theme) and `style_light.qss` (light theme) files for better organization and maintainability.

### Fixed
- **Corrected AI prompt construction.** Fixed a significant bug where multiple, conflicting calls to build the AI prompt were overwriting each other, causing important context like location and face tags to be lost. The prompt is now built in a single, correct pass.

## [1.6.0] — 2026-07-10

### Changed
- **Redesigned interface.** The window is reorganised into distinct cards — Model, Prompt, Batch Context, Options — each with a hairline border, rounded corners and its own section label, instead of one continuous scroll. The palette is warmer and far less saturated: the accent is now reserved for the things that actually mean something (the active tab, section labels, ticked checkboxes, and the Generate button), so nothing else competes for your eye.
- **Clearer controls.** Buttons share one height and radius and are ranked by weight: Generate is solid accent, Write Metadata is a muted teal, Export/Import are bordered ghost buttons. Checkboxes are a filled accent square when ticked and a plain outline when not. Tabs get a pill-shaped active state, and the backend connection status is now a pill badge in the header.
- **The prompt box is taller**, so the default prompt reads in full without scrolling.

### Fixed
- A stray white strip could appear at the right-hand edge of the settings panel, and the scrollbar rendered light against the dark theme.

## [1.5.6] — 2026-07-10

### Fixed
- **The location option no longer switches itself off between sessions.** "Look up location from photo GPS / metadata" was never saved, so it silently reset to unticked on every launch — while the one-time consent *was* remembered, making it look as though the option should still be on. It now persists, as do "Use folder context" and the EXIF-date fallback.
- **Location now takes effect when you enable it, and on Regenerate.** It used to be resolved once, when photos were loaded. Ticking the option afterwards, or re-running Regenerate, did nothing — you had to clear and reload the folder. The location is now resolved per photo when the metadata is generated.
- **Each photo gets its own location.** Previously one location was sampled from the first few files and applied to the whole batch, so a folder spanning several places tagged them all identically — and a geotagged photo further down the list was never even looked at. Anything typed into the Location field still overrides everything, for every photo.
- **Rural and coastal places are named properly.** The geocoder ignored OpenStreetMap's `locality` and `neighbourhood` fields, so a beach at Gerroa, NSW came back as the useless "New South Wales, Australia". It now reads them, giving "Gerroa, New South Wales, Australia".
- **The lookup says what it found.** It logs the location resolved for each photo, and says so once when a photo has no GPS or place name at all, instead of failing silently.

### Changed
- **Geocoding results are cached and rate-limited.** Coordinates are rounded (~11m) and cached, so a folder shot in one place makes a single request, and requests are held to one per second in line with OpenStreetMap Nominatim's usage policy.

## [1.5.5] — 2026-07-10

### Fixed
- **"Look up location from GPS" now actually runs on its own.** The location lookup was only executed when **Use folder context** was *also* enabled — with folder context off, enabling the GPS/location option did nothing at all (no network request, no location filled). Each source now runs on its own checkbox independently: folder-name detection, the EXIF-date fallback, and the location lookup no longer depend on one another. Reported on GitHub (#18).

### Changed
- **Location lookup renamed and clarified.** The option is now **"Look up location from photo GPS / metadata"**: it fills the Location field from the place name your cataloguer (e.g. Lightroom) already resolved — City/State/Country, from the file or its `.xmp` sidecar, with no network request — and only reverse-geocodes the GPS coordinates via OpenStreetMap when there's no such place name. The tooltip and consent dialog now describe this.

## [1.5.4] — 2026-07-10

### Fixed
- **Location from RAW/DNG photos is no longer missed, so captions stop inventing far-away places.** PhotoScribe now reads GPS *and* the resolved place name (Sublocation / City / State / Country) from a photo's `.xmp` sidecar, not just from the file itself. RAW files geotagged in Lightroom or Geotag Photos Pro keep that data in the sidecar, so previously a RAW/DNG shot arrived with no location and the model would free-associate from the image alone — e.g. a Gaudí tower in Comillas, Spain captioned as being in Phuket, Thailand. JPEGs (GPS baked into EXIF) always worked; RAW now behaves the same. Reported on GitHub.
- **The resolved place name is now preferred over a GPS lookup.** When a cataloguer (e.g. Lightroom) has already written City/State/Country, PhotoScribe uses that directly — exact and no network call — and only falls back to reverse-geocoding GPS coordinates when there's no place name to use.
- **Accented keywords no longer show as "?" in Lightroom.** Keywords like *Château de Chenonceau* were written as Latin-1 and mis-decoded by readers. The IPTC block is now marked UTF-8 (`CodedCharacterSet=UTF8`) on every write, so accents survive round-trip.

### Changed
- **The photo's location is now treated as ground truth in the prompt.** When a Location is supplied, the model is explicitly told the photo was taken there and must not name a different city, region, or country even if the scene reminds it of somewhere else — and to describe the scene without naming a place when it isn't sure, rather than guessing.

## [1.5.3] — 2026-07-09

### Added
- **Regenerate photos after they're already done.** Right-click a photo in the list for **Regenerate this photo** or **Regenerate all photos** — it resets them and runs generation again with your current settings. Previously a processed (green-dot) photo was skipped by Generate with no way to redo it, so changing a setting (e.g. turning on GPS location lookup) meant it wouldn't take effect on already-processed photos. Requested on GitHub.

## [1.5.2] — 2026-07-06

### Fixed
- **Models are now forced to return JSON, so "couldn't read metadata" failures should essentially stop.** Some models (e.g. Gemma via LM Studio) would occasionally reply with a bulleted "thinking" plan and never actually produce the JSON — which no amount of parsing can recover. PhotoScribe now uses the backend's structured-output mode (LM Studio / OpenAI `json_schema`, Ollama schema `format`) to grammar-constrain the reply to the required `{title, caption, keywords}` shape, so the model can't wander off into prose. Falls back gracefully if a backend doesn't support it, and the tolerant parser from 1.5.1 remains as a safety net. Verified against Gemma-4-12B in LM Studio.

### Changed
- **Often much faster, too.** Because the model no longer spends time writing a reasoning essay before the JSON, generation is frequently several times quicker — in testing on the same model, roughly **7s per photo instead of ~65s**. A pleasant side effect of the fix above.

## [1.5.1] — 2026-07-06

### Fixed
- **Far fewer "couldn't read metadata" failures.** The model's reply is now parsed much more forgivingly. Previously a photo could fail if the model wrapped its JSON in a "thinking" preamble, used single quotes or smart quotes, left a trailing comma, added `//` comments, or left keywords unquoted (`[gulls, beach]`) — all common with smaller local models. The parser now scans for the real JSON object (ignoring stray braces in surrounding prose) and repairs these common malformations before giving up. When it genuinely can't parse a reply, the raw response is now written to the log so the failure can be diagnosed.

## [1.5.0] — 2026-07-06

### Changed
- **Much faster metadata writing.** Writing a folder now uses a single persistent ExifTool process (`-stay_open` batch mode) instead of launching a new one per photo — roughly **3× faster** on large folders (measured 47 photos in 33s vs 102s), and on Windows it no longer steals window focus for every file. Skip-existing, append-keywords, and replace all behave exactly as before, including the numeric-keyword handling from 1.4.2. RAW/XMP-sidecar files are still written individually. Contributed by [@bridgew99](https://github.com/bridgew99) (#16), closing the batch-writing request in #13.

### Internal
- Added tests covering the batch write worker across replace/append/skip, plus the metadata read/write path generally (`tests/test_metadata.py`).

## [1.4.2] — 2026-07-05

### Fixed
- **Writing metadata no longer fails on files with numeric keywords.** If a photo already had a purely numeric keyword (e.g. a year like `2025`), writing aborted with `'int' object has no attribute 'lower'` — ExifTool returns numeric values as numbers, not text, which broke the keyword comparison. Keywords are now normalised to text everywhere, whether read from the file or generated by the model, so the write goes through. Affected RAW/XMP-sidecar files (e.g. `.ORF`) as well as embedded metadata. Thanks to the user who reported it with the exact error.

## [1.4.1] — 2026-07-04

### Fixed
- **Stop the model inventing specific names it can't know.** On subjects like landmarks or bridges, small vision models would confabulate a plausible-but-wrong proper name to fill the gap — and pick a different one for each near-identical frame (four burst photos of one bridge → four different, mostly-wrong bridge names). PhotoScribe now instructs the model to only name specifics that are given in the context/tags or clearly legible in the image, and to stay generic ("a bridge over a river") when it isn't sure — better general and correct than specific and wrong. Setting the **Location** field gives it a real place name to anchor to. Reported by @Zoolander06 in #15.

## [1.4.0] — 2026-07-04

### Added
- **Person-aware captions.** When "Describe people in photos" is on, PhotoScribe reads any names already tagged on a photo — from `PersonInImage`, MWG face regions, and Excire FaceTags, in the image *and* its co-located XMP sidecar — and weaves them into the title, caption, and keywords ("Andy and his dog on a coastal trail" instead of "a man with a dog"). Only kicks in when names are present; photos with no tags behave as before. Based on [@Boui3D](https://github.com/Boui3D)'s reference in #9.
- **Species / subject-aware captions.** PhotoScribe now reads keyword and subject tags already on a file (and its XMP sidecar) — e.g. bird names written by a specialist tagger like SuperPicky — and feeds them to the model as facts. Local generalist vision models can't reliably identify a species, so the caption can now say "a Superb Fairywren perched in reeds" instead of "a small bird". Off when there are no existing tags.
- **"Kept" title/caption shown in Results.** With "Skip title/caption if file already has them" turned on, the Results panel now shows the *existing* title/caption (marked **KEPT**) — the value that will actually stay on the file — instead of the AI's discarded suggestion. This clears up the common confusion where it looked like skip wasn't working.

### Changed
- **Model recommender now detects AMD and Intel GPUs** (Windows/Linux) and Intel-Mac discrete cards, not just NVIDIA and Apple Silicon — so it shows your actual GPU and uses its VRAM where it can read it, instead of always falling back to system RAM.

## [1.3.4] — 2026-06-30

### Added
- **Auto-write after generating** — a new option writes metadata to your files as soon as generation finishes, so a large folder can run fully unattended.
- **Live ETA** on the progress bar while generating (estimated time remaining).
- **Version number** shown under the title.

### Fixed
- **Windows: ExifTool no longer steals focus.** Each ExifTool call was popping a console window that grabbed focus mid-write; that window is now suppressed.
- **Ignore macOS AppleDouble (`._*`) and hidden files** when loading. On external/network volumes these were loaded as phantom photos (doubling the count and wasting processing).

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
