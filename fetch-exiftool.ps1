# Downloads the current ExifTool Windows build and lays it out for bundling.
# Produces, next to this script:
#   exiftool.exe       - the launcher (renamed from "exiftool(-k).exe")
#   exiftool_files\    - the Perl runtime the launcher needs to run
#
# Used by both the GitHub Actions workflow and local Windows builds.
# Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File fetch-exiftool.ps1

$ErrorActionPreference = "Stop"

# SourceForge serves the real file to non-browser user agents; a browser-like
# UA gets an HTML interstitial instead, so we masquerade as curl.
$ua = "curl/8.4.0"

# Resolve the current ExifTool version (fall back if ver.txt is unreachable)
try {
    $ver = (Invoke-WebRequest -Uri "https://exiftool.org/ver.txt" `
            -UseBasicParsing -UserAgent $ua).Content.Trim()
} catch {
    $ver = "13.59"
}
Write-Host "ExifTool version: $ver"

$zip = "exiftool.zip"
$url = "https://sourceforge.net/projects/exiftool/files/exiftool-${ver}_64.zip/download"
Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $zip -UserAgent $ua

if (Test-Path exiftool_extract) { Remove-Item -Recurse -Force exiftool_extract }
Expand-Archive -Path $zip -DestinationPath exiftool_extract -Force

$src = Join-Path "exiftool_extract" "exiftool-${ver}_64"

# Clean any previous layout, then place the launcher + its files at the root
if (Test-Path exiftool.exe)   { Remove-Item -Force exiftool.exe }
if (Test-Path exiftool_files) { Remove-Item -Recurse -Force exiftool_files }
Copy-Item (Join-Path $src "exiftool(-k).exe") "exiftool.exe"
Copy-Item (Join-Path $src "exiftool_files") "exiftool_files" -Recurse

Remove-Item -Force $zip
Remove-Item -Recurse -Force exiftool_extract

Write-Host "Done: exiftool.exe + exiftool_files\ ready for the build"
