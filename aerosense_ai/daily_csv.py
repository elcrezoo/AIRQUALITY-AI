# -*- coding: utf-8 -*-

# ==============================================================================
# AeroSense AI — Günlük ölçüm tablosu (UTF-8 CSV, Excel uyumlu BOM)
# -----------------------------------------------------------------------------
# Telif (Copyright) © 2026 Enes Bozkurt. Tüm hakları saklıdır.
# Karabük Üniversitesi (KBU) — Mekatronik Mühendisliği — 2026
# ==============================================================================

"""data/logs/YYYY-MM-DD.csv — tarih, genel sağlık, AQI/AI tahminleri, kanal ölçüm ve durum."""

from __future__ import unicode_literals

import csv
import errno
import os
import shutil
import threading
import time
from datetime import datetime

from . import config

# CSV baska surec (Excel vb.) tarafindan kilitlendiginde konsola spam olmamasi icin
_last_csv_warn_ts = 0.0
_CSV_WARN_INTERVAL_SEC = 60.0


def _is_lock_or_permission(err):
    en = getattr(err, "errno", None)
    if en is None and getattr(err, "winerror", None) is not None:
        # WinError 32: dosya baska surec tarafindan kullaniliyor
        return err.winerror in (32, 5)
    return en in (errno.EACCES, errno.EPERM, 13)


def _warn_csv_once(path, err):
    global _last_csv_warn_ts
    now = time.monotonic()
    if now - _last_csv_warn_ts < _CSV_WARN_INTERVAL_SEC:
        return
    _last_csv_warn_ts = now
    print(
        "[daily_csv] Dosyaya yazilamadi (genelde Excel acikken): %s — %s"
        % (path, err)
    )


def _fmt_val(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Evet" if v else "Hayir"
    if isinstance(v, float):
        if v != v:
            return ""
        return ("%.4g" % v).replace("e", "E")
    return str(v)


def _status_tr(st):
    m = {"ok": "Saglikli", "uyari": "Uyari", "hata": "Hata"}
    return m.get((st or "").strip(), st or "")


def _genel_saglik_from_rows(health_rows):
    if not health_rows:
        return "Bilinmiyor"
    if any((r.get("status") or "") == "hata" for r in health_rows):
        return "Hata"
    if any((r.get("status") or "") == "uyari" for r in health_rows):
        return "Uyari"
    return "Saglikli"


def build_tablo_fieldnames(channels):
    base = [
        "tarih_saat",
        "genel_saglik",
        "aqi_seviye",
        "aqi_indeks",
        "guven_yuzde",
        "anomali",
        "co_tahmin_ppm",
        "nox_tahmin_ppm",
        "pm25_tahmin",
        "sicaklik_c",
    ]
    return base + ["olcum_%s" % c for c in channels] + ["durum_%s" % c for c in channels]


def build_tablo_row(timestamp_str, latest, channels, analysis, health_rows):
    by_ch = {r["channel"]: r for r in (health_rows or [])}
    row = {
        "tarih_saat": timestamp_str,
        "genel_saglik": _genel_saglik_from_rows(health_rows),
        "aqi_seviye": _fmt_val((analysis or {}).get("aqi_level", "")),
        "aqi_indeks": _fmt_val((analysis or {}).get("aqi_index", "")),
        "guven_yuzde": _fmt_val((analysis or {}).get("confidence", "")),
        "anomali": _fmt_val(bool((analysis or {}).get("is_anomaly"))),
        "co_tahmin_ppm": _fmt_val((analysis or {}).get("co_ppm_est", "")),
        "nox_tahmin_ppm": _fmt_val((analysis or {}).get("nox_ppm_est", "")),
        "pm25_tahmin": _fmt_val((analysis or {}).get("pm25_est", "")),
        "sicaklik_c": _fmt_val((analysis or {}).get("temp_c", "")),
    }
    for c in channels:
        row["olcum_%s" % c] = _fmt_val(latest.get(c, ""))
        st = (by_ch.get(c) or {}).get("status", "")
        row["durum_%s" % c] = _status_tr(st)
    return row


class DailyCsvLogger(object):
    def __init__(self, logs_dir=None):
        self.logs_dir = logs_dir or config.LOGS_DIR
        self._lock = threading.Lock()
        self._current_date = None
        self._path = None

    def _path_for_today(self):
        day = datetime.now().strftime("%Y-%m-%d")
        if day != self._current_date:
            self._current_date = day
            self._path = os.path.join(self.logs_dir, "%s.csv" % day)
        return self._path

    def _read_header_line(self, path):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return None
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                r = csv.reader(f)
                return next(r, None)
        except (OSError, StopIteration, UnicodeError):
            return None

    def _rotate_stale_file(self, path, fieldnames):
        hdr = self._read_header_line(path)
        if hdr is None:
            return
        if hdr == fieldnames:
            return
        bak = path[:-4] + "_eski_format.csv"
        n = 1
        while os.path.isfile(bak):
            bak = path[:-4] + "_eski_%s.csv" % n
            n += 1
        try:
            shutil.move(path, bak)
        except OSError:
            try:
                os.remove(path)
            except OSError:
                pass

    def append(self, timestamp_str, latest, channels, analysis, health_rows):
        """
        health_rows: sensor_health_tr listesi.
        Dönüş: GUI tamponu için satır kopyası.
        Dosya kilitliyse (Excel vb.) birkaç kez dener; yine olmazsa satır yine de
        döner — AI dongusu ve arayuz kesintiye ugramaz.
        """
        path = self._path_for_today()
        fieldnames = build_tablo_fieldnames(channels)
        row = build_tablo_row(timestamp_str, latest, channels, analysis, health_rows)
        out = dict(row)
        last_err = None
        for attempt in range(5):
            try:
                with self._lock:
                    os.makedirs(self.logs_dir, exist_ok=True)
                    if os.path.isfile(path) and os.path.getsize(path) > 0:
                        self._rotate_stale_file(path, fieldnames)
                    write_header = not os.path.isfile(path) or os.path.getsize(path) == 0
                    with open(path, "a", newline="", encoding="utf-8-sig") as f:
                        w = csv.DictWriter(
                            f, fieldnames=fieldnames, extrasaction="ignore"
                        )
                        if write_header:
                            w.writeheader()
                        w.writerow(row)
                return out
            except OSError as e:
                last_err = e
                if not _is_lock_or_permission(e):
                    _warn_csv_once(path, e)
                    return out
                time.sleep(0.12 * (attempt + 1))
        if last_err is not None:
            _warn_csv_once(path, last_err)
        return out
