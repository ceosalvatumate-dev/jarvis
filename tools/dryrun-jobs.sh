#!/bin/bash
# tools/dryrun-jobs.sh — offline test of jobs/run-job.sh with a stub `claude` (no login, no network).
# Copies the Jarvis to a temp folder, runs every scheduled job in file-delivery mode and checks:
# the locked-down flags reach claude, the autopilot ops block is applied to TASKS.md, STOP_AUTOPILOT
# skips the run, a silent HEARTBEAT_OK stays silent, and a failing run writes an AVISO.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp -a "$SRC/." "$T/j"; cd "$T/j"
mkdir -p stub logs outbox drafts tasks/archive
cat > .env <<'EOF'
JARVIS_TZ=America/Mexico_City
OWNER_TELEGRAM_ID=1
JARVIS_MODEL_CHEAP=haiku
JARVIS_MODEL_MAIN=sonnet
JARVIS_DELIVERY=file
EOF
chmod 600 .env
# stub claude: records its argv, answers per job, never touches the network
cat > stub/claude <<'EOF'
#!/bin/bash
printf '%s\n' "$@" > "$PWD/logs/stub-args-$$.txt"
env > "$PWD/logs/stub-env-$$.txt"
case "$*" in
  *"/autopilot"*) R='Piloto 10:13 — avancé 1:\n• T-0001 guion del reel: en drafts/T-0001.md\n\n```json\n{"ops": [{"op": "set", "id": "T-0001", "field": "state", "value": "done"}], "drafts": [{"id": "T-0001", "body": "Guion: hook, 3 tips, CTA a la clase gratis."}]}\n```' ;;
  *heartbeat.md*) R='HEARTBEAT_OK' ;;
  *"/tendencias"*) [ -e "$PWD/stub/FAIL" ] && exit 1; R='📈 Tendencias de la semana' ;;
  *) R='Buenos días, CEO.' ;;
esac
R="$(printf '%b' "$R")" python3 -c 'import json,os;print(json.dumps({"result":os.environ["R"],"is_error":False,"total_cost_usd":0.01,"permission_denials":[]}))'
EOF
chmod 700 stub/claude
export PATH="$T/j/stub:$PATH"
cat > TASKS.md.new <<'EOF'
EOF
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("TASKS.md"); t = p.read_text()
t = t.replace("## Hoy\n", "## Hoy\n- [ ] T-0001 · Guion del reel de la clase gratis · state:todo · who:jarvis · lvl:L1 · src:owner/telegram/2026-10-24\n", 1)
p.write_text(t)
PY
rm -f TASKS.md.new
python3 -I tools/parse_tasks.py TASKS.md >/dev/null

pass() { printf '  ✓ %s\n' "$1"; }
fail() { printf '  ✗ %s\n' "$1"; exit 1; }

bash jobs/run-job.sh morning-briefing && grep -q "morning-briefing ok" logs/jobs.log && pass "morning-briefing corre y queda en outbox" || fail morning-briefing
A="$(ls -t logs/stub-args-*.txt | head -1)"
grep -qx -- "--permission-mode" "$A" && grep -qx "dontAsk" "$A" && grep -qx -- "--strict-mcp-config" "$A" \
  && grep -qx ".claude/headless-settings.json" "$A" && grep -qx "sonnet" "$A" && pass "flags bloqueados (dontAsk, strict MCP, headless, modelo main)" || fail flags
E="$(ls -t logs/stub-env-*.txt | head -1)"
! grep -q "TELEGRAM_BOT_TOKEN\|META_ACCESS_TOKEN" "$E" && grep -q "JARVIS_UNATTENDED=1" "$E" && pass "claude no recibe tokens (env -i)" || fail env

bash jobs/run-job.sh heartbeat && grep -q "heartbeat ok (silent)" logs/jobs.log && pass "heartbeat silencioso con HEARTBEAT_OK" || fail heartbeat
grep -qx "haiku" "$(ls -t logs/stub-args-*.txt | head -1)" && pass "heartbeat usa el modelo barato" || fail heartbeat-model

bash jobs/run-job.sh autopilot && grep -q "autopilot ok" logs/jobs.log && pass "autopilot ok" || fail autopilot
grep -q "T-0001 .*state:done" TASKS.md && test -s drafts/T-0001.md && pass "ops block aplicado: T-0001 done + borrador" || fail apply-ops
python3 -I tools/parse_tasks.py TASKS.md >/dev/null && pass "TASKS.md sigue válido" || fail parse
! grep -q '"ops"' "$(ls -t outbox/*-autopilot.txt | head -1)" && pass "el aviso no lleva el bloque de operaciones" || fail note

touch STOP_AUTOPILOT
N=$(ls outbox | wc -l)
bash jobs/run-job.sh autopilot && grep -q "autopilot skipped: STOP_AUTOPILOT" logs/jobs.log && [ "$(ls outbox | wc -l)" = "$N" ] && pass "STOP_AUTOPILOT detiene el piloto sin llamar a claude" || fail stop
rm STOP_AUTOPILOT

touch stub/FAIL; set +e; bash jobs/run-job.sh tendencias; RC=$?; set -e; rm stub/FAIL
[ "$RC" = 1 ] && ls outbox/*-tendencias-AVISO.txt >/dev/null && grep -q "tendencias FAILED" logs/jobs.log && pass "una falla nunca es silenciosa (AVISO + exit 1)" || fail aviso
grep -q "WebSearch" "$(ls -t logs/stub-args-*.txt | head -1)" && pass "tendencias tiene WebSearch" || fail websearch

set +e; bash jobs/run-job.sh "../etc"; RC=$?; set -e
[ "$RC" = 2 ] && pass "nombre de trabajo con ruta rechazado" || fail badname
echo "ok dryrun: todos los trabajos pasan"
