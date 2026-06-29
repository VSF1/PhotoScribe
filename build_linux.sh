#!/bin/bash
# PhotoScribe Linux Package Builder
# Produces: .deb (Debian/Ubuntu), .rpm (Fedora), or .tar.gz (fallback)
#
# This script creates a self-contained executable using PyInstaller and bundles
# it into a native package for distribution on Linux.
#
# Requirements: Python 3.10-3.13
# Recommended: fpm (for .deb/.rpm builds) -> `gem install fpm`
# 
# Usage: ./build_linux.sh [deb|rpm|tar]
# If no argument is given, the script auto-detects the package type.
#
# To sign the release archive (tar.gz only):
# To sign the release archive, set your GPG key ID:
#   export GPG_SIGNING_KEY_ID="YourKeyID"
#   ./build_linux.sh

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

# ── Get version from CHANGELOG.md ──
APP_VERSION=$(grep -m 1 '^## \[' CHANGELOG.md | sed -E 's/## \[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/')
if [ -z "$APP_VERSION" ]; then
    echo -e "${RED}✗ Could not determine version from CHANGELOG.md.${NC}"
    echo "  Make sure there is a line like '## [1.2.3] — YYYY-MM-DD'"
    exit 1
fi
echo -e "${GREEN}✓${NC} Building version $APP_VERSION"

# ── Find a compatible Python (3.10-3.13) ──
PYTHON=""
for v in "3.13" "3.12" "3.11" "3.10"; do
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

# ── Check signing capability ──
WILL_SIGN=false
if [ -n "$GPG_SIGNING_KEY_ID" ]; then
    if command -v gpg &>/dev/null; then
        if gpg --list-secret-keys "$GPG_SIGNING_KEY_ID" &>/dev/null; then
            WILL_SIGN=true
            echo -e "${GREEN}✓${NC} GPG signing key found ($GPG_SIGNING_KEY_ID)"
        else
            echo -e "${YELLOW}⚠${NC} GPG key '$GPG_SIGNING_KEY_ID' not found. Archive will be unsigned."
        fi
    else
        echo -e "${YELLOW}⚠${NC} gpg command not found. Archive will be unsigned."
    fi
else
    echo -e "${YELLOW}⚠${NC} GPG_SIGNING_KEY_ID not set. Archive will be unsigned."
fi

# ── Check packaging capability (fpm) ──
PKG_TYPE="$1"

if [ -n "$PKG_TYPE" ]; then
    if [[ "$PKG_TYPE" != "deb" && "$PKG_TYPE" != "rpm" && "$PKG_TYPE" != "tar" ]]; then
        echo -e "${RED}✗ Invalid package type '$PKG_TYPE'. Must be 'deb', 'rpm', or 'tar'.${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} User specified package type: $PKG_TYPE"
else
    # Auto-detect if no package type is provided
    if command -v fpm &>/dev/null; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            if [[ "$ID_LIKE" == *"debian"* || "$ID" == "debian" || "$ID" == "ubuntu" || "$ID" == "mint" ]]; then
                PKG_TYPE="deb"
                echo -e "${GREEN}✓${NC} fpm found, auto-detecting .deb package"
            elif [[ "$ID_LIKE" == *"fedora"* || "$ID" == "fedora" || "$ID" == "centos" || "$ID" == "rhel" ]]; then
                PKG_TYPE="rpm"
                echo -e "${GREEN}✓${NC} fpm found, auto-detecting .rpm package"
            fi
        fi
    fi
    if [ -z "$PKG_TYPE" ]; then
        echo -e "${YELLOW}⚠${NC} fpm not found or OS not detected. Building .tar.gz archive as fallback."
        echo "  For native packages (.deb/.rpm), install fpm: sudo gem install fpm"
        PKG_TYPE="tar"
    fi
fi

# ── Set up build venv ──
BUILD_VENV="$SCRIPT_DIR/.build_venv_linux"
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

# ── Create package or archive ──
if [ "$PKG_TYPE" = "deb" ] || [ "$PKG_TYPE" = "rpm" ]; then
    echo "Creating $PKG_TYPE package..."
    # Create post-install script to make a symlink
    POST_INSTALL_SCRIPT="dist/post-install.sh"
    cat > "$POST_INSTALL_SCRIPT" << 'EOF'
#!/bin/sh
set -e
echo "Creating symlink /usr/local/bin/photoscribe..."
ln -sf /opt/photoscribe/photoscribe /usr/local/bin/photoscribe
exit 0
EOF
    chmod +x "$POST_INSTALL_SCRIPT"

    # Set dependencies based on package type
    if [ "$PKG_TYPE" = "deb" ]; then
        EXIFTOOL_DEP="libimage-exiftool-perl"
    else # rpm
        EXIFTOOL_DEP="perl-Image-ExifTool"
    fi

    fpm -s dir -t "$PKG_TYPE" \
        -n "photoscribe" \
        --force \
        -v "$APP_VERSION" \
        --iteration "1" \
        --prefix "/opt/photoscribe" \
        -p "dist/" \
        -C "dist" \
        --depends "$EXIFTOOL_DEP" \
        --after-install "$POST_INSTALL_SCRIPT" \
        --license "MIT" \
        --vendor "Andy Hutchinson" \
        --url "https://github.com/repomonkey/PhotoScribe" \
        --description "AI-powered photo metadata generator that runs entirely on your PC. No cloud, no subscription." \
        "PhotoScribe/=/opt/photoscribe"

    PACKAGE_FILE=$(find dist/ -name "photoscribe*.${PKG_TYPE}" -print -quit)
    echo -e "${GREEN}✓${NC} Package created: $PACKAGE_FILE"
    echo ""
    echo -e "${BOLD}Build complete!${NC}"
    echo "  Package:   $PACKAGE_FILE"
    echo "  To install:"
    if [ "$PKG_TYPE" = "deb" ]; then
        echo "    sudo dpkg -i $PACKAGE_FILE"
        echo "    sudo apt-get install -f  # To install dependencies"
    else
        echo "    sudo rpm -i $PACKAGE_FILE"
    fi

else # Fallback to tar.gz
    echo "Creating tar.gz archive..."
    ARCHIVE_NAME="PhotoScribe-linux-x86_64.tar.gz"
    cd dist
    tar -czf "$ARCHIVE_NAME" PhotoScribe
    cd ..
    echo -e "${GREEN}✓${NC} dist/$ARCHIVE_NAME created"

    # Sign the archive with GPG
    if $WILL_SIGN; then
        echo "Signing archive with GPG..."
        gpg --detach-sign --armor \
            --local-user "$GPG_SIGNING_KEY_ID" \
            --output "dist/$ARCHIVE_NAME.asc" \
            "dist/$ARCHIVE_NAME"
        echo -e "${GREEN}✓${NC} Signature created at dist/$ARCHIVE_NAME.asc"
    fi

    echo ""
    echo -e "${BOLD}Build complete!${NC}"
    echo "  Archive:   dist/$ARCHIVE_NAME"
    if $WILL_SIGN; then
        echo "  Signature: dist/$ARCHIVE_NAME.asc"
    fi
    echo ""
    echo "  To verify the build, users can run:"
    echo "    gpg --verify dist/$ARCHIVE_NAME.asc dist/$ARCHIVE_NAME"
    echo ""
    echo "  To run the app:"
    echo "    tar -xzf dist/$ARCHIVE_NAME && ./PhotoScribe/photoscribe"
fi