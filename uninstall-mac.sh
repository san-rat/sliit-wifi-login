#!/bin/bash
# Uninstall the SLIIT WiFi auto-login agent on macOS.

PLIST="$HOME/Library/LaunchAgents/com.sliit-login.plist"

if launchctl list | grep -q "com.sliit-login"; then
    launchctl unload "$PLIST"
    echo "Agent unloaded."
fi

[ -f "$PLIST" ] && rm "$PLIST" && echo "Plist removed."

echo "Done. You can delete this folder to fully remove."
