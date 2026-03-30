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

"""AeroSense AI v2 — alici + API + AI dongusu + gunluk CSV + ses + PyQt."""
from __future__ import print_function

import os
import sys
import threading
import time
from datetime import datetime

# Proje kokunu PYTHONPATH'e ekle (dogrudan calistirma)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from aerosense_ai.ai_engine import AIEngine, sensor_health_tr
from aerosense_ai.api_server import run_flask_thread
from aerosense_ai.project_meta import COPYRIGHT_LINE, NOTICE_ONE_LINE
from aerosense_ai.csv_logger import CsvLogger
from aerosense_ai.daily_csv import DailyCsvLogger
from aerosense_ai.receiver import start_receiver_thread
from aerosense_ai.shared_state import SharedState
from aerosense_ai.event_runtime import start_event_classifier_thread
from aerosense_ai.telegram_notify import maybe_alert_analysis, maybe_channel_stream
from aerosense_ai.ai.interpreter import analysis_to_summary_tr
from aerosense_ai import config


def _ai_loop(state, engine, stop_event, daily):
    first = True
    while state.running and not stop_event.is_set():
        latest, ch, ts = state.get_latest()
        if latest:
            try:
                # AI motoru icin kisa gecmis
                hist = state.get_history(120)
                t_ai = time.perf_counter()
                r = engine.analyze(latest, ch, hist)
                state.set_ai_timing_ms((time.perf_counter() - t_ai) * 1000.0)

                # HIZLI DEGISIM (rate-of-change) uyarisi:
                # - anlik degisimleri yakalar (örn. mq135/mq7/toz hizi artiyor/azaliyor)
                # - Telegram ve GUI'de net gorunmesi icin r["alerts"] listesine eklenir
                try:
                    rapid_N = max(5, int(getattr(config, "RAPID_SAMPLES", 20)))
                    rel_thr = float(getattr(config, "RAPID_REL_THRESHOLD", 0.25))
                    abs_thr = float(getattr(config, "RAPID_ABS_THRESHOLD", 0.0))
                    rate_hist = state.get_history(max(2 * rapid_N + 5, 40))
                    rapid_alerts = []
                    for key in (ch or []):
                        try:
                            cur = latest.get(key)
                            if cur is None:
                                continue
                            # deger dizisi (chronological)
                            vals = []
                            for it in rate_hist:
                                d = it.get("data") or {}
                                v = d.get(key)
                                if v is None:
                                    continue
                                try:
                                    vals.append(float(v))
                                except Exception:
                                    continue
                            if len(vals) < 2 * rapid_N + 1:
                                continue
                            prev_slice = vals[-2 * rapid_N : -rapid_N]
                            if not prev_slice:
                                continue
                            prev_avg = sum(prev_slice) / float(len(prev_slice))
                            delta = float(cur) - float(prev_avg)
                            rel = abs(delta) / (abs(prev_avg) + 1e-9)
                            if rel_thr > 0 and rel >= rel_thr and abs(delta) >= abs_thr:
                                direction = "artiyor" if delta > 0 else "azaliyor"
                                rapid_alerts.append(
                                    (
                                        "RAPID",
                                        "%s hızlı %s (Δ=%+.4g, rel=%.2f×)"
                                        % (key, direction, delta, rel),
                                    )
                                )
                        except Exception:
                            continue
                    # En buyuk 2 hizli uyarinin yazilmasi (spam engeli)
                    if rapid_alerts:
                        rapid_alerts = rapid_alerts[:2]
                        cur_alerts = list(r.get("alerts") or [])
                        r["alerts"] = list(rapid_alerts) + cur_alerts
                        r["summary_tr"] = analysis_to_summary_tr(r)
                except Exception:
                    pass

                state.set_analysis(r)
                state.set_ai(r.get("summary_tr", ""), r.get("detail_tr", ""))
                health_rows = sensor_health_tr(latest, ch, ts)
                ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_row = daily.append(ts_str, latest, ch, r, health_rows)
                if log_row:
                    state.push_data_log_row(log_row)
                try:
                    maybe_alert_analysis(r, health_rows)
                except Exception:
                    pass
                try:
                    maybe_channel_stream(state)
                except Exception:
                    pass
            except Exception as e:
                state.set_ai("AI guncelleme hatasi: %s" % e, "")
        time.sleep(0.35 if first else 2.0)
        first = False


def main():
    # Windows görev çubuğu simgesi: QApplication'dan önce (mümkün olan en erken)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "KarabukUni.EnesBozkurt.AeroSenseAI.2.0"
            )
        except Exception:
            pass
    print("[AeroSense]", NOTICE_ONE_LINE)
    print("[AeroSense]", COPYRIGHT_LINE)
    stop_event = threading.Event()
    state = SharedState(history_max=config.HISTORY_MAX if hasattr(config, "HISTORY_MAX") else 800)
    engine = AIEngine()
    engine_holder = {"engine": engine}

    csv_logger = CsvLogger()
    daily = DailyCsvLogger()
    start_receiver_thread(state, csv_logger, stop_event)
    # Weak-label olay sınıflandırması (sigara/duman/havasız/kalabalık proxy)
    start_event_classifier_thread(state, stop_event, interval_sec=2.0)
    run_flask_thread(state, engine_holder)

    ai_thread = threading.Thread(
        target=_ai_loop,
        args=(state, engine, stop_event, daily),
        name="aerosense-ai-loop",
        daemon=True,
    )
    ai_thread.start()

    def get_summary():
        return state.get_ai()

    from aerosense_ai.voice_service import VoiceService

    voice = VoiceService(state, get_summary)
    voice.start()

    no_gui = os.environ.get("AEROSENSE_NO_GUI", "").lower() in ("1", "true", "yes")
    if no_gui:
        print("[launcher] GUI yok (AEROSENSE_NO_GUI); Ctrl+C ile cik.")
        try:
            while state.running:
                time.sleep(1)
        except KeyboardInterrupt:
            state.set_shutdown()
            stop_event.set()
        return

    try:
        from aerosense_ai.gui_app import run_gui
    except ImportError as e:
        print("[launcher] PyQt5/pyqtgraph yukleyin: %s" % e)
        try:
            while state.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        state.set_shutdown()
        stop_event.set()
        return

    app, win = run_gui(state, engine_holder, voice)
    try:
        rc = app.exec_()
    finally:
        state.set_shutdown()
        stop_event.set()
        voice.stop()
    sys.exit(rc)


if __name__ == "__main__":
    main()
