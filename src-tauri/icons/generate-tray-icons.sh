#!/usr/bin/env bash
# generate-tray-icons.sh
# Creates the three 22x22 tray status indicator icons.
# Requires ImageMagick (brew install imagemagick).

set -euo pipefail
ICONS_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v convert &>/dev/null; then
  echo "ERROR: ImageMagick 'convert' not found."
  echo "Install: brew install imagemagick"
  exit 1
fi

echo "Generating tray status icons..."

# Green  — pipeline ready
convert -size 22x22 xc:transparent \
  -fill '#00e676' -draw 'circle 11,11 11,3' \
  "$ICONS_DIR/tray-ready.png"
echo "✓ tray-ready.png"

# Amber  — pipeline collecting / synthesizing
convert -size 22x22 xc:transparent \
  -fill '#ffab00' -draw 'circle 11,11 11,3' \
  "$ICONS_DIR/tray-collecting.png"
echo "✓ tray-collecting.png"

# Red    — pipeline error
convert -size 22x22 xc:transparent \
  -fill '#ff3d5a' -draw 'circle 11,11 11,3' \
  "$ICONS_DIR/tray-error.png"
echo "✓ tray-error.png"

echo ""
echo "Done. Run 'npx tauri icon <source-1024.png>' to generate the app icons."
