#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR/package"
PLUGIN_ID="com.akiflow.panelwidget"

# Install the icon so KDE can find it
ICON_SRC="$PACKAGE_DIR/contents/icons/akiflow.png"
ICON_DST="$HOME/.local/share/icons/hicolor/256x256/apps/akiflow.png"
mkdir -p "$(dirname "$ICON_DST")"
cp "$ICON_SRC" "$ICON_DST"

# Update icon cache (best-effort)
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# Install or update the plasmoid
if kpackagetool6 -t Plasma/Applet -l 2>/dev/null | grep -q "$PLUGIN_ID"; then
    echo "Updating existing Akiflow plasmoid..."
    kpackagetool6 -t Plasma/Applet -u "$PACKAGE_DIR"
else
    echo "Installing Akiflow plasmoid..."
    kpackagetool6 -t Plasma/Applet -i "$PACKAGE_DIR"
fi

# Ensure the cache directory exists
mkdir -p "$HOME/.cache/akiflow"

# Create a sample tray-status.json if it doesn't exist
if [ ! -f "$HOME/.cache/akiflow/tray-status.json" ]; then
    echo '{"title": "", "hasEvent": false, "timestamp": 0}' > "$HOME/.cache/akiflow/tray-status.json"
    echo "Created sample tray-status.json"
fi

echo ""
echo "Done! You can now add the 'Akiflow' widget to your panel:"
echo "  Right-click panel -> Add Widgets -> search 'Akiflow'"
echo ""
echo "To uninstall later:"
echo "  kpackagetool6 -t Plasma/Applet -r $PLUGIN_ID"
