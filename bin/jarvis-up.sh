#!/bin/bash
# Start the Jarvis channel session if it is not running; restart it if it leaks past the RSS cap.
set -euo pipefail
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # absolute path of this Jarvis folder
cd "$JARVIS_DIR"
mkdir -p logs
[ -e STOP_ALL ] && { echo "$(date '+%F %T') jarvis-up skipped: STOP_ALL" >> logs/jarvis-up.log; exit 0; }
cfg_get() { [ -f .env ] || return 0; grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- | cut -d' ' -f1 | tr -d '\r"' || true; }
S="$(cfg_get JARVIS_TMUX_SESSION)"; S="${S:-jarvis}"
CAP="$(cfg_get JARVIS_RSS_CAP_KB)"; CAP="${CAP:-3145728}"
# The channel session needs no secrets from .env: the Meta token is read only by bin/meta-sync.py,
# the bot token only by the Telegram plugin. Subscription /login only (SEC-30):
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN META_ACCESS_TOKEN META_APP_SECRET
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$HOME/.bun/bin:/usr/bin:/bin"
export LANG="${LANG:-es_MX.UTF-8}"

# Largest RSS among processes started with --channels (claude itself, not caffeinate/bun).
PIDS=$(pgrep -f -- '--channels plugin:' | paste -sd, - || true)
RSS=0; [ -n "$PIDS" ] && RSS=$(ps -o rss= -p "$PIDS" | sort -n | tail -1 | tr -d ' ')
if [ "${RSS:-0}" -gt "$CAP" ]; then
  echo "$(date '+%F %T') RSS ${RSS} KB > cap, restarting" >> logs/jarvis-up.log
  tmux kill-session -t "$S" 2>/dev/null || true
fi
tmux has-session -t "$S" 2>/dev/null && exit 0

KEEPAWAKE=""; [ "$(uname)" = "Darwin" ] && KEEPAWAKE="caffeinate -i"
echo "$(date '+%F %T') starting session $S" >> logs/jarvis-up.log
tmux new-session -d -s "$S" -c "$JARVIS_DIR" \
  "$KEEPAWAKE claude --channels plugin:telegram@claude-plugins-official \
     --permission-mode auto --settings $JARVIS_DIR/.claude/launch-settings.json"
