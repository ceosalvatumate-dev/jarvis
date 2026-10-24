#!/bin/bash
# Run by launchd (com.jarvis.meta-sync): hourly, and whenever Jarvis drops data/meta/refresh.request
# ("actualiza los datos de Meta"). Runs outside Claude, so the Meta token never reaches the model.
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$JARVIS_DIR" || exit 1
mkdir -p logs data/meta
rm -f data/meta/refresh.request
[ -e STOP ] && { echo "$(date '+%F %T') skipped: STOP file" >> logs/meta-sync.log; exit 0; }
LOCK="logs/.meta-sync.lock"
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
for f in logs/meta-sync.out logs/meta-sync.err; do   # launchd does not rotate logs
  [ -f "$f" ] && [ "$(wc -c < "$f")" -gt 5000000 ] && : > "$f"
done
exec /usr/bin/env python3 -I "$JARVIS_DIR/bin/meta-sync.py"
