# -*- coding: utf-8 -*-

"""
Event classifier (weak-label) için runtime tahmin.
Veri: MQ7/MQ135/Toz/Sicaklik rolling pencere ozellikleri.
Model: data/models/event_classifier.joblib
"""

from __future__ import print_function

import os
import threading
import time

import pandas as pd

from . import config

try:
    import joblib
except Exception:
    joblib = None


EVENT_LABELS = {
    0: "Normal",
    1: "Duman/Smoke",
    2: "Sigara",
    3: "Havasız",
    4: "Kalabalık",
}


def _build_event_features(history_items, window_size):
    """
    history_items: SharedState.get_history(...) dönen liste
      her item: {"t": ..., "data": {...}}
    """
    cols = ["mq7", "mq135", "toz", "sicaklik"]

    rows = []
    for it in history_items:
        data = it.get("data") or {}
        ok = True
        r = {}
        for c in cols:
            v = data.get(c)
            if v is None:
                ok = False
                break
            r[c] = v
        if ok:
            rows.append(r)

    if len(rows) < window_size:
        return None

    df = pd.DataFrame(rows)
    # Rolling özellikleri (build_event_dataset ile aynı)
    feats = pd.DataFrame(index=df.index)
    slope_periods = max(1, window_size // 3)
    for col in cols:
        feats[col + "_mean"] = df[col].rolling(window=window_size, min_periods=window_size).mean()
        feats[col + "_std"] = df[col].rolling(window=window_size, min_periods=window_size).std()
        feats[col + "_slope"] = df[col].diff(periods=slope_periods)

    feats = feats.dropna()
    if feats.empty:
        return None
    return feats.iloc[-1]


class EventRuntime(object):
    def __init__(self):
        self._model = None
        self._feature_cols = None
        self._label_names = EVENT_LABELS
        self._window = int(config.EVENT_WINDOW)
        self._loaded = False

    def try_load(self):
        if self._loaded:
            return self._model is not None
        self._loaded = True
        if joblib is None:
            return False
        if not os.path.isfile(config.EVENT_MODEL_PATH):
            return False
        try:
            payload = joblib.load(config.EVENT_MODEL_PATH)
            if isinstance(payload, dict):
                self._model = payload.get("model")
                self._feature_cols = payload.get("feature_cols")
                self._label_names = payload.get("label_names") or EVENT_LABELS
            else:
                # eski/alternatif format
                self._model = payload
                self._feature_cols = None
            return self._model is not None
        except Exception:
            self._model = None
            self._feature_cols = None
            return False

    def predict_from_state(self, history_items):
        if not self.try_load():
            return None
        feats_row = _build_event_features(history_items, self._window)
        if feats_row is None:
            return None
        if self._feature_cols:
            # Eğitim script'inde seçilen feature sırası
            vec = feats_row[self._feature_cols].values.reshape(1, -1)
        else:
            vec = feats_row.values.reshape(1, -1)

        if hasattr(self._model, "predict_proba"):
            proba = self._model.predict_proba(vec)[0]
            pred = int(proba.argmax())
            conf = float(proba.max() * 100.0)
        else:
            pred = int(self._model.predict(vec)[0])
            conf = 0.0
            proba = None

        name = self._label_names.get(pred, str(pred))
        out = {
            "event_label": pred,
            "event_name": name,
            "confidence": round(conf, 1),
        }
        if proba is not None:
            try:
                out["proba"] = {int(i): float(p * 100.0) for i, p in enumerate(proba)}
            except Exception:
                pass
        return out


def start_event_classifier_thread(state, stop_event=None, interval_sec=2.0):
    stop_event = stop_event or threading.Event()
    rt = EventRuntime()

    def _loop():
        while state.running and not stop_event.is_set():
            try:
                # yeterli pencere için window*2 yeterli; bazı slope hesapları için biraz fazla olsun
                hist = state.get_history(max(200, rt._window * 2))
                ev = rt.predict_from_state(hist)
                if ev is not None:
                    state.set_event(ev)
            except Exception:
                pass
            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, name="aerosense-event-classifier", daemon=True)
    t.start()
    return t

