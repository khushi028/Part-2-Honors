"""
controller/main.py
────────────────────────────────────────────────────────
TADR System — main control loop.

Flow per tick:
  Kafka msg
      │
      ├─ vm-metrics  → update vms dict (also stores prev_temp)
      │
      └─ task-queue  → append to tasks list
                              │
                    ┌─────────▼──────────┐
                    │  predict per VM    │  pred_temp, confidence, velocity
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  decision()        │  SCHEDULE / SCALE_OUT / IDLE
                    └─────────┬──────────┘
                         ┌────┴────┐
                      SCHED    SCALE
                         │        │
                    scheduler  scaler
                         │
                    update prometheus
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
import time

from controller.consumer  import get_stream
from controller.predictor import predict
from controller.decision  import decision
from controller.scheduler import schedule
from controller.scaler    import scale_out
from controller.state     import vms, tasks
from monitoring.exporter  import start_prometheus, update_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("main")

# ── Config: set USE_AWS=True and fill config/config.py for real EC2 ──
USE_AWS = os.getenv("TADR_USE_AWS", "false").lower() == "true"

SCALE_COOLDOWN = 60   # seconds between scale-out events (avoid thrashing)
_last_scale_ts = 0.0


def main():
    global _last_scale_ts

    log.info("🟢 TADR Controller starting …")
    start_prometheus()
    log.info("📊 Prometheus exporter running")

    for topic, data in get_stream():

        # ── Ingest ───────────────────────────────────────────────────
        if topic == "vm-metrics":
            vm_id = data["vm_id"]
            if vm_id in vms:
                data["prev_temp"]     = vms[vm_id].get("temp",     data["temp"])
                data["prev_gpu_temp"] = vms[vm_id].get("gpu_temp", data.get("gpu_temp", data["temp"]))
            else:
                data["prev_temp"]     = data["temp"]
                data["prev_gpu_temp"] = data.get("gpu_temp", data["temp"])
            vms[vm_id] = data

        elif topic == "task-queue":
            tasks.append(data)
            log.debug("📋 Queued task %s (queue depth=%d)", data["task_id"], len(tasks))

        # ── Need at least one VM before running logic ─────────────────
        if not vms:
            continue

        # ── Predict ───────────────────────────────────────────────────
        for vm in vms.values():
            pred, conf, vel = predict(vm)
            vm["pred_temp"]  = pred
            vm["confidence"] = conf
            vm["velocity"]   = vel

        # ── Decide ────────────────────────────────────────────────────
        action = decision(vms)

        # ── Act ───────────────────────────────────────────────────────
        if action == "SCHEDULE" and tasks:
            remaining = schedule(tasks, vms)
            tasks.clear()
            tasks.extend(remaining)

        elif action == "SCALE_OUT":
            now = time.time()
            if now - _last_scale_ts >= SCALE_COOLDOWN:
                scale_out(vms, use_aws=USE_AWS)
                _last_scale_ts = now
            else:
                log.info(
                    "Scale-out suppressed (cooldown %.0fs remaining)",
                    SCALE_COOLDOWN - (now - _last_scale_ts),
                )

        # ── Monitor ───────────────────────────────────────────────────
        update_metrics(vms, tasks)


if __name__ == "__main__":
    main()
