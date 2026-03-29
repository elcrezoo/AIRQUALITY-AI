# -*- coding: utf-8 -*-
# AeroSense AI — CPU / RAM / GPU (yerel sistem)
# Telif © 2026 Enes Bozkurt | KBU Mekatronik 2026

"""psutil + isteğe bağlı nvidia-smi; Jetson için tegrastats denemesi yok (basit tutuldu)."""

from __future__ import unicode_literals

import os
import shutil
import subprocess
import sys


def sample_cpu_ram_percent(interval=0.05):
    """
    Canlı CPU ve RAM yüzdeleri.
    interval: psutil.cpu_percent için kısa örnekleme (ilk çağrıda 0 dönebilir).
    """
    try:
        import psutil

        cpu = float(psutil.cpu_percent(interval=interval))
        ram = float(psutil.virtual_memory().percent)
        return cpu, ram
    except Exception:
        return None, None


def sample_gpu_nvidia_smi():
    """
    NVIDIA sürücüsü varsa (util%, temp°C).
    Dönüş: (util 0-100 veya None, temp veya None)
    """
    exe = shutil.which("nvidia-smi")
    if not exe and sys.platform == "win32":
        for cand in (
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
            r"C:\Windows\System32\nvidia-smi.exe",
        ):
            if os.path.isfile(cand):
                exe = cand
                break
    if not exe:
        return None, None
    try:
        out = subprocess.check_output(
            [
                exe,
                "--query-gpu=utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=1.2,
            universal_newlines=True,
        )
        line = (out or "").strip().split("\n")[0].strip()
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            u = int(float(parts[0])) if parts[0] else None
            t = int(float(parts[1])) if parts[1] else None
            return u, t
    except Exception:
        pass
    return None, None


def sample_gpu_combined():
    """Tek giriş noktası: şimdilik NVIDIA."""
    return sample_gpu_nvidia_smi()
