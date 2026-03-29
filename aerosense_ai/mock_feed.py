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

"""TX2/verici olmadan arayuz demosu icin sahte sensor akisi."""
from __future__ import print_function

import math
import threading
import time

from . import config
from .shared_state import merge_channel_order


def start_mock_feed_thread(state, stop_event, interval_sec=1.0):
    """sicaklik, mq7, mq135, toz icin periyodik ornekler yazar."""

    def loop():
        t0 = time.time()
        while state.running and not stop_event.is_set():
            t = time.time() - t0
            payload = {
                "sicaklik": 22.0 + 4.0 * math.sin(t * 0.25),
                "mq7": 1.15 + 0.55 * math.sin(t * 0.6),
                "mq135": 1.4 + 0.45 * math.cos(t * 0.45),
                "toz": 1.05 + 0.6 * abs(math.sin(t * 0.35)),
            }
            ch_order = merge_channel_order(payload.keys(), config.CHANNEL_ORDER)
            state.update_reading(payload, ch_order)
            time.sleep(interval_sec)

    th = threading.Thread(target=loop, name="aerosense-mock-feed", daemon=True)
    th.start()
    return th
