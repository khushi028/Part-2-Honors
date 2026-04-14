"""
models/train_models.py
────────────────────────────────────────────────────────
Trains RandomForestRegressor models for CPU and GPU temperature
prediction using the TADR dataset (Mar–Dec 2021).

Features used:
    cpu, gpu, temp, prev_temp, delta_temp, hour_sin, hour_cos

Targets:
    streaming_cpu.pkl  → predicts CPU temperature at t+30 min
    streaming_gpu.pkl  → predicts GPU temperature at t+30 min

Usage:
    python models/train_models.py --data path/to/full_dataset_mar_dec_2021.csv
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import math
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

HORIZON = 30   # prediction horizon in minutes (rows, since 1-min intervals)


def build_features(df: pd.DataFrame) -> tuple:
    df = df.copy()
    df["prev_cpu_temp"]  = df["CPU Temperature (°C)"].shift(1)
    df["prev_gpu_temp"]  = df["GPU Temperature (°C)"].shift(1)
    df["delta_cpu_temp"] = df["CPU Temperature (°C)"] - df["prev_cpu_temp"]
    df["delta_gpu_temp"] = df["GPU Temperature (°C)"] - df["prev_gpu_temp"]

    ts = pd.to_datetime(df["timestamp"])
    hour = ts.dt.hour + ts.dt.minute / 60.0
    df["hour_sin"] = hour.apply(lambda h: math.sin(2 * math.pi * h / 24))
    df["hour_cos"] = hour.apply(lambda h: math.cos(2 * math.pi * h / 24))

    # Target: temperature HORIZON minutes ahead
    df["target_cpu"] = df["CPU Temperature (°C)"].shift(-HORIZON)
    df["target_gpu"] = df["GPU Temperature (°C)"].shift(-HORIZON)

    df.dropna(inplace=True)

    feature_cols = [
        "CPU consumption - Percentage (%)",
        "GPU consumption - Percentage (%)",
        "CPU Temperature (°C)",
        "GPU Temperature (°C)",
        "prev_cpu_temp",
        "prev_gpu_temp",
        "delta_cpu_temp",
        "delta_gpu_temp",
        "hour_sin",
        "hour_cos",
    ]

    X = df[feature_cols].values
    y_cpu = df["target_cpu"].values
    y_gpu = df["target_gpu"].values

    return X, y_cpu, y_gpu


def train_and_save(data_path: str, out_dir: str = "models"):
    print(f"📂 Loading dataset: {data_path}")
    df = pd.read_csv(data_path)
    print(f"   Rows: {len(df):,}")

    print("🔧 Building features …")
    X, y_cpu, y_gpu = build_features(df)
    print(f"   Feature matrix: {X.shape}")

    X_tr, X_te, yc_tr, yc_te, yg_tr, yg_te = train_test_split(
        X, y_cpu, y_gpu,   # parallel split keeping same indices
        test_size=0.15, random_state=42, shuffle=False   # time-ordered
    )

    # ── CPU model ────────────────────────────────────────────────────
    print("\n🌲 Training CPU temperature model …")
    cpu_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    cpu_model.fit(X_tr, yc_tr)
    yc_pred = cpu_model.predict(X_te)
    print(f"   MAE  = {mean_absolute_error(yc_te, yc_pred):.3f} °C")
    print(f"   R²   = {r2_score(yc_te, yc_pred):.4f}")

    cpu_path = os.path.join(out_dir, "streaming_cpu.pkl")
    joblib.dump(cpu_model, cpu_path)
    print(f"   ✅ Saved → {cpu_path}")

    # ── GPU model ────────────────────────────────────────────────────
    print("\n🌲 Training GPU temperature model …")
    gpu_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    gpu_model.fit(X_tr, yg_tr)
    yg_pred = gpu_model.predict(X_te)
    print(f"   MAE  = {mean_absolute_error(yg_te, yg_pred):.3f} °C")
    print(f"   R²   = {r2_score(yg_te, yg_pred):.4f}")

    gpu_path = os.path.join(out_dir, "streaming_gpu.pkl")
    joblib.dump(gpu_model, gpu_path)
    print(f"   ✅ Saved → {gpu_path}")

    print("\n🎉 Training complete. Models ready for controller/predictor.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to full dataset CSV")
    parser.add_argument("--out-dir", default="models", help="Output directory for .pkl files")
    args = parser.parse_args()
    train_and_save(args.data, args.out_dir)
