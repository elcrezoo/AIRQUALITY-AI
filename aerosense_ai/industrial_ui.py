# -*- coding: utf-8 -*-
# AeroSense AI — endüstriyel koyu tema sabitleri (mockup / tasarım dili)
# Telif © 2026 Enes Bozkurt | KBU Mekatronik 2026

"""PyQt5 + pyqtgraph için renk ve pyqtgraph arka plan ayarları."""

import pyqtgraph as pg

THEME = {
    "bg": "#080C18",
    "surface1": "#0E1428",
    "surface2": "#09102A",
    "border": "#1C2240",
    "text": "#DDE3F5",
    "text_muted": "#8B9BC4",
    "accent_cyan": "#00C8E0",
    "blue": "#4C8EF7",
    "green": "#22D3A5",
    "orange": "#F5A524",
    "red": "#F04343",
    "purple": "#9B72F5",
    "grid": "#1C2240",
}

# Kanal → mockup paleti
SENSOR_COLORS = {
    "sicaklik": THEME["blue"],
    "mq7": THEME["orange"],
    "mq135": THEME["green"],
    "toz": THEME["purple"],
}

# Türkçe AQI adı → (şerit+aksan hex, zemin üst, zemin alt) — yaklaşık eşleme
AQI_LEVEL_STYLES = {
    "İyi": (THEME["green"], "#0A1F14", "#080C18"),
    "iyi": (THEME["green"], "#0A1F14", "#080C18"),
    "Orta": (THEME["orange"], "#1C1A0A", "#080C18"),
    "orta": (THEME["orange"], "#1C1A0A", "#080C18"),
    "Hassas": (THEME["orange"], "#1C1A0A", "#080C18"),
    "Sağlıksız": (THEME["red"], "#1A0A0A", "#080C18"),
    "sagliksiz": (THEME["red"], "#1A0A0A", "#080C18"),
    "Kötü": (THEME["red"], "#1A0A0A", "#080C18"),
    "Tehlikeli": ("#8B00FF", "#150A1A", "#080C18"),
    "tehlikeli": ("#8B00FF", "#150A1A", "#080C18"),
}


def aqi_style_for_level(name):
    if not name:
        return THEME["accent_cyan"], THEME["surface1"], THEME["bg"]
    key = (name or "").strip()
    return AQI_LEVEL_STYLES.get(key, AQI_LEVEL_STYLES.get(key.lower(), (THEME["accent_cyan"], THEME["surface1"], THEME["bg"])))


def apply_pyqtgraph_theme():
    try:
        pg.setConfigOptions(antialias=True)
    except Exception:
        pass
    pg.setConfigOption("background", THEME["surface1"])
    pg.setConfigOption("foreground", THEME["text_muted"])
