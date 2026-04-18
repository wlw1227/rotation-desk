# RotationDesk Icons

## Required files

| File | Size | How to create |
|------|------|---------------|
| `icon.png` | 1024×1024 | You provide the source PNG |
| `32x32.png` | 32×32 | Auto-generated (see below) |
| `128x128.png` | 128×128 | Auto-generated |
| `128x128@2x.png` | 256×256 | Auto-generated |
| `icon.icns` | — | Auto-generated (macOS) |
| `icon.ico` | — | Auto-generated (Windows) |
| `tray-ready.png` | 22×22 | Script (see below) |
| `tray-collecting.png` | 22×22 | Script |
| `tray-error.png` | 22×22 | Script |

## Step 1 — Create a 1024×1024 app icon

Design or source a 1024×1024 PNG, save it as `src-tauri/icons/icon-source.png`.

Tips for macOS tray icon template mode (`iconAsTemplate: true`):
- Use pure **black** (or dark grey) on a **transparent** background.
- macOS automatically inverts the icon for light/dark menu bar.

## Step 2 — Generate all standard Tauri icon variants

```bash
npx tauri icon src-tauri/icons/icon-source.png
```

This writes `32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico`
(and others) into `src-tauri/icons/`.

## Step 3 — Generate the 3 tray status icons

```bash
bash src-tauri/icons/generate-tray-icons.sh
```

Requires ImageMagick: `brew install imagemagick`

The script creates:
- `tray-ready.png` — green dot (pipeline ready)
- `tray-collecting.png` — amber dot (collecting / synthesizing)
- `tray-error.png` — red dot (pipeline error)

## Coloured vs. template tray icons

The current `tauri.conf.json` sets `"iconAsTemplate": true`, which means macOS
renders the tray icon as a monochrome template. To use the colour dot icons,
change that field to `"iconAsTemplate": false` in `src-tauri/tauri.conf.json`.
