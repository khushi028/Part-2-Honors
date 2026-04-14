"""
controller/decision.py
────────────────────────────────────────────────────────
Evaluates the current VM fleet state and returns one of:

    "SCHEDULE"  — redistribute tasks to cooler VMs
    "SCALE_OUT" — launch a new VM (AWS EC2 or simulated)
    "IDLE"      — no action required

─── Decision logic ───────────────────────────────────────
For each VM we have:
    pred_temp   — predicted temperature at t+horizon
    confidence  — how much to trust the prediction
    velocity    — °C/min thermal slope

A VM is considered "at risk" if ALL of:
    1. pred_temp  > CPU_TEMP_THRESHOLD  OR  temp > CPU_TEMP_THRESHOLD
    2. confidence >= CONFIDENCE_MIN     (prediction trustworthy)
    3. velocity   >= VELOCITY_SCHEDULE  (temperature is rising)

SCALE_OUT is chosen when:
    - at-risk VM count / total VM count  >= 0.5   AND
    - velocity on at least one VM        >= VELOCITY_SCALE  AND
    - confidence is high enough to act

SCHEDULE is chosen when:
    - at least one VM is at-risk
    - but not all VMs are at capacity (room to redistribute)

IDLE otherwise.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from config.config import (
    CPU_TEMP_THRESHOLD,
    CONFIDENCE_MIN,
    VELOCITY_SCHEDULE,
    VELOCITY_SCALE,
    CPU_CAPACITY_MAX,
)

log = logging.getLogger("decision")


def _score(vm: dict) -> float:
    """
    Lower score = better candidate to receive tasks.
    Combines current load, predicted temp, and confidence-weighted velocity.
    """
    pred      = vm.get("pred_temp",  vm["temp"])
    conf      = vm.get("confidence", 0.5)
    vel       = vm.get("velocity",   0.0)
    cpu       = vm.get("cpu",        50.0)

    # Penalise: hot VMs, high confidence of getting hotter, fast-rising VMs
    score = (cpu * 0.3
             + pred * 0.4
             + conf * vel * 10      # velocity weighted by how much we trust it
             )
    return round(score, 3)


def decision(vms: dict) -> str:
    if not vms:
        return "IDLE"

    at_risk_vms  = []
    cool_vms     = []

    for vm in vms.values():
        pred   = vm.get("pred_temp",  vm["temp"])
        conf   = vm.get("confidence", 0.0)
        vel    = vm.get("velocity",   0.0)
        temp   = vm["temp"]

        # Annotate score onto VM for scheduler to use
        vm["score"] = _score(vm)

        is_hot      = pred > CPU_TEMP_THRESHOLD or temp > CPU_TEMP_THRESHOLD
        trustworthy = conf >= CONFIDENCE_MIN
        rising      = vel  >= VELOCITY_SCHEDULE

        if is_hot and trustworthy and rising:
            at_risk_vms.append(vm)
        elif vm["cpu"] < CPU_CAPACITY_MAX:
            cool_vms.append(vm)

    n_total   = len(vms)
    n_at_risk = len(at_risk_vms)

    if n_at_risk == 0:
        log.debug("IDLE — no at-risk VMs")
        return "IDLE"

    # Check if fast-rising VMs dominate AND velocity is severe
    max_vel = max((v.get("velocity", 0.0) for v in at_risk_vms), default=0.0)
    frac_at_risk = n_at_risk / n_total

    if frac_at_risk >= 0.5 and max_vel >= VELOCITY_SCALE and not cool_vms:
        log.warning(
            "SCALE_OUT — %d/%d VMs at risk, max_velocity=%.3f°C/min",
            n_at_risk, n_total, max_vel,
        )
        return "SCALE_OUT"

    if cool_vms:
        log.info(
            "SCHEDULE — %d at-risk VMs, %d cool VMs available",
            n_at_risk, len(cool_vms),
        )
        return "SCHEDULE"

    # All VMs hot but not enough velocity to scale → still try schedule (warn)
    log.warning(
        "SCALE_OUT (all VMs hot) — %d/%d at risk, max_vel=%.3f",
        n_at_risk, n_total, max_vel,
    )
    return "SCALE_OUT"
