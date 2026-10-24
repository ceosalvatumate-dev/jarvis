#!/usr/bin/env python3
"""bin/launchd.py — writes (and optionally loads) Jarvis's macOS LaunchAgents. No secrets in any plist.

  python3 -I bin/launchd.py write     render the plists into ~/Library/LaunchAgents (no load)
  python3 -I bin/launchd.py load      write + launchctl bootstrap each one (idempotent)
  python3 -I bin/launchd.py unload    launchctl bootout + delete the plists
  python3 -I bin/launchd.py list      show which agents are loaded
  python3 -I bin/launchd.py kick <label-suffix>   force a run now, e.g. `kick briefing`

Schedules are local time (America/Mexico_City on a Mac set to Mexico). launchd has no ranges, so
each weekday/hour gets its own StartCalendarInterval dict. Off-minutes avoid the :00/:30 jitter.
"""
import os, plistlib, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LA = Path.home() / "Library" / "LaunchAgents"
PREFIX = "com.jarvis.salvatomate"
MON_FRI, MON_SAT = [1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6]


def path_env():
    dirs = []
    claude = shutil.which("claude")
    if claude:
        dirs.append(str(Path(claude).parent))
    dirs += [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".bun/bin"),
             "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return ":".join(out)


def cal(days, hours, minute):
    return [{"Weekday": d, "Hour": h, "Minute": minute} for d in days for h in hours]


def job(name, args, calendar=None, interval=None, watch=None, run_at_load=False, abandon=False):
    p = {
        "Label": f"{PREFIX}.{name}",
        "ProgramArguments": args,
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {"PATH": path_env(), "LANG": "es_MX.UTF-8", "LC_ALL": "es_MX.UTF-8",
                                 "TZ": "America/Mexico_City", "JARVIS_HOME": str(ROOT)},
        "ProcessType": "Background",
        "Umask": 63,
        "StandardOutPath": str(ROOT / "logs" / f"{name}.out"),
        "StandardErrorPath": str(ROOT / "logs" / f"{name}.err"),
    }
    if calendar:
        p["StartCalendarInterval"] = calendar
    if interval:
        p["StartInterval"] = interval
    if watch:
        p["WatchPaths"] = watch
    if run_at_load:
        p["RunAtLoad"] = True
    if abandon:
        p["AbandonProcessGroup"] = True
    return p


def agents():
    sh = ["/bin/bash"]
    run = lambda j: sh + [str(ROOT / "jobs" / "run-job.sh"), j]
    return [
        # the always-on Telegram session (watchdog every 5 min) + nightly restart at 04:17
        job("session", sh + [str(ROOT / "bin" / "jarvis-up.sh")], interval=300, run_at_load=True, abandon=True),
        job("restart", sh + [str(ROOT / "bin" / "jarvis-restart.sh")], calendar=[{"Hour": 4, "Minute": 17}], abandon=True),
        # Meta collector: hourly 06:51–21:51 and on demand (Jarvis writes data/meta/refresh.request)
        job("meta-sync", sh + [str(ROOT / "bin" / "meta-sync-run.sh")],
            calendar=[{"Hour": h, "Minute": 51} for h in range(6, 22)],
            watch=[str(ROOT / "data" / "meta" / "refresh.request")]),
        job("briefing", run("morning-briefing"), calendar=cal(MON_SAT, [7], 3)),
        job("heartbeat", run("heartbeat"), calendar=cal(MON_SAT, [13], 7)),
        job("autopilot", run("autopilot"), calendar=cal(MON_FRI, [10, 13, 16], 13)),
        job("cierre", run("cierre-del-dia"), calendar=cal(MON_SAT, [19], 3)),
        job("tendencias", run("tendencias"), calendar=cal([1], [8], 17)),
        job("weekly", run("weekly-review"), calendar=cal([5], [17], 3)),
        job("learning", sh + [str(ROOT / "bin" / "learn.sh"), "weekly"], calendar=cal([0], [19], 37)),
    ]


def target(label):
    return f"gui/{os.getuid()}/{label}"


def write():
    LA.mkdir(parents=True, exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "data" / "meta").mkdir(parents=True, exist_ok=True)
    out = []
    for a in agents():
        f = LA / f"{a['Label']}.plist"
        with f.open("wb") as fh:
            plistlib.dump(a, fh)
        subprocess.run(["plutil", "-lint", str(f)], check=True, stdout=subprocess.DEVNULL)
        out.append(f)
    return out


def load():
    for f in write():
        label = f.stem
        subprocess.run(["launchctl", "bootout", target(label)], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(f)], check=True)
        print("cargado", label)


def unload():
    for a in agents():
        subprocess.run(["launchctl", "bootout", target(a["Label"])], stderr=subprocess.DEVNULL)
        (LA / f"{a['Label']}.plist").unlink(missing_ok=True)
        print("quitado", a["Label"])


def listing():
    rc = 0
    for a in agents():
        ok = subprocess.run(["launchctl", "print", target(a["Label"])], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode == 0
        rc |= 0 if ok else 1
        print(("✓ " if ok else "✗ ") + a["Label"])
    return rc


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if sys.platform != "darwin" and cmd != "write-test":
        sys.exit("launchd.py es solo para macOS")
    if cmd == "write":
        for f in write():
            print("escrito", f)
    elif cmd == "load":
        load()
    elif cmd == "unload":
        unload()
    elif cmd == "list":
        sys.exit(listing())
    elif cmd == "kick" and len(sys.argv) > 2:
        subprocess.run(["launchctl", "kickstart", "-k", target(f"{PREFIX}.{sys.argv[2]}")], check=True)
        print("lanzado", sys.argv[2])
    elif cmd == "write-test":  # CI on Linux: render into a temp dir and validate with plistlib
        import tempfile
        LA = Path(tempfile.mkdtemp())
        for a in agents():
            f = LA / f"{a['Label']}.plist"
            f.write_bytes(plistlib.dumps(a))
            assert plistlib.loads(f.read_bytes())["Label"] == a["Label"]
        print(f"ok {len(agents())} plists válidos")
    else:
        sys.exit(__doc__)
