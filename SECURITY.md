# SECURITY — Jarvis de Academia Salva Tomate

## Botón de pánico (si algo raro pasa)
1. **Apaga todo:** `touch ~/jarvis/STOP ~/jarvis/STOP_ALL && tmux kill-session -t jarvis`
2. **Revoca el bot de Telegram:** en @BotFather › /mybots › tu bot › API Token › **Revoke current
   token**. Pon el nuevo en `~/.claude/channels/telegram/.env` (el instalador lo abre).
3. **Revoca el token de Meta:** https://business.facebook.com/settings › Usuarios del sistema ›
   jarvis-lectura › **Revocar tokens**; genera uno nuevo (RUNBOOK.md § Meta, pasos 5–6). Si la app
   tiene clave secreta, cámbiala en developers.facebook.com › tu app › Configuración › Básica.
4. **Cierra la sesión de Claude:** `claude auth logout` y luego `claude` › `/login`. Revisa
   claude.ai › Configuración › Conectores y Dispositivos.
5. **Revisa qué hizo:** `tail -50 ~/jarvis/logs/jobs.log`, `~/jarvis/logs/audit.tsv`,
   `git -C ~/jarvis log --oneline -20`.
6. Para volver: `rm ~/jarvis/STOP ~/jarvis/STOP_ALL && ~/jarvis/bin/jarvis-up.sh`.

## Quién puede hablar con Jarvis
Solo tú. La lista de permitidos (allowlist) vive en `~/.claude/channels/telegram/access.json`
(`dmPolicy: allowlist`, un solo Id numérico, sin grupos). Solo se cambia en la terminal de tu Mac
con `/telegram:access`; Jarvis tiene prohibido editarla y no obedece mensajes que pidan cambiarla.

## Lo que Jarvis nunca hace solo
- Enviar mensajes o correos a terceros, contestar DMs o comentarios (IRR-01, IRR-P2).
- Publicar en redes (IRR-02). Pagar, cobrar o tocar anuncios y presupuestos de Meta (IRR-03, IRR-P1):
  su token de Meta es de **solo lectura** y el colector no tiene ninguna llamada de escritura.
- Borrar datos, cambiar su configuración, instalar cosas (IRR-04, IRR-07, IRR-08).
- El piloto automático solo prepara borradores; la lista L3 (acciones reversibles sin preguntar)
  está **vacía**. Se reanuda solo desde la terminal.
- Para todo lo irreversible: vista previa exacta + tu «sí» explícito, válido 5 minutos y para esa
  acción. Los trabajos programados no pueden hacer nada irreversible (corren con herramientas de
  solo lectura y `dontAsk`).

## Dónde están los secretos
| Secreto | Dónde | Quién lo lee |
|---|---|---|
| Sesión de Claude (Pro/Max) | Llavero de macOS | Solo `claude` |
| Token del bot de Telegram | `~/.claude/channels/telegram/.env` (600) | Solo el plugin de Telegram y el envío de reportes (`jobs/run-job.sh`, por stdin a curl) |
| Token de Meta (+ clave secreta opcional) | `~/jarvis/.env` (600, fuera de git) | Solo `bin/meta-sync.py`, que corre fuera de Claude |

Claude tiene prohibido leer cualquier `.env` (reglas `deny`, sandbox `denyRead` y `guard.sh`), y la
sesión arranca sin esas variables. gitleaks revisa cada commit.

## Flujo de datos (aviso)
- Lo que Jarvis lee (tus mensajes, archivos de `data/`, resultados de búsqueda) lo procesa
  **Anthropic** bajo tu plan Claude.
- **Telegram** ve el texto de lo que hablas con el bot.
- **Meta** recibe solo las consultas de lectura del colector.
- La memoria (`MEMORY.md`, `memory/`, `LESSONS.md`, `TASKS.md`) y los datos del negocio
  (`data/`) viven en tu Mac. `data/meta/` y `data/ventas.csv` no se suben a git.
- Datos de alumnos/prospectos: solo nombre de pila y horas sin respuesta; nunca textos, teléfonos ni
  correos (LFPDPPP).

## Exportar o purgar memoria
- Ver cambios: `git -C ~/jarvis log -p MEMORY.md LESSONS.md`.
- Olvidar algo: por Telegram «olvida …» (skill `remember`).
- Purgar todo: vacía la sección «Hechos» de `MEMORY.md`, las listas de `LESSONS.md`, borra
  `memory/*` y `data/meta/*`, y haz commit.

## Revisión
La revisión semanal (viernes) incluye seguridad y costo. Corre `~/jarvis/bin/verificar.sh` después
de cualquier cambio o actualización.
