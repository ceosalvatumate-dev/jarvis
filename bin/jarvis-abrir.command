#!/bin/bash
# Doble clic en Finder: abre la sesión de Jarvis en Terminal. Para salir SIN apagarlo: Control+B, luego D.
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$JARVIS_DIR/bin/jarvis-up.sh"
S="$(grep -E '^JARVIS_TMUX_SESSION=' "$JARVIS_DIR/.env" 2>/dev/null | tail -n 1 | cut -d= -f2- | cut -d' ' -f1 | tr -d '\r"')"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
exec tmux attach -t "${S:-jarvis}"
