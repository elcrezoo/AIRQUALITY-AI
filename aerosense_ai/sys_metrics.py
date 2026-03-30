# -*- coding: utf-8 -*-
# AeroSense AI — CPU / RAM / GPU (yerel sistem)
# Telif © 2026 Enes Bozkurt | KBU Mekatronik 2026

"""Yerel sistem metrikleri: CPU/RAM için psutil veya Jetson'da tegrastats; GPU için de tegrastats (fallback: nvidia-smi)."""

from __future__ import unicode_literals

import os
import shutil
import subprocess
import sys
import threading
import time
import re


def sample_cpu_ram_percent(interval=0.05):
    """
    Canlı CPU ve RAM yüzdeleri.
    interval: psutil.cpu_percent için kısa örnekleme (ilk çağrıda 0 dönebilir).
    """
    # Jetson/L4T: psutil olmadan da CPU/RAM okunabilir.
    if sys.platform != "win32":
        try:
            _ensure_tegrastats_thread()
            cpu, ram = _tegrastats_get_cpu_ram_latest()
            if cpu is not None and ram is not None and (time.time() - _TEGRA_LAST_T) <= 5.5:
                return cpu, ram
        except Exception:
            pass

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
    """Tek giriş noktası: tegrastats (Jetson) -> nvidia-smi (fallback)."""
    if sys.platform != "win32":
        try:
            _ensure_tegrastats_thread()
            gpu_u, gpu_t = _tegrastats_get_gpu_latest()
            if gpu_u is not None and (time.time() - _TEGRA_LAST_T) <= 5.5:
                return gpu_u, gpu_t
        except Exception:
            pass
    return sample_gpu_nvidia_smi()


# -----------------------------
# Jetson tegrastats uyumluluğu
# -----------------------------

_TEGRA_LOCK = threading.Lock()
_TEGRA_CPU = None
_TEGRA_RAM = None
_TEGRA_GPU = None
_TEGRA_TEMP = None
_TEGRA_LAST_T = 0.0
_TEGRA_THREAD = None


def _parse_tegrastats_line(line):
    """
    tegrastats tek satırını parse eder.
    Sürüme göre alanlar değişebilir; bulunabilenleri döndürür.
    """
    if not line:
        return None, None, None, None

    cpu_avg = None
    ram_pct = None
    gpu_pct = None
    gpu_temp = None

    try:
        m = re.search(r"RAM\s+(\d+)\s*/\s*(\d+)MB", line)
        if m:
            used = float(m.group(1))
            total = float(m.group(2))
            if total > 0:
                ram_pct = (used / total) * 100.0
    except Exception:
        pass

    try:
        m = re.search(r"CPU\s+\[([^\]]+)\]", line)
        if m:
            core_parts = m.group(1).split(",")
            vals = []
            for part in core_parts:
                part = part.strip()
                mv = re.search(r"([\d.]+)\s*%?@", part) or re.search(r"([\d.]+)\s*%?", part)
                if mv:
                    vals.append(float(mv.group(1)))
            if vals:
                cpu_avg = sum(vals) / float(len(vals))
    except Exception:
        pass

    try:
        # GR3D_FREQ 12%@1300  => 12
        m = re.search(r"GR3D_FREQ\s+([\d.]+)", line)
        if m:
            gpu_pct = float(m.group(1))
    except Exception:
        pass

    try:
        m = re.search(r"GPU@([\d.]+)C", line)
        if m:
            gpu_temp = float(m.group(1))
    except Exception:
        pass

    try:
        if gpu_temp is None:
            m = re.search(r"Tboard\s+([\d.]+)C", line)
            if m:
                gpu_temp = float(m.group(1))
    except Exception:
        pass

    return cpu_avg, ram_pct, gpu_pct, gpu_temp


def _ensure_tegrastats_thread():
    """tegrastats'i bir kere arka planda çalıştır ve cache et."""
    global _TEGRA_THREAD
    if sys.platform == "win32":
        return
    if _TEGRA_THREAD is not None and _TEGRA_THREAD.is_alive():
        return
    if not shutil.which("tegrastats"):
        return

    def _worker():
        global _TEGRA_LAST_T, _TEGRA_CPU, _TEGRA_RAM, _TEGRA_GPU, _TEGRA_TEMP
        while True:
            try:
                cmd = ["tegrastats", "--interval", "1000"]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    universal_newlines=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    cpu_avg, ram_pct, gpu_pct, gpu_temp = _parse_tegrastats_line(line)
                    if cpu_avg is None and ram_pct is None and gpu_pct is None and gpu_temp is None:
                        continue
                    with _TEGRA_LOCK:
                        if cpu_avg is not None:
                            _TEGRA_CPU = cpu_avg
                        if ram_pct is not None:
                            _TEGRA_RAM = ram_pct
                        if gpu_pct is not None:
                            _TEGRA_GPU = gpu_pct
                        if gpu_temp is not None:
                            _TEGRA_TEMP = gpu_temp
                        _TEGRA_LAST_T = time.time()
            except Exception:
                # tegrastats izin / aygıt problemi olabilir; tekrar dene
                time.sleep(2.0)

    _TEGRA_THREAD = threading.Thread(
        target=_worker, name="aerosense-tegrastats", daemon=True
    )
    _TEGRA_THREAD.start()


def _tegrastats_get_cpu_ram_latest():
    with _TEGRA_LOCK:
        return _TEGRA_CPU, _TEGRA_RAM


def _tegrastats_get_gpu_latest():
    with _TEGRA_LOCK:
        return _TEGRA_GPU, _TEGRA_TEMP
