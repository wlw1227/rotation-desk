#!/usr/bin/env bash
# build.sh — RotationDesk full build
#
# Steps:
#   1. Create Python venv and install dependencies
#   2. Build Python sidecar binary with PyInstaller
#   3. Build Tauri desktop app
#
# Prerequisites:
#   - Python 3.11+
#   - Rust + cargo (https://rustup.rs)
#   - Node.js 18+ (for npm/tauri-cli)
#   - Xcode Command Line Tools (macOS)
#
# Usage:
#   bash build.sh
#
# Output:
#   src-tauri/target/release/bundle/macos/RotationDesk.app  (macOS)
#   src-tauri/target/release/bundle/nsis/RotationDesk_*.exe (Windows)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
SIDECAR_DIR="$PROJECT_ROOT/src-tauri/binaries"
VENV="$PROJECT_ROOT/venv"

print_step() { echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo "  $1"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }

# ── Step 1: Python venv + dependencies ────────────────────────────────────
print_step "[1/3] Python environment"

cd "$PROJECT_ROOT"

if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pyinstaller

echo "✓ Python $(python3 --version) ready"

# ── Step 2: PyInstaller sidecar binary ─────────────────────────────────────
print_step "[2/3] PyInstaller sidecar"

# Tauri expects binaries named: <name>-<rust-target-triple>
# e.g. rotation-intel-server-aarch64-apple-darwin
TARGET_TRIPLE=$(rustc -vV 2>/dev/null | grep '^host:' | cut -d' ' -f2)
if [ -z "$TARGET_TRIPLE" ]; then
  echo "ERROR: 'rustc' not found. Install Rust: https://rustup.rs"
  exit 1
fi
SIDECAR_NAME="rotation-intel-server-${TARGET_TRIPLE}"

mkdir -p "$SIDECAR_DIR"
mkdir -p "$PROJECT_ROOT/build/pyinstaller-work"

echo "Target: $TARGET_TRIPLE"
echo "Building rotation-intel-server..."

pyinstaller \
  --onefile \
  --name "rotation-intel-server" \
  --distpath "$SIDECAR_DIR" \
  --workpath "$PROJECT_ROOT/build/pyinstaller-work" \
  --specpath "$PROJECT_ROOT/build" \
  \
  --hidden-import "uvicorn.logging" \
  --hidden-import "uvicorn.loops" \
  --hidden-import "uvicorn.loops.auto" \
  --hidden-import "uvicorn.loops.asyncio" \
  --hidden-import "uvicorn.protocols" \
  --hidden-import "uvicorn.protocols.http" \
  --hidden-import "uvicorn.protocols.http.auto" \
  --hidden-import "uvicorn.protocols.http.h11_impl" \
  --hidden-import "uvicorn.protocols.websockets" \
  --hidden-import "uvicorn.protocols.websockets.auto" \
  --hidden-import "uvicorn.protocols.websockets.websockets_impl" \
  --hidden-import "uvicorn.lifespan" \
  --hidden-import "uvicorn.lifespan.on" \
  --hidden-import "uvicorn.lifespan.off" \
  \
  --hidden-import "apscheduler.schedulers.asyncio" \
  --hidden-import "apscheduler.executors.asyncio" \
  --hidden-import "apscheduler.triggers.interval" \
  --hidden-import "apscheduler.triggers.cron" \
  --hidden-import "apscheduler.jobstores.memory" \
  \
  --hidden-import "httpx._transports.default" \
  --hidden-import "httpx._transports.asgi" \
  \
  --hidden-import "fastapi" \
  --hidden-import "fastapi.responses" \
  --hidden-import "starlette.routing" \
  --hidden-import "starlette.middleware" \
  --hidden-import "starlette.middleware.cors" \
  \
  --hidden-import "anthropic" \
  --hidden-import "anthropic._client" \
  --hidden-import "anthropic.types" \
  \
  --collect-all "telethon" \
  --collect-all "anthropic" \
  \
  --exclude-module "pytest" \
  --exclude-module "_pytest" \
  --exclude-module "matplotlib" \
  --exclude-module "numpy" \
  --exclude-module "pandas" \
  \
  --noconfirm \
  "$PROJECT_ROOT/server.py"

# Rename to include the Rust target triple (Tauri naming requirement)
if [ -f "$SIDECAR_DIR/rotation-intel-server" ]; then
  mv "$SIDECAR_DIR/rotation-intel-server" "$SIDECAR_DIR/$SIDECAR_NAME"
  chmod +x "$SIDECAR_DIR/$SIDECAR_NAME"
  echo "✓ Sidecar: src-tauri/binaries/$SIDECAR_NAME"
else
  echo "ERROR: PyInstaller did not produce the expected binary"
  exit 1
fi

# ── Step 3: Icons check ────────────────────────────────────────────────────
print_step "[3/3] Tauri build"

ICONS_DIR="$PROJECT_ROOT/src-tauri/icons"
MISSING_ICONS=()

for f in "32x32.png" "128x128.png" "128x128@2x.png" "icon.icns" "icon.ico" \
         "tray-ready.png" "tray-collecting.png" "tray-error.png"; do
  [ ! -f "$ICONS_DIR/$f" ] && MISSING_ICONS+=("$f")
done

if [ ${#MISSING_ICONS[@]} -gt 0 ]; then
  echo ""
  echo "WARNING: Missing icon files in src-tauri/icons/:"
  for f in "${MISSING_ICONS[@]}"; do echo "  - $f"; done
  echo ""
  echo "To generate all icons from a 1024x1024 source PNG:"
  echo "  npx tauri icon src-tauri/icons/icon-source.png"
  echo ""
  echo "To generate tray status icons (requires ImageMagick):"
  echo "  bash src-tauri/icons/generate-tray-icons.sh"
  echo ""
  echo "Continuing build — icons must exist before final bundle..."
  echo ""
fi

# Install npm dependencies (Tauri CLI)
if [ ! -d "$PROJECT_ROOT/node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install
fi

# Build Tauri app
npm run tauri build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Build complete!"
echo ""
echo "  macOS: src-tauri/target/release/bundle/macos/"
echo "  Windows: src-tauri/target/release/bundle/nsis/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
