"""
controller/state.py
────────────────────────────────────────────────────────
Single source of truth for VM registry and task queue.
Both are plain dicts/lists so controller components can
import and mutate them directly without extra coupling.

VM record schema (built up incrementally by controller):
{
    "vm_id":       str,
    "cpu":         float,   # current CPU %
    "gpu":         float,   # current GPU %
    "temp":        float,   # current temperature °C
    "prev_temp":   float,   # previous tick temperature (for velocity)
    "timestamp":   float,   # epoch of last update
    # ── added by predictor ──
    "pred_temp":   float,   # predicted temp at t+horizon
    "confidence":  float,   # 0-1 inverse-uncertainty confidence
    "velocity":    float,   # °C / min  (predicted thermal slope)
    # ── added by decision ──
    "score":       float,   # scheduling score (lower = prefer this VM)
}
"""

from typing import Dict, List, Any

# vm_id → vm_record
vms: Dict[str, Dict[str, Any]] = {}

# pending tasks (FIFO list, sorted by priority inside scheduler)
tasks: List[Dict[str, Any]] = []
