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

"""Dashboard UI — endüstriyel koyu tema, üç sütun, sabit AI paneli."""
import html
import os
import sys
import time
from collections import deque
from datetime import datetime

import pyqtgraph as pg
from PyQt5.QtCore import QEventLoop, QElapsedTimer, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplashScreen,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from . import config
from . import project_meta
from . import sys_metrics
from . import user_settings
from .ai_engine import sensor_health_tr
from .daily_csv import build_tablo_fieldnames
from .industrial_ui import THEME, aqi_style_for_level, apply_pyqtgraph_theme

# Masaüstü yerleşim (piksel)
SIDEBAR_WIDTH_EXPANDED = 216
SIDEBAR_WIDTH_COLLAPSED = 56
RIGHT_AI_PANEL_WIDTH = 392

SENSOR_META = {
    "sicaklik": ("Sıcaklık (LM35)", "°C", "Ortam sıcaklığı"),
    "mq7": ("MQ-7 — CO / yanıcı gaz", "V", "Analog çıkış"),
    "mq135": ("MQ-135 — hava kalitesi", "V", "NOx benzeri gaz"),
    "toz": ("Toz / PM", "V", "Partikül sensörü"),
}

SENSOR_COLORS = {
    "sicaklik": THEME["blue"],
    "mq7": THEME["orange"],
    "mq135": THEME["green"],
    "toz": THEME["purple"],
}

SENSOR_META_EN = {
    "sicaklik": ("Temperature (LM35)", "°C", "Ambient temperature"),
    "mq7": ("MQ-7 — CO / combustible gas", "V", "Analog output"),
    "mq135": ("MQ-135 — air quality", "V", "NOx-like gas"),
    "toz": ("Dust / PM", "V", "Particle sensor"),
}


def _sensor_meta_for_lang(lang, key):
    if (lang or "tr") == "en":
        return SENSOR_META_EN.get(key, SENSOR_META.get(key, (key, "", "")))
    return SENSOR_META.get(key, (key, "", ""))


def _estimate_sample_hz(hist):
    """Geçmiş zaman damgalarından medyan örnekleme sıklığı."""
    if not hist or len(hist) < 2:
        return None
    ts = [h["t"] for h in hist[-40:]]
    dts = []
    for i in range(1, len(ts)):
        d = ts[i] - ts[i - 1]
        if d > 1e-4:
            dts.append(d)
    if not dts:
        return None
    dts.sort()
    med = dts[len(dts) // 2]
    if med <= 0:
        return None
    return 1.0 / med


def _badge_text(lang, status):
    L = "en" if (lang or "tr") == "en" else "tr"
    key = status if status in ("ok", "uyari") else "hata"
    return {
        "tr": {
            "ok": "● Normal",
            "uyari": "● Uyarı",
            "hata": "● Hata / bekleme",
        },
        "en": {
            "ok": "● OK",
            "uyari": "● Warning",
            "hata": "● Error / idle",
        },
    }[L][key]


UI_STR = {
    "tr": {
        "nav": [
            "📊  Genel bakış",
            "📈  Sensör grafikleri",
            "🧠  AI merkezi",
            "📋  Sağlık & kanallar",
            "📁  Geçmiş & CSV",
            "📋  Veri günlüğü",
            "🌐  API & uzak",
            "⚙  Ayarlar",
        ],
        "menu_title": "MENÜ",
        "collapse_on": "◀ Menüyü daralt",
        "collapse_off": "▶ Menü",
        "brand_sub": "v2.0 · Jetson TX2 · NI DAQ 6002",
        "ai_stub_hint": "AI özeti ve ses kontrolü sağ sütunda.",
        "ai_hub_title": "AI merkezi — tam görünüm",
        "ai_hub_intro": (
            "Özet, uyarılar, tahminler ve detay bu sayfada. Sağ sütun: kısayollar, soru kutusu, "
            "AI günlüğü ve ses paneli — birbirinden bağımsız çalışır."
        ),
        "hist_title": "Günlük CSV ve veri klasörü",
        "data_log_title": "Veri günlüğü",
        "data_log_hint": "AI döngüsüyle güncellenen son 50 satır (aynı sütunlar günlük CSV ile). Dosya: data/logs/GG-AA-YYYY.csv",
        "overview_data_snap": "Son kayıtlar (özet)",
        "hdr_tarih_saat": "Tarih / saat",
        "hdr_genel_saglik": "Genel sağlık",
        "hdr_aqi_seviye": "AQI seviye",
        "hdr_aqi_indeks": "AQI indeks",
        "hdr_guven_yuzde": "Güven %",
        "hdr_anomali": "Anomali",
        "hdr_co_tahmin_ppm": "CO tahmin (ppm)",
        "hdr_nox_tahmin_ppm": "NOx tahmin (ppm)",
        "hdr_pm25_tahmin": "PM2.5 tahmin",
        "hdr_sicaklik_c": "Sıcaklık °C (AI)",
        "hdr_olcum": "Ölçüm %s",
        "hdr_durum": "Durum %s",
        "api_title": "REST uçları (özet)",
        "settings_title": "Yerel ayarlar ve bildirimler",
        "settings_tg_gb": "Telegram bot",
        "settings_tg_enable": "Telegram bildirimleri",
        "settings_tg_token": "Bot token",
        "settings_tg_chat": "Chat ID",
        "settings_tg_crit": "Sensör uyarı / hata bildir",
        "settings_tg_aqi": "Kötü AQI bildir",
        "settings_tg_stream": "Kanala / gruba düzenli özet gönder",
        "settings_tg_stream_sec": "Özet aralığı (sn)",
        "settings_save": "Ayarları kaydet",
        "settings_test_tg": "Test mesajı",
        "settings_saved": "Ayarlar config/user_settings.json dosyasına kaydedildi.",
        "settings_tg_ok": "Telegram test mesajı gönderildi.",
        "settings_tg_fail": "Gönderilemedi: token, chat ID veya ağ bağlantısını kontrol edin.",
        "settings_path_lbl": "Ayar dosyası",
        "settings_env_hint": "Ortam (salt okunur)",
        "badge_daq": "DAQ",
        "badge_rf": "RF",
        "badge_ai": "AI",
        "badge_warn": "Uyarı",
        "uptime_lbl": "Çalışma süresi",
        "res_cpu": "CPU",
        "res_ram": "RAM",
        "res_gpu": "GPU",
        "bottom_alerts": "Aktif uyarılar",
        "bottom_aqi_hist": "AQI geçmişi (oturum)",
        "bottom_lstm": "Tahmin eğilimi (kural)",
        "chart_live": "Canlı",
        "chart_1m": "1 dk",
        "chart_5m": "5 dk",
        "chart_30m": "30 dk",
        "norm_plot": "Normalize",
        "quick_co": "CO raporu",
        "quick_health": "Sensör sağlığı",
        "quick_csv": "CSV yolu",
        "quick_pred": "Tahmin",
        "ai_log_title": "AI günlüğü",
        "ask_placeholder": "Soru yazın…",
        "btn_send": "Gönder",
        "btn_mic": "🎤 Sesli komut",
        "btn_speak": "🔊 Sesli özet",
        "btn_help": "❔ AI nasıl çalışır?",
        "btn_full": "⛶ Tam ekran",
        "trend_gb": "Genel trend — tüm kanallar (özet)",
        "graphs_hint": "Her sensör <b>ayrı eksende</b> çizilir; değer kutusu anlık ölçümü gösterir.",
        "ai_page_title": "Yapay zeka özeti ve sesli asistan",
        "ai_box": "AI — yorum ve öneriler",
        "voice_box": "Ses — TTS · otomatik bildirim · sesli komut",
        "health_title": "Kanal bazlı sağlık ve aralık kontrolü",
        "tbl_ch": "Kanal",
        "tbl_st": "Durum",
        "tbl_msg": "Açıklama",
        "hero_wait": "Özet: veri bekleniyor (TCP üzerinden verici bağlayın).",
        "aqi_title": "Hava kalitesi özeti",
        "aqi_pending": "AQI henüz hesaplanmadı.",
        "stable": "✓ Stabil",
        "anomaly": "⚠ Anomali",
        "lang_label": "Dil",
        "voice_hint": (
            "Komutlar: <i>durum</i>, <i>hava kalitesi</i>, <i>özet</i>, <i>status</i>. "
            "Mikrofon açıkken <b>%(sec).0f sn</b> içinde konuşun. Otomatik AI sesi: %(auto)s"
        ),
        "no_analysis": "Henüz analiz yok.",
        "voice_tts_ok": "✓ TTS aktif",
        "voice_tts_bad": "✗ TTS: %s",
        "voice_stt_ok": "✓ Mikrofon / sesli komut",
        "voice_stt_bad": "✗ STT: %s",
        "voice_heard": "Son duyulan komut:",
        "voice_spoke": "Son sesli çıktı:",
        "voice_auto_on": "açık",
        "voice_auto_off": "kapalı",
        "label_confidence": "Güven",
        "dlg_summary_title": "Özet metni",
        "no_data": "Veri yok.",
        "ai_sec_summary": "📝 Canlı özet",
        "ai_sec_advice": "💡 Öneri ve sağlık eşiği",
        "ai_sec_alerts": "⚠ Uyarılar",
        "ai_sec_estimates": "📊 Tahmini kirleticiler",
        "ai_sec_ml": "🤖 Model / güven",
        "ai_sec_detail": "📋 Detaylı analiz metni",
        "ai_updated": "Son güncelleme: %s",
        "ai_no_analysis_run": "AI analizi henüz çalışmadı veya sensör verisi yok.",
        "ai_hint_ask": (
            "Kısa özet için «durum» veya «özet» yazın ya da 🔊 ile sesli özet alın."
        ),
        "ai_hint_no_sensor": (
            "Sensör verisi geldiğinde analiz burada görünür. Verici bağlantısını ve TCP portunu kontrol edin."
        ),
        "ai_no_alerts": "Şu an tetiklenen uyarı yok.",
        "ai_est_co": "CO (tahmini)",
        "ai_est_nox": "NOx benzeri",
        "ai_est_pm": "PM₂.₅ tahmini",
        "ai_est_temp": "Sıcaklık",
        "ai_conf_caption": "Güven skoru (ML olasılık + kural tabanı)",
    },
    "en": {
        "nav": [
            "📊  Overview",
            "📈  Sensor charts",
            "🧠  AI hub",
            "📋  Health & channels",
            "📁  History & CSV",
            "📋  Data log",
            "🌐  API & remote",
            "⚙  Settings",
        ],
        "menu_title": "MENU",
        "collapse_on": "◀ Collapse menu",
        "collapse_off": "▶ Menu",
        "brand_sub": "v2.0 · Jetson TX2 · NI DAQ 6002",
        "ai_stub_hint": "AI summary and voice are in the right column.",
        "ai_hub_title": "AI hub — full view",
        "ai_hub_intro": (
            "Summary, alerts, estimates and full detail on this page. The right column: shortcuts, "
            "ask box, AI log and voice — independent from this view."
        ),
        "hist_title": "Daily CSV and data folder",
        "data_log_title": "Data log",
        "data_log_hint": "Last 50 rows from the AI loop (same columns as the daily CSV). File: data/logs/YYYY-MM-DD.csv",
        "overview_data_snap": "Recent rows (summary)",
        "hdr_tarih_saat": "Date / time",
        "hdr_genel_saglik": "Overall health",
        "hdr_aqi_seviye": "AQI level",
        "hdr_aqi_indeks": "AQI index",
        "hdr_guven_yuzde": "Confidence %",
        "hdr_anomali": "Anomaly",
        "hdr_co_tahmin_ppm": "CO est. (ppm)",
        "hdr_nox_tahmin_ppm": "NOx est. (ppm)",
        "hdr_pm25_tahmin": "PM2.5 est.",
        "hdr_sicaklik_c": "Temp °C (AI)",
        "hdr_olcum": "Reading %s",
        "hdr_durum": "Status %s",
        "api_title": "REST endpoints (summary)",
        "settings_title": "Local settings & alerts",
        "settings_tg_gb": "Telegram bot",
        "settings_tg_enable": "Enable Telegram alerts",
        "settings_tg_token": "Bot token",
        "settings_tg_chat": "Chat ID",
        "settings_tg_crit": "Alert on sensor warning / error",
        "settings_tg_aqi": "Alert on poor AQI",
        "settings_tg_stream": "Post periodic summary to channel / group",
        "settings_tg_stream_sec": "Summary interval (sec)",
        "settings_save": "Save settings",
        "settings_test_tg": "Send test message",
        "settings_saved": "Saved to config/user_settings.json",
        "settings_tg_ok": "Telegram test message sent.",
        "settings_tg_fail": "Failed: check token, chat ID, or network.",
        "settings_path_lbl": "Settings file",
        "settings_env_hint": "Environment (read-only)",
        "badge_daq": "DAQ",
        "badge_rf": "RF",
        "badge_ai": "AI",
        "badge_warn": "Alerts",
        "uptime_lbl": "Uptime",
        "res_cpu": "CPU",
        "res_ram": "RAM",
        "res_gpu": "GPU",
        "bottom_alerts": "Active alerts",
        "bottom_aqi_hist": "AQI session history",
        "bottom_lstm": "Trend hint (rules)",
        "chart_live": "Live",
        "chart_1m": "1 min",
        "chart_5m": "5 min",
        "chart_30m": "30 min",
        "norm_plot": "Normalized",
        "quick_co": "CO report",
        "quick_health": "Sensor health",
        "quick_csv": "CSV path",
        "quick_pred": "Forecast",
        "ai_log_title": "AI log",
        "ask_placeholder": "Ask a question…",
        "btn_send": "Send",
        "btn_mic": "🎤 Voice",
        "btn_speak": "🔊 Speak summary",
        "btn_help": "❔ How does AI work?",
        "btn_full": "⛶ Full screen",
        "trend_gb": "Combined trend — all channels (summary)",
        "graphs_hint": "Each sensor uses <b>its own axis</b>; the value box shows the live reading.",
        "ai_page_title": "AI summary and voice assistant",
        "ai_box": "AI — insights and recommendations",
        "voice_box": "Voice — TTS · auto alert · voice commands",
        "health_title": "Per-channel health and range checks",
        "tbl_ch": "Channel",
        "tbl_st": "Status",
        "tbl_msg": "Detail",
        "hero_wait": "Summary: waiting for data (connect the sender over TCP).",
        "aqi_title": "Air quality summary",
        "aqi_pending": "AQI not computed yet.",
        "stable": "✓ Stable",
        "anomaly": "⚠ Anomaly",
        "lang_label": "Language",
        "voice_hint": (
            "Try: <i>status</i>, <i>air quality</i>, <i>summary</i>, <i>durum</i>. "
            "Speak within <b>%(sec).0f s</b> while the mic is active. Auto AI voice: %(auto)s"
        ),
        "no_analysis": "No analysis yet.",
        "voice_tts_ok": "✓ TTS on",
        "voice_tts_bad": "✗ TTS: %s",
        "voice_stt_ok": "✓ Mic / voice commands",
        "voice_stt_bad": "✗ STT: %s",
        "voice_heard": "Last heard:",
        "voice_spoke": "Last spoken:",
        "voice_auto_on": "on",
        "voice_auto_off": "off",
        "label_confidence": "Confidence",
        "dlg_summary_title": "Summary",
        "no_data": "No data.",
        "ai_sec_summary": "📝 Live summary",
        "ai_sec_advice": "💡 Guidance & thresholds",
        "ai_sec_alerts": "⚠ Alerts",
        "ai_sec_estimates": "📊 Estimated pollutants",
        "ai_sec_ml": "🤖 Model / confidence",
        "ai_sec_detail": "📋 Detailed analysis",
        "ai_updated": "Last update: %s",
        "ai_no_analysis_run": "No AI analysis yet or no sensor data.",
        "ai_hint_ask": (
            "Type «status» or «summary» for a short overview, or use 🔊 Speak summary."
        ),
        "ai_hint_no_sensor": (
            "Analysis appears when sensor data arrives. Check sender connection and TCP port."
        ),
        "ai_no_alerts": "No active alerts.",
        "ai_est_co": "CO (est.)",
        "ai_est_nox": "NOx-like",
        "ai_est_pm": "PM₂.₅ est.",
        "ai_est_temp": "Temperature",
        "ai_conf_caption": "Confidence (ML probability + rules)",
    },
}


def _apply_plot_theme():
    apply_pyqtgraph_theme()


def _windows_pin_taskbar_icon():
    """Windows 7+ görev çubuğunda .ico göstermek için (python.exe yerine uygulama kimliği)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "KarabukUni.EnesBozkurt.AeroSenseAI.2.0"
        )
    except Exception:
        pass


def _load_app_icon():
    path = config.WINDOW_ICON_PATH
    if not path:
        return QIcon()
    abs_path = os.path.normpath(os.path.abspath(path))
    if not os.path.isfile(abs_path):
        return QIcon()
    # addFile: .ico içindeki çoklu çözünürlükleri kullanır (görev çubuğu için daha güvenilir)
    ic = QIcon()
    ic.addFile(abs_path)
    if ic.isNull():
        pm = QPixmap(abs_path)
        if not pm.isNull():
            ic = QIcon(pm)
    return ic


def _create_splash_screen(app_icon):
    """
    Uygulama açılır açılmaz gösterilir: splash görseli varsa onu, yoksa markalı yedek ekranı kullanır.
    """
    min_ms = int(os.environ.get("AEROSENSE_SPLASH_MS", "2500"))
    if os.environ.get("AEROSENSE_NO_SPLASH", "").lower() in ("1", "true", "yes", "on"):
        return None, min_ms

    def _finish(sp):
        if not app_icon.isNull():
            sp.setWindowIcon(app_icon)
        return sp

    splash_path = config.SPLASH_IMAGE_PATH
    if splash_path:
        abs_p = os.path.normpath(os.path.abspath(splash_path))
        if os.path.isfile(abs_p):
            pm = QPixmap(abs_p)
            if not pm.isNull():
                if pm.height() > 920:
                    pm = pm.scaledToHeight(920, Qt.SmoothTransformation)
                return _finish(
                    QSplashScreen(pm, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
                ), min_ms

    w_px, h_px = 800, 450
    pm = QPixmap(w_px, h_px)
    pm.fill(QColor("#0d1117"))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QColor("#58a6ff"))
    painter.setFont(QFont("Segoe UI", 26, QFont.Bold))
    painter.drawText(
        0, 70, w_px, 44, Qt.AlignHCenter, "%s %s" % (project_meta.PROJECT_NAME, project_meta.VERSION)
    )
    painter.setPen(QColor("#e6edf3"))
    painter.setFont(QFont("Segoe UI", 12))
    painter.drawText(
        40,
        130,
        w_px - 80,
        220,
        Qt.AlignCenter | Qt.TextWordWrap,
        "%s\n%s" % (project_meta.AFFILIATION, project_meta.AUTHOR),
    )
    painter.setPen(QColor("#6e7681"))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(
        0,
        h_px - 48,
        w_px,
        40,
        Qt.AlignHCenter | Qt.TextWordWrap,
        project_meta.WEBSITE,
    )
    painter.end()
    return _finish(
        QSplashScreen(pm, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    ), min_ms


AI_HELP_HTML = """
<h2>Yapay zeka nasıl çalışır?</h2>
<p><b>1) Kural tabanlı AQI</b> — Voltaj/sıcaklıktan tahmini kirletici ölçeği ve 6 kademeli tablo.</p>
<p><b>2) ML</b> — <code>train_model.py</code> ile <code>aerosense_model.joblib</code>.</p>
<p><b>3) Anomali</b> — IForest veya z-skor.</p>
"""


def _mono_font(px=12, bold=False):
    for name in ("JetBrains Mono", "Cascadia Mono", "Consolas", "Courier New"):
        f = QFont(name, px)
        if bold:
            f.setBold(True)
        if f.exactMatch() or name == "Courier New":
            return f
    f = QFont()
    f.setFamily("monospace")
    f.setPointSize(px)
    f.setBold(bold)
    return f


class SensorCard(QFrame):
    def __init__(self, key, lang="tr", parent=None, show_sparkline=False):
        super(SensorCard, self).__init__(parent)
        self._key = key
        self._lang = lang or "tr"
        self.setObjectName("SensorCard")
        self.setMinimumHeight(130)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        self._title = QLabel()
        self._title.setObjectName("CardTitle")
        lay.addWidget(self._title)
        self._sub = QLabel()
        self._sub.setObjectName("CardSub")
        self._sub.setWordWrap(True)
        lay.addWidget(self._sub)
        self._val = QLabel("—")
        self._val.setObjectName("CardValue")
        self._val.setFont(_mono_font(22, True))
        lay.addWidget(self._val)
        self._unit = QLabel()
        self._unit.setObjectName("CardUnit")
        lay.addWidget(self._unit)
        self._delta = QLabel("")
        self._delta.setObjectName("CardDelta")
        self._delta.setTextFormat(Qt.RichText)
        lay.addWidget(self._delta)
        self._badge = QLabel("—")
        self._badge.setObjectName("CardBadge")
        lay.addWidget(self._badge)
        self._spark = None
        if show_sparkline:
            self._spark = pg.PlotWidget()
            self._spark.setFixedHeight(54)
            self._spark.setBackground(THEME["bg"])
            self._spark.showGrid(False, False)
            self._spark.hideButtons()
            self._spark.setMenuEnabled(False)
            for ax in ("left", "bottom"):
                try:
                    self._spark.hideAxis(ax)
                except Exception:
                    pass
            lay.addWidget(self._spark)
        self._apply_labels()

    def _apply_labels(self):
        title, unit, sub = _sensor_meta_for_lang(self._lang, self._key)
        self._title.setText(title)
        self._sub.setText(sub)
        self._unit.setText(unit)

    def set_language(self, lang):
        self._lang = lang or "tr"
        self._apply_labels()

    def set_reading(self, value, status, detail_tr, prev_value=None):
        if value is None:
            self._val.setText("—")
            self._delta.clear()
        else:
            try:
                fv = float(value)
                self._val.setText("%.5g" % fv)
                if prev_value is not None:
                    try:
                        d = fv - float(prev_value)
                        col = THEME["green"] if d <= 0 else THEME["red"]
                        self._delta.setText(
                            "<span style='color:%s;font-family:monospace;font-size:11px'>Δ %s</span>"
                            % (col, ("%+.4g" % d))
                        )
                    except (TypeError, ValueError):
                        self._delta.clear()
                else:
                    self._delta.clear()
            except (TypeError, ValueError):
                self._val.setText(str(value))
                self._delta.clear()
        accent = SENSOR_COLORS.get(self._key, THEME["accent_cyan"])
        if status == "ok":
            self._badge.setText(_badge_text(self._lang, "ok"))
            self._badge.setStyleSheet("color: %s; font-weight: 700;" % THEME["green"])
            self.setStyleSheet(
                "#SensorCard { border-left: 3px solid %s; border-radius: 12px; }" % accent
            )
        elif status == "uyari":
            self._badge.setText(_badge_text(self._lang, "uyari"))
            self._badge.setStyleSheet("color: %s; font-weight: 700;" % THEME["orange"])
            self.setStyleSheet(
                "#SensorCard { border-left: 3px solid %s; border-radius: 12px; }"
                % THEME["orange"]
            )
        else:
            self._badge.setText(_badge_text(self._lang, "hata"))
            self._badge.setStyleSheet("color: %s; font-weight: 700;" % THEME["red"])
            self.setStyleSheet(
                "#SensorCard { border-left: 3px solid %s; border-radius: 12px; }" % THEME["red"]
            )
        self.setToolTip(detail_tr or "")

    def update_spark(self, hist, max_n=64):
        if not self._spark or not hist:
            return
        ys = []
        for it in hist[-max_n:]:
            if self._key in it.get("data", {}):
                try:
                    ys.append(float(it["data"][self._key]))
                except (TypeError, ValueError):
                    pass
        self._spark.clear()
        if len(ys) < 2:
            return
        c = SENSOR_COLORS.get(self._key, THEME["accent_cyan"])
        xi = list(range(len(ys)))
        self._spark.plot(xi, ys, pen=pg.mkPen(color=c, width=2))
        mn, mx = min(ys), max(ys)
        pad = max((mx - mn) * 0.15, 1e-6)
        self._spark.setYRange(mn - pad, mx + pad)


class MainWindow(QMainWindow):
    def __init__(self, state, engine_holder, voice_service=None, app_icon=None):
        super(MainWindow, self).__init__()
        self.state = state
        self.engine_holder = engine_holder
        self.voice = voice_service
        self._app_icon = app_icon if app_icon is not None else QIcon()
        self._lang = getattr(config, "UI_LANG", "tr")
        if self._lang not in ("tr", "en"):
            self._lang = "tr"
        self._sensor_cards = {}
        self._per_ch_plots = {}
        self._per_ch_values = {}
        self._plot_overview = None
        self._chart_window_sec = None
        self._aqi_hist = deque(maxlen=120)
        self._prev_sensor_vals = {}
        self._boot = time.time()
        self._last_ai_log_hash = None
        self._last_aqi_tick = 0.0
        self._gpu_sample = (None, None)
        self._gpu_sample_t = 0.0
        self.setWindowTitle("%s v2.0 — %s" % (project_meta.PROJECT_NAME, project_meta.AUTHOR))
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)
        _apply_plot_theme()
        self._apply_global_style()
        self._build_ui()
        self.statusBar().showMessage(project_meta.NOTICE_ONE_LINE)
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(500)
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)

    def _apply_global_style(self):
        bg, s1, s2, bd, tx, mu, cy, pu = (
            THEME["bg"],
            THEME["surface1"],
            THEME["surface2"],
            THEME["border"],
            THEME["text"],
            THEME["text_muted"],
            THEME["accent_cyan"],
            THEME["purple"],
        )
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background-color: %s; color: %s; font-family: 'Segoe UI', system-ui; }
            QLabel { color: %s; }
            #SideBar {
                background-color: %s;
                border-right: 1px solid %s;
            }
            #SideTitle {
                color: %s;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
                padding: 8px 10px 4px 10px;
            }
            QListWidget#NavList {
                background: transparent;
                border: none;
                outline: none;
                padding: 6px;
            }
            QListWidget#NavList::item {
                color: %s;
                padding: 12px 10px;
                border-radius: 8px;
                margin: 3px 0;
            }
            QListWidget#NavList::item:hover { background-color: %s; }
            QListWidget#NavList::item:selected {
                background-color: #162038;
                border-left: 2px solid %s;
            }
            #TopHeader {
                background-color: %s;
                border-bottom: 1px solid %s;
                min-height: 50px;
                max-height: 56px;
            }
            #BrandTitle { font-size: 18px; font-weight: 800; color: %s; }
            #BrandSub { font-size: 11px; color: %s; }
            #BadgePill {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            #ClockLabel { color: %s; font-family: Consolas, monospace; font-size: 13px; font-weight: 700; }
            QComboBox {
                background-color: %s;
                color: %s;
                border: 1px solid %s;
                border-radius: 8px;
                padding: 6px 10px;
                min-width: 5em;
            }
            QComboBox:hover { border-color: %s; }
            QComboBox::drop-down { border: none; width: 20px; }
            #AqiBanner {
                border: 1px solid %s;
                border-radius: 12px;
                background-color: %s;
            }
            #HeroStrip, #AiHeroStrip {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 12px;
            }
            #SensorCard {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 12px;
            }
            #CardTitle { font-size: 11px; font-weight: 800; color: %s; }
            #CardSub { font-size: 10px; color: %s; }
            #CardValue { font-size: 26px; font-weight: 800; color: %s; }
            #CardUnit { font-size: 10px; color: %s; }
            QGroupBox {
                font-weight: 700;
                color: %s;
                border: 1px solid %s;
                border-radius: 9px;
                margin-top: 10px;
                padding-top: 12px;
                background-color: %s;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QPushButton {
                background-color: %s;
                color: %s;
                border: 1px solid %s;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { border-color: %s; background-color: #121a30; }
            QPushButton#ChartFilterOn {
                background-color: #162038;
                border-color: %s;
                color: %s;
            }
            QPushButton#MicBtn {
                background-color: %s;
                color: #fff;
                border: 1px solid %s;
            }
            QTableWidget {
                background-color: %s;
                gridline-color: %s;
                border: 1px solid %s;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: %s;
                color: %s;
                padding: 8px;
                border: none;
                border-bottom: 1px solid %s;
            }
            QTextBrowser, QLineEdit {
                background-color: %s;
                color: %s;
                border: 1px solid %s;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
            }
            #AiSectionCard {
                background-color: #0c1020;
                border: 1px solid %s;
                border-radius: 10px;
            }
            #AiSectionTitle { color: %s; font-size: 11px; font-weight: 800; }
            #AiMutedCaption { color: %s; font-size: 10px; }
            QProgressBar {
                border: 1px solid %s;
                border-radius: 8px;
                background-color: %s;
                text-align: center;
                color: %s;
                font-weight: 700;
                font-size: 10px;
                min-height: 20px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 %s, stop:1 %s);
            }
            QScrollBar:vertical { background: #0A0E1C; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #2A3050; border-radius: 3px; min-height: 24px; }
            """
            % (
                bg,
                tx,
                tx,
                s2,
                bd,
                mu,
                tx,
                s1,
                cy,
                s1,
                bd,
                tx,
                mu,
                s1,
                bd,
                cy,
                s1,
                tx,
                bd,
                cy,
                bd,
                s1,
                s1,
                bd,
                s1,
                bd,
                cy,
                mu,
                tx,
                mu,
                cy,
                bd,
                s1,
                s1,
                tx,
                bd,
                cy,
                cy,
                cy,
                pu,
                pu,
                s1,
                bd,
                bd,
                s2,
                mu,
                bd,
                s1,
                tx,
                bd,
                bd,
                cy,
                mu,
                bd,
                s1,
                tx,
                cy,
                pu,
            )
        )

    def _tick_clock(self):
        lbl = getattr(self, "_lbl_clock", None)
        if lbl is not None:
            lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _uptime_hms(self):
        sec = int(time.time() - getattr(self, "_boot", time.time()))
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return "%02d:%02d:%02d" % (h, m, s)

    def _on_chart_span(self, sec):
        self._chart_window_sec = sec
        for k, b in getattr(self, "_chart_btns", {}).items():
            b.setChecked(k == sec)

    def _toggle_norm_plot(self, checked):
        self._plot_normalize = bool(checked)

    def _mini_res_bar(self, caption_attr, bar_attr, pct_attr):
        row = QHBoxLayout()
        cap = QLabel()
        setattr(self, caption_attr, cap)
        cap.setObjectName("AiMutedCaption")
        cap.setStyleSheet("font-size:11px;font-weight:700;color:#C0CCE8;min-width:36px;")
        row.addWidget(cap)
        pb = QProgressBar()
        pb.setRange(0, 100)
        pb.setValue(0)
        pb.setTextVisible(False)
        pb.setFixedHeight(11)
        setattr(self, bar_attr, pb)
        row.addWidget(pb, 1)
        pct = QLabel("—%")
        pct.setObjectName("ClockLabel")
        pct.setStyleSheet("font-size:11px;font-weight:800;min-width:40px;")
        setattr(self, pct_attr, pct)
        row.addWidget(pct)
        return row

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_v = QVBoxLayout(root)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        top = QFrame()
        top.setObjectName("TopHeader")
        th = QHBoxLayout(top)
        th.setContentsMargins(14, 8, 14, 8)
        brand = QVBoxLayout()
        bt = QLabel("AeroSense AI")
        bt.setObjectName("BrandTitle")
        brand.addWidget(bt)
        self._lbl_brand_sub = QLabel()
        self._lbl_brand_sub.setObjectName("BrandSub")
        brand.addWidget(self._lbl_brand_sub)
        th.addLayout(brand)
        th.addSpacing(20)
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._badge_daq = QLabel()
        self._badge_rf = QLabel()
        self._badge_ai = QLabel()
        self._badge_warn = QLabel()
        for b in (self._badge_daq, self._badge_rf, self._badge_ai, self._badge_warn):
            b.setObjectName("BadgePill")
            badge_row.addWidget(b)
        th.addLayout(badge_row)
        th.addStretch(1)
        self.lbl_api = QLabel()
        self.lbl_api.setTextFormat(Qt.RichText)
        self.lbl_api.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        th.addWidget(self.lbl_api, 0, Qt.AlignRight | Qt.AlignVCenter)
        th.addSpacing(12)
        self._lbl_clock = QLabel()
        self._lbl_clock.setObjectName("ClockLabel")
        th.addWidget(self._lbl_clock, 0, Qt.AlignRight | Qt.AlignVCenter)
        th.addSpacing(10)
        self._lbl_lang_tag = QLabel()
        self._lbl_lang_tag.setObjectName("AiMutedCaption")
        th.addWidget(self._lbl_lang_tag, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Türkçe", "tr")
        self.combo_lang.addItem("English", "en")
        self.combo_lang.setCurrentIndex(0 if self._lang == "tr" else 1)
        self.combo_lang.currentIndexChanged.connect(self._on_lang_combo)
        th.addWidget(self.combo_lang, 0, Qt.AlignRight | Qt.AlignVCenter)
        th.addSpacing(8)
        self.btn_full = QPushButton()
        self.btn_full.clicked.connect(self._toggle_fullscreen)
        th.addWidget(self.btn_full, 0, Qt.AlignRight | Qt.AlignVCenter)
        main_v.addWidget(top)

        body = QWidget()
        bh = QHBoxLayout(body)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(0)

        self._sidebar = QFrame()
        self._sidebar.setObjectName("SideBar")
        self._sidebar.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
        side_lay = QVBoxLayout(self._sidebar)
        side_lay.setContentsMargins(0, 10, 0, 10)
        self._lbl_side_title = QLabel()
        self._lbl_side_title.setObjectName("SideTitle")
        side_lay.addWidget(self._lbl_side_title)

        self._lbl_uptime_cap = QLabel()
        self._lbl_uptime_cap.setObjectName("AiMutedCaption")
        side_lay.addWidget(self._lbl_uptime_cap)
        self._lbl_uptime = QLabel("00:00:00")
        self._lbl_uptime.setFont(_mono_font(12, True))
        side_lay.addWidget(self._lbl_uptime)
        side_lay.addSpacing(4)
        side_lay.addLayout(self._mini_res_bar("_cap_cpu", "_pb_cpu", "_lbl_cpu_pct"))
        side_lay.addLayout(self._mini_res_bar("_cap_ram", "_pb_ram", "_lbl_ram_pct"))
        side_lay.addLayout(self._mini_res_bar("_cap_gpu", "_pb_gpu", "_lbl_gpu_pct"))
        side_lay.addSpacing(8)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        for text in UI_STR[self._lang]["nav"]:
            QListWidgetItem(text, self.nav)
        self.nav.setCurrentRow(0)
        side_lay.addWidget(self.nav, 1)

        self.btn_collapse = QPushButton()
        self.btn_collapse.setStyleSheet("font-size: 11px; padding: 8px;")
        self.btn_collapse.clicked.connect(self._toggle_sidebar)
        side_lay.addWidget(self.btn_collapse)
        bh.addWidget(self._sidebar)

        center_col = QWidget()
        cv = QVBoxLayout(center_col)
        cv.setContentsMargins(12, 10, 8, 10)
        cv.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_speak = QPushButton()
        self.btn_speak.clicked.connect(self._on_speak)
        btn_row.addWidget(self.btn_speak)
        self.btn_ai_help = QPushButton()
        self.btn_ai_help.clicked.connect(self._show_ai_help)
        btn_row.addWidget(self.btn_ai_help)
        btn_row.addStretch()
        cv.addLayout(btn_row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_overview())
        self.stack.addWidget(self._page_graphs())
        self.stack.addWidget(self._page_ai_hub())
        self.stack.addWidget(self._page_health())
        self.stack.addWidget(self._page_history())
        self.stack.addWidget(self._page_data_log())
        self.stack.addWidget(self._page_api())
        self.stack.addWidget(self._page_settings())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        cv.addWidget(self.stack, 1)

        self.lbl_wm = QLabel(project_meta.NOTICE_GUI_FOOTER)
        self.lbl_wm.setWordWrap(True)
        self.lbl_wm.setObjectName("AiMutedCaption")
        cv.addWidget(self.lbl_wm)

        bh.addWidget(center_col, 1)

        self._right_ai = self._build_right_ai_column()
        self._right_ai.setFixedWidth(RIGHT_AI_PANEL_WIDTH)
        self._right_ai.setMinimumWidth(RIGHT_AI_PANEL_WIDTH)
        self._right_ai.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        bh.addWidget(self._right_ai)

        main_v.addWidget(body, 1)

        sb = self.statusBar()
        sb.setStyleSheet(
            "QStatusBar { background: #09102A; border-top: 1px solid #1C2240; "
            "min-height: 28px; font-size: 11px; padding: 2px 8px; }"
        )
        self._sb_left = QLabel()
        self._sb_right = QLabel()
        self._sb_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sb.addWidget(self._sb_left, 1)
        sb.addPermanentWidget(self._sb_right)

        port = config.API_PORT
        self._api_port = port
        self._plot_normalize = False
        self._chart_window_sec = None
        self._tick_clock()
        self._apply_header_api_text()
        self._sync_i18n_widgets()
        self._load_user_settings_ui()

    def t(self, key):
        return UI_STR.get(self._lang, UI_STR["tr"]).get(key, key)

    def _data_log_column_title(self, key):
        L = UI_STR.get(self._lang, UI_STR["tr"])
        if key.startswith("olcum_"):
            return L.get("hdr_olcum", "%s") % key[7:]
        if key.startswith("durum_"):
            return L.get("hdr_durum", "%s") % key[7:]
        return L.get("hdr_" + key, key.replace("_", " "))

    def _apply_header_api_text(self):
        port = getattr(self, "_api_port", config.API_PORT)
        host = getattr(config, "API_HOST", "127.0.0.1") or "127.0.0.1"
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        url = "http://%s:%s" % (host, port)
        cy = THEME["accent_cyan"]
        if self._lang == "en":
            self.lbl_api.setText(
                "<span style='color:#8B9BC4;font-size:11px'>REST API</span><br/>"
                "<span style='color:%s;font-family:Consolas,monospace;font-size:12px;font-weight:700'>%s</span>"
                % (cy, html.escape(url))
            )
        else:
            self.lbl_api.setText(
                "<span style='color:#8B9BC4;font-size:11px'>REST API</span><br/>"
                "<span style='color:%s;font-family:Consolas,monospace;font-size:12px;font-weight:700'>%s</span>"
                % (cy, html.escape(url))
            )

    def _sync_i18n_widgets(self):
        self._lbl_side_title.setText(self.t("menu_title"))
        self._lbl_brand_sub.setText(self.t("brand_sub"))
        self._lbl_lang_tag.setText(self.t("lang_label"))
        if getattr(self, "_lbl_uptime_cap", None):
            self._lbl_uptime_cap.setText(self.t("uptime_lbl"))
        if getattr(self, "_cap_cpu", None):
            self._cap_cpu.setText(self.t("res_cpu"))
            self._cap_ram.setText(self.t("res_ram"))
            self._cap_gpu.setText(self.t("res_gpu"))
        if self._sidebar.width() > SIDEBAR_WIDTH_COLLAPSED + 2:
            self.btn_collapse.setText(self.t("collapse_on"))
        else:
            self.btn_collapse.setText(self.t("collapse_off"))
        self.btn_speak.setText(self.t("btn_speak"))
        self.btn_ai_help.setText(self.t("btn_help"))
        self.btn_full.setText(self.t("btn_full"))
        for i, text in enumerate(UI_STR[self._lang]["nav"]):
            it = self.nav.item(i)
            if it:
                it.setText(text)
        if getattr(self, "_gb_trend", None):
            self._gb_trend.setTitle(self.t("trend_gb"))
        if getattr(self, "_btn_norm", None):
            self._btn_norm.setText(self.t("norm_plot"))
        cfmap = (
            (None, "chart_live"),
            (60, "chart_1m"),
            (300, "chart_5m"),
            (1800, "chart_30m"),
        )
        if getattr(self, "_chart_btns", None):
            for sec, key in cfmap:
                b = self._chart_btns.get(sec)
                if b:
                    b.setText(self.t(key))
        if getattr(self, "_gb_bottom_alerts", None):
            self._gb_bottom_alerts.setTitle(self.t("bottom_alerts"))
        if getattr(self, "_gb_bottom_aqi", None):
            self._gb_bottom_aqi.setTitle(self.t("bottom_aqi_hist"))
        if getattr(self, "_gb_bottom_lstm", None):
            self._gb_bottom_lstm.setTitle(self.t("bottom_lstm"))
        if getattr(self, "_gb_overview_data", None):
            self._gb_overview_data.setTitle(self.t("overview_data_snap"))
        if getattr(self, "_lbl_data_log_title", None):
            self._lbl_data_log_title.setText(self.t("data_log_title"))
        if getattr(self, "_lbl_data_log_hint", None):
            self._lbl_data_log_hint.setText(self.t("data_log_hint"))
        if getattr(self, "_lbl_graph_hint", None):
            self._lbl_graph_hint.setText(self.t("graphs_hint"))
        if getattr(self, "_lbl_ai_hub_title", None):
            self._lbl_ai_hub_title.setText(self.t("ai_hub_title"))
        if getattr(self, "_lbl_ai_hub_intro", None):
            self._lbl_ai_hub_intro.setText(self.t("ai_hub_intro"))
        if getattr(self, "_btn_hub_speak", None):
            self._btn_hub_speak.setText(self.t("btn_speak"))
        if getattr(self, "_btn_hub_help", None):
            self._btn_hub_help.setText(self.t("btn_help"))
        if getattr(self, "_hub_i18n_title_pairs", None):
            for lbl, key in self._hub_i18n_title_pairs:
                lbl.setText(self.t(key))
        if getattr(self, "_hub_est_labels", None) and len(self._hub_est_labels) >= 4:
            keys = ("ai_est_co", "ai_est_nox", "ai_est_pm", "ai_est_temp")
            for i, k in enumerate(keys):
                self._hub_est_labels[i].setText(self.t(k))
        if getattr(self, "_hub_lbl_conf_caption", None):
            self._hub_lbl_conf_caption.setText(self.t("ai_conf_caption"))
        if getattr(self, "_lbl_right_ai_title", None):
            self._lbl_right_ai_title.setText(self.t("ai_page_title"))
        if getattr(self, "_lbl_ai_log_cap", None):
            self._lbl_ai_log_cap.setText(self.t("ai_log_title"))
        if getattr(self, "_ai_query", None):
            self._ai_query.setPlaceholderText(self.t("ask_placeholder"))
        if getattr(self, "_btn_ai_send", None):
            self._btn_ai_send.setText(self.t("btn_send"))
        if getattr(self, "_btn_mic", None):
            self._btn_mic.setText(self.t("btn_mic"))
        if getattr(self, "_btn_q_co", None):
            self._btn_q_co.setText(self.t("quick_co"))
            self._btn_q_health.setText(self.t("quick_health"))
            self._btn_q_csv.setText(self.t("quick_csv"))
            self._btn_q_pred.setText(self.t("quick_pred"))
        if getattr(self, "_gb_ai", None):
            self._gb_ai.setTitle(self.t("ai_box"))
        if getattr(self, "_gb_voice", None):
            self._gb_voice.setTitle(self.t("voice_box"))
        if getattr(self, "_lbl_health", None):
            self._lbl_health.setText(self.t("health_title"))
        if getattr(self, "_lbl_hist_title", None):
            self._lbl_hist_title.setText(self.t("hist_title"))
        if getattr(self, "_lbl_api_page_title", None):
            self._lbl_api_page_title.setText(self.t("api_title"))
        if getattr(self, "_lbl_settings_title", None):
            self._lbl_settings_title.setText(self.t("settings_title"))
        if getattr(self, "_gb_telegram", None):
            self._gb_telegram.setTitle(self.t("settings_tg_gb"))
            self._chk_tg_enable.setText(self.t("settings_tg_enable"))
            self._lbl_tg_token.setText(self.t("settings_tg_token"))
            self._lbl_tg_chat.setText(self.t("settings_tg_chat"))
            self._chk_tg_crit.setText(self.t("settings_tg_crit"))
            self._chk_tg_aqi.setText(self.t("settings_tg_aqi"))
            if getattr(self, "_chk_tg_stream", None):
                self._chk_tg_stream.setText(self.t("settings_tg_stream"))
            if getattr(self, "_lbl_tg_stream_sec", None):
                self._lbl_tg_stream_sec.setText(self.t("settings_tg_stream_sec"))
            self._btn_save_settings.setText(self.t("settings_save"))
            self._btn_test_tg.setText(self.t("settings_test_tg"))
            self._lbl_settings_env_cap.setText(self.t("settings_env_hint"))
        if getattr(self, "_ai_i18n_title_pairs", None):
            for lbl, key in self._ai_i18n_title_pairs:
                lbl.setText(self.t(key))
        if getattr(self, "_lbl_ai_conf_caption", None):
            self._lbl_ai_conf_caption.setText(self.t("ai_conf_caption"))
        if getattr(self, "_lbl_ai_est_labels", None) and len(self._lbl_ai_est_labels) >= 4:
            keys = ("ai_est_co", "ai_est_nox", "ai_est_pm", "ai_est_temp")
            for i, k in enumerate(keys):
                self._lbl_ai_est_labels[i].setText(self.t(k))
        self.table.setHorizontalHeaderLabels(
            [self.t("tbl_ch"), self.t("tbl_st"), self.t("tbl_msg")]
        )
        for key, card in self._sensor_cards.items():
            card.set_language(self._lang)
        for key, val_lbl in self._per_ch_values.items():
            parent = val_lbl.parent()
            if isinstance(parent, QGroupBox):
                title, unit, _s = _sensor_meta_for_lang(self._lang, key)
                parent.setTitle("%s (%s)" % (title, unit))
        self._sync_static_info_pages()
        self._apply_header_api_text()

    def _sync_static_info_pages(self):
        if getattr(self, "_lbl_csv_path", None):
            self._lbl_csv_path.setText(os.path.abspath(config.CSV_PATH))
        if getattr(self, "_txt_hist_body", None):
            logs = getattr(config, "LOGS_DIR", "")
            logs_esc = html.escape(os.path.abspath(logs))
            if self._lang == "en":
                body = (
                    "<p style='color:#DDE3F5;line-height:1.55'><b>%s</b></p>"
                    "<ul style='color:#8B9BC4;line-height:1.5'>"
                    "<li><b>Table CSV</b> — <code>data/logs/YYYY-MM-DD.csv</code> (UTF-8)</li>"
                    "<li>Columns: date/time, overall health, AQI, confidence, AI estimates, per-channel reading/status.</li>"
                    "<li>Legacy files with old headers are renamed to <code>_eski_format.csv</code>.</li>"
                    "<li>Logs folder: %s</li></ul>"
                    % (html.escape(self.t("hist_title")), logs_esc)
                )
            else:
                body = (
                    "<p style='color:#DDE3F5;line-height:1.55'><b>%s</b></p>"
                    "<ul style='color:#8B9BC4;line-height:1.5'>"
                    "<li><b>Tablo CSV</b> — <code>data/logs/GG-AA-YYYY.csv</code> (UTF-8)</li>"
                    "<li>Sütunlar: tarih/saat, genel sağlık, AQI, güven, AI tahminleri, kanal ölçüm ve durum.</li>"
                    "<li>Eski farklı başlıklı dosya otomatik <code>_eski_format.csv</code> olarak yedeklenir.</li>"
                    "<li>Klasör: %s</li></ul>"
                    % (html.escape(self.t("hist_title")), logs_esc)
                )
            self._txt_hist_body.setHtml(body)
        port = config.API_PORT
        if getattr(self, "_txt_api_body", None):
            self._txt_api_body.setHtml(
                "<pre style='color:#DDE3F5;font-family:Consolas,monospace;font-size:12px'>"
                "GET  /api/status\n"
                "GET  /api/latest\n"
                "GET  /api/history?n=200\n"
                "GET  /api/ai\n"
                "POST /api/command\n"
                "</pre>"
                "<p style='color:#8B9BC4'>Port: %s</p>" % port
            )
        if getattr(self, "_txt_settings_env", None):
            self._txt_settings_env.setHtml(
                "<pre style='color:#DDE3F5;font-family:Consolas,monospace;font-size:11px'>"
                "AEROSENSE_VOICE=%s\n"
                "AEROSENSE_VOICE_COMMANDS=%s\n"
                "AEROSENSE_LANG=%s\n"
                "AEROSENSE_API_PORT=%s\n"
                "</pre>"
                % (
                    os.environ.get("AEROSENSE_VOICE", ""),
                    os.environ.get("AEROSENSE_VOICE_COMMANDS", ""),
                    os.environ.get("AEROSENSE_LANG", self._lang),
                    os.environ.get("AEROSENSE_API_PORT", str(config.API_PORT)),
                )
            )

    def _on_lang_combo(self, index):
        lang = self.combo_lang.itemData(index)
        if lang is None:
            lang = "tr"
        if lang == self._lang:
            return
        self._lang = lang
        try:
            # Oturum boyunca tercih (yeniden başlatmada env ile birleştirilebilir)
            os.environ["AEROSENSE_LANG"] = self._lang
        except Exception:
            pass
        self._sync_i18n_widgets()

    def _toggle_sidebar(self):
        if self._sidebar.width() > SIDEBAR_WIDTH_COLLAPSED + 2:
            self._sidebar.setFixedWidth(SIDEBAR_WIDTH_COLLAPSED)
            self.nav.setVisible(False)
            self._lbl_side_title.setVisible(False)
            if getattr(self, "_lbl_uptime_cap", None):
                self._lbl_uptime_cap.setVisible(False)
                self._lbl_uptime.setVisible(False)
                for name in ("_cap_cpu", "_cap_ram", "_cap_gpu", "_pb_cpu", "_pb_ram", "_pb_gpu", "_lbl_cpu_pct", "_lbl_ram_pct", "_lbl_gpu_pct"):
                    w = getattr(self, name, None)
                    if w is not None:
                        w.setVisible(False)
            self.btn_collapse.setText(self.t("collapse_off"))
        else:
            self._sidebar.setFixedWidth(SIDEBAR_WIDTH_EXPANDED)
            self.nav.setVisible(True)
            self._lbl_side_title.setVisible(True)
            if getattr(self, "_lbl_uptime_cap", None):
                self._lbl_uptime_cap.setVisible(True)
                self._lbl_uptime.setVisible(True)
                for name in ("_cap_cpu", "_cap_ram", "_cap_gpu", "_pb_cpu", "_pb_ram", "_pb_gpu", "_lbl_cpu_pct", "_lbl_ram_pct", "_lbl_gpu_pct"):
                    w = getattr(self, name, None)
                    if w is not None:
                        w.setVisible(True)
            self.btn_collapse.setText(self.t("collapse_on"))

    def _page_overview(self):
        scroll = QScrollArea()
        scroll.setObjectName("OverviewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea#OverviewScroll { background: transparent; border: none; }"
        )
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(12)
        v.setContentsMargins(0, 0, 8, 12)

        self._frm_aqi = QFrame()
        self._frm_aqi.setObjectName("AqiBanner")
        aq_l = QVBoxLayout(self._frm_aqi)
        aq_l.setContentsMargins(14, 12, 18, 12)
        self.lbl_aqi = QLabel("")
        self.lbl_aqi.setTextFormat(Qt.RichText)
        self.lbl_aqi.setWordWrap(True)
        aq_l.addWidget(self.lbl_aqi)
        v.addWidget(self._frm_aqi)

        grid = QGridLayout()
        grid.setSpacing(12)
        for i, key in enumerate(config.CHANNEL_ORDER):
            r, c = divmod(i, 2)
            card = SensorCard(key, self._lang, show_sparkline=True)
            self._sensor_cards[key] = card
            grid.addWidget(card, r, c)
        v.addLayout(grid)

        self._gb_overview_data = QGroupBox()
        odt = QVBoxLayout(self._gb_overview_data)
        self._table_overview_data = QTableWidget(0, 4)
        self._table_overview_data.setObjectName("OverviewDataTable")
        self._table_overview_data.setAlternatingRowColors(True)
        self._table_overview_data.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table_overview_data.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table_overview_data.verticalHeader().setVisible(False)
        self._table_overview_data.horizontalHeader().setStretchLastSection(True)
        self._table_overview_data.setMinimumHeight(200)
        self._table_overview_data.setMaximumHeight(320)
        self._table_overview_data.setFont(_mono_font(9))
        odt.addWidget(self._table_overview_data)
        v.addWidget(self._gb_overview_data)

        self._gb_trend = QGroupBox()
        ol = QVBoxLayout(self._gb_trend)
        filt = QHBoxLayout()
        self._chart_btns = {}
        self._chart_btn_group = QButtonGroup(self)
        self._chart_btn_group.setExclusive(True)
        for sec, key in ((None, "chart_live"), (60, "chart_1m"), (300, "chart_5m"), (1800, "chart_30m")):
            btn = QPushButton(UI_STR[self._lang][key])
            btn.setCheckable(True)
            self._chart_btn_group.addButton(btn)
            btn.setChecked(sec is None)
            sec_ref = sec
            btn.clicked.connect(lambda _=False, s=sec_ref: self._on_chart_span(s))
            filt.addWidget(btn)
            self._chart_btns[sec] = btn
        filt.addStretch(1)
        self._btn_norm = QPushButton(UI_STR[self._lang]["norm_plot"])
        self._btn_norm.setCheckable(True)
        self._btn_norm.toggled.connect(self._toggle_norm_plot)
        filt.addWidget(self._btn_norm)
        ol.addLayout(filt)
        self._plot_overview = pg.PlotWidget()
        self._plot_overview.showGrid(x=True, y=True, alpha=0.25)
        self._plot_overview.setMinimumHeight(260)
        ol.addWidget(self._plot_overview)
        # Kaydırılabilir sayfa: trend tüm yüksekliği kaplamasın; alt kartlar sıkışmasın
        v.addWidget(self._gb_trend)

        bot = QHBoxLayout()
        bot.setSpacing(10)
        self._gb_bottom_alerts = QGroupBox()
        self._gb_bottom_alerts.setMinimumHeight(168)
        bl = QVBoxLayout(self._gb_bottom_alerts)
        self._txt_bottom_alerts = QTextBrowser()
        self._txt_bottom_alerts.setMinimumHeight(120)
        self._txt_bottom_alerts.setMaximumHeight(240)
        self._txt_bottom_alerts.setOpenExternalLinks(False)
        bl.addWidget(self._txt_bottom_alerts)
        bot.addWidget(self._gb_bottom_alerts, 1)

        self._gb_bottom_aqi = QGroupBox()
        self._gb_bottom_aqi.setMinimumHeight(168)
        ba = QVBoxLayout(self._gb_bottom_aqi)
        self._lbl_aqi_hist_bars = QLabel("—")
        self._lbl_aqi_hist_bars.setFont(_mono_font(10))
        self._lbl_aqi_hist_bars.setWordWrap(True)
        self._lbl_aqi_hist_bars.setMinimumHeight(120)
        self._lbl_aqi_hist_bars.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        ba.addWidget(self._lbl_aqi_hist_bars)
        bot.addWidget(self._gb_bottom_aqi, 1)

        self._gb_bottom_lstm = QGroupBox()
        self._gb_bottom_lstm.setMinimumHeight(168)
        bls = QVBoxLayout(self._gb_bottom_lstm)
        self._lbl_lstm_hint = QLabel("—")
        self._lbl_lstm_hint.setWordWrap(True)
        self._lbl_lstm_hint.setTextFormat(Qt.RichText)
        self._lbl_lstm_hint.setMinimumHeight(120)
        self._lbl_lstm_hint.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        bls.addWidget(self._lbl_lstm_hint)
        bot.addWidget(self._gb_bottom_lstm, 1)
        v.addLayout(bot)

        scroll.setWidget(inner)
        return scroll

    def _page_graphs(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._lbl_graph_hint = QLabel()
        self._lbl_graph_hint.setStyleSheet("color: #8b949e; font-size: 12px;")
        v.addWidget(self._lbl_graph_hint)
        self.lbl_graph_summary = QLabel("")
        self.lbl_graph_summary.setObjectName("HeroStrip")
        self.lbl_graph_summary.setWordWrap(True)
        v.addWidget(self.lbl_graph_summary)

        grid = QGridLayout()
        grid.setSpacing(14)
        row, col = 0, 0
        for key in config.CHANNEL_ORDER:
            title, unit, _sub = _sensor_meta_for_lang(self._lang, key)
            box = QGroupBox("%s (%s)" % (title, unit))
            bl = QVBoxLayout(box)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #f0f6fc;")
            bl.addWidget(val_lbl)
            pw = pg.PlotWidget()
            pw.showGrid(x=True, y=True, alpha=0.2)
            pw.setMinimumHeight(200)
            bl.addWidget(pw)
            self._per_ch_values[key] = val_lbl
            self._per_ch_plots[key] = pw
            grid.addWidget(box, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1
        v.addLayout(grid, 1)
        return w

    def _ai_make_card(self, title_attr, body_is_browser=False):
        card = QFrame()
        card.setObjectName("AiSectionCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 16)
        cl.setSpacing(8)
        tl = QLabel()
        tl.setObjectName("AiSectionTitle")
        setattr(self, title_attr, tl)
        cl.addWidget(tl)
        if body_is_browser:
            body = QTextBrowser()
            body.setMinimumHeight(100)
            body.setOpenExternalLinks(True)
        else:
            body = QLabel()
            body.setWordWrap(True)
            body.setTextFormat(Qt.RichText)
            body.setOpenExternalLinks(True)
            body.setTextInteractionFlags(
                Qt.TextBrowserInteraction | Qt.LinksAccessibleByMouse
            )
        cl.addWidget(body)
        return card, body

    def _page_ai_hub(self):
        """Menü AI merkezi — sağ panelden bağımsız tam AI panosu."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)
        self._lbl_ai_hub_title = QLabel()
        self._lbl_ai_hub_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_ai_hub_title)
        self._lbl_ai_hub_intro = QLabel()
        self._lbl_ai_hub_intro.setWordWrap(True)
        self._lbl_ai_hub_intro.setObjectName("AiMutedCaption")
        v.addWidget(self._lbl_ai_hub_intro)

        hub_row = QHBoxLayout()
        self._hub_lbl_refresh = QLabel()
        self._hub_lbl_refresh.setObjectName("AiMutedCaption")
        hub_row.addWidget(self._hub_lbl_refresh, 1)
        self._btn_hub_speak = QPushButton()
        self._btn_hub_speak.clicked.connect(self._on_speak)
        hub_row.addWidget(self._btn_hub_speak, 0)
        self._btn_hub_help = QPushButton()
        self._btn_hub_help.clicked.connect(self._show_ai_help)
        hub_row.addWidget(self._btn_hub_help, 0)
        v.addLayout(hub_row)

        hero = QFrame()
        hero.setObjectName("AiHeroStrip")
        hh = QHBoxLayout(hero)
        hh.setContentsMargins(14, 12, 14, 12)
        hh.setSpacing(12)
        self._hub_lbl_hero_aqi = QLabel()
        self._hub_lbl_hero_aqi.setTextFormat(Qt.RichText)
        self._hub_lbl_hero_aqi.setMinimumWidth(0)
        hh.addWidget(self._hub_lbl_hero_aqi, 0, Qt.AlignTop)
        hv = QVBoxLayout()
        hv.setSpacing(6)
        self._hub_lbl_conf_caption = QLabel()
        self._hub_lbl_conf_caption.setObjectName("AiMutedCaption")
        self._hub_lbl_conf_caption.setWordWrap(True)
        self._hub_pb_conf = QProgressBar()
        self._hub_pb_conf.setRange(0, 100)
        self._hub_pb_conf.setValue(0)
        self._hub_pb_conf.setFormat("%v%")
        self._hub_lbl_anomaly_badge = QLabel()
        self._hub_lbl_anomaly_badge.setTextFormat(Qt.RichText)
        hv.addWidget(self._hub_lbl_conf_caption)
        hv.addWidget(self._hub_pb_conf)
        hv.addWidget(self._hub_lbl_anomaly_badge)
        hh.addLayout(hv, 1)
        v.addWidget(hero)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        inner = QWidget()
        sc_l = QVBoxLayout(inner)
        sc_l.setSpacing(12)
        sc_l.setContentsMargins(0, 0, 2, 4)

        c1, self._hub_lbl_body_summary = self._ai_make_card("_hub_tl_summary", False)
        sc_l.addWidget(c1)
        c2, self._hub_lbl_body_advice = self._ai_make_card("_hub_tl_advice", False)
        sc_l.addWidget(c2)
        c3, self._hub_lbl_body_alerts = self._ai_make_card("_hub_tl_alerts", False)
        sc_l.addWidget(c3)

        est_card = QFrame()
        est_card.setObjectName("AiSectionCard")
        el = QVBoxLayout(est_card)
        el.setContentsMargins(14, 12, 14, 12)
        self._hub_tl_estimates = QLabel()
        self._hub_tl_estimates.setObjectName("AiSectionTitle")
        el.addWidget(self._hub_tl_estimates)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self._hub_est_labels = []
        self._hub_est_values = []
        for i in range(4):
            lb = QLabel()
            lb.setObjectName("AiMutedCaption")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size: 16px; font-weight: 800; color: %s;" % THEME["text"]
            )
            self._hub_est_labels.append(lb)
            self._hub_est_values.append(val)
            grid.addWidget(lb, i, 0)
            grid.addWidget(val, i, 1)
        el.addLayout(grid)
        sc_l.addWidget(est_card)

        c4, self._hub_lbl_body_ml = self._ai_make_card("_hub_tl_ml", False)
        sc_l.addWidget(c4)
        c5, self._hub_txt_detail = self._ai_make_card("_hub_tl_detail", True)
        self._hub_txt_detail.setMinimumHeight(200)
        sc_l.addWidget(c5)
        sc_l.addStretch(1)

        scroll.setWidget(inner)
        v.addWidget(scroll, 1)

        self._hub_i18n_title_pairs = [
            (self._hub_tl_summary, "ai_sec_summary"),
            (self._hub_tl_advice, "ai_sec_advice"),
            (self._hub_tl_alerts, "ai_sec_alerts"),
            (self._hub_tl_estimates, "ai_sec_estimates"),
            (self._hub_tl_ml, "ai_sec_ml"),
            (self._hub_tl_detail, "ai_sec_detail"),
        ]
        return w

    def _page_history(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._lbl_hist_title = QLabel()
        self._lbl_hist_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_hist_title)
        self._lbl_csv_path = QLabel()
        self._lbl_csv_path.setWordWrap(True)
        self._lbl_csv_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._lbl_csv_path.setFont(_mono_font(10))
        v.addWidget(self._lbl_csv_path)
        self._txt_hist_body = QTextBrowser()
        v.addWidget(self._txt_hist_body, 1)
        return w

    def _page_data_log(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self._lbl_data_log_title = QLabel()
        self._lbl_data_log_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_data_log_title)
        self._lbl_data_log_hint = QLabel()
        self._lbl_data_log_hint.setObjectName("AiMutedCaption")
        self._lbl_data_log_hint.setWordWrap(True)
        v.addWidget(self._lbl_data_log_hint)
        self._table_data_log = QTableWidget(0, 0)
        self._table_data_log.setObjectName("DataLogTable")
        self._table_data_log.setAlternatingRowColors(True)
        self._table_data_log.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table_data_log.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table_data_log.verticalHeader().setVisible(False)
        self._table_data_log.horizontalHeader().setStretchLastSection(True)
        self._table_data_log.setFont(_mono_font(9))
        self._table_data_log.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        v.addWidget(self._table_data_log, 1)
        return w

    def _page_api(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._lbl_api_page_title = QLabel()
        self._lbl_api_page_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_api_page_title)
        self._txt_api_body = QTextBrowser()
        v.addWidget(self._txt_api_body, 1)
        return w

    def _page_settings(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setSpacing(12)
        self._lbl_settings_title = QLabel()
        self._lbl_settings_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_settings_title)

        self._gb_telegram = QGroupBox()
        tg = QFormLayout(self._gb_telegram)
        tg.setSpacing(10)
        self._chk_tg_enable = QCheckBox()
        tg.addRow(self._chk_tg_enable)
        self._lbl_tg_token = QLabel()
        self._edit_tg_token = QLineEdit()
        self._edit_tg_token.setEchoMode(QLineEdit.Password)
        self._edit_tg_token.setPlaceholderText("123456789:ABC…")
        tg.addRow(self._lbl_tg_token, self._edit_tg_token)
        self._lbl_tg_chat = QLabel()
        self._edit_tg_chat = QLineEdit()
        self._edit_tg_chat.setPlaceholderText("-1001234567890")
        tg.addRow(self._lbl_tg_chat, self._edit_tg_chat)
        self._chk_tg_crit = QCheckBox()
        self._chk_tg_crit.setChecked(True)
        tg.addRow(self._chk_tg_crit)
        self._chk_tg_aqi = QCheckBox()
        self._chk_tg_aqi.setChecked(True)
        tg.addRow(self._chk_tg_aqi)
        self._chk_tg_stream = QCheckBox()
        tg.addRow(self._chk_tg_stream)
        self._lbl_tg_stream_sec = QLabel()
        self._spin_tg_stream_sec = QSpinBox()
        self._spin_tg_stream_sec.setRange(30, 3600)
        self._spin_tg_stream_sec.setSingleStep(30)
        self._spin_tg_stream_sec.setValue(120)
        tg.addRow(self._lbl_tg_stream_sec, self._spin_tg_stream_sec)
        v.addWidget(self._gb_telegram)

        row = QHBoxLayout()
        self._btn_save_settings = QPushButton()
        self._btn_save_settings.clicked.connect(self._save_user_settings_ui)
        self._btn_test_tg = QPushButton()
        self._btn_test_tg.clicked.connect(self._test_telegram_ui)
        row.addWidget(self._btn_save_settings)
        row.addWidget(self._btn_test_tg)
        row.addStretch(1)
        v.addLayout(row)

        self._lbl_settings_path = QLabel()
        self._lbl_settings_path.setWordWrap(True)
        self._lbl_settings_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._lbl_settings_path.setFont(_mono_font(9))
        v.addWidget(self._lbl_settings_path)

        self._lbl_settings_env_cap = QLabel()
        self._lbl_settings_env_cap.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_settings_env_cap)
        self._txt_settings_env = QTextBrowser()
        self._txt_settings_env.setMaximumHeight(140)
        v.addWidget(self._txt_settings_env)
        v.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return w

    def _load_user_settings_ui(self):
        if not getattr(self, "_edit_tg_token", None):
            return
        s = user_settings.load_user_settings()
        self._chk_tg_enable.setChecked(bool(s.get("telegram_enabled")))
        self._edit_tg_token.setText((s.get("telegram_bot_token") or "").strip())
        self._edit_tg_chat.setText((s.get("telegram_chat_id") or "").strip())
        self._chk_tg_crit.setChecked(bool(s.get("telegram_on_critical", True)))
        self._chk_tg_aqi.setChecked(bool(s.get("telegram_on_aqi_bad", True)))
        if getattr(self, "_chk_tg_stream", None):
            self._chk_tg_stream.setChecked(bool(s.get("telegram_stream_enabled")))
        if getattr(self, "_spin_tg_stream_sec", None):
            try:
                sec = int(s.get("telegram_stream_interval_sec", 120))
            except (TypeError, ValueError):
                sec = 120
            self._spin_tg_stream_sec.setValue(max(30, min(sec, 3600)))
        if getattr(self, "_lbl_settings_path", None):
            self._lbl_settings_path.setText(
                "%s:\n%s" % (self.t("settings_path_lbl"), os.path.abspath(config.USER_SETTINGS_JSON))
            )

    def _save_user_settings_ui(self):
        user_settings.save_user_settings(
            {
                "telegram_enabled": self._chk_tg_enable.isChecked(),
                "telegram_bot_token": self._edit_tg_token.text().strip(),
                "telegram_chat_id": self._edit_tg_chat.text().strip(),
                "telegram_on_critical": self._chk_tg_crit.isChecked(),
                "telegram_on_aqi_bad": self._chk_tg_aqi.isChecked(),
                "telegram_stream_enabled": self._chk_tg_stream.isChecked(),
                "telegram_stream_interval_sec": int(self._spin_tg_stream_sec.value()),
            }
        )
        QMessageBox.information(self, self.t("settings_title"), self.t("settings_saved"))

    def _test_telegram_ui(self):
        from .telegram_notify import send_telegram_message

        ok = send_telegram_message(
            "AeroSense AI — test mesajı / test message",
            settings={
                "telegram_enabled": True,
                "telegram_bot_token": self._edit_tg_token.text().strip(),
                "telegram_chat_id": self._edit_tg_chat.text().strip(),
            },
        )
        if ok:
            QMessageBox.information(self, self.t("settings_test_tg"), self.t("settings_tg_ok"))
        else:
            QMessageBox.warning(self, self.t("settings_test_tg"), self.t("settings_tg_fail"))

    def _on_ai_send(self):
        q = (self._ai_query.text() or "").strip()
        if not q:
            return
        self._txt_ai_event_log.append(
            "<span style='color:#8B9BC4'>[%s]</span> %s"
            % (datetime.now().strftime("%H:%M:%S"), html.escape(q))
        )
        self._ai_query.clear()
        low = q.lower()
        if any(x in low for x in ("durum", "status", "özet", "ozet", "summary")):
            self._on_speak()
        else:
            QMessageBox.information(
                self,
                self.t("btn_send"),
                self.t("ai_hint_ask"),
            )

    def _on_mic_hint(self):
        sec = float(getattr(config, "VOICE_STT_LISTEN_TIMEOUT", 8))
        auto = self.t("voice_auto_on" if config.VOICE_AUTO_ALERTS else "voice_auto_off")
        QMessageBox.information(
            self,
            self.t("btn_mic"),
            self.t("voice_hint") % {"sec": sec, "auto": auto},
        )

    def _quick_co(self):
        an = self.state.get_analysis()
        if not an:
            QMessageBox.information(self, self.t("quick_co"), self.t("no_data"))
            return
        QMessageBox.information(
            self,
            self.t("quick_co"),
            "CO ~ %.1f ppm · %s" % (float(an.get("co_ppm_est", 0)), an.get("aqi_level", "—")),
        )

    def _quick_health_nav(self):
        self.nav.setCurrentRow(3)

    def _quick_csv_msg(self):
        QMessageBox.information(
            self,
            self.t("quick_csv"),
            os.path.abspath(config.CSV_PATH),
        )

    def _quick_pred_msg(self):
        an = self.state.get_analysis()
        msg = (an.get("ml_note") or self.t("no_data")) if an else self.t("no_data")
        QMessageBox.information(self, self.t("quick_pred"), msg)

    def _build_right_ai_column(self):
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setSpacing(8)
        v.setContentsMargins(6, 8, 8, 8)

        self._lbl_right_ai_title = QLabel()
        self._lbl_right_ai_title.setObjectName("AiSectionTitle")
        v.addWidget(self._lbl_right_ai_title)

        self._gb_ai = QGroupBox()
        al = QVBoxLayout(self._gb_ai)
        al.setSpacing(8)
        al.setContentsMargins(8, 14, 8, 8)

        hero = QFrame()
        hero.setObjectName("AiHeroStrip")
        hh = QHBoxLayout(hero)
        hh.setContentsMargins(12, 10, 12, 10)
        hh.setSpacing(10)
        self._lbl_ai_hero_aqi = QLabel()
        self._lbl_ai_hero_aqi.setTextFormat(Qt.RichText)
        self._lbl_ai_hero_aqi.setMinimumWidth(0)
        hh.addWidget(self._lbl_ai_hero_aqi, 0, Qt.AlignTop)
        hv = QVBoxLayout()
        hv.setSpacing(6)
        self._lbl_ai_conf_caption = QLabel()
        self._lbl_ai_conf_caption.setObjectName("AiMutedCaption")
        self._lbl_ai_conf_caption.setWordWrap(True)
        self._pb_ai_conf = QProgressBar()
        self._pb_ai_conf.setRange(0, 100)
        self._pb_ai_conf.setValue(0)
        self._pb_ai_conf.setFormat("%v%")
        self._lbl_ai_anomaly_badge = QLabel()
        self._lbl_ai_anomaly_badge.setTextFormat(Qt.RichText)
        hv.addWidget(self._lbl_ai_conf_caption)
        hv.addWidget(self._pb_ai_conf)
        hv.addWidget(self._lbl_ai_anomaly_badge)
        hh.addLayout(hv, 1)
        al.addWidget(hero)

        self._lbl_ai_refresh = QLabel()
        self._lbl_ai_refresh.setObjectName("AiMutedCaption")
        al.addWidget(self._lbl_ai_refresh)

        self._lbl_ai_log_cap = QLabel()
        self._lbl_ai_log_cap.setObjectName("AiMutedCaption")
        al.addWidget(self._lbl_ai_log_cap)

        self._txt_ai_event_log = QTextBrowser()
        self._txt_ai_event_log.setMaximumHeight(88)
        self._txt_ai_event_log.setOpenExternalLinks(False)
        al.addWidget(self._txt_ai_event_log)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        inner = QWidget()
        sc_l = QVBoxLayout(inner)
        sc_l.setSpacing(10)
        sc_l.setContentsMargins(0, 0, 4, 6)

        c1, self._lbl_ai_body_summary = self._ai_make_card("_tl_ai_summary", False)
        sc_l.addWidget(c1)
        c2, self._lbl_ai_body_advice = self._ai_make_card("_tl_ai_advice", False)
        sc_l.addWidget(c2)
        c3, self._lbl_ai_body_alerts = self._ai_make_card("_tl_ai_alerts", False)
        sc_l.addWidget(c3)

        est_card = QFrame()
        est_card.setObjectName("AiSectionCard")
        el = QVBoxLayout(est_card)
        el.setContentsMargins(12, 10, 12, 10)
        self._tl_ai_estimates = QLabel()
        self._tl_ai_estimates.setObjectName("AiSectionTitle")
        el.addWidget(self._tl_ai_estimates)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self._lbl_ai_est_labels = []
        self._lbl_ai_est_values = []
        for i in range(4):
            lb = QLabel()
            lb.setObjectName("AiMutedCaption")
            val = QLabel("—")
            val.setStyleSheet(
                "font-size: 15px; font-weight: 800; color: %s;" % THEME["text"]
            )
            self._lbl_ai_est_labels.append(lb)
            self._lbl_ai_est_values.append(val)
            grid.addWidget(lb, i, 0)
            grid.addWidget(val, i, 1)
        el.addLayout(grid)
        sc_l.addWidget(est_card)

        c4, self._lbl_ai_body_ml = self._ai_make_card("_tl_ai_ml", False)
        sc_l.addWidget(c4)
        c5, self._txt_ai_detail = self._ai_make_card("_tl_ai_detail", True)
        self._txt_ai_detail.setMinimumHeight(100)
        sc_l.addWidget(c5)
        sc_l.addStretch(1)

        scroll.setWidget(inner)
        al.addWidget(scroll, 1)
        v.addWidget(self._gb_ai, 1)

        ask_row = QHBoxLayout()
        self._ai_query = QLineEdit()
        self._ai_query.setPlaceholderText(UI_STR[self._lang]["ask_placeholder"])
        ask_row.addWidget(self._ai_query, 1)
        self._btn_ai_send = QPushButton(UI_STR[self._lang]["btn_send"])
        self._btn_ai_send.clicked.connect(self._on_ai_send)
        ask_row.addWidget(self._btn_ai_send)
        v.addLayout(ask_row)

        self._btn_mic = QPushButton()
        self._btn_mic.setObjectName("MicBtn")
        self._btn_mic.clicked.connect(self._on_mic_hint)
        v.addWidget(self._btn_mic)

        qg = QGridLayout()
        qg.setSpacing(6)
        self._btn_q_co = QPushButton()
        self._btn_q_co.clicked.connect(self._quick_co)
        self._btn_q_health = QPushButton()
        self._btn_q_health.clicked.connect(self._quick_health_nav)
        self._btn_q_csv = QPushButton()
        self._btn_q_csv.clicked.connect(self._quick_csv_msg)
        self._btn_q_pred = QPushButton()
        self._btn_q_pred.clicked.connect(self._quick_pred_msg)
        qg.addWidget(self._btn_q_co, 0, 0)
        qg.addWidget(self._btn_q_health, 0, 1)
        qg.addWidget(self._btn_q_csv, 1, 0)
        qg.addWidget(self._btn_q_pred, 1, 1)
        v.addLayout(qg)

        self._gb_voice = QGroupBox()
        vl = QVBoxLayout(self._gb_voice)
        self.lbl_voice = QLabel()
        self.lbl_voice.setWordWrap(True)
        self.lbl_voice.setTextFormat(Qt.RichText)
        self.lbl_voice.setMinimumWidth(0)
        vl.addWidget(self.lbl_voice)
        v.addWidget(self._gb_voice)

        self._ai_i18n_title_pairs = [
            (self._tl_ai_summary, "ai_sec_summary"),
            (self._tl_ai_advice, "ai_sec_advice"),
            (self._tl_ai_alerts, "ai_sec_alerts"),
            (self._tl_ai_estimates, "ai_sec_estimates"),
            (self._tl_ai_ml, "ai_sec_ml"),
            (self._tl_ai_detail, "ai_sec_detail"),
        ]

        return panel

    def _page_health(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self._lbl_health = QLabel()
        self._lbl_health.setStyleSheet("color: #8b949e;")
        v.addWidget(self._lbl_health)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Kanal", "Durum", "Açıklama"])
        self.table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.table)
        return w

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)
        if config.FULLSCREEN_DEFAULT:
            self.showFullScreen()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _show_ai_help(self):
        d = QDialog(self)
        if not self._app_icon.isNull():
            d.setWindowIcon(self._app_icon)
        d.setWindowTitle("AI — nasıl çalışır?")
        d.resize(540, 440)
        lay = QVBoxLayout(d)
        tb = QTextBrowser()
        tb.setHtml(AI_HELP_HTML)
        lay.addWidget(tb)
        b = QPushButton("Close" if self._lang == "en" else "Kapat")
        b.clicked.connect(d.accept)
        lay.addWidget(b)
        d.exec_()

    def _on_speak(self):
        text, _ = self.state.get_ai()
        msg = text or self.t("no_analysis")
        if self.voice:
            self.voice.speak(msg)
        else:
            QMessageBox.information(self, self.t("dlg_summary_title"), msg)

    def _refresh_voice_panel(self):
        vs = self.voice.get_status_copy() if self.voice else {}
        tts = (
            self.t("voice_tts_ok")
            if vs.get("tts_ready")
            else (self.t("voice_tts_bad") % html.escape(str(vs.get("tts_note", "?"))))
        )
        stt = (
            self.t("voice_stt_ok")
            if vs.get("stt_ready")
            else (self.t("voice_stt_bad") % html.escape(str(vs.get("stt_note", "?"))))
        )
        heard = html.escape(str(vs.get("last_heard", "-")))
        prev = html.escape(str(vs.get("last_spoke_preview", "-")))
        auto = self.t("voice_auto_on" if config.VOICE_AUTO_ALERTS else "voice_auto_off")
        sec = float(getattr(config, "VOICE_STT_LISTEN_TIMEOUT", 8))
        hint = self.t("voice_hint") % {"sec": sec, "auto": auto}
        self.lbl_voice.setText(
            "<p style='line-height:1.55;font-size:13px'>%s<br/>%s</p>"
            "<p><b>%s</b> %s</p>"
            "<p><b>%s</b> %s</p>"
            "<p style='color:#8b949e;font-size:11px'>%s</p>"
            % (tts, stt, self.t("voice_heard"), heard, self.t("voice_spoke"), prev, hint)
        )

    def _right_ai_surface(self):
        return {
            "hero": self._lbl_ai_hero_aqi,
            "pb": self._pb_ai_conf,
            "anomaly": self._lbl_ai_anomaly_badge,
            "summary": self._lbl_ai_body_summary,
            "advice": self._lbl_ai_body_advice,
            "alerts": self._lbl_ai_body_alerts,
            "est": self._lbl_ai_est_values,
            "ml": self._lbl_ai_body_ml,
            "detail": self._txt_ai_detail,
        }

    def _hub_ai_surface(self):
        if not getattr(self, "_hub_lbl_hero_aqi", None):
            return None
        return {
            "hero": self._hub_lbl_hero_aqi,
            "pb": self._hub_pb_conf,
            "anomaly": self._hub_lbl_anomaly_badge,
            "summary": self._hub_lbl_body_summary,
            "advice": self._hub_lbl_body_advice,
            "alerts": self._hub_lbl_body_alerts,
            "est": self._hub_est_values,
            "ml": self._hub_lbl_body_ml,
            "detail": self._hub_txt_detail,
        }

    def _paint_ai_surface(self, an, ai_text, ai_detail, surf, hero_font_pt=34):
        """Sağ panel ve AI merkezi sayfası ortak boyama (surf widget sözlüğü)."""
        h = surf["hero"]
        pb = surf["pb"]
        badge = surf["anomaly"]
        body_sum = surf["summary"]
        body_adv = surf["advice"]
        body_alr = surf["alerts"]
        est_vals = surf["est"]
        body_ml = surf["ml"]
        txt_det = surf["detail"]
        dash_pt = max(26, hero_font_pt - 6)

        if not an:
            h.setText(
                "<span style='font-size:%dpx;font-weight:800;color:#484f58'>—</span>"
                "<br/><span style='font-size:12px;color:#6e7681'>AQI</span>" % dash_pt
            )
            pb.setValue(0)
            badge.clear()
            ph = (
                "<p style='font-size:15px;line-height:1.65;color:#c9d1d9'>%s</p>"
                "<p style='margin-top:14px;font-size:13px;color:#8b949e;line-height:1.5'>%s</p>"
                % (
                    html.escape(self.t("ai_no_analysis_run")),
                    self.t("ai_hint_no_sensor"),
                )
            )
            body_sum.setText(ph)
            body_adv.clear()
            body_alr.setText(
                "<span style='color:#484f58'><i>%s</i></span>"
                % html.escape(self.t("ai_no_alerts"))
            )
            for v in est_vals:
                v.setText("—")
            body_ml.clear()
            txt_det.setHtml(
                "<p style='color:#8b949e;line-height:1.55'>%s</p>"
                % html.escape(ai_text or self.t("no_data"))
            )
            return

        col = an.get("color_hex") or "58a6ff"
        aqi = html.escape(str(an.get("aqi_level", "—")))
        h.setText(
            "<span style='font-size:%dpx;font-weight:800;color:#%s'>%s</span><br/>"
            "<span style='font-size:11px;color:#8b949e;letter-spacing:3px;text-transform:uppercase'>"
            "AQI · AeroSense</span>"
            % (hero_font_pt, col, aqi)
        )
        conf = int(round(float(an.get("confidence", 0))))
        pb.setValue(max(0, min(100, conf)))
        if an.get("is_anomaly"):
            badge.setText(
                "<span style='background-color:#3d1117;color:#f85149;padding:6px 14px;"
                "border-radius:8px;font-weight:700;font-size:12px;border:1px solid #f85149'>%s</span>"
                % html.escape(self.t("anomaly"))
            )
        else:
            badge.setText(
                "<span style='color:#3fb950;font-weight:700;font-size:12px'>%s</span>"
                % html.escape(self.t("stable"))
            )

        summary = (ai_text or an.get("summary_tr") or "").strip()
        if not summary:
            summary = self.t("no_data")
        sum_fs = 17 if hero_font_pt >= 40 else 16
        body_sum.setText(
            "<p style='font-size:%dpx;line-height:1.65;color:#f0f6fc;font-weight:500'>%s</p>"
            % (sum_fs, html.escape(summary))
        )

        adv = (an.get("advice") or "").strip()
        if adv:
            body_adv.setText(
                "<p style='font-size:14px;line-height:1.65;color:#c9d1d9'>%s</p>"
                % html.escape(adv)
            )
        else:
            body_adv.setText("<span style='color:#484f58'><i>—</i></span>")

        alerts = an.get("alerts") or []
        if not alerts:
            body_alr.setText(
                "<span style='color:#3fb950;font-weight:600'>✓ %s</span>"
                % html.escape(self.t("ai_no_alerts"))
            )
        else:
            parts = []
            for pair in alerts:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    sev, msg = pair[0], pair[1]
                else:
                    sev, msg = "—", str(pair)
                sev_u = (str(sev) or "").upper()
                color = (
                    "#f85149"
                    if ("UYARI" in sev_u or "WARN" in sev_u or "ERROR" in sev_u)
                    else "#d29922"
                )
                parts.append(
                    "<div style='margin:8px 0;padding:10px 12px;background:#161b22;"
                    "border-left:4px solid %s;border-radius:8px'>"
                    "<span style='color:%s;font-weight:800;font-size:11px'>%s</span><br/>"
                    "<span style='color:#e6edf3;font-size:13px;line-height:1.45'>%s</span></div>"
                    % (
                        color,
                        color,
                        html.escape(str(sev)),
                        html.escape(str(msg)),
                    )
                )
            body_alr.setText("".join(parts))

        try:
            est_vals[0].setText("%.1f ppm" % float(an.get("co_ppm_est", 0)))
            est_vals[1].setText("%.1f ppm" % float(an.get("nox_ppm_est", 0)))
            est_vals[2].setText("%.1f µg/m³" % float(an.get("pm25_est", 0)))
            est_vals[3].setText("%.1f °C" % float(an.get("temp_c", 0)))
        except (TypeError, ValueError):
            for v in est_vals:
                v.setText("—")

        ml = (an.get("ml_note") or "").strip()
        ml_line = html.escape(ml) if ml else "—"
        body_ml.setText(
            "<p style='font-size:14px;color:#58a6ff;line-height:1.55'>%s</p>"
            "<p style='font-size:12px;color:#8b949e;margin-top:10px;line-height:1.45'>"
            "%s <b style='color:#f0f6fc'>%.1f%%</b> · AQI index <b style='color:#f0f6fc'>%s</b>"
            "</p>"
            % (
                ml_line,
                html.escape(self.t("label_confidence")),
                float(an.get("confidence", 0)),
                html.escape(str(an.get("aqi_index", "—"))),
            )
        )

        det = (ai_detail or an.get("detail_tr") or "").strip()
        if det:
            safe = html.escape(det).replace("\n", "<br/>")
            det_fs = 14 if hero_font_pt >= 40 else 13
            txt_det.setHtml(
                "<div style='color:#e6edf3;font-size:%dpx;line-height:1.6'>%s</div>"
                % (det_fs, safe)
            )
        else:
            txt_det.setHtml("<p style='color:#6e7681'><i>—</i></p>")

    def _apply_ai_dashboard(self, an, ai_text, ai_detail):
        """Sağ sütun + menü AI merkezi aynı analiz verisiyle güncellenir."""
        now = datetime.now().strftime("%H:%M:%S")
        self._lbl_ai_refresh.setText(self.t("ai_updated") % now)
        self._paint_ai_surface(an, ai_text, ai_detail, self._right_ai_surface(), hero_font_pt=34)
        if getattr(self, "_hub_lbl_refresh", None):
            self._hub_lbl_refresh.setText(self.t("ai_updated") % now)
        hs = self._hub_ai_surface()
        if hs:
            self._paint_ai_surface(an, ai_text, ai_detail, hs, hero_font_pt=44)

    def _hero_text(self, an, ai_text):
        if not an:
            return (
                "<span style='color:#8b949e;font-size:14px'>%s</span>"
                % html.escape(self.t("hero_wait"))
            )
        col = an.get("color_hex") or "58a6ff"
        stab = self.t("anomaly") if an.get("is_anomaly") else self.t("stable")
        conf = float(an.get("confidence", 0))
        lc = html.escape(self.t("label_confidence"))
        return (
            "<table width='100%%' cellspacing='0'><tr>"
            "<td style='font-size:26px;font-weight:800;color:#%s'>%s</td>"
            "<td align='right' style='color:#8b949e;font-size:13px'>"
            "%s <b style='color:#f0f6fc'>%.0f%%</b> · %s · "
            "CO~%.0f NOx~%.0f PM~%.0f · <b>%.1f°C</b></td></tr></table>"
            "<p style='margin-top:10px;font-size:14px;color:#e6edf3;line-height:1.5'>%s</p>"
            % (
                col,
                html.escape(str(an.get("aqi_level", "-"))),
                lc,
                conf,
                stab,
                float(an.get("co_ppm_est", 0)),
                float(an.get("nox_ppm_est", 0)),
                float(an.get("pm25_est", 0)),
                float(an.get("temp_c", 0)),
                html.escape(ai_text or "-"),
            )
        )

    def _refresh(self):
        latest, channels, ts = self.state.get_latest()
        ch_list = channels if channels else list(latest.keys()) or list(config.CHANNEL_ORDER)
        health_rows = sensor_health_tr(
            latest, ch_list if ch_list else list(config.CHANNEL_ORDER), ts
        )
        health_by_ch = {r["channel"]: r for r in health_rows}

        for key, card in self._sensor_cards.items():
            val = latest.get(key)
            row = health_by_ch.get(key)
            prev = self._prev_sensor_vals.get(key)
            if row:
                card.set_reading(val, row["status"], row["message_tr"], prev_value=prev)
            else:
                card.set_reading(val, "hata" if val is None else "ok", "", prev_value=prev)
            if val is not None:
                try:
                    self._prev_sensor_vals[key] = float(val)
                except (TypeError, ValueError):
                    self._prev_sensor_vals[key] = val

        ai_text, ai_detail = self.state.get_ai()
        an = self.state.get_analysis()

        if getattr(self, "_lbl_uptime", None):
            self._lbl_uptime.setText(self._uptime_hms())

        if getattr(self, "_frm_aqi", None) and getattr(self, "lbl_aqi", None):
            strip, topc, _bot = aqi_style_for_level(
                (an or {}).get("aqi_level") if an else None
            )
            self._frm_aqi.setStyleSheet(
                "QFrame#AqiBanner { border: 1px solid %s; border-left: 3px solid %s; "
                "border-radius: 12px; background-color: %s; }"
                % (THEME["border"], strip, topc)
            )
            if an:
                self.lbl_aqi.setText(self._hero_text(an, ai_text))
            else:
                self.lbl_aqi.setText(
                    "<span style='color:#8B9BC4;font-size:14px'>%s</span>"
                    % html.escape(self.t("aqi_pending"))
                )
        if getattr(self, "lbl_graph_summary", None) and getattr(self, "lbl_aqi", None):
            self.lbl_graph_summary.setText(self.lbl_aqi.text())

        self._apply_ai_dashboard(an, ai_text, ai_detail)

        if getattr(self, "_badge_daq", None):
            fresh = ts and (time.time() - float(ts)) < 8.0
            self._badge_daq.setText("● %s" % self.t("badge_daq"))
            self._badge_daq.setStyleSheet(
                "color: %s;" % (THEME["green"] if fresh else THEME["text_muted"])
            )
            self._badge_rf.setText("● %s" % self.t("badge_rf"))
            self._badge_rf.setStyleSheet("color: %s;" % THEME["accent_cyan"])
            self._badge_ai.setText("● %s" % self.t("badge_ai"))
            self._badge_ai.setStyleSheet(
                "color: %s;" % (THEME["orange"] if not an else THEME["green"])
            )
            nw = sum(1 for r in health_rows if r.get("status") != "ok")
            self._badge_warn.setText("%s %s" % (nw, self.t("badge_warn")))
            self._badge_warn.setStyleSheet(
                "color: %s;" % (THEME["red"] if nw else THEME["text_muted"])
            )

        now_m = time.time()
        if now_m - self._gpu_sample_t >= 1.2:
            self._gpu_sample_t = now_m
            self._gpu_sample = sys_metrics.sample_gpu_combined()
        gpu_u, gpu_t = self._gpu_sample

        cpu, ram = sys_metrics.sample_cpu_ram_percent(0.05)
        if cpu is not None and getattr(self, "_pb_cpu", None):
            ci, ri = int(round(cpu)), int(round(ram))
            self._pb_cpu.setValue(min(100, max(0, ci)))
            self._lbl_cpu_pct.setText("%d%%" % ci)
            self._pb_ram.setValue(min(100, max(0, ri)))
            self._lbl_ram_pct.setText("%d%%" % ri)
        elif getattr(self, "_lbl_cpu_pct", None):
            self._lbl_cpu_pct.setText("—")
            self._lbl_ram_pct.setText("—")

        if getattr(self, "_pb_gpu", None):
            if gpu_u is not None:
                self._pb_gpu.setValue(min(100, max(0, int(gpu_u))))
                if gpu_t is not None:
                    self._lbl_gpu_pct.setText("%d%% · %d°C" % (int(gpu_u), int(gpu_t)))
                else:
                    self._lbl_gpu_pct.setText("%d%%" % int(gpu_u))
            else:
                self._pb_gpu.setValue(0)
                self._lbl_gpu_pct.setText("—")

        hist = self.state.get_history(400)
        for _k, card in self._sensor_cards.items():
            card.update_spark(hist, 60)

        ah = getattr(self, "_aqi_hist", None)
        if ah is not None and an:
            nowt = time.time()
            if nowt - getattr(self, "_last_aqi_tick", 0) >= 4.0:
                self._last_aqi_tick = nowt
                try:
                    ah.append(float(an.get("aqi_index", 0)))
                except (TypeError, ValueError):
                    ah.append(0.0)
        if getattr(self, "_lbl_aqi_hist_bars", None) and ah:
            bars = []
            for x in list(ah)[-24:]:
                try:
                    xi = int(round(float(x)))
                except (TypeError, ValueError):
                    xi = 0
                xi = max(0, min(500, xi))
                u = min(8, int(round(xi / 60.0)))
                bars.append("▮" * u if u else "▯")
            self._lbl_aqi_hist_bars.setText(" ".join(bars) or "—")

        if getattr(self, "_txt_bottom_alerts", None):
            parts = []
            for row in health_rows:
                if row.get("status") != "ok":
                    if self._lang == "en":
                        sev = "WARN" if row.get("status") == "uyari" else "CRIT"
                    else:
                        sev = "UYARI" if row.get("status") == "uyari" else "KRİTİK"
                    col = THEME["orange"] if row.get("status") == "uyari" else THEME["red"]
                    parts.append(
                        "<div style='border-left:3px solid %s;padding:4px 0 4px 8px;margin:4px 0'>"
                        "<b style='color:%s'>%s</b> · %s · <span style='color:#8B9BC4'>%s</span></div>"
                        % (
                            col,
                            col,
                            html.escape(sev),
                            html.escape(str(row.get("channel", ""))),
                            html.escape(str(row.get("message_tr", ""))[:120]),
                        )
                    )
            if not parts:
                parts.append(
                    "<span style='color:%s'>%s</span>"
                    % (THEME["green"], html.escape(self.t("ai_no_alerts")))
                )
            self._txt_bottom_alerts.setHtml("".join(parts))

        if getattr(self, "_lbl_lstm_hint", None) and an:
            co = float(an.get("co_ppm_est", 0))
            conf = float(an.get("confidence", 0))
            self._lbl_lstm_hint.setText(
                "<span style='color:#9B72F5;font-weight:700'>LSTM</span> "
                "<span style='color:#DDE3F5'>· CO eğilim ~ %.0f%% · güven %.0f%%</span>"
                % (min(100, co * 3), conf)
            )
        elif getattr(self, "_lbl_lstm_hint", None):
            self._lbl_lstm_hint.setText(
                "<span style='color:#8B9BC4'>%s</span>" % html.escape(self.t("no_data"))
            )

        sig = None
        if an:
            sig = (
                str(an.get("aqi_level", "")),
                int(round(float(an.get("confidence", 0)))),
            )
        h_an = hash(sig) if sig else 0
        if h_an != self._last_ai_log_hash and getattr(self, "_txt_ai_event_log", None):
            self._last_ai_log_hash = h_an
            if an:
                self._txt_ai_event_log.append(
                    "<span style='color:#9B72F5'>[%s]</span> "
                    "<span style='color:#DDE3F5'>AQI %s · %.0f%%</span>"
                    % (
                        datetime.now().strftime("%H:%M:%S"),
                        html.escape(str(an.get("aqi_level", "—"))),
                        float(an.get("confidence", 0)),
                    )
                )

        for key in config.CHANNEL_ORDER:
            vl = self._per_ch_values.get(key)
            if vl is not None:
                v = latest.get(key)
                if v is None:
                    vl.setText("—")
                else:
                    try:
                        u = _sensor_meta_for_lang(self._lang, key)[1]
                        vl.setText("%.5g %s" % (float(v), u))
                    except (TypeError, ValueError):
                        vl.setText(str(v))

        self.table.setRowCount(len(health_rows))
        for i, row in enumerate(health_rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["channel"]))
            st = row["status"]
            it = QTableWidgetItem(st)
            if st == "ok":
                it.setForeground(QBrush(QColor(THEME["green"])))
            elif st == "uyari":
                it.setForeground(QBrush(QColor(THEME["orange"])))
            else:
                it.setForeground(QBrush(QColor(THEME["red"])))
            self.table.setItem(i, 1, it)
            self.table.setItem(i, 2, QTableWidgetItem(row["message_tr"]))

        self._update_plot_multi(self._plot_overview, hist, ch_list)
        for ch, pw in self._per_ch_plots.items():
            self._update_plot_single(pw, hist, ch)

        if getattr(self, "_sb_left", None):
            hz = _estimate_sample_hz(hist)
            hz_txt = ("%.2f Hz" % hz) if hz else "— Hz"
            ai_ms = self.state.get_ai_timing_ms()
            ai_txt = ("~%.0f ms" % ai_ms) if ai_ms and ai_ms > 0.5 else "— ms"
            gt = self._gpu_sample[1] if self._gpu_sample else None
            gpu_txt = ("%d°C" % int(gt)) if gt is not None else "—°C"
            if self._lang == "en":
                self._sb_left.setText(
                    "Sampling %s · AI %s · GPU %s" % (hz_txt, ai_txt, gpu_txt)
                )
            else:
                self._sb_left.setText(
                    "Örnekleme %s · AI %s · GPU %s" % (hz_txt, ai_txt, gpu_txt)
                )
        if getattr(self, "_sb_right", None):
            csvp = os.path.abspath(config.CSV_PATH).replace("\\", "/")
            nf = "{:,}".format(len(hist)).replace(",", ".")
            if self._lang == "en":
                nf = "{:,}".format(len(hist))
            self._sb_right.setText("%s · %s %s" % (csvp, nf, "rows" if self._lang == "en" else "kayıt"))

        self._refresh_data_tables()
        self._refresh_voice_panel()

    def _refresh_data_tables(self):
        rows = self.state.get_data_log_rows()
        snap_cols = ["tarih_saat", "genel_saglik", "aqi_seviye", "guven_yuzde"]
        if getattr(self, "_table_overview_data", None):
            self._table_overview_data.setColumnCount(len(snap_cols))
            self._table_overview_data.setHorizontalHeaderLabels(
                [self._data_log_column_title(c) for c in snap_cols]
            )
            chunk = list(rows)[-5:]
            self._table_overview_data.setRowCount(len(chunk))
            for ri, rd in enumerate(reversed(chunk)):
                for ci, c in enumerate(snap_cols):
                    self._table_overview_data.setItem(
                        ri, ci, QTableWidgetItem(str(rd.get(c, "")))
                    )
        if getattr(self, "_table_data_log", None):
            ch = list(config.CHANNEL_ORDER)
            if rows:
                dur = [k[7:] for k in rows[-1] if k.startswith("durum_")]
                if dur:
                    ch = sorted(dur)
            fieldnames = build_tablo_fieldnames(ch)
            self._table_data_log.setColumnCount(len(fieldnames))
            self._table_data_log.setHorizontalHeaderLabels(
                [self._data_log_column_title(k) for k in fieldnames]
            )
            tail = list(rows)[-50:]
            self._table_data_log.setRowCount(len(tail))
            for ri, rd in enumerate(reversed(tail)):
                for ci, k in enumerate(fieldnames):
                    self._table_data_log.setItem(
                        ri, ci, QTableWidgetItem(str(rd.get(k, "")))
                    )

    def _update_plot_multi(self, plot_w, hist, channels):
        if plot_w is None:
            return
        plot_w.clear()
        if not hist or not channels:
            return
        cw = getattr(self, "_chart_window_sec", None)
        histw = list(hist)
        if cw and len(histw) > 1:
            t_end = histw[-1]["t"]
            histw = [h for h in histw if h["t"] >= t_end - float(cw)]
        if len(histw) < 2:
            return
        t0 = histw[0]["t"]
        plot_w.setBackground(THEME["surface1"])
        plot_w.showGrid(x=True, y=True, alpha=0.25)
        plot_w.addLegend(offset=(6, 6))
        norm = getattr(self, "_plot_normalize", False)
        for ch in channels:
            xs, ys = [], []
            for it in histw:
                if ch in it["data"]:
                    xs.append(it["t"] - t0)
                    try:
                        ys.append(float(it["data"][ch]))
                    except (TypeError, ValueError):
                        pass
            if len(xs) < 2:
                continue
            if norm:
                lo, hi = min(ys), max(ys)
                span = max(hi - lo, 1e-9)
                ys = [(y - lo) / span for y in ys]
            c = SENSOR_COLORS.get(ch, THEME["blue"])
            pen = pg.mkPen(color=c, width=2.2)
            plot_w.plot(xs, ys, pen=pen, name=ch)
        span_t = max(histw[-1]["t"] - t0, 1e-6)
        plot_w.setXRange(0, span_t, padding=0.02)

    def _update_plot_single(self, plot_w, hist, channel):
        plot_w.clear()
        if not hist or not channel:
            return
        t0 = hist[0]["t"]
        xs, ys = [], []
        for it in hist:
            if channel in it["data"]:
                xs.append(it["t"] - t0)
                ys.append(it["data"][channel])
        if xs:
            c = SENSOR_COLORS.get(channel, "#58a6ff")
            plot_w.plot(xs, ys, pen=pg.mkPen(color=c, width=2.5))
        plot_w.showGrid(x=True, y=True, alpha=0.2)


class _QtTtsBridge(QObject):
    """Sesli komut / TTS — ana Qt iş parçacığında konuşur (Windows SAPI + arka plan işi sessiz kalmasın)."""

    _say = pyqtSignal(str)

    def __init__(self, parent=None):
        super(_QtTtsBridge, self).__init__(parent)
        self._say.connect(self._do_say)
        self._engine = None

    def schedule_speak(self, text):
        t = (text or "").strip()
        if t:
            self._say.emit(t)

    def _do_say(self, text):
        try:
            from PyQt5.QtTextToSpeech import QTextToSpeech
            from PyQt5.QtCore import QLocale
        except ImportError:
            print("[voice] PyQt5.QtTextToSpeech yuklu degil; pyttsx3 kullanin.")
            return
        if self._engine is None:
            self._engine = QTextToSpeech(self)
            try:
                for loc in self._engine.availableLocales():
                    if loc.language() == QLocale.Turkish:
                        self._engine.setLocale(loc)
                        break
            except Exception:
                pass
            try:
                self._engine.setRate(0.0)
                self._engine.setVolume(1.0)
            except Exception:
                pass
        try:
            self._engine.say(text)
        except Exception as e:
            print("[voice] QTextToSpeech.say hatasi: %s" % e)


def _voice_try_attach_qt_tts(app, voice_service):
    if voice_service is None or not config.VOICE_ENABLED:
        return
    if os.environ.get("AEROSENSE_FORCE_PYTTSX3", "").lower() in ("1", "true", "yes"):
        print("[voice] AEROSENSE_FORCE_PYTTSX3: yalnizca pyttsx3.")
        return
    try:
        from PyQt5.QtTextToSpeech import QTextToSpeech  # noqa: F401
    except ImportError:
        print("[voice] Qt TextToSpeech modulu yok; pyttsx3 + Windows COM kullanilacak.")
        return
    bridge = _QtTtsBridge(app)
    app._aerosense_tts_bridge = bridge
    voice_service.attach_qt_tts(bridge.schedule_speak)
    print("[voice] TTS: Qt TextToSpeech (ana is parcacigi) baglandi.")


def run_gui(state, engine_holder, voice_service=None):
    from PyQt5.QtWidgets import QApplication

    _windows_pin_taskbar_icon()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("AeroSense AI")

    _voice_try_attach_qt_tts(app, voice_service)

    app_icon = _load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    splash, min_splash_ms = _create_splash_screen(app_icon)
    if splash is not None:
        splash.show()
        app.processEvents()

    f = QFont("Segoe UI", 10)
    if not f.exactMatch():
        f = QFont()
    app.setFont(f)

    elapsed_timer = QElapsedTimer()
    elapsed_timer.start()

    win = MainWindow(state, engine_holder, voice_service, app_icon=app_icon)
    win.resize(1420, 920)

    elapsed = elapsed_timer.elapsed()
    if splash is not None and elapsed < min_splash_ms:
        loop = QEventLoop()
        QTimer.singleShot(int(min_splash_ms - elapsed), loop.quit)
        loop.exec_()
        app.processEvents()

    win.show()
    if config.FULLSCREEN_DEFAULT:
        win.showFullScreen()
    if splash is not None:
        splash.finish(win)

    return app, win
