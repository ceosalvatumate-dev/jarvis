# RUNBOOK — Jarvis de Academia Salva Tomate

Todo se hace desde la Terminal de tu Mac, en la carpeta `~/jarvis`. Si algo no está aquí, usa el
Jarvis Architect: `git clone https://github.com/Hainrixz/jarvis-architect ~/jarvis-architect`,
`cd ~/jarvis-architect && claude`, y escribe `/jarvis-doctor` (salud) o `/jarvis-add` (agregar
WhatsApp, Hotmart/Stripe, Gmail, panel web, más trabajos). Nunca abras `claude` dentro de
`~/jarvis` mientras Jarvis corre: le robaría el bot de Telegram.

## Instalar (una sola vez, ~30 min)
```bash
git clone -b claude/jarvis-academia-salva-tomate https://github.com/ceosalvatumate-dev/jarvis.git ~/jarvis
bash ~/jarvis/bin/instalar.sh
```
El instalador te guía en 11 pasos, se puede repetir y salta lo que ya está hecho. Los pasos donde
haces algo tú: iniciar sesión en Claude, apagar «Uso extra», crear el bot con @BotFather, tu Id
de @userinfobot, el token de Meta (abajo) y emparejar Telegram.

## Lo de todos los días (por Telegram)
| Le dices | Hace |
|---|---|
| «¿cómo vamos?», «¿cuántos mensajes sin contestar?», «¿cuánto llevo gastado en anuncios?» | Te contesta con los datos de Meta (skill `metricas`) |
| «actualiza los datos» | Pide al colector una foto nueva de Meta (≈1 min) |
| «vendí 2 del curso X a 1500» | Registra la venta en `data/ventas.csv` |
| «mi presupuesto de anuncios de este mes es 15 mil y mi meta son 40 ventas» | Actualiza `data/presupuesto.json` (te pide confirmar) |
| «anótame grabar el reel el jueves», «¿qué tengo pendiente?» | Pendientes en `TASKS.md` |
| «la academia es de …», «mis competidores son …» | Afina `data/sector.md` para las tendencias |
| «tendencias», «ideas de contenido» | Reporte de tendencias al momento |
| una nota de voz | La transcribe en tu Mac y te contesta |
| «no, así no: …» / «deshaz» | Aprende la corrección / la quita |
| «pausa el piloto» | Detiene el piloto automático |

## Horarios automáticos (hora de México)
| Cuándo | Qué |
|---|---|
| Cada hora 6:51–21:51 | Colector de Meta → `data/meta/` (no te escribe) |
| L–S 7:03 | Resumen de la mañana |
| L–V 10:13, 13:13, 16:13 | Piloto: prepara borradores de tus pendientes `who:jarvis` (silencio si no hay nada) |
| L–S 13:07 | Pulso: solo te escribe si hay mensajes sin contestar > 4 h o gasto raro |
| L–S 19:03 | Cierre del día |
| Lunes 8:17 | Tendencias del sector |
| Viernes 17:03 | Revisión semanal |
| Domingo 19:37 | Resumen de lo que aprendió |
| 4:17 diario | Reinicio de la sesión (memoria fresca) |

Forzar uno ahora: `python3 -I ~/jarvis/bin/launchd.py kick briefing` (o `heartbeat`, `cierre`,
`tendencias`, `weekly`, `autopilot`, `meta-sync`).

## Encender, apagar, ver
| Acción | Comando |
|---|---|
| Ver la sesión en vivo | doble clic en `~/jarvis/bin/jarvis-abrir.command` (salir sin apagar: Control+B, luego D) |
| Reiniciar la sesión | `~/jarvis/bin/jarvis-restart.sh` |
| Apagar la sesión (vuelve en ≤5 min por el watchdog) | `tmux kill-session -t jarvis` |
| Apagar TODO hasta nuevo aviso | `touch ~/jarvis/STOP ~/jarvis/STOP_ALL && tmux kill-session -t jarvis` |
| Volver a encender | `rm ~/jarvis/STOP ~/jarvis/STOP_ALL && ~/jarvis/bin/jarvis-up.sh` |
| Pausar solo el piloto | por Telegram «pausa el piloto», o `touch ~/jarvis/STOP_AUTOPILOT` |
| Reanudar el piloto (solo desde aquí, nunca por chat) | `rm ~/jarvis/STOP_AUTOPILOT` |
| Quitar los servicios automáticos | `python3 -I ~/jarvis/bin/launchd.py unload` |
| Revisar la salud | `~/jarvis/bin/verificar.sh` |
| Logs | `~/jarvis/logs/` (`jobs.log`, `meta-sync.log`, `audit.tsv`, `audit.jsonl`, `jarvis-up.log`) |

## Meta
Jarvis lee Meta con un **usuario del sistema** de tu portafolio comercial: un token que no caduca,
con permisos de solo lectura, que no depende de tu sesión personal. El token lo usa solo
`bin/meta-sync.py`; Claude nunca lo ve.

### Paso a paso (≈10 min, desde una computadora)
1. **Crea la app.** Entra a https://developers.facebook.com/apps › **Crear app**. Caso de uso: «Otro»;
   tipo: **Negocios (Business)**. Nombre: «Jarvis Salva Tomate». Vincúlala a tu portafolio comercial
   (el de la academia). No hace falta publicarla ni pedir revisión: en modo desarrollo funciona con
   tus propias cuentas.
2. **Agrega productos a la app** (en el panel de la app › Agregar producto): *Marketing API* e
   *Instagram* (configuración «API con inicio de sesión de Facebook»). Si te pregunta por Messenger,
   agrégalo también.
3. **Crea el usuario del sistema.** https://business.facebook.com/settings › Usuarios › **Usuarios del
   sistema** › Agregar › nombre «jarvis-lectura», rol **Empleado** (no Administrador).
4. **Asígnale activos** (botón «Asignar activos»), solo lectura donde se pueda:
   - **Página** de Facebook de la academia: «Ver contenido», «Ver estadísticas», «Mensajes» (para
     leer conversaciones). Nada de «Crear contenido» ni «Anuncios».
   - **Cuenta de Instagram**: acceso a estadísticas y mensajes.
   - **Cuenta publicitaria**: **Ver rendimiento** (no «Administrar campañas»).
   - **App** «Jarvis Salva Tomate»: Desarrollar app.
5. **Genera el token.** En el usuario del sistema › **Generar token** › app «Jarvis Salva Tomate» ›
   caducidad **Nunca** › marca SOLO estos permisos:
   `pages_show_list`, `pages_read_engagement`, `read_insights`, `pages_messaging`,
   `instagram_basic`, `instagram_manage_insights`, `instagram_manage_messages`, `ads_read`,
   `business_management`.
   **No** marques `ads_management`, `pages_manage_posts`, `instagram_content_publish` ni
   `pages_manage_metadata`.
6. **Copia el token** (se muestra una sola vez) y pégalo en `~/jarvis/.env` después de
   `META_ACCESS_TOKEN=` (el instalador te abre el archivo en TextEdit). Nunca lo pegues en un chat,
   ni en Telegram ni con Claude.
7. **Permite leer mensajes de Instagram:** en la app de Instagram › Configuración › Mensajes y
   respuestas a historias › Controles de mensajes › Herramientas conectadas › activa **Permitir
   acceso a los mensajes**.
8. **IDs automáticos:** `python3 -I ~/jarvis/bin/meta-sync.py --discover --save` encuentra y guarda
   el ID de la página, del Instagram vinculado y de la cuenta publicitaria.
9. **Prueba:** `python3 -I ~/jarvis/bin/meta-sync.py --check` (dice `ok` y los nombres de los
   permisos) y luego `python3 -I ~/jarvis/bin/meta-sync.py` (escribe `data/meta/summary.md`).
10. Opcional, más seguro: en la app › Configuración › Básica copia la **clave secreta** a
    `META_APP_SECRET=` en `.env` (firma cada llamada con `appsecret_proof`).

### Si algo falla
| Ves | Qué hacer |
|---|---|
| `errors` con «190» o «token» en `data/meta/latest.json` | Token revocado o vencido: repite los pasos 5–6 |
| «mensajes instagram: … (#200) / (#10)» | Falta el paso 7, o el permiso `instagram_manage_messages`/«Mensajes» en el paso 4 |
| «anuncios …: (#200)» | El usuario del sistema no tiene la cuenta publicitaria asignada (paso 4) |
| Una métrica con `error` «invalid metric» | Meta la retiró (pasa seguido). El resto sigue funcionando; avísale a Jarvis Architect con `/jarvis-doctor` |
| `generated_at` viejo | ¿La Mac estuvo dormida? `python3 -I bin/launchd.py kick meta-sync` y revisa `logs/meta-sync.log` |

### Qué guarda el colector
Conteos de mensajes por día, conversaciones sin contestar (solo **nombre de pila** y horas de
espera, nunca el texto), métricas de página e Instagram, tus últimas 15 publicaciones (texto
recortado a 100 caracteres) y gasto/resultados de anuncios por cuenta y campaña. Todo en
`data/meta/` en tu Mac, fuera de git. La foto de cada día queda en `data/meta/history/`.

## Medios
Notas de voz: whisper.cpp en tu Mac con `models/ggml-large-v3-turbo-q5_0.bin`
(SHA-256 `394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2`, del commit
`5359861c` de huggingface.co/ggerganov/whisper.cpp). Las versiones instaladas quedan en
`docs/medios-instalados.md` al correr el instalador. Nada de audio sale de la Mac.

Videos: por ahora solo los que mandas como archivo. Para habilitar enlaces (YouTube, reels), lee
esto: *Para ver videos de un link, Jarvis lee sus subtítulos y, si preguntas qué se ve, baja una copia
temporal. Los términos de YouTube no permiten descargar salvo lo autorizado: úsalo solo para tu
consulta personal; nunca usa tus cookies ni tu cuenta y borra todo al terminar.* Si aceptas:
`brew install yt-dlp`, agrega en `docs/jarvis-spec.md` § 7 la fila
`| AAAA-MM-DD | video-urls-terms — aceptado | sí |` y borra el punto 0 de
`.claude/skills/watch-video/SKILL.md` (los dos a mano, desde la Mac). Actualiza yt-dlp cada mes con
`brew upgrade yt-dlp`.

## Actualizar
- Claude Code: `brew upgrade --cask claude-code` (el piso seguro es 2.1.283; Homebrew no se
  actualiza solo). Luego `~/jarvis/bin/jarvis-restart.sh`.
- Herramientas: `brew upgrade tmux jq bun ffmpeg whisper.cpp gitleaks`.
- Jarvis (este repo): `cd ~/jarvis && git pull` y `python3 -I bin/launchd.py load`.

## Deshacer lo aprendido
Por Telegram «deshaz», o `~/jarvis/bin/learn.sh undo` en la terminal. Todo aprendizaje queda en git
(`git log -p LESSONS.md`).

## Costo
$0 extra: usa tu plan Claude Pro/Max. Si Jarvis y tú agotan el límite del plan, Jarvis deja de
contestar hasta que se reinicie la ventana (nunca cobra extra con «Uso extra» apagado). Revisa
claude.ai › Configuración › Uso después de la primera semana; si se queda corto, sube a Max o pide
a `/jarvis-add` menos trabajos. La API de Meta es gratuita.

## Exportar o borrar todo
- Exportar: `cd ~ && zip -r jarvis-respaldo.zip jarvis -x 'jarvis/models/*' 'jarvis/media-tmp/*'`
  (incluye `.env`: guárdalo en un lugar seguro).
- Borrar: `python3 -I ~/jarvis/bin/launchd.py unload`, `tmux kill-session -t jarvis`, borra
  `~/jarvis` y `~/.claude/channels/telegram/`, y revoca los tokens (SECURITY.md).

## Problemas
| Síntoma | Qué hacer |
|---|---|
| El bot no contesta | `~/jarvis/bin/verificar.sh`; si «Sesión de Jarvis viva» ✗ → `bin/jarvis-up.sh`; si «Poller» ✗ → otra sesión de Claude con el plugin se robó el bot: ciérrala y `bin/jarvis-restart.sh` |
| Un AVISO «Login expired» | Abre la sesión (`jarvis-abrir.command`), escribe `/login`, luego Control+B, D |
| Los reportes no llegan | `tail ~/jarvis/logs/jobs.log`; si dice `rc=127`, launchd no encuentra `claude`: corre `python3 -I bin/launchd.py load` otra vez |
| Pide permisos en Telegram todo el rato | Es el modo «auto» apagado del lado de Claude; responde con los botones o espera a que vuelva |
