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

"""Ham JSON sensorden dokumandaki ppm/PM/temp olceklerine kabaca esleme (kalibrasyon sonrasi guncellenir)."""


def _f(d, key, default=0.0):
    try:
        v = d.get(key)
        if v is None:
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def raw_to_estimates(raw):
    """
    verici.py: sicaklik (LM35 C), mq7/mq135 (V), toz (V).
    ppm/PM tahmini — sadece AQI kural motoru icin vekil olcek; kalibrasyon CSV ile iyilestirilir.
    """
    mq7 = _f(raw, "mq7")
    mq135 = _f(raw, "mq135")
    toz = _f(raw, "toz")
    temp = _f(raw, "sicaklik")
    if "temp_c" in raw:
        temp = _f(raw, "temp_c", temp)
    return {
        "temp_c": temp,
        "co_ppm_est": mq7 * 100.0,
        "nox_ppm_est": mq135 * 100.0,
        "pm25_est": toz * 50.0,
        "_raw": dict(raw),
    }


def feature_vector_from_raw(raw, feature_names):
    """Egitilmis model icin vektor (feature_names sirasi)."""
    row = []
    for name in feature_names:
        row.append(_f(raw, name, 0.0))
    return row
