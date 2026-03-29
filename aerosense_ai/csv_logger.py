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

import csv
import os
import threading

from . import config


class CsvLogger(object):
    """Basliklari ilk satirda tutar; yeni kanal eklenirse yeni dosyaya gecer (eski yedeklenir)."""

    def __init__(self, path=None):
        self.path = path or config.CSV_PATH
        self._lock = threading.Lock()
        self._header = None

    def _ensure_header(self, row_keys):
        """row_keys: ['Timestamp'] + kanallar."""
        need_write = False
        with self._lock:
            if self._header is None and os.path.isfile(self.path):
                with open(self.path, "r", newline="") as f:
                    r = csv.reader(f)
                    try:
                        self._header = next(r)
                    except StopIteration:
                        self._header = None
            if self._header != row_keys:
                if self._header is not None and os.path.isfile(self.path):
                    bak = self.path + ".bak"
                    try:
                        if os.path.isfile(bak):
                            os.remove(bak)
                        os.rename(self.path, bak)
                    except OSError:
                        pass
                self._header = list(row_keys)
                need_write = True
            header = list(self._header)
        if need_write:
            with self._lock:
                with open(self.path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(header)
        return header

    def append(self, timestamp_str, values_by_channel, channel_order):
        row_keys = ["Timestamp"] + list(channel_order)
        self._ensure_header(row_keys)
        row = [timestamp_str] + [values_by_channel.get(k, "") for k in channel_order]
        with self._lock:
            with open(self.path, "a", newline="") as f:
                csv.writer(f).writerow(row)
