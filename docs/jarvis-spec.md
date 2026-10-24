# Jarvis spec — Jarvis (Academia Salva Tomate)

Generated: 2026-10-24 · Architect: Hainrixz/jarvis-architect (main, knowledge verified 2026-10-06), modo express

## 1. Who and what for
- Owner: CEO · Profession pack: creator (secundario: founder) · Country: México (America/Mexico_City, MXN)
- Week-one jobs:
  1. Cada mañana (07:03): mensajes de Instagram y Messenger recibidos/contestados/sin contestar, gasto de anuncios vs presupuesto, ventas y pendientes.
  2. Pulso de mediodía (13:07): alerta si hay prospectos sin contestar > 4 h o gasto fuera de lo normal; silencio si todo va bien.
  3. Lunes 08:17: tendencias del sector, competencia, Instagram y Meta Ads, con 3 ideas conectadas a los números de la cuenta.

## 2. Non-Goals (v1)
| Not in this version | Why |
|---|---|
| Contestar DMs o comentarios a alumnos/prospectos | IRR-P2 y política de Meta para bots; Jarvis solo prepara borradores (`draft-reply`) |
| Pausar, activar o mover presupuesto de campañas | IRR-P1; token solo con `ads_read` |
| Publicar en Instagram/Facebook | IRR-02; sin `pages_manage_posts` / `instagram_content_publish` |
| WhatsApp | No hay canal oficial para este runtime; se agrega después con `/jarvis-add` (Cloud API) |
| Pasarela de pagos (Hotmart, Stripe, Mercado Pago) | El dueño no marcó ninguna; ventas se registran por chat en `data/ventas.csv` |
| Panel web | Telegram cubre v1; se agrega con `/jarvis-add` |
| Videos desde enlaces | Sin consentimiento de términos de YouTube todavía; solo archivos |

## 3. Architecture
| Slot | Choice | Reason | Source |
|---|---|---|---|
| Host | Mac del dueño + launchd (watchdog 5 min, reinicio 04:17), `caffeinate -i` | $0 hosting, sin puertos abiertos | knowledge/capabilities/deploy-local.md |
| Runtime | claude-code-local, Claude Code ≥ 2.1.283 (stable 2.1.285) | Ya paga Claude Pro/Max; único arnés que cumple con la suscripción | knowledge/runtimes/claude-code-local.md |
| Credential | `/login` claude.ai (Pro/Max) en el binario oficial, sin API key | auth-matrix: CLI interactivo + `--channels`, columna local | knowledge/auth-matrix.md |
| Models | cheap haiku · main sonnet · max opus (alias de Claude Code) | Alias sobreviven al retiro de modelos | knowledge/models.json (verified 2026-10-06) |
| Channels | Telegram (`telegram@claude-plugins-official`, long polling, allowlist = solo el dueño) | Gratis, oficial, outbound only | knowledge/capabilities/channels.md |
| Memory | Markdown (MEMORY.md + memory/), auto-memoria apagada | Portable y versionada en git | knowledge/capabilities/memory.md |
| Tools / MCP | Colector propio `bin/meta-sync.py` (Graph API v26.0, solo lectura, fuera del modelo) → `data/meta/`; WebSearch; archivos `data/` | El token de Meta nunca entra al contexto del modelo; sin MCP de terceros | knowledge/capabilities/tools-mcp.md |
| Jobs | morning-briefing L–S 07:03 · heartbeat L–S 13:07 · autopilot L–V 10:13/13:13/16:13 · cierre-del-dia L–S 19:03 · tendencias L 08:17 · weekly-review V 17:03 · learning-review D 19:37 · meta-sync 06:51–21:51 cada hora + a pedido | Pack creator + estándar | knowledge/capabilities/scheduling.md |
| Autonomy | level L1 · l3_types ninguna · daily_usd 1.00 · autopilot `13 10,13,16 * * 1-5` | Prepara, el dueño decide | knowledge/capabilities/autonomy.md |
| Learning | mode: automatic (lecciones al instante + skills en prueba) · native: claude auto memory off · channels: telegram | | knowledge/capabilities/learning.md |
| Multimodal | stt: local · model: ggml-large-v3-turbo-q5_0 · video: on (solo archivos; enlaces off) · gemini: off | Nada sale de la Mac | knowledge/capabilities/multimodal.md |
| ↳ Voice | ninguna (voz de salida apagada; notas de voz de entrada sí) | | knowledge/capabilities/voice.md |
| Face / UI | Telegram + terminal (sin panel) | | knowledge/capabilities/web-ui.md |

## 4. Security controls (knowledge/security-checklist.md)
| ID | Control | How it is implemented here | Verified by |
|---|---|---|---|
| SEC-01 | Owner-only allowlist | `access.json` dmPolicy allowlist, 1 ID numérico | `bin/verificar.sh` "Allowlist: solo tú" |
| SEC-02 | Grupos apagados | `groups: {}` | idem |
| SEC-04 | Pairing solo en la terminal | AGENTS.md § 1; guard.sh bloquea `access.json` y `channels/` | verificar "guard.sh bloquea leer tokens" |
| SEC-05/06 | Sin plano de control público | Nada escucha; Telegram long polling | — |
| SEC-07 | Sandbox | launch/headless-settings: enabled, sin comandos fuera, failIfUnavailable | verificar "Sandbox estricto" |
| SEC-08 | Rutas de credenciales ilegibles | denyRead + deny `Read(**/.env)` | verificar "JSON válidos" |
| SEC-09 | Egress allowlist | `allowedDomains: [wttr.in]`, strictAllowlist; WebFetch en `ask` | verificar |
| SEC-10 | Sin bypass; destructivo bloqueado | `--permission-mode auto`; guard.sh; deny list | verificar "Nunca skip-permissions" |
| SEC-11 | Rule of Two | § 5 | — |
| SEC-12 | Contenido externo = datos | AGENTS.md § 2; skills metricas/tendencias lo repiten | — |
| SEC-13 | Higiene de memoria | Tags de origen; sin IDs/tarjetas; `remember` olvida | verificar "LESSONS.md sin permisos" |
| SEC-14 | Aprobación con vista previa | AGENTS.md § 3 + IRR-P1/P2; `ask` para editar presupuesto, rm, curl, WebFetch | — |
| SEC-15 | Desatendido sin IRR | run-job.sh: dontAsk + tools Read/Grep/Glob(+WebSearch) | `tools/dryrun-jobs.sh` |
| SEC-16 | Aprobación caduca y se liga | Relay de Telegram con ID por petición; SOUL/AGENTS 5 min | — |
| SEC-17/18 | Secretos en archivos 600, nunca en chat/log | Bot token en `~/.claude/channels/telegram/.env` (600); Meta en `.env` (600) leído solo por meta-sync; gitleaks pre-commit | verificar ".env privado", `tools/test_meta_sync.py` "token leaked" |
| SEC-19 | Entorno mínimo | `env -i` en jobs; `jarvis-up.sh` quita META_* y llaves de modelo; sandbox envVars deny | dryrun "claude no recibe tokens" |
| SEC-20 | Logs redactados | audit.sh guarda hash; meta-sync redacta tokens | test_meta_sync |
| SEC-21 | Rotación | SECURITY.md botón de pánico | — |
| SEC-22 | Integraciones solo lectura | Permisos Meta de lectura; colector sin ninguna llamada de escritura | código `bin/meta-sync.py` (solo GET) |
| SEC-23 | Perfiles mínimos | Sin `Bash(*)` ni `mcp__*` | — |
| SEC-24 | Sin auto-instalar | Solo plugin oficial; sin MCP de terceros | — |
| SEC-25/26 | Piso + instalación segura | `minimumVersion 2.1.283`; brew; modelo whisper con SHA-256 | verificar |
| SEC-27 | Tope de gasto | Plan Pro/Max con «Uso extra» apagado (person-confirmed, `.jarvis/consents.log`) | instalar.sh paso 2 |
| SEC-28 | Límites + kill switch | max-turns 12, budget 0.50/corrida, piloto 1 USD/día, STOP / STOP_AUTOPILOT / tmux kill | dryrun |
| SEC-29 | Auditoría | `logs/audit.jsonl`, `logs/audit.tsv`, `logs/meta-sync.log` | weekly-review |
| SEC-30 | Credencial = celda de la matriz | `/login` only; unset de llaves | verificar "Sesión con plan Claude" |
| SEC-31 | WhatsApp no oficial | N/A | — |
| SEC-32 | Data-flow disclosure | SECURITY.md § Flujo de datos | — |
| SEC-33 | Revisión semanal | weekly-review + `bin/verificar.sh` | — |
| SEC-34/35 | Piloto solo prepara; reanudar solo en terminal | apply-ops.sh; protect-paths niega quitar STOP | dryrun "STOP_AUTOPILOT" |
| SEC-36/37 | Aprendizaje sin permisos, auditado | protect-paths + learn.sh | verificar |
| SEC-38 | Medios | scripts de skill con límites, carpeta temporal, sin enlaces de terceros | — |

## 5. Rule of Two map
| Capability | Untrusted input [A] | Private data [B] | External action [C] | Approval required? |
|---|---|---|---|---|
| Métricas de Meta (`metricas`, briefing, heartbeat) | yes (nombres, captions, campañas) | yes (números del negocio) | no (solo lectura; el modelo nunca ve el token) | No (solo lectura) |
| Registrar ventas | no (solo el dueño en vivo) | yes | no (archivo local) | Corregir/borrar = IRR-04 |
| Tendencias (WebSearch) | yes | yes (lee data/) | no | No (solo lectura) |
| Borradores de respuesta | yes | yes | no (solo borrador) | Enviar = IRR-P2, lo hace el dueño en Meta |
| Autopilot | yes (data/ y web vía tareas) | yes | no (L3 list empty) | L2 via "sí, ejecuta T-N" |
| Video fetch (`watch-video`) | yes (the video, its captions) | no | no | Solo archivos enviados por el dueño (enlaces off) |

## 6. Cost
- Model: ~$0/month extra (plan Claude Pro/Max ya pagado; trabajos ≈ 22 briefings + 26 pulsos + 66 piloto + 26 cierres + 4 tendencias + 4 semanales al mes, dentro de los límites del plan) · Hosting: $0 (Mac propia) · Other: Graph API de Meta $0
- Provider spend cap: $0 extra («Uso extra» apagado en claude.ai) · Railway usage limit: N/A

## 7. Decisions and consents
| Date | Decision / consent | Person's answer |
|---|---|---|
| 2026-10-24 | Arquitectura: Telegram, en la Mac, plan Claude Pro/Max, Meta solo lectura, México | Sí, constrúyelo así (AskUserQuestion) |
| 2026-10-24 | Nivel de autonomía L1, piloto 3×/día hábil, tope 1 USD/día; lista L3 vacía | Acepto (AskUserQuestion) |
| 2026-10-24 | Aprendizaje automático con aviso y «deshaz» | Acepto (AskUserQuestion) |
| 2026-10-24 | Audio y video en la computadora (local); nube de voz a texto: no; videos de enlaces: no aceptado todavía (video: solo archivos) | Por defecto seguro |
| pendiente | «Uso extra» apagado en claude.ai (SEC-27) | person-confirmed en `bin/instalar.sh` → `.jarvis/consents.log` |

## 8. Risks
| Risk | Mitigation |
|---|---|
| La Mac se duerme o se apaga: no llegan reportes | `caffeinate -i`, ajuste de energía (instalar.sh paso 10); launchd corre al despertar; los prompts tienen guardia de "llegó tarde" |
| Se agotan los límites del plan Claude | Trabajos en haiku salvo briefing/tendencias/semanal; revisar Uso tras la primera semana; «Uso extra» apagado = nunca cobra |
| Meta cambia o retira métricas (v26 retiró varias) | El colector pide cada métrica por separado y registra `errors` sin fallar; `META_GRAPH_VERSION` configurable |
| Token de Meta caduca o se revoca | Token de usuario del sistema (no caduca por defecto); heartbeat avisa si los datos tienen > 3 h; RUNBOOK § Meta para regenerar |
| Channels es research preview | Piso de versión + `/jarvis-doctor`; fallback: trabajos `claude -p` siguen llegando por Bot API |
| Prompt injection desde DMs/captions | El colector solo guarda conteos, nombre de pila y captions recortados; AGENTS § 2; sin herramientas de envío |

## 9. Compliance notes
LFPDPPP (México): el colector guarda solo nombre de pila y antigüedad de conversaciones sin contestar, en la Mac (`data/meta/`, fuera de git); no guarda textos de mensajes, teléfonos ni correos. Si en el futuro Jarvis responde a alumnos, actualizar el aviso de privacidad de la academia (nombrar a Anthropic y Meta como encargados). Uso de Claude: personal del dueño (Consumer Terms); nadie más puede hablar con el bot.

## 10. Runbook pointers
Jarvis folder: ~/jarvis · Start: `bin/jarvis-up.sh` · Stop: `tmux kill-session -t jarvis` (y `python3 -I bin/launchd.py unload`) · Logs: `logs/` · Health: `bin/verificar.sh`
