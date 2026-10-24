#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-$(command -v python3)}
PLIST="$HOME/Library/LaunchAgents/com.manick.repsy.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.repsy"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.manick.repsy</string>
  <key>ProgramArguments</key><array><string>$PYTHON</string><string>$ROOT/app.py</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$HOME/.repsy/repsy.log</string>
  <key>StandardErrorPath</key><string>$HOME/.repsy/repsy.err.log</string>
</dict></plist>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
printf 'Installed %s\n' "$PLIST"
