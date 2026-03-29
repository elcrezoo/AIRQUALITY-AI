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

"""
Dokuman Bolum 6.3 — AQI siniflari (0–5).
CO/NOx/PM2.5/temp tahminleri ile en kotu seviye secilir.
"""

AQI_LEVELS = {
    0: ("Iyi", "00E400", "Hava kalitesi iyi. Tum aktiviteler guvenli."),
    1: ("Orta", "FFFF00", "Hassas gruplar icin hafif risk."),
    2: ("Hassas", "FF7E00", "Hassas gruplar etkilenebilir."),
    3: ("Sagliksiz", "FF0000", "Herkes etkilenebilir; dis aktiviteleri sinirlayin."),
    4: ("Cok Kotu", "8F3F97", "Saglik uyarisi; disarida kalma suresini azaltin."),
    5: ("Tehlikeli", "7E0023", "Acil: disari cikmayin; hava temizleyici kullanin."),
}


def _co_level(co):
    if co <= 50:
        return 0
    if co <= 100:
        return 1
    if co <= 200:
        return 2
    if co <= 350:
        return 3
    if co <= 500:
        return 4
    return 5


def _nox_level(nox):
    if nox <= 40:
        return 0
    if nox <= 80:
        return 1
    if nox <= 150:
        return 2
    if nox <= 300:
        return 3
    if nox <= 500:
        return 4
    return 5


def _pm_level(pm):
    if pm <= 12:
        return 0
    if pm <= 35:
        return 1
    if pm <= 55:
        return 2
    if pm <= 150:
        return 3
    if pm <= 250:
        return 4
    return 5


def _temp_level(t):
    """Sicaklik ekstrem — dokuman araliklarinin disi uyarilir."""
    if 15 <= t <= 25:
        return 0
    if 25 < t <= 30 or 10 <= t < 15:
        return 1
    if 30 < t <= 35:
        return 2
    if 35 < t <= 40:
        return 3
    if 40 < t <= 45:
        return 4
    if t > 45 or t < 5:
        return 5
    return 1


def rule_based_aqi_index(estimates):
    co = estimates.get("co_ppm_est", 0)
    nox = estimates.get("nox_ppm_est", 0)
    pm = estimates.get("pm25_est", 0)
    temp = estimates.get("temp_c", 20)
    return max(
        _co_level(co),
        _nox_level(nox),
        _pm_level(pm),
        _temp_level(temp),
    )
