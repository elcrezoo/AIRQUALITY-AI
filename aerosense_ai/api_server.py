# -*- coding: utf-8 -*-

# ==============================================================================
# AeroSense AI — Akıllı Hava Kalitesi İzleme ve Analiz Sistemi
# -----------------------------------------------------------------------------
# Telif (Copyright) © 2026 Enes Bozkurt. Tüm hakları saklıdır.
# Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026
# Web: https://enesbozkurt.com.tr
#
# Bu yazılım ve eşlik eden dokümantasyon, yazarın yazılı izni olmadan çoğaltılamaz,
# dağıtılamaz, kiralanamaz veya üçüncü kişilere devredilemez. Ticari kullanım yasaktır.
# Akademik ve proje sunumlarında kaynak gösterilmesi zorunludur.
# ==============================================================================

"""Flask REST — dokuman Bolum 8 + v1 uyumluluk uclari."""
import json
import os
import threading
import time

from flask import Flask, jsonify, request, send_file, send_from_directory

from . import config
from .ai.interpreter import answer_query_tr
from .ai_engine import sensor_health_tr
from .project_meta import NOTICE_ONE_LINE, api_notice_dict


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def create_app(state, engine_holder):
    _pkg = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(_pkg, "static")
    app = Flask(__name__, static_folder=static_dir)

    def get_engine():
        return engine_holder.get("engine")

    @app.after_request
    def add_cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["X-AeroSense-Notice"] = NOTICE_ONE_LINE
        return resp

    # ----- Dokuman 8.2 web panel -----
    @app.route("/", methods=["GET"])
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/m", methods=["GET"])
    def mobile_panel():
        """Aynı panel (responsive); telefondan kısayol için."""
        return send_from_directory(static_dir, "index.html")

    # ----- /api/status -----
    @app.route("/api/status", methods=["GET"])
    def api_status():
        body = {
            "status": "ok",
            "service": "aerosense_ai",
            "uptime_sec": round(state.uptime_seconds(), 1),
            "time": time.time(),
        }
        body.update(api_notice_dict())
        return jsonify(body)

    @app.route("/api/health", methods=["GET"])
    def health():
        body = {"ok": True, "service": "aerosense_ai", "time": time.time()}
        body.update(api_notice_dict())
        return jsonify(body)

    def _payload_latest():
        try:
            latest_d, channels, ts = state.get_latest()
            ai_text, ai_detail = state.get_ai()
            analysis = state.get_analysis()

            ev_raw = state.get_event()
            # JSON uyumluluk için sadece temel alanları döndürüyoruz.
            safe_ev = {}
            try:
                if isinstance(ev_raw, dict):
                    for k in ("event_label", "event_name", "confidence"):
                        if k in ev_raw:
                            safe_ev[k] = ev_raw.get(k)
            except Exception:
                safe_ev = {}

            health_rows = sensor_health_tr(latest_d, channels, ts)
            out = {
                "timestamp_unix": ts,
                "sensors": latest_d,
                "channels": channels,
                "ai_tr": ai_text,
                "ai_detail_tr": ai_detail,
                "ai_analysis": analysis,
                "sensor_health": health_rows,
                "events": safe_ev,
            }
            out["project_notice"] = api_notice_dict()
            return out
        except Exception as e:
            # 500 yerine JSON dönelim; böylece hata panel/CLI'dan görülebilir.
            try:
                latest_d, channels, ts = state.get_latest()
            except Exception:
                latest_d, channels, ts = {}, [], 0.0
            return {
                "timestamp_unix": ts,
                "sensors": latest_d,
                "channels": channels,
                "ai_tr": "",
                "ai_detail_tr": "",
                "ai_analysis": {},
                "sensor_health": [],
                "events": {},
                "project_notice": api_notice_dict(),
                "api_error": str(e),
            }

    @app.route("/api/sensors", methods=["GET"])
    def api_sensors():
        p = _payload_latest()
        return jsonify(p.get("sensors", {}))

    @app.route("/api/sensors/latest", methods=["GET"])
    def api_sensors_latest():
        return jsonify(_payload_latest())

    @app.route("/api/latest", methods=["GET"])
    def latest():
        return jsonify(_payload_latest())

    @app.route("/api/sensors/history", methods=["GET"])
    def api_sensors_history():
        n = request.args.get("n", type=int) or 100
        items = state.get_history(min(n, 5000))
        out = [{"ts": it["t"], **it["data"]} for it in items]
        return jsonify({"count": len(out), "items": out})

    @app.route("/api/history", methods=["GET"])
    def history():
        n = request.args.get("n", type=int) or 200
        items = state.get_history(min(n, 5000))
        out = []
        for it in items:
            out.append({"t": it["t"], "sensors": it["data"]})
        return jsonify({"count": len(out), "items": out})

    @app.route("/api/ai/analysis", methods=["GET"])
    def api_ai_analysis():
        return jsonify(state.get_analysis())

    @app.route("/api/events/latest", methods=["GET"])
    def api_events_latest():
        # Aynı safe alanlar
        ev_raw = state.get_event() or {}
        safe_ev = {}
        if isinstance(ev_raw, dict):
            for k in ("event_label", "event_name", "confidence"):
                if k in ev_raw:
                    safe_ev[k] = ev_raw.get(k)
        return jsonify(safe_ev)

    @app.route("/api/ai/query", methods=["POST", "OPTIONS"])
    def api_ai_query():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("q") or data.get("question") or ""
        latest_d, channels, ts = state.get_latest()
        eng = get_engine()
        hist = state.get_history(100)
        if eng and latest_d:
            analysis = eng.analyze(latest_d, channels, hist)
        else:
            analysis = state.get_analysis()
        reply = answer_query_tr(q, latest_d, analysis)
        return jsonify({"q": q, "answer_tr": reply})

    @app.route("/api/alerts", methods=["GET"])
    def api_alerts():
        a = state.get_analysis()
        alerts = a.get("alerts") or []
        out = [{"severity": s, "message_tr": m} for s, m in alerts]
        return jsonify({"alerts": out})

    @app.route("/api/sensors/config", methods=["GET"])
    def api_sensors_config():
        cfg = _load_json(config.ACTIVE_SENSORS_JSON, {})
        return jsonify({"channels": cfg, "channel_order": config.CHANNEL_ORDER})

    @app.route("/api/csv/path", methods=["GET"])
    def csv_path():
        return jsonify(
            {
                "legacy": os.path.abspath(config.CSV_PATH),
                "logs_dir": os.path.abspath(config.LOGS_DIR),
            }
        )

    @app.route("/api/csv/tail", methods=["GET"])
    def csv_tail():
        lines = request.args.get("lines", type=int) or 50
        path = config.CSV_PATH
        if not os.path.isfile(path):
            return jsonify({"error": "csv yok"}), 404
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return jsonify({"lines": "".join(tail)})

    @app.route("/api/export/csv", methods=["GET"])
    def api_export_csv():
        day = request.args.get("date")
        if day:
            safe = day.replace("..", "").strip()
            path = os.path.join(config.LOGS_DIR, "%s.csv" % safe)
        else:
            path = os.path.join(
                config.LOGS_DIR, time.strftime("%Y-%m-%d.csv", time.localtime())
            )
        if not os.path.isfile(path):
            path = config.CSV_PATH
        if not os.path.isfile(path):
            return jsonify({"error": "dosya yok"}), 404
        return send_file(
            path,
            mimetype="text/csv",
            as_attachment=True,
            attachment_filename=os.path.basename(path),
        )

    @app.route("/api/csv/download", methods=["GET"])
    def csv_download():
        path = config.CSV_PATH
        if not os.path.isfile(path):
            return jsonify({"error": "csv yok"}), 404
        return send_file(
            path,
            mimetype="text/csv",
            as_attachment=True,
            attachment_filename="sensor_log.csv",
        )

    @app.route("/api/webhook", methods=["POST", "OPTIONS"])
    def webhook_add():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url") or data.get("webhook")
        if not url:
            return jsonify({"ok": False, "error": "url gerekli"}), 400
        ok = state.add_webhook(str(url))
        return jsonify({"ok": ok, "webhooks": state.list_webhooks()})

    @app.route("/api/webhook", methods=["DELETE"])
    def webhook_del():
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url")
        if not url:
            return jsonify({"ok": False}), 400
        state.remove_webhook(str(url))
        return jsonify({"ok": True, "webhooks": state.list_webhooks()})

    @app.route("/api/push", methods=["POST", "OPTIONS"])
    def push_once():
        if request.method == "OPTIONS":
            return ("", 204)
        data = request.get_json(force=True, silent=True) or {}
        url = data.get("url")
        if not url:
            return jsonify({"ok": False, "error": "url gerekli"}), 400
        latest_d, channels, ts = state.get_latest()
        eng = get_engine()
        hist = state.get_history(100)
        if eng and latest_d:
            ai_text, _ = eng.predict_tr(latest_d, channels, hist)
            analysis = eng.analyze(latest_d, channels, hist)
        else:
            ai_text, _ = state.get_ai()
            analysis = state.get_analysis()
        payload = {
            "timestamp_unix": ts,
            "sensors": latest_d,
            "channels": channels,
            "ai_tr": ai_text,
            "ai_analysis": analysis,
        }
        body = json.dumps(payload).encode("utf-8")
        try:
            from urllib.request import Request, urlopen

            req = Request(
                str(url),
                data=body,
                headers={"Content-Type": "application/json"},
            )
            urlopen(req, timeout=10).read()
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 502
        return jsonify({"ok": True})

    @app.route("/api/model/reload", methods=["POST"])
    def model_reload():
        eng = get_engine()
        if eng:
            eng.reload_model()
        return jsonify({"ok": True})

    @app.route("/api/system/restart", methods=["POST"])
    def api_system_restart():
        """Dokuman: sifre korumali — basit ortam degiskeni."""
        pwd = os.environ.get("AEROSENSE_ADMIN_PASSWORD", "")
        data = request.get_json(force=True, silent=True) or {}
        if not pwd:
            return jsonify({"ok": False, "error": "AEROSENSE_ADMIN_PASSWORD tanimli degil"}), 403
        if data.get("password") != pwd:
            return jsonify({"ok": False, "error": "Yetkisiz"}), 401
        return jsonify({"ok": True, "hint": "systemctl restart air-ai.service"})

    return app


def run_flask_thread(state, engine_holder, host=None, port=None):
    host = host or config.API_HOST
    port = port or config.API_PORT
    app = create_app(state, engine_holder)

    def _run():
        app.run(host=host, port=port, threaded=True, use_reloader=False)

    t = threading.Thread(target=_run, name="aerosense-api", daemon=True)
    t.start()
    print("[api] AeroSense v2 http://%s:%s  (panel: /)" % (host, port))
    print("[api]", NOTICE_ONE_LINE)
    return t
