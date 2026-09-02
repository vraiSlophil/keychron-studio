#!/usr/bin/env bash
# Install Keychron Studio as a double-clickable app in your GNOME app grid.
set -euo pipefail
APPDIR="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$APPS" "$ICONS"
sed "s|__APPDIR__|$APPDIR|g" "$APPDIR/packaging/keychron-studio.desktop" \
    > "$APPS/com.github.vraislophil.keychron_studio.desktop"
cp "$APPDIR/packaging/icons/keychron-studio.svg" "$ICONS/keychron-studio.svg"
chmod +x "$APPS/com.github.vraislophil.keychron_studio.desktop"
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Installed. Search 'Keychron Studio' in your apps — double-click to launch."
echo "Tip: right-click its grid icon → 'Pin to Dash', or copy the .desktop to ~/Desktop."
