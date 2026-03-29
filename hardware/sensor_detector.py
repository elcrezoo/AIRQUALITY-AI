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
Dokuman 3.5 — NI DAQ ile kanal kontrolu (PC, NI-DAQmx kurulu).
Jetson'da calismaz; active_sensors.json sablonu kullanilir.

  PYTHONPATH=. python3 hardware/sensor_detector.py
"""
from __future__ import print_function

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CONFIG_DIR = os.path.join(ROOT, "config")
OUT = os.path.join(CONFIG_DIR, "active_sensors.json")

# verici.py ile ayni kanal sirasi: ai0 sicaklik, ai1 mq7, ai2 mq135, ai3 toz
CHANNEL_KEYS = ["sicaklik", "mq7", "mq135", "toz"]
SENSOR_MAP = {
    "ai0": {"name": "LM35", "gas": "Temp", "unit": "C"},
    "ai1": {"name": "MQ-7", "gas": "CO", "unit": "V"},
    "ai2": {"name": "MQ-135", "gas": "NOx", "unit": "V"},
    "ai3": {"name": "DSM501A", "gas": "PM", "unit": "V"},
}


def detect_with_nidaqmx():
    import numpy as np
    import nidaqmx
    from nidaqmx.constants import TerminalConfiguration

    NOISE_THRESHOLD = 0.05
    active = {}
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(
            "Dev1/ai0:3",
            terminal_config=TerminalConfiguration.RSE,
            min_val=0.0,
            max_val=5.0,
        )
        raw = task.read(number_of_samples_per_channel=30)
        avg_v = [float(np.mean(channel)) for channel in raw]
    chans = list(SENSOR_MAP.keys())
    for i, daq_ch in enumerate(chans):
        if i >= len(avg_v):
            break
        if abs(avg_v[i]) > NOISE_THRESHOLD:
            meta = SENSOR_MAP[daq_ch]
            key = CHANNEL_KEYS[i]
            active[key] = {
                "name": meta["name"],
                "gas": meta["gas"],
                "unit": meta["unit"],
                "daq": daq_ch,
            }
    return active


def write_default():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    default = {
        "sicaklik": {"name": "LM35", "gas": "Temp", "unit": "C", "daq": "ai0"},
        "mq7": {"name": "MQ-7", "gas": "CO", "unit": "V", "daq": "ai1"},
        "mq135": {"name": "MQ-135", "gas": "NOx", "unit": "V", "daq": "ai2"},
        "toz": {"name": "DSM501A", "gas": "PM", "unit": "V", "daq": "ai3"},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(default, f, indent=2, ensure_ascii=False)
    print("[sensor_detector] Varsayilan: %s" % OUT)


def main():
    try:
        active = detect_with_nidaqmx()
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(active, f, indent=2, ensure_ascii=False)
        print("[sensor_detector] Algilanan: %s -> %s" % (list(active.keys()), OUT))
    except Exception as e:
        print("[sensor_detector] nidaqmx/okuma yok: %s" % e)
        write_default()


if __name__ == "__main__":
    main()
