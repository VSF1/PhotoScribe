#!/bin/bash
# PhotoScribe macOS App Builder
# Produces: dist/PhotoScribe.app  and  dist/PhotoScribe.dmg
#
# Signing + notarization happen automatically if your credentials are stored.
# One-time setup (only needed once per machine):
#
#   xcrun notarytool store-credentials "notarytool" \
#     --apple-id barefootgeek@me.com \
#     --team-id PXUGHCDN9B \
#     --password <app-specific-password>
#
# Generate the app-specific password at: https://appleid.apple.com → App-Specific Passwords
#
# Requirements: Python 3.10-3.13 (3.14 not yet supported by PyInstaller)
# Run from the photoscribe/ directory:  ./build_app.sh

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

SIGNING_IDENTITY="Developer ID Application: Andrew Hutchinson (PXUGHCDN9B)"
NOTARYTOOL_PROFILE="notarytool"
BUNDLE_ID="com.photoscribe.app"

echo ""
echo -e "${BOLD}PhotoScribe — macOS App Builder${NC}"
echo ""

# ── Find a compatible Python (3.10-3.13; PyInstaller doesn't support 3.14 yet) ──
PYTHON=""
for v in 3.13 3.12 3.11 3.10; do
    if command -v "python$v" &>/dev/null; then
        PYTHON="python$v"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    if command -v python3 &>/dev/null; then
        VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MINOR" -ge 10 ] && [ "$MINOR" -le 13 ]; then
            PYTHON="python3"
        fi
    fi
fi
if [ -z "$PYTHON" ]; then
    echo -e "${RED}✗ Python 3.10-3.13 required. PyInstaller does not yet support 3.14.${NC}"
    echo "  Install with: brew install python@3.13"
    exit 1
fi
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓${NC} Using $PYTHON ($PY_VER)"

# ── Check signing capability ──
WILL_SIGN=false
WILL_NOTARIZE=false

if security find-identity -v -p codesigning | grep -qF "$SIGNING_IDENTITY"; then
    WILL_SIGN=true
    echo -e "${GREEN}✓${NC} Signing identity found"
else
    echo -e "${YELLOW}⚠${NC} Signing identity not found — app will be unsigned"
fi

if $WILL_SIGN; then
    if xcrun notarytool history --keychain-profile "$NOTARYTOOL_PROFILE" &>/dev/null 2>&1; then
        WILL_NOTARIZE=true
        echo -e "${GREEN}✓${NC} Notarization credentials found"
    else
        echo -e "${YELLOW}⚠${NC} Notarization credentials not stored"
        echo "  Run once to enable automatic notarization:"
        echo "    xcrun notarytool store-credentials \"notarytool\" \\"
        echo "      --apple-id barefootgeek@me.com \\"
        echo "      --team-id PXUGHCDN9B \\"
        echo "      --password <app-specific-password>"
    fi
fi

# ── Set up build venv ──
BUILD_VENV="$SCRIPT_DIR/.build_venv"
if [ ! -d "$BUILD_VENV" ]; then
    echo "Creating build environment..."
    $PYTHON -m venv "$BUILD_VENV"
fi
source "$BUILD_VENV/bin/activate"

echo "Installing build dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q "pyinstaller>=6.0"
echo -e "${GREEN}✓${NC} Build dependencies ready"

# ── Generate .icns from logo.png ──
ICNS_PATH="$SCRIPT_DIR/PhotoScribe.icns"
if [ -f "$ICNS_PATH" ]; then
    echo -e "${GREEN}✓${NC} Using committed app icon (PhotoScribe.icns)"
elif [ -f "$SCRIPT_DIR/logo.png" ]; then
    echo "Generating app icon..."
    ICONSET="$SCRIPT_DIR/PhotoScribe.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size "$SCRIPT_DIR/logo.png" \
            --out "$ICONSET/icon_${size}x${size}.png" &>/dev/null
        double=$((size * 2))
        sips -z $double $double "$SCRIPT_DIR/logo.png" \
            --out "$ICONSET/icon_${size}x${size}@2x.png" &>/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$ICNS_PATH"
    rm -rf "$ICONSET"
    echo -e "${GREEN}✓${NC} App icon generated"
else
    echo -e "${YELLOW}⚠${NC} logo.png not found — app will use default icon"
    sed -i '' "s/icon='PhotoScribe.icns'/icon=None/" PhotoScribe.spec
fi

# ── PyInstaller build ──
echo ""
echo "Building PhotoScribe.app..."
echo "(This takes a minute or two on first run)"
echo ""

pyinstaller PhotoScribe.spec --noconfirm --clean

# Restore spec icon line if we patched it
if [ -f "$SCRIPT_DIR/logo.png" ]; then
    sed -i '' "s/icon=None/icon='PhotoScribe.icns'/" PhotoScribe.spec 2>/dev/null || true
fi

APP_PATH="$SCRIPT_DIR/dist/PhotoScribe.app"
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}✗ Build failed — dist/PhotoScribe.app not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} dist/PhotoScribe.app built"

# ── Deep sign all binaries inside the bundle ──
# PyInstaller signs the outer shell, but we need to re-sign everything inside
# so Gatekeeper accepts it as fully signed.
if $WILL_SIGN; then
    echo "Signing app bundle..."

    # Sign all dylibs and .so files first (deepest first)
    find "$APP_PATH" -type f \( -name "*.dylib" -o -name "*.so" \) | while read f; do
        codesign --force --sign "$SIGNING_IDENTITY" \
            --options runtime \
            --timestamp \
            "$f" 2>/dev/null || true
    done

    # Sign all nested executables
    find "$APP_PATH" -type f -perm +111 | while read f; do
        if file "$f" | grep -q "Mach-O"; then
            codesign --force --sign "$SIGNING_IDENTITY" \
                --options runtime \
                --timestamp \
                "$f" 2>/dev/null || true
        fi
    done

    # Sign the whole .app bundle last
    codesign --force --deep --sign "$SIGNING_IDENTITY" \
        --options runtime \
        --timestamp \
        "$APP_PATH"

    # Verify
    codesign --verify --deep --strict "$APP_PATH" \
        && echo -e "${GREEN}✓${NC} Code signing verified" \
        || echo -e "${YELLOW}⚠${NC} Code signing verification had warnings"
fi

# ── Notarize ──
if $WILL_NOTARIZE; then
    echo "Notarizing (submitting to Apple — takes 1-5 minutes)..."

    # Zip the app for notarization submission
    NOTARIZE_ZIP="$SCRIPT_DIR/dist/PhotoScribe_notarize.zip"
    ditto -c -k --keepParent "$APP_PATH" "$NOTARIZE_ZIP"

    # Submit and wait
    xcrun notarytool submit "$NOTARIZE_ZIP" \
        --keychain-profile "$NOTARYTOOL_PROFILE" \
        --wait \
        --timeout 600

    rm -f "$NOTARIZE_ZIP"

    # Staple the notarization ticket to the app
    xcrun stapler staple "$APP_PATH" \
        && echo -e "${GREEN}✓${NC} Notarization stapled" \
        || echo -e "${RED}✗ Stapling failed — check notarytool output above${NC}"
fi

# ── Create DMG ──
echo "Creating DMG..."
DMG_PATH="$SCRIPT_DIR/dist/PhotoScribe.dmg"
TMP_DMG_DIR="$SCRIPT_DIR/dist/_dmg_staging"

rm -f "$DMG_PATH"
rm -rf "$TMP_DMG_DIR"
mkdir -p "$TMP_DMG_DIR"
cp -R "$APP_PATH" "$TMP_DMG_DIR/"
ln -s /Applications "$TMP_DMG_DIR/Applications"

hdiutil create \
    -volname "PhotoScribe" \
    -srcfolder "$TMP_DMG_DIR" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_PATH" \
    &>/dev/null

rm -rf "$TMP_DMG_DIR"
echo -e "${GREEN}✓${NC} dist/PhotoScribe.dmg created"

# ── Sign and notarize the DMG itself ──
if $WILL_SIGN; then
    codesign --sign "$SIGNING_IDENTITY" --timestamp "$DMG_PATH"
    echo -e "${GREEN}✓${NC} DMG signed"
fi

if $WILL_NOTARIZE; then
    echo "Notarizing DMG..."
    xcrun notarytool submit "$DMG_PATH" \
        --keychain-profile "$NOTARYTOOL_PROFILE" \
        --wait \
        --timeout 300
    xcrun stapler staple "$DMG_PATH" \
        && echo -e "${GREEN}✓${NC} DMG notarization stapled" \
        || true
fi

# ── Summary ──
APP_SIZE=$(du -sh "$APP_PATH" 2>/dev/null | cut -f1)
DMG_SIZE=$(du -sh "$DMG_PATH" 2>/dev/null | cut -f1)
echo ""
echo -e "${BOLD}Build complete!${NC}"
echo "  App:  dist/PhotoScribe.app  ($APP_SIZE)"
echo "  DMG:  dist/PhotoScribe.dmg  ($DMG_SIZE)"
if $WILL_NOTARIZE; then
    echo "  Status: Signed and notarized ✓"
elif $WILL_SIGN; then
    echo "  Status: Signed (not notarized)"
else
    echo "  Status: Unsigned — right-click → Open on first launch"
fi
echo ""
echo "To distribute: share dist/PhotoScribe.dmg"
echo ""
