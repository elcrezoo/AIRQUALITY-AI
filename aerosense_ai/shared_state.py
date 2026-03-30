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

from __future__ import unicode_literals

import threading
import time
from collections import deque

try:
    from collections.abc import Mapping
except ImportError:
    Mapping = dict


class SharedState(object):
    """Sensör verisi, AI metni ve geçmiş için iş parçacığı güvenli durum."""

    def __init__(self, history_max=600):
        self._lock = threading.RLock()
        self._boot_ts = time.time()
        self._latest = {}
        self._latest_ts = 0.0
        self._channels_order = list()
        self.ai_text_tr = u"Henuz veri yok; baglanti bekleniyor."
        self.ai_detail_tr = u""
        self._last_analysis = {}
        self.history_max = history_max
        # history_max <= 0 veya None ise "sınırsız" (deque maxlen'siz) sakla.
        # Not: bu durumda bellek büyüyebilir; gerçek kullanımda çok büyük bir değer daha güvenlidir.
        if history_max is None or history_max <= 0:
            self._history = deque()
        else:
            self._history = deque(maxlen=history_max)
        self._webhook_urls = []  # list of str
        self._running = True
        self._last_ai_duration_ms = 0.0
        self._data_log = deque(maxlen=50)
        self._last_event = {}  # event_label tahmini (weak-label classifier)

    def set_shutdown(self):
        with self._lock:
            self._running = False

    @property
    def running(self):
        with self._lock:
            return self._running

    def update_reading(self, payload_dict, channels_order):
        """payload_dict: json'dan gelen sayisal kanallar (timestamp yok)."""
        now = time.time()
        with self._lock:
            self._latest = dict(payload_dict)
            self._channels_order = list(channels_order)
            self._latest_ts = now
            snap = {"t": now, "data": dict(payload_dict)}
            self._history.append(snap)

    def get_latest(self):
        with self._lock:
            return (
                dict(self._latest),
                list(self._channels_order),
                float(self._latest_ts),
            )

    def get_history(self, n):
        with self._lock:
            items = list(self._history)
        if n and n < len(items):
            return items[-n:]
        return items

    def set_ai(self, text, detail=u""):
        with self._lock:
            self.ai_text_tr = text
            self.ai_detail_tr = detail or u""

    def get_ai(self):
        with self._lock:
            return self.ai_text_tr, self.ai_detail_tr

    def set_analysis(self, result_dict):
        with self._lock:
            self._last_analysis = dict(result_dict) if result_dict else {}

    def get_analysis(self):
        with self._lock:
            return dict(self._last_analysis)

    def uptime_seconds(self):
        return time.time() - self._boot_ts

    def add_webhook(self, url):
        url = (url or u"").strip()
        if not url:
            return False
        with self._lock:
            if url not in self._webhook_urls:
                self._webhook_urls.append(url)
        return True

    def remove_webhook(self, url):
        with self._lock:
            if url in self._webhook_urls:
                self._webhook_urls.remove(url)
                return True
        return False

    def list_webhooks(self):
        with self._lock:
            return list(self._webhook_urls)

    def set_ai_timing_ms(self, ms):
        with self._lock:
            try:
                self._last_ai_duration_ms = float(ms)
            except (TypeError, ValueError):
                self._last_ai_duration_ms = 0.0

    def get_ai_timing_ms(self):
        with self._lock:
            return float(self._last_ai_duration_ms)

    def push_data_log_row(self, row_dict):
        """Son kayıtlar tamponu (masaüstü Veri günlüğü tablosu)."""
        if not row_dict:
            return
        with self._lock:
            self._data_log.append(dict(row_dict))

    def get_data_log_rows(self):
        with self._lock:
            return list(self._data_log)

    def set_event(self, event_dict):
        with self._lock:
            self._last_event = dict(event_dict) if event_dict else {}

    def get_event(self):
        with self._lock:
            return dict(self._last_event)


def merge_channel_order(payload_keys, preferred_order):
    """Bilinen sira + kalan anahtarlar alfabetik."""
    keys = set(payload_keys)
    ordered = [k for k in preferred_order if k in keys]
    rest = sorted(keys - set(ordered))
    return ordered + rest
