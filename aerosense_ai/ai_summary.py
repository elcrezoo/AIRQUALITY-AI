# -*- coding: utf-8 -*-
"""
AI tarzinda ozet uretimi.

Not:
- Bu proje harici LLM kullanmiyor; "AI yorum" metni kural/tabanli ve log istatistiklerinden cikiyor.
- Daily CSV (data/logs/YYYY-MM-DD.csv) uzerinden "su saatte su oldu" seklinde olay cikartilir.
"""

from __future__ import unicode_literals

import csv
import os
import time
from datetime import datetime, timedelta

from . import config
from .ai.interpreter import build_alerts


def _parse_dt(ts_s):
    # daily_csv build_tablo_row: "%Y-%m-%d %H:%M:%S"
    try:
        return datetime.strptime(ts_s.strip(), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _to_float(s):
    try:
        if s is None:
            return None
        s = str(s).strip()
        if not s:
            return None
        v = float(s)
        # NaN'i ele
        if v != v:
            return None
        return v
    except Exception:
        return None


def _parse_anomali(v):
    s = (v or "").strip().lower()
    if s in ("evet", "true", "1", "yes"):
        return True
    return False


def _status_sev_order(tr_status):
    m = {"hata": 3, "uyari": 2, "saglikli": 1, "sagliklı": 1}
    return m.get((tr_status or "").strip().lower(), 0)


def _safe_slice(s, n=250):
    try:
        s = str(s)
    except Exception:
        s = ""
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"


def _load_daily_csv_rows(log_path, start_dt=None, end_dt=None):
    if not log_path or not os.path.isfile(log_path):
        return []

    out = []
    try:
        with open(log_path, "r", encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                dt = _parse_dt(row.get("tarih_saat") or "")
                if not dt:
                    continue
                if start_dt and dt < start_dt:
                    continue
                if end_dt and dt > end_dt:
                    continue
                # analize gore gerekli temel alanlar:
                out.append(
                    {
                        "dt": dt,
                        "genel_saglik": (row.get("genel_saglik") or "").strip(),
                        "aqi_seviye": (row.get("aqi_seviye") or "").strip(),
                        "aqi_indeks": _to_float(row.get("aqi_indeks")),
                        "guven_yuzde": _to_float(row.get("guven_yuzde")),
                        "anomali": _parse_anomali(row.get("anomali")),
                        "co_ppm_est": _to_float(row.get("co_tahmin_ppm")),
                        "nox_ppm_est": _to_float(row.get("nox_tahmin_ppm")),
                        "pm25_est": _to_float(row.get("pm25_tahmin")),
                        "temp_c": _to_float(row.get("sicaklik_c")),
                    }
                )
    except Exception:
        return []
    return out


def _iter_log_paths(start_dt, end_dt):
    # tum gunleri gez; daily csv: YYYY-MM-DD.csv
    if not start_dt or not end_dt:
        return []
    out = []
    day0 = start_dt.date()
    day1 = end_dt.date()
    d = day0
    while d <= day1:
        name = "%s.csv" % d.strftime("%Y-%m-%d")
        out.append(os.path.join(config.LOGS_DIR, name))
        d = d + timedelta(days=1)
    return out


def build_ai_summary_from_csv(mode, lang="tr", since_ts_unix=None, state=None):
    """
    mode:
      - "today": bugun 00:00 -> simdi
      - "uptime": program acilisindan itibaren simdi
      - "custom": since_ts_unix -> simdi
    """
    lang = lang if lang in ("tr", "en") else "tr"
    now = datetime.now()

    # start/end belirleme
    if mode == "today":
        start_dt = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_dt = now
        header = "Bugünlük"
    elif mode == "uptime":
        start_ts = time.time() - (state.uptime_seconds() if state else 0)
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = now
        header = "Bu ana kadar"
    else:
        start_ts = float(since_ts_unix or now.timestamp())
        start_dt = datetime.fromtimestamp(start_ts)
        end_dt = now
        header = "Özel aralık"

    rows = []
    for p in _iter_log_paths(start_dt, end_dt):
        rows.extend(_load_daily_csv_rows(p, start_dt=start_dt, end_dt=end_dt))

    rows.sort(key=lambda x: x.get("dt") or datetime.min)
    if not rows:
        if lang == "en":
            return {"summary_tr": "No log data found for this range.", "detail_tr": "", "stats": {}}
        return {"summary_tr": "Bu aralik icin log verisi bulunamadi.", "detail_tr": "", "stats": {}}

    # stats
    total = len(rows)
    overall_counts = {"Saglikli": 0, "Uyari": 0, "Hata": 0}
    anomaly_count = 0
    aqi_vals = []
    conf_vals = []
    co_vals = []
    nox_vals = []
    pm_vals = []
    temp_vals = []

    prev_overall = None
    prev_aqi_idx = None
    prev_anom = None
    key_moments = []  # (severity, dt, msg)

    def _mk_moment(sev, dt, msg):
        try:
            sev = int(sev)
        except Exception:
            sev = 0
        key_moments.append((sev, dt, msg))

    for it in rows:
        overall = it.get("genel_saglik") or ""
        overall_counts[overall] = overall_counts.get(overall, 0) + 1
        if it.get("anomali"):
            anomaly_count += 1
        ai = it.get("aqi_indeks")
        if ai is not None:
            aqi_vals.append(ai)
        cf = it.get("guven_yuzde")
        if cf is not None:
            conf_vals.append(cf)
        if it.get("co_ppm_est") is not None:
            co_vals.append(it.get("co_ppm_est"))
        if it.get("nox_ppm_est") is not None:
            nox_vals.append(it.get("nox_ppm_est"))
        if it.get("pm25_est") is not None:
            pm_vals.append(it.get("pm25_est"))
        if it.get("temp_c") is not None:
            temp_vals.append(it.get("temp_c"))

        # "su saatte su oldu" -> kritik degisim noktalarini yakala
        sev_ord = _status_sev_order(overall)
        if prev_overall is not None and overall != prev_overall:
            when = it["dt"].strftime("%H:%M:%S")
            _mk_moment(sev_ord or 1, it["dt"], "%s genel durum %s oldu" % (when, overall))

        if prev_anom is False and it.get("anomali") is True:
            when = it["dt"].strftime("%H:%M:%S")
            _mk_moment(3, it["dt"], "%s anomali tespiti (istatistiksel sapma)" % when)

        if prev_aqi_idx is not None and ai is not None:
            try:
                if abs(ai - prev_aqi_idx) >= 2.0:
                    when = it["dt"].strftime("%H:%M:%S")
                    _mk_moment(2, it["dt"], "%s AQI tahmini hızlı degisti (%.0f -> %.0f)" % (when, prev_aqi_idx, ai))
            except Exception:
                pass

        prev_overall = overall
        prev_aqi_idx = ai
        prev_anom = it.get("anomali")

    last = rows[-1]
    # Tahmin/uyari altyapisi: build_alerts
    last_est = {
        "co_ppm_est": last.get("co_ppm_est"),
        "nox_ppm_est": last.get("nox_ppm_est"),
        "pm25_est": last.get("pm25_est"),
        "temp_c": last.get("temp_c") if last.get("temp_c") is not None else 20,
    }
    alerts = build_alerts(last_est)

    # top anomali/aqi
    aqi_str = str(last.get("aqi_seviye") or "-")
    co_last = last.get("co_ppm_est")
    nox_last = last.get("nox_ppm_est")
    pm_last = last.get("pm25_est")
    temp_last = last.get("temp_c")

    # key moments secimi:
    # - severity'e gore oncelikle al, sonra dt’ye gore sirala
    key_moments.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked = key_moments[:4]
    picked.sort(key=lambda x: x[1])

    def _fmt(v, nd=1):
        if v is None:
            return "—"
        try:
            return (("%%.%df" % nd) % float(v)).rstrip("0").rstrip(".")
        except Exception:
            return "—"

    # oranlari hesapla:
    def _pct(n):
        try:
            return int(round((float(n) / float(total)) * 100.0))
        except Exception:
            return 0

    if lang == "en":
        summary = "AI summary (%s). " % header
        summary += "Total records: %d. "
        summary += "Overall: Healthy %d%%, Warning %d%%, Critical %d%%. " % (
            _pct(overall_counts.get("Saglikli", 0)),
            _pct(overall_counts.get("Uyari", 0)),
            _pct(overall_counts.get("Hata", 0)),
        )
        summary += "Anomaly detections: %d. " % anomaly_count
        summary += "Last AQI: %s. " % aqi_str
        summary += "Latest estimates: CO %s ppm, NOx %s ppm, PM2.5 %s, Temp %s°C. " % (
            _fmt(co_last),
            _fmt(nox_last),
            _fmt(pm_last, 1),
            _fmt(temp_last, 1),
        )
        if picked:
            detail_lines = []
            for _sev, dt, msg in picked:
                detail_lines.append("%s: %s" % (dt.strftime("%H:%M:%S"), msg))
            detail = "Highlights:\n" + "\n".join(detail_lines)
        else:
            detail = ""
        if alerts:
            detail = (detail + ("\n" if detail else "") + "Active alerts: " + "; ".join(["%s: %s" % (s, m) for s, m in alerts[:3]]))
        return {"summary_tr": summary, "detail_tr": detail, "stats": {"total": total}}

    # TR metin
    summary = "Özet (%s)\n" % header
    summary += "Toplam kayıt: %d\n" % total
    summary += "Genel durum: Sağlıklı %d%% · Uyarı %d%% · Hata %d%%\n" % (
        _pct(overall_counts.get("Saglikli", 0)),
        _pct(overall_counts.get("Uyari", 0)),
        _pct(overall_counts.get("Hata", 0)),
    )
    summary += "Anomali tespiti: %d kez\n" % anomaly_count
    summary += "Son tahmin: AQI=%s · Güven=%s%%\n" % (
        aqi_str,
        _fmt(last.get("guven_yuzde"), 0),
    )
    summary += "Tahmin ortam (son): CO=%s ppm, NOx=%s ppm, PM2.5=%s, Sıcaklık=%s°C\n" % (
        _fmt(co_last),
        _fmt(nox_last),
        _fmt(pm_last, 1),
        _fmt(temp_last, 1),
    )

    # öneriler:
    if alerts:
        top_alerts = alerts[:3]
        rec = ", ".join(["%s: %s" % (s, _safe_slice(m, 60)) for s, m in top_alerts])
    else:
        rec = "Aktif büyük bir uyari yok."

    detail_lines = []
    if picked:
        detail_lines.append("Öne çıkan anlar:")
        for _sev, dt, msg in picked:
            detail_lines.append("- %s" % msg)
    else:
        detail_lines.append("Öne çıkan anlar: belirgin degisim yok.")

    detail_lines.append("Yorum (AI): %s" % rec)
    if picked:
        # ek bilgi: en son genel durum
        detail_lines.append("Son durum: %s" % (last.get("genel_saglik") or "—"))

    # Event classifier (sadece simdiki an icin)
    if state:
        ev = state.get_event() or {}
        try:
            lbl = int(ev.get("event_label", -1))
            conf = float(ev.get("confidence", 0) or 0)
            name = ev.get("event_name") or str(lbl)
            if lbl in (1, 2, 3, 4):
                detail_lines.append("Şu anki olay sınıfı: %s (%.0f%%)" % (name, conf))
        except Exception:
            pass

    return {
        "summary_tr": summary.strip(),
        "detail_tr": "\n".join(detail_lines).strip(),
        "stats": {
            "total": total,
            "anomali": anomaly_count,
            "overall_counts": dict(overall_counts),
        },
    }

