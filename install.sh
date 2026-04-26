#!/bin/bash
# Akiflow Linux Installer (unofficial)
# Extracts Windows exe and runs via system electron

set -e

AKIFLOW_VERSION="2.70.7"
AKIFLOW_URL="https://download.akiflow.com/builds/Akiflow-${AKIFLOW_VERSION}-6676a46d-x64.exe"
INSTALL_DIR="$HOME/.local/share/akiflow"
BIN_DIR="$HOME/.local/bin"

echo "=== Akiflow Linux Installer (unofficial) ==="
echo ""

# Check dependencies
for cmd in 7z electron; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is required but not installed."
        case $cmd in
            7z) echo "  Install with: sudo pacman -S p7zip" ;;
            electron) echo "  Install with: sudo pacman -S electron" ;;
        esac
        exit 1
    fi
done

# Create directories
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# Download
echo "[1/4] Downloading Akiflow ${AKIFLOW_VERSION}..."
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
curl -L -o Akiflow.exe "$AKIFLOW_URL"

# Extract
echo "[2/4] Extracting..."
7z x -y Akiflow.exe -oextracted > /dev/null

# Find and copy app.asar
echo "[3/4] Installing..."
ASAR_PATH=$(find extracted -name 'app.asar' -type f | head -1)
if [ -z "$ASAR_PATH" ]; then
    echo "Error: Could not find app.asar in extracted files"
    rm -rf "$TEMP_DIR"
    exit 1
fi

RESOURCES_DIR=$(dirname "$ASAR_PATH")
cp "$RESOURCES_DIR/app.asar" "$INSTALL_DIR/"
[ -d "$RESOURCES_DIR/app.asar.unpacked" ] && cp -r "$RESOURCES_DIR/app.asar.unpacked" "$INSTALL_DIR/"

# Try to extract icon
if command -v wrestool &> /dev/null && command -v icotool &> /dev/null; then
    EXE_FILE=$(find extracted -name '*.exe' -type f | grep -i akiflow | head -1)
    if [ -n "$EXE_FILE" ]; then
        wrestool -x -t 14 "$EXE_FILE" -o akiflow.ico 2>/dev/null || true
        if [ -f "akiflow.ico" ]; then
            icotool -x akiflow.ico 2>/dev/null || true
            ICON_256=$(ls akiflow_*256x256*.png 2>/dev/null | head -1)
            [ -n "$ICON_256" ] && cp "$ICON_256" "$INSTALL_DIR/akiflow.png"
        fi
    fi
fi

# Create launcher
echo "[4/4] Creating launcher..."
cat > "$BIN_DIR/akiflow" << 'EOF'
#!/bin/sh
exec electron "$HOME/.local/share/akiflow/app.asar" "$@"
EOF
chmod +x "$BIN_DIR/akiflow"

# Create desktop entry
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/akiflow.desktop" << EOF
[Desktop Entry]
Name=Akiflow
GenericName=Task Management
Comment=Time blocking and task management
Exec=$BIN_DIR/akiflow %u
Icon=$INSTALL_DIR/akiflow.png
Type=Application
Terminal=false
Categories=Office;ProjectManagement;Calendar;
MimeType=x-scheme-handler/akiflow;
StartupWMClass=Akiflow
EOF

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Run with: akiflow"
echo "  (make sure $BIN_DIR is in your PATH)"
echo ""
echo "Or run directly: electron $INSTALL_DIR/app.asar"
