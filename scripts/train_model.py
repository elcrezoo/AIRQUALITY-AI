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
AeroSense AI v2 — siniflandirici (0-5 AQI) + Isolation Forest anomali.
Cikti:
  data/models/aerosense_model.joblib  (model, scaler, feature_names)
  data/models/anomaly_iforest.joblib  (model, scaler)

Ornek:
  python3 scripts/train_model.py --csv data/sensor_log.csv --format aerosense
  python3 scripts/train_model.py --uci AirQualityUCI.csv --format uci
"""
from __future__ import print_function

import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aerosense_ai import config  # noqa: E402
from aerosense_ai.ai.aqi_classifier import rule_based_aqi_index  # noqa: E402
from aerosense_ai.ai.preprocessor import raw_to_estimates  # noqa: E402


def _labels_six_bins(df, col_names):
    """UCI / genel: kirilik skoruna gore 6 sinif."""
    X = df[col_names].values.astype(np.float64)
    scores = np.zeros(len(df))
    for j, _c in enumerate(col_names):
        col = X[:, j]
        med = np.nanmedian(col)
        mad = np.nanmedian(np.abs(col - med)) + 1e-6
        scores += (col - med) / mad
    qs = [16, 33, 50, 66, 83]
    edges = [np.percentile(scores, q) for q in qs]
    y = np.zeros(len(scores), dtype=np.int64)
    for i, s in enumerate(scores):
        y[i] = sum(s > e for e in edges)
    y = np.clip(y, 0, 5)
    return X, y


def train_aerosense_aqi6(csv_path):
    df = pd.read_csv(csv_path)
    drop = [c for c in ("Timestamp", "timestamp", "date") if c in df.columns]
    if drop:
        df = df.drop(columns=drop)
    feature_names = [c for c in df.columns if df[c].dtype.kind in "fiu"]
    if len(feature_names) < 2:
        raise SystemExit("Yetersiz sayisal sutun: %s" % list(df.columns))
    df = df.dropna(subset=feature_names)
    ys = []
    X_list = []
    for _, row in df.iterrows():
        d = {k: row[k] for k in feature_names}
        est = raw_to_estimates(d)
        ys.append(rule_based_aqi_index(est))
        X_list.append([float(row[k]) for k in feature_names])
    return np.array(X_list, dtype=np.float64), np.array(ys, dtype=np.int64), feature_names


def read_table_flexible(path):
    last_err = None
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(path, sep=sep)
            if df.shape[1] >= 3:
                return df
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return pd.read_csv(path)


def train_uci(csv_path):
    df = read_table_flexible(csv_path)
    df = df.replace(-200, np.nan)
    numeric = [c for c in df.columns if df[c].dtype.kind in "fiu"]
    if len(numeric) < 4:
        numeric = [
            c
            for c in df.columns
            if any(x in c.lower() for x in ("co", "nmhc", "nox", "pt08", "rh", "ah"))
        ]
    df = df[numeric].dropna()
    if len(df) < 100:
        raise SystemExit("UCI verisi yetersiz veya ayrac ; yerine , deneyin.")
    feature_names = list(df.columns)
    X, y = _labels_six_bins(df, feature_names)
    return X, y, feature_names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    ap.add_argument("--uci", default=None)
    ap.add_argument("--format", choices=("aerosense", "uci"), default="aerosense")
    args = ap.parse_args()

    if args.uci:
        path = args.uci
        fmt = "uci"
    elif args.csv:
        path = args.csv
        fmt = args.format
    else:
        default_csv = config.CSV_PATH
        if not os.path.isfile(default_csv):
            raise SystemExit("CSV verin: --csv veya once veri toplayin: %s" % default_csv)
        path = default_csv
        fmt = "aerosense"

    if fmt == "uci":
        X, y, names = train_uci(path)
    else:
        X, y, names = train_aerosense_aqi6(path)

    _, cnt = np.unique(y, return_counts=True)
    strat = y if np.all(cnt >= 2) and len(cnt) > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=strat
    )
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X_train_s, y_train)
    acc = clf.score(X_test_s, y_test)
    print("AQI siniflandirici dogruluk: %.4f" % acc)
    print("Ozellikler: %s" % names)

    iso = IsolationForest(
        contamination=0.05, n_estimators=200, random_state=42
    )
    iso.fit(X_train_s)

    os.makedirs(config.MODEL_DIR, exist_ok=True)
    joblib.dump(
        {"model": clf, "scaler": scaler, "feature_names": names},
        config.MODEL_PATH,
    )
    joblib.dump({"model": iso, "scaler": scaler}, config.ANOMALY_MODEL_PATH)
    print("Kaydedildi: %s" % config.MODEL_PATH)
    print("Anomali: %s" % config.ANOMALY_MODEL_PATH)


if __name__ == "__main__":
    main()
