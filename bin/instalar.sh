#!/bin/bash
# bin/instalar.sh — instala Jarvis de Academia Salva Tomate en esta Mac, paso a paso.
# Lo corres TÚ en la Terminal:   bash ~/jarvis/bin/instalar.sh
# Se puede correr varias veces: cada paso revisa si ya está hecho y lo salta.
# Nunca usa sudo, nunca baja un script para ejecutarlo, nunca imprime un token.
set -uo pipefail
JARVIS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$JARVIS_DIR"
CLAUDE_FLOOR="2.1.283"
WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-large-v3-turbo-q5_0.bin"
WHISPER_SHA="394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
TG_DIR="$HOME/.claude/channels/telegram"

b() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok() { printf '  ✓ %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }
ask() { local r; read -r -p "  $1 [s/n] " r; [[ "$r" =~ ^[sSyY] ]]; }
pausa() { read -r -p "  $1 (Enter para seguir) " _; }
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | cut -d' ' -f1 | tr -d '\r"'; }
env_set() {  # env_set KEY VALUE — only for non-secret values
  /usr/bin/python3 -I - "$1" "$2" <<'PY'
import sys, re, pathlib
k, v = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env"); t = p.read_text()
t = re.sub(rf"^{re.escape(k)}=.*$", f"{k}={v}", t, flags=re.M) if re.search(rf"^{re.escape(k)}=", t, re.M) else t + f"\n{k}={v}\n"
p.write_text(t)
PY
}

[ "$(uname)" = "Darwin" ] || { echo "Este instalador es para macOS."; exit 1; }
b "Jarvis · Academia Salva Tomate — instalación en $JARVIS_DIR"
echo "  Te voy guiando. Donde diga 👤, el paso lo haces tú (te digo exactamente cómo)."

# ------------------------------------------------------------------ 1. herramientas
b "1/11 · Herramientas base"
if ! command -v brew >/dev/null; then
  warn "Falta Homebrew (el instalador de programas de Mac)."
  echo "  👤 Abre https://brew.sh, copia la línea que aparece, pégala en otra ventana de Terminal y"
  echo "     sigue sus instrucciones (te pide tu contraseña de la Mac; no se ve al escribirla, es normal)."
  echo "     Luego vuelve a correr: bash $JARVIS_DIR/bin/instalar.sh"
  exit 1
fi
ok "Homebrew"
/usr/bin/python3 -c 'import json,hashlib' 2>/dev/null || { warn "Falta python3 de Apple: corre  xcode-select --install  y elige Instalar."; exit 1; }
ok "python3"
NEED=()
for f in tmux jq gitleaks bun ffmpeg whisper-cpp; do
  bin="$f"; [ "$f" = whisper-cpp ] && bin=whisper-cli
  command -v "$bin" >/dev/null || NEED+=("$( [ "$f" = whisper-cpp ] && echo whisper.cpp || echo "$f")")
done
if [ ${#NEED[@]} -gt 0 ]; then
  echo "  Faltan: ${NEED[*]}"
  if ask "¿Los instalo con brew install ${NEED[*]}?"; then brew install "${NEED[@]}" || exit 1; else exit 1; fi
fi
ok "tmux, jq, gitleaks, bun, ffmpeg, whisper.cpp"

# ------------------------------------------------------------------ 2. Claude Code
b "2/11 · Claude Code"
if ! command -v claude >/dev/null; then
  if ask "Claude Code no está instalado. ¿Lo instalo con  brew install --cask claude-code ?"; then
    brew install --cask claude-code || exit 1
  else exit 1; fi
fi
v="$(claude --version 2>/dev/null | awk '{print $1}')"
if [ "$(printf '%s\n' "$CLAUDE_FLOOR" "$v" | sort -V | head -1)" != "$CLAUDE_FLOOR" ]; then
  warn "Tu Claude Code ($v) es más viejo que el mínimo seguro ($CLAUDE_FLOOR)."
  ask "¿Lo actualizo con  brew upgrade --cask claude-code ?" && brew upgrade --cask claude-code
fi
ok "Claude Code $(claude --version 2>/dev/null | awk '{print $1}')"
if ! claude auth status 2>/dev/null | grep -q '"authMethod": *"claude.ai"'; then
  echo "  👤 Inicia sesión con tu plan Claude Pro/Max: en esta Terminal escribe  claude  , luego  /login ,"
  echo "     elige tu cuenta de Claude (NO 'API key'), y al terminar escribe  /exit ."
  pausa "Cuando hayas iniciado sesión"
  claude auth status 2>/dev/null | grep -q '"authMethod": *"claude.ai"' || { warn "Sigue sin sesión de Claude Pro/Max."; exit 1; }
fi
ok "Sesión de Claude con tu plan (no API)"
/usr/bin/python3 -I - <<'PY'
import json, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"; p.parent.mkdir(exist_ok=True)
d = json.loads(p.read_text()) if p.exists() else {}
d.setdefault("autoUpdatesChannel", "stable"); d["minimumVersion"] = "2.1.283"
p.write_text(json.dumps(d, indent=2) + "\n")
PY
ok "Versión mínima segura fijada en ~/.claude/settings.json"
echo "  👤 Importante: en claude.ai › Configuración › Uso (Usage), deja **Uso extra / Extra usage APAGADO**."
echo "     Así Jarvis nunca te cobra de más: si se acaba el límite del plan, solo espera."
pausa "Cuando lo hayas revisado"
mkdir -p .jarvis && echo "$(date +%F) extra-usage-off confirmado por el dueño" >> .jarvis/consents.log

# ------------------------------------------------------------------ 3. carpeta y archivos
b "3/11 · Carpeta de Jarvis"
mkdir -p logs outbox drafts tasks/archive memory/weekly memory/briefings memory/topics proposals/skills data/meta/history models media-tmp
[ -f .env ] || { cp .env.example .env; ok "Creé .env desde .env.example"; }
chmod 600 .env
[ -f data/ventas.csv ] || cp data/ventas.example.csv data/ventas.csv
[ -f data/presupuesto.json ] || cp data/presupuesto.example.json data/presupuesto.json
chmod 700 bin/*.sh bin/*.py bin/*.command bin/hooks/*.sh jobs/*.sh jobs/*.post .claude/hooks/*.sh .claude/skills/*/scripts/* 2>/dev/null
git config user.name >/dev/null || git config user.name "Jarvis"
git config user.email >/dev/null || git config user.email "jarvis@localhost"
if [ ! -f .git/hooks/pre-commit ]; then
  printf '#!/bin/bash\nexec gitleaks git --pre-commit --staged --redact --no-banner\n' > .git/hooks/pre-commit
  chmod 700 .git/hooks/pre-commit
fi
ok "Carpetas, .env (privado), datos y gitleaks antes de cada commit"

# ------------------------------------------------------------------ 4. modelo de voz
b "4/11 · Notas de voz (whisper local, ~574 MB, una sola vez)"
M="models/ggml-large-v3-turbo-q5_0.bin"
if [ -f "$M" ] && [ "$(shasum -a 256 "$M" | awk '{print $1}')" = "$WHISPER_SHA" ]; then
  ok "Modelo ya descargado y verificado"
elif ask "¿Descargo el modelo de voz a texto (574 MB) para entender tus audios en tu Mac?"; then
  curl -fL --progress-bar -o "$M.part" "$WHISPER_URL" && mv "$M.part" "$M"
  if [ "$(shasum -a 256 "$M" | awk '{print $1}')" = "$WHISPER_SHA" ]; then ok "Modelo verificado (SHA-256 correcto)"
  else rm -f "$M"; warn "El archivo no coincide con su huella SHA-256; lo borré. Corre el instalador otra vez."; fi
else warn "Sin modelo: Jarvis no entenderá notas de voz hasta que lo descargues."; fi
{
  echo "## Medios (generado por bin/instalar.sh el $(date +%F))"
  brew list --versions whisper.cpp ffmpeg 2>/dev/null
  echo "Modelo: $WHISPER_URL"
  [ -f "$M" ] && shasum -a 256 "$M"
} > docs/medios-instalados.md

# ------------------------------------------------------------------ 5. bot de Telegram
b "5/11 · Tu bot de Telegram"
mkdir -p "$TG_DIR" && chmod 700 "$TG_DIR"
[ -f "$TG_DIR/.env" ] || install -m 600 /dev/null "$TG_DIR/.env"
if ! grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$TG_DIR/.env"; then
  echo "  👤 En tu celular, abre Telegram y busca @BotFather (palomita azul)."
  echo "     Escríbele /newbot, ponle de nombre «Jarvis Salva Tomate» y un usuario que termine en bot"
  echo "     (por ejemplo jarvis_salvatomate_bot). Te dará un token largo. NO lo pegues en ningún chat."
  echo "  👤 Ahora se abre TextEdit con un archivo vacío: escribe  TELEGRAM_BOT_TOKEN=  y pega el token"
  echo "     justo después, sin espacios. Guarda con Cmd+S y cierra la ventana."
  pausa "Cuando tengas el token a la mano"
  open -e "$TG_DIR/.env"
  pausa "Cuando lo hayas guardado"
fi
chmod 600 "$TG_DIR/.env"
if ( . "$TG_DIR/.env"; printf 'url = "https://api.telegram.org/bot%s/getMe"\n' "$TELEGRAM_BOT_TOKEN" | curl -fsS -K - | grep -q '"ok":true' ); then
  ok "Bot de Telegram válido"
else warn "Telegram no reconoce el token. Revisa el archivo (corre de nuevo el instalador)."; exit 1; fi
if [ -z "$(env_get OWNER_TELEGRAM_ID)" ]; then
  echo "  👤 En Telegram busca @userinfobot, escríbele cualquier cosa y copia tu número de Id."
  read -r -p "  Tu Id numérico de Telegram: " TGID
  [[ "$TGID" =~ ^[0-9]+$ ]] || { warn "Debe ser solo números."; exit 1; }
  env_set OWNER_TELEGRAM_ID "$TGID"
fi
ok "Tu Id de Telegram está en .env (los reportes llegan solo a ti)"

# ------------------------------------------------------------------ 6. plugin
b "6/11 · Canal de Telegram para Claude Code (plugin oficial, solo en esta carpeta)"
if claude plugin list 2>/dev/null | grep -q 'telegram@claude-plugins-official'; then ok "Plugin instalado"
else
  claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
  if claude plugin install telegram@claude-plugins-official --scope project; then ok "Plugin instalado"
  else
    warn "No pude instalarlo desde aquí. Hazlo a mano: en esta carpeta escribe  claude  y luego"
    echo "     /plugin install telegram@claude-plugins-official   (elige 'project'), y  /exit"
    pausa "Cuando esté instalado"
  fi
fi

# ------------------------------------------------------------------ 7. Meta
b "7/11 · Conectar Meta (Instagram, Facebook y anuncios) — solo lectura"
if [ -z "$(env_get META_ACCESS_TOKEN)" ]; then
  echo "  👤 Sigue RUNBOOK.md § Meta (10 minutos): creas una app de Meta y un usuario del sistema con"
  echo "     permisos de SOLO LECTURA y generas su token. Se abre ahora la guía y luego tu .env en TextEdit:"
  echo "     pega el token después de META_ACCESS_TOKEN= (sin espacios). Guarda con Cmd+S y cierra."
  echo "     Los IDs de página, Instagram y anuncios los busco yo con el token."
  open RUNBOOK.md 2>/dev/null || true
  pausa "Cuando tengas el token de Meta"
  open -e .env
  pausa "Cuando hayas guardado .env"
fi
if [ -n "$(env_get META_ACCESS_TOKEN)" ]; then
  if [ -z "$(env_get META_PAGE_ID)" ] || [ -z "$(env_get META_AD_ACCOUNT_ID)" ]; then
    /usr/bin/env python3 -I bin/meta-sync.py --discover --save
    [ -z "$(env_get META_PAGE_ID)" ] && { echo "  👤 Copia el META_PAGE_ID / META_IG_USER_ID / META_AD_ACCOUNT_ID correctos a .env"; open -e .env; pausa "Guardado"; }
  fi
  if /usr/bin/env python3 -I bin/meta-sync.py --check; then
    /usr/bin/env python3 -I bin/meta-sync.py && ok "Primera foto de Meta en data/meta/summary.md"
    cat data/meta/summary.md 2>/dev/null | head -12
  else warn "Meta rechazó el token. Revisa RUNBOOK.md § Meta y vuelve a correr el instalador."; fi
else warn "Sin Meta por ahora: Jarvis funcionará, pero sin métricas. Vuelve a correr el instalador después."; fi

# ------------------------------------------------------------------ 8. primera sesión
b "8/11 · Primera sesión (confianza + emparejar tu Telegram)"
if [ -f "$TG_DIR/access.json" ] && /usr/bin/python3 -c 'import json,os,sys;a=json.load(open(os.path.expanduser("~/.claude/channels/telegram/access.json")));sys.exit(0 if a.get("dmPolicy")=="allowlist" and len(a.get("allowFrom",[]))==1 else 1)'; then
  ok "Ya está emparejado y con allowlist"
else
  echo "  Se abrirá una ventana de Terminal con tu Jarvis. Ahí:"
  echo "   a) Si pregunta si confías en esta carpeta, elige Yes (flechas y Enter)."
  echo "   b) Desde tu celular mándale «hola» a tu bot. Te responde con un código de 6 letras."
  echo "   c) En la ventana de Jarvis escribe  /telegram:access pair CODIGO  y Enter."
  echo "   d) Luego escribe  /telegram:access policy allowlist  y Enter."
  echo "   e) Para salir sin apagarlo: Control+B, suelta, y luego D."
  pausa "¿Listo para abrirla?"
  bin/jarvis-up.sh
  open bin/jarvis-abrir.command
  pausa "Cuando hayas hecho a)–e)"
fi

# ------------------------------------------------------------------ 9. servicios
b "9/11 · Servicios automáticos (launchd)"
echo "  Instalo 10 servicios de tu usuario (sin sudo): sesión 24/7 con watchdog, reinicio 4:17,"
echo "  colector de Meta cada hora, resumen 7:03, pulso 13:07, piloto 10:13/13:13/16:13,"
echo "  cierre 19:03, tendencias lunes 8:17, revisión viernes 17:03, aprendizaje domingo 19:37."
if ask "¿Los instalo?"; then /usr/bin/env python3 -I bin/launchd.py load; fi

# ------------------------------------------------------------------ 10. energía
b "10/11 · Que tu Mac no se duerma mientras Jarvis trabaja"
echo "  👤 Configuración del Sistema › Batería (o Energía) › Opciones: activa «Evitar reposo automático"
echo "     cuando la pantalla está apagada» (si es laptop, con el cargador conectado). Con la tapa"
echo "     cerrada la Mac duerme: los reportes llegan cuando la abras."
pausa "Hecho"

# ------------------------------------------------------------------ 11. verificación
b "11/11 · Verificación"
bin/verificar.sh
echo
echo "  Prueba final 👤: en Telegram mándale a tu bot «hola», luego «¿cómo vamos?» y"
echo "  «anótame grabar un reel mañana». Para forzar el resumen ahora:  python3 -I bin/launchd.py kick briefing"
