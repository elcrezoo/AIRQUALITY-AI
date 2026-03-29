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
from aerosense_ai.telegram_notify import maybe_alert_analysis, maybe_channel_stream


def _use_mock():
    return os.environ.get("AEROSENSE_MOCK", "").lower() in ("1", "true", "yes")


def _ai_loop(state, engine, stop_event, daily):
    first = True
    while state.running and not stop_event.is_set():
        latest, ch, ts = state.get_latest()
        if latest:
            try:
                hist = state.get_history(120)
                t_ai = time.perf_counter()
                r = engine.analyze(latest, ch, hist)
                state.set_ai_timing_ms((time.perf_counter() - t_ai) * 1000.0)
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
    state = SharedState(history_max=800)
    engine = AIEngine()
    engine_holder = {"engine": engine}

    csv_logger = CsvLogger()
    daily = DailyCsvLogger()
    if _use_mock():
        from aerosense_ai.mock_feed import start_mock_feed_thread

        start_mock_feed_thread(state, stop_event, interval_sec=1.0)
        print(
            "[launcher] AEROSENSE_MOCK=1 — sahte sensör verisi (PC onizleme; TX2 gerekmez)."
        )
    else:
        start_receiver_thread(state, csv_logger, stop_event)
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
