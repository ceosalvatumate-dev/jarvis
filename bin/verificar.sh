#!/bin/bash
# bin/verificar.sh — health check (claude-code-local Verify + learning § 9 + autonomy + Meta).
# Prints ✓/✗ per check, never a secret. Exit 0 only when every check passes.
#   bin/verificar.sh          full check on the Mac
#   bin/verificar.sh --static only the checks that need no Mac, no login and no network (CI)
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$JARVIS_DIR" || exit 1
STATIC=0; [ "${1:-}" = "--static" ] && STATIC=1
FAIL=0
chk() { local name="$1"; shift; if ( eval "$@" ) >/dev/null 2>&1; then printf '  ✓ %s\n' "$name"; else printf '  ✗ %s\n' "$name"; FAIL=1; fi; }
mode() { stat -f %Lp "$1" 2>/dev/null || stat -c %a "$1" 2>/dev/null; }
TG="$HOME/.claude/channels/telegram"

echo "Archivos y configuración"
chk "JSON válidos (settings, launch, headless, mcp)" 'for f in .claude/settings.json .claude/launch-settings.json .claude/headless-settings.json .mcp.json mcp.jobs.json; do python3 -m json.tool "$f" >/dev/null || exit 1; done'
chk "Headless = sandbox idéntico + plugin apagado" 'python3 -c "import json;h=json.load(open(\".claude/headless-settings.json\"));l=json.load(open(\".claude/launch-settings.json\"));assert h[\"enabledPlugins\"][\"telegram@claude-plugins-official\"] is False and h[\"sandbox\"]==l[\"sandbox\"]"'
chk "Sandbox estricto" 'python3 -c "import json;s=json.load(open(\".claude/launch-settings.json\"))[\"sandbox\"];assert s[\"enabled\"] and s[\"allowUnsandboxedCommands\"] is False and s[\"failIfUnavailable\"] is True and s[\"network\"][\"strictAllowlist\"]"'
chk "run-job.sh usa headless-settings" 'grep -q "headless-settings.json" jobs/run-job.sh'
chk "Nunca skip-permissions" '! grep -rq --exclude=verificar.sh "dangerously-skip""-permissions" bin/ jobs/ .claude/'
chk "jarvis-up.sh quita llaves de API" 'grep -q "^unset ANTHROPIC_API_KEY" bin/jarvis-up.sh && ! grep -q "env.jobs" bin/jarvis-up.sh'
chk "Sin {{marcadores}} pendientes" '! grep -rnE "\{\{[a-z_]+\}\}" --include=*.md . | grep -v "^./docs/LICENSE" | grep -q .'
chk "Scripts ejecutables" 'for f in bin/learn.sh bin/promote-skill.sh bin/hooks/capture-correction.sh bin/hooks/learn-nudge.sh bin/hooks/protect-paths.sh bin/jarvis-up.sh bin/meta-sync.py jobs/run-job.sh jobs/apply-ops.sh jobs/autopilot.post .claude/hooks/guard.sh .claude/hooks/audit.sh; do test -x "$f" || exit 1; done'
chk "autopilot.post y cierre-del-dia.post idénticos" 'cmp -s jobs/autopilot.post jobs/cierre-del-dia.post'
chk "Aprendizaje: hooks, sin auto-memoria, LESSONS importado" 'python3 -c "import json;s=json.load(open(\".claude/settings.json\"));assert s[\"autoMemoryEnabled\"] is False and s[\"hooks\"][\"UserPromptSubmit\"] and s[\"hooks\"][\"Stop\"]" && grep -q "^@LESSONS.md" CLAUDE.md'
chk "LESSONS.md sin contenido de permisos" '! grep -Eiq "allowlist|sin preguntar|without asking|api[ _-]?key|token|permis|aprobaci[oó]n autom" LESSONS.md'
chk "protect-paths bloquea AGENTS.md" 'printf "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"AGENTS.md\",\"content\":\"x\"},\"cwd\":\"%s\"}" "$PWD" | CLAUDE_PROJECT_DIR="$PWD" bin/hooks/protect-paths.sh | grep -q "\"deny\""'
chk "guard.sh bloquea leer tokens" 'printf "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"cat ~/.claude/channels/telegram/.env\"}}" | .claude/hooks/guard.sh | grep -q "\"deny\""'
chk "TASKS.md válido" 'python3 -I tools/parse_tasks.py TASKS.md'
chk "Lista L3 vacía" 'sed -n "/^## 10\./,/^## /p" AGENTS.md | grep -q "ninguna (lista vacía)"'
chk "Colector de Meta (prueba offline)" 'NO_PROXY=127.0.0.1 no_proxy=127.0.0.1 python3 -I tools/test_meta_sync.py'
chk ".env fuera de git" 'git check-ignore -q .env && git check-ignore -q data/meta/latest.json && git check-ignore -q data/ventas.csv'
[ "$STATIC" = 1 ] && { [ "$FAIL" = 0 ] && echo "OK (estático)" || echo "HAY FALLAS"; exit $FAIL; }

echo "Mac, sesión y canal"
chk "Claude Code ≥ 2.1.283" 'v=$(claude --version | awk "{print \$1}"); [ "$(printf "%s\n" 2.1.283 "$v" | sort -V | head -1)" = 2.1.283 ]'
chk "Sesión con plan Claude (no API)" 'claude auth status 2>/dev/null | grep -q "\"authMethod\": *\"claude.ai\""'
chk "Sin llaves de modelo en .env" '! grep -Eq "^(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN|TELEGRAM_BOT_TOKEN)=" .env'
chk ".env privado (600)" 'test "$(mode .env)" = 600'
chk "bun, tmux, jq, ffmpeg, whisper-cli" 'command -v bun && command -v tmux && command -v jq && command -v ffmpeg && command -v whisper-cli'
chk "Modelo de voz verificado" 'test "$(shasum -a 256 models/ggml-large-v3-turbo-q5_0.bin | cut -d" " -f1)" = 394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2'
chk "Token de Telegram privado" 'test "$(mode "$TG/.env")" = 600 && grep -q "^TELEGRAM_BOT_TOKEN=.\+" "$TG/.env"'
chk "Bot de Telegram válido" '( . "$TG/.env"; printf "url = \"https://api.telegram.org/bot%s/getMe\"\n" "$TELEGRAM_BOT_TOKEN" | curl -fsS -K - | grep -q "\"ok\":true" )'
chk "OWNER_TELEGRAM_ID definido" 'grep -Eq "^OWNER_TELEGRAM_ID=[0-9]+" .env'
chk "Allowlist: solo tú" 'python3 -c "import json,os;a=json.load(open(os.path.expanduser(\"~/.claude/channels/telegram/access.json\")));assert a.get(\"dmPolicy\")==\"allowlist\" and len(a.get(\"allowFrom\",[]))==1 and a[\"allowFrom\"][0].isdigit() and not a.get(\"groups\")"'
chk "Sesión de Jarvis viva" 'tmux has-session -t "$(grep -E "^JARVIS_TMUX_SESSION=" .env | cut -d= -f2 | cut -d" " -f1)"'
chk "Poller de Telegram vivo" 'ps -p "$(cat "$TG/bot.pid")" -o args= | grep -q server.ts'
chk "Servicios launchd cargados" 'python3 -I bin/launchd.py list'
chk "Datos de Meta recientes (< 3 h)" 'python3 -c "import json,datetime as d;s=json.load(open(\"data/meta/latest.json\"));t=d.datetime.fromisoformat(s[\"generated_at\"]);assert (d.datetime.now(d.timezone.utc)-t).total_seconds()<10800"'
chk "gitleaks: historial sin secretos" 'gitleaks git --no-banner --redact .'
[ "$FAIL" = 0 ] && echo "TODO OK" || echo "HAY FALLAS: revisa las líneas con ✗ (RUNBOOK.md § Problemas)"
exit $FAIL
