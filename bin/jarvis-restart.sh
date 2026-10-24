#!/bin/bash
# Nightly fresh session (memory-leak cap, expired-login refresh). Run by com.jarvis.salvatomate.restart.
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
S="$(grep -E '^JARVIS_TMUX_SESSION=' "$JARVIS_DIR/.env" 2>/dev/null | tail -n 1 | cut -d= -f2- | cut -d' ' -f1 | tr -d '\r"')"
tmux kill-session -t "${S:-jarvis}" 2>/dev/null
exec "$JARVIS_DIR/bin/jarvis-up.sh"
