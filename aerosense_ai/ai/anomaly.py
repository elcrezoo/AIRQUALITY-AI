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

"""Isolation Forest (dosya) veya gecmis uzerinde basit z-skor anomali."""

import os

import numpy as np

from .. import config

try:
    import joblib
except ImportError:
    joblib = None


def _history_matrix(history_items, channels, max_rows=80):
    """Son N ornekten ozellik matrisi."""
    if not history_items or not channels:
        return None
    rows = []
    for it in history_items[-max_rows:]:
        d = it.get("data") or {}
        try:
            rows.append([float(d.get(c) or 0) for c in channels])
        except (TypeError, ValueError):
            continue
    if len(rows) < 5:
        return None
    return np.array(rows, dtype=np.float64)


def zscore_anomaly(current_vec, hist_matrix, sigma=3.0):
    if hist_matrix is None or len(hist_matrix) < 5:
        return False
    mu = np.mean(hist_matrix, axis=0)
    std = np.std(hist_matrix, axis=0) + 1e-9
    z = np.abs((current_vec - mu) / std)
    return bool(np.any(z > sigma))


class AnomalyDetector(object):
    def __init__(self):
        self._model = None
        self._scaler = None
        self._load()

    def _path(self):
        return config.ANOMALY_MODEL_PATH

    def _load(self):
        if joblib is None:
            return
        p = self._path()
        if not os.path.isfile(p):
            return
        try:
            bundle = joblib.load(p)
            if isinstance(bundle, dict):
                self._model = bundle.get("model") or bundle.get("iforest")
                self._scaler = bundle.get("scaler")
            else:
                self._model = bundle
        except Exception as e:
            print("[anomaly] Yukleme hatasi: %s" % e)

    def reload(self):
        self._model = None
        self._scaler = None
        self._load()

    def is_anomaly(self, latest, channels, history_items):
        chans = list(channels) if channels else list(latest.keys())
        if not chans:
            return False
        vec = np.array([float(latest.get(c) or 0) for c in chans], dtype=np.float64).reshape(1, -1)
        if self._model is not None:
            try:
                X = vec
                if self._scaler is not None:
                    X = self._scaler.transform(X)
                pred = self._model.predict(X)
                return pred[0] == -1
            except Exception:
                pass
        mat = _history_matrix(history_items or [], chans)
        if mat is None:
            return False
        return zscore_anomaly(vec.ravel(), mat)
