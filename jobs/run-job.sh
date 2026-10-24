#!/usr/bin/env bash
# jobs/run-job.sh <job>: the one wrapper for every scheduled `claude -p` job
# (claude-code-local and claude-p-cron). Canonical copy: knowledge/capabilities/scheduling.md.
set -euo pipefail
JOB="${1:-}"
case "$JOB" in (""|-*|*[!a-z0-9-]*) echo "bad job name" >&2; exit 2;; esac   # no paths, no flags
cd "$(dirname "$0")/.."                                    # the Jarvis folder
mkdir -p outbox logs
STAMP="$(date +%Y-%m-%dT%H%M%S)"; OUT="outbox/$STAMP-$JOB.json"   # seconds: two runs in one minute never overwrite
[ -f STOP ] && { echo "$(date '+%F %T') $JOB skipped: STOP file" >> logs/jobs.log; exit 0; }   # kill switch
if [ "$JOB" = autopilot ]; then                            # autopilot pause: no model call at all
  for f in STOP_AUTOPILOT JARVIS_PAUSED; do
    [ -e "$f" ] && { echo "$(date '+%F %T') $JOB skipped: $f" >> logs/jobs.log; exit 0; }
  done
fi

# Config is parsed, never sourced, never exported. Only non-secret JARVIS_*/OWNER_* settings and
# the model credential are kept; the bot token is skipped here and read only at send time.
cfg_get() { [ -f "$1" ] || return 0; grep -E "^$2=" "$1" | tail -n 1 | cut -d= -f2- | tr -d '\r"' || true; }
load_cfg() {
  [ -f "$1" ] || return 0
  local line k
  while IFS= read -r line || [ -n "$line" ]; do
    k="${line%%=*}"; [ "$k" != "$line" ] || continue
    case "$k" in (JARVIS_*|OWNER_*|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY) ;; (*) continue;; esac
    case "$k" in (*[!A-Z0-9_]*) continue;; esac
    line="${line#*=}"; line="${line%$'\r'}"; line="${line%\"}"; printf -v "$k" '%s' "${line#\"}"
  done < "$1"
}
load_cfg .env                  # OWNER_TELEGRAM_ID, JARVIS_* (models, limits, delivery)
load_cfg jobs/.env.jobs        # claude-code-local only: optional setup-token fallback (mode 600)
[ "${JARVIS_AUTH:-subscription}" = "api_key" ] || unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
DELIVERY="${JARVIS_DELIVERY:-telegram}"                     # telegram | file
TOKEN_FILE="${JARVIS_BOT_TOKEN_FILE:-$HOME/.claude/channels/telegram/.env}"   # claude-p-cron: .env
if [ "$JOB" = autopilot ] && [ -f logs/audit.tsv ]; then  # daily cap: today's autopilot cost_est sum
  SPENT="$(awk -F'\t' -v d="$(date +%Y-%m-%d)" '$2 == "autopilot" && index($1, d) == 1 { v = $5; sub(/^cost_est=/, "", v); s += v } END { printf "%.4f", s + 0 }' logs/audit.tsv)"
  if awk -v s="$SPENT" -v c="${JARVIS_AUTOPILOT_DAILY_USD:-1.00}" 'BEGIN { exit !(s + 0 >= c + 0) }'; then
    echo "$(date '+%F %T') $JOB skipped: daily cap (${SPENT} USD)" >> logs/jobs.log; exit 0; fi
fi

audit() {  # one complete line per run, even when claude is missing or printed nothing
  printf '%s\t%s\trc=%s\terror=%s\tcost_est=%s\tdenied=%s\n' \
    "$STAMP" "$JOB" "${RC:-2}" "${ISERR:-unknown}" "${COST:-0}" "${DENIED:-0}" >> logs/audit.tsv
}
send_telegram() {  # subshell: the token is read at send time, never exported, never in argv
  ( TOK="$(cfg_get "$TOKEN_FILE" TELEGRAM_BOT_TOKEN)"; [ -n "$TOK" ] || exit 1
    printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$TOK" |
      curl -sS --fail --max-time 20 -o /dev/null -K - \
        --data-urlencode "chat_id=${OWNER_TELEGRAM_ID:-}" --data-urlencode "text=$1" 2>/dev/null )
}
fail() {  # never silent: log line, AVISO file in outbox/, Telegram when configured, exit 1
  local msg="AVISO Jarvis: el trabajo '$JOB' falló ($1). Revisa logs/$JOB.stderr y logs/audit.tsv, o corre /jarvis-doctor. Si dice 'Login expired': abre la terminal, ejecuta claude y escribe /login."
  echo "$(date '+%F %T') $JOB FAILED ($1)" >> logs/jobs.log
  printf '%s\n' "$msg" > "outbox/$STAMP-$JOB-AVISO.txt"
  if [ "$DELIVERY" = telegram ] && [ -z "${JARVIS_DRY_RUN:-}" ] && [ -z "${NO_TG:-}" ]; then
    send_telegram "$msg" || echo "telegram send failed" >> "logs/$JOB.stderr"; fi
  exit 1
}
abort() { audit; fail "$1"; }                              # config error before claude ran

LOCK="logs/.$JOB.lock"
mkdir "$LOCK" 2>/dev/null || { echo "$(date '+%F %T') $JOB skipped: previous run still going" >> logs/jobs.log; exit 0; }
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
case "$DELIVERY" in (telegram|file) ;; (*) abort "JARVIS_DELIVERY debe ser telegram o file";; esac

# Job definition: prompt (jobs/<job>.md or a skill), tool list, model slot, optional deny list
if   [ -f "jobs/$JOB.md" ];                 then PROMPT="Run the job described in your instructions."; PFILE=(--append-system-prompt-file "jobs/$JOB.md")
elif [ -f ".claude/skills/$JOB/SKILL.md" ]; then PROMPT="/$JOB"; PFILE=()
else abort "no existe jobs/$JOB.md ni .claude/skills/$JOB/SKILL.md"; fi
for d in .claude/skills skills; do                         # a learned skill on probation never runs unattended
  [ -e "$d/$JOB/.probation" ] && abort "la skill $JOB está en prueba (.probation): úsala una vez en vivo primero"; done
TOOLS="Read,Grep,Glob"
[ -f "jobs/$JOB.tools" ] && { TOOLS="$(tr -s ' \r\n,' ',' < "jobs/$JOB.tools")"; TOOLS="${TOOLS#,}"; TOOLS="${TOOLS%,}"; }
case "$TOOLS" in (""|*'*'*) abort "lista de herramientas vacía o con comodín";; esac
printf '%s\n' "$TOOLS" | tr ',' '\n' | grep -Eq '^(Bash|Edit|Write|NotebookEdit)($|\()|^WebFetch$' \
  && abort "lista de herramientas con shell, escritura o fetch sin dominio"
BUILTIN="$(printf '%s\n' "$TOOLS" | tr ',' '\n' | grep -v '^mcp__' | paste -sd, - || true)"
DENY=(); [ -f "jobs/$JOB.deny" ] && DENY=(--disallowedTools "$(tr -s ' \r\n,' ',' < "jobs/$JOB.deny")")
SLOT=main; [ "$JOB" = heartbeat ] && SLOT=cheap
[ -f "jobs/$JOB.model" ] && SLOT="$(tr -d ' \r\n' < "jobs/$JOB.model")"
case "$SLOT" in
  (cheap) MODEL="${JARVIS_MODEL_CHEAP:-${JARVIS_MODEL_MAIN:-}}";;
  (main)  MODEL="${JARVIS_MODEL_MAIN:-}";;
  (*)     MODEL="";;
esac
[ -n "$MODEL" ] || abort "sin modelo: JARVIS_MODEL_MAIN / JARVIS_MODEL_CHEAP en .env"
[ -f mcp.jobs.json ] || abort "falta mcp.jobs.json"
SETTINGS=(--setting-sources project)                                                     # claude-p-cron
[ -f .claude/headless-settings.json ] && SETTINGS=(--settings .claude/headless-settings.json)   # claude-code-local

# claude gets an explicit, minimal environment: no bot token, nothing inherited by accident
CENV=(HOME="$HOME" PATH="$PATH" USER="${USER:-$(id -un)}" LANG="${LANG:-en_US.UTF-8}" TMPDIR="${TMPDIR:-/tmp}" JARVIS_UNATTENDED=1)   # hooks and bin/ scripts refuse learning here
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && CENV+=(CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN")
[ -n "${ANTHROPIC_API_KEY:-}" ] && CENV+=(ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY")         # only with JARVIS_AUTH=api_key
for k in ${JARVIS_JOB_ENV:-}; do                           # MCP secrets mcp.jobs.json references as ${NAME}
  case "$k" in (*BOT_TOKEN*|*[!A-Z0-9_]*) continue;; esac
  CENV+=("$k=$(cfg_get .env "$k")")
done

set +e
env -i "${CENV[@]}" claude -p "$PROMPT" ${PFILE[@]+"${PFILE[@]}"} "${SETTINGS[@]}" \
  --model "$MODEL" --output-format json \
  --permission-mode dontAsk --permission-prompts none \
  --tools "$BUILTIN" --allowedTools "$TOOLS" ${DENY[@]+"${DENY[@]}"} \
  --strict-mcp-config --mcp-config ./mcp.jobs.json \
  --max-turns "${JARVIS_MAX_TURNS:-12}" --max-budget-usd "${JARVIS_MAX_BUDGET_USD:-0.50}" \
  --no-session-persistence < /dev/null > "$OUT" 2> "logs/$JOB.stderr"
RC=$?
set -e

TEXT=""; ISERR=unknown; COST=0; DENIED=0                   # defaults when the JSON is empty or missing
if [ -s "$OUT" ] && command -v jq >/dev/null && jq -e . "$OUT" >/dev/null 2>&1; then
  TEXT="$(jq -r '.result // empty' "$OUT" 2>/dev/null || true)"
  ISERR="$(jq -r '.is_error // false' "$OUT" 2>/dev/null || echo unknown)"
  COST="$(jq -r '.total_cost_usd // 0' "$OUT" 2>/dev/null || echo 0)"
  DENIED="$(jq -r '(.permission_denials // []) | length' "$OUT" 2>/dev/null || echo 0)"
fi
audit
{ [ "$RC" -eq 0 ] && [ "$ISERR" = false ] && [ -n "$TEXT" ]; } || fail "rc=$RC error=$ISERR"
if [ -f "jobs/$JOB.post" ]; then  # optional post hook (e.g. autopilot → apply-ops.sh); its stdout is what gets delivered
  set +e
  TEXT="$(env -i HOME="$HOME" PATH="$PATH" LANG="${LANG:-en_US.UTF-8}" TMPDIR="${TMPDIR:-/tmp}" \
    /bin/bash "jobs/$JOB.post" "$OUT" 2>> "logs/$JOB.stderr")"; PRC=$?
  set -e
  [ "$PRC" -eq 0 ] || fail "post rc=$PRC"
  [ -n "$TEXT" ] || { echo "$(date '+%F %T') $JOB ok (silent)" >> logs/jobs.log; exit 0; }
fi

case "$TEXT" in (HEARTBEAT_OK*|*HEARTBEAT_OK|NADA)       # nothing to report: stay silent
  echo "$(date '+%F %T') $JOB ok (silent)" >> logs/jobs.log; exit 0;; esac
if [ "$DELIVERY" = telegram ] && [ -z "${JARVIS_DRY_RUN:-}" ]; then
  i=0; while [ "$i" -lt "${#TEXT}" ]; do                 # plain text, 3900-char chunks (cap 4096)
    send_telegram "${TEXT:$i:3900}" || { NO_TG=1; fail "envío a Telegram falló"; }
    i=$((i+3900)); done
fi                                                         # file mode: the result stays in $OUT
[ -f "jobs/$JOB.post" ] && printf '%s\n' "$TEXT" > "outbox/$STAMP-$JOB.txt"   # post-hook text, without the ops block
echo "$(date '+%F %T') $JOB ok" >> logs/jobs.log
