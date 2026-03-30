#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Event classifier training (weak-label) — MQ7/MQ135/toz rolling özelliklerinden.

Amaç:
- event_label (0..4) için çok sınıflı model eğitmek
- random split yerine zaman sıralı (holdout) split yapmak
- model ve feature listesi ile birlikte kaydetmek
"""

from __future__ import print_function

import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from aerosense_ai import config  # noqa: E402


LABEL_NAMES = {
    0: "Normal",
    1: "Duman/Smoke",
    2: "Sigara",
    3: "Havasız",
    4: "Kalabalık",
}


def _select_feature_cols(df):
    # event_label hedef; Timestamp'i özellik yapmıyoruz
    drop = {"event_label", "Timestamp"}
    cols = [c for c in df.columns if c not in drop]
    # sadece sayısal kolonlar
    cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    return cols


def _time_split(df, train_ratio=0.8):
    if "Timestamp" in df.columns:
        # Bazı datasetlerde Timestamp string gelebilir.
        dt = pd.to_datetime(df["Timestamp"], errors="coerce")
        df2 = df.copy()
        df2["_ts_ord"] = dt.astype("int64", errors="ignore")
        df2 = df2.sort_values("_ts_ord")
        df2 = df2.drop(columns=["_ts_ord"])
    else:
        df2 = df

    n = len(df2)
    n_train = max(1, int(n * train_ratio))
    train_df = df2.iloc[:n_train]
    test_df = df2.iloc[n_train:]
    return train_df, test_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--train_ratio", type=float, default=0.8)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    csv_path = args.csv
    if not os.path.isfile(csv_path):
        raise SystemExit("CSV bulunamadı: %s" % csv_path)

    out_path = args.out
    if not out_path:
        out_path = os.path.join(config.MODEL_DIR, "event_classifier.joblib")

    df = pd.read_csv(csv_path)
    if "event_label" not in df.columns:
        raise SystemExit("event_label kolonu yok. Dosya adı/şema kontrol et.")

    feature_cols = _select_feature_cols(df)
    if not feature_cols:
        raise SystemExit("Özellik kolonu bulunamadı.")

    df = df.copy()
    df["event_label"] = df["event_label"].astype(int)

    print("Dataset:", csv_path)
    print("Rows:", len(df))
    print("Features:", len(feature_cols), feature_cols[:8], "...")
    print("Class distribution:", df["event_label"].value_counts().sort_index().to_dict())

    train_df, test_df = _time_split(df, train_ratio=args.train_ratio)
    X_train = train_df[feature_cols].values
    y_train = train_df["event_label"].values
    X_test = test_df[feature_cols].values
    y_test = test_df["event_label"].values

    # Dengesizlik için class_weight destekli RF (sklearn bunu destekler)
    # label 0..4 olduğu için balanced weight hesaplamasını manuel de yapabiliriz,
    # burada class_weight='balanced' kullanıyoruz.
    clf = RandomForestClassifier(
        n_estimators=400,
        max_depth=18,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )

    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, pred))

    print("Holdout accuracy:", acc)

    payload = {
        "model": clf,
        "feature_cols": feature_cols,
        "label_names": LABEL_NAMES,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    joblib.dump(payload, out_path)
    print("Kaydedildi:", out_path)


if __name__ == "__main__":
    main()

