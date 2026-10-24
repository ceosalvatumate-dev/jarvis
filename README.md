# Jarvis · Academia Salva Tomate

Tu asistente personal en Telegram. Corre en tu Mac con tu plan Claude Pro/Max, sin costo extra.
Te dice en todo momento qué pasa en la academia:

- 💬 **Mensajes** de Instagram y Messenger: recibidos, contestados, sin contestar (y desde hace
  cuánto) y tiempo de respuesta.
- 💰 **Anuncios de Meta**: gasto de hoy, de ayer, de 7 días y del mes; resultados y costo por
  resultado por campaña; presupuesto usado contra el plan y proyección del mes.
- 📊 **Redes**: alcance, vistas, interacciones, seguidores (y su cambio) y mejores publicaciones.
- 🧾 **Ventas**: las registras por chat («vendí 2 del curso X a 1500»); calcula la meta, el costo
  por venta y el ROAS real.
- ✅ **Pendientes**: los anota, te los recuerda y el piloto automático prepara borradores.
- 📈 **Tendencias** del sector cada lunes, con 3 ideas conectadas a tus números.
- 🎙️ Entiende tus **notas de voz** (en tu Mac) y aprende de tus correcciones.

Hecho con [Jarvis Architect](https://github.com/Hainrixz/jarvis-architect) (MIT), runtime
`claude-code-local`. Diseño completo: [`docs/jarvis-spec.md`](docs/jarvis-spec.md).

## Instalar en tu Mac
```bash
git clone -b claude/jarvis-academia-salva-tomate https://github.com/ceosalvatumate-dev/jarvis.git ~/jarvis
bash ~/jarvis/bin/instalar.sh
```
Guía completa y uso diario: [RUNBOOK.md](RUNBOOK.md) · Seguridad y botón de pánico:
[SECURITY.md](SECURITY.md).

## Cómo está armado
| Pieza | Archivo |
|---|---|
| Personalidad, perfil, reglas, herramientas | `SOUL.md`, `USER.md`, `AGENTS.md`, `TOOLS.md` (cargados por `CLAUDE.md`) |
| Memoria, pendientes, lecciones | `MEMORY.md` + `memory/`, `TASKS.md`, `LESSONS.md` |
| Colector de Meta (solo lectura, fuera del modelo) | `bin/meta-sync.py` → `data/meta/` |
| Ventas, presupuesto, sector | `data/ventas.csv`, `data/presupuesto.json`, `data/sector.md` |
| Habilidades | `.claude/skills/` (metricas, registrar-venta, tendencias, morning-briefing, pending, autopilot, learn, remember, transcribe, watch-video, weekly-review, draft-reply) |
| Trabajos programados | `jobs/` + `bin/launchd.py` |
| Seguridad | `.claude/settings.json`, `.claude/launch-settings.json` (sandbox), `.claude/hooks/`, `bin/hooks/` |
| Pruebas | `bin/verificar.sh`, `tools/test_meta_sync.py`, `tools/dryrun-jobs.sh` |
