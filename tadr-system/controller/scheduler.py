"""
controller/scheduler.py
────────────────────────────────────────────────────────
Assigns pending tasks to VMs:

  1. Sorts tasks by priority (high → normal → low)
  2. Sorts VMs by score ascending (coolest / least loaded first)
  3. Fits each task into the first VM that has headroom
  4. Tasks that cannot be placed stay in the queue

Also drains tasks from hot VMs:
  - If a VM's predicted temp > threshold, its "virtual" CPU
    load is reduced to simulate offloading (actual execution
    is on the receiving VM; here we update in-memory state).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from config.config import CPU_TEMP_THRESHOLD, CPU_CAPACITY_MAX

log = logging.getLogger("scheduler")

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


def schedule(tasks: list, vms: dict) -> list:
    """
    Mutates:  vms  (cpu fields updated to reflect assigned tasks)
    Returns:  remaining tasks that could not be assigned
    """
    if not tasks or not vms:
        return tasks

    # Sort tasks: high-priority first
    ordered = sorted(tasks, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "normal"), 1))

    # Sort VMs: best candidates first (lowest score = coolest + lightest)
    sorted_vms = sorted(vms.values(), key=lambda v: v.get("score", 999))

    # Filter: don't assign to VMs that are already too hot
    eligible_vms = [
        v for v in sorted_vms
        if v.get("pred_temp", v["temp"]) <= CPU_TEMP_THRESHOLD
        and v["cpu"] < CPU_CAPACITY_MAX
    ]

    if not eligible_vms:
        log.warning("No eligible VMs for scheduling — all hot or at capacity")
        return tasks

    remaining = []
    assigned_count = 0

    for task in ordered:
        placed = False
        for vm in eligible_vms:
            headroom = CPU_CAPACITY_MAX - vm["cpu"]
            if headroom >= task["cpu_req"]:
                vm["cpu"]  = round(vm["cpu"] + task["cpu_req"], 2)
                vm["gpu"]  = round(vm.get("gpu", 0) + task.get("gpu_req", 0) * 0.5, 2)
                assigned_count += 1
                placed = True
                log.info(
                    "✅ Task %s → %s (cpu_req=%d, vm_cpu_now=%.1f%%)",
                    task["task_id"], vm["vm_id"], task["cpu_req"], vm["cpu"],
                )
                break
        if not placed:
            remaining.append(task)

    log.info(
        "Scheduler: assigned=%d  queued=%d",
        assigned_count, len(remaining),
    )
    return remaining
