# -*- coding: utf-8 -*-
# AeroSense AI — yerel kullanıcı ayarları (Telegram vb.)
# Telif © 2026 Enes Bozkurt | KBU Mekatronik 2026

"""config/user_settings.json — GUI ve arka plan aynı dosyayı okur."""

from __future__ import unicode_literals

import json
import os

from . import config

DEFAULT_USER_SETTINGS = {
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_on_critical": True,
    "telegram_on_aqi_bad": True,
    "telegram_stream_enabled": False,
    "telegram_stream_interval_sec": 120,
}


def load_user_settings():
    """Tüm anahtarları döndür (varsayılanlar + dosya)."""
    data = dict(DEFAULT_USER_SETTINGS)
    path = config.USER_SETTINGS_JSON
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                blob = json.load(f)
            if isinstance(blob, dict):
                for k, v in blob.items():
                    if k in DEFAULT_USER_SETTINGS or k.startswith("telegram_"):
                        data[k] = v
        except (OSError, ValueError, TypeError):
            pass
    return data


def save_user_settings(updates):
    """Sözlükteki izinli alanları günceller, dosyaya yazar."""
    cur = load_user_settings()
    for k, v in updates.items():
        if k in DEFAULT_USER_SETTINGS or (isinstance(k, str) and k.startswith("telegram_")):
            cur[k] = v
    path = config.USER_SETTINGS_JSON
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        try:
            os.makedirs(d)
        except OSError:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)
    return cur
