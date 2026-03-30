#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weak-labeling ile olay (event) dataseti üretir.

Hedef sınıflar (event_label):
  0: Normal
  1: Duman / Smoke
  2: Sigara
  3: Havasız (stale air)
  4: Kalabalık

Notlar:
- CO2 yoksa kalabalık/havasız ayrımı yalnızca proxy'lerle yapılır (MQ7/MQ135/toz + trend).
- Leakage olmaması için rolling özellikleri üretildikten sonra eşikler yalnızca train_part'tan hesaplanır.
"""

import argparse
import os
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd


LABELS = {
    0: "Normal",
    1: "Duman",
    2: "Sigara",
    3: "Havasız",
    4: "Kalabalık",
}


def _find_timestamp_col(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "Timestamp",
        "timestamp",
        "tarih_saat",
        "datetime",
        "dt",
        "t",
        "time",
        "date",
    ]
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _ensure_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _rolling_features(df: pd.DataFrame, window_size: int) -> pd.DataFrame:
    """
    window_size: kaç örnek üzerinden rolling yapılacağı.
    (receiver akışının frekansına göre 60 -> ~60 saniye varsayılır.)
    """
    cols = ["mq7", "mq135", "toz", "sicaklik"]
    for c in cols:
        if c not in df.columns:
            raise SystemExit(f"Gerekli kolon yok: {c}")

    feats = pd.DataFrame(index=df.index)

    for col in cols:
        feats[f"{col}_mean"] = df[col].rolling(window=window_size, min_periods=window_size).mean()
        feats[f"{col}_std"] = df[col].rolling(window=window_size, min_periods=window_size).std()
        # Slope: son (window_size//3) adımın farkını yaklaşık eğim gibi kullan.
        # scale veri setine göre değişebileceğinden slope eşikleri train'den türetilir.
        feats[f"{col}_slope"] = df[col].diff(periods=max(1, window_size // 3))

    return feats


def build_event_dataset(
    input_csv: str,
    output_csv: str,
    window_size: int = 60,
    train_ratio: float = 0.8,
    q_high_pm: float = 0.90,
    q_high_nox: float = 0.85,
    q_high_co: float = 0.85,
    stale_slope_abs_quantile: float = 0.20,
):
    if not os.path.isfile(input_csv):
        raise SystemExit(f"Input bulunamadı: {input_csv}")

    df = pd.read_csv(input_csv)

    # Kolonlar
    needed = ["mq7", "mq135", "toz", "sicaklik"]
    # Eğer farklı isim varsa kullanıcıyı zorlamadan çevirelim (opsiyonel)
    rename_map = {}
    aliases = {
        "temperature": "sicaklik",
        "temp": "sicaklik",
        "temp_c": "sicaklik",
        "MQ7": "mq7",
        "MQ135": "mq135",
        "PM25": "toz",
        "pm25": "toz",
    }
    for c in df.columns:
        lc = str(c).strip()
        if lc in needed:
            continue
        if lc in aliases:
            rename_map[c] = aliases[lc]
    if rename_map:
        df = df.rename(columns=rename_map)

    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise SystemExit(f"Inputta gerekli kolonlar yok: {missing}. Mevcut: {df.columns.tolist()}")

    df = _ensure_numeric(df, needed)

    # Zaman sıralaması (slope/leakage kontrolü için)
    ts_col = _find_timestamp_col(df)
    if ts_col:
        # timestamp bazı dosyalarda string olabilir
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        df = df.dropna(subset=[ts_col]).sort_values(ts_col).reset_index(drop=True)
    else:
        # Zaman yoksa index sırası varsayılır
        df = df.reset_index(drop=True)

    # Rolling özellikler
    feats = _rolling_features(df, window_size=window_size)

    # Rolling sonrası ilk satırlar NaN olacak; temizle
    feats = feats.dropna().copy()
    if len(feats) < 10:
        raise SystemExit("Rolling sonrası çok az satır kaldı. window_size çok büyük olabilir.")

    # Timestamp/ham değer taşımak istersen:
    ts_out: Optional[np.ndarray] = None
    if ts_col and ts_col in df.columns:
        # feats index'i df index'ini taşıdığı için aynı index'ten alabiliriz
        ts_out = df.loc[feats.index, ts_col].values

    # Zaman bazlı split (leakage önlemek için)
    n = len(feats)
    n_train = max(1, int(n * train_ratio))
    train_part = feats.iloc[:n_train]
    test_part = feats.iloc[n_train:]  # burada label üretsek bile eşikleri train'den alıyoruz

    # Train'den eşikler (leakage yok)
    q_high_pm_v = float(train_part["toz_mean"].quantile(q_high_pm))
    q_high_nox_v = float(train_part["mq135_mean"].quantile(q_high_nox))
    q_high_co_v = float(train_part["mq7_mean"].quantile(q_high_co))
    stale_slope_abs_thr = float(train_part["mq135_slope"].abs().quantile(stale_slope_abs_quantile))

    # Weak-label kuralları (vectorize)
    toz_mean = feats["toz_mean"]
    toz_slope = feats["toz_slope"]
    mq135_mean = feats["mq135_mean"]
    mq135_slope = feats["mq135_slope"]
    mq7_mean = feats["mq7_mean"]
    mq7_slope = feats["mq7_slope"]

    event_label = pd.Series(0, index=feats.index, dtype=np.int64)

    # 1) Duman / Smoke
    smoke_mask = (toz_mean > q_high_pm_v) & (toz_slope > 0)
    event_label = event_label.mask(smoke_mask, 1)

    # 2) Sigara
    # Sigara kuralı: mq135 yüksek + mq7 "hafif" yüksek + toz çok yüksek değil
    # (toz yüksek ise duman/smoke'a kaymasın diye)
    sigara_mask = (
        (mq135_mean > q_high_nox_v)
        & (mq7_mean > (q_high_co_v * 0.8))
        & (~smoke_mask)
    )
    event_label = event_label.mask(sigara_mask, 2)

    # 4) Kalabalık (proxy): VOC yüksek (mq135) + nefes proxy (mq7) yüksek + toz düşük/sınırlı
    # Kalabalık proxy'si: VOC (mq135) artışı ve "nefes" proxy'si (mq7) birlikte yükselmeli.
    # Böylece "havasız (durağan VOC)" örneklerini kalabalık 4'e yanlış çekmemiş oluyoruz.
    kalabalik_mask = (
        (mq135_mean > q_high_nox_v)
        & (mq7_mean > q_high_co_v)
        & (toz_mean < q_high_pm_v)
        & (mq135_slope > 0)
        & (mq7_slope > 0)
        & (~smoke_mask)
    )
    event_label = event_label.mask(kalabalik_mask, 4)

    # 3) Havasız (stale): VOC yüksek ama slope yatay (abs eğim küçük)
    havasiz_mask = (
        (mq135_mean > q_high_nox_v)
        & (mq135_slope.abs() <= stale_slope_abs_thr)
        & (toz_mean < q_high_pm_v)
        & (~smoke_mask)
        # Kalabalık zaten 4'e set edilmişse onu bozmak istemiyoruz.
        & (~kalabalik_mask)
    )
    event_label = event_label.mask(havasiz_mask, 3)

    # Çıktı
    out = feats.copy()
    out["event_label"] = event_label.astype(int)
    if ts_out is not None:
        out["Timestamp"] = pd.to_datetime(ts_out)

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    out.to_csv(output_csv, index=False)

    # Quick stats
    vc = out["event_label"].value_counts().sort_index().to_dict()
    print("Eşikler (train'den):")
    print(f"  q_high_pm(toz_mean)   = {q_high_pm_v:.6f}")
    print(f"  q_high_nox(mq135_mean)= {q_high_nox_v:.6f}")
    print(f"  q_high_co(mq7_mean)  = {q_high_co_v:.6f}")
    print(f"  stale_slope_abs_thr    = {stale_slope_abs_thr:.6f}")
    print("Event_label dağılımı:", {k: int(v) for k, v in vc.items()})
    print(f"Kaydedildi: {output_csv}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/sensor_log.csv")
    ap.add_argument("--output", default="data/models/aerosense_events_weaklabel.csv")
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--train_ratio", type=float, default=0.8)
    ap.add_argument("--q_high_pm", type=float, default=0.90)
    ap.add_argument("--q_high_nox", type=float, default=0.85)
    ap.add_argument("--q_high_co", type=float, default=0.85)
    ap.add_argument("--stale_slope_abs_quantile", type=float, default=0.20)
    args = ap.parse_args()

    build_event_dataset(
        input_csv=args.input,
        output_csv=args.output,
        window_size=args.window,
        train_ratio=args.train_ratio,
        q_high_pm=args.q_high_pm,
        q_high_nox=args.q_high_nox,
        q_high_co=args.q_high_co,
        stale_slope_abs_quantile=args.stale_slope_abs_quantile,
    )


if __name__ == "__main__":
    main()

