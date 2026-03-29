# -*- coding: utf-8 -*-
# AeroSense AI — Telegram Bot API bildirimi
# Telif © 2026 Enes Bozkurt | KBU Mekatronik 2026

"""Yerel HTTPS çağrısı (urllib); token/chat_id user_settings.json içinde."""

from __future__ import unicode_literals

import json
import sys
import time

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import user_settings

_last_send = (None, 0.0)  # (signature tuple, unix time)
_DEBOUNCE_SEC = 180.0

_last_channel_stream_ts = 0.0


def send_telegram_message(text, settings=None, require_enabled=True):
    """Ayarlar verilmezse dosyadan okunur. Başarı: True, aksi False.
    require_enabled=False: sadece token+chat yeterli (kanal akışı vb.)."""
    settings = settings or user_settings.load_user_settings()
    if require_enabled and not settings.get("telegram_enabled"):
        return False
    token = (settings.get("telegram_bot_token") or "").strip()
    chat = (settings.get("telegram_chat_id") or "").strip()
    if not token or not chat:
        return False
    body = json.dumps(
        {"chat_id": chat, "text": (text or "")[:4096], "disable_web_page_preview": True}
    )
    if sys.version_info[0] >= 3:
        body = body.encode("utf-8")
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=12)
        return True
    except (HTTPError, URLError, OSError):
        return False


def _is_bad_aqi(level):
    if not level:
        return False
    s = (level or "").strip().lower()
    bad = (
        "sağlıksız",
        "sagliksiz",
        "tehlikeli",
        "kötü",
        "kotu",
        "unhealthy",
        "hazardous",
        "poor",
    )
    return any(b in s for b in bad)


def maybe_alert_analysis(analysis, health_rows):
    """
    Sensör uyarısı veya kötü AQI için Telegram (aynı durum ~3 dk'da bir).
    """
    global _last_send
    s = user_settings.load_user_settings()
    if not s.get("telegram_enabled"):
        return

    reasons = []
    if s.get("telegram_on_critical", True):
        for row in health_rows or []:
            st = row.get("status") or ""
            if st in ("hata", "uyari"):
                reasons.append("%s:%s" % (row.get("channel", "?"), st))
    if s.get("telegram_on_aqi_bad", True) and analysis:
        lv = analysis.get("aqi_level")
        if _is_bad_aqi(lv):
            reasons.append("aqi:%s" % lv)

    if not reasons:
        return

    sig = tuple(sorted(reasons))
    now = time.time()
    prev_sig, prev_t = _last_send
    if prev_sig == sig and (now - prev_t) < _DEBOUNCE_SEC:
        return

    parts = ["⚠ AeroSense AI"]
    if analysis:
        parts.append("AQI: %s" % analysis.get("aqi_level", "—"))
        summ = (analysis.get("summary_tr") or "").strip()
        if summ:
            parts.append(summ[:800])
    for row in health_rows or []:
        if row.get("status") != "ok":
            parts.append(
                "%s · %s · %s"
                % (
                    row.get("channel", "?"),
                    row.get("status", "?"),
                    (row.get("message_tr") or "")[:200],
                )
            )
    msg = "\n".join(parts)[:4000]
    if send_telegram_message(msg, settings=s):
        _last_send = (sig, now)


def build_channel_stream_message(state):
    """Kanal için kısa durum metni (SharedState)."""
    from datetime import datetime

    latest, channels, _ts = state.get_latest()
    analysis = state.get_analysis()
    lines = []
    lines.append("📊 AeroSense AI")
    lines.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if analysis:
        aqi = analysis.get("aqi_level") or "—"
        idx = analysis.get("aqi_index")
        conf = analysis.get("confidence")
        idx_s = idx if idx is not None else "—"
        conf_s = conf if conf is not None else "—"
        lines.append("AQI: %s (idx %s) · Güven: %s%%" % (aqi, idx_s, conf_s))
        parts = []
        for key, fmt in (
            ("co_ppm_est", "CO~%.1f"),
            ("nox_ppm_est", "NOx~%.1f"),
            ("pm25_est", "PM~%.1f"),
        ):
            v = analysis.get(key)
            if v is not None:
                try:
                    parts.append(fmt % float(v))
                except (TypeError, ValueError):
                    parts.append("%s=%s" % (key, v))
        tc = analysis.get("temp_c")
        if tc is not None:
            try:
                parts.append("%.1f°C" % float(tc))
            except (TypeError, ValueError):
                pass
        if parts:
            lines.append(" · ".join(parts))
        summ = (analysis.get("summary_tr") or "").strip()
        if summ:
            lines.append(summ[:500])
    if channels and latest:
        raw_bits = []
        for c in channels[:12]:
            v = latest.get(c)
            if v is not None:
                try:
                    raw_bits.append("%s=%.3f" % (c, float(v)))
                except (TypeError, ValueError):
                    raw_bits.append("%s=%s" % (c, v))
        if raw_bits:
            lines.append("Ölçüm: " + " · ".join(raw_bits))
    return "\n".join(lines)[:4090]


def maybe_channel_stream(state, settings=None):
    """
    Kanala / gruba belirli aralıkla özet gönderir (chat_id = kanal -100... olabilir).
    Bot o kanalda mesaj gönderebilmeli (yönetici önerilir).
    """
    global _last_channel_stream_ts
    settings = settings or user_settings.load_user_settings()
    if not settings.get("telegram_stream_enabled"):
        return
    token = (settings.get("telegram_bot_token") or "").strip()
    chat = (settings.get("telegram_chat_id") or "").strip()
    if not token or not chat:
        return
    try:
        interval = int(settings.get("telegram_stream_interval_sec", 120))
    except (TypeError, ValueError):
        interval = 120
    interval = max(20, min(interval, 7200))
    now = time.time()
    if now - _last_channel_stream_ts < interval:
        return
    latest, _, _ = state.get_latest()
    analysis = state.get_analysis()
    if not latest and not analysis:
        return
    text = build_channel_stream_message(state)
    if send_telegram_message(text, settings=settings, require_enabled=False):
        _last_channel_stream_ts = now
