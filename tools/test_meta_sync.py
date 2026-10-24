#!/usr/bin/env python3
"""Offline test for bin/meta-sync.py: a fake Graph API on 127.0.0.1, a temp Jarvis copy, assertions.

Run: python3 -I tools/test_meta_sync.py   (exits 0 when everything passes; never touches Meta)
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "FAKE_TOKEN_1234567890"
PAGE, IG, ACT = "111", "222", "act_333"
now = dt.datetime.now(dt.timezone.utc)
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S+0000")

def conv(cid, msgs):
    return {"id": cid, "updated_time": iso(msgs[0][0]),
            "messages": {"data": [{"created_time": iso(t), "from": {"id": f, "name": n}} for t, f, n in msgs]}}

H = dt.timedelta(hours=1)
IG_CONVS = [
    conv("c1", [(now - 1 * H, IG, "Academia"), (now - 2 * H, "9001", "Ana López")]),   # answered after 1 h
    conv("c2", [(now - 5 * H, "9002", "Luis Pérez")]),                                 # unanswered 5 h
    conv("c3", [(now - 30 * H, "9003", "Marta"), (now - 31 * H, IG, "Academia")]),     # unanswered 30 h
]
FB_CONVS = [conv("m1", [(now - 3 * H, PAGE, "Academia"), (now - 3.5 * H, "8001", "Pedro")])]

class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        path = u.path.split("/", 2)[2]  # strip /v26.0/
        assert q.get("access_token") in (TOKEN, "PAGE_TOKEN"), "token missing"
        body = self.route(path, q)
        if body is None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"type": "OAuthException", "code": 100,
                                                   "message": f"invalid metric {q.get('metric')} token={TOKEN}"}}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def route(self, path, q):
        if path == "me":
            return {"id": "1", "name": "Sistema"}
        if path == "me/accounts":
            return {"data": [{"id": PAGE, "name": "Academia Salva Tomate", "instagram_business_account": {"id": IG, "username": "salvatomate"}}]}
        if path == "me/adaccounts":
            return {"data": [{"account_id": "333", "name": "Cuenta", "currency": "MXN", "account_status": 1}]}
        if path == "me/permissions":
            return {"data": [{"permission": "ads_read", "status": "granted"}]}
        if path == PAGE and q.get("fields") == "access_token":
            return {"access_token": "PAGE_TOKEN"}
        if path == PAGE:
            return {"name": "Academia Salva Tomate", "followers_count": 5000, "fan_count": 4800}
        if path == f"{PAGE}/insights":
            if q["metric"] == "page_views_total":
                return None  # deprecated metric → must be skipped, not fatal
            return {"data": [{"name": q["metric"], "values": [{"value": 10, "end_time": "2026-10-22T07:00:00+0000"},
                                                             {"value": {"paid": 5, "organic": 15}, "end_time": "2026-10-23T07:00:00+0000"}]}]}
        if path == f"{PAGE}/conversations":
            return {"data": IG_CONVS if q["platform"] == "instagram" else FB_CONVS}
        if path == IG:
            return {"username": "salvatomate", "followers_count": 1200, "follows_count": 10, "media_count": 80}
        if path == f"{IG}/insights":
            return {"data": [{"name": q["metric"], "total_value": {"value": 321}}]}
        if path == f"{IG}/media":
            return {"data": [{"id": "p1", "caption": "Clase gratis hoy", "media_type": "VIDEO", "media_product_type": "REELS",
                              "timestamp": iso(now - 24 * H), "like_count": 50, "comments_count": 7, "permalink": "https://x/p1"}]}
        if path == "p1/insights":
            return {"data": [{"name": "views", "values": [{"value": 900}]}, {"name": "total_interactions", "values": [{"value": 70}]}]}
        if path == ACT:
            return {"name": "Cuenta", "currency": "MXN", "account_status": 1}
        if path == f"{ACT}/insights" and q.get("level") == "account":
            spend = {"today": "300", "yesterday": "500", "last_7d": "3500", "this_month": "9000", "last_month": "12000"}[q["date_preset"]]
            return {"data": [{"spend": spend, "impressions": "10000", "reach": "8000", "clicks": "200", "inline_link_clicks": "150",
                              "ctr": "2.0", "cpc": "2.5", "cpm": "50",
                              "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "40"},
                                          {"action_type": "link_click", "value": "150"}],
                              "cost_per_action_type": [{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "12.5"}]}]}
        if path == f"{ACT}/insights" and q.get("level") == "campaign":
            if q["date_preset"] == "today":
                return {"data": [{"campaign_id": "k1", "campaign_name": "Inscripciones", "spend": "300"}]}
            return {"data": [{"campaign_id": "k1", "campaign_name": "Inscripciones", "spend": "3000", "clicks": "180", "ctr": "2.1",
                              "cpc": "2.4", "actions": []},
                             {"campaign_id": "k2", "campaign_name": "Remarketing", "spend": "500", "clicks": "20", "ctr": "1", "cpc": "25"}]}
        if path == f"{ACT}/campaigns":
            return {"data": [{"id": "k1", "name": "Inscripciones", "effective_status": "ACTIVE", "daily_budget": "50000"},
                             {"id": "k2", "name": "Remarketing", "effective_status": "ACTIVE"}]}
        return None


def main():
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-meta-test-"))
    try:
        (tmp / "bin").mkdir()
        shutil.copy(ROOT / "bin" / "meta-sync.py", tmp / "bin" / "meta-sync.py")
        (tmp / "data").mkdir()
        (tmp / "data" / "presupuesto.json").write_text(json.dumps({"presupuesto_ads_mes": 15000, "meta_ventas_mes": 40, "moneda": "MXN"}))
        today = dt.datetime.now().astimezone().date()
        (tmp / "data" / "ventas.csv").write_text("fecha,producto,cantidad,precio_unitario,total,canal,nota\n"
                                                 f"{today},Curso A,2,1500,3000,instagram,\n")
        (tmp / ".env").write_text(f"META_ACCESS_TOKEN={TOKEN}\nMETA_PAGE_ID={PAGE}\nMETA_IG_USER_ID={IG}\n"
                                  f"META_AD_ACCOUNT_ID=333\nMETA_GRAPH_BASE=http://127.0.0.1:{srv.server_port}\n"
                                  "JARVIS_TZ=America/Mexico_City\n")
        r = subprocess.run([sys.executable, "-I", str(tmp / "bin" / "meta-sync.py")], capture_output=True, text=True)
        assert r.returncode == 0, (r.stdout, r.stderr)
        snap = json.loads((tmp / "data/meta/latest.json").read_text())
        ig = snap["messages"]["instagram"]
        assert ig["unanswered_count"] == 2, ig
        assert ig["oldest_unanswered_hours"] >= 29.9, ig
        assert ig["unanswered"][0]["nombre"] == "Marta", ig
        assert ig["median_first_response_min_7d"] == 60.0, ig
        assert ig["answered_rate_7d"] == round(100 / 3, 1), ig
        assert snap["messages"]["messenger"]["unanswered_count"] == 0
        assert snap["page"]["insights"]["page_media_view"]["last_7d"] == 30
        assert "error" in snap["page"]["insights"]["page_views_total"]
        assert snap["instagram"]["insights"]["reach"]["yesterday"] == 321
        assert snap["instagram"]["posts_14d"][0]["views"] == 900
        assert snap["ads"]["this_month"]["spend"] == 9000
        assert snap["ads"]["daily_average_7d"] == 500
        assert snap["ads"]["today"]["resultado"]["nombre"] == "conversaciones iniciadas"
        assert snap["ads"]["campaigns_7d"][0]["presupuesto_diario"] == 500
        assert snap["kpis"]["presupuesto_usado_pct"] == 60.0
        assert snap["ventas"]["hoy"]["ventas"] == 2 and snap["ventas"]["mes"]["ingreso"] == 3000
        assert snap["kpis"]["costo_adquisicion_mes"] == 4500
        all_text = (tmp / "data/meta/latest.json").read_text() + (tmp / "data/meta/summary.md").read_text() + \
            (tmp / "logs/meta-sync.log").read_text()
        assert TOKEN not in all_text and "PAGE_TOKEN" not in all_text, "token leaked"
        summary = (tmp / "data/meta/summary.md").read_text()
        assert "sin contestar ahora: 2" in summary, summary
        r = subprocess.run([sys.executable, "-I", str(tmp / "bin" / "meta-sync.py"), "--check"], capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout.startswith("ok") and TOKEN not in r.stdout, r.stdout
        env = (tmp / ".env").read_text()
        (tmp / ".env").write_text("\n".join(l for l in env.splitlines() if not l.startswith(("META_PAGE_ID", "META_IG_USER_ID", "META_AD_ACCOUNT_ID"))) + "\n")
        r = subprocess.run([sys.executable, "-I", str(tmp / "bin" / "meta-sync.py"), "--discover", "--save"], capture_output=True, text=True)
        env = (tmp / ".env").read_text()
        assert r.returncode == 0 and f"META_PAGE_ID={PAGE}" in env and f"META_IG_USER_ID={IG}" in env and "META_AD_ACCOUNT_ID=333" in env, (r.stdout, env)
        assert TOKEN not in r.stdout
        print("ok meta-sync: 22 checks passed")
        print(summary)
    finally:
        srv.shutdown()
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
