#!/bin/bash
# PhotoScribe Linux App Builder
# Produces: dist/PhotoScribe-linux-x86_64.tar.gz
#
# This script creates a self-contained executable using PyInstaller and bundles
# it into a tarball for distribution on Linux.
#
# Requirements: Python 3.10-3.13
# Run from the photoscribe/ directory:  ./build_linux.sh

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${BOLD}PhotoScribe — Linux App Builder${NC}"
echo ""

# ── Find a compatible Python (3.10-3.13) ──
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
    echo -e "${RED}✗ Python 3.10-3.13 required.${NC}"
    echo "  Install with: sudo apt install python3.13"
    exit 1
fi
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}✓${NC} Using $PYTHON ($PY_VER)"

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

# ── PyInstaller build ──
echo ""
echo "Building PhotoScribe executable..."
pyinstaller PhotoScribe.spec --noconfirm --clean

APP_DIR="$SCRIPT_DIR/dist/PhotoScribe"
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}✗ Build failed — dist/PhotoScribe directory not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Executable built"

# ── Create tar.gz archive ──
echo "Creating tar.gz archive..."
ARCHIVE_NAME="PhotoScribe-linux-x86_64.tar.gz"
cd dist
tar -czf "$ARCHIVE_NAME" PhotoScribe
cd ..
echo -e "${GREEN}✓${NC} dist/$ARCHIVE_NAME created"
echo ""
echo -e "${BOLD}Build complete!${NC}"
echo "  To run: tar -xzf dist/$ARCHIVE_NAME && ./PhotoScribe/photoscribe"
echo ""