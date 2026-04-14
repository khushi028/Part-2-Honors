"""
worker/simulator.py
────────────────────────────────────────────────────────
Generates realistic CPU %, GPU %, and temperature readings
for a single simulated VM.  Includes:
  - diurnal load pattern (low at night, peaks at 9-11h & 14-17h)
  - random burst events (simulate academic / batch jobs)
  - physics-based temperature derived from load + ambient
  - occasional sustained-load spikes that push temp above threshold
"""

import random
import math
import time
from datetime import datetime


# ── Internal state per VM ────────────────────────────────────────────
class VMSimulator:
    def __init__(self, vm_id: str):
        self.vm_id       = vm_id
        self.prev_cpu    = 20.0
        self.prev_gpu    = 15.0
        self.prev_temp   = 45.0
        self.burst_ttl   = 0          # remaining minutes of burst
        self.burst_cpu   = 0.0
        self.burst_gpu   = 0.0

    # ── Diurnal base load ────────────────────────────────────────────
    def _diurnal_cpu(self) -> float:
        h = datetime.now().hour + datetime.now().minute / 60.0
        # Two peaks: ~10h and ~15h
        peak1 = 40 * math.exp(-((h - 10) ** 2) / 8)
        peak2 = 35 * math.exp(-((h - 15) ** 2) / 6)
        night = max(0, 10 - h) * 0.5 if h < 8 else 0
        return 8 + peak1 + peak2 + night

    # ── Burst event generator ────────────────────────────────────────
    def _maybe_trigger_burst(self):
        """1 % chance per tick to start a heavy burst (exam / render job)."""
        if self.burst_ttl <= 0 and random.random() < 0.01:
            self.burst_ttl  = random.randint(12, 40)   # ticks
            self.burst_cpu  = random.uniform(35, 55)
            self.burst_gpu  = random.uniform(25, 45)

        if self.burst_ttl > 0:
            self.burst_ttl -= 1
        else:
            # decay burst back to zero
            self.burst_cpu = max(0, self.burst_cpu - random.uniform(2, 5))
            self.burst_gpu = max(0, self.burst_gpu - random.uniform(1, 3))

    # ── Temperature model ─────────────────────────────────────────────
    @staticmethod
    def _compute_temp(cpu: float, gpu: float, prev_temp: float) -> float:
        """
        Physics-inspired thermal model:
          - Steady-state: linear + nonlinear component of load
          - Thermal lag: exponential moving average with prev_temp
          - Ambient ~ 25 °C
        """
        ambient  = 25.0
        load_avg = (cpu * 0.6 + gpu * 0.4)                 # weighted load
        ss_temp  = ambient + load_avg * 0.45 + (load_avg / 100) ** 2 * 15
        alpha    = 0.15                                      # thermal inertia
        new_temp = prev_temp + alpha * (ss_temp - prev_temp)
        return round(new_temp + random.gauss(0, 0.4), 2)

    # ── Main tick ────────────────────────────────────────────────────
    def tick(self) -> dict:
        self._maybe_trigger_burst()

        base_cpu = self._diurnal_cpu()
        raw_cpu  = base_cpu + self.burst_cpu + random.gauss(0, 3)
        raw_gpu  = base_cpu * 0.65 + self.burst_gpu + random.gauss(0, 4)

        # Smooth with previous value (no sudden jumps)
        cpu  = round(self.prev_cpu * 0.7 + raw_cpu * 0.3, 4)
        gpu  = round(self.prev_gpu * 0.7 + raw_gpu * 0.3, 4)
        cpu  = max(3.0, min(99.0, cpu))
        gpu  = max(3.0, min(95.0, gpu))

        temp = self._compute_temp(cpu, gpu, self.prev_temp)
        temp = max(38.0, min(95.0, temp))

        self.prev_cpu  = cpu
        self.prev_gpu  = gpu
        self.prev_temp = temp

        return {
            "vm_id":     self.vm_id,
            "cpu":       cpu,
            "gpu":       gpu,
            "temp":      temp,
            "timestamp": time.time(),
        }
