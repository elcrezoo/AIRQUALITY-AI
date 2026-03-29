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

import json
import threading

try:
    from urllib2 import Request, urlopen
    from urllib2 import URLError, HTTPError
except ImportError:
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError


def _post_json(url, body_bytes, timeout_sec):
    req = Request(url, data=body_bytes, headers={"Content-Type": "application/json"})
    try:
        urlopen(req, timeout=timeout_sec).read()
    except (URLError, HTTPError, OSError, Exception):
        pass


def fire_webhooks_async(urls, payload_dict, timeout_sec=3):
    if not urls:
        return
    body = json.dumps(payload_dict).encode("utf-8")
    for u in urls:
        threading.Thread(
            target=_post_json,
            args=(u, body, timeout_sec),
            daemon=True,
        ).start()
