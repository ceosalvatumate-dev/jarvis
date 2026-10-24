#!/usr/bin/env python3
"""bin/meta-sync.py — read-only Meta collector for Academia Salva Tomate's Jarvis.

Runs OUTSIDE Claude (launchd, every hour), so the Meta token never enters the model's context.
It only issues GET requests to the Graph API and writes:
  data/meta/latest.json          full snapshot (what Jarvis reads)
  data/meta/summary.md           short human summary in Spanish
  data/meta/history/YYYY-MM-DD.json   last snapshot of each day (trends, follower deltas)
  logs/meta-sync.log             one line per run, never the token

Usage:
  bin/meta-sync.py            collect everything
  bin/meta-sync.py --check    verify the token and list granted permission NAMES (prints no secret)
  bin/meta-sync.py --discover [--save]   list page / Instagram / ad-account IDs the token sees
                              (--save fills the empty META_*_ID lines in .env when there is one of each)

Config: parsed (never sourced) from .env: META_ACCESS_TOKEN, META_PAGE_ID, META_IG_USER_ID,
META_AD_ACCOUNT_ID, META_GRAPH_VERSION (default v26.0), META_APP_SECRET (optional, adds
appsecret_proof), JARVIS_TZ. META_GRAPH_BASE overrides the API host (tests only).
Python 3.9+ standard library only.
"""
import csv, datetime as dt, hashlib, hmac, json, os, statistics, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
META_DIR = DATA / "meta"
KEYS = ("META_ACCESS_TOKEN", "META_PAGE_ID", "META_IG_USER_ID", "META_AD_ACCOUNT_ID",
        "META_GRAPH_VERSION", "META_APP_SECRET", "META_GRAPH_BASE", "JARVIS_TZ")

PAGE_METRICS = ["page_media_view", "page_total_media_view_unique", "page_post_engagements",
                "page_follows", "page_daily_follows_unique", "page_views_total"]
IG_METRICS = ["reach", "views", "accounts_engaged", "total_interactions", "follows_and_unfollows",
              "profile_links_taps", "website_clicks"]
IG_MEDIA_METRICS = "views,reach,saved,shares,total_interactions"
ACTION_LABELS = {
    "purchase": "compras", "offsite_conversion.fb_pixel_purchase": "compras (píxel)",
    "lead": "leads", "onsite_conversion.lead_grouped": "leads (formulario)",
    "onsite_conversion.messaging_conversation_started_7d": "conversaciones iniciadas",
    "complete_registration": "registros", "landing_page_view": "visitas a la página",
    "link_click": "clics al enlace", "onsite_conversion.messaging_first_reply": "primeras respuestas",
}
RESULT_ORDER = ["purchase", "offsite_conversion.fb_pixel_purchase", "lead", "onsite_conversion.lead_grouped",
                "complete_registration", "onsite_conversion.messaging_conversation_started_7d"]


def load_cfg():
    cfg = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in KEYS:
                v = v.split(" #", 1)[0].strip().strip('"').strip("'")
                cfg[k] = v
    for k in KEYS:  # tests and one-off runs may pass values in the environment
        if os.environ.get(k):
            cfg.setdefault(k, os.environ[k])
    return cfg


class GraphError(Exception):
    pass


class Graph:
    def __init__(self, token, version, app_secret=None, base=None):
        self.token = token
        self.version = version
        self.app_secret = app_secret
        self.base = (base or "https://graph.facebook.com").rstrip("/")
        self.calls = 0

    def _url(self, path, params, token):
        q = dict(params or {})
        q["access_token"] = token
        if self.app_secret:
            q["appsecret_proof"] = hmac.new(self.app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        if path.startswith("http"):
            return path  # pagination URL from Meta already carries the token
        return f"{self.base}/{self.version}/{path.lstrip('/')}?{urllib.parse.urlencode(q)}"

    def get(self, path, params=None, token=None):
        url = self._url(path, params, token or self.token)
        self.calls += 1
        req = urllib.request.Request(url, headers={"User-Agent": "jarvis-meta-sync/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8")).get("error", {})
                msg = f"{err.get('type', 'HTTP')} {err.get('code', e.code)}: {err.get('message', '')}"
            except Exception:
                msg = f"HTTP {e.code}"
            raise GraphError(redact(msg, self.token)) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise GraphError(f"red: {type(e).__name__}") from None

    def paged(self, path, params=None, token=None, max_pages=5):
        data = self.get(path, params, token)
        pages = 1
        while True:
            for item in data.get("data", []):
                yield item
            nxt = (data.get("paging") or {}).get("next")
            if not nxt or pages >= max_pages:
                return
            data = self.get(nxt, token=token)
            pages += 1


def redact(text, *secrets):
    for s in secrets:
        if s and len(s) > 8:
            text = text.replace(s, "[REDACTED]")
    return text[:300]


def num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0
    if isinstance(v, dict):  # breakdown values, e.g. {"organic": 10, "paid": 5}
        return sum(num(x) for x in v.values())
    return 0


def parse_time(s):
    # Graph returns 2026-10-24T13:05:11+0000
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def ctx_dates(tz):
    now = dt.datetime.now(tz)
    today = now.date()
    yday = today - dt.timedelta(days=1)
    return now, today, yday


def day_bounds(d, tz):
    start = dt.datetime.combine(d, dt.time(0, 0), tz)
    return start, start + dt.timedelta(days=1)


# ----------------------------------------------------------------------------------- sections

def collect_page(g, cfg, page_token, tz, errors):
    pid = cfg["META_PAGE_ID"]
    out = {"id": pid}
    try:
        info = g.get(pid, {"fields": "name,followers_count,fan_count"}, page_token)
        out.update({k: info.get(k) for k in ("name", "followers_count", "fan_count")})
    except GraphError as e:
        errors.append(f"página: {e}")
    now, today, yday = ctx_dates(tz)
    since = int(day_bounds(today - dt.timedelta(days=7), tz)[0].timestamp())
    until = int(day_bounds(today, tz)[0].timestamp())
    ins = {}
    for m in PAGE_METRICS:
        try:
            r = g.get(f"{pid}/insights", {"metric": m, "period": "day", "since": since, "until": until}, page_token)
            vals = []
            for series in r.get("data", []):
                for v in series.get("values", []):
                    vals.append((v.get("end_time", ""), num(v.get("value"))))
            if vals:
                vals.sort()
                ins[m] = {"yesterday": vals[-1][1], "last_7d": sum(v for _, v in vals)}
        except GraphError as e:
            ins[m] = {"error": str(e)[:120]}
    out["insights"] = ins
    return out


def collect_instagram(g, cfg, token, tz, errors):
    ig = cfg["META_IG_USER_ID"]
    out = {"id": ig}
    try:
        info = g.get(ig, {"fields": "username,followers_count,follows_count,media_count"}, token)
        out.update({k: info.get(k) for k in ("username", "followers_count", "follows_count", "media_count")})
    except GraphError as e:
        errors.append(f"instagram: {e}")
    now, today, yday = ctx_dates(tz)
    ranges = {
        "yesterday": (day_bounds(yday, tz)[0], day_bounds(yday, tz)[1]),
        "last_7d": (day_bounds(today - dt.timedelta(days=7), tz)[0], day_bounds(today, tz)[0]),
    }
    ins = {}
    for m in IG_METRICS:
        row = {}
        for label, (a, b) in ranges.items():
            try:
                r = g.get(f"{ig}/insights", {"metric": m, "period": "day", "metric_type": "total_value",
                                             "since": int(a.timestamp()), "until": int(b.timestamp())}, token)
                for series in r.get("data", []):
                    tv = series.get("total_value") or {}
                    if "value" in tv:
                        row[label] = num(tv["value"])
                    elif tv.get("breakdowns"):
                        row[label] = sum(num(x.get("value")) for bd in tv["breakdowns"] for x in bd.get("results", []))
            except GraphError as e:
                row["error"] = str(e)[:120]
                break
        ins[m] = row
    out["insights"] = ins
    posts = []
    try:
        cutoff = now - dt.timedelta(days=14)
        for p in g.paged(f"{ig}/media", {"fields": "id,caption,media_type,media_product_type,timestamp,"
                                                   "like_count,comments_count,permalink", "limit": 15},
                         token, max_pages=1):
            ts = parse_time(p["timestamp"])
            if ts < cutoff:
                continue
            item = {
                "fecha": ts.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                "tipo": p.get("media_product_type") or p.get("media_type"),
                "texto": (p.get("caption") or "").replace("\n", " ")[:100],
                "likes": p.get("like_count", 0), "comentarios": p.get("comments_count", 0),
                "enlace": p.get("permalink"),
            }
            try:
                r = g.get(f"{p['id']}/insights", {"metric": IG_MEDIA_METRICS}, token)
                for series in r.get("data", []):
                    vals = series.get("values") or [{}]
                    item[series.get("name")] = num(vals[0].get("value"))
            except GraphError:
                pass
            posts.append(item)
    except GraphError as e:
        errors.append(f"instagram publicaciones: {e}")
    posts.sort(key=lambda x: x.get("total_interactions", x["likes"] + x["comentarios"]), reverse=True)
    out["posts_14d"] = posts
    return out


def analyze_conversations(convs, self_ids, now, tz):
    """Message counts, unanswered threads and response times from Graph conversation objects."""
    _, today, yday = ctx_dates(tz)
    y0, y1 = day_bounds(yday, tz)
    t0 = day_bounds(today, tz)[0]
    d24, d7 = now - dt.timedelta(hours=24), now - dt.timedelta(days=7)
    res = {"received_today": 0, "sent_today": 0, "received_yesterday": 0, "sent_yesterday": 0,
           "received_24h": 0, "sent_24h": 0, "received_7d": 0, "sent_7d": 0,
           "conversations_7d": 0, "conversations_with_customer_msgs_7d": 0, "answered_7d": 0,
           "unanswered": [], "first_response_minutes": []}
    for c in convs:
        msgs = []
        for m in (c.get("messages") or {}).get("data", []):
            try:
                ts = parse_time(m["created_time"])
            except (KeyError, ValueError):
                continue
            frm = m.get("from") or {}
            msgs.append((ts, str(frm.get("id")) in self_ids, frm.get("name") or frm.get("username") or ""))
        if not msgs:
            continue
        msgs.sort()
        if msgs[-1][0] < d7:
            continue
        res["conversations_7d"] += 1
        had_customer = False
        prev_out = True
        for i, (ts, out, _name) in enumerate(msgs):
            if ts >= d7:
                res["sent_7d" if out else "received_7d"] += 1
                if not out:
                    had_customer = True
            if ts >= d24:
                res["sent_24h" if out else "received_24h"] += 1
            if y0 <= ts < y1:
                res["sent_yesterday" if out else "received_yesterday"] += 1
            if ts >= t0:
                res["sent_today" if out else "received_today"] += 1
            if not out and prev_out and ts >= d7:  # start of a customer burst → time to next reply
                nxt = next((t for t, o, _ in msgs[i + 1:] if o), None)
                if nxt:
                    res["first_response_minutes"].append(round((nxt - ts).total_seconds() / 60, 1))
            prev_out = out
        if had_customer:
            res["conversations_with_customer_msgs_7d"] += 1
            if msgs[-1][1]:
                res["answered_7d"] += 1
        last_ts, last_out, last_name = msgs[-1]
        if not last_out:
            first = (last_name.split() or ["(sin nombre)"])[0]
            res["unanswered"].append({"nombre": first, "hace_horas": round((now - last_ts).total_seconds() / 3600, 1),
                                      "conversacion": c.get("id")})
    res["unanswered"].sort(key=lambda x: -x["hace_horas"])
    frm = res.pop("first_response_minutes")
    res["unanswered_count"] = len(res["unanswered"])
    res["oldest_unanswered_hours"] = res["unanswered"][0]["hace_horas"] if res["unanswered"] else 0
    res["unanswered"] = res["unanswered"][:15]
    res["median_first_response_min_7d"] = statistics.median(frm) if frm else None
    base = res["conversations_with_customer_msgs_7d"]
    res["answered_rate_7d"] = round(100 * res["answered_7d"] / base, 1) if base else None
    return res


def collect_messages(g, cfg, page_token, tz, errors):
    now = dt.datetime.now(tz)
    cutoff = now - dt.timedelta(days=7)
    self_ids = {str(cfg.get("META_PAGE_ID")), str(cfg.get("META_IG_USER_ID"))} - {"None", ""}
    out = {}
    for platform, label in (("instagram", "instagram"), ("messenger", "messenger")):
        if platform == "instagram" and not cfg.get("META_IG_USER_ID"):
            continue
        convs = []
        try:
            for c in g.paged(f"{cfg['META_PAGE_ID']}/conversations",
                             {"platform": platform, "limit": 50,
                              "fields": "id,updated_time,messages.limit(30){from,created_time}"},
                             page_token, max_pages=6):
                convs.append(c)
                if c.get("updated_time") and parse_time(c["updated_time"]) < cutoff:
                    break
            out[label] = analyze_conversations(convs, self_ids, now, tz)
        except GraphError as e:
            errors.append(f"mensajes {label}: {e}")
    return out


def summarize_actions(rows):
    acts = {}
    for a in rows or []:
        acts[a.get("action_type")] = num(a.get("value"))
    return acts


def main_result(actions, cpa):
    for k in RESULT_ORDER:
        if actions.get(k):
            return {"tipo": k, "nombre": ACTION_LABELS.get(k, k), "cantidad": actions[k], "costo_por": cpa.get(k)}
    return None


def collect_ads(g, cfg, errors):
    act = cfg["META_AD_ACCOUNT_ID"]
    if not act.startswith("act_"):
        act = "act_" + act
    out = {}
    try:
        out["account"] = g.get(act, {"fields": "name,currency,account_status,amount_spent,spend_cap,timezone_name"})
    except GraphError as e:
        errors.append(f"cuenta de anuncios: {e}")
    fields = "spend,impressions,reach,clicks,inline_link_clicks,ctr,cpc,cpm,actions,cost_per_action_type,purchase_roas"
    for preset, key in (("today", "today"), ("yesterday", "yesterday"), ("last_7d", "last_7d"),
                        ("this_month", "this_month"), ("last_month", "last_month")):
        try:
            r = g.get(f"{act}/insights", {"date_preset": preset, "level": "account", "fields": fields})
            row = (r.get("data") or [{}])[0]
            actions = summarize_actions(row.get("actions"))
            cpa = summarize_actions(row.get("cost_per_action_type"))
            out[key] = {
                "spend": num(row.get("spend")), "impressions": num(row.get("impressions")),
                "reach": num(row.get("reach")), "clicks": num(row.get("clicks")),
                "link_clicks": num(row.get("inline_link_clicks")), "ctr": num(row.get("ctr")),
                "cpc": num(row.get("cpc")), "cpm": num(row.get("cpm")),
                "roas": num((row.get("purchase_roas") or [{}])[0].get("value")) if row.get("purchase_roas") else None,
                "resultado": main_result(actions, cpa),
                "acciones": {ACTION_LABELS.get(k, k): v for k, v in actions.items() if k in ACTION_LABELS},
            }
        except GraphError as e:
            errors.append(f"anuncios {preset}: {e}")
    if "last_7d" in out:
        out["daily_average_7d"] = round(out["last_7d"]["spend"] / 7, 2)
    camps = {}
    try:
        for row in g.paged(f"{act}/insights", {"date_preset": "last_7d", "level": "campaign", "limit": 50,
                                               "fields": "campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,"
                                                         "actions,cost_per_action_type"}, max_pages=2):
            actions = summarize_actions(row.get("actions"))
            cpa = summarize_actions(row.get("cost_per_action_type"))
            camps[row.get("campaign_id")] = {
                "nombre": row.get("campaign_name"), "spend_7d": num(row.get("spend")),
                "clicks_7d": num(row.get("clicks")), "ctr_7d": num(row.get("ctr")), "cpc_7d": num(row.get("cpc")),
                "resultado_7d": main_result(actions, cpa), "spend_today": 0,
            }
        for row in g.paged(f"{act}/insights", {"date_preset": "today", "level": "campaign", "limit": 50,
                                               "fields": "campaign_id,campaign_name,spend"}, max_pages=2):
            c = camps.setdefault(row.get("campaign_id"), {"nombre": row.get("campaign_name"), "spend_7d": 0})
            c["spend_today"] = num(row.get("spend"))
        for row in g.paged(f"{act}/campaigns", {"fields": "id,name,effective_status,daily_budget,lifetime_budget",
                                                "limit": 100}, max_pages=2):
            if row.get("effective_status") in ("ARCHIVED", "DELETED"):
                continue
            c = camps.setdefault(row["id"], {"nombre": row.get("name"), "spend_7d": 0, "spend_today": 0})
            c["estado"] = row.get("effective_status")
            if row.get("daily_budget"):
                c["presupuesto_diario"] = num(row["daily_budget"]) / 100  # minor units
    except GraphError as e:
        errors.append(f"campañas: {e}")
    out["campaigns_7d"] = sorted(camps.values(), key=lambda c: -c.get("spend_7d", 0))[:20]
    return out


def read_budget():
    p = DATA / "presupuesto.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {"error": "data/presupuesto.json no es JSON válido"}


def read_sales(tz):
    p = DATA / "ventas.csv"
    _, today, yday = ctx_dates(tz)
    res = {"hoy": {"ventas": 0, "ingreso": 0.0}, "ayer": {"ventas": 0, "ingreso": 0.0},
           "mes": {"ventas": 0, "ingreso": 0.0}, "mes_anterior": {"ventas": 0, "ingreso": 0.0}, "por_producto_mes": {}}
    if not p.exists():
        return res
    first = today.replace(day=1)
    prev_last = first - dt.timedelta(days=1)
    with p.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                d = dt.date.fromisoformat((row.get("fecha") or "")[:10])
                qty = num(row.get("cantidad") or 1) or 1
                total = num(row.get("total")) or qty * num(row.get("precio_unitario"))
            except ValueError:
                continue
            buckets = []
            if d == today:
                buckets.append("hoy")
            if d == yday:
                buckets.append("ayer")
            if d >= first and d <= today:
                buckets.append("mes")
                prod = row.get("producto") or "(sin producto)"
                pp = res["por_producto_mes"].setdefault(prod, {"ventas": 0, "ingreso": 0.0})
                pp["ventas"] += qty
                pp["ingreso"] += total
            if prev_last.replace(day=1) <= d <= prev_last:
                buckets.append("mes_anterior")
            for b in buckets:
                res[b]["ventas"] += qty
                res[b]["ingreso"] += total
    return res


def business_kpis(snap, tz):
    now, today, _ = ctx_dates(tz)
    import calendar
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    elapsed = today.day / days_in_month
    budget = snap.get("presupuesto", {})
    ads = snap.get("ads", {})
    sales = snap.get("ventas", {})
    k = {"dia_del_mes": today.day, "dias_del_mes": days_in_month, "avance_mes_pct": round(100 * elapsed, 1)}
    spend = (ads.get("this_month") or {}).get("spend")
    cap = budget.get("presupuesto_ads_mes")
    if spend is not None:
        k["gasto_ads_mes"] = spend
        k["proyeccion_gasto_mes"] = round(spend / max(today.day, 1) * days_in_month, 2)
        if cap:
            k["presupuesto_ads_mes"] = cap
            k["presupuesto_usado_pct"] = round(100 * spend / cap, 1)
            k["presupuesto_restante"] = round(cap - spend, 2)
            k["ritmo"] = "arriba" if spend / cap > elapsed + 0.10 else ("abajo" if spend / cap < elapsed - 0.15 else "en línea")
    mes = sales.get("mes") or {}
    if mes.get("ventas"):
        if spend:
            k["costo_adquisicion_mes"] = round(spend / mes["ventas"], 2)
            k["roas_real_mes"] = round(mes["ingreso"] / spend, 2)
        meta = budget.get("meta_ventas_mes")
        if meta:
            k["meta_ventas_mes"] = meta
            k["meta_ventas_pct"] = round(100 * mes["ventas"] / meta, 1)
    return k


def money(v, cur):
    if v is None:
        return "—"
    return f"${v:,.2f} {cur}".replace(".00 ", " ")


def write_summary(snap, tz):
    cur = (snap.get("ads", {}).get("account") or {}).get("currency") or snap.get("presupuesto", {}).get("moneda") or "MXN"
    L = [f"# Pulso de Meta — {snap['generated_at_local']}", ""]
    for label, key in (("Instagram", "instagram"), ("Messenger", "messenger")):
        m = snap.get("messages", {}).get(key)
        if not m:
            continue
        L.append(f"**{label} (mensajes):** ayer {m['received_yesterday']} recibidos / {m['sent_yesterday']} enviados · "
                 f"hoy {m['received_today']} / {m['sent_today']} · sin contestar ahora: {m['unanswered_count']}"
                 + (f" (el más antiguo hace {m['oldest_unanswered_hours']} h)" if m["unanswered_count"] else "")
                 + (f" · respuesta mediana 7 d: {m['median_first_response_min_7d']} min" if m.get("median_first_response_min_7d") is not None else "")
                 + (f" · contestadas 7 d: {m['answered_rate_7d']} %" if m.get("answered_rate_7d") is not None else ""))
    ads = snap.get("ads", {})
    for label, key in (("Hoy", "today"), ("Ayer", "yesterday"), ("Últimos 7 días", "last_7d"), ("Este mes", "this_month")):
        a = ads.get(key)
        if not a:
            continue
        r = a.get("resultado")
        res = f" · {r['nombre']}: {r['cantidad']:g}" + (f" a {money(r['costo_por'], cur)} c/u" if r.get("costo_por") else "") if r else ""
        L.append(f"**Anuncios {label.lower()}:** gasto {money(a['spend'], cur)} · alcance {a['reach']:,.0f} · "
                 f"clics {a['clicks']:,.0f} · CTR {a['ctr']:.2f} %{res}")
    k = snap.get("kpis", {})
    if "presupuesto_usado_pct" in k:
        L.append(f"**Presupuesto:** {money(k['gasto_ads_mes'], cur)} de {money(k['presupuesto_ads_mes'], cur)} "
                 f"({k['presupuesto_usado_pct']} %) con el {k['avance_mes_pct']} % del mes · ritmo {k['ritmo']} · "
                 f"proyección {money(k['proyeccion_gasto_mes'], cur)}")
    v = snap.get("ventas", {})
    if v:
        L.append(f"**Ventas registradas:** ayer {v['ayer']['ventas']:g} ({money(v['ayer']['ingreso'], cur)}) · "
                 f"mes {v['mes']['ventas']:g} ({money(v['mes']['ingreso'], cur)})"
                 + (f" · meta {k['meta_ventas_pct']} %" if "meta_ventas_pct" in k else "")
                 + (f" · costo por venta {money(k['costo_adquisicion_mes'], cur)} · ROAS real {k['roas_real_mes']}" if "roas_real_mes" in k else ""))
    ig = snap.get("instagram", {})
    if ig.get("followers_count") is not None:
        d = snap.get("deltas", {}).get("instagram_followers_vs_7d")
        L.append(f"**Instagram:** {ig['followers_count']:,} seguidores" + (f" ({d:+,} vs hace 7 días)" if d is not None else ""))
        if ig.get("posts_14d"):
            p = ig["posts_14d"][0]
            L.append(f"  Mejor post 14 d: {p['fecha']} {p['tipo']} — \"{p['texto'][:60]}\" · "
                     f"{p.get('views', '—')} vistas · {p['likes']} likes · {p['comentarios']} comentarios")
    if snap.get("errors"):
        L.append("")
        L.append("**Avisos del colector:** " + " | ".join(snap["errors"][:6]))
    (META_DIR / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def follower_deltas(snap, tz):
    _, today, _ = ctx_dates(tz)
    old = META_DIR / "history" / f"{today - dt.timedelta(days=7)}.json"
    res = {}
    if old.exists():
        try:
            o = json.loads(old.read_text(encoding="utf-8"))
            a, b = (o.get("instagram") or {}).get("followers_count"), (snap.get("instagram") or {}).get("followers_count")
            if a is not None and b is not None:
                res["instagram_followers_vs_7d"] = b - a
            a, b = (o.get("page") or {}).get("followers_count"), (snap.get("page") or {}).get("followers_count")
            if a is not None and b is not None:
                res["page_followers_vs_7d"] = b - a
        except ValueError:
            pass
    return res


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def log(line):
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs" / "meta-sync.log").open("a", encoding="utf-8") as fh:
        fh.write(dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S") + " " + line + "\n")


def main(argv):
    os.umask(0o077)
    cfg = load_cfg()
    tz = ZoneInfo(cfg.get("JARVIS_TZ") or "America/Mexico_City") if ZoneInfo else dt.timezone(dt.timedelta(hours=-6))
    token = cfg.get("META_ACCESS_TOKEN")
    if not token:
        print("meta-sync: falta META_ACCESS_TOKEN en .env (RUNBOOK.md § Meta)", file=sys.stderr)
        log("FAILED no token")
        return 2
    g = Graph(token, cfg.get("META_GRAPH_VERSION") or "v26.0", cfg.get("META_APP_SECRET"), cfg.get("META_GRAPH_BASE"))

    if "--discover" in argv:  # list the IDs this token can see (IDs are not secrets) and offer to save them
        try:
            pages = list(g.paged("me/accounts", {"fields": "id,name,instagram_business_account{id,username}", "limit": 50}))
            ads = list(g.paged("me/adaccounts", {"fields": "account_id,name,currency,account_status", "limit": 50}))
        except GraphError as e:
            print("fail", e)
            return 1
        print("Páginas:")
        for p in pages:
            ig = p.get("instagram_business_account") or {}
            print(f"  META_PAGE_ID={p['id']}  ({p.get('name')})  ->  META_IG_USER_ID={ig.get('id', '(sin Instagram vinculado)')}"
                  + (f" @{ig['username']}" if ig.get("username") else ""))
        print("Cuentas de anuncios:")
        for a in ads:
            print(f"  META_AD_ACCOUNT_ID={a.get('account_id')}  ({a.get('name')}, {a.get('currency')}, estado {a.get('account_status')})")
        if "--save" in argv and len(pages) == 1 and len(ads) <= 1:
            p, a = pages[0], (ads[0] if ads else {})
            vals = {"META_PAGE_ID": p["id"], "META_IG_USER_ID": (p.get("instagram_business_account") or {}).get("id", ""),
                    "META_AD_ACCOUNT_ID": a.get("account_id", "")}
            env = ROOT / ".env"
            lines = env.read_text(encoding="utf-8").splitlines()
            for k, v in vals.items():
                if not v or cfg.get(k):
                    continue
                lines = [f"{k}={v}" if l.startswith(f"{k}=") else l for l in lines]
                if not any(l.startswith(f"{k}=") for l in lines):
                    lines.append(f"{k}={v}")
            env.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("guardado en .env (solo IDs vacíos)")
        elif "--save" in argv:
            print("Hay varias páginas o cuentas: copia los IDs correctos a .env a mano.")
        return 0

    if "--check" in argv:
        try:
            me = g.get("me", {"fields": "id,name"})
            perms = [p["permission"] for p in g.get("me/permissions").get("data", []) if p.get("status") == "granted"]
            print("ok token válido · cuenta:", me.get("name", "?"))
            print("permisos:", ", ".join(sorted(perms)) or "(ninguno listado; los tokens de página no los listan)")
            for k in ("META_PAGE_ID", "META_IG_USER_ID", "META_AD_ACCOUNT_ID"):
                print(f"{k}: {'definido' if cfg.get(k) else 'FALTA'}")
            return 0
        except GraphError as e:
            print("fail", e)
            return 1

    errors = []
    snap = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "generated_at_local": dt.datetime.now(tz).strftime("%Y-%m-%d %H:%M"),
            "timezone": str(tz), "graph_version": g.version}
    page_token = token
    if cfg.get("META_PAGE_ID"):
        try:
            pt = g.get(cfg["META_PAGE_ID"], {"fields": "access_token"}).get("access_token")
            if pt:
                page_token = pt
        except GraphError as e:
            errors.append(f"token de página: {e}")
        snap["page"] = collect_page(g, cfg, page_token, tz, errors)
        snap["messages"] = collect_messages(g, cfg, page_token, tz, errors)
    else:
        errors.append("falta META_PAGE_ID: sin página ni mensajes")
    if cfg.get("META_IG_USER_ID"):
        snap["instagram"] = collect_instagram(g, cfg, page_token, tz, errors)
    else:
        errors.append("falta META_IG_USER_ID: sin Instagram")
    if cfg.get("META_AD_ACCOUNT_ID"):
        snap["ads"] = collect_ads(g, cfg, errors)
    else:
        errors.append("falta META_AD_ACCOUNT_ID: sin anuncios")
    snap["presupuesto"] = read_budget()
    snap["ventas"] = read_sales(tz)
    snap["kpis"] = business_kpis(snap, tz)
    snap["deltas"] = follower_deltas(snap, tz)
    snap["errors"] = [redact(e, token, page_token) for e in errors]
    snap["api_calls"] = g.calls

    text = json.dumps(snap, ensure_ascii=False, indent=1)
    atomic_write(META_DIR / "latest.json", text)
    atomic_write(META_DIR / "history" / f"{dt.datetime.now(tz).date()}.json", text)
    write_summary(snap, tz)
    got_any = any(k in snap for k in ("messages", "instagram", "ads")) and len(errors) < 12
    log(f"{'ok' if got_any else 'FAILED'} calls={g.calls} errors={len(errors)}")
    print(f"meta-sync {'ok' if got_any else 'FAILED'}: {g.calls} llamadas, {len(errors)} avisos")
    return 0 if got_any else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
