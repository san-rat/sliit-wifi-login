#!/bin/bash
# Setup script for macOS — installs a launchd agent that runs sliit-login.py
# on every network change and every 30 minutes.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.sliit-login.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
PYTHON="$(which python3 2>/dev/null)"

if [ -z "$PYTHON" ]; then
    echo "Error: python3 not found. Install it from https://python.org or via Homebrew."
    exit 1
fi

echo "Python: $PYTHON"
echo "Script: $SCRIPT_DIR/sliit-login.py"

# Check credentials
if [ ! -f "$SCRIPT_DIR/credentials.json" ]; then
    echo ""
    echo "No credentials.json found."
    echo "Copy credentials.example.json to credentials.json and fill in your username/password:"
    echo "  cp credentials.example.json credentials.json"
    echo "  nano credentials.json"
    exit 1
fi

# Protect credentials file
chmod 600 "$SCRIPT_DIR/credentials.json"

# Unload existing agent if present
launchctl list | grep -q "com.sliit-login" && launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Generate plist
cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sliit-login</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/sliit-login.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WatchPaths</key>
    <array>
        <string>/etc/resolv.conf</string>
        <string>/Library/Preferences/SystemConfiguration</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl load "$PLIST_DEST"

echo ""
echo "Done! The agent is now running."
echo "It will auto-login whenever you connect to SLIIT WiFi."
echo ""
echo "Useful commands:"
echo "  Check logs:    tail -f $SCRIPT_DIR/sliit-login.log"
echo "  Manual run:    python3 $SCRIPT_DIR/sliit-login.py"
echo "  Uninstall:     launchctl unload $PLIST_DEST && rm $PLIST_DEST"
