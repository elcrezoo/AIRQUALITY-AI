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
Uyumluluk katmani — sensor sagligi burada; AI motoru ai.pipeline.AeroSenseAI.
"""
import time

from . import config
from .ai.pipeline import AeroSenseAI

# Launcher / API eski import
AIEngine = AeroSenseAI


def _safe_float(d, key, default=0.0):
    try:
        v = d.get(key)
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def sensor_health_tr(latest, channels, last_unix_ts):
    """Kanal basina: ok / uyari / hata metni (dokuman 12.1 ile uyumlu)."""
    now = time.time()
    stale = (now - last_unix_ts) > config.STALE_SECONDS if last_unix_ts else True
    rows = []
    for ch in channels:
        val = latest.get(ch)
        rng = config.CHANNEL_HEALTH_RANGES.get(ch)
        status = "ok"
        msg = "Olculuyor"
        if stale or val is None:
            status = "hata"
            msg = "Veri bayat veya yok"
        elif rng is not None:
            lo, hi = rng
            if val < lo or val > hi:
                status = "uyari"
                msg = "Aralik disi (%.2f)" % val
            else:
                msg = "Normal (%.3f)" % val
        else:
            msg = "Deger %.3f" % float(val) if val is not None else "Bilinmiyor"
        rows.append({"channel": ch, "status": status, "message_tr": msg, "value": val})
    return rows
