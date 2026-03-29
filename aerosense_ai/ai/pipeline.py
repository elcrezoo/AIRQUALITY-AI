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

import os

import numpy as np

from .. import config
from .anomaly import AnomalyDetector
from .aqi_classifier import AQI_LEVELS, rule_based_aqi_index
from .interpreter import analysis_to_detail_tr, analysis_to_summary_tr, build_alerts
from .preprocessor import feature_vector_from_raw, raw_to_estimates

try:
    import joblib
except ImportError:
    joblib = None


class AeroSenseAI(object):
    """Dokuman 4.2.2 — analiz koordinatoru."""

    def __init__(self):
        self._model = None
        self._scaler = None
        self._feature_names = None
        self._anomaly = AnomalyDetector()
        self._load_classifier()

    def _load_classifier(self):
        if joblib is None:
            return
        if os.path.isfile(config.MODEL_PATH):
            try:
                bundle = joblib.load(config.MODEL_PATH)
                if isinstance(bundle, dict):
                    self._model = bundle.get("model")
                    self._scaler = bundle.get("scaler")
                    self._feature_names = bundle.get("feature_names")
                else:
                    self._model = bundle
            except Exception as e:
                print("[ai] Siniflandirici yuklenemedi: %s" % e)
        if self._scaler is None and os.path.isfile(config.SCALER_PATH):
            try:
                self._scaler = joblib.load(config.SCALER_PATH)
            except Exception:
                pass

    def reload_model(self):
        self._model = None
        self._scaler = None
        self._feature_names = None
        self._anomaly.reload()
        self._load_classifier()

    def analyze(self, latest, channels, history_items=None):
        history_items = history_items or []
        est = raw_to_estimates(latest)
        alerts = build_alerts(est)
        is_anomaly = self._anomaly.is_anomaly(latest, channels, history_items)

        ml_note = ""
        confidence = 72.0
        aqi_idx = rule_based_aqi_index(est)

        if self._model is not None and self._feature_names:
            try:
                vec = np.array(
                    [feature_vector_from_raw(latest, self._feature_names)],
                    dtype=np.float64,
                )
                X = vec
                if self._scaler is not None:
                    X = self._scaler.transform(X)
                pred = self._model.predict(X)[0]
                aqi_idx = int(np.clip(int(pred), 0, 5))
                if hasattr(self._model, "predict_proba"):
                    pr = self._model.predict_proba(X)[0]
                    confidence = float(np.max(pr) * 100.0)
                ml_note = "ML sinif: %s" % aqi_idx
            except Exception as e:
                ml_note = "ML hata: %s" % e

        if is_anomaly:
            alerts = [("UYARI", "Istatistiksel anomali")] + list(alerts)

        name, color, advice = AQI_LEVELS.get(aqi_idx, AQI_LEVELS[0])
        level_name = name

        result = {
            "aqi_index": aqi_idx,
            "aqi_level": level_name,
            "color_hex": color,
            "is_anomaly": is_anomaly,
            "confidence": round(confidence, 1),
            "advice": advice,
            "alerts": alerts,
            "summary_tr": "",
            "co_ppm_est": est["co_ppm_est"],
            "nox_ppm_est": est["nox_ppm_est"],
            "pm25_est": est["pm25_est"],
            "temp_c": est["temp_c"],
            "ml_note": ml_note,
        }
        result["summary_tr"] = analysis_to_summary_tr(result)
        result["detail_tr"] = analysis_to_detail_tr(result)
        return result

    def predict_tr(self, latest, channels, history_items=None):
        if not latest:
            return "Veri yok.", ""
        r = self.analyze(latest, channels, history_items)
        return r["summary_tr"], r["detail_tr"]
