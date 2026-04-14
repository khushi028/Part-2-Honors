"""
controller/predictor.py
────────────────────────────────────────────────────────
Loads pre-trained streaming models (RandomForest for CPU & GPU
temperatures) and produces:

  pred_temp  — predicted temperature at t + PREDICTION_HORIZON
  confidence — inverse-uncertainty confidence score  ∈ (0, 1]
  velocity   — estimated thermal rate of change  (°C / min)

─── Confidence derivation ───────────────────────────────
RandomForest gives per-tree predictions.  We treat the ensemble
as an approximation to p(y|x) ~ N(μ, σ²):

    μ  = mean of tree predictions
    σ  = std  of tree predictions  (ensemble variance proxy)

    confidence = 1 / (1 + σ)

"Higher disagreement among trees → larger σ → lower confidence."
This is the heuristic inverse-uncertainty mapping used in
trend-aware thermal control literature.

─── Velocity derivation ──────────────────────────────────
velocity = (pred_temp − current_temp) / horizon   [°C / min]

This is the estimated mean thermal slope over the prediction
horizon.  A positive velocity means the VM is heating up;
a high positive velocity triggers early scheduling/scaling.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
import numpy as np

try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False

from config.config import CPU_MODEL_PATH, GPU_MODEL_PATH, PREDICTION_HORIZON, N_ESTIMATORS

log = logging.getLogger("predictor")

# ── Load models once at import time ─────────────────────────────────
_cpu_model = None
_gpu_model = None

def _load_models():
    global _cpu_model, _gpu_model
    if not _JOBLIB:
        log.warning("joblib not available — using fallback heuristic predictor")
        return
    try:
        _cpu_model = joblib.load(CPU_MODEL_PATH)
        log.info("✅ Loaded CPU model from %s", CPU_MODEL_PATH)
    except FileNotFoundError:
        log.warning("CPU model not found at %s — using fallback", CPU_MODEL_PATH)
    try:
        _gpu_model = joblib.load(GPU_MODEL_PATH)
        log.info("✅ Loaded GPU model from %s", GPU_MODEL_PATH)
    except FileNotFoundError:
        log.warning("GPU model not found at %s — using fallback", GPU_MODEL_PATH)

_load_models()


# ── Feature vector ────────────────────────────────────────────────────
def _build_features(vm: dict) -> np.ndarray:
    import time, math
    hour       = (time.time() % 86400) / 3600
    cpu_temp   = vm["temp"]
    gpu_temp   = vm.get("gpu_temp", vm["temp"] * 1.05)   # fallback if not in stream
    prev_cpu   = vm.get("prev_temp", cpu_temp)
    prev_gpu   = vm.get("prev_gpu_temp", gpu_temp)
    delta_cpu  = cpu_temp - prev_cpu
    delta_gpu  = gpu_temp - prev_gpu
    return np.array([[
        vm["cpu"],                              # CPU consumption %
        vm["gpu"],                              # GPU consumption %
        cpu_temp,                               # CPU Temperature current
        gpu_temp,                               # GPU Temperature current
        prev_cpu,                               # prev_cpu_temp
        prev_gpu,                               # prev_gpu_temp
        delta_cpu,                              # delta_cpu_temp
        delta_gpu,                              # delta_gpu_temp
        math.sin(2 * math.pi * hour / 24),     # hour_sin
        math.cos(2 * math.pi * hour / 24),     # hour_cos
    ]])


# ── Fallback heuristic predictor (no model file) ─────────────────────
def _heuristic_predict(vm: dict):
    """
    If no model is available, use a simple physics-inspired heuristic:
      steady-state temp  = 25 + load * 0.45 + nonlinear term
      predicted temp     = EMA toward steady-state over horizon
    std is estimated from recent delta (proxy for uncertainty).
    """
    load   = vm["cpu"] * 0.6 + vm["gpu"] * 0.4
    ss     = 25 + load * 0.45 + (load / 100) ** 2 * 15
    alpha  = 1 - np.exp(-PREDICTION_HORIZON / 60)     # exponential approach
    pred   = vm["temp"] + alpha * (ss - vm["temp"])

    delta  = abs(vm["temp"] - vm.get("prev_temp", vm["temp"]))
    std    = max(0.5, delta * 2)                       # uncertainty proxy
    return pred, std


# ── Ensemble prediction ───────────────────────────────────────────────
def _ensemble_predict(model, X: np.ndarray):
    """
    Use individual tree estimators to compute mean and std.
    Works with sklearn RandomForest (estimators_ attribute).
    """
    if hasattr(model, "estimators_"):
        tree_preds = np.array([t.predict(X)[0] for t in model.estimators_])
        return tree_preds.mean(), tree_preds.std()
    else:
        # Fallback for other regressors
        pred = model.predict(X)[0]
        return pred, 1.5


# ── Public API ────────────────────────────────────────────────────────
def predict(vm: dict):
    """
    Returns:
        pred_temp  (float) — °C at t + PREDICTION_HORIZON
        confidence (float) — ∈ (0, 1]
        velocity   (float) — °C / min
    """
    X = _build_features(vm)

    if _cpu_model is not None:
        cpu_pred, cpu_std = _ensemble_predict(_cpu_model, X)
    else:
        cpu_pred, cpu_std = _heuristic_predict(vm)

    if _gpu_model is not None:
        gpu_pred, gpu_std = _ensemble_predict(_gpu_model, X)
    else:
        gpu_pred, _ = _heuristic_predict(vm)
        gpu_std     = cpu_std

    # Weighted combined predicted temperature
    pred_temp = round(cpu_pred * 0.6 + gpu_pred * 0.4, 2)

    # Combined std (conservative: take max)
    combined_std = max(cpu_std, gpu_std)

    # ── Confidence: inverse-uncertainty mapping ───────────────────────
    # confidence = 1 / (1 + σ)
    # Higher σ (disagreement) → lower confidence
    confidence = round(1.0 / (1.0 + combined_std), 4)

    # ── Velocity: estimated thermal slope over horizon ────────────────
    # velocity = (pred_temp − current_temp) / horizon   [°C / min]
    velocity = round((pred_temp - vm["temp"]) / PREDICTION_HORIZON, 4)

    log.debug(
        "%s | pred=%.1f°C  conf=%.3f  vel=%.3f°C/min",
        vm.get("vm_id", "?"), pred_temp, confidence, velocity,
    )

    return pred_temp, confidence, velocity
