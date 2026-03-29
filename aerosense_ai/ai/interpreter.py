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

"""Uyari listesi ve Turkce ozet."""

from .aqi_classifier import AQI_LEVELS


def build_alerts(estimates):
    alerts = []
    co = estimates.get("co_ppm_est", 0)
    nox = estimates.get("nox_ppm_est", 0)
    pm = estimates.get("pm25_est", 0)
    t = estimates.get("temp_c", 0)
    if co > 200:
        alerts.append(("KRITIK", "CO seviyesi yuksek; havalandirin."))
    elif co > 100:
        alerts.append(("UYARI", "CO artisi var."))
    if nox > 150:
        alerts.append(("UYARI", "NOx benzeri gaz sinyali yuksek."))
    if pm > 55:
        alerts.append(("UYARI", "Toz/partikul sinyali yuksek."))
    if t > 35:
        alerts.append(("BILGI", "Ortam sicakligi yuksek."))
    return alerts


def analysis_to_summary_tr(result):
    """Kisa satir: sesli geri bildirim + GUI."""
    level = result.get("aqi_level", "-")
    adv = result.get("advice", "")
    anom = result.get("is_anomaly", False)
    conf = result.get("confidence", 0)
    parts = ["Hava kalitesi: %s." % level]
    if anom:
        parts.append("Anomali tespiti.")
    parts.append("Guven: %%%.0f." % conf)
    parts.append(adv)
    alerts = result.get("alerts") or []
    for sev, msg in alerts[:2]:
        parts.append("%s: %s" % (sev, msg))
    return " ".join(parts)


def analysis_to_detail_tr(result):
    parts = [result.get("advice", "")]
    if result.get("ml_note"):
        parts.append(result["ml_note"])
    return " | ".join(p for p in parts if p)


def answer_query_tr(q, latest, analysis):
    """Basit anahtar kelime yaniti (JWT'siz dokuman uyumu)."""
    low = (q or "").lower()
    if not low.strip():
        return "Soru bos."
    if "co" in low and ("seviye" in low or "nedir" in low or "kac" in low):
        return "CO (tahmini): %.1f ppm esdegeri." % analysis.get("co_ppm_est", 0)
    if "saglik" in low or "sensor" in low:
        return analysis.get("summary_tr", "")
    if "uyari" in low or "alarm" in low:
        al = analysis.get("alerts") or []
        if not al:
            return "Aktif uyari yok."
        return "; ".join("%s: %s" % (a[0], a[1]) for a in al)
    if "hava" in low or "durum" in low or "aqi" in low:
        return analysis.get("summary_tr", "Veri yok.")
    return "Ornek sorular: hava durumu, CO seviyesi, uyarılar, sensör sağlığı."
